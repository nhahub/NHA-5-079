import sys
import json
import time
from pathlib import Path
import pandas as pd
import logging

# Ensure UTF-8 output in Windows PowerShell/cmd terminals
if sys.stdout.encoding != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[logging.StreamHandler(sys.stdout)],
)

logger = logging.getLogger("transform_silver")


# =============================================================================
# 1. Arabic Text Normalization (Pure string .replace)
# =============================================================================
def normalize_arabic(text):
    if not text:
        return ""
    text = text.replace("إ", "ا").replace("أ", "ا").replace("آ", "ا")
    text = text.replace("ى", "ي").replace("ة", "ه")
    for diacritic in ["َ", "ً", "ُ", "ٌ", "ِ", "ٍ", "ْ", "ّ"]:
        text = text.replace(diacritic, "")
    return text.lower()


# =============================================================================
# 2. Egyptian Governorates Taxonomy (Key -> [Official Name, Keywords...])
# Matches schema.sql dim_location EXACTLY.
# =============================================================================
GOVERNORATES = {

    #Frontier Sinai (checked before generic keywords)
    27: ["جنوب سيناء", "شرم الشيخ", "طور سيناء", "دهب", "نويبع"],
    26: ["شمال سيناء", "العريش", "رفح", "شيخ زويد"],
    25: ["مطروح", "مرسي مطروح", "السلوم", "العلمين", "الضبعة"],
    24: ["الوادي الجديد", "وادي جديد", "الخارجه", "الداخله", "فرافره"],
    23: ["البحر الأحمر", "بحر احمر", "الغردقه", "غردقه", "سفاجا", "قصير"],

    #Upper Egypt
    22: ["أسوان", "اسوان", "كوم امبو", "ادفو", "النوبه"],
    21: ["الأقصر", "اقصر", "اسنا", "ارمنت"],
    20: ["قنا", "نجع حمادي", "دشنا", "ابو تشت", "فرشوط", "قفط"],
    19: ["سوهاج", "طهطا", "جرجا", "اخميم", "المراغه"],
    18: ["أسيوط", "اسيوط", "ديروط", "القوصيه", "ابنوب", "منفلوط"],
    17: ["المنيا", "منيا", "ملوي", "مغاغه", "سمالوط", "بني مزار", "ابو قرقاص"],
    16: ["بني سويف", "بنسويف", "الواسطي", "ببا", "اهناسيا"],
    15: ["الفيوم", "فيوم", "طاميه", "سنورس", "اطسا"],

    #Canal Zone
    14: ["السويس", "سويس", "العين السخنه"],
    13: ["الإسماعيلية", "اسماعيليه", "فايد", "القنطره"],
    12: ["بورسعيد", "بور سعيد"],

    #*Alexandria & Delta
    11: ["دمياط", "راس البر", "فارسكور"],
    10: ["الشرقية", "شرقيه", "الزقازيق", "زقازيق", "العاشر من رمضان", "بلبيس", "فاقوس"],
    9: ["الدقهلية", "دقهليه", "المنصوره", "منصوره", "ميت غمر", "بلقاس", "دكرنس"],
    8: ["المنوفية", "منوفيه", "شبين الكوم", "اشمون", "قويسنا", "السادات", "منوف"],
    7: ["الغربية", "غربيه", "طنطا", "المحله الكبري", "المحله", "زفتي"],
    6: ["كفر الشيخ", "كفرالشيخ", "دسوق", "بلطيم", "فوه"],
    5: ["البحيرة", "بحيره", "دمنهور", "كفر الدوار", "ايتاي البارود"],
    4: ["الإسكندرية", "اسكندريه", "برج العرب", "العامريه", "الرمل", "سيدي جابر", "المنتزه"],

    #Greater Cairo
    3: ["القليوبية", "قليوبيه", "بنها", "شبرا الخيمه", "القناطر"],
    2: ["الجيزة", "جيزه", "اكتوبر", "زايد", "الهرم", "فيصل", "العجوزه", "الدقي", "بولاق الدكرور", "بدرشين", "الصف"],
    1: ["القاهرة", "قاهره", "شبرا", "حلوان", "مطريه", "عين شمس", "المرج", "المعادي", "التجمع"],
    
}


def extract_location_id(title, full_details):
    norm_title = normalize_arabic(title)
    norm_body = normalize_arabic(full_details)
    
    # Check title first (high accuracy)
    for loc_id, keywords in GOVERNORATES.items():
        for kw in keywords:
            if normalize_arabic(kw) in norm_title:
                return loc_id

    # Check body text
    for loc_id, keywords in GOVERNORATES.items():
        for kw in keywords:
            if normalize_arabic(kw) in norm_body:
                return loc_id

    return 0  # Unknown


# =============================================================================
# 3. Egyptian Crime Taxonomy (Matches schema.sql dim_crime_type EXACTLY)
# =============================================================================
CRIME_TAXONOMY = {
    8: ["غسيل أموال وكسب غير مشروع", "غسيل اموال", "غسل اموال", "كسب غير مشروع", "اخفاء مصدرها", "اصباغها بالصبغه الشرعيه"],
    7: ["جرائم إلكترونية وابتزاز", "جرائم تقنيه المعلومات", "صفحه بمواقع التواصل", "ابتزاز الكتروني", "ابتزاز", "فيس بوك", "تيك توك"],
    2: ["تجارة المواد المخدرة", "مخدر", "حشيش", "هيروين", "شابو", "ايس", "كبتاجون", "بانجو", "اقراص مخدره", "ترامادول", "استروكس", "هيدرو", "مخدرات"],
    1: ["بلطجة وفرض سيطرة", "بلطجه", "فرض سيطره", "اتاوات", "بؤره اجراميه شديده الخطوره", "ترويع المواطنين"],
    6: ["نصب واحتيال وتوظيف أموال", "توظيف اموال", "نصب", "احتيال", "استيلاء علي اموال", "شهادات مقلده", "نقد اجنبي", "عملات اجنبيه", "تجاره عمله"],
    9: ["شروع في قتل وقتل عمد", "قتل عمد", "شروع في قتل", "انهاء حياه", "اودت بحياته", "لقي مصرعه في مشاجره"],
    4: ["سرقة بالإكراه وتشكيل عصابي", "سرقه بالاكراه", "تشكيل عصابي", "سطو مسلح"],
    3: ["حيازة أسلحة نارية وذخائر", "سلاح ناري", "اسلحه ناريه", "اعيره ناريه", "اطلاق اعيره", "اطلاق نار", "بنادق", "طبنجه", "فرد خرطوش", "ذخيره", "طلقات"],
    5: ["سرقة مساكن ومتاجر", "سرقه مساكن", "سرقه متاجر", "سرقه سيارات", "سرقه دراجات", "نشل", "سرقه"],
    10: ["تهريب وجرائم جمركية", "تهريب", "جمارك", "بضائع مهربه", "ميناء", "هجره غير شرعيه"],
    11: ["تعديات على الأراضي ومباني مخالفة", "تعديات", "مباني مخالفه", "تبوير", "اراضي زراعيه", "ازاله تعديات"],
    12: ["مخالفات تموينية واحتكار سلع", "تموين", "احتكار", "سلع تموينيه", "اسطوانات بوتاجاز", "سوق سوداء", "دقيق مدعم"]
}


def extract_crime_type_id(title, full_details):
    norm_title = normalize_arabic(title)
    norm_body = normalize_arabic(full_details)
    
    # Check title first
    for crime_id, keywords in CRIME_TAXONOMY.items():
        for kw in keywords[1:]:
            if normalize_arabic(kw) in norm_title:
                return crime_id

    # Check body text
    for crime_id, keywords in CRIME_TAXONOMY.items():
        for kw in keywords[1:]:
            if normalize_arabic(kw) in norm_body:
                return crime_id

    return 0  # Other / Unclassified


# =============================================================================
# 4. Date & Metrics Parser
# =============================================================================
def extract_date_id(date_str):
    if not date_str:
        return 0
    try:
        clean_date = str(date_str)[:10].replace("-", "")
        return int(clean_date)
    except (ValueError, TypeError):
        return 0


def extract_metrics(title, full_details):
    combined_text = normalize_arabic(f"{title} {full_details}")
    
    # Campaign flag
    is_campaign = any(kw in combined_text for kw in ["حمله", "حملات", "مكبره", "موسعه", "انضباطيه"])

    # Suspects count
    suspects_count = 1
    import re
    num_match = re.search(r"(?:ضبط|تضم|تشكيل|مصرع|اصابه)\s*\(?\s*(\d+)\s*(?:عناصر|اشخاص|متهمين|عاطلين|عنصر|شخص)", combined_text)
    if num_match:
        val = int(num_match.group(1))
        if 1 <= val <= 100:
            suspects_count = val
    elif any(dual in combined_text for dual in ["شخصين", "عنصرين", "متهمين اثنين"]):
        suspects_count = 2

    # Weapons count
    weapons_count = 0
    has_weapons = any(w in combined_text for w in ["سلاح ناري", "اسلحه ناريه", "بندقيه", "بنادق", "طبنجه", "فرد خرطوش", "رشاش"])
    if has_weapons:
        weapons_count = 1
        w_match = re.search(r"\(?\s*(\d+)\s*(?:بنادق|بندقيه|طبنجه|طبنجات|سلاح|اسلحه|فرد)", combined_text)
        if w_match:
            w_val = int(w_match.group(1))
            if 1 <= w_val <= 100:
                weapons_count = w_val

    return suspects_count, weapons_count, is_campaign


# =============================================================================
# 5. Main Silver Transformation Pipeline
# =============================================================================
def transform_bronze_to_silver(bronze_file=None, silver_file=None):
    project_root = Path(__file__).resolve().parent.parent
    data_dir = project_root / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    if bronze_file is None:
        bronze_file = data_dir / "bronze_crime_news.json"
    if silver_file is None:
        silver_file = data_dir / "silver_crime_news.parquet"

    logger.info("STARTING SILVER TRANSFORMATION PIPELINE")
    logger.info(f"Source (Bronze): {bronze_file.name}")
    logger.info(f"Target (Silver): {silver_file.name}")

    start_time = time.time()

    with open(bronze_file, "r", encoding="utf-8") as f:
        bronze_data = json.load(f)

    total_records = len(bronze_data)
    logger.info(f"Loaded {total_records:,} raw articles from Bronze.")

    silver_records = []
    loc_matched = 0
    crime_matched = 0

    for idx, item in enumerate(bronze_data, 1):
        news_id = item.get("news_id")
        title = item.get("title", "")
        full_details = item.get("full_details", "")
        date_published = item.get("date_published")

        # 1. Transform Dimensions
        date_id = extract_date_id(date_published)
        location_id = extract_location_id(title, full_details)
        crime_type_id = extract_crime_type_id(title, full_details)

        if location_id > 0:
            loc_matched += 1
        if crime_type_id > 0:
            crime_matched += 1

        # 2. Extract Metrics
        suspects_count, weapons_count, is_campaign = extract_metrics(title, full_details)

        # 3. Build Clean Silver Record (Matches fact_crime table)
        silver_record = {
            "news_id": str(news_id),
            "date_id": int(date_id),
            "location_id": int(location_id),
            "crime_type_id": int(crime_type_id),
            "title": title,
            "full_details": full_details,
            "source_url": item.get("source_url", ""),
            "image_url": item.get("image_url", ""),
            "incident_count": 1,
            "suspects_count": int(suspects_count),
            "weapons_count": int(weapons_count),
            "is_campaign": bool(is_campaign),
            "published_timestamp": date_published,
            "ingested_at": item.get("ingested_at")
        }
        silver_records.append(silver_record)

    # 4. Convert to DataFrame and Export to Parquet via PyArrow
    df = pd.DataFrame(silver_records)
    
    # Enforce strict data types matching PostgreSQL warehouse
    df["date_id"] = df["date_id"].astype("int32")
    df["location_id"] = df["location_id"].astype("int32")
    df["crime_type_id"] = df["crime_type_id"].astype("int32")
    df["incident_count"] = df["incident_count"].astype("int32")
    df["suspects_count"] = df["suspects_count"].astype("int32")
    df["weapons_count"] = df["weapons_count"].astype("int32")
    df["is_campaign"] = df["is_campaign"].astype("bool")

    df.to_parquet(silver_file, engine="pyarrow", index=False)

    duration = time.time() - start_time

    logger.info("SILVER TRANSFORMATION COMPLETED SUCCESSFULLY!")
    logger.info(f"Processed Records   : {total_records:,}")
    logger.info(f"Location Match Rate : {loc_matched:,}/{total_records:,} ({(loc_matched/total_records)*100:.1f}%)")
    logger.info(f"Crime Match Rate    : {crime_matched:,}/{total_records:,} ({(crime_matched/total_records)*100:.1f}%)")
    logger.info(f"Total Duration      : {duration:.2f} seconds")
    logger.info(f"Destination         : {silver_file}")

    return df


if __name__ == "__main__":
    transform_bronze_to_silver()
