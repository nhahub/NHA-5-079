import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.transform_silver import (
    normalize_arabic,
    extract_location_id,
    extract_crime_type_id,
    extract_metrics,
    extract_date_id
)

def test_normalize_arabic():
    assert normalize_arabic("") == ""
    assert normalize_arabic("مُخَدِّرَات") == "مخدرات"
    assert normalize_arabic("الإسماعيلية") == "الاسماعيليه"

def test_extract_location_id():
    assert extract_location_id("ضبط شخص في العريش", "") == 26 
    assert extract_location_id("مشاجرة في المنتزه", "") == 4
    assert extract_location_id("بيان رسمي عام", "لا تفاصيل") == 0
    assert extract_location_id("بيان من القاهرة حول ضبط متهم في العريش", "") == 26

def test_extract_crime_type_id():
    assert extract_crime_type_id("ضبط حشيش وهيروين", "") == 2
    assert extract_crime_type_id("حيازة بندقية آلية وذخائر", "") == 3
    assert extract_crime_type_id("بيان مرور عادي", "") == 0

def test_extract_metrics():
    assert extract_metrics("حملة مكبرة لضبط 3 اشخاص وبندقيه", "") == (3, 1, True)
    assert extract_metrics("ضبط شخصين بمطروح", "") == (2, 0, False)

def test_real_moi_article():
    #https://moi.gov.eg/news/GetDetails?newsId=f32fbd78-7b9d-4981-b742-d7c65d0570dd&sectionId=3
    title = 'كشف ملابسات مقطع فيديو تضمن قيام الأهالى بإمساك أحد الأشخاص يرتدى ملابس نسائية بالجيزة'
    body = """فى إطار كشف ملابسات منشور مدعوم بمقطع فيديو تم تداوله بمواقع التواصل الإجتماعى تضمن قيام الأهالى بإمساك أحد الأشخاص يرتدى ملابس نسائية وإدعاء طفل بمحاولته خطف شقيقته بالجيزة.
بالفحص تبين أنه بتاريخ 2/ الجارى تبلغ لقسم شرطة بولاق الدكرور بالجيزة من مالك مطعم وبعض الأهالى بالإمساك برجل يرتدى ملابس نسائية وإستجداء المارة بأحد الشوارع بدائرة القسم.. وبالإنتقال وسؤال (مالك المطعم المُشار إليه - مقيم بدائرة القسم) أقر أنه حال تواجده بمحل عمله الكائن بذات الدائرة إرتاب فى المشكو فى حقه حال سيره بذات المنطقة فأستوقفه بمساعدة الأهالى وقام بكشف النقاب عن وجهه وتبين أنه رجل.
وبمواجهة المشكو فى حقه (عاطل "له معلومات جنائية" - مقيم بدائرة القسم)، أقر بأنه يقوم بإرتداء النقاب لإستجداء المارة والتحصل منهم على مبالغ مالية ونفى قيامه بمحاولة إختطاف الطفلة المذكورة.. وبسؤال الطفل "الظاهر بمقطع الفيديو" أقر بإختلاقه واقعة محاولة المشكو فى حقه خطف شقيقته حال مشاهدته الأهالى ممسكين به ، ونفت شقيقته تعرضها لمكروه.
تم إتخاذ الإجراءات القانونية.. وتولت النيابة العامة التحقيق.
    """
    assert extract_location_id(title, body) == 2
    assert extract_crime_type_id(title, body) == 0
    assert extract_metrics(title, body) == (1, 0, False)


def test_extract_date_id():
    assert extract_date_id("2026-11-05") == 20261105 
    assert extract_date_id(None) == 0 
    assert extract_date_id("invalid") == 0 
   

