"""
load_product_to_sql.py

Loads product_predictions.csv into the gold database
via staging table + surrogate key resolution.
"""

import logging
import pyodbc
import pandas as pd
import numpy as np

from db_config import DB_CONFIG

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# -- PATHS ---------------------------------------------------
PRODUCT_FILE = r"C:\DataCycle\ml\output\product_predictions.csv"
# ------------------------------------------------------------


def get_connection():
    conn_str = (
        f"DRIVER={{{DB_CONFIG['driver']}}};"
        f"SERVER={DB_CONFIG['server']};"
        f"DATABASE={DB_CONFIG['database']};"
        f"UID={DB_CONFIG['username']};"
        f"PWD={DB_CONFIG['password']};"
        "Encrypt=yes;"
        "TrustServerCertificate=no;"
        "Connection Timeout=30;"
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
    cursor.execute("TRUNCATE TABLE [gold].[stg_product_predictions]")
    logger.info("Staging table truncated.")


def load_product_to_staging(cursor, filepath):
    df = pd.read_csv(
        filepath,
        encoding="utf-8-sig",
        parse_dates=[
            "week_start",
            "week_end",
            "prediction_run_date"
        ]
    )

    rows = df[[
        "machine_id",
        "prod_type",
        "prod_type_name",
        "tier",
        "week_start",
        "week_end",
        "predicted_count",
        "last_7d_actual",
        "days_since_active",
        "combo_mae",
        "combo_rmse",
        "combo_test_weeks",
        "prediction_run_date"
    ]].values.tolist()

    rows = [[clean_value(v) for v in row] for row in rows]

    cursor.fast_executemany = True
    cursor.executemany(
        """
        INSERT INTO [gold].[stg_product_predictions]
            (machine_id, prod_type, prod_type_name, tier,
             week_start, week_end, predicted_count,
             last_7d_actual, days_since_active,
             combo_mae, combo_rmse, combo_test_weeks,
             prediction_run_date)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        rows
    )

    logger.info(f"Loaded {len(rows)} rows into stg_product_predictions.")


def validate_staging(cursor):
    cursor.execute("""
        SELECT DISTINCT stg.machine_id
        FROM [gold].[stg_product_predictions] stg
        LEFT JOIN [gold].[dim_machine] dm
            ON dm.machine_id = stg.machine_id
            AND dm.is_current = 1
        WHERE dm.machine_key IS NULL
    """)
    missing = [row[0] for row in cursor.fetchall()]
    if missing:
        raise ValueError(f"Product predictions: machine_id(s) not in dim_machine: {missing}")

    cursor.execute("""
        SELECT DISTINCT stg.prod_type, stg.prod_type_name
        FROM [gold].[stg_product_predictions] stg
        LEFT JOIN [gold].[dim_product_type] dpt
            ON dpt.prod_type = stg.prod_type
        WHERE dpt.product_key IS NULL
    """)
    missing = cursor.fetchall()
    if missing:
        raise ValueError(f"Product predictions: prod_type(s) not in dim_product_type: {missing}")

    logger.info("Validation passed -- all machine_ids and prod_types found in dimension tables.")


def promote_to_fact(cursor):
    cursor.execute("""
        DELETE fpp
        FROM [gold].[fact_product_predictions] fpp
        WHERE fpp.prediction_run_date IN (
            SELECT DISTINCT prediction_run_date
            FROM [gold].[stg_product_predictions]
        )
    """)
    logger.info(f"Deleted {cursor.rowcount} existing product prediction rows for same run_date.")

    cursor.execute("""
        INSERT INTO [gold].[fact_product_predictions] (
            machine_key, product_key, tier,
            week_start, week_end, predicted_count,
            last_7d_actual, days_since_active,
            combo_mae, combo_rmse, combo_test_weeks,
            prediction_run_date
        )
        SELECT
            dm.machine_key,
            dpt.product_key,
            stg.tier,
            stg.week_start,
            stg.week_end,
            stg.predicted_count,
            stg.last_7d_actual,
            stg.days_since_active,
            stg.combo_mae,
            stg.combo_rmse,
            stg.combo_test_weeks,
            stg.prediction_run_date
        FROM [gold].[stg_product_predictions] stg
        INNER JOIN [gold].[dim_machine] dm
            ON dm.machine_id = stg.machine_id
            AND dm.is_current = 1
        INNER JOIN [gold].[dim_product_type] dpt
            ON dpt.prod_type = stg.prod_type
    """)
    inserted = cursor.rowcount
    logger.info(f"Inserted {inserted} rows into fact_product_predictions.")

    return inserted


def main():
    conn   = get_connection()
    cursor = conn.cursor()

    try:
        truncate_staging(cursor)
        load_product_to_staging(cursor, PRODUCT_FILE)
        validate_staging(cursor)
        inserted = promote_to_fact(cursor)
        conn.commit()

        logger.info(f"SUCCESS -- Loaded {inserted} product predictions into gold.")

    except Exception:
        conn.rollback()
        logger.exception("FAILED -- Transaction rolled back.")
        raise

    finally:
        cursor.close()
        conn.close()


if __name__ == "__main__":
    main()