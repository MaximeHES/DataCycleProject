"""
load_cleaning_to_sql.py

Loads cleaning_predictions.csv into the gold database
via staging table + surrogate key resolution.
"""

import logging
import pyodbc
import pandas as pd
import numpy as np

from keyVaultConfig import DB_CONFIG


logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# -- PATHS ---------------------------------------------------
CLEANING_FILE = r"C:\DataCycle\ml\output\cleaning_predictions.csv"
# ------------------------------------------------------------


def get_connection():

    conn_str = (
        f"DRIVER={{{DB_CONFIG['driver']}}};"
        f"SERVER=tcp:{DB_CONFIG['server']},1433;"
        f"DATABASE={DB_CONFIG['database']};"
        f"UID={DB_CONFIG['username']};"
        f"PWD={DB_CONFIG['password']};"
        "Encrypt=yes;"
        "TrustServerCertificate=no;"
        "Connection Timeout=60;"
    )

    return pyodbc.connect(conn_str)


def clean_value(v):
    if pd.isna(v):
        return None
    if isinstance(v, np.integer):
        return int(v)
    if isinstance(v, np.floating):
        return float(v)
    return v


def truncate_staging(cursor):
    cursor.execute("TRUNCATE TABLE [gold].[stg_cleaning_predictions]")
    logger.info("Staging table truncated.")


def load_cleaning_to_staging(cursor, filepath):
    df = pd.read_csv(
        filepath,
        encoding="utf-8-sig",
        parse_dates=[
            "last_cleaning_date",
            "next_cleaning_approx",
            "prediction_run_date"
        ]
    )

    rows = df[[
        "machine_id",
        "last_cleaning_date",
        "days_since_last_cleaning",
        "predicted_hours",
        "predicted_days",
        "next_cleaning_approx",
        "urgency",
        "prediction_run_date",
        "machine_mae",
        "machine_rmse",
        "machine_test_rows"
    ]].values.tolist()

    rows = [[clean_value(v) for v in row] for row in rows]

    cursor.fast_executemany = True
    cursor.executemany(
        """
        INSERT INTO [gold].[stg_cleaning_predictions]
            (machine_id, last_cleaning_date, days_since_last_cleaning,
             predicted_hours, predicted_days, next_cleaning_approx,
             urgency, prediction_run_date,
             machine_mae, machine_rmse, machine_test_rows)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        rows
    )

    logger.info(f"Loaded {len(rows)} rows into stg_cleaning_predictions.")


def validate_staging(cursor):
    cursor.execute("""
        SELECT DISTINCT stg.machine_id
        FROM [gold].[stg_cleaning_predictions] stg
        LEFT JOIN [gold].[dim_machine] dm
            ON dm.machine_id = stg.machine_id
            AND dm.is_current = 1
        WHERE dm.machine_key IS NULL
    """)
    missing = [row[0] for row in cursor.fetchall()]
    if missing:
        raise ValueError(f"Cleaning predictions: machine_id(s) not in dim_machine: {missing}")

    logger.info("Validation passed -- all machine_ids found in dim_machine.")


def promote_to_fact(cursor):
    cursor.execute("""
        DELETE fcp
        FROM [gold].[fact_cleaning_predictions] fcp
        WHERE fcp.prediction_run_date IN (
            SELECT DISTINCT prediction_run_date
            FROM [gold].[stg_cleaning_predictions]
        )
    """)
    logger.info(f"Deleted {cursor.rowcount} existing cleaning prediction rows for same run_date.")

    cursor.execute("""
        INSERT INTO [gold].[fact_cleaning_predictions] (
            machine_key, last_cleaning_date, days_since_last_cleaning,
            predicted_hours, predicted_days, next_cleaning_approx,
            urgency, machine_mae, machine_rmse, machine_test_rows,
            prediction_run_date
        )
        SELECT
            dm.machine_key,
            stg.last_cleaning_date,
            stg.days_since_last_cleaning,
            stg.predicted_hours,
            stg.predicted_days,
            stg.next_cleaning_approx,
            stg.urgency,
            stg.machine_mae,
            stg.machine_rmse,
            stg.machine_test_rows,
            stg.prediction_run_date
        FROM [gold].[stg_cleaning_predictions] stg
        INNER JOIN [gold].[dim_machine] dm
            ON dm.machine_id = stg.machine_id
            AND dm.is_current = 1
    """)
    inserted = cursor.rowcount
    logger.info(f"Inserted {inserted} rows into fact_cleaning_predictions.")

    return inserted


def main():
    conn   = get_connection()
    cursor = conn.cursor()

    try:
        truncate_staging(cursor)
        load_cleaning_to_staging(cursor, CLEANING_FILE)
        validate_staging(cursor)
        inserted = promote_to_fact(cursor)
        conn.commit()

        logger.info(f"SUCCESS -- Loaded {inserted} cleaning predictions into gold.")

    except Exception:
        conn.rollback()
        logger.exception("FAILED -- Transaction rolled back.")
        raise

    finally:
        cursor.close()
        conn.close()


if __name__ == "__main__":
    main()