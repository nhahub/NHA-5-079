"""PostgreSQL access layer for the MOI Crime Gold Star Schema.

Design principles:
1. Incidents (fact grain) and seized items (bridge grain) are fetched via two
   separate cached queries and filtered in memory by incident_key. Never join
   them in SQL for summary metrics so incident counts and arrests never fan out.
2. Uses psycopg2 cursors directly instead of pd.read_sql() to stay compatible
   with pandas 3.x without SQLAlchemy warnings.
"""

import os
from pathlib import Path
from typing import Any

import pandas as pd
import psycopg2
import streamlit as st
from dotenv import load_dotenv

from dashboard.labels import (
    CRIME_LABELS_AR,
    CRIME_LABELS_BI,
    CRIME_LABELS_EN,
    EVENT_LABELS_AR,
    EVENT_LABELS_BI,
    EVENT_LABELS_EN,
    ITEM_CATEGORY_LABELS_AR,
    ITEM_CATEGORY_LABELS_BI,
    ITEM_CATEGORY_LABELS_EN,
    REGION_LABELS_AR,
    REGION_LABELS_BI,
    canonicalize_drug_name,
)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(dotenv_path=PROJECT_ROOT / ".env")


def _get_setting(key: str, default: str = "") -> str:
    """Read configuration from Streamlit Cloud/HF Secrets first, then .env / env."""
    try:
        if key in st.secrets:
            return str(st.secrets[key])
    except Exception:
        pass
    return os.getenv(key, default)


def get_connection():
    """Open a TLS-encrypted connection to Azure PostgreSQL."""
    return psycopg2.connect(
        host=_get_setting("PGHOST", "mo-crime.postgres.database.azure.com"),
        port=_get_setting("PGPORT", "5432"),
        dbname=_get_setting("PGDATABASE", "moi_crimes"),
        user=_get_setting("PGUSER", "team"),
        password=_get_setting("PGPASSWORD", ""),
        sslmode=_get_setting("PGSSLMODE", "require"),
        connect_timeout=15,
    )


def _fetch_df(sql: str) -> pd.DataFrame:
    """Execute a read query cleanly and materialize into a pandas DataFrame."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql)
            columns = [desc[0] for desc in cur.description]
            rows = cur.fetchall()
    return pd.DataFrame(rows, columns=columns)


INCIDENTS_SQL = """
SELECT
    f.incident_key,
    d.full_date,
    d.year,
    d.month,
    d.month_name,
    d.quarter,
    l.governorate,
    l.region,
    l.is_multi_place,
    l.police_station_clean,
    c.crime_category,
    c.crime_subcategory,
    e.event_type,
    e.event_type_ar,
    f.report_type,
    f.is_aggregate_report,
    f.investigation_status,
    f.incident_count_clean,
    f.campaign_case_count,
    f.suspect_count,
    f.victim_count,
    f.injury_count,
    f.death_count,
    f.arrested_count,
    f.seized_item_count,
    f.financial_value,
    f.is_financial_corrected,
    f.title,
    f.source_url
FROM gold.fact_incident f
JOIN gold.dim_date       d ON f.date_key       = d.date_key
JOIN gold.dim_location   l ON f.location_key   = l.location_key
JOIN gold.dim_crime_type c ON f.crime_type_key = c.crime_type_key
JOIN gold.dim_event      e ON f.event_key      = e.event_key
ORDER BY d.full_date DESC, f.incident_key DESC;
"""

ITEMS_SQL = """
SELECT
    b.bridge_id,
    b.incident_key,
    i.item_category,
    i.item_type_clean,
    b.quantity,
    b.unit_clean,
    b.quantity_kg,
    b.is_unit_corrected,
    b.status
FROM gold.bridge_incident_item b
JOIN gold.dim_item i ON b.item_key = i.item_key;
"""


@st.cache_data(ttl=600, show_spinner=False)
def load_incidents() -> pd.DataFrame:
    """Load all verified criminal incidents from the Gold Star Schema (cached 10m)."""
    df = _fetch_df(INCIDENTS_SQL)
    df["full_date"] = pd.to_datetime(df["full_date"])
    df["year_month"] = df["full_date"].dt.to_period("M").astype(str)
    for col in ("financial_value", "incident_count_clean", "campaign_case_count",
                "suspect_count", "victim_count", "injury_count", "death_count",
                "arrested_count", "seized_item_count"):
        df[col] = pd.to_numeric(df[col], errors="coerce")

    df["is_campaign"] = (
        df["event_type"].eq("enforcement_campaign")
        | df["is_aggregate_report"].fillna(False)
    )
    df["crime_label_en"] = df["crime_category"].map(CRIME_LABELS_EN).fillna(df["crime_category"])
    df["crime_label_ar"] = df["crime_category"].map(CRIME_LABELS_AR).fillna(df["crime_category"])
    df["crime_label_bi"] = df["crime_category"].map(CRIME_LABELS_BI).fillna(df["crime_category"])
    df["event_label_en"] = df["event_type"].map(EVENT_LABELS_EN).fillna(df["event_type"])
    df["event_label_ar"] = df["event_type"].map(EVENT_LABELS_AR).fillna(df["event_type"])
    df["event_label_bi"] = df["event_type"].map(EVENT_LABELS_BI).fillna(df["event_type"])
    df["region_label_ar"] = df["region"].map(REGION_LABELS_AR).fillna(df["region"])
    df["region_label_bi"] = df["region"].map(REGION_LABELS_BI).fillna(df["region"])
    return df


@st.cache_data(ttl=600, show_spinner=False)
def load_items() -> pd.DataFrame:
    """Load seized contraband bridge rows separately to avoid fan-out."""
    df = _fetch_df(ITEMS_SQL)
    for col in ("quantity", "quantity_kg"):
        df[col] = pd.to_numeric(df[col], errors="coerce")
    df["item_category_en"] = df["item_category"].map(ITEM_CATEGORY_LABELS_EN).fillna(df["item_category"])
    df["item_category_ar"] = df["item_category"].map(ITEM_CATEGORY_LABELS_AR).fillna(df["item_category"])
    df["item_category_bi"] = df["item_category"].map(ITEM_CATEGORY_LABELS_BI).fillna(df["item_category"])
    df["drug_canonical"] = df["item_type_clean"].apply(canonicalize_drug_name)
    return df


@st.cache_data(ttl=600, show_spinner=False)
def load_quality_audit() -> dict[str, Any]:
    """Query live Silver vs. Gold metrics and all 6 automated quality-gate invariants."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT
                    (SELECT COUNT(*) FROM silver.fact_incident) AS silver_incidents,
                    (SELECT COUNT(*) FROM gold.fact_incident) AS gold_incidents,
                    (SELECT COUNT(*) FROM silver.bridge_incident_item) AS silver_items,
                    (SELECT COUNT(*) FROM gold.bridge_incident_item) AS gold_items,
                    (SELECT COUNT(*) FROM gold.fact_incident f
                       JOIN gold.dim_event e ON f.event_key = e.event_key
                      WHERE e.event_type IN ('administrative', 'rumor_denial')) AS rumor_admin_leaks,
                    (SELECT COUNT(*) - COUNT(DISTINCT news_key) FROM gold.fact_incident) AS duplicate_news,
                    (SELECT COUNT(*) FROM gold.bridge_incident_item
                      WHERE unit_clean IN ('كيلو جرام', 'كج', 'كيلو غرام', 'كيلوغرام', 'كغ', 'غرام', 'وحدة')) AS unnormalized_units,
                    (SELECT COALESCE(MAX(b.quantity_kg), 0)
                       FROM gold.bridge_incident_item b
                       JOIN gold.dim_item i ON b.item_key = i.item_key
                      WHERE i.item_category = 'drugs') AS max_drug_kg,
                    (SELECT COUNT(*) FROM gold.fact_incident WHERE financial_value = 0) AS zero_financials,
                    (SELECT COALESCE(MAX(financial_value), 0) FROM gold.fact_incident) AS max_financial,
                    (SELECT COUNT(*) FROM gold.bridge_incident_item WHERE is_unit_corrected) AS unit_corrected_rows,
                    (SELECT COUNT(*) FROM gold.fact_incident WHERE is_financial_corrected) AS fin_corrected_rows,
                    (SELECT COUNT(*) FROM gold.fact_incident WHERE financial_value IS NOT NULL) AS fin_stated_rows,
                    (SELECT COUNT(*) FROM silver.fact_incident WHERE is_criminal_incident = TRUE AND financial_value = 0) AS silver_fake_zeros
            """)
            row = cur.fetchone()
            cols = [d[0] for d in cur.description]
            summary = dict(zip(cols, row))

            # Fetch concrete audited before/after examples directly from Silver & Gold
            cur.execute("""
                SELECT sb.bridge_id, sb.quantity AS silver_qty, sb.unit AS silver_unit,
                       gb.quantity_kg AS gold_kg, LEFT(sn.title, 42) AS title
                FROM silver.bridge_incident_item sb
                JOIN gold.bridge_incident_item gb ON sb.bridge_id = gb.bridge_id
                JOIN gold.fact_incident gf ON gb.incident_key = gf.incident_key
                JOIN silver.dim_news sn ON gf.news_key = sn.news_key
                WHERE gb.is_unit_corrected = TRUE
                ORDER BY sb.quantity DESC
                LIMIT 5
            """)
            unit_samples = pd.DataFrame(cur.fetchall(), columns=[d[0] for d in cur.description])

            cur.execute("""
                SELECT sf.incident_key, sf.financial_value AS silver_egp,
                       gf.financial_value AS gold_egp, LEFT(sn.title, 42) AS title
                FROM silver.fact_incident sf
                JOIN gold.fact_incident gf ON sf.incident_key = gf.incident_key
                JOIN silver.dim_news sn ON gf.news_key = sn.news_key
                WHERE gf.is_financial_corrected = TRUE
                ORDER BY sf.financial_value DESC
                LIMIT 5
            """)
            fin_samples = pd.DataFrame(cur.fetchall(), columns=[d[0] for d in cur.description])

    summary["unit_samples"] = unit_samples
    summary["fin_samples"] = fin_samples
    return summary
