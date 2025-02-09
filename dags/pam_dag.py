# credentials_dag.py
import sys
sys.path.insert(0, '/opt/airflow')
import json
from datetime import datetime
from airflow import DAG
from airflow.models import Variable
from airflow.operators.python import PythonOperator

# Import the run_for_user function from your module
from plugins.pam_main import run_for_user

default_args = {
    "start_date": datetime(2025, 2, 8),
}

with DAG(
    "credentials_dag",
    schedule_interval=None,
    default_args=default_args,
    catchup=False,
) as dag:

    def run_task_for_user(user_name, **kwargs):
        # Get the credentials JSON from Airflow Variables.
        # You should set a variable called "creds" in Airflow with the entire JSON content.
        credentials_str = Variable.get("creds")
        try:
            credentials_json = json.loads(credentials_str)
        except Exception as e:
            raise ValueError(f"Invalid JSON in Airflow Variable: {e}")
        run_for_user(user_name, credentials_json)

    # List of user names to create tasks for:
    user_list = ["business-lead", "finance", "marketing", "product-lead", "engineering", "labware-engineer"]

    tasks = {}
    for user in user_list:
        tasks[user] = PythonOperator(
            task_id=f"run_for_{user}",
            python_callable=run_task_for_user,
            op_kwargs={"user_name": user},
        )

    # (Optional) If there is an order/dependency between tasks, you can set them here.
    # For instance, you might want to run them sequentially:
    # tasks["business-lead"] >> tasks["finance"] >> tasks["marketing"] >> ...
