BEGIN;
DROP TABLE IF EXISTS
  gold.bridge_incident_item,
  gold.fact_incident,
  gold.dim_item,
  gold.dim_event,
  gold.dim_crime_type,
  gold.dim_location,
  gold.dim_date
CASCADE;

CREATE TABLE gold.dim_date AS 
SELECT date_key, full_date, year, quarter, month, month_name, day, day_of_week, week_of_year
FROM silver.dim_date;

CREATE TABLE gold.dim_location AS 
SELECT location_key, governorate, region, country, is_multi_place, TRIM(REGEXP_REPLACE(TRANSLATE(police_station, 'أإآىة', 'ااايه'), '^قسم شرطه\s+', 'قسم ')) AS police_station_clean
FROM silver.dim_location;

CREATE TABLE gold.dim_crime_type AS 
SELECT crime_type_key, crime_category, crime_category_ar, TRIM(crime_subcategory) AS crime_subcategory
FROM silver.dim_crime_type;

CREATE TABLE gold.dim_event AS 
SELECT event_key, event_type, event_type_ar
FROM silver.dim_event;

CREATE TABLE gold.dim_item AS 
SELECT item_key, item_category, TRIM(TRANSLATE(item_type, 'أإآىة', 'ااايه')) AS item_type_clean
FROM silver.dim_item;

CREATE TABLE gold.fact_incident AS
SELECT 
    f.incident_key, f.date_key, f.location_key, f.crime_type_key, f.event_key, f.news_key, 
    n.title, n.source_url, f.report_type, f.is_aggregate_report, f.investigation_status,
    COALESCE(incident_count_clean, 0) AS incident_count_clean,
    COALESCE(campaign_case_count, 0)  AS campaign_case_count,
    COALESCE(suspect_count, 0)        AS suspect_count,
    COALESCE(victim_count, 0)         AS victim_count,
    COALESCE(injury_count, 0)         AS injury_count,
    COALESCE(death_count, 0)          AS death_count,
    COALESCE(arrested_count, 0)       AS arrested_count,
    COALESCE(seized_item_count, 0)    AS seized_item_count,
    CASE
        WHEN f.financial_value IS NULL OR f.financial_value <= 0 THEN NULL
        WHEN f.financial_value >= 1000000000000
             AND (COALESCE(n.title, '') || ' ' || COALESCE(f.description, '')) NOT LIKE '%مليار%'
             THEN ROUND(f.financial_value / 1000000.0, 2)
        WHEN f.financial_value >= 1000000000
             AND (COALESCE(n.title, '') || ' ' || COALESCE(f.description, '')) NOT LIKE '%مليار%'
             THEN ROUND(f.financial_value / 1000.0, 2)
        ELSE f.financial_value
    END AS financial_value,
    (
        f.financial_value >= 1000000000
        AND (COALESCE(n.title, '') || ' ' || COALESCE(f.description, '')) NOT LIKE '%مليار%'
    ) AS is_financial_corrected
FROM silver.fact_incident f
JOIN silver.dim_event e
    ON f.event_key = e.event_key
JOIN silver.dim_news n
    ON f.news_key = n.news_key
WHERE f.is_criminal_incident = TRUE AND e.event_type NOT IN ('administrative', 'rumor_denial');


CREATE TABLE gold.bridge_incident_item AS
SELECT 
    bi.bridge_id, bi.incident_key, bi.item_key, bi.quantity, bi.status, 

    CASE
        WHEN TRIM(bi.unit) IN ('كيلو جرام', 'كيلوجرام', 'كج', 'كيلو غرام', 'كيلوغرام', 'كغ') THEN 'كيلوجرام'
        WHEN TRIM(bi.unit) = 'غرام' THEN 'جرام'
        WHEN TRIM(bi.unit) IN ('وحدة') THEN 'قطعة'
        WHEN bi.unit IS NULL OR TRIM(bi.unit) = '' THEN 'غير محدد'
        ELSE TRIM(bi.unit)
    END AS unit_clean,

    CASE
        WHEN TRIM(bi.unit) = 'طن' AND bi.quantity >= 1000 THEN bi.quantity
        WHEN TRIM(bi.unit) = 'طن' THEN bi.quantity * 1000.0
        WHEN TRIM(bi.unit) IN ('كيلو جرام', 'كيلوجرام', 'كج', 'كيلو غرام', 'كيلوغرام', 'كغ') AND bi.quantity >= 1000 THEN bi.quantity / 1000.0
        WHEN TRIM(bi.unit) IN ('كيلو جرام', 'كيلوجرام', 'كج', 'كيلو غرام', 'كيلوغرام', 'كغ') THEN bi.quantity
        WHEN TRIM(bi.unit) IN ('جرام', 'غرام') THEN bi.quantity / 1000.0
        ELSE NULL
    END AS quantity_kg,
    COALESCE(TRIM(bi.unit) IN ('طن', 'كيلو جرام', 'كيلوجرام', 'كج', 'كيلو غرام', 'كيلوغرام', 'كغ') AND bi.quantity >= 1000, FALSE) AS is_unit_corrected

FROM silver.bridge_incident_item bi
JOIN gold.fact_incident g
    ON bi.incident_key = g.incident_key;


ALTER TABLE gold.dim_date ADD PRIMARY KEY (date_key);
ALTER TABLE gold.dim_location ADD PRIMARY KEY (location_key);
ALTER TABLE gold.dim_crime_type ADD PRIMARY KEY (crime_type_key);
ALTER TABLE gold.dim_event ADD PRIMARY KEY (event_key);
ALTER TABLE gold.dim_item ADD PRIMARY KEY (item_key);
ALTER TABLE gold.fact_incident ADD PRIMARY KEY (incident_key);
ALTER TABLE gold.bridge_incident_item ADD PRIMARY KEY (bridge_id);

ALTER TABLE gold.fact_incident
ADD FOREIGN KEY (date_key) REFERENCES gold.dim_date(date_key),
ADD FOREIGN KEY (location_key) REFERENCES gold.dim_location(location_key),
ADD FOREIGN KEY (crime_type_key) REFERENCES gold.dim_crime_type(crime_type_key),
ADD FOREIGN KEY (event_key) REFERENCES gold.dim_event(event_key);

ALTER TABLE gold.bridge_incident_item
ADD FOREIGN KEY (incident_key) REFERENCES gold.fact_incident(incident_key),
ADD FOREIGN KEY (item_key) REFERENCES gold.dim_item(item_key);

COMMIT;