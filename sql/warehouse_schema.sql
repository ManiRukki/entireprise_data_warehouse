-- Enterprise Data Warehouse Schema
-- Designing for High Volume & Partitioning

-- 1. RAW LANDING LAYER (JSON Store)
CREATE TABLE raw.events_stream (
    event_id UUID PRIMARY KEY,
    kafka_offset BIGINT,
    ingest_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    raw_payload JSONB
) PARTITION BY RANGE (ingest_timestamp);

-- 2. DIMENSION TABLES (Star Schema)
CREATE TABLE dim_users (
    user_key BIGSERIAL PRIMARY KEY,
    user_id VARCHAR(50) UNIQUE,
    current_segment VARCHAR(20),
    registration_date DATE,
    ltv_score DECIMAL(10,2),
    valid_from TIMESTAMP,
    valid_to TIMESTAMP,
    is_current BOOLEAN
);

CREATE TABLE dim_products (
    product_key BIGSERIAL PRIMARY KEY,
    product_id VARCHAR(50) UNIQUE,
    category VARCHAR(100),
    brand VARCHAR(100),
    base_price DECIMAL(10,2)
);

-- 3. FACT TABLE (Transactional)
-- High volume table partitioned by date
CREATE TABLE fact_purchases (
    purchase_key BIGSERIAL PRIMARY KEY,
    transaction_id VARCHAR(100),
    user_key BIGINT REFERENCES dim_users(user_key),
    product_key BIGINT REFERENCES dim_products(product_key),
    purchase_timestamp TIMESTAMP,
    quantity INT,
    total_amount DECIMAL(12,2),
    discount_applied DECIMAL(10,2),
    platform_key INT
) PARTITION BY RANGE (purchase_timestamp);

-- Indexes for performance
CREATE INDEX idx_fact_purchases_user ON fact_purchases(user_key);
CREATE INDEX idx_fact_purchases_time ON fact_purchases(purchase_timestamp);
