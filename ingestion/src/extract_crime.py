"""
extract_crime.py - Ministry of Interior news  ->  star-schema-ready JSON (one record per article).

Run from the src folder (next to .env):
    python3 extract_crime.py                        # every page_*.json found next to this script (or in ./data)
    python3 extract_crime.py --input DIR_OR_FILE    # a pages folder, or one .json / .jsonl file
        accepted article shapes: page_*.json (news_id, full_text_raw, api_payload) and
        bronze_crime_all_news.json (news_id, title, full_details, date_published, source_url, image_url, ...)
    python3 extract_crime.py --sample 20            # 20 random articles (best way to test the prompt)
    python3 extract_crime.py --limit 20 --workers 2
    python3 extract_crime.py --redo                 # ignore earlier results and start the output files fresh

Team split (every member runs a different slice of the SAME input file, with their own API key):
    python3 extract_crime.py --part 3/6             # 3rd of 6 equal slices
    python3 extract_crime.py --range 1001-2000      # articles 1001..2000 (1-based, inclusive)
  Slice results go to results/extracted_<start>-<end>.jsonl(.json) so nobody overwrites anybody.
  Afterwards: python3 merge_results.py  (joins every file in results/ into one).
  On Windows use `python` instead of `python3`.

Output (next to this script):
    extracted_news.jsonl   one record per line, appended as it goes (so a stopped run can resume)
    extracted_news.json    the same records as one pretty JSON array (rebuilt at the end of each run)
    errors.jsonl           articles that failed

Each record mirrors the ERD (crime_erd_fields_with_types.json):
    dim_news          <- scraper fields (id, title, publication date, image, ingested_at)        [no LLM]
    dim_date          <- derived from the publish date                                           [no LLM]
    dim_location      <- LLM (governorate, city, police_station, location_text) + region/country by lookup
    dim_crime_type    <- LLM (crime_category, crime_subcategory, crime_type, description)
    secondary_crimes  <- LLM (extra offences in the same article; optional, ignore if you don't need it)
    dim_event         <- LLM (event_type, event_description)
    persons[]         <- LLM: person_role + count (BRIDGE_INCIDENT_PERSON), gender, description, residence_governorate
    items[]           <- LLM: DIM_ITEM columns + quantity / unit / quantity_note / status (BRIDGE_INCIDENT_ITEM)
    fact_incident     <- LLM counts / financial_value / legal_action / investigation_status / description
                         + seized_item_count, is_criminal_incident, incident_count and incident_date computed here
v4 (after the team's null analysis): dropped district, age, occupation, has_criminal_record from the LLM output
(they were almost always empty), added incident_date (resolved in code), quantity_note, no more invented zeros.
Provider: Groq by default; set LLM_BASE_URL + LLM_API_KEY + LLM_MODEL in .env to use any OpenAI-compatible API.
Surrogate keys (news_key, location_key, ...) are NOT created here - the warehouse load does that.
"""

import argparse
import collections
import hashlib
import json
import math
import os
import random
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from threading import Event, Lock

from dotenv import load_dotenv
from openai import (
    APIConnectionError,
    APITimeoutError,
    BadRequestError,
    InternalServerError,
    OpenAI,
    RateLimitError,
)

for _stream in (sys.stdout, sys.stderr):  # Windows consoles: print Arabic without crashing
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        pass

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(dotenv_path=BASE_DIR / ".env")

MODEL = os.getenv("LLM_MODEL", "openai/gpt-oss-120b")
REASONING_EFFORT = os.getenv("REASONING_EFFORT", "low")  # low | medium | high  (lower = fewer tokens)
BASE_URL = os.getenv("LLM_BASE_URL", "https://api.groq.com/openai/v1")
PROMPT_VERSION = "v4"

OUTPUT_JSONL = BASE_DIR / "extracted_news.jsonl"
OUTPUT_JSON = BASE_DIR / "extracted_news.json"
ERRORS_FILE = BASE_DIR / "errors.jsonl"

# ----------------------------------------------------------------------------
# Controlled vocabularies (English codes; the prompt explains each one)
# ----------------------------------------------------------------------------
UNKNOWN_GOV = "غير محدد"
GOVERNORATES = [
    "القاهرة", "الجيزة", "الإسكندرية", "القليوبية", "الدقهلية", "الشرقية", "الغربية",
    "المنوفية", "البحيرة", "كفر الشيخ", "دمياط", "بورسعيد", "الإسماعيلية", "السويس",
    "شمال سيناء", "جنوب سيناء", "الفيوم", "بني سويف", "المنيا", "أسيوط", "سوهاج", "قنا",
    "الأقصر", "أسوان", "البحر الأحمر", "الوادي الجديد", "مطروح", UNKNOWN_GOV,
]
REGION_BY_GOV = {}
for _region, _govs in {
    "القاهرة الكبرى": ["القاهرة", "الجيزة", "القليوبية"],
    "الإسكندرية والساحل الشمالي": ["الإسكندرية", "مطروح"],
    "الدلتا": ["الدقهلية", "الشرقية", "الغربية", "المنوفية", "البحيرة", "كفر الشيخ", "دمياط"],
    "القناة": ["بورسعيد", "الإسماعيلية", "السويس"],
    "الصعيد": ["الفيوم", "بني سويف", "المنيا", "أسيوط", "سوهاج", "قنا", "الأقصر", "أسوان", "الوادي الجديد"],
    "سيناء والبحر الأحمر": ["شمال سيناء", "جنوب سيناء", "البحر الأحمر"],
}.items():
    for _g in _govs:
        REGION_BY_GOV[_g] = _region
COUNTRY = "مصر"

EVENT_TYPES = [
    "viral_claim_investigation", "arrest_operation", "armed_clash", "rumor_denial",
    "enforcement_campaign", "administrative", "other",
]
CRIME_CATEGORIES = [
    "drugs", "fraud", "theft_robbery", "violence_assault", "homicide", "weapons_firearms",
    "kidnapping_extortion", "financial_crimes", "commercial_fraud_supply", "antiquities",
    "juvenile_exploitation", "traffic_accident", "false_news_cyber", "missing_person",
    "other_crime", "non_criminal",
]
PERSON_ROLES = ["suspect", "victim", "complainant", "publisher", "witness", "official", "other"]
GENDERS = ["male", "female", "unknown"]
ITEM_CATEGORIES = [
    "weapon", "ammunition", "drugs", "phones_electronics", "cash_valuables", "cards_wallets",
    "vehicle", "goods_commodities", "tools_equipment", "animal", "other",
]
ITEM_STATUSES = ["seized", "recovered", "stolen", "impounded", "unknown"]
INVESTIGATION_STATUSES = [
    "court_ruling", "detained_pending_investigation", "prosecution_investigating",
    "legal_action_taken", "not_stated",
]
QUANTITY_NOTES = ["none", "more_than", "about"]
FINANCIAL_BASES = [
    "none", "seized_goods_value", "laundered_amount", "currency_trade_value",
    "fraud_theft_amount", "other",
]

# ----------------------------------------------------------------------------
# JSON schema (strict: every property required, no extra properties)
# ----------------------------------------------------------------------------
STR = {"type": "string"}
N_STR = {"type": ["string", "null"]}
N_INT = {"type": ["integer", "null"]}
N_NUM = {"type": ["number", "null"]}
N_BOOL = {"type": ["boolean", "null"]}


def _obj(**props):
    return {"type": "object", "properties": props, "required": list(props), "additionalProperties": False}


def _enum(*values):
    return {"type": "string", "enum": list(values)}


def _arr(item):
    return {"type": "array", "items": item}


LOCATION = _obj(
    governorate=_enum(*GOVERNORATES), city=N_STR, police_station=N_STR, location_text=N_STR,
)
RESIDENCE = _obj(governorate=_enum(*GOVERNORATES))

SCHEMA = _obj(
    event=_obj(event_type=_enum(*EVENT_TYPES), event_description=STR),
    location=LOCATION,
    crime=_obj(
        crime_category=_enum(*CRIME_CATEGORIES), crime_subcategory=STR, crime_type=STR, description=N_STR,
    ),
    secondary_crimes=_arr(_obj(crime_category=_enum(*CRIME_CATEGORIES), crime_type=STR)),
    persons=_arr(_obj(
        role=_enum(*PERSON_ROLES), count=N_INT, person_description=STR, gender=_enum(*GENDERS),
        description=N_STR, residence=RESIDENCE,
    )),
    items=_arr(_obj(
        item_category=_enum(*ITEM_CATEGORIES), item_type=STR, description=N_STR,
        quantity=N_NUM, unit=N_STR, quantity_note=_enum(*QUANTITY_NOTES), status=_enum(*ITEM_STATUSES),
    )),
    fact=_obj(
        incident_count=N_INT, suspect_count=N_INT, victim_count=N_INT, injury_count=N_INT,
        death_count=N_INT, arrested_count=N_INT, financial_value=N_NUM,
        financial_value_basis=_enum(*FINANCIAL_BASES), legal_action=N_STR,
        investigation_status=_enum(*INVESTIGATION_STATUSES), incident_date_text=N_STR, description=STR,
    ),
)

SYSTEM_PROMPT = """You convert ONE Arabic news item from Egypt's Ministry of Interior into JSON for a crime data warehouse.
Input: Title, Publish date, Article text. Return only JSON that matches the schema.

SOURCES AND HONESTY
- Facts may come from the Title or the Text. The text often starts mid-story (the opening paragraph is missing), so the crime type, place or money amount can be only in the title. Read both.
- Use only what is written. No outside knowledge, no guessing. Unknown -> null ("غير محدد" for governorate, [] for lists, "unknown" / "not_stated" for enums).
- Never add a detail that is not written: no "unlicensed", no "armed", no gender, no residence, no age unless the text says so.
- Text values in Arabic, close to the original wording (fix obvious typos, keep singular/plural agreement).

NUMBERS
- A number is allowed only if it is written, or is clear from grammar: singular = 1, dual (مقيمان، شخصين) = 2, listed groups add up ("4 أشخاص، سيدة" = 5).
- Never subtract or estimate (arrested is NOT total minus killed minus injured). Vague words (عدد من، آخرين، كمية من، عشرات، مجموعة) -> null.
- A count is null unless the text gives it. Write 0 ONLY when the text says there were none ("دون إصابات", "لم يسفر عن"); silence is null, never 0.
- ألف = 1,000 and مليون = 1,000,000 (320 ألف قرص -> 320000). With "أكثر من / قرابة / ما يقرب من" use the stated number.
- incident_date_text: the date of the incident itself, copied as written ("13/ الجارى", "بتاريخ 19/ الجارى"); if several dates appear, the date the main event happened (usually the earliest). Never resolve it.

EVENT (what kind of news this is)
- viral_claim_investigation: "كشف ملابسات" a video/post/news item that circulated online, whatever was found (even if arrests followed).
- arrest_operation: an arrest, seizure or "اتخاذ الإجراءات القانونية" announcement against suspects (also money laundering, fraud rings) that was not triggered by a viral post.
- armed_clash: exchange of fire with security forces.
- rumor_denial: an official source denies a claim or statement.
- enforcement_campaign: totals of many cases in a period (flour/bread, currency trading "خلال 24 ساعة"), no single story.
- administrative: ONLY news with no suspect: traffic diversions, ceremonies, personnel decisions.   - other.

CRIME (classify by what the investigation established, not by what the post claimed)
- If the claim was found false and nothing else happened, the offence is the false claim: false_news_cyber, and the publisher is a suspect. If the investigation also found a REAL offence by the people involved (brawl, arson, molotov, assault), crime = that real offence and the false claim goes to secondary_crimes (false_news_cyber). If there is no offence at all (ceremony, traffic diversion, disciplinary dismissal, denial with no action): non_criminal, crime_subcategory and crime_type = "غير جنائي".
- A page that sells drugs/weapons/fireworks: if the suspect says he only meant to scam buyers -> fraud (put the possession in secondary_crimes); if he really held or sold the goods -> drugs or weapons_firearms.
- crime = the main offence the suspect was arrested or accused of; secondary_crimes = other offences stated. Weapons or drugs seized in addition to the main offence are listed as a secondary crime (weapons_firearms / drugs), without repeating the main offence.
- Categories: drugs (مخدرات), fraud (نصب واحتيال، انتحال صفة، دجل، تزوير), theft_robbery (سرقة، شروع في سرقة، بالإكراه), violence_assault (مشاجرة، ضرب، تعدٍ بسلاح أبيض، إطلاق نار، بلطجة، عنف أسري), homicide (قتل، شروع في قتل), weapons_firearms (سلاح بدون ترخيص، ألعاب نارية، صواعق), kidnapping_extortion (خطف، إتاوات، ابتزاز), financial_crimes (غسل أموال، اتجار بالنقد الأجنبي), commercial_fraud_supply (غش تجاري، تقليد، دقيق/خبز مدعم، مصنع غير مرخص), antiquities (تنقيب عن آثار), juvenile_exploitation (استغلال أحداث في التسول), traffic_accident (حادث، قيادة بدون رخصة، مخالفة مرورية)، false_news_cyber (ادعاءات كاذبة، شائعات), missing_person (تغيب), other_crime, non_criminal.
- crime_subcategory: a short Arabic label that you reuse across articles (e.g. "حيازة بقصد الإتجار", "ترويج عبر الإنترنت", "نصب إلكتروني", "مشاجرة", "شروع في سرقة"). crime_type: the specific offence in Arabic, at most 8 words.

PERSONS
- One entry per person, or per group with the same role (use count for groups). In a brawl list every party (each side, with its count) as suspects/victims by what the text says; a person who only filmed, posted or reported is a publisher/complainant, not a suspect.
- role: suspect (committed it / "المشكو فى حقه"; also the publisher if he lied), victim, complainant (reported or complained but is not the victim), publisher (القائم على النشر when neither suspect nor victim), witness, official (police or officials involved), other. One role per entry; priority suspect > victim > complainant > publisher.
- person_description: who they are as written ("والد الطفلة", "قائد الميكروباص", "عناصر التشكيل العصابي").
- gender: only from clear Arabic words or grammar (طالبة، ربة منزل، سيدة، مرتكبة، والدها, رجل); groups ("عناصر", "أشخاص") and anything else -> unknown.
- description: extra facts about the person as written: age ("سن 16"), job (عاطل، سائق، طالب)، prior charges / criminal record ("سبق اتهامهم في ..."), nationality hints. Null if none.
- residence.governorate = the governorate where the person LIVES, only when the text says so ("مقيم بالجيزة", "مقيمين بدائرة القسم" -> the station's governorate). NEVER copy the incident location otherwise; if residence is not stated -> "غير محدد". Officials and police officers never get a residence.

ITEMS (seized, stolen, recovered or impounded things)
- One entry per described item type. One number covering a mixed group ("10 بنادق آلية، خرطوش") is ONE entry with that quantity. "كمية من" -> quantity null.
- quantity = a number only; unit in Arabic (قرص، كيلو جرام، طن، لتر، قطعة، عبوة، شريحة، هاتف). Whenever there is a quantity there must be a unit; for countable things (weapons, phones, vehicles, cards) the unit is "قطعة" unless the text names another one.
- quantity_note: more_than for "أكثر من" ("أكثر من طن" -> quantity 1, unit طن, more_than), about for "حوالى / قرابة / نحو", otherwise none.
- item_category: weapon, ammunition, drugs, phones_electronics (phones, SIM cards, laptops), cash_valuables (cash, gold, currency), cards_wallets (bank cards, e-wallets, crypto wallets), vehicle, goods_commodities (flour, perfume, oils, fireworks, stock), tools_equipment (digging or production tools), animal, other.
- status: seized (found with suspects), recovered (stolen goods got back), stolen (taken, not recovered), impounded (vehicle/animal held: "التحفظ / إيداع").

LOCATION (where the incident happened)
- governorate from the list; "غير محدد" if several governorates or none are named (say so in location_text). For online crimes use the suspect's governorate and station.
- police_station as written without the governorate: "قسم شرطة ثان الشيخ زايد", "مركز شرطة الصف". city / district only if written. location_text: the place in Arabic ("منطقة زراعية", "داخل شقة سكنية"), plus where a missing person or suspect was found if different.

FACT
- incident_count: 1 for a single case; the written number for "27 واقعة"; null for "عدد من القضايا".
- suspect_count / victim_count / injury_count / arrested_count: people in that group, as written. death_count: deaths caused by the incident (not by illness).
- financial_value: EGP only, a number (3 مليون -> 3000000), from the text or the title. financial_value_basis says what it measures (seized_goods_value, laundered_amount, currency_trade_value, fraud_theft_amount, other; "none" if no value).
- legal_action: the actions as written (حبس على ذمة التحقيق، التحفظ على السيارة، أخذ تعهد على الأهل). investigation_status = the furthest stage stated: court_ruling > detained_pending_investigation > prosecution_investigating (النيابة تتولى التحقيق) > legal_action_taken (any "اتخاذ الإجراءات القانونية" counts, whatever the crime) > not_stated (no legal step mentioned at all).
- description: at most two Arabic sentences using only stated facts. Add nothing and no new numbers."""

# ----------------------------------------------------------------------------
# Arabic helpers, dates, input loading
# ----------------------------------------------------------------------------
_AR_MAP = str.maketrans({"أ": "ا", "إ": "ا", "آ": "ا", "ٱ": "ا", "ى": "ي", "ة": "ه", "ؤ": "و", "ئ": "ي"})
_TASHKEEL = re.compile(r"[ً-ْـ]")
_INDIC_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789")
_STATION_STOP = {"قسم", "مركز", "شرطه", "ثان", "ثاني", "اول", "ثالث", "رابع", "خامس"}
MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August",
          "September", "October", "November", "December"]


def norm_ar(s):
    s = _TASHKEEL.sub("", s or "").translate(_AR_MAP)
    return re.sub(r"\s+", " ", s).strip()


TEXT_KEYS = ["full_text_raw", "full_details", "full_content", "full_text", "content", "text", "body"]

try:
    from zoneinfo import ZoneInfo
    CAIRO = ZoneInfo("Africa/Cairo")
except Exception:  # noqa: BLE001  (no tz database: Egypt is UTC+3 in summer)
    CAIRO = timezone(timedelta(hours=3))


def pick(d, keys):
    for k in keys:
        if isinstance(d, dict) and d.get(k) not in (None, ""):
            return d[k]
    return None


def parse_publish(article):
    """Return (utc datetime or None, date or None)."""
    api = article.get("api_payload") or {}
    dt = None
    m = re.search(r"\((-?\d+)\)", str(api.get("datePublished") or ""))
    if m:
        dt = datetime.fromtimestamp(int(m.group(1)) / 1000, timezone.utc)
    elif article.get("date_published"):  # bronze_crime_all_news.json: "2026-09-27 16:53:28" (UTC)
        try:
            dt = datetime.fromisoformat(str(article["date_published"]).strip().replace("Z", "+00:00"))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
        except ValueError:
            dt = None
    d = None
    ts = str(api.get("timeSpan") or "")
    if re.fullmatch(r"\d{4}/\d{2}/\d{2}", ts):
        d = date.fromisoformat(ts.replace("/", "-"))
    elif dt:
        d = dt.astimezone(CAIRO).date()  # the date as Egypt saw it
    return dt, d


def derive_dim_date(d):
    if not d:
        return None
    return {
        "date_key": int(d.strftime("%Y%m%d")), "full_date": d.isoformat(), "day": d.day,
        "month": d.month, "month_name": MONTHS[d.month - 1], "quarter": (d.month - 1) // 3 + 1,
        "year": d.year, "day_of_week": d.isoweekday(), "week_of_year": d.isocalendar()[1],
    }


_CUR_WORDS = r"(?:الجاري|الحالي)"
_PREV_WORDS = r"(?:المنقضي|الماضي|السابق)"


def _safe_date(y, m, d):
    try:
        return date(y, m, d)
    except ValueError:
        return None


def _month_back(y, m):
    return (y - 1, 12) if m == 1 else (y, m - 1)


def resolve_incident_date(txt, pub):
    """'20/ الجارى' + publish date 2026-09-24 -> 2026-09-20. Returns an ISO string or None."""
    if not txt or not pub:
        return None
    t = norm_ar(str(txt).translate(_INDIC_DIGITS))
    m = re.search(r"(\d{1,2})\s*/\s*(\d{1,2})\s*/\s*(\d{4})", t)
    if m:
        r = _safe_date(int(m[3]), int(m[2]), int(m[1]))
    elif (m := re.search(r"(\d{1,2})\s*/\s*" + _CUR_WORDS, t)):
        r = _safe_date(pub.year, pub.month, int(m[1]))
        if r and r > pub:  # "30/ الجارى" published on the 2nd can only mean last month
            r = _safe_date(*_month_back(pub.year, pub.month), int(m[1]))
    elif (m := re.search(r"(\d{1,2})\s*/\s*" + _PREV_WORDS, t)):
        r = _safe_date(*_month_back(pub.year, pub.month), int(m[1]))
    elif (m := re.search(r"(\d{1,2})\s*/\s*(\d{1,2})(?!\s*/\s*\d)", t)):
        r = _safe_date(pub.year, int(m[2]), int(m[1]))
        if r and r > pub:
            r = _safe_date(pub.year - 1, int(m[2]), int(m[1]))
    else:
        r = None
    return r.isoformat() if r else None


def find_date_in_text(text):
    """Fallback when the model left incident_date_text empty: first 'بتاريخ 19/ الجارى' in the article."""
    t = norm_ar(str(text).translate(_INDIC_DIGITS))
    m = re.search(r"بتاريخ\s*(\d{1,2}\s*/\s*(?:\d{1,2}(?:\s*/\s*\d{4})?|" + _CUR_WORDS + "|" + _PREV_WORDS + "))", t)
    return m.group(1) if m else None


def article_fields(article, idx):
    api = article.get("api_payload") or {}
    art_id = str(pick(article, ["news_id", "id"]) or api.get("newsId") or f"idx_{idx}")
    text = pick(article, TEXT_KEYS) or ""
    title = (pick(api, ["title"]) or pick(article, ["title"]) or "").strip()
    return art_id, title, str(text)


def load_articles(input_arg):
    """Return [(article_dict, source_file_name), ...]."""
    if input_arg:
        p = Path(input_arg).expanduser()
    else:
        p = None
        for cand in (BASE_DIR, BASE_DIR / "data", BASE_DIR.parent / "data", Path.cwd()):
            if cand.is_dir() and any(cand.glob("*page_*.json")):
                p = cand
                break
        if p is None:
            raise SystemExit(
                "No input found. Put page_*.json next to this script (or in ./data), or pass --input DIR_OR_FILE."
            )
    if p.is_dir():
        files = sorted(p.glob("*page_*.json")) or sorted(
            f for f in list(p.glob("*.json")) + list(p.glob("*.jsonl"))
            if f.name not in (OUTPUT_JSON.name, "test_result.json")
        )
    elif p.is_file():
        files = [p]
    else:
        raise SystemExit(f"Input path not found: {p}")
    out = []
    for f in files:
        raw = f.read_text(encoding="utf-8")
        if f.suffix == ".jsonl":
            data = [json.loads(line) for line in raw.splitlines() if line.strip()]
        else:
            data = json.loads(raw)
            if isinstance(data, dict):
                data = next((v for v in data.values() if isinstance(v, list)), list(data.values()))
        out += [(a, f.name) for a in data if isinstance(a, dict) and pick(a, TEXT_KEYS) is not None]
    if not out:
        raise SystemExit(f"No articles with text found in {p} (looked for keys: {TEXT_KEYS})")
    return out


# ----------------------------------------------------------------------------
# LLM call (retries, rate limits, graceful fallbacks)
# ----------------------------------------------------------------------------
class DailyLimit(Exception):
    pass


STOP = Event()
_state = {"use_schema": True, "use_effort": True}
_client = None
_print_lock = Lock()
_write_lock = Lock()


def get_client():
    global _client
    if _client is None:
        key = os.getenv("LLM_API_KEY") or os.getenv("GROQ_API_KEY")
        if not key:
            raise SystemExit(f"API key not found. Put it in {BASE_DIR / '.env'} as GROQ_API_KEY=... (or LLM_API_KEY=...)")
        _client = OpenAI(base_url=BASE_URL, api_key=key, max_retries=0)
    return _client


def _retry_after(e):
    try:
        v = e.response.headers.get("retry-after")
        return float(v) if v else None
    except Exception:
        return None


def call_llm(user_msg):
    for attempt in range(7):
        if STOP.is_set():
            raise DailyLimit("daily limit reached")
        system = SYSTEM_PROMPT
        if _state["use_schema"]:
            rf = {"type": "json_schema", "json_schema": {"name": "moi_news", "strict": True, "schema": SCHEMA}}
        else:
            rf = {"type": "json_object"}
            system += "\n\nReturn ONLY a JSON object that matches this JSON Schema:\n" + json.dumps(SCHEMA, ensure_ascii=False)
        extra = {}
        if _state["use_effort"] and REASONING_EFFORT:
            extra["extra_body"] = {"reasoning_effort": REASONING_EFFORT}
        try:
            resp = get_client().chat.completions.create(
                model=MODEL,
                messages=[{"role": "system", "content": system}, {"role": "user", "content": user_msg}],
                temperature=0,
                response_format=rf,
                **extra,
            )
            return json.loads(resp.choices[0].message.content)
        except BadRequestError as e:
            msg = str(e).lower()
            if "reasoning_effort" in msg and _state["use_effort"]:
                _state["use_effort"] = False
                print("note: the API rejected reasoning_effort, continuing without it")
                continue
            if "json_validate_failed" in msg or "failed_generation" in msg:
                time.sleep(1)  # the model produced bad JSON this time: just retry
                continue
            if _state["use_schema"] and ("schema" in msg or "response_format" in msg):
                _state["use_schema"] = False
                print("note: json_schema was rejected by the API, falling back to json_object mode")
                continue
            raise
        except RateLimitError as e:
            if "per day" in str(e).lower():
                STOP.set()
                raise DailyLimit(str(e))
            time.sleep(max(_retry_after(e) or 0, min(2 ** attempt * 2, 60)))
        except (APIConnectionError, APITimeoutError, InternalServerError):
            time.sleep(min(2 ** attempt * 2, 60))
        except json.JSONDecodeError:
            time.sleep(1)
    raise RuntimeError("failed after retries")


# ----------------------------------------------------------------------------
# Post-processing: cleaning, derived fields, review flags
# ----------------------------------------------------------------------------
_ZERO_OK = re.compile(
    r"(دون|بدون|لم يسفر|لم ينتج|لا توجد|لا يوجد|عدم وجود|لم يصب)[^.]{0,40}(اصاب|خسائر|وفيات|ضحايا|مصاب|قتلي|وفاه)")
_COUNTABLE = {"weapon", "phones_electronics", "vehicle", "cards_wallets", "tools_equipment", "animal", "other"}


def clean_llm(d, blob=""):
    """Deterministic clean-up of the model output. Returns (d, notes)."""
    notes = []

    def gov(x):
        return None if x in (None, "", UNKNOWN_GOV) else x

    d["location"]["governorate"] = gov(d["location"]["governorate"])
    for p in d["persons"]:
        p["residence"]["governorate"] = gov(p["residence"]["governorate"])
        if p["role"] == "official":  # officials never get a residence
            p["residence"]["governorate"] = None
    f = d["fact"]
    if f["financial_value_basis"] == "none":
        f["financial_value_basis"] = None
    # a 0 is only believable when the text says "nobody was hurt"; otherwise it is the model filling a blank
    if not _ZERO_OK.search(blob):
        for k in ("suspect_count", "victim_count", "injury_count", "death_count", "arrested_count"):
            if f[k] == 0:
                f[k] = None
                notes.append(f"zero_count_nulled:{k}")
    crime = d["crime"]["crime_category"] != "non_criminal"
    if crime and f["investigation_status"] == "not_stated" and f["legal_action"]:
        f["investigation_status"] = "legal_action_taken"
    for it in d["items"]:
        it["quantity_note"] = None if it["quantity_note"] == "none" else it["quantity_note"]
        if it["quantity"] is not None and not it["unit"] and it["item_category"] in _COUNTABLE:
            it["unit"] = "قطعة"
    return d, notes


def _numbers(d):
    f = d["fact"]
    out = [(k, f.get(k)) for k in (
        "incident_count", "suspect_count", "victim_count", "injury_count",
        "death_count", "arrested_count", "financial_value")]
    for i, p in enumerate(d["persons"]):
        out.append((f"persons[{i}].count", p["count"]))
    for i, it in enumerate(d["items"]):
        out.append((f"items[{i}].quantity", it["quantity"]))
    return out


def review_flags(d, title, text):
    """Cheap automatic checks. A flag means 'look at this one', not 'this is wrong'."""
    flags = []
    raw = f"{title} {text}"
    blob = norm_ar(raw)
    digits = {int(x) for x in re.findall(r"\d+", raw.translate(_INDIC_DIGITS)) if len(x) <= 9}
    derived = {a + b for a in digits for b in digits} | {a + 1 for a in digits} | {a + 2 for a in digits}

    # a scaled number (320 ألف -> 320000, 3 مليون -> 3000000) is only accepted if the scale WORD is in the text
    scales = []
    if re.search(r"(?<![ء-ي])الف(?![ء-ي])", blob):
        scales.append(1000)
    if "مليون" in blob:
        scales.append(1_000_000)
    if "مليار" in blob:
        scales.append(1_000_000_000)

    def num_ok(n):
        n = int(n) if float(n) == int(n) else n
        if n in digits or n in derived:
            return True
        return any(isinstance(n, int) and n % u == 0 and n // u in digits for u in scales)

    for label, n in _numbers(d):
        if n is not None and n > 2 and not num_ok(n):
            flags.append(f"number_not_in_text:{label}={n}")

    gov = d["location"]["governorate"]
    if gov and norm_ar(gov) not in blob:
        flags.append(f"governorate_not_in_text:{gov}")
    ps = d["location"]["police_station"]
    if ps:
        toks = [t for t in norm_ar(ps).split() if t not in _STATION_STOP]
        if toks and not all(t in blob for t in toks):
            flags.append(f"police_station_not_in_text:{ps}")

    f = d["fact"]
    non_crime = d["crime"]["crime_category"] == "non_criminal"
    if non_crime and any(p["role"] == "suspect" for p in d["persons"]):
        flags.append("non_criminal_but_has_suspect")
    # "arrested = total - killed - injured" is the classic invented number: flag it when the text never says it
    tot, a = f["suspect_count"], f["arrested_count"]
    if tot is not None and a is not None and (f["death_count"] or 0) + (f["injury_count"] or 0) > 0 \
            and a == tot - (f["death_count"] or 0) - (f["injury_count"] or 0) and a not in digits:
        flags.append(f"arrested_count_looks_subtracted:{a}")
    known = [x for x in (f["suspect_count"], f["victim_count"]) if x is not None]
    harm = sum(x or 0 for x in (f["death_count"], f["injury_count"], f["arrested_count"]))
    if known and harm > sum(known):
        flags.append("death_injury_arrested_exceed_people_counts")
    if (f["financial_value"] is None) != (f["financial_value_basis"] is None):
        flags.append("financial_value_and_basis_disagree")
    if any(it["quantity"] is not None and not it["unit"] for it in d["items"]):
        flags.append("item_quantity_without_unit")
    return flags


def build_record(article, source_file, idx, llm):
    api = article.get("api_payload") or {}
    art_id, title, text = article_fields(article, idx)
    pub_dt, pub_date = parse_publish(article)
    d, notes = clean_llm(llm, norm_ar(f"{title} {text}"))
    flags = notes + review_flags(d, title, text)

    loc = d["location"]
    items = d["items"]
    fact = dict(d["fact"])
    fact["seized_item_count"] = sum(1 for it in items if it["status"] in ("seized", "recovered", "impounded"))
    fact["is_criminal_incident"] = d["crime"]["crime_category"] != "non_criminal"
    if not fact["is_criminal_incident"]:
        fact["incident_count"] = 0
    elif not fact["incident_count"] and d["event"]["event_type"] != "enforcement_campaign":
        fact["incident_count"] = 1
    if not fact["incident_date_text"]:
        fact["incident_date_text"] = find_date_in_text(text)
    fact["incident_date"] = resolve_incident_date(fact["incident_date_text"], pub_date)

    persons = []
    for p in d["persons"]:
        gov = p["residence"]["governorate"]
        persons.append({
            "person_role": p["role"], "count": p["count"], "person_description": p["person_description"],
            "gender": p["gender"], "description": p["description"],
            "residence_governorate": gov, "residence_region": REGION_BY_GOV.get(gov),
        })

    return {
        "id": art_id,
        "extracted_at": datetime.now().isoformat(timespec="seconds"),
        "model": MODEL,
        "prompt_version": PROMPT_VERSION,
        "needs_review": flags,
        "dim_news": {
            "source_news_id": art_id,
            "title": title,
            "publication_date": pub_dt.isoformat() if pub_dt else None,
            "source_url": article.get("source_url"),
            "image_url": api.get("imagePathLarge") or article.get("image_url"),
            "section_id": article.get("section_id"),
            "paragraphs_count": article.get("paragraphs_count"),
            "raw_text_reference": f"{source_file}#{art_id}",
            "ingested_at": article.get("scraped_at") or article.get("ingested_at"),
        },
        "dim_date": derive_dim_date(pub_date),
        "dim_location": {
            "governorate": loc["governorate"], "city": loc["city"],
            "police_station": loc["police_station"],
            "region": REGION_BY_GOV.get(loc["governorate"]), "country": COUNTRY,
            "location_text": loc["location_text"],
        },
        "dim_crime_type": d["crime"],
        "secondary_crimes": d["secondary_crimes"],
        "dim_event": d["event"],
        "persons": persons,
        "items": items,
        "fact_incident": fact,
    }


def build_user_msg(title, pub_date, text):
    return f"Title: {title}\nPublish date: {pub_date.isoformat() if pub_date else 'unknown'}\nArticle text:\n{text[:6000]}"


def process(idx, article, source_file):
    if STOP.is_set():
        raise DailyLimit("daily limit reached")
    art_id, title, text = article_fields(article, idx)
    if not text.strip():
        raise ValueError("article has no text (looked for full_text_raw / full_content / text ...)")
    _, pub_date = parse_publish(article)
    llm = call_llm(build_user_msg(title, pub_date, text))
    return build_record(article, source_file, idx, llm)


# ----------------------------------------------------------------------------
# Main
# ----------------------------------------------------------------------------
def load_done_ids():
    done = set()
    if OUTPUT_JSONL.exists():
        for line in OUTPUT_JSONL.read_text(encoding="utf-8").splitlines():
            if line.strip():
                try:
                    done.add(str(json.loads(line)["id"]))
                except Exception:
                    pass
    return done


def rebuild_pretty_json():
    recs = []
    if OUTPUT_JSONL.exists():
        for line in OUTPUT_JSONL.read_text(encoding="utf-8").splitlines():
            if line.strip():
                recs.append(json.loads(line))
    OUTPUT_JSON.write_text(json.dumps(recs, ensure_ascii=False, indent=2), encoding="utf-8")
    return len(recs)


def estimate_tokens(articles):
    avg_chars = sum(len(article_fields(a, i)[2]) for i, (a, _) in enumerate(articles)) / max(len(articles), 1)
    prompt = (len(SYSTEM_PROMPT) + len(json.dumps(SCHEMA))) / 3.5
    return int(prompt + avg_chars / 2.5 + 900)  # +900 = rough output (JSON + reasoning)


def main(argv=None):
    ap = argparse.ArgumentParser(description="MOI news -> star-schema-ready JSON")
    ap.add_argument("--input", help="folder with page_*.json, or a single .json / .jsonl file")
    ap.add_argument("--limit", type=int, help="process only the first N articles that are not done yet")
    ap.add_argument("--sample", type=int, help="process N random articles (seed 42) - good for testing")
    ap.add_argument("--workers", type=int, default=2, help="parallel requests (keep low for rate limits)")
    ap.add_argument("--redo", action="store_true", help="ignore earlier results and start the outputs fresh")
    ap.add_argument("--part", help="K/N: run slice K of N equal slices, e.g. 3/6")
    ap.add_argument("--range", dest="range_", help="START-END: run articles START..END (1-based, inclusive), e.g. 1001-2000")
    ap.add_argument("--show", type=int, default=1, help="print the first N full records at the end")
    args = ap.parse_args(argv)

    global OUTPUT_JSONL, OUTPUT_JSON, ERRORS_FILE
    articles = load_articles(args.input)
    total_all = len(articles)
    fingerprint = hashlib.sha1("\n".join(article_fields(a, i)[0] for i, (a, _) in enumerate(articles)).encode()).hexdigest()[:8]
    if args.part or args.range_:
        try:
            if args.part:
                k, n = (int(x) for x in args.part.split("/"))
                per = math.ceil(total_all / n)
                start, end = (k - 1) * per + 1, min(k * per, total_all)
            else:
                a, b = (int(x) for x in args.range_.split("-"))
                start, end = a, min(b, total_all)
        except ValueError:
            raise SystemExit("Use --part K/N (e.g. 3/6) or --range START-END (e.g. 1001-2000)")
        if start < 1 or start > end:
            raise SystemExit(f"Empty slice: {start}-{end} (the input has {total_all} articles)")
        articles = articles[start - 1:end]
        out_dir = BASE_DIR / "results"
        out_dir.mkdir(exist_ok=True)
        stem = f"extracted_{start:04d}-{end:04d}"
        OUTPUT_JSONL, OUTPUT_JSON, ERRORS_FILE = out_dir / f"{stem}.jsonl", out_dir / f"{stem}.json", out_dir / f"errors_{start:04d}-{end:04d}.jsonl"
        print(f"Slice {start}-{end} of {total_all} articles (input fingerprint {fingerprint} - every member must see the same one)")
    print(f"Loaded {len(articles)} articles | model: {MODEL} | reasoning_effort: {REASONING_EFFORT} | api: {BASE_URL}")

    if args.redo:
        for f in (OUTPUT_JSONL, OUTPUT_JSON, ERRORS_FILE):
            if f.exists():
                f.replace(f.with_name(f.name + ".bak"))
    done = load_done_ids()
    todo = [(i, a, src) for i, (a, src) in enumerate(articles) if article_fields(a, i)[0] not in done]
    if args.sample:
        random.Random(42).shuffle(todo)
        todo = todo[: args.sample]
    elif args.limit:
        todo = todo[: args.limit]
    if not todo:
        print(f"Nothing to do: every article is already in {OUTPUT_JSONL.name}. Use --redo to run again.")
        return
    est = estimate_tokens([(a, s) for _, a, s in todo])
    print(f"Already done: {len(done)} | processing now: {len(todo)} | rough budget: ~{est:,} tokens per article, "
          f"~{est * len(todo):,} in total (check your limits: console.groq.com/settings/limits)")

    ok = fail = 0
    cats, events, flagged = collections.Counter(), collections.Counter(), collections.Counter()
    shown = []
    daily_limit_hit = False
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {pool.submit(process, i, a, src): (i, a) for i, a, src in todo}
        for fut in as_completed(futures):
            i, a = futures[fut]
            art_id = article_fields(a, i)[0]
            try:
                rec = fut.result()
            except DailyLimit as e:
                if not daily_limit_hit:
                    daily_limit_hit = True
                    print(f"\nDAILY LIMIT reached - stopping. Run the same command again later, it resumes.\n  {str(e)[:300]}")
                    for f in futures:
                        f.cancel()
                continue
            except Exception as e:  # noqa: BLE001
                fail += 1
                with _write_lock:
                    with ERRORS_FILE.open("a", encoding="utf-8") as ef:
                        ef.write(json.dumps({"id": art_id, "error": str(e)[:500]}, ensure_ascii=False) + "\n")
                print(f"[{ok + fail}/{len(todo)}] ERR {art_id[:8]}: {str(e)[:150]}")
                continue
            with _write_lock:
                with OUTPUT_JSONL.open("a", encoding="utf-8") as of:
                    of.write(json.dumps(rec, ensure_ascii=False) + "\n")
            ok += 1
            cats[rec["dim_crime_type"]["crime_category"]] += 1
            events[rec["dim_event"]["event_type"]] += 1
            for fl in rec["needs_review"]:
                flagged[fl.split(":")[0]] += 1
            if len(shown) < args.show:
                shown.append(rec)
            with _print_lock:
                print(f"[{ok + fail}/{len(todo)}] ok  {art_id[:8]}  {rec['dim_event']['event_type']} | "
                      f"{rec['dim_crime_type']['crime_category']}/{rec['dim_crime_type']['crime_subcategory']} | "
                      f"{rec['dim_location']['governorate'] or '-'} | persons={len(rec['persons'])} "
                      f"items={len(rec['items'])}" + (f" | REVIEW {rec['needs_review']}" if rec["needs_review"] else ""))

    total = rebuild_pretty_json()
    print(f"\nDone. success={ok} failed={fail} | records in file: {total}")
    if cats:
        print("crime_category:", dict(cats.most_common()))
        print("event_type:    ", dict(events.most_common()))
    if flagged:
        print("review flags:  ", dict(flagged.most_common()))
    for rec in shown:
        print("\n--- sample record ---")
        print(json.dumps(rec, ensure_ascii=False, indent=2))
    print(f"\nResults: {OUTPUT_JSON}  (and {OUTPUT_JSONL.name})")
    if fail:
        print(f"Errors:  {ERRORS_FILE}")


if __name__ == "__main__":
    main()