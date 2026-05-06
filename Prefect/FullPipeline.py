from prefect import flow, task, get_run_logger
import subprocess
import sys
from pathlib import Path


@task(retries=2, retry_delay_seconds=30)
def run_bronze():
    logger = get_run_logger()

    ps_script = Path(r"C:\DataCycle_CICD_Test\Bronze\eversys_incremental_flat_V11_regenerated.ps1")
    working_dir = str(ps_script.parent)

    logger.info(f"Starting Bronze layer: {ps_script}")

    result = subprocess.run(
        [
            "powershell.exe",
            "-NoProfile",
            "-ExecutionPolicy", "Bypass",
            "-File", str(ps_script)
        ],
        capture_output=True,
        text=True,
        cwd=working_dir
    )

    logger.info(f"Bronze return code: {result.returncode}")

    if result.stdout:
        logger.info(f"Bronze STDOUT:\n{result.stdout}")

    if result.stderr:
        logger.error(f"Bronze STDERR:\n{result.stderr}")

    if result.returncode != 0:
        raise Exception(f"Bronze script failed with exit code {result.returncode}")

    logger.info("Bronze completed successfully")


@task(retries=2, retry_delay_seconds=30)
def run_silver():
    logger = get_run_logger()

    py_script = Path(r"C:\DataCycle_CICD_Test\Silver\Silver_CleanerV3.py")
    working_dir = str(py_script.parent)

    logger.info(f"Starting Silver Cleaner: {py_script}")

    result = subprocess.run(
        [
            sys.executable,
            str(py_script)
        ],
        capture_output=True,
        text=True,
        cwd=working_dir
    )

    logger.info(f"Silver return code: {result.returncode}")

    if result.stdout:
        logger.info(f"Silver STDOUT:\n{result.stdout}")

    if result.stderr:
        logger.error(f"Silver STDERR:\n{result.stderr}")

    if result.returncode != 0:
        raise Exception(f"Silver script failed with exit code {result.returncode}")

    logger.info("Silver completed successfully")


@task(retries=2, retry_delay_seconds=30)
def run_gold():
    logger = get_run_logger()

    gold_script = Path(r"C:\DataCycle_CICD_Test\Gold\gold_loading_flow_v3.py")
    working_dir = str(gold_script.parent)

    logger.info(f"Starting Gold layer: {gold_script}")
    logger.info(f"Gold working directory: {working_dir}")
    logger.info(f"Python executable used by Prefect: {sys.executable}")

    result = subprocess.run(
        [
            sys.executable,
            str(gold_script)
        ],
        capture_output=True,
        text=True,
        cwd=working_dir
    )

    logger.info(f"Gold return code: {result.returncode}")

    if result.stdout:
        logger.info(f"Gold STDOUT:\n{result.stdout}")

    if result.stderr:
        logger.error(f"Gold STDERR:\n{result.stderr}")

    if result.returncode != 0:
        raise Exception(f"Gold script failed with exit code {result.returncode}")

    logger.info("Gold completed successfully")


@flow(name="eversys-pipeline")
def eversys_pipeline():
    run_bronze()
    run_silver()
    run_gold()


if __name__ == "__main__":
    eversys_pipeline.serve(
        name="eversys-pipeline-scheduled",
        cron="*/5 * * * *",
        pause_on_shutdown=False,
    )