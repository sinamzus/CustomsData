-- Iran Trade Map — PostgreSQL Schema
-- Optimized for time-series queries by HS code, country, and customs office

CREATE TABLE IF NOT EXISTS countries (
    iso3        CHAR(3)      PRIMARY KEY,
    iso2        CHAR(2),
    name_en     VARCHAR(100) NOT NULL,
    name_fa     VARCHAR(100),
    region      VARCHAR(80),
    continent   VARCHAR(40),
    latitude    NUMERIC(8,4),
    longitude   NUMERIC(8,4)
);

CREATE TABLE IF NOT EXISTS hs_chapters (
    chapter     SMALLINT     PRIMARY KEY,  -- 2-digit
    section     SMALLINT     NOT NULL,
    name_en     VARCHAR(120) NOT NULL,
    name_fa     VARCHAR(120)
);

CREATE TABLE IF NOT EXISTS hs_sections (
    section     SMALLINT     PRIMARY KEY,
    name_en     VARCHAR(120) NOT NULL,
    name_fa     VARCHAR(120)
);

CREATE TABLE IF NOT EXISTS customs_offices (
    id          SERIAL       PRIMARY KEY,
    name_fa     VARCHAR(120) NOT NULL UNIQUE,
    name_en     VARCHAR(120),
    province    VARCHAR(80),
    border_type VARCHAR(20)  CHECK (border_type IN ('land','sea','air','rail','special'))
);

CREATE TABLE IF NOT EXISTS trade_flows (
    id              BIGSERIAL    PRIMARY KEY,
    -- Time
    shamsi_year     SMALLINT     NOT NULL,
    shamsi_month    SMALLINT,                    -- NULL for annual records
    -- Direction
    direction       VARCHAR(10)  NOT NULL CHECK (direction IN ('export','import','transit')),
    -- Commodity
    hs_code         VARCHAR(12),
    hs_chapter      SMALLINT     REFERENCES hs_chapters(chapter),
    commodity_fa    VARCHAR(300),
    -- Geography
    country_iso3    CHAR(3)      REFERENCES countries(iso3),
    country_raw     VARCHAR(120),                -- original string before normalization
    customs_id      INT          REFERENCES customs_offices(id),
    customs_raw     VARCHAR(120),
    province        VARCHAR(80),
    -- Quantities & Values
    net_weight_kg   NUMERIC(18,2),
    gross_weight_kg NUMERIC(18,2),
    quantity        NUMERIC(18,2),
    quantity_unit   VARCHAR(20),
    value_usd       NUMERIC(18,2),
    value_rial      NUMERIC(22,0),
    value_cif_usd   NUMERIC(18,2),
    value_fob_usd   NUMERIC(18,2),
    -- Provenance
    source_file     VARCHAR(255),
    file_hash       CHAR(8),
    loaded_at       TIMESTAMP    DEFAULT NOW()
);

-- Indexes for common query patterns
CREATE INDEX IF NOT EXISTS idx_tf_year_month   ON trade_flows (shamsi_year, shamsi_month);
CREATE INDEX IF NOT EXISTS idx_tf_direction    ON trade_flows (direction);
CREATE INDEX IF NOT EXISTS idx_tf_country      ON trade_flows (country_iso3);
CREATE INDEX IF NOT EXISTS idx_tf_hs_code      ON trade_flows (hs_code);
CREATE INDEX IF NOT EXISTS idx_tf_hs_chapter   ON trade_flows (hs_chapter);
CREATE INDEX IF NOT EXISTS idx_tf_customs      ON trade_flows (customs_id);
CREATE INDEX IF NOT EXISTS idx_tf_year_dir     ON trade_flows (shamsi_year, direction);

-- Aggregate view: annual trade by country
CREATE OR REPLACE VIEW v_annual_by_country AS
SELECT
    shamsi_year,
    direction,
    country_iso3,
    SUM(net_weight_kg)  AS total_weight_kg,
    SUM(value_usd)      AS total_value_usd
FROM trade_flows
WHERE country_iso3 IS NOT NULL
GROUP BY shamsi_year, direction, country_iso3;

-- Aggregate view: annual trade by HS section
CREATE OR REPLACE VIEW v_annual_by_section AS
SELECT
    shamsi_year,
    direction,
    hs_chapter,
    SUM(net_weight_kg)  AS total_weight_kg,
    SUM(value_usd)      AS total_value_usd
FROM trade_flows
WHERE hs_chapter IS NOT NULL
GROUP BY shamsi_year, direction, hs_chapter;
