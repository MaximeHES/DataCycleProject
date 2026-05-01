"""
Loads cleaning_model.pkl and predicts hours/days until
the next cleaning cycle for each active machine.
Per-machine MAE and RMSE are pulled from the pkl (computed during training).
Active = last cleaning within the past 30 days.
Input   : Cleaning_History_Merged.csv + cleaning_model.pkl
Output  : cleaning_predictions.csv
Run AFTER train_test_cleaning.py has been executed.
"""

import pandas as pd
import numpy as np
import pickle
import os
from datetime import datetime
import warnings
warnings.filterwarnings("ignore")

# -- PATHS ---------------------------------------------------
DATA_PATH   = r"C:\DataCycle\ml\data\merged\Cleaning_History_Merged.csv"
MODEL_PATH  = r"C:\DataCycle\ml\models\cleaning_model.pkl"
OUTPUT_PATH = r"C:\DataCycle\ml\output\cleaning_predictions.csv"
# ------------------------------------------------------------

ACTIVE_DAYS_FILTER = 30  # skip machines with no cleaning in last 30 days


# ─────────────────────────────────────────────
# 1. LOAD MODEL
# ─────────────────────────────────────────────
print("=" * 55)
print("  CLEANING HISTORY -- GENERATE PREDICTIONS")
print("=" * 55)

with open(MODEL_PATH, "rb") as f:
    model_package = pickle.load(f)

model           = model_package["model"]
FEATURE_COLS    = model_package["feature_cols"]
machine_metrics = model_package["machine_metrics"]

print(f"\n[1] Model loaded")
print(f"    Trained on : {model_package['trained_on']}")
print(f"    Tested on  : {model_package['tested_on']}")
print(f"    MAE        : {model_package['mae_hours']}h  |  RMSE: {model_package['rmse_hours']}h")
print(f"    Per-machine metrics available for {len(machine_metrics)} machines")


# ─────────────────────────────────────────────
# 2. LOAD ALL DATA
# ─────────────────────────────────────────────
df = pd.read_csv(
    DATA_PATH,
    dtype={"machine_id": "int32"},
)

df["timestamp_start"] = pd.to_datetime(df["timestamp_start"], errors="coerce")
df = df.dropna(subset=["timestamp_start"])
df = df.sort_values(["machine_id", "timestamp_start"]).reset_index(drop=True)

print(f"\n[2] Data loaded")
print(f"    Rows     : {len(df):,}")
print(f"    Machines : {df['machine_id'].nunique()}")
print(f"    Period   : {df['timestamp_start'].min().date()} -> {df['timestamp_start'].max().date()}")


# ─────────────────────────────────────────────
# 3. REBUILD FEATURES (must match train_test_cleaning.py)
# ─────────────────────────────────────────────
df["next_cleaning_date"] = df.groupby("machine_id")["timestamp_start"].shift(-1)
df["hours_until_next_cleaning"] = (
    df["next_cleaning_date"] - df["timestamp_start"]
).dt.total_seconds() / 3600

df["hour_of_day"] = df["timestamp_start"].dt.hour
df["day_of_week"] = df["timestamp_start"].dt.dayofweek
df["month"]       = df["timestamp_start"].dt.month
df["is_weekend"]  = (df["day_of_week"] >= 5).astype(int)

df["rolling_avg_3"] = (
    df.groupby("machine_id")["hours_until_next_cleaning"]
    .transform(lambda x: x.shift(1).rolling(3, min_periods=1).mean())
)
df["rolling_avg_5"] = (
    df.groupby("machine_id")["hours_until_next_cleaning"]
    .transform(lambda x: x.shift(1).rolling(5, min_periods=1).mean())
)

df["cleaning_count"] = df.groupby("machine_id").cumcount()

print(f"\n[3] Features rebuilt")


# ─────────────────────────────────────────────
# 4. GET LAST ROW PER MACHINE + ACTIVITY FILTER
# ─────────────────────────────────────────────
last_rows = (
    df.sort_values("timestamp_start")
    .groupby("machine_id")
    .last()
    .reset_index()
)

latest_date = df["timestamp_start"].max()
last_rows["days_since_last_cleaning"] = (
    latest_date - last_rows["timestamp_start"]
).dt.days

active_rows = last_rows[
    last_rows["days_since_last_cleaning"] <= ACTIVE_DAYS_FILTER
].copy()

print(f"\n[4] Activity filter ({ACTIVE_DAYS_FILTER} days)")
print(f"    Total machines  : {len(last_rows)}")
print(f"    Active machines : {len(active_rows)}")
print(f"    Filtered out    : {len(last_rows) - len(active_rows)} inactive machines")


# ─────────────────────────────────────────────
# 5. PREDICT
# ─────────────────────────────────────────────
X_last = active_rows[FEATURE_COLS].fillna(-1)
predicted_hours = model.predict(X_last)
predicted_hours = np.maximum(predicted_hours, 0)

print(f"\n[5] Predictions generated for {len(active_rows)} machines")


# ─────────────────────────────────────────────
# 6. BUILD OUTPUT TABLE
# ─────────────────────────────────────────────
prediction_run_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def get_urgency(hours):
    if hours <= 24:    return "URGENT"
    elif hours <= 72:  return "SOON"
    elif hours <= 168: return "OK"
    else:              return "FINE"

predictions = pd.DataFrame({
    "machine_id"              : active_rows["machine_id"].astype(int).values,
    "last_cleaning_date"      : active_rows["timestamp_start"].dt.strftime("%Y-%m-%d %H:%M:%S").values,
    "days_since_last_cleaning": active_rows["days_since_last_cleaning"].values,
    "predicted_hours"         : predicted_hours.round(1),
    "predicted_days"          : (predicted_hours / 24).round(2),
    "next_cleaning_approx"    : (
        active_rows["timestamp_start"] +
        pd.to_timedelta(predicted_hours, unit="h")
    ).dt.strftime("%Y-%m-%d %H:%M:%S").values,
    "urgency"                 : [get_urgency(h) for h in predicted_hours],
    "prediction_run_date"     : prediction_run_date,
})

# Merge per-machine metrics from pkl
predictions = predictions.merge(
    machine_metrics[["machine_id", "machine_mae", "machine_rmse", "machine_test_rows"]],
    on="machine_id",
    how="left"
)

# Sort by predicted hours (most urgent first)
predictions = predictions.sort_values("predicted_hours").reset_index(drop=True)


# ─────────────────────────────────────────────
# 7. DISPLAY & SAVE
# ─────────────────────────────────────────────
print(f"\n[6] Predictions Table")
print("=" * 55)
print(predictions.to_string(index=False))

print(f"\n[7] Urgency Summary")
print("=" * 55)
urgency_order  = ["URGENT", "SOON", "OK", "FINE"]
urgency_labels = {
    "URGENT": "URGENT  (< 24h)",
    "SOON"  : "SOON    (< 3 days)",
    "OK"    : "OK      (< 1 week)",
    "FINE"  : "FINE    (> 1 week)",
}
for key in urgency_order:
    count = (predictions["urgency"] == key).sum()
    if count > 0:
        print(f"    {urgency_labels[key]} : {count} machines")

os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
predictions.to_csv(OUTPUT_PATH, index=False)

print(f"\n[8] Saved -> {OUTPUT_PATH}")
print(f"    Rows : {len(predictions)} active machines")
print(f"    Run  : {prediction_run_date}")
print(f"\nDone -- cleaning_predictions.csv is ready")
print("=" * 55)