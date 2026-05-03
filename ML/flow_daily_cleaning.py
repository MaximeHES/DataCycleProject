from prefect import flow, task, get_run_logger
import subprocess
import sys
import time
from pathlib import Path

SCRIPTS_DIR = Path(r"C:\DataCycle\ml\scripts")


@task(retries=2, retry_delay_seconds=60)
def run_merge_cleaning():
    logger = get_run_logger()
    script = SCRIPTS_DIR / "merge_cleaning_history.py"
    logger.info(f"Starting: {script}")

    result = subprocess.run(
        [sys.executable, str(script)],
        capture_output=True,
        text=True,
        cwd=str(SCRIPTS_DIR)
    )

    logger.info(f"Return code: {result.returncode}")
    if result.stdout:
        logger.info(f"STDOUT:\n{result.stdout}")
    if result.stderr:
        logger.error(f"STDERR:\n{result.stderr}")
    if result.returncode != 0:
        raise Exception(f"merge_cleaning_history.py failed with exit code {result.returncode}")

    logger.info("merge_cleaning_history.py completed successfully")


@task(retries=2, retry_delay_seconds=60)
def run_predict_cleaning():
    logger = get_run_logger()
    script = SCRIPTS_DIR / "predict_cleaning.py"
    logger.info(f"Starting: {script}")

    result = subprocess.run(
        [sys.executable, str(script)],
        capture_output=True,
        text=True,
        cwd=str(SCRIPTS_DIR)
    )

    logger.info(f"Return code: {result.returncode}")
    if result.stdout:
        logger.info(f"STDOUT:\n{result.stdout}")
    if result.stderr:
        logger.error(f"STDERR:\n{result.stderr}")
    if result.returncode != 0:
        raise Exception(f"predict_cleaning.py failed with exit code {result.returncode}")

    logger.info("predict_cleaning.py completed successfully")


@task(retries=2, retry_delay_seconds=60)
def run_load_cleaning():
    logger = get_run_logger()
    script = SCRIPTS_DIR / "load_cleaning_to_sql.py"
    logger.info(f"Starting: {script}")

    result = subprocess.run(
        [sys.executable, str(script)],
        capture_output=True,
        text=True,
        cwd=str(SCRIPTS_DIR)
    )

    logger.info(f"Return code: {result.returncode}")
    if result.stdout:
        logger.info(f"STDOUT:\n{result.stdout}")
    if result.stderr:
        logger.error(f"STDERR:\n{result.stderr}")
    if result.returncode != 0:
        raise Exception(f"load_cleaning_to_sql.py failed with exit code {result.returncode}")

    logger.info("load_cleaning_to_sql.py completed successfully")


@flow(name="ml-daily-cleaning-pipeline")
def daily_cleaning_pipeline():
    run_merge_cleaning()
    time.sleep(90)
    run_predict_cleaning()
    time.sleep(30)
    run_load_cleaning()


if __name__ == "__main__":
    daily_cleaning_pipeline.serve(
        name="ml-daily-cleaning-scheduled",
        cron="0 2 * * *",
        pause_on_shutdown=False,
    )
