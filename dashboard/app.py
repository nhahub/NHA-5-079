"""MOI Criminal Releases Observatory — Editorial Egyptian Analytics Dashboard."""

from __future__ import annotations

import html
import sys
from pathlib import Path

import pandas as pd
import streamlit as st

_ROOT_DIR = Path(__file__).resolve().parent.parent
if str(_ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(_ROOT_DIR))

from dashboard.charts import (  # noqa: E402
    chart_crime_event_heatmap,
    chart_egypt_map,
    chart_lethality_rate,
    chart_monthly_trajectory,
    chart_operation_divergence,
    chart_ranked_barh,
)
from dashboard.db import load_incidents, load_items, load_quality_audit  # noqa: E402
from dashboard.labels import (  # noqa: E402
    CRIME_LABELS_AR,
    CRIME_LABELS_BI,
    EVENT_LABELS_AR,
    EVENT_LABELS_BI,
    GOVERNORATE_COORDS,
    PALETTE,
    REGION_LABELS_AR,
    REGION_LABELS_BI,
    fmt_egp,
    fmt_kg,
)

st.set_page_config(
    page_title="MOI Criminal Observatory · مرصد البيانات الجنائية",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------------------------------------------------------------------------
# Bilingual / Arabic UI string dictionary
# ---------------------------------------------------------------------------
_TEXT = {
    "ar": {
        "kicker": "مرصد البيانات الجنائية · الطبقة الذهبية (Gold Star Schema)",
        "title": "تحليل البيانات الرسمية لوزارة الداخلية المصرية",
        "subtitle": "رصد وقائع الضبط والحملات الأمنية، التوزيع الجغرافي للمحافظات، كميات المضبوطات، ومؤشرات جودة البيانات.",
        "sidebar_lang": "لغة الواجهة · Language",
        "sidebar_filters": "نطاق التحليل والتصفية",
        "scope_label": "نطاق البيانات",
        "scope_all": "كافة البيانات الجنائية",
        "scope_single": "وقائع منفردة فقط (دون الحملات المجمعة)",
        "year_label": "الفترة الزمنية (السنة)",
        "region_label": "الأقاليم الجغرافية",
        "region_ph": "كل الأقاليم",
        "gov_label": "المحافظات",
        "gov_ph": "كل المحافظات",
        "crime_label": "تصنيف الجريمة",
        "crime_ph": "كل التصنيفات",
        "event_label": "نوع العملية الأمنية",
        "event_ph": "كل العمليات",
        "search_label": "بحث نصي في العناوين",
        "search_ph": "مثال: حشيش، غسل أموال، منشور...",
        "reset_btn": "إعادة ضبط الفلاتر",
        "slice_prefix": "النطاق النشط:",
        "slice_showing": "يعرض",
        "slice_of": "من أصل",
        "slice_releases": "بيان رسمي",
        "kpi_releases": "البيانات الرسمية",
        "kpi_arrests": "المضبوطون والمتهمون",
        "kpi_deaths": "حالات الوفاة",
        "kpi_drugs": "مضبوطات المخدرات",
        "kpi_financial": "القيمة المالية المصرح بها",
        "national_share": "من إجمالي الجمهورية",
        "kpi_releases_sub": "{single:,} واقعة منفردة · {camp:,} حملة مجمعة",
        "kpi_arrests_sub": "متوسط {avg:.1f} متهم لكل بيان",
        "kpi_deaths_sub": "{clash:,} في تبادل إطلاق نار",
        "kpi_drugs_sub": "{rows:,} سجل حرز مخدرات (وحدات موحدة)",
        "kpi_fin_sub": "{cnt:,} بيان بمتوسط وسيط {med}",
        "tabs": [
            "نظرة عامة",
            "التحليل الجغرافي",
            "العمليات ونوع الجريمة",
            "المضبوطات والأحراز",
            "جودة البيانات",
            "سجل الوقائع",
        ],
        "ov_monthly_h": "المسار الشهري للبيانات المنشورة",
        "ov_monthly_cap": "الأعمدة توضح العدد الشهري للبيانات المنشورة، والخط الذهبي يبين المتوسط المتحرك لآخر 3 أشهر.",
        "ov_crimes_h": "أكثر تصنيفات الجرائم تكرارًا (أعلى 10)",
        "ov_ops_h": "الوقائع المنفردة مقابل الحملات الأمنية المجمعة",
        "ov_insight": "قراءة هيكلية للنطاق المحدد: تمثل الوقائع المنفردة {pct_single:.1f}% من البيانات ({single:,} بيانًا)، بينما تمثل الحملات الأمنية المجمعة {pct_camp:.1f}% ({camp:,} بيانًا) وتتركز غالبًا في قضايا المرور والتموين وتقنين المواقف دون تخصيص محافظة.",
        "geo_metric_label": "المؤشر المعروض على الخريطة والترتيب",
        "geo_metrics": {
            "releases": "عدد البيانات",
            "arrests": "المضبوطون",
            "deaths": "الوفيات",
            "financial": "القيمة المالية (ج.م)",
        },
        "geo_map_h": "التوزيع المكاني عبر المحافظات",
        "geo_rank_h": "أعلى 12 محافظة حسب المؤشر المختار",
        "geo_region_h": "التوزيع الإقليمي الشامل (بما في ذلك البيانات غير المحددة بمحافظة)",
        "geo_unknown_note": "ملاحظة منهجية: يوجد {unk:,} بيانًا مصنفًا على مستوى الجمهورية أو بدون تحديد محافظة (مثل الحملات العامة)، ولذلك لا يظهر على خريطة المحافظات أو ترتيبها ويظهر تحت بند «غير محدد / عام» في توزيع الأقاليم.",
        "ops_heat_h": "مصفوفة تقاطع تصنيف الجريمة مع نوع العملية",
        "ops_lethal_h": "معدل الوفيات لكل 100 بيان حسب نوع العملية",
        "ops_lethal_cap": "يميز اللون القرمزي عمليات «تبادل إطلاق النار» لأنها تفسر التركز الأعلى لمعدلات الوفاة مقارنة بضبطيات القبض الاعتيادية.",
        "ops_sub_h": "أبرز التصنيفات الفرعية المسجلة (Top 10)",
        "con_kpis": ("إجمالي سجلات الأحراز", "إجمالي وزن المخدرات", "القيمة المالية الوسيطة المصرح بها"),
        "con_cat_h": "توزيع الأحراز والمضبوطات حسب الفئة (عدد السجلات)",
        "con_drug_h": "أبرز المواد المخدرة المضبوطة حسب الوزن الموحّد (كجم / طن)",
        "con_note": "تحذير منهجي ضد التضخيم (Anti-Fanout): الأرقام الرئيسية للبيانات والموقوفين تحسب من جدول الحقائق فقط، بينما تحسب كميات المضبوطات من جدول الجسر (bridge_incident_item) منفصلًا بعد توحيد الجرام والكيلو والطن (288 سجلًا مصححًا).",
        "dq_funnel_h": "حوكمة وجودة البيانات (Silver -> Gold)",
        "dq_checks_h": "نتائج اختبارات الجودة الحية على قاعدة البيانات",
        "dq_unit_h": "عينات توحيد أوزان المخدرات (معالجة 288 خطأ وحدة بين الجرام والطن)",
        "dq_fin_h": "عينات إصلاح الفواصل العشرية العربية (معالجة 15 رقمًا متطرفًا وتصفير 1,445 صفرًا وهميًا)",
        "led_sort_label": "ترتيب السجل",
        "led_sorts": {
            "date_desc": "الأحدث أولًا",
            "arrests_desc": "الأكثر من حيث الموقوفين",
            "deaths_desc": "الأكثر من حيث الوفيات",
            "financial_desc": "الأعلى قيمة مالية",
        },
        "led_dl": "تنزيل النطاق الحالي (CSV)",
        "led_hint": "اضغط على أي صف في الجدول لعرض ملف الواقعة التفصيلي والمضبوطات المرتبطة بها.",
        "led_dossier_h": "ملف الواقعة التفصيلي",
        "led_items_h": "المضبوطات المسجلة في هذه الواقعة",
        "led_no_items": "لا توجد سجلات مضبوطات منفصلة مسجلة لهذه الواقعة في جدول الجسر.",
        "led_source": "فتح رابط البيان الأصلي",
        "station_lbl": "قسم / مركز الشرطة:",
        "empty_msg": "لا توجد بيانات تطابق الفلاتر المختارة حاليًا. جرب توسيع النطاق أو الضغط على «إعادة ضبط الفلاتر».",
    },
    "en": {
        "kicker": "MOI CRIMINAL OBSERVATORY · GOLD STAR SCHEMA",
        "title": "Egyptian Ministry of Interior Releases Observatory",
        "subtitle": "Operational tracking of arrest releases, multi-case campaigns, governorate footprint, contraband mass, and audited Gold data quality.",
        "sidebar_lang": "لغة الواجهة · Language",
        "sidebar_filters": "Scope & Filters · التصفية",
        "scope_label": "Release Scope · نطاق البيانات",
        "scope_all": "كافة البيانات · All Criminal Releases",
        "scope_single": "وقائع منفردة · Single Incidents Only",
        "year_label": "Release Year · السنة",
        "region_label": "Regions · الأقاليم",
        "region_ph": "All regions",
        "gov_label": "Governorates · المحافظات",
        "gov_ph": "All governorates",
        "crime_label": "Crime Category · نوع الجريمة",
        "crime_ph": "All categories",
        "event_label": "Operation Type · نوع العملية",
        "event_ph": "All operations",
        "search_label": "Headline Search · بحث في العناوين",
        "search_ph": "e.g., حشيش، غسل أموال...",
        "reset_btn": "Reset Filters · إعادة ضبط",
        "slice_prefix": "Active Slice:",
        "slice_showing": "Showing",
        "slice_of": "of",
        "slice_releases": "releases",
        "kpi_releases": "Official Releases · البيانات",
        "kpi_arrests": "Arrests · الموقوفون",
        "kpi_deaths": "Fatalities · الوفيات",
        "kpi_drugs": "Narcotics · المخدرات",
        "kpi_financial": "Stated Value · القيمة المالية",
        "national_share": "of national",
        "kpi_releases_sub": "{single:,} single · {camp:,} campaigns",
        "kpi_arrests_sub": "Avg {avg:.1f} arrests / release",
        "kpi_deaths_sub": "{clash:,} in armed clashes",
        "kpi_drugs_sub": "{rows:,} standardized drug records",
        "kpi_fin_sub": "{cnt:,} stated · median {med}",
        "tabs": [
            "نظرة عامة · Overview",
            "الجغرافيا · Geography",
            "العمليات · Operations",
            "المضبوطات · Contraband",
            "جودة البيانات · Data Quality",
            "السجل · Case Dossier",
        ],
        "ov_monthly_h": "Monthly Release Trajectory · المسار الشهري للبيانات",
        "ov_monthly_cap": "Bars show monthly release count; ochre line traces the 3-month rolling average.",
        "ov_crimes_h": "Top 10 Crime Categories · أعلى تصنيفات الجرائم",
        "ov_ops_h": "Single Incidents vs. Campaigns · الوقائع المنفردة مقابل الحملات",
        "ov_insight": "Slice structure: Single-incident releases account for {pct_single:.1f}% ({single:,}) while multi-case enforcement campaigns make up {pct_camp:.1f}% ({camp:,}).",
        "geo_metric_label": "Map & Ranking Metric · المؤشر",
        "geo_metrics": {
            "releases": "البيانات · Releases",
            "arrests": "الموقوفون · Arrests",
            "deaths": "الوفيات · Deaths",
            "financial": "القيمة · Stated EGP",
        },
        "geo_map_h": "Governorate Footprint · التوزيع الجغرافي عبر المحافظات",
        "geo_rank_h": "Top 12 Governorates · أعلى 12 محافظة",
        "geo_region_h": "Regional Totals (Includes Nationwide Releases) · التوزيع الإقليمي",
        "geo_unknown_note": "Methodological note: {unk:,} releases in this slice have unspecified/nationwide governorate scope and are excluded from map pins while retained under «غير محدد · Nationwide» below.",
        "ops_heat_h": "Crime Category × Operation Matrix · مصفوفة الجرائم والعمليات",
        "ops_lethal_h": "Fatality Rate per 100 Releases · معدل الوفيات لكل 100 بيان",
        "ops_lethal_cap": "Crimson isolates Armed Clashes (تبادل إطلاق نار), explaining the primary concentration of fatalities.",
        "ops_sub_h": "Top Recorded Subcategories · أبرز التصنيفات الفرعية",
        "con_kpis": ("Seized Item Records · سجلات الأحراز", "Narcotics Mass · وزن المخدرات", "Median Stated EGP · الوسيط المالي"),
        "con_cat_h": "Seizures by Category (Record Count) · تصنيفات المضبوطات",
        "con_drug_h": "Top Narcotics by Standardized Mass · أبرز المخدرات بالوزن",
        "con_note": "Anti-fanout design: release counts & arrests stay strictly at fact_incident grain while item mass comes independently from bridge_incident_item (288 unit-corrected rows).",
        "dq_funnel_h": "Silver -> Gold Pipeline Governance · حوكمة جودة البيانات",
        "dq_checks_h": "Live Warehouse Audit Checks · اختبارات الجودة الحية",
        "dq_unit_h": "Unit Normalization Samples (288 rows fixed: g / kg / ton) · عينات توحيد الأوزان",
        "dq_fin_h": "Arabic Decimal-Comma Repairs (15 outliers fixed, 1,445 fake zeros nullified) · عينات تصحيح القيم المالية",
        "led_sort_label": "Sort Order · الترتيب",
        "led_sorts": {
            "date_desc": "الأحدث · Newest",
            "arrests_desc": "الموقوفون · Arrests",
            "deaths_desc": "الوفيات · Deaths",
            "financial_desc": "القيمة · Financial EGP",
        },
        "led_dl": "Download Slice CSV · تنزيل السجل",
        "led_hint": "Select any row in the table below to populate the full Arabic Case Dossier and linked seizures.",
        "led_dossier_h": "Case Dossier · ملف الواقعة التفصيلي",
        "led_items_h": "Linked Contraband Items · المضبوطات المسجلة",
        "led_no_items": "No itemized contraband rows recorded in bridge_incident_item for this release.",
        "led_source": "Open Source Post · رابط البيان الأصلي",
        "station_lbl": "Police Station · القسم/المركز:",
        "empty_msg": "No records match your active filters. Broaden the selection or click Reset Filters.",
    },
}


@st.cache_data(ttl=600, show_spinner=False)
def _get_cached_data() -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    return load_incidents(), load_items(), load_quality_audit()


def _reset_filters(defaults: dict) -> None:
    for key, val in defaults.items():
        st.session_state[key] = list(val) if isinstance(val, list) else val


def _clean_html(raw: str) -> str:
    """Strip leading indentation and blank lines so CommonMark never opens a code block."""
    return "\n".join(line.strip() for line in raw.splitlines() if line.strip())


def _render_css(is_ar: bool) -> None:
    dir_rules = (
        """
        [data-testid="stAppViewContainer"],
        [data-testid="stSidebar"] {
            direction: rtl;
            text-align: right;
        }
        [data-testid="stSlider"] {
            direction: ltr !important;
        }
        """
        if is_ar
        else """
        [data-testid="stAppViewContainer"],
        [data-testid="stSidebar"] {
            direction: ltr;
            text-align: left;
        }
        """
    )

    accent_side = "border-right: 3px solid" if is_ar else "border-left: 3px solid"
    st.markdown(
        _clean_html(
            f"""
            <link rel="preconnect" href="https://fonts.googleapis.com">
            <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
            <link href="https://fonts.googleapis.com/css2?family=IBM+Plex+Sans+Arabic:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500&family=Plus+Jakarta+Sans:wght@400;500;600;700&display=swap" rel="stylesheet">
            <style>
            html, body, [class*="css"], [data-testid="stAppViewContainer"], [data-testid="stSidebar"] {{
                font-family: 'IBM Plex Sans Arabic', 'Plus Jakarta Sans', -apple-system, BlinkMacSystemFont, sans-serif;
                color: {PALETTE["ink"]};
            }}
            {dir_rules}
            .js-plotly-plot,
            .plot-container,
            .svg-container {{
                direction: ltr !important;
            }}
            [data-testid="stHeader"] {{
                background: rgba(247, 246, 242, 0.92);
                backdrop-filter: blur(6px);
            }}
            .block-container {{
                padding-top: 3.4rem;
                padding-bottom: 2.5rem;
                max-width: 1380px;
            }}
            .masthead {{
                border-bottom: 1px solid {PALETTE["hairline"]};
                padding-bottom: 0.9rem;
                margin-bottom: 1.0rem;
            }}
            .masthead-kicker {{
                font-size: 0.74rem;
                font-weight: 600;
                letter-spacing: 0.06em;
                color: {PALETTE["navy"]};
                margin-bottom: 0.25rem;
            }}
            .masthead-title {{
                font-size: 1.72rem;
                font-weight: 700;
                line-height: 1.25;
                margin: 0 0 0.3rem 0;
                color: {PALETTE["ink"]};
            }}
            .masthead-sub {{
                font-size: 0.92rem;
                color: {PALETTE["muted_ink"]};
                margin: 0;
            }}
            .slice-banner {{
                background: {PALETTE["sidebar"]};
                border: 1px solid {PALETTE["hairline"]};
                {accent_side} {PALETTE["navy"]};
                border-radius: 6px;
                padding: 0.55rem 0.9rem;
                font-size: 0.85rem;
                margin-bottom: 0.95rem;
                color: {PALETTE["ink"]};
            }}
            .kpi-card {{
                background: {PALETTE["surface"]};
                border: 1px solid {PALETTE["hairline"]};
                border-top: 3px solid {PALETTE["navy"]};
                border-radius: 8px;
                padding: 0.85rem 1.0rem;
                height: 100%;
            }}
            .kpi-card.crimson {{ border-top-color: {PALETTE["crimson"]}; }}
            .kpi-card.ochre {{ border-top-color: {PALETTE["ochre"]}; }}
            .kpi-card.teal {{ border-top-color: {PALETTE["teal"]}; }}
            .kpi-lbl {{
                font-size: 0.78rem;
                font-weight: 600;
                color: {PALETTE["muted_ink"]};
                margin-bottom: 0.35rem;
            }}
            .kpi-val {{
                font-size: 1.55rem;
                font-weight: 700;
                font-variant-numeric: tabular-nums;
                line-height: 1.2;
                color: {PALETTE["ink"]};
            }}
            .kpi-sub {{
                font-size: 0.76rem;
                color: {PALETTE["muted_ink"]};
                margin-top: 0.35rem;
                line-height: 1.35;
            }}
            .kpi-share {{
                display: inline-block;
                background: #EEF3F7;
                color: {PALETTE["navy"]};
                font-size: 0.71rem;
                font-weight: 600;
                padding: 0.1rem 0.45rem;
                border-radius: 4px;
                margin-top: 0.3rem;
            }}
            .insight-box {{
                background: {PALETTE["surface"]};
                border: 1px solid {PALETTE["hairline"]};
                {accent_side} {PALETTE["teal"]};
                border-radius: 6px;
                padding: 0.7rem 0.95rem;
                font-size: 0.86rem;
                color: {PALETTE["ink"]};
                margin-top: 0.5rem;
            }}
            .audit-row {{
                display: flex;
                justify-content: space-between;
                align-items: center;
                background: {PALETTE["surface"]};
                border: 1px solid {PALETTE["hairline"]};
                border-radius: 6px;
                padding: 0.6rem 0.9rem;
                margin-bottom: 0.45rem;
                font-size: 0.88rem;
            }}
            .badge-pass {{
                background: {PALETTE["pass_bg"]};
                color: {PALETTE["pass_text"]};
                font-family: 'JetBrains Mono', monospace;
                font-size: 0.74rem;
                font-weight: 700;
                padding: 0.15rem 0.55rem;
                border-radius: 4px;
            }}
            .badge-fail {{
                background: {PALETTE["fail_bg"]};
                color: {PALETTE["fail_text"]};
                font-family: 'JetBrains Mono', monospace;
                font-size: 0.74rem;
                font-weight: 700;
                padding: 0.15rem 0.55rem;
                border-radius: 4px;
            }}
            .dossier-card {{
                background: {PALETTE["surface"]};
                border: 1px solid {PALETTE["hairline"]};
                border-top: 3px solid {PALETTE["navy"]};
                border-radius: 8px;
                padding: 1.05rem 1.2rem;
                margin-top: 0.65rem;
            }}
            .pill {{
                display: inline-block;
                background: {PALETTE["sidebar"]};
                border: 1px solid {PALETTE["hairline"]};
                border-radius: 4px;
                padding: 0.15rem 0.55rem;
                font-size: 0.76rem;
                font-weight: 600;
                margin-inline-end: 0.4rem;
                margin-bottom: 0.35rem;
            }}
            .pill-crime {{
                background: #E9EFF5;
                color: {PALETTE["navy"]};
                border-color: #CBD8E6;
            }}
            .num-ltr {{
                direction: ltr;
                display: inline-block;
                unicode-bidi: isolate;
                font-variant-numeric: tabular-nums;
            }}
            </style>
            """
        ),
        unsafe_allow_html=True,
    )


def _kpi_html(
    label: str,
    value: str,
    subcaption: str,
    share_badge: str | None = None,
    tone: str = "",
) -> str:
    badge_html = f'<div class="kpi-share">{html.escape(share_badge)}</div>' if share_badge else ""
    cls = f"kpi-card {tone}".strip()
    return (
        f'<div class="{cls}">'
        f'<div class="kpi-lbl">{html.escape(label)}</div>'
        f'<div class="kpi-val">{html.escape(value)}</div>'
        f"{badge_html}"
        f'<div class="kpi-sub">{html.escape(subcaption)}</div>'
        f"</div>"
    )


def _fmt_gov(gov: str, is_ar: bool) -> str:
    if is_ar:
        return gov
    coords = GOVERNORATE_COORDS.get(gov)
    return f"{gov} · {coords[2]}" if coords else gov


def main() -> None:
    incidents_df, items_df, audit = _get_cached_data()

    # 1. Sidebar language switcher MUST stay at top & initialize cleanly before CSS
    st.session_state.setdefault("ui_lang", "Bilingual (AR · EN)")
    ui_lang = st.sidebar.radio(
        _TEXT["ar"]["sidebar_lang"],
        options=["Bilingual (AR · EN)", "العربية"],
        key="ui_lang",
        horizontal=True,
    )
    lang_code = "ar" if ui_lang == "العربية" else "en"
    is_ar = lang_code == "ar"
    txt = _TEXT[lang_code]

    _render_css(is_ar)

    # 2. Initialize code-backed filter defaults once (immune to mid-session language toggle)
    min_yr = int(incidents_df["year"].min())
    max_yr = int(incidents_df["year"].max())
    filter_defaults = {
        "f_scope": "all",
        "f_years": (min_yr, max_yr),
        "f_regions": [],
        "f_govs": [],
        "f_crimes": [],
        "f_events": [],
        "f_search": "",
    }
    for k, v in filter_defaults.items():
        st.session_state.setdefault(k, list(v) if isinstance(v, list) else v)

    # Label lookup maps matching raw database codes
    region_map = REGION_LABELS_AR if is_ar else REGION_LABELS_BI
    crime_map = CRIME_LABELS_AR if is_ar else CRIME_LABELS_BI
    event_map = EVENT_LABELS_AR if is_ar else EVENT_LABELS_BI
    scope_map = {"all": txt["scope_all"], "single": txt["scope_single"]}

    region_options = incidents_df["region"].value_counts().index.tolist()
    crime_options = incidents_df["crime_category"].value_counts().index.tolist()
    event_options = incidents_df["event_type"].value_counts().index.tolist()

    # 3. Sidebar controls
    st.sidebar.markdown(f"### {txt['sidebar_filters']}")
    f_scope = st.sidebar.radio(
        txt["scope_label"],
        options=["all", "single"],
        format_func=lambda code: scope_map[code],
        key="f_scope",
    )
    f_years = st.sidebar.slider(
        txt["year_label"],
        min_value=min_yr,
        max_value=max_yr,
        key="f_years",
    )
    f_regions = st.sidebar.multiselect(
        txt["region_label"],
        options=region_options,
        format_func=lambda c: region_map.get(c, c),
        placeholder=txt["region_ph"],
        key="f_regions",
    )

    gov_pool = incidents_df[incidents_df["governorate"] != "unknown"]
    if f_regions:
        gov_pool = gov_pool[gov_pool["region"].isin(f_regions)]
    gov_options = gov_pool["governorate"].value_counts().index.tolist()

    # Keep cascading governorate state clean if selected regions narrow gov_options
    cleaned_govs = [g for g in st.session_state["f_govs"] if g in gov_options]
    if cleaned_govs != st.session_state["f_govs"]:
        st.session_state["f_govs"] = cleaned_govs

    f_govs = st.sidebar.multiselect(
        txt["gov_label"],
        options=gov_options,
        format_func=lambda g: _fmt_gov(g, is_ar),
        placeholder=txt["gov_ph"],
        key="f_govs",
    )
    f_crimes = st.sidebar.multiselect(
        txt["crime_label"],
        options=crime_options,
        format_func=lambda c: crime_map.get(c, c),
        placeholder=txt["crime_ph"],
        key="f_crimes",
    )
    f_events = st.sidebar.multiselect(
        txt["event_label"],
        options=event_options,
        format_func=lambda c: event_map.get(c, c),
        placeholder=txt["event_ph"],
        key="f_events",
    )
    f_search = st.sidebar.text_input(
        txt["search_label"],
        placeholder=txt["search_ph"],
        key="f_search",
    )

    st.sidebar.button(
        txt["reset_btn"],
        width="stretch",
        on_click=_reset_filters,
        args=(filter_defaults,),
    )

    # 4. Filter incidents & linked contraband bridge items
    mask = pd.Series(True, index=incidents_df.index)
    if f_scope == "single":
        mask &= ~incidents_df["is_campaign"]
    mask &= incidents_df["year"].between(f_years[0], f_years[1])
    if f_regions:
        mask &= incidents_df["region"].isin(f_regions)
    if f_govs:
        mask &= incidents_df["governorate"].isin(f_govs)
    if f_crimes:
        mask &= incidents_df["crime_category"].isin(f_crimes)
    if f_events:
        mask &= incidents_df["event_type"].isin(f_events)
    if f_search.strip():
        q = f_search.strip().lower()
        mask &= incidents_df["title"].fillna("").str.lower().str.contains(q, regex=False)

    filtered = incidents_df[mask].copy()
    filtered_items = items_df[items_df["incident_key"].isin(filtered["incident_key"])].copy()

    # 5. Masthead
    date_min = incidents_df["full_date"].min().strftime("%Y-%m-%d")
    date_max = incidents_df["full_date"].max().strftime("%Y-%m-%d")
    st.markdown(
        _clean_html(
            f"""
            <div class="masthead">
                <div class="masthead-kicker">{html.escape(txt["kicker"])} · <span class="num-ltr">{date_min} → {date_max}</span></div>
                <h1 class="masthead-title">{html.escape(txt["title"])}</h1>
                <p class="masthead-sub">{html.escape(txt["subtitle"])}</p>
            </div>
            """
        ),
        unsafe_allow_html=True,
    )

    # Active slice banner whenever any filter narrows below full dataset
    is_filtered = len(filtered) < len(incidents_df)
    if is_filtered:
        parts = [f"{txt['slice_showing']} {len(filtered):,} {txt['slice_of']} {len(incidents_df):,} {txt['slice_releases']}"]
        if f_scope == "single":
            parts.append(scope_map["single"])
        if f_years != (min_yr, max_yr):
            parts.append(f"{f_years[0]}–{f_years[1]}")
        if f_regions:
            parts.append("، ".join(region_map.get(r, r) for r in f_regions[:3]))
        if f_govs:
            parts.append("، ".join(_fmt_gov(g, is_ar) for g in f_govs[:3]))
        if f_crimes:
            parts.append("، ".join(crime_map.get(c, c) for c in f_crimes[:3]))
        if f_events:
            parts.append("، ".join(event_map.get(e, e) for e in f_events[:3]))
        if f_search.strip():
            parts.append(f'«{f_search.strip()}»')
        st.markdown(
            f'<div class="slice-banner"><b>{html.escape(txt["slice_prefix"])}</b> '
            + html.escape(" · ".join(parts))
            + "</div>",
            unsafe_allow_html=True,
        )

    # 6. National totals & filtered KPIs
    nat_rel = len(incidents_df)
    nat_arr = int(incidents_df["arrested_count"].sum())
    nat_dea = int(incidents_df["death_count"].sum())
    nat_drugs_kg = float(items_df.loc[items_df["item_category"] == "drugs", "quantity_kg"].fillna(0).sum())
    nat_fin_total = float(incidents_df["financial_value"].dropna().sum())

    cur_rel = len(filtered)
    cur_arr = int(filtered["arrested_count"].sum()) if cur_rel else 0
    cur_dea = int(filtered["death_count"].sum()) if cur_rel else 0
    cur_single = int((~filtered["is_campaign"]).sum()) if cur_rel else 0
    cur_camp = int(filtered["is_campaign"].sum()) if cur_rel else 0
    cur_clash_deaths = int(filtered.loc[filtered["event_type"] == "armed_clash", "death_count"].sum()) if cur_rel else 0

    drug_rows = filtered_items[filtered_items["item_category"] == "drugs"]
    cur_drugs_kg = float(drug_rows["quantity_kg"].fillna(0).sum()) if not drug_rows.empty else 0.0

    fin_series = filtered["financial_value"].dropna()
    cur_fin_cnt = int(len(fin_series))
    cur_fin_total = float(fin_series.sum()) if cur_fin_cnt else 0.0
    cur_fin_med = float(fin_series.median()) if cur_fin_cnt else None

    def _share(cur: float, nat: float) -> str | None:
        if not is_filtered or nat <= 0:
            return None
        return f"{(cur / nat) * 100:.1f}% {txt['national_share']}"

    kcols = st.columns(5)
    cards = [
        (
            txt["kpi_releases"],
            f"{cur_rel:,}",
            txt["kpi_releases_sub"].format(single=cur_single, camp=cur_camp),
            _share(cur_rel, nat_rel),
            "",
        ),
        (
            txt["kpi_arrests"],
            f"{cur_arr:,}",
            txt["kpi_arrests_sub"].format(avg=(cur_arr / cur_rel) if cur_rel else 0.0),
            _share(cur_arr, nat_arr),
            "teal",
        ),
        (
            txt["kpi_deaths"],
            f"{cur_dea:,}",
            txt["kpi_deaths_sub"].format(clash=cur_clash_deaths),
            _share(cur_dea, nat_dea),
            "crimson",
        ),
        (
            txt["kpi_drugs"],
            fmt_kg(cur_drugs_kg, lang=lang_code),
            txt["kpi_drugs_sub"].format(rows=len(drug_rows)),
            _share(cur_drugs_kg, nat_drugs_kg),
            "ochre",
        ),
        (
            txt["kpi_financial"],
            fmt_egp(cur_fin_total, lang=lang_code) if cur_fin_cnt else fmt_egp(None, lang=lang_code),
            txt["kpi_fin_sub"].format(cnt=cur_fin_cnt, med=fmt_egp(cur_fin_med, lang=lang_code)),
            _share(cur_fin_total, nat_fin_total) if cur_fin_cnt else None,
            "",
        ),
    ]
    for col, (lbl, val, sub, shr, tone) in zip(kcols, cards):
        col.markdown(_kpi_html(lbl, val, sub, shr, tone), unsafe_allow_html=True)

    st.markdown("<div style='height:0.65rem'></div>", unsafe_allow_html=True)

    if filtered.empty:
        st.info(txt["empty_msg"])
        return

    crime_col = "crime_label_ar" if is_ar else "crime_label_bi"
    region_col = "region_label_ar" if is_ar else "region_label_bi"
    item_cat_col = "item_category_ar" if is_ar else "item_category_bi"

    # 7. Six Main Tabs
    tab_ov, tab_geo, tab_ops, tab_con, tab_dq, tab_led = st.tabs(txt["tabs"])

    # ---------------- TAB 1: OVERVIEW ----------------
    with tab_ov:
        st.subheader(txt["ov_monthly_h"])
        st.caption(txt["ov_monthly_cap"])
        st.plotly_chart(chart_monthly_trajectory(filtered, lang=lang_code), width="stretch", theme=None)

        c1, c2 = st.columns([1.15, 1.0])
        with c1:
            st.subheader(txt["ov_crimes_h"])
            top_crimes = (
                filtered.groupby(crime_col, as_index=False)["incident_key"]
                .count()
                .rename(columns={"incident_key": "releases"})
                .sort_values("releases", ascending=False)
                .head(10)
            )
            st.plotly_chart(
                chart_ranked_barh(top_crimes, y_col=crime_col, x_col="releases", color=PALETTE["navy"], height=350),
                width="stretch",
                theme=None,
            )
        with c2:
            st.subheader(txt["ov_ops_h"])
            st.plotly_chart(chart_operation_divergence(filtered, lang=lang_code), width="stretch", theme=None)

        pct_single = (cur_single / cur_rel) * 100.0 if cur_rel else 0.0
        pct_camp = (cur_camp / cur_rel) * 100.0 if cur_rel else 0.0
        st.markdown(
            f'<div class="insight-box">{html.escape(txt["ov_insight"].format(pct_single=pct_single, single=cur_single, pct_camp=pct_camp, camp=cur_camp))}</div>',
            unsafe_allow_html=True,
        )

    # ---------------- TAB 2: GEOGRAPHY ----------------
    with tab_geo:
        st.session_state.setdefault("metric_select", "releases")
        metric_choice = st.radio(
            txt["geo_metric_label"],
            options=["releases", "arrests", "deaths", "financial"],
            format_func=lambda m: txt["geo_metrics"][m],
            horizontal=True,
            key="metric_select",
        )

        metric_styles = {
            "releases": (PALETTE["navy"], "{:,.0f}"),
            "arrests": (PALETTE["teal"], "{:,.0f}"),
            "deaths": (PALETTE["crimson"], "{:,.0f}"),
            "financial": (PALETTE["ochre"], "{:,.0f}"),
        }
        m_color, m_fmt = metric_styles[metric_choice]

        gov_known = filtered[filtered["governorate"] != "unknown"].copy()
        unknown_cnt = int((filtered["governorate"] == "unknown").sum())

        if gov_known.empty:
            st.info(txt["geo_unknown_note"].format(unk=unknown_cnt))
        else:
            gov_agg = (
                gov_known.groupby("governorate", as_index=False)
                .agg(
                    releases=("incident_key", "count"),
                    arrests=("arrested_count", "sum"),
                    deaths=("death_count", "sum"),
                    financial=("financial_value", "sum"),
                )
            )
            gov_agg["financial"] = gov_agg["financial"].fillna(0.0)
            gov_agg["lat"] = gov_agg["governorate"].map(lambda g: GOVERNORATE_COORDS.get(g, (None, None, g))[0])
            gov_agg["lon"] = gov_agg["governorate"].map(lambda g: GOVERNORATE_COORDS.get(g, (None, None, g))[1])
            gov_agg["gov_en"] = gov_agg["governorate"].map(lambda g: GOVERNORATE_COORDS.get(g, (None, None, g))[2])
            gov_agg["gov_disp"] = gov_agg["governorate"].map(lambda g: _fmt_gov(g, is_ar))
            mappable = gov_agg.dropna(subset=["lat", "lon"]).copy()

            g1, g2 = st.columns([1.25, 1.0])
            with g1:
                st.subheader(txt["geo_map_h"])
                st.plotly_chart(
                    chart_egypt_map(
                        mappable,
                        metric_col=metric_choice,
                        metric_label=txt["geo_metrics"][metric_choice],
                        color=m_color,
                        value_fmt=m_fmt,
                        height=440,
                        lang=lang_code,
                    ),
                    width="stretch",
                    theme=None,
                )
            with g2:
                st.subheader(txt["geo_rank_h"])
                top_govs = gov_agg.sort_values(metric_choice, ascending=False).head(12)
                fmt_fn = (lambda v: fmt_egp(v, lang=lang_code)) if metric_choice == "financial" else None
                st.plotly_chart(
                    chart_ranked_barh(
                        top_govs,
                        y_col="gov_disp",
                        x_col=metric_choice,
                        color=m_color,
                        value_fmt=m_fmt,
                        height=440,
                        formatter=fmt_fn,
                    ),
                    width="stretch",
                    theme=None,
                )

        if unknown_cnt > 0:
            st.caption(txt["geo_unknown_note"].format(unk=unknown_cnt))

        st.subheader(txt["geo_region_h"])
        reg_agg = (
            filtered.groupby(region_col, as_index=False)["incident_key"]
            .count()
            .rename(columns={"incident_key": "releases"})
            .sort_values("releases", ascending=False)
        )
        st.plotly_chart(
            chart_ranked_barh(
                reg_agg,
                y_col=region_col,
                x_col="releases",
                color=PALETTE["teal"],
                height=280,
                highlight_map={region_map.get("unknown", "unknown"): PALETTE["stone"]},
            ),
            width="stretch",
            theme=None,
        )

    # ---------------- TAB 3: OPERATIONS & CRIME MIX ----------------
    with tab_ops:
        o1, o2 = st.columns([1.2, 1.0])
        with o1:
            st.subheader(txt["ops_heat_h"])
            st.plotly_chart(chart_crime_event_heatmap(filtered, lang=lang_code), width="stretch", theme=None)
        with o2:
            st.subheader(txt["ops_lethal_h"])
            st.plotly_chart(chart_lethality_rate(filtered, lang=lang_code), width="stretch", theme=None)
            st.caption(txt["ops_lethal_cap"])

        sub_clean = filtered[
            filtered["crime_subcategory"].notna()
            & ~filtered["crime_subcategory"].isin(["unknown", "", "None"])
        ]
        if not sub_clean.empty:
            st.subheader(txt["ops_sub_h"])
            top_sub = (
                sub_clean.groupby("crime_subcategory", as_index=False)["incident_key"]
                .count()
                .rename(columns={"incident_key": "releases"})
                .sort_values("releases", ascending=False)
                .head(10)
            )
            st.plotly_chart(
                chart_ranked_barh(top_sub, y_col="crime_subcategory", x_col="releases", color=PALETTE["navy"], height=330),
                width="stretch",
                theme=None,
            )

    # ---------------- TAB 4: CONTRABAND & SEIZURES ----------------
    with tab_con:
        ck1, ck2, ck3 = st.columns(3)
        ck1.markdown(_kpi_html(txt["con_kpis"][0], f"{len(filtered_items):,}", txt["kpi_drugs_sub"].format(rows=len(drug_rows))), unsafe_allow_html=True)
        ck2.markdown(_kpi_html(txt["con_kpis"][1], fmt_kg(cur_drugs_kg, lang=lang_code), f"{int(drug_rows['is_unit_corrected'].sum()):,} unit-fixed" if not is_ar else f"{int(drug_rows['is_unit_corrected'].sum()):,} سجلًا موحد الوحدة", tone="ochre"), unsafe_allow_html=True)
        ck3.markdown(_kpi_html(txt["con_kpis"][2], fmt_egp(cur_fin_med, lang=lang_code), f"{cur_fin_cnt:,} {'stated' if not is_ar else 'بيان بقيمة مصرحة'} · {fmt_egp(cur_fin_total, lang=lang_code)}"), unsafe_allow_html=True)

        st.markdown("<div style='height:0.65rem'></div>", unsafe_allow_html=True)

        b1, b2 = st.columns(2)
        with b1:
            st.subheader(txt["con_cat_h"])
            cat_agg = (
                filtered_items.groupby(item_cat_col, as_index=False)["bridge_id"]
                .count()
                .rename(columns={"bridge_id": "records"})
                .sort_values("records", ascending=False)
                .head(12)
            )
            st.plotly_chart(
                chart_ranked_barh(cat_agg, y_col=item_cat_col, x_col="records", color=PALETTE["navy"], height=360),
                width="stretch",
                theme=None,
            )
        with b2:
            st.subheader(txt["con_drug_h"])
            drug_disp_map = {
                "امفيتامين، ميثامفيتامين، …": "أمفيتامين وميثامفيتامين",
                "حشيش – شابو – هيرورين – ا…": "حشيش وشابو وهيروين",
                'الايس "الشابو"': "الآيس (الشابو)",
                "مواد مخدره لاعاده التدوير": "مواد مخدرة لإعادة التدوير",
                "مواد مخدره": "مواد مخدرة عامة",
            }
            drug_clean = drug_rows.dropna(subset=["drug_canonical"]).copy()
            drug_clean["drug_display"] = drug_clean["drug_canonical"].map(lambda s: drug_disp_map.get(s, s))
            drugs_mass = (
                drug_clean.groupby("drug_display", as_index=False)["quantity_kg"]
                .sum()
                .sort_values("quantity_kg", ascending=False)
                .head(12)
            )
            st.plotly_chart(
                chart_ranked_barh(
                    drugs_mass,
                    y_col="drug_display",
                    x_col="quantity_kg",
                    color=PALETTE["ochre"],
                    height=360,
                    formatter=lambda v: fmt_kg(v, lang=lang_code),
                ),
                width="stretch",
                theme=None,
            )

        st.caption(txt["con_note"])

    # ---------------- TAB 5: DATA QUALITY & PIPELINE AUDIT ----------------
    with tab_dq:
        st.subheader(txt["dq_funnel_h"])
        dq_cols = st.columns(5)
        dq_cards = [
            ("Silver -> Gold (البيانات)" if is_ar else "Silver -> Gold Incidents", f"{audit['silver_incidents']:,} -> {audit['gold_incidents']:,}", "استبعاد الشائعات والتكرار" if is_ar else "Filtered rumors & duplicates", ""),
            ("Silver -> Gold (الأحراز)" if is_ar else "Silver -> Gold Items", f"{audit['silver_items']:,} -> {audit['gold_items']:,}", "سجلات جدول الجسر النظيفة" if is_ar else "Verified bridge rows", "teal"),
            ("تصحيح وحدات الوزن" if is_ar else "Unit Repairs", f"{audit['unit_corrected_rows']:,}", "جرام / كجم / طن" if is_ar else "g / kg / metric ton normalized", "ochre"),
            ("إصلاح الفواصل العشرية" if is_ar else "Comma Outlier Repairs", f"{audit['fin_corrected_rows']:,}", "تضخم تاريخي مصحح" if is_ar else "Arabic decimal-comma fixes", ""),
            ("أصفار مالية محولة لـ NULL" if is_ar else "Fake Zeros Nullified", f"{audit['silver_fake_zeros']:,}", "تمييز غير المعلن عن الصفر" if is_ar else "Zeroes coerced to NULL", ""),
        ]
        for col, (lbl, val, sub, tone) in zip(dq_cols, dq_cards):
            col.markdown(_kpi_html(lbl, val, sub, tone=tone), unsafe_allow_html=True)

        st.markdown("<div style='height:0.65rem'></div>", unsafe_allow_html=True)
        st.subheader(txt["dq_checks_h"])
        checks = [
            (
                "خلو الطبقة الذهبية من الشائعات والمنشورات الإدارية (rumor_admin_leaks = 0)" if is_ar else "Zero rumor/admin leaks in Gold (rumor_admin_leaks = 0)",
                audit["rumor_admin_leaks"] == 0,
                f"val={audit['rumor_admin_leaks']}",
            ),
            (
                "خلو الطبقة الذهبية من الأخبار المكررة (duplicate_news = 0)" if is_ar else "Zero duplicate releases in Gold (duplicate_news = 0)",
                audit["duplicate_news"] == 0,
                f"val={audit['duplicate_news']}",
            ),
            (
                "توحيد جميع وحدات أوزان المخدرات (unnormalized_units = 0)" if is_ar else "All drug units standardized (unnormalized_units = 0)",
                audit["unnormalized_units"] == 0,
                f"val={audit['unnormalized_units']}",
            ),
            (
                "الحد الأقصى لوزن شحنة المخدرات منطقي (<= 5,000 كجم)" if is_ar else "Max drug shipment weight <= 5,000 kg",
                float(audit["max_drug_kg"] or 0) <= 5000.0,
                f"max={float(audit['max_drug_kg'] or 0):,.1f} kg",
            ),
            (
                "عدم وجود قيم مالية صفرية وهمية (zero_financials = 0)" if is_ar else "Zero fake-zero financial rows (zero_financials = 0)",
                audit["zero_financials"] == 0,
                f"val={audit['zero_financials']}",
            ),
            (
                "الحد الأقصى للقيمة المالية الموثقة ضمن السقف المصحح (<= 2 مليار ج.م)" if is_ar else "Max stated financial value <= EGP 2B",
                float(audit["max_financial"] or 0) <= 2_000_000_000.0,
                f"max={fmt_egp(audit['max_financial'], lang=lang_code)}",
            ),
        ]
        for label, passed, metric_txt in checks:
            badge = '<span class="badge-pass">PASS</span>' if passed else '<span class="badge-fail">FAIL</span>'
            st.markdown(
                f'<div class="audit-row"><span>{html.escape(label)}</span>'
                f'<span><span class="num-ltr" style="margin-inline-end:0.65rem;color:{PALETTE["muted_ink"]}">{html.escape(metric_txt)}</span>{badge}</span></div>',
                unsafe_allow_html=True,
            )

        s1, s2 = st.columns(2)
        with s1:
            st.subheader(txt["dq_unit_h"])
            u_df = audit["unit_samples"].copy()
            u_df.columns = (
                ["معرف السجل", "الكمية الأصلية", "الوحدة الأصلية", "الوزن الذهبي (كجم)", "عنوان البيان"]
                if is_ar
                else ["Bridge ID", "Silver Qty", "Silver Unit", "Gold kg", "Title"]
            )
            st.dataframe(u_df, width="stretch", hide_index=True)
        with s2:
            st.subheader(txt["dq_fin_h"])
            f_df = audit["fin_samples"].copy()
            f_df.columns = (
                ["معرف الواقعة", "القيمة قبل الإصلاح", "القيمة الذهبية (ج.م)", "عنوان البيان"]
                if is_ar
                else ["Incident Key", "Silver EGP", "Gold EGP", "Title"]
            )
            st.dataframe(f_df, width="stretch", hide_index=True)

    # ---------------- TAB 6: INCIDENT LEDGER & CASE DOSSIER ----------------
    with tab_led:
        st.session_state.setdefault("sort_select", "date_desc")
        lc1, lc2 = st.columns([2.2, 1.0])
        with lc1:
            sort_choice = st.radio(
                txt["led_sort_label"],
                options=["date_desc", "arrests_desc", "deaths_desc", "financial_desc"],
                format_func=lambda s: txt["led_sorts"][s],
                horizontal=True,
                key="sort_select",
            )
        sort_map = {
            "date_desc": ("full_date", False),
            "arrests_desc": ("arrested_count", False),
            "deaths_desc": ("death_count", False),
            "financial_desc": ("financial_value", False),
        }
        scol, sasc = sort_map[sort_choice]
        sorted_df = filtered.sort_values(scol, ascending=sasc, na_position="last").reset_index(drop=True)

        csv_bytes = sorted_df.to_csv(index=False).encode("utf-8-sig")
        with lc2:
            st.markdown("<div style='height:1.35rem'></div>", unsafe_allow_html=True)
            st.download_button(
                txt["led_dl"],
                data=csv_bytes,
                file_name="moi_criminal_releases_slice.csv",
                mime="text/csv",
                width="stretch",
            )

        st.caption(txt["led_hint"])

        view_df = sorted_df.head(500).copy()
        event_col = "event_label_ar" if is_ar else "event_label_bi"
        tbl = pd.DataFrame(
            {
                "التاريخ" if is_ar else "التاريخ · Date": view_df["full_date"].dt.strftime("%Y-%m-%d"),
                "المحافظة" if is_ar else "المحافظة · Gov": view_df["governorate"].map(
                    lambda g: ("غير محدد" if is_ar else "غير محدد · Unspecified") if g == "unknown" else _fmt_gov(g, is_ar)
                ),
                "نوع الجريمة" if is_ar else "الجريمة · Crime": view_df[crime_col],
                "نوع العملية" if is_ar else "العملية · Op": view_df[event_col],
                "الموقوفون" if is_ar else "الموقوفون · Arrests": view_df["arrested_count"].astype(int),
                "الوفيات" if is_ar else "الوفيات · Deaths": view_df["death_count"].astype(int),
                "القيمة المالية" if is_ar else "القيمة · Value": view_df["financial_value"].apply(lambda v: fmt_egp(v, lang=lang_code)),
                "عنوان البيان" if is_ar else "العنوان · Title": view_df["title"].fillna(""),
            }
        )

        event = st.dataframe(
            tbl,
            width="stretch",
            hide_index=True,
            on_select="rerun",
            selection_mode="single-row",
            height=340,
        )

        sel_rows = event.selection.rows if event and hasattr(event, "selection") else []
        sel_idx = sel_rows[0] if sel_rows else 0
        row = view_df.iloc[sel_idx]

        # Live Case Dossier Card
        gov_disp = (
            ("غير محدد / عام" if is_ar else "غير محدد · Nationwide")
            if row["governorate"] == "unknown"
            else _fmt_gov(row["governorate"], is_ar)
        )
        reg_disp = row[region_col]
        station_raw = str(row["police_station_clean"] or "").strip()
        station_pill = (
            f'<span class="pill">{html.escape(txt["station_lbl"])} {html.escape(station_raw)}</span>'
            if station_raw and station_raw not in ("unknown", "None", "nan")
            else ""
        )
        date_str = row["full_date"].strftime("%Y-%m-%d")
        fin_str = fmt_egp(row["financial_value"], lang=lang_code)
        src_url = str(row["source_url"] or "").strip()
        link_html = (
            f' · <a href="{html.escape(src_url)}" target="_blank">{html.escape(txt["led_source"])}</a>'
            if src_url.startswith("http")
            else ""
        )

        st.markdown(f"### {txt['led_dossier_h']}")
        st.markdown(
            _clean_html(
                f"""
                <div class="dossier-card">
                    <div style="margin-bottom:0.55rem;">
                        <span class="pill pill-crime">{html.escape(str(row[crime_col]))}</span>
                        <span class="pill">{html.escape(str(row[event_col]))}</span>
                        <span class="pill">{html.escape(reg_disp)}</span>
                        <span class="pill">{html.escape(gov_disp)}</span>
                        {station_pill}
                    </div>
                    <div style="font-size:1.05rem;font-weight:700;line-height:1.5;margin-bottom:0.65rem;">
                        {html.escape(str(row["title"] or ""))}
                    </div>
                    <div style="font-size:0.86rem;color:{PALETTE["muted_ink"]};">
                        <span class="num-ltr">{date_str}</span> ·
                        {"الموقوفون" if is_ar else "Arrests"}: <b class="num-ltr">{int(row["arrested_count"]):,}</b> ·
                        {"الوفيات" if is_ar else "Deaths"}: <b class="num-ltr">{int(row["death_count"]):,}</b> ·
                        {"المصابون" if is_ar else "Injuries"}: <b class="num-ltr">{int(row["injury_count"]):,}</b> ·
                        {"القيمة المالية" if is_ar else "Stated Value"}: <b>{html.escape(fin_str)}</b>
                        {link_html}
                    </div>
                </div>
                """
            ),
            unsafe_allow_html=True,
        )

        linked = items_df[items_df["incident_key"] == row["incident_key"]].copy()
        st.markdown(f"**{txt['led_items_h']} ({len(linked)})**")
        if linked.empty:
            st.caption(txt["led_no_items"])
        else:
            linked_view = pd.DataFrame(
                {
                    "الفئة" if is_ar else "الفئة · Category": linked[item_cat_col],
                    "الصنف" if is_ar else "الصنف · Item": linked["item_type_clean"].fillna(""),
                    "الكمية" if is_ar else "الكمية · Qty": linked["quantity"].apply(lambda v: f"{v:,.2f}" if pd.notna(v) else "—"),
                    "الوحدة" if is_ar else "الوحدة · Unit": linked["unit_clean"].fillna("—"),
                    "الوزن (كجم)" if is_ar else "الوزن · kg": linked["quantity_kg"].apply(lambda v: f"{v:,.2f}" if pd.notna(v) else "—"),
                }
            )
            st.dataframe(linked_view, width="stretch", hide_index=True)


if __name__ == "__main__":
    main()
