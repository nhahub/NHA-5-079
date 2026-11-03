from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.bash import BashOperator

default_args = {
    "owner": "omar_elhadidi",
    "retries": 2,
    "retry_delay": timedelta(minutes=5),
}

with DAG(
    dag_id="moi_crime_pipeline",
    default_args=default_args,
    schedule="@daily",
    start_date=datetime(2026, 11, 1),
    catchup=False,
    tags=["crime_intelligence", "medallion", "production"],
) as dag:

    extract_bronze = BashOperator(
        task_id="extract_bronze",
        bash_command="python src/extract_crime_news.py",
    )

    transform_silver = BashOperator(
        task_id="transform_silver",
        bash_command="python src/transform_silver.py",
    )

    load_gold = BashOperator(
        task_id="load_gold",
        bash_command="python src/load_gold_warehouse.py",
    )

    quality_gate = BashOperator(
        task_id="quality_gate",
        bash_command="pytest tests/test_warehouse.py",
    )

    extract_bronze >> transform_silver >> load_gold >> quality_gate

