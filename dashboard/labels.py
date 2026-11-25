"""Bilingual label mappings, editorial color tokens, and tabular formatters."""

import re

# Editorial Warm-Stone & Archival Ink palette (strict 4-hue ceiling + neutral stone)
PALETTE = {
    "canvas": "#F7F6F2",
    "surface": "#FFFFFF",
    "sidebar": "#EFECE6",
    "hairline": "#E2E0D8",
    "grid": "#EAE7DF",
    "ink": "#16181D",
    "muted_ink": "#5A6270",
    "navy": "#1B365D",       # Primary series: incident volume
    "teal": "#2E6F95",       # Secondary series: arrests / geographic reach
    "ochre": "#B7791F",      # Enforcement campaigns / valuation / audit corrections
    "crimson": "#B42318",    # Reserved strictly for fatalities & armed_clash lethality
    "stone": "#94A3B8",      # Unspecified / other buckets
    "pass_text": "#166534",
    "pass_bg": "#DCFCE7",
    "fail_text": "#991B1B",
    "fail_bg": "#FEE2E2",
}

CRIME_LABELS_EN = {
    "drugs": "Narcotics Trafficking",
    "violence_assault": "Violence & Assault",
    "fraud": "Fraud & Scams",
    "commercial_fraud_supply": "Supply & Commercial Fraud",
    "other_crime": "Other Criminal Offenses",
    "theft_robbery": "Theft & Armed Robbery",
    "financial_crimes": "Financial & Money Laundering",
    "false_news_cyber": "Cybercrime & False Claims",
    "weapons_firearms": "Illegal Firearms & Ammo",
    "traffic_accident": "Traffic Violations & Accidents",
    "homicide": "Homicide & Attempted Murder",
    "kidnapping_extortion": "Kidnapping & Extortion",
    "juvenile_exploitation": "Juvenile Exploitation",
    "antiquities": "Antiquities Trafficking",
    "missing_person": "Missing Persons",
}

CRIME_LABELS_AR = {
    "drugs": "المخدرات",
    "violence_assault": "العنف والاعتداء",
    "fraud": "النصب والاحتيال",
    "commercial_fraud_supply": "الغش التجاري والتموين",
    "other_crime": "جرائم أخرى",
    "theft_robbery": "السرقة والسطو",
    "financial_crimes": "الجرائم المالية",
    "false_news_cyber": "الجرائم الإلكترونية",
    "weapons_firearms": "الأسلحة والذخائر",
    "traffic_accident": "حوادث المرور",
    "homicide": "القتل والشروع فيه",
    "kidnapping_extortion": "الخطف والابتزاز",
    "juvenile_exploitation": "استغلال الأحداث",
    "antiquities": "التنقيب وتهريب الآثار",
    "missing_person": "التغيب والفقد",
}

CRIME_LABELS_BI = {
    "drugs": "مخدرات · Narcotics",
    "violence_assault": "عنف واعتداء · Violence",
    "fraud": "نصب واحتيال · Fraud",
    "commercial_fraud_supply": "غش تجاري · Commercial",
    "other_crime": "جرائم أخرى · Other",
    "theft_robbery": "سرقة وسطو · Theft",
    "financial_crimes": "جرائم مالية · Financial",
    "false_news_cyber": "إلكترونية · Cybercrime",
    "weapons_firearms": "أسلحة وذخائر · Firearms",
    "traffic_accident": "حوادث مرور · Traffic",
    "homicide": "قتل وشروع · Homicide",
    "kidnapping_extortion": "خطف وابتزاز · Extortion",
    "juvenile_exploitation": "استغلال أحداث · Juvenile",
    "antiquities": "تهريب آثار · Antiquities",
    "missing_person": "تغيب · Missing Persons",
}

EVENT_LABELS_EN = {
    "arrest_operation": "Arrest Operation",
    "viral_claim_investigation": "Viral Claim Investigation",
    "enforcement_campaign": "Enforcement Campaign",
    "armed_clash": "Armed Clash",
    "other": "Other Operations",
}

EVENT_LABELS_AR = {
    "arrest_operation": "عملية ضبط",
    "viral_claim_investigation": "كشف منشور متداول",
    "enforcement_campaign": "حملة أمنية",
    "armed_clash": "تبادل إطلاق نار",
    "other": "عمليات أخرى",
}

EVENT_LABELS_BI = {
    "arrest_operation": "عملية ضبط · Arrest Op",
    "viral_claim_investigation": "منشور متداول · Viral",
    "enforcement_campaign": "حملة أمنية · Campaign",
    "armed_clash": "إطلاق نار · Armed Clash",
    "other": "أخرى · Other Ops",
}

REGION_LABELS_AR = {
    "القاهرة الكبرى": "القاهرة الكبرى",
    "الدلتا": "الدلتا",
    "الصعيد": "الصعيد",
    "الإسكندرية والساحل الشمالي": "الإسكندرية والساحل",
    "القناة": "مدن القناة",
    "سيناء والبحر الأحمر": "سيناء والبحر الأحمر",
    "unknown": "غير محدد / عام",
}

REGION_LABELS_BI = {
    "القاهرة الكبرى": "القاهرة الكبرى · Cairo",
    "الدلتا": "الدلتا · Nile Delta",
    "الصعيد": "الصعيد · Upper Egypt",
    "الإسكندرية والساحل الشمالي": "الإسكندرية · Alex & Coast",
    "القناة": "القناة · Suez Canal",
    "سيناء والبحر الأحمر": "سيناء والبحر الأحمر · Sinai",
    "unknown": "غير محدد · Nationwide",
}

ITEM_CATEGORY_LABELS_EN = {
    "drugs": "Narcotics",
    "weapon": "Weapons",
    "goods_commodities": "Goods & Commodities",
    "phones_electronics": "Phones & Electronics",
    "vehicle": "Vehicles",
    "other": "Other Items",
    "ammunition": "Ammunition",
    "cash_valuables": "Cash & Valuables",
    "tools_equipment": "Tools & Equipment",
    "cards_wallets": "Cards & Documents",
    "animal": "Livestock / Animals",
}

ITEM_CATEGORY_LABELS_AR = {
    "drugs": "مواد مخدرة",
    "weapon": "أسلحة",
    "goods_commodities": "سلع وبضائع",
    "phones_electronics": "هواتف وإلكترونيات",
    "vehicle": "مركبات",
    "other": "مضبوطات أخرى",
    "ammunition": "ذخائر وطلقات",
    "cash_valuables": "عملات ومشغولات",
    "tools_equipment": "أدوات ومعدات",
    "cards_wallets": "بطاقات ومحافظ",
    "animal": "حيوانات وماشية",
}

ITEM_CATEGORY_LABELS_BI = {
    "drugs": "مواد مخدرة · Narcotics",
    "weapon": "أسلحة · Weapons",
    "goods_commodities": "سلع وبضائع · Goods",
    "phones_electronics": "إلكترونيات · Electronics",
    "vehicle": "مركبات · Vehicles",
    "other": "أخرى · Other Items",
    "ammunition": "ذخائر · Ammunition",
    "cash_valuables": "نقد ومشغولات · Valuables",
    "tools_equipment": "أدوات ومعدات · Tools",
    "cards_wallets": "بطاقات ومستندات · Cards",
    "animal": "حيوانات · Livestock",
}

# Governorate centroids (lat, lon, English display name) for Egypt choropleth/bubble map
GOVERNORATE_COORDS: dict[str, tuple[float, float, str]] = {
    "القاهرة": (30.0444, 31.2357, "Cairo"),
    "الجيزة": (30.0131, 31.2089, "Giza"),
    "القليوبية": (30.4660, 31.1848, "Qalyubia"),
    "الإسكندرية": (31.2001, 29.9187, "Alexandria"),
    "البحيرة": (31.0409, 30.4700, "Beheira"),
    "مطروح": (31.3543, 27.2373, "Matrouh"),
    "دمياط": (31.4175, 31.8144, "Damietta"),
    "الدقهلية": (31.0409, 31.3785, "Dakahlia"),
    "كفر الشيخ": (31.1107, 30.9388, "Kafr El-Sheikh"),
    "الغربية": (30.7865, 31.0004, "Gharbia"),
    "المنوفية": (30.5503, 31.0106, "Monufia"),
    "الشرقية": (30.5765, 31.5041, "Sharqia"),
    "بورسعيد": (31.2653, 32.3019, "Port Said"),
    "الإسماعيلية": (30.5965, 32.2715, "Ismailia"),
    "السويس": (29.9668, 32.5498, "Suez"),
    "شمال سيناء": (31.1321, 33.8033, "North Sinai"),
    "جنوب سيناء": (28.2417, 33.6222, "South Sinai"),
    "بني سويف": (29.0661, 31.0994, "Beni Suef"),
    "الفيوم": (29.3084, 30.8428, "Fayoum"),
    "المنيا": (28.1099, 30.7503, "Minya"),
    "أسيوط": (27.1783, 31.1859, "Assiut"),
    "الوادي الجديد": (25.4514, 30.5463, "New Valley"),
    "البحر الأحمر": (27.2579, 33.8116, "Red Sea"),
    "سوهاج": (26.5591, 31.6957, "Sohag"),
    "قنا": (26.1551, 32.7160, "Qena"),
    "الأقصر": (25.6872, 32.6396, "Luxor"),
    "أسوان": (24.0889, 32.8998, "Aswan"),
}


def canonicalize_drug_name(name: str) -> str:
    """Fold minor Arabic phrasing variants (e.g. 'مخدر الحشيش' vs 'حشيش') for clean charts."""
    if not name:
        return "غير محدد"
    text = str(name).strip()
    if text.startswith(("مواد مخدره متنوعه", "المواد المخدره المتنوعه")):
        return "مواد مخدرة متنوعة (مجمعة)"
    if "حشيش" in text and "هيدرو" in text and not any(k in text for k in ("شابو", "ايس", "هيروين", "كوكايين")):
        return "حشيش وهيدرو (مشترك)"
    text = re.sub(r"^(?:كميات?\s+من\s+|مخدر\s+|عقار\s+)+", "", text)
    if text.startswith("ال") and len(text) > 4 and text not in ("الهيروين",):
        stripped = text[2:]
        if stripped in ("حشيش", "بانجو", "شابو", "ايس", "هيدرو", "هيروين", "استروكس", "كبتاجون", "ترامادول"):
            text = stripped
    return text if len(text) <= 26 else text[:25] + "…"


def fmt_int(val) -> str:
    if val is None:
        return "0"
    return f"{int(round(float(val))):,}"


def fmt_egp(val, lang: str = "ar") -> str:
    """Format EGP compactly in Arabic or English units using tabular precision."""
    if val is None or (isinstance(val, float) and val != val):
        return "غير معلن" if lang == "ar" else "N/A"
    num = float(val)
    if lang == "ar":
        if num >= 1_000_000_000:
            return f"{num / 1_000_000_000:.2f} مليار ج.م"
        if num >= 1_000_000:
            return f"{num / 1_000_000:.1f} مليون ج.م"
        if num >= 1_000:
            return f"{num / 1_000:.0f} ألف ج.م"
        return f"{num:,.0f} ج.م"
    if num >= 1_000_000_000:
        return f"EGP {num / 1_000_000_000:.2f}B"
    if num >= 1_000_000:
        return f"EGP {num / 1_000_000:.1f}M"
    if num >= 1_000:
        return f"EGP {num / 1_000:.0f}K"
    return f"EGP {num:,.0f}"


def fmt_kg(val, lang: str = "ar") -> str:
    """Format kilogram totals cleanly in Arabic or English units."""
    if val is None or (isinstance(val, float) and val != val):
        return "0 كجم" if lang == "ar" else "0 kg"
    num = float(val)
    if lang == "ar":
        if num >= 1_000:
            return f"{num / 1_000:,.1f} طن"
        return f"{num:,.1f} كجم"
    if num >= 1_000:
        return f"{num / 1_000:,.1f} t"
    return f"{num:,.1f} kg"
