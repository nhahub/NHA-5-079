import sys
import re
import json
import time
import logging
from pathlib import Path
from datetime import datetime, timezone
import requests
from bs4 import BeautifulSoup

# Ensure UTF-8 output in Windows PowerShell/cmd terminals
if sys.stdout.encoding != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if sys.stderr.encoding != "utf-8":
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[logging.StreamHandler(sys.stdout)],
)

logger = logging.getLogger("extract_bronze")


# --- CONFIGURATION ---
INDEX_ENDPOINT = "https://www.moi.gov.eg/News/GetNews"
DETAILS_ENDPOINT = "https://www.moi.gov.eg/news/GetDetails"
SECTION_ID = 3  # أهم القضايا (Major Crime Cases)
ARTICLES_PER_PAGE = 8

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json, text/javascript, */*; q=0.01",
    "X-Requested-With": "XMLHttpRequest",
    "Referer": "https://www.moi.gov.eg/"
}


def parse_moi_date(date_raw):
    """
    Parses .NET timestamp format like '/Date(1790528008227)/'
    into a clean ISO datetime timestamp string (YYYY-MM-DD HH:MM:SS).
    """
    if not date_raw:
        return None
    
    match = re.search(r"\d+", str(date_raw))
    if not match:
        return None

    epoch_ms = int(match.group())
    dt = datetime.fromtimestamp(epoch_ms / 1000.0, tz=timezone.utc)
    return dt.strftime("%Y-%m-%d %H:%M:%S")


def fetch_article_details(session, news_id, section_id=SECTION_ID, max_retries=3):
    """
    Fetches the un-truncated full body paragraphs from the detail page using BeautifulSoup.
    Uses persistent HTTP session for connection reuse.
    """
    url = f"{DETAILS_ENDPOINT}?newsId={news_id}&sectionId={section_id}"
    
    for attempt in range(1, max_retries + 1):
        try:
            response = session.get(url, headers=HEADERS, timeout=12)
            if response.status_code == 200:
                soup = BeautifulSoup(response.text, "lxml")
                
                # Extract all legitimate article paragraphs while excluding nav, footer, and menu text
                paragraphs = []
                for p in soup.find_all("p"):
                    if p.find_parent("nav") or p.find_parent("footer"):
                        continue
                    text = p.get_text(strip=True)
                    if not text or "القائمة الرئيسية" in text or "جميع الحقوق محفوظة" in text:
                        continue
                    paragraphs.append(text)

                if paragraphs:
                    return "\n\n".join(paragraphs), paragraphs
                return "", []
            elif response.status_code == 429:
                wait_time = 2 * attempt
                logger.warning(f"[429 Rate Limit] Backing off for {wait_time}s...")
                time.sleep(wait_time)
            else:
                time.sleep(1)
        except requests.RequestException as e:
            if attempt == max_retries:
                logger.warning(f"Failed to fetch details for {news_id}: {e}")
            time.sleep(1.5)

    return "", []


def save_checkpoint(records_dict, output_path):
    """
    Atomically writes the current records dictionary to JSON so no data is lost on crash.
    """
    temp_path = output_path.with_suffix(".tmp")
    data_list = list(records_dict.values())
    with open(temp_path, "w", encoding="utf-8") as f:
        json.dump(data_list, f, ensure_ascii=False, indent=2)
    temp_path.replace(output_path)



def extract_crime_cases(start_page=1, end_page=None, output_path=None, delay=0.25):
    """
    Production-grade batch extraction pipeline:
    1. Resumable & Idempotent: Skips articles already saved in bronze_crime_news.json.
    2. Atomic Checkpointing: Flushes to disk after every single page.
    3. HTTP Connection Pooling: Reuses TCP connections via requests.Session.
    4. Auto-detects total page count if end_page is None.
    """
    if output_path is None:
        project_root = Path(__file__).resolve().parent.parent
        data_dir = project_root / "data"
        data_dir.mkdir(parents=True, exist_ok=True)
        output_path = data_dir / "bronze_crime_news.json"
    else:
        output_path = Path(output_path)

    # 1. Load existing checkpoint to enable resuming
    records_dict = {}
    if output_path.exists():
        try:
            with open(output_path, "r", encoding="utf-8") as f:
                existing_list = json.load(f)
                for item in existing_list:
                    if isinstance(item, dict) and "news_id" in item:
                        records_dict[item["news_id"]] = item
            logger.info(f"Resuming extraction: Found {len(records_dict)} previously saved articles.")

        except Exception as e:
            logger.warning(f"Could not read existing file ({e}). Starting fresh.")

   

    # 2. Probe total count if end_page is not provided
    session = requests.Session()
    
    try:
        probe_res = session.get(INDEX_ENDPOINT, params={"sectionId": SECTION_ID, "pageIndex": 1}, headers=HEADERS, timeout=10)
        probe_data = probe_res.json()
        total_items = probe_data.get("pager", {}).get("totalCount")
        calculated_pages = (total_items + ARTICLES_PER_PAGE - 1) // ARTICLES_PER_PAGE
        if end_page is None:
            end_page = calculated_pages

        logger.info(f"Archive Stats: {total_items:,} articles across {calculated_pages} pages.")
        logger.info(f"Execution Target: Pages {start_page} to {end_page}.")

    except Exception as e:
        logger.warning(f"Could not probe total pages: {e}. Defaulting to end_page = {end_page or 588}")
        if end_page is None:
            end_page = 588

    total_new_extracted = 0
    start_time = time.time()

    try:
        for page in range(start_page, end_page + 1):
            params = {"sectionId": SECTION_ID, "pageIndex": page}
            
            try:
                res = session.get(INDEX_ENDPOINT, params=params, headers=HEADERS, timeout=12)
                if res.status_code != 200:
                    logger.error(f"Page {page} returned status {res.status_code}. Skipping.")
                    continue

                data = res.json()
                results = data.get("results", [])
                if not results:
                    logger.info(f"No articles returned on page {page}. Reached end of archive.")
                    break

                page_new_count = 0
                for idx, article in enumerate(results, 1):
                    news_id = article.get("newsId")
                    if not news_id:
                        continue

                    # Idempotency check: Skip if already fetched
                    if news_id in records_dict:
                        continue

                    title = (article.get("title") or "").strip()
                    date_published = parse_moi_date(article.get("datePublished"))

                    # Fetch full body text
                    full_text, paragraphs = fetch_article_details(session, news_id)

                    record = {
                        "news_id": news_id,
                        "title": title,
                        "full_details": full_text,
                        "paragraphs_count": len(paragraphs),
                        "date_published": date_published,
                        "section_id": SECTION_ID,
                        "image_url": article.get("imagePathLarge") or article.get("image"),
                        "source_url": f"{DETAILS_ENDPOINT}?newsId={news_id}&sectionId={SECTION_ID}",
                        "ingested_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
                    }

                    records_dict[news_id] = record
                    page_new_count += 1
                    total_new_extracted += 1
                    
                    time.sleep(delay)

                # Save checkpoint after every page
                save_checkpoint(records_dict, output_path)

                if page_new_count == 0:
                    logger.info(f"All articles on page {page} already exist in Bronze. Terminating.")
                    break

                elapsed = time.time() - start_time
                pct = (page / end_page) * 100
                logger.info(f"Page {page}/{end_page} ({pct:.1f}%) | +{page_new_count} new | Total stored: {len(records_dict)} | Time: {elapsed:.0f}s")

            except Exception as e:
                logger.error(f"Failed to process page {page}: {e}")
                time.sleep(2)

    except KeyboardInterrupt:
        logger.warning("Process paused by user (Ctrl+C). Saving current checkpoint...")
        save_checkpoint(records_dict, output_path)
        logger.info(f"Checkpoint saved safely: {len(records_dict)} articles persisted.")
        return list(records_dict.values())

    logger.info("EXTRACTION COMPLETE!")
    logger.info(f"Total articles in Bronze store: {len(records_dict):,}")
    logger.info(f"Total duration: {(time.time() - start_time) / 60:.1f} minutes")
    logger.info(f"Destination: {output_path}")

    return list(records_dict.values())


if __name__ == "__main__":
    # By default, runs from page 1 to the end of the archive all 4,700 articles
    # Can be safely stopped and resumed at any time without losing data!
    extract_crime_cases(start_page=1, end_page=None)
