import argparse
import json
import logging
import os
import sys
import time
from datetime import datetime, timezone

# Add project root directory to system path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.api_client import MOINewsClient

SECTION_ID = 3
OUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", "bronze")
PAGE_DELAY = 1.0   # seconds between pages
ITEM_DELAY = 0.5   # seconds between article detail requests


def page_path(page_index: int) -> str:
    return os.path.join(OUT_DIR, f"page_{page_index:04d}.json")


def save_page(page_index: int, records: list) -> None:
    """Write to a temp file then rename, so a crash never leaves a half-written page."""
    path = page_path(page_index)
    tmp_path = path + ".tmp"
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(records, f, ensure_ascii=False, indent=2)
    os.replace(tmp_path, path)


def build_records(client: MOINewsClient, page_index: int, items: list) -> list:
    records = []
    for item in items:
        news_id = item.get("newsId")
        full_text = client.scrape_full_article_text(news_id=news_id, section_id=SECTION_ID)
        records.append({
            "news_id": news_id,
            "section_id": SECTION_ID,
            "page_index": page_index,
            "scraped_at": datetime.now(timezone.utc).isoformat(),
            # "api_brief_only" means the details page returned nothing: re-check these later
            "content_source": "details_page" if full_text else "api_brief_only",
            "full_text_raw": full_text,
            "api_payload": item,  # the API item exactly as returned
        })
        time.sleep(ITEM_DELAY)
    return records


def main(max_pages: int | None = None) -> None:
    os.makedirs(OUT_DIR, exist_ok=True)
    client = MOINewsClient()

    first = client.fetch_page(section_id=SECTION_ID, page_index=1)
    if not first or not first.get("results"):
        logging.error("Could not fetch page 1. Aborting.")
        return

    pager = first.get("pager", {})
    page_size = pager.get("pageSize", 8) or 8
    total_pages = (pager.get("totalCount", 0) + page_size - 1) // page_size
    if max_pages:
        total_pages = min(total_pages, max_pages)
    logging.info(f"Total pages to process: {total_pages}")

    failed_pages = []
    for page_index in range(1, total_pages + 1):
        if os.path.exists(page_path(page_index)):
            continue  # already scraped: this is what makes the script resumable

        data = first if page_index == 1 else client.fetch_page(section_id=SECTION_ID, page_index=page_index)
        if not data or not data.get("results"):
            failed_pages.append(page_index)
            continue

        records = build_records(client, page_index, data["results"])
        save_page(page_index, records)
        logging.info(f"Saved page {page_index}/{total_pages} ({len(records)} articles)")
        time.sleep(PAGE_DELAY)

    if failed_pages:
        logging.warning(f"Failed pages (run the script again to retry them): {failed_pages}")
    else:
        logging.info("Done. All pages saved.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--max-pages", type=int, default=None, help="limit pages (for testing)")
    args = parser.parse_args()
    main(max_pages=args.max_pages)
