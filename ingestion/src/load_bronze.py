import glob
import json
import logging
import os

import psycopg2
from psycopg2.extras import Json, execute_values

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# Example: postgresql://user:password@localhost:5432/testdb
DATABASE_URL = os.environ["DATABASE_URL"]
BRONZE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", "bronze")

DDL = """
CREATE SCHEMA IF NOT EXISTS bronze;

CREATE TABLE IF NOT EXISTS bronze.raw_news (
    news_id        TEXT PRIMARY KEY,
    section_id     INT,
    page_index     INT,
    content_source TEXT,
    full_text_raw  TEXT,
    api_payload    JSONB,
    scraped_at     TIMESTAMPTZ,
    loaded_at      TIMESTAMPTZ DEFAULT now()
);
"""

INSERT = """
INSERT INTO bronze.raw_news
    (news_id, section_id, page_index, content_source, full_text_raw, api_payload, scraped_at)
VALUES %s
ON CONFLICT (news_id) DO NOTHING
"""


def main() -> None:
    files = sorted(glob.glob(os.path.join(BRONZE_DIR, "page_*.json")))
    logging.info(f"Found {len(files)} page files")

    with psycopg2.connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            cur.execute(DDL)

            for path in files:
                with open(path, encoding="utf-8") as f:
                    records = json.load(f)

                rows = [
                    (
                        str(r["news_id"]),
                        r.get("section_id"),
                        r.get("page_index"),
                        r.get("content_source"),
                        r.get("full_text_raw"),
                        Json(r.get("api_payload")),
                        r.get("scraped_at"),
                    )
                    for r in records
                ]
                execute_values(cur, INSERT, rows)

            cur.execute("SELECT count(*) FROM bronze.raw_news")
            logging.info(f"bronze.raw_news now has {cur.fetchone()[0]} rows")


if __name__ == "__main__":
    main()
