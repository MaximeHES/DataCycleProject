"""
predict_product.py
-------------------
Loads product_model_high.pkl and product_model_low.pkl,
runs predictions for active machine+product combinations
(active = last activity within 30 days of latest data date),
and combines results into one ready CSV.

Per-combo MAE and RMSE are pulled from the pkl (computed during training).

Input   : Product_History_Merged.csv + product_model_high.pkl + product_model_low.pkl
Output  : product_predictions.csv

Run AFTER train_test_product.py has been executed.
"""

import pandas as pd
import numpy as np
import pickle
import gc
import os
from datetime import datetime
import warnings
warnings.filterwarnings("ignore")

# -- PATHS ---------------------------------------------------
DATA_PATH       = r"C:\DataCycle\ml\data\merged\Product_History_Merged.csv"
MODEL_PATH_HIGH = r"C:\DataCycle\ml\models\product_model_high.pkl"
MODEL_PATH_LOW  = r"C:\DataCycle\ml\models\product_model_low.pkl"
OUTPUT_PATH     = r"C:\DataCycle\ml\output\product_predictions.csv"
# ------------------------------------------------------------

EXCLUDE_TYPES      = [0, 4, 6, 7]
ACTIVE_DAYS_FILTER = 30   # only predict combos active within last 30 days

PROD_TYPE_NAMES = {
    1: "Ristretto", 2: "Espresso", 3: "Coffee",
    5: "Americano", 8: "Hot Water", 9: "Manual Steam",
    10: "Auto Steam", 11: "Everfoam", 12: "Milk Coffee",
    13: "Cappuccino", 14: "Espresso Macchiato", 15: "Latte Macchiato",
    16: "Milk", 17: "Milk Foam"
}


# ─────────────────────────────────────────────
# 1. LOAD BOTH MODELS
# ─────────────────────────────────────────────
print("=" * 60)
print("  PRODUCT HISTORY -- GENERATE PREDICTIONS (TWO-TIER)")
print("=" * 60)

with open(MODEL_PATH_HIGH, "rb") as f:
    pkg_high = pickle.load(f)

with open(MODEL_PATH_LOW, "rb") as f:
    pkg_low = pickle.load(f)

FEATURE_COLS = pkg_high["feature_cols"]

print(f"\n[1] Models loaded")
print(f"    HIGH tier -- types: {pkg_high['prod_types']}")
print(f"                 MAE: {pkg_high['mae']}  RMSE: {pkg_high['rmse']}  MAPE: {pkg_high['mape_pct']}%")
print(f"    LOW  tier -- types: {pkg_low['prod_types']}")
print(f"                 MAE: {pkg_low['mae']}  RMSE: {pkg_low['rmse']}  MAPE: {pkg_low['mape_pct']}%")


# ─────────────────────────────────────────────
# 2. LOAD ALL DATA
# ─────────────────────────────────────────────
df = pd.read_csv(
    DATA_PATH,
    usecols=["machine_id", "timestamp", "prod_type"],
    dtype={"machine_id": "int32", "prod_type": "int8"},
)

df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")
df = df[~df["prod_type"].isin(EXCLUDE_TYPES)]
df = df.dropna(subset=["timestamp"])

print(f"\n[2] Data loaded")
print(f"    Rows     : {len(df):,}")
print(f"    Machines : {df['machine_id'].nunique()}")
print(f"    Period   : {df['timestamp'].min().date()} -> {df['timestamp'].max().date()}")


# ─────────────────────────────────────────────
# 3. DAILY AGGREGATION
# ─────────────────────────────────────────────
df["date"] = df["timestamp"].dt.normalize()

daily = (
    df.groupby(["machine_id", "prod_type", "date"])
    .size()
    .reset_index(name="count")
    .sort_values(["machine_id", "prod_type", "date"])
    .reset_index(drop=True)
)

del df
gc.collect()

daily["machine_id"] = daily["machine_id"].astype("int32")
daily["prod_type"]  = daily["prod_type"].astype("int8")
daily["count"]      = daily["count"].astype("int32")

print(f"\n[3] Daily aggregation done -- {len(daily):,} rows")


# ─────────────────────────────────────────────
# 4. FEATURE ENGINEERING
# ─────────────────────────────────────────────
daily = daily.sort_values(["machine_id", "prod_type", "date"]).reset_index(drop=True)

for lag in [1, 2, 3, 7, 14]:
    daily[f"lag_{lag}"] = daily.groupby(["machine_id", "prod_type"])["count"].shift(lag)

daily["rolling_7d"]  = daily.groupby(["machine_id", "prod_type"])["count"].transform(
    lambda x: x.shift(1).rolling(7,  min_periods=1).mean()
)
daily["rolling_14d"] = daily.groupby(["machine_id", "prod_type"])["count"].transform(
    lambda x: x.shift(1).rolling(14, min_periods=1).mean()
)
daily["rolling_30d"] = daily.groupby(["machine_id", "prod_type"])["count"].transform(
    lambda x: x.shift(1).rolling(30, min_periods=1).mean()
)

daily["same_day_last_week"] = daily.groupby(["machine_id", "prod_type"])["count"].shift(7)
daily["same_day_last_year"] = daily.groupby(["machine_id", "prod_type"])["count"].shift(365)

daily["last_7d_total"] = daily.groupby(["machine_id", "prod_type"])["count"].transform(
    lambda x: x.shift(1).rolling(7, min_periods=1).sum()
)

daily["trend"] = daily["lag_1"] - daily["rolling_7d"]

daily["day_of_week"]  = daily["date"].dt.dayofweek.astype("int8")
daily["is_weekend"]   = (daily["day_of_week"] >= 5).astype("int8")
daily["week_of_year"] = daily["date"].dt.isocalendar().week.astype("int16")
daily["month"]        = daily["date"].dt.month.astype("int8")
daily["quarter"]      = daily["date"].dt.quarter.astype("int8")

print(f"\n[4] Features rebuilt")


# ─────────────────────────────────────────────
# 5. GET LAST KNOWN DAY PER COMBINATION
# ─────────────────────────────────────────────
last_rows = (
    daily.sort_values("date")
    .groupby(["machine_id", "prod_type"])
    .last()
    .reset_index()
)

# Apply 30-day activity filter
latest_date = daily["date"].max()
last_rows["days_since_active"] = (latest_date - last_rows["date"]).dt.days
active_rows = last_rows[last_rows["days_since_active"] <= ACTIVE_DAYS_FILTER].copy()

# ─────────────────────────────────────────────
# 5b. CALCULATE LAST 7 DAYS ACTUAL COUNT
# ─────────────────────────────────────────────
# For each active combo, sum actual product counts
# from the last 7 days of available data
cutoff_date = latest_date - pd.Timedelta(days=7)

last_7d_actual = (
    daily[daily["date"] > cutoff_date]
    .groupby(["machine_id", "prod_type"])["count"]
    .sum()
    .reset_index()
    .rename(columns={"count": "last_7d_actual"})
)

active_rows = active_rows.merge(
    last_7d_actual,
    on=["machine_id", "prod_type"],
    how="left"
)
# Fill 0 for combos with no activity in last 7 days
active_rows["last_7d_actual"] = active_rows["last_7d_actual"].fillna(0).astype(int)

print(f"\n[5] Activity filter ({ACTIVE_DAYS_FILTER} days)")
print(f"    Total combos      : {len(last_rows)}")
print(f"    Active combos     : {len(active_rows)}")
print(f"    Filtered out      : {len(last_rows) - len(active_rows)} inactive combos")
print(f"    Last 7d actual    : calculated from {cutoff_date.date()} -> {latest_date.date()}")


# ─────────────────────────────────────────────
# 6. PREDICT WITH EACH MODEL & COMBINE
# ─────────────────────────────────────────────
prediction_run_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
all_predictions = []

for pkg, tier_label in [(pkg_high, "HIGH"), (pkg_low, "LOW")]:
    tier_rows = active_rows[active_rows["prod_type"].isin(pkg["prod_types"])].copy()

    if tier_rows.empty:
        continue

    X     = tier_rows[FEATURE_COLS].fillna(0)
    preds = np.maximum(pkg["model"].predict(X), 0)

    next_week_start = (tier_rows["date"] + pd.Timedelta(days=1)).dt.strftime("%Y-%m-%d")
    next_week_end   = (tier_rows["date"] + pd.Timedelta(days=7)).dt.strftime("%Y-%m-%d")

    # Merge per-combo metrics from pkl
    combo_metrics = pkg["combo_metrics"]
    tier_rows = tier_rows.merge(
        combo_metrics[["machine_id", "prod_type", "combo_mae", "combo_rmse", "combo_test_weeks"]],
        on=["machine_id", "prod_type"],
        how="left"
    )

    all_predictions.append(pd.DataFrame({
        "machine_id"          : tier_rows["machine_id"].astype(int).values,
        "prod_type"           : tier_rows["prod_type"].astype(int).values,
        "prod_type_name"      : tier_rows["prod_type"].astype(int).map(PROD_TYPE_NAMES).values,
        "tier"                : tier_label,
        "week_start"          : next_week_start.values,
        "week_end"            : next_week_end.values,
        "predicted_count"     : preds.round(0).astype(int),
        "last_7d_actual"      : tier_rows["last_7d_actual"].values,
        "days_since_active"   : tier_rows["days_since_active"].values,
        "combo_mae"           : tier_rows["combo_mae"].round(2).values,
        "combo_rmse"          : tier_rows["combo_rmse"].round(2).values,
        "combo_test_weeks"    : tier_rows["combo_test_weeks"].fillna(0).astype(int).values,
        "prediction_run_date" : prediction_run_date,
    }))

    print(f"\n[6] {tier_label} tier -- {len(tier_rows)} active predictions generated")


# ─────────────────────────────────────────────
# 7. COMBINE & SAVE
# ─────────────────────────────────────────────
predictions = (
    pd.concat(all_predictions, ignore_index=True)
    .sort_values(["machine_id", "prod_type"])
    .reset_index(drop=True)
)

print(f"\n[7] Combined predictions table")
print("=" * 60)
print(predictions.to_string(index=False))

print(f"\n[8] Summary per product type")
print("=" * 60)
summary = (
    predictions.groupby(["prod_type", "prod_type_name", "tier"])
    .agg(
        machines     = ("machine_id", "count"),
        total_pred   = ("predicted_count", "sum"),
        avg_per_mach = ("predicted_count", "mean"),
        avg_combo_mae= ("combo_mae", "mean"),
    )
    .round(1)
    .reset_index()
)
print(summary.to_string(index=False))

os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
predictions.to_csv(OUTPUT_PATH, index=False)

print(f"\n[9] Saved -> {OUTPUT_PATH}")
print(f"    Rows : {len(predictions)} active combos (filtered from 322 total)")
print(f"    Run  : {prediction_run_date}")
print(f"\nDone -- product_predictions.csv is ready")
print("=" * 60)