import os
import psycopg2
from pathlib import Path
from dotenv import load_dotenv
import logging
import sys

PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(dotenv_path=PROJECT_ROOT / ".env")


def run_query(sql):
    conn = None

    host = os.getenv("PGHOST", "")
    port = os.getenv("PGPORT", "5432")
    dbname = os.getenv("PGDATABASE", "moi_crimes")
    user = os.getenv("PGUSER", "team")
    password = os.getenv("PGPASSWORD", "")
    sslmode = os.getenv("PGSSLMODE", "require")

    try:
        with psycopg2.connect(host=host, port=port, dbname=dbname, user=user, password=password, sslmode=sslmode ) as conn:
            with conn.cursor() as cursor:
                cursor.execute(sql)
                return cursor.fetchone()[0]
            
    finally:
        if conn is not None:
            conn.close()

def test_gold_fact_completeness():
    rows = run_query("SELECT COUNT(*) FROM gold.fact_incident")
    assert rows >= 1500

def test_no_non_criminal_or_rumor_leaks():
    rows = run_query("SELECT COUNT(*) FROM gold.fact_incident f JOIN gold.dim_event e ON f.event_key = e.event_key WHERE e.event_type IN ('administrative', 'rumor_denial')")
    assert rows == 0

def test_no_duplicate_news_grain():
    rows = run_query("SELECT COUNT(*) - COUNT(DISTINCT news_key) FROM gold.fact_incident")
    assert rows == 0

def test_unit_normalization_clean():
    rows = run_query("SELECT COUNT(*) FROM gold.bridge_incident_item WHERE unit_clean IN ('كيلو جرام', 'كج', 'كيلو غرام', 'كيلوغرام', 'كغ', 'غرام', 'وحدة')")
    assert rows == 0

def test_drugs_kg_no_1000x_outliers(): 
    rows = run_query("SELECT MAX(b.quantity_kg) FROM gold.bridge_incident_item b JOIN gold.dim_item i ON b.item_key = i.item_key WHERE i.item_category = 'drugs'")
    assert rows < 50000


