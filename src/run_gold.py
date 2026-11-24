import logging
import os
import sys
import time
from pathlib import Path

import psycopg2
from dotenv import load_dotenv

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

logger = logging.getLogger("run_gold")

PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(dotenv_path=PROJECT_ROOT / ".env")


def run_gold_pipeline():
    conn = None

    host = os.getenv("PGHOST", "")
    port = os.getenv("PGPORT", "5432")
    dbname = os.getenv("PGDATABASE", "moi_crimes")
    user = os.getenv("PGUSER", "team")
    password = os.getenv("PGPASSWORD", "")
    sslmode = os.getenv("PGSSLMODE", "require")

    if not host or not password:
        logger.error("Missing PGHOST or PGPASSWORD in environment")
        sys.exit(1)

    try:
        with psycopg2.connect(
            host=host, port=port, dbname=dbname, user=user, password=password, sslmode=sslmode
        ) as conn:
            with conn.cursor() as cursor:
                logger.info(f"Connected to PostgreSQL at {host}/{dbname}")

                sql_text = (PROJECT_ROOT / "sql" / "build_gold.sql").read_text(encoding="utf-8")
                t0 = time.time()
                cursor.execute(sql_text)
                elapsed = time.time() - t0
                logger.info(f"Gold Star Schema rebuilt in {elapsed:.2f}s")

                gold_tables = [
                    "dim_date",
                    "dim_location",
                    "dim_crime_type",
                    "dim_event",
                    "dim_item",
                    "fact_incident",
                    "bridge_incident_item",
                ]

                for tbl in gold_tables:
                    cursor.execute(f"SELECT COUNT(*) FROM gold.{tbl}")
                    logger.info(f"gold.{tbl:<22} -> {cursor.fetchone()[0]:,} rows")

                cursor.execute("""
                    SELECT
                        COUNT(*) FILTER (WHERE b.is_unit_corrected) AS corrected_rows,
                        ROUND(COALESCE(SUM(b.quantity_kg) FILTER (WHERE i.item_category = 'drugs'), 0), 2) AS drugs_kg
                    FROM gold.bridge_incident_item b
                    JOIN gold.dim_item i ON b.item_key = i.item_key
                """)
                corrected_rows, drugs_kg = cursor.fetchone()
                logger.info(f"Telemetry | is_unit_corrected={corrected_rows:,} rows | drugs_total_kg={drugs_kg:,} kg")

    except Exception as e:
        logger.error(f"Gold pipeline failed: {e}")
        sys.exit(1)
    finally:
        if conn is not None:
            conn.close()


if __name__ == "__main__":
    run_gold_pipeline()