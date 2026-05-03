from prefect import flow, task, get_run_logger
import subprocess
import sys
import time
from pathlib import Path

SCRIPTS_DIR = Path(r"C:\DataCycle\ml\scripts")


@task(retries=2, retry_delay_seconds=60)
def run_merge_product():
    logger = get_run_logger()
    script = SCRIPTS_DIR / "merge_product_history.py"
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
        raise Exception(f"merge_product_history.py failed with exit code {result.returncode}")

    logger.info("merge_product_history.py completed successfully")


@task(retries=2, retry_delay_seconds=60)
def run_predict_product():
    logger = get_run_logger()
    script = SCRIPTS_DIR / "predict_product.py"
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
        raise Exception(f"predict_product.py failed with exit code {result.returncode}")

    logger.info("predict_product.py completed successfully")


@task(retries=2, retry_delay_seconds=60)
def run_load_product():
    logger = get_run_logger()
    script = SCRIPTS_DIR / "load_product_to_sql.py"
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
        raise Exception(f"load_product_to_sql.py failed with exit code {result.returncode}")

    logger.info("load_product_to_sql.py completed successfully")


@flow(name="ml-weekly-product-pipeline")
def weekly_product_pipeline():
    run_merge_product()
    time.sleep(90)
    run_predict_product()
    time.sleep(30)
    run_load_product()


if __name__ == "__main__":
    weekly_product_pipeline.serve(
        name="ml-weekly-product-scheduled",
        cron="0 4 * * 0",
        pause_on_shutdown=False,
    )
