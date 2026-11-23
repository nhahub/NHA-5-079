"""
load_to_postgres.py - load results/all_extracted_news.jsonl into Azure PostgreSQL.

  1. every record is copied as-is into  staging.extracted_news  (id + full JSON)
  2. SQL then fills the star schema  dw.*  from staging  (dimensions, fact, bridges)

Safe to run again and again: staging rows are upserted, dimensions use
"insert if missing", and the fact/bridge rows of the loaded articles are rebuilt.
Everything happens in ONE transaction - if anything fails, nothing is changed.

Run (from the ingestion folder, inside your venv):
    pip install psycopg2-binary
    python3 src/load_to_postgres.py                      # asks for the password
    python3 src/load_to_postgres.py --file results/all_extracted_news.jsonl

Connection settings come from environment variables (or the defaults below):
    PGHOST  PGPORT  PGDATABASE  PGUSER  PGPASSWORD  PGSSLMODE
The password is never stored in this file. If PGPASSWORD is not set it is asked for.
"""
import argparse
import getpass
import json
import os
import sys
import uuid
from pathlib import Path

import psycopg2
from psycopg2.extras import Json, execute_values

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        pass

DEFAULT_FILE = Path(__file__).resolve().parent.parent / "results" / "all_extracted_news.jsonl"

TRANSFORM_SQL = r"""
-- helper views over staging (temporary, die with the transaction) ----------------
CREATE TEMP VIEW v_news AS
SELECT s.id, s.payload AS p FROM staging.extracted_news s;

CREATE TEMP VIEW v_persons AS
SELECT v.id, e AS j
FROM v_news v,
     jsonb_array_elements(CASE WHEN jsonb_typeof(v.p->'persons') = 'array' THEN v.p->'persons' ELSE '[]'::jsonb END) e;

CREATE TEMP VIEW v_items AS
SELECT v.id, e AS j
FROM v_news v,
     jsonb_array_elements(CASE WHEN jsonb_typeof(v.p->'items') = 'array' THEN v.p->'items' ELSE '[]'::jsonb END) e;

CREATE TEMP VIEW v_secondary AS
SELECT v.id, e AS j
FROM v_news v,
     jsonb_array_elements(CASE WHEN jsonb_typeof(v.p->'secondary_crimes') = 'array' THEN v.p->'secondary_crimes' ELSE '[]'::jsonb END) e;

-- DIMENSIONS ------------------------------------------------------------------------
INSERT INTO dw.dim_date (date_key, full_date, day, month, month_name, quarter, year, day_of_week, week_of_year)
SELECT DISTINCT
    (p->'dim_date'->>'date_key')::int, (p->'dim_date'->>'full_date')::date,
    (p->'dim_date'->>'day')::smallint, (p->'dim_date'->>'month')::smallint,
    p->'dim_date'->>'month_name', (p->'dim_date'->>'quarter')::smallint,
    (p->'dim_date'->>'year')::smallint, (p->'dim_date'->>'day_of_week')::smallint,
    (p->'dim_date'->>'week_of_year')::smallint
FROM v_news
ON CONFLICT (date_key) DO NOTHING;

INSERT INTO dw.dim_news (source_news_id, title, publication_date, source_url, image_url,
                         section_id, paragraphs_count, raw_text_reference, ingested_at)
SELECT
    (p->'dim_news'->>'source_news_id')::uuid,
    COALESCE(p->'dim_news'->>'title', ''),
    (p->'dim_news'->>'publication_date')::timestamptz,
    p->'dim_news'->>'source_url', p->'dim_news'->>'image_url',
    (p->'dim_news'->>'section_id')::int, (p->'dim_news'->>'paragraphs_count')::int,
    p->'dim_news'->>'raw_text_reference',
    (p->'dim_news'->>'ingested_at')::timestamp
FROM v_news
ON CONFLICT (source_news_id) DO UPDATE SET
    title = EXCLUDED.title, publication_date = EXCLUDED.publication_date,
    source_url = EXCLUDED.source_url, image_url = EXCLUDED.image_url,
    section_id = EXCLUDED.section_id, paragraphs_count = EXCLUDED.paragraphs_count,
    raw_text_reference = EXCLUDED.raw_text_reference, ingested_at = EXCLUDED.ingested_at;

INSERT INTO dw.dim_location (governorate, city, police_station, region, country)
SELECT DISTINCT
    p->'dim_location'->>'governorate', p->'dim_location'->>'city',
    p->'dim_location'->>'police_station', p->'dim_location'->>'region',
    COALESCE(p->'dim_location'->>'country', 'مصر')
FROM v_news
ON CONFLICT (governorate, city, police_station) DO NOTHING;

INSERT INTO dw.dim_crime_type (crime_category, crime_subcategory, crime_type)
SELECT DISTINCT COALESCE(p->'dim_crime_type'->>'crime_category', 'unknown'),
       p->'dim_crime_type'->>'crime_subcategory', p->'dim_crime_type'->>'crime_type'
FROM v_news
ON CONFLICT (crime_category, crime_subcategory, crime_type) DO NOTHING;

INSERT INTO dw.dim_crime_type (crime_category, crime_subcategory, crime_type)
SELECT DISTINCT COALESCE(j->>'crime_category', 'unknown'), NULL, j->>'crime_type'
FROM v_secondary
ON CONFLICT (crime_category, crime_subcategory, crime_type) DO NOTHING;

INSERT INTO dw.dim_event (event_type)
SELECT DISTINCT COALESCE(p->'dim_event'->>'event_type', 'unknown') FROM v_news
ON CONFLICT (event_type) DO NOTHING;

INSERT INTO dw.dim_person (person_role, gender, residence_governorate, residence_region)
SELECT DISTINCT COALESCE(j->>'person_role', 'unknown'), j->>'gender',
       j->>'residence_governorate', j->>'residence_region'
FROM v_persons
ON CONFLICT (person_role, gender, residence_governorate, residence_region) DO NOTHING;

INSERT INTO dw.dim_item (item_category, item_type)
SELECT DISTINCT COALESCE(j->>'item_category', 'other'), COALESCE(j->>'item_type', '')
FROM v_items
ON CONFLICT (item_category, item_type) DO NOTHING;

-- FACT: rebuild the rows of the articles being loaded -------------------------------------
DELETE FROM dw.fact_incident
WHERE news_key IN (SELECT n.news_key FROM dw.dim_news n JOIN v_news v ON n.source_news_id = v.id);

INSERT INTO dw.fact_incident (
    news_key, date_key, location_key, crime_type_key, event_key,
    incident_date, incident_date_text, incident_count,
    suspect_count, victim_count, injury_count, death_count, arrested_count,
    seized_item_count, financial_value, financial_value_basis, is_criminal_incident,
    legal_action, investigation_status, description,
    location_text, event_description, crime_description,
    needs_review, model, prompt_version, extracted_at)
SELECT
    n.news_key,
    (v.p->'dim_date'->>'date_key')::int,
    l.location_key, ct.crime_type_key, ev.event_key,
    (f->>'incident_date')::date, f->>'incident_date_text',
    COALESCE((f->>'incident_count')::smallint, 0),
    (f->>'suspect_count')::int, (f->>'victim_count')::int, (f->>'injury_count')::int,
    (f->>'death_count')::int, (f->>'arrested_count')::int,
    COALESCE((f->>'seized_item_count')::int, 0),
    (f->>'financial_value')::numeric, f->>'financial_value_basis',
    COALESCE((f->>'is_criminal_incident')::boolean, false),
    f->>'legal_action', f->>'investigation_status', f->>'description',
    v.p->'dim_location'->>'location_text', v.p->'dim_event'->>'event_description',
    v.p->'dim_crime_type'->>'description',
    CASE WHEN jsonb_typeof(v.p->'needs_review') = 'array'
         THEN ARRAY(SELECT jsonb_array_elements_text(v.p->'needs_review')) ELSE '{}'::text[] END,
    v.p->>'model', v.p->>'prompt_version', (v.p->>'extracted_at')::timestamp
FROM v_news v
CROSS JOIN LATERAL (SELECT v.p->'fact_incident' AS f) x
JOIN dw.dim_news n ON n.source_news_id = v.id
JOIN dw.dim_location l
  ON  l.governorate    IS NOT DISTINCT FROM v.p->'dim_location'->>'governorate'
  AND l.city           IS NOT DISTINCT FROM v.p->'dim_location'->>'city'
  AND l.police_station IS NOT DISTINCT FROM v.p->'dim_location'->>'police_station'
JOIN dw.dim_crime_type ct
  ON  ct.crime_category    = COALESCE(v.p->'dim_crime_type'->>'crime_category', 'unknown')
  AND ct.crime_subcategory IS NOT DISTINCT FROM v.p->'dim_crime_type'->>'crime_subcategory'
  AND ct.crime_type        IS NOT DISTINCT FROM v.p->'dim_crime_type'->>'crime_type'
JOIN dw.dim_event ev ON ev.event_type = COALESCE(v.p->'dim_event'->>'event_type', 'unknown');

-- BRIDGES ---------------------------------------------------------------------------------------
INSERT INTO dw.bridge_incident_person (incident_key, person_key, person_count, person_description, description)
SELECT fi.incident_key, dp.person_key, (vp.j->>'count')::int, vp.j->>'person_description', vp.j->>'description'
FROM v_persons vp
JOIN dw.dim_news n ON n.source_news_id = vp.id
JOIN dw.fact_incident fi ON fi.news_key = n.news_key
JOIN dw.dim_person dp
  ON  dp.person_role = COALESCE(vp.j->>'person_role', 'unknown')
  AND dp.gender                IS NOT DISTINCT FROM vp.j->>'gender'
  AND dp.residence_governorate IS NOT DISTINCT FROM vp.j->>'residence_governorate'
  AND dp.residence_region      IS NOT DISTINCT FROM vp.j->>'residence_region';

INSERT INTO dw.bridge_incident_item (incident_key, item_key, quantity, unit, quantity_note, status, description)
SELECT fi.incident_key, di.item_key, (vi.j->>'quantity')::numeric, vi.j->>'unit',
       vi.j->>'quantity_note', vi.j->>'status', vi.j->>'description'
FROM v_items vi
JOIN dw.dim_news n ON n.source_news_id = vi.id
JOIN dw.fact_incident fi ON fi.news_key = n.news_key
JOIN dw.dim_item di
  ON  di.item_category = COALESCE(vi.j->>'item_category', 'other')
  AND di.item_type     = COALESCE(vi.j->>'item_type', '');

INSERT INTO dw.bridge_incident_secondary_crime (incident_key, crime_type_key)
SELECT fi.incident_key, ct.crime_type_key
FROM v_secondary vs
JOIN dw.dim_news n ON n.source_news_id = vs.id
JOIN dw.fact_incident fi ON fi.news_key = n.news_key
JOIN dw.dim_crime_type ct
  ON  ct.crime_category    = COALESCE(vs.j->>'crime_category', 'unknown')
  AND ct.crime_subcategory IS NULL
  AND ct.crime_type        IS NOT DISTINCT FROM vs.j->>'crime_type';
"""

COUNT_TABLES = [
    "staging.extracted_news", "dw.dim_date", "dw.dim_news", "dw.dim_location", "dw.dim_crime_type",
    "dw.dim_event", "dw.dim_person", "dw.dim_item", "dw.fact_incident",
    "dw.bridge_incident_person", "dw.bridge_incident_item", "dw.bridge_incident_secondary_crime",
]


def read_records(path: Path):
    recs, bad = {}, 0
    with path.open(encoding="utf-8") as fh:
        for n, line in enumerate(fh, 1):
            if not line.strip():
                continue
            try:
                r = json.loads(line)
                rid = str(uuid.UUID(str(r["id"])))
            except Exception as e:  # noqa: BLE001
                bad += 1
                print(f"  skipped line {n}: {e}")
                continue
            recs[rid] = r
    return recs, bad


def connect(args):
    password = os.getenv("PGPASSWORD") or getpass.getpass("PostgreSQL password (hidden): ")
    return psycopg2.connect(
        host=args.host, port=args.port, dbname=args.dbname, user=args.user,
        password=password, sslmode=os.getenv("PGSSLMODE", "require"), connect_timeout=15,
    )


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--file", default=str(DEFAULT_FILE), help="merged jsonl file (default: results/all_extracted_news.jsonl)")
    ap.add_argument("--host", default=os.getenv("PGHOST", "mo-crime.postgres.database.azure.com"))
    ap.add_argument("--port", default=os.getenv("PGPORT", "5432"))
    ap.add_argument("--dbname", default=os.getenv("PGDATABASE", "moi_crimes"))
    ap.add_argument("--user", default=os.getenv("PGUSER", "moi_crime"))
    args = ap.parse_args()

    path = Path(args.file)
    if not path.exists():
        raise SystemExit(f"File not found: {path}  (run merge_results.py first)")
    recs, bad = read_records(path)
    if not recs:
        raise SystemExit("No valid records in the file.")
    versions = {}
    for r in recs.values():
        versions[r.get("prompt_version")] = versions.get(r.get("prompt_version"), 0) + 1
    print(f"Read {len(recs)} records from {path.name} ({bad} bad lines skipped) | prompt versions: {versions}")
    if len(versions) > 1:
        print("  WARNING: more than one prompt version in the file - re-run the odd ones later.")

    conn = connect(args)
    try:
        with conn:  # one transaction: commit at the end, rollback on any error
            with conn.cursor() as cur:
                cur.execute("SELECT 1 FROM information_schema.tables WHERE table_schema='dw' AND table_name='fact_incident'")
                if not cur.fetchone():
                    raise SystemExit("Tables not found - run sql/01_create_schema.sql first.")
                execute_values(
                    cur,
                    """INSERT INTO staging.extracted_news (id, prompt_version, payload) VALUES %s
                       ON CONFLICT (id) DO UPDATE SET prompt_version = EXCLUDED.prompt_version,
                                                      payload = EXCLUDED.payload, loaded_at = now()""",
                    [(rid, r.get("prompt_version"), Json(r, dumps=lambda o: json.dumps(o, ensure_ascii=False)))
                     for rid, r in recs.items()],
                    page_size=200,
                )
                print(f"Staged {len(recs)} records.")
                cur.execute(TRANSFORM_SQL)
                print("Star schema filled.")
                print("\nRow counts:")
                for t in COUNT_TABLES:
                    cur.execute(f"SELECT count(*) FROM {t}")
                    print(f"  {t:<38}{cur.fetchone()[0]:>8}")
                cur.execute("SELECT count(*) FROM staging.extracted_news s "
                            "WHERE NOT EXISTS (SELECT 1 FROM dw.dim_news n WHERE n.source_news_id = s.id "
                            "AND EXISTS (SELECT 1 FROM dw.fact_incident f WHERE f.news_key = n.news_key))")
                missing = cur.fetchone()[0]
                print(f"\nArticles in staging without a fact row: {missing}" + ("  <-- should be 0" if missing else "  (ok)"))
        print("\nDone - committed.")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
