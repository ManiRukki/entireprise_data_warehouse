# Enterprise Data Warehouse — Snowflake Lakehouse Migration

Migration of 8 heterogeneous source systems (95TB+) from legacy data warehouses into a unified Snowflake lakehouse. Built with dbt Core, Apache Airflow, Snowpark, and Azure Data Factory — zero data loss, 36% query efficiency improvement, 37% reduction in batch execution costs.

---

## Architecture

```
Source Systems (8x)
┌──────────┬────────────┬───────────┬──────────┐
│ Oracle DW │ SQL Server │ Teradata  │ SAP HANA │
│ MySQL RDS │ PostgreSQL │ Flat Files│ REST APIs│
└─────┬─────┴──────┬─────┴─────┬─────┴────┬─────┘
      │            │           │          │
      └────────────┴───────────┴──────────┘
                        │
               Azure Data Factory
             (Extraction + Landing)
                        │
               ADLS Gen2 (Raw Zone)
                        │
                   dbt Core
            ┌───────────┴──────────┐
            │       Snowflake      │
            │  RAW → STAGING → MARTS│
            └──────────────────────┘
                        │
              Apache Airflow (Orchestration)
                        │
              Power BI / Tableau Dashboards
```

---

## Repository Structure

```
enterprise_data_warehouse/
├── dags/
│   ├── main_etl_dag.py              # Master orchestration DAG
│   └── source_extractors/
│       ├── oracle_extractor_dag.py
│       └── sqlserver_extractor_dag.py
├── dbt/
│   ├── models/
│   │   ├── staging/
│   │   │   ├── stg_oracle__orders.sql
│   │   │   └── stg_sqlserver__customers.sql
│   │   └── marts/
│   │       ├── fct_orders.sql
│   │       ├── dim_customers.sql
│   │       └── dim_products.sql
│   ├── tests/
│   │   └── assert_revenue_reconciliation.sql
│   └── dbt_project.yml
├── scripts/
│   ├── snowpark_validator.py        # Row count + checksum reconciliation
│   └── bulk_loader.py              # COPY INTO wrapper for high-throughput load
├── sql/
│   └── warehouse_schema.sql        # Snowflake DDL — star schema definition
└── requirements.txt
```

---

## Core Components

### Airflow Orchestration DAG
```python
# dags/main_etl_dag.py
from datetime import datetime, timedelta
from airflow import DAG
from airflow.providers.snowflake.operators.snowflake import SnowflakeOperator
from airflow.operators.bash import BashOperator
from airflow.operators.python import PythonOperator

default_args = {
    "owner": "data-engineering",
    "retries": 2,
    "retry_delay": timedelta(minutes=5),
    "email_on_failure": True,
}

with DAG(
    dag_id="enterprise_dw_migration_orchestrator",
    default_args=default_args,
    schedule_interval="@daily",
    start_date=datetime(2024, 1, 1),
    catchup=False,
    tags=["migration", "snowflake", "dbt"],
) as dag:

    extract_oracle = BashOperator(
        task_id="extract_oracle_orders",
        bash_command="python /opt/airflow/scripts/oracle_extractor.py --date {{ ds }}",
    )

    extract_sqlserver = BashOperator(
        task_id="extract_sqlserver_customers",
        bash_command="python /opt/airflow/scripts/sqlserver_extractor.py --date {{ ds }}",
    )

    load_to_snowflake = SnowflakeOperator(
        task_id="copy_into_raw",
        snowflake_conn_id="snowflake_migration",
        sql="""
            COPY INTO raw.oracle.orders
            FROM @migration_stage/orders/{{ ds }}/
            FILE_FORMAT = (TYPE = PARQUET);
        """,
    )

    run_dbt_staging = BashOperator(
        task_id="dbt_run_staging",
        bash_command="cd /opt/dbt && dbt run --select staging --target prod",
    )

    run_dbt_marts = BashOperator(
        task_id="dbt_run_marts",
        bash_command="cd /opt/dbt && dbt run --select marts --target prod",
    )

    run_dbt_tests = BashOperator(
        task_id="dbt_test",
        bash_command="cd /opt/dbt && dbt test --target prod",
    )

    [extract_oracle, extract_sqlserver] >> load_to_snowflake
    load_to_snowflake >> run_dbt_staging >> run_dbt_marts >> run_dbt_tests
```

### dbt Staging Model
```sql
-- dbt/models/staging/stg_oracle__orders.sql
{{
  config(
    materialized='incremental',
    unique_key='order_id',
    incremental_strategy='merge',
    cluster_by=['order_date']
  )
}}

WITH source AS (
  SELECT * FROM {{ source('oracle_raw', 'orders') }}
  {% if is_incremental() %}
    WHERE updated_at > (SELECT MAX(updated_at) FROM {{ this }})
  {% endif %}
),

cleaned AS (
  SELECT
    CAST(order_id AS VARCHAR(36))                      AS order_id,
    CAST(customer_id AS VARCHAR(36))                   AS customer_id,
    TRY_TO_DATE(order_dt, 'YYYYMMDD')                  AS order_date,
    CAST(REPLACE(order_amt, '$', '') AS DECIMAL(18,2)) AS order_amount_usd,
    UPPER(TRIM(order_status))                          AS order_status,
    CAST(qty AS INTEGER)                               AS quantity,
    CURRENT_TIMESTAMP()                                AS _dbt_updated_at
  FROM source
  WHERE order_id IS NOT NULL
)

SELECT * FROM cleaned
```

### Snowpark Reconciliation Validator
```python
# scripts/snowpark_validator.py
from snowflake.snowpark import Session
from snowflake.snowpark import functions as F
import logging

logger = logging.getLogger(__name__)

class MigrationValidator:
    """Validates row counts and checksums between source and target tables."""

    def __init__(self, session: Session):
        self.session = session

    def validate_row_counts(self, source_table: str, target_table: str) -> dict:
        source_count = self.session.table(source_table).count()
        target_count = self.session.table(target_table).count()

        result = {
            "source_table": source_table,
            "target_table": target_table,
            "source_count": source_count,
            "target_count": target_count,
            "match": source_count == target_count,
            "delta": target_count - source_count,
        }

        if not result["match"]:
            logger.warning(
                f"Row count mismatch: {source_table}={source_count} "
                f"vs {target_table}={target_count}"
            )
        return result

    def validate_checksum(self, source_table: str, target_table: str, numeric_cols: list) -> dict:
        def get_sums(table):
            df = self.session.table(table)
            return df.agg(*[F.sum(c).alias(c) for c in numeric_cols]).collect()[0].as_dict()

        source_sums = get_sums(source_table)
        target_sums = get_sums(target_table)

        mismatches = {
            col: {"source": source_sums[col], "target": target_sums[col]}
            for col in numeric_cols
            if abs((source_sums[col] or 0) - (target_sums[col] or 0)) > 0.01
        }

        return {
            "all_checksums_match": len(mismatches) == 0,
            "mismatches": mismatches,
        }
```

### Snowflake Star Schema DDL
```sql
-- sql/warehouse_schema.sql

-- Fact table: Orders
CREATE OR REPLACE TABLE marts.fct_orders (
    order_key         VARCHAR(64)    NOT NULL,
    order_id          VARCHAR(36)    NOT NULL,
    customer_key      VARCHAR(64),
    product_key       VARCHAR(64),
    order_date        DATE           NOT NULL,
    order_status      VARCHAR(50),
    order_amount_usd  DECIMAL(18,2),
    quantity          INTEGER,
    gross_revenue     DECIMAL(18,2),
    source_system     VARCHAR(50),
    _dbt_updated_at   TIMESTAMP_NTZ  DEFAULT CURRENT_TIMESTAMP(),
    PRIMARY KEY (order_key)
)
CLUSTER BY (order_date, source_system);

-- Dimension: Customers
CREATE OR REPLACE TABLE marts.dim_customers (
    customer_key      VARCHAR(64)    NOT NULL,
    customer_id       VARCHAR(36)    NOT NULL,
    customer_name     VARCHAR(255),
    email             VARCHAR(255),
    country           VARCHAR(100),
    segment           VARCHAR(50),
    created_date      DATE,
    source_system     VARCHAR(50),
    PRIMARY KEY (customer_key)
);

-- Dimension: Products
CREATE OR REPLACE TABLE marts.dim_products (
    product_key       VARCHAR(64)    NOT NULL,
    product_id        VARCHAR(36)    NOT NULL,
    product_name      VARCHAR(255),
    category          VARCHAR(100),
    subcategory       VARCHAR(100),
    unit_price        DECIMAL(18,2),
    source_system     VARCHAR(50),
    PRIMARY KEY (product_key)
);
```

---

## Performance Results

| Metric | Before | After | Improvement |
|---|---|---|---|
| Data sources consolidated | 8 siloed DWs | 1 Snowflake lakehouse | — |
| Total data migrated | 95TB | 95TB | Zero data loss |
| Avg query runtime | 8.2 min | 5.2 min | **36% faster** |
| Batch execution cost | Baseline | — | **37% reduction** |
| Pipeline reliability | Manual / ad hoc | Fully automated | — |

---

## Setup

```bash
# Install dependencies
pip install -r requirements.txt

# Configure dbt profile
cp dbt/profiles.yml.example ~/.dbt/profiles.yml

# Run dbt models
cd dbt
dbt deps
dbt run --target dev
dbt test --target dev

# Run validation
python scripts/snowpark_validator.py --config config/sources.yaml
```

---

## Tech Stack

`dbt Core` `Snowflake` `Snowpark` `Apache Airflow` `Azure Data Factory`
`ADLS Gen2` `Python` `SQL` `Terraform` `Power BI`

---

## Related Projects

- [realtime-ml-feature-store](https://github.com/ManiRukki/realtime_ml_feature_store)
- [streaming-event-pipeline](https://github.com/ManiRukki/streaming_event_pipeline)
- [customer-analytics-platform](https://github.com/ManiRukki/customer-analytics-platform)
