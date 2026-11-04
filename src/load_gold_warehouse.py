import os
import sys
import time
from pathlib import Path
import pandas as pd
import psycopg2
from psycopg2.extras import execute_values
from dotenv import load_dotenv
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

logger = logging.getLogger("load_gold")

PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(dotenv_path=PROJECT_ROOT / ".env")



def load_silver_to_gold(parquet_path=None):
    """
    Bulk loads records from Silver Parquet into PostgreSQL Gold Warehouse (fact_crime).
    Guarantees idempotency via ON CONFLICT (news_id) DO NOTHING.
    """
    data_dir = PROJECT_ROOT / "data"

    if parquet_path is None:
        parquet_path = data_dir / "silver_crime_news.parquet"
    else:
        parquet_path = Path(parquet_path)

    if not parquet_path.exists():
        logger.error(f"Silver Parquet file not found at {parquet_path}")
        sys.exit(1)

    logger.info("STARTING GOLD WAREHOUSE LOADER")
    logger.info(f"Source (Silver): {parquet_path.name}")
    logger.info(f"Target Database: {os.getenv('DB_NAME', 'moi_crime_dw')}")

    start_time = time.time()

    # 1. Read Silver Parquet
    df = pd.read_parquet(parquet_path)
    total_silver_rows = len(df)
    logger.info(f"Loaded {total_silver_rows:,} records from Silver Parquet.")

    # Convert DataFrame rows into a list of tuples for psycopg2
    records_to_insert = [
        (
            row["news_id"],
            int(row["date_id"]),
            int(row["location_id"]),
            int(row["crime_type_id"]),
            row["title"],
            row["full_details"],
            row["source_url"],
            row["image_url"],
            int(row["incident_count"]),
            int(row["suspects_count"]),
            int(row["weapons_count"]),
            bool(row["is_campaign"]),
            row["published_timestamp"],
            row["ingested_at"]
        )
        for _, row in df.iterrows()
    ]

    conn = None

    try:
        with psycopg2.connect(
            host = os.getenv("DB_HOST", "localhost"),
            port = os.getenv("DB_PORT", "5432"),
            dbname = os.getenv("DB_NAME", "moi_crime_dw"),
            user = os.getenv("DB_USER", "postgres"),
            password = os.getenv("DB_PASSWORD", "")
        ) as conn:
            
            with conn.cursor() as cursor:
                logger.info("Connected to PostgreSQL")

                # 3. Fast Bulk Insert using execute_values
                insert_query = """
                INSERT INTO fact_crime (
                    news_id, date_id, location_id, crime_type_id,
                    title, full_details, source_url, image_url,
                    incident_count, suspects_count, weapons_count, is_campaign,
                    published_timestamp, ingested_at
                ) VALUES %s
                ON CONFLICT (news_id) DO NOTHING;
                """

                logger.info(f"Bulk inserting {len(records_to_insert):,} rows into fact_crime...")
                execute_values(cursor, insert_query, records_to_insert, page_size=1000)

                # 4. Warehouse Verification Queries
                cursor.execute("SELECT COUNT(*) FROM fact_crime;")
                total_in_warehouse = cursor.fetchone()[0]

                cursor.execute("SELECT COUNT(*) FROM fact_crime WHERE location_id > 0;")
                with_location = cursor.fetchone()[0]

                cursor.execute("SELECT COUNT(*) FROM fact_crime WHERE crime_type_id > 0;")
                with_crime = cursor.fetchone()[0]

                cursor.execute("SELECT SUM(suspects_count), SUM(weapons_count), SUM(CASE WHEN is_campaign THEN 1 ELSE 0 END) FROM fact_crime;")
                total_suspects, total_weapons, total_campaigns = cursor.fetchone()

                duration = time.time() - start_time

                logger.info("GOLD WAREHOUSE LOAD COMPLETE!")
                logger.info(f"Total Rows in fact_crime   : {total_in_warehouse:,}")
                logger.info(f"Mapped to Known Location   : {with_location:,} ({(with_location/total_in_warehouse)*100:.1f}%)")
                logger.info(f"Mapped to Crime Category   : {with_crime:,} ({(with_crime/total_in_warehouse)*100:.1f}%)")
                logger.info(f"Total Suspects Tracked     : {int(total_suspects):,}")
                logger.info(f"Total Weapons Tracked      : {int(total_weapons):,}")
                logger.info(f"Total Security Campaigns   : {int(total_campaigns):,}")
                logger.info(f"Load Duration              : {duration:.2f} seconds")

    except Exception as e:
        logger.error(f"Database Connection error: {e}")
        sys.exit(1)
    finally:
        if conn is not None:
            conn.close()


if __name__ == "__main__":
    load_silver_to_gold()
