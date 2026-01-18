from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.python_operator import PythonOperator
from airflow.operators.bash_operator import BashOperator

default_args = {
    'owner': 'data_engineering',
    'depends_on_past': False,
    'start_date': datetime(2024, 1, 1),
    'email_on_failure': True,
    'email_on_retry': False,
    'retries': 3,
    'retry_delay': timedelta(minutes=5),
}

dag = DAG(
    'enterprise_daily_etl',
    default_args=default_args,
    description='Main ETL DAG for Enterprise Data Warehouse',
    schedule_interval='0 2 * * *', # Daily at 2 AM
    catchup=False
)

def _audit_check(**context):
    print("Running data quality audit on raw stream...")
    # Logic to check nulls, schema validation etc.
    return "Audit Pass"

t1_ingest_kafka = BashOperator(
    task_id='ingest_kafka_topic_purchases',
    bash_command='python /opt/scripts/ingest_stream.py --topic purchases --lookback 1h',
    dag=dag,
)

t2_data_quality = PythonOperator(
    task_id='raw_zone_quality_check',
    python_callable=_audit_check,
    dag=dag,
)

t3_dbt_run = BashOperator(
    task_id='dbt_run_models',
    bash_command='dbt run --models tag:daily_core',
    dag=dag,
)

t4_refresh_marts = BashOperator(
    task_id='refresh_tableau_extracts',
    bash_command='echo "Triggering API for Tableau refresh"',
    dag=dag,
)

t1_ingest_kafka >> t2_data_quality >> t3_dbt_run >> t4_refresh_marts
