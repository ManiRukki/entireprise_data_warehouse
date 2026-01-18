# Enterprise Data Warehouse Project

## Overview
This repository contains the infrastructure code for a modern, high-volume Enterprise Data Warehouse (EDW). It is designed to ingest real-time streaming data, process it via batch ETL using Airflow and dbt, and store it in a partitioned SQL warehouse (simulating Snowflake/PostgreSQL).

## Architecture
1.  **Ingestion:** Python scripts (`scripts/`) simulate High-Velocity Events (Kafka-like producers) generating 1M+ events.
2.  **Storage:** SQL Schema (`sql/`) utilizing Table Partitioning and Star Schema (Fact/Dim) design for performant queries on "Big Data".
3.  **Transformation:** dbt project structure (placeholder) for modeling data.
4.  **Orchestration:** Apache Airflow DAGs (`dags/`) for managing dependencies and scheduling.

## Project Structure
```
enterprise_data_warehouse/
├── dags/                  # Airflow Orchestration
│   └── main_etl_dag.py    # Daily Batch Processing DAG
├── scripts/               # Python Ingestion Scripts
│   └── generate_streaming_data.py # Simulates massive event stream
├── sql/                   # Database DDLs
│   └── warehouse_schema.sql # Complex schema definition
├── dbt/                   # dbt transformation layer
└── requirements.txt       # Python dependencies
```

## Quick Start
1.  **Install Dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

2.  **Simulate Real-Time Data Stream:**
    Run the generator to see the "throughput" simulation:
    ```bash
    python scripts/generate_streaming_data.py
    ```

## Technology Stack
- **Languages:** Python, SQL
- **Orchestration:** Apache Airflow
- **Modeling:** dbt (Data Build Tool)
- **Database:** PostgreSQL (Compatible Syntax)
