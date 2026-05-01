"""
Trains a Random Forest Regressor to predict hours until
the next cleaning cycle per coffee machine.
Also computes per-machine MAE and RMSE from the 2022 test set,
saved into the pkl for use in predictions.

Data    : Cleaning_History_Merged.csv
Target  : hours_until_next_cleaning (regression)
Train   : 2020 - 2021
Test    : 2022
Output  : cleaning_model.pkl
"""

import pandas as pd
import numpy as np
import pickle
import os
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error
import warnings
warnings.filterwarnings("ignore")

# -- PATHS ---------------------------------------------------
DATA_PATH  = r"C:\DataCycle\ml\data\merged\Cleaning_History_Merged.csv"
MODEL_PATH = r"C:\DataCycle\ml\models\cleaning_model.pkl"
# ------------------------------------------------------------


# ─────────────────────────────────────────────
# 1. LOAD & PARSE
# ─────────────────────────────────────────────
print("=" * 55)
print("  CLEANING HISTORY -- PREDICTION MODEL TRAINING")
print("=" * 55)

df = pd.read_csv(
    DATA_PATH,
    dtype={"machine_id": "int32"},
)

df["timestamp_start"] = pd.to_datetime(df["timestamp_start"], errors="coerce")
df = df.dropna(subset=["timestamp_start"])
df = df.sort_values(["machine_id", "timestamp_start"]).reset_index(drop=True)

print(f"\n[1] Data loaded")
print(f"    Rows     : {len(df):,}")
print(f"    Machines : {df['machine_id'].nunique()}")
print(f"    Period   : {df['timestamp_start'].min().date()} -> {df['timestamp_start'].max().date()}")


# ─────────────────────────────────────────────
# 2. TARGET: hours until next cleaning
# ─────────────────────────────────────────────
df["next_cleaning_date"] = df.groupby("machine_id")["timestamp_start"].shift(-1)

df["hours_until_next_cleaning"] = (
    df["next_cleaning_date"] - df["timestamp_start"]
).dt.total_seconds() / 3600

df = df.dropna(subset=["hours_until_next_cleaning"])
df = df[df["hours_until_next_cleaning"].between(0.1, 24 * 60)]

print(f"\n[2] Target engineered")
print(f"    Rows after filter           : {len(df):,}")
print(f"    Avg hours between cleanings : {df['hours_until_next_cleaning'].mean():.1f}h")
print(f"    Min : {df['hours_until_next_cleaning'].min():.1f}h  |  Max : {df['hours_until_next_cleaning'].max():.1f}h")


# ─────────────────────────────────────────────
# 3. FEATURE ENGINEERING
# ─────────────────────────────────────────────
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

print(f"\n[3] Features engineered")


# ─────────────────────────────────────────────
# 4. DEFINE FEATURES
# ─────────────────────────────────────────────
FEATURE_COLS = [
    "machine_id",
    "hour_of_day",
    "day_of_week",
    "month",
    "is_weekend",
    "rolling_avg_3",
    "rolling_avg_5",
    "cleaning_count",
]

X = df[FEATURE_COLS].fillna(-1)
y = df["hours_until_next_cleaning"]

print(f"    Features used ({len(FEATURE_COLS)}) : {FEATURE_COLS}")


# ─────────────────────────────────────────────
# 5. TIME-BASED TRAIN / TEST SPLIT
# ─────────────────────────────────────────────
train_mask = df["timestamp_start"].dt.year.isin([2020, 2021])
test_mask  = df["timestamp_start"].dt.year == 2022

X_train, y_train = X[train_mask], y[train_mask]
X_test,  y_test  = X[test_mask],  y[test_mask]

print(f"\n[4] Time-based split")
print(f"    Train (2020-2021) : {len(X_train):,} rows")
print(f"    Test  (2022)      : {len(X_test):,} rows")
print(f"    Predict (2023+)   : used in predict_cleaning.py")


# ─────────────────────────────────────────────
# 6. TRAIN MODEL
# ─────────────────────────────────────────────
print(f"\n[5] Training model...")

model = RandomForestRegressor(
    n_estimators=200,
    max_depth=12,
    min_samples_leaf=5,
    random_state=42,
    n_jobs=-1
)

model.fit(X_train, y_train)
print(f"    Done")


# ─────────────────────────────────────────────
# 7. OVERALL EVALUATION
# ─────────────────────────────────────────────
y_pred = model.predict(X_test)

mae  = mean_absolute_error(y_test, y_pred)
rmse = np.sqrt(mean_squared_error(y_test, y_pred))
mape = np.mean(np.abs((y_test - y_pred) / y_test.clip(lower=1))) * 100

print(f"\n[6] Test Set Evaluation (2022 data)")
print("=" * 55)
print(f"    MAE  (Mean Absolute Error)     : {mae:.1f} hours  (~{mae/24:.1f} days)")
print(f"    RMSE (Root Mean Squared Error) : {rmse:.1f} hours  (~{rmse/24:.1f} days)")
print(f"    MAPE (Mean Absolute % Error)   : {mape:.1f}%")

errors = np.abs(y_test - y_pred)
print(f"\n    Accuracy buckets:")
print(f"      Within  6 hours : {(errors <=  6).mean()*100:.1f}%")
print(f"      Within 12 hours : {(errors <= 12).mean()*100:.1f}%")
print(f"      Within 24 hours : {(errors <= 24).mean()*100:.1f}%")
print(f"      Within 48 hours : {(errors <= 48).mean()*100:.1f}%")


# ─────────────────────────────────────────────
# 8. PER-MACHINE METRICS
# ─────────────────────────────────────────────
test_df = df[test_mask].copy().reset_index(drop=True)
test_df["predicted"] = y_pred
test_df["abs_error"] = np.abs(test_df["hours_until_next_cleaning"] - test_df["predicted"])
test_df["sq_error"]  = (test_df["hours_until_next_cleaning"] - test_df["predicted"]) ** 2

machine_metrics = test_df.groupby("machine_id").agg(
    machine_mae       = ("abs_error", "mean"),
    machine_rmse_sq   = ("sq_error",  "mean"),
    machine_test_rows = ("abs_error", "count"),
).reset_index()

machine_metrics["machine_rmse"] = np.sqrt(machine_metrics["machine_rmse_sq"])
machine_metrics = machine_metrics.drop(columns=["machine_rmse_sq"])
machine_metrics["machine_mae"]  = machine_metrics["machine_mae"].round(2)
machine_metrics["machine_rmse"] = machine_metrics["machine_rmse"].round(2)

print(f"\n[7] Per-machine metrics computed for {len(machine_metrics)} machines")
print(f"    Machine MAE  range : {machine_metrics['machine_mae'].min():.1f}h - {machine_metrics['machine_mae'].max():.1f}h")
print(f"    Machine RMSE range : {machine_metrics['machine_rmse'].min():.1f}h - {machine_metrics['machine_rmse'].max():.1f}h")
print(f"    Test rows range    : {machine_metrics['machine_test_rows'].min()} - {machine_metrics['machine_test_rows'].max()}")


# ─────────────────────────────────────────────
# 9. FEATURE IMPORTANCES
# ─────────────────────────────────────────────
importances = pd.Series(model.feature_importances_, index=FEATURE_COLS)
importances = importances.sort_values(ascending=False)

print(f"\n[8] Top Feature Importances")
print("=" * 55)
for feat, score in importances.items():
    bar = "=" * int(score * 100)
    print(f"    {feat:<20} {score:.4f}  {bar}")


# ─────────────────────────────────────────────
# 10. SAVE MODEL TO PKL
# ─────────────────────────────────────────────
os.makedirs(os.path.dirname(MODEL_PATH), exist_ok=True)

model_package = {
    "model"           : model,
    "feature_cols"    : FEATURE_COLS,
    "machine_metrics" : machine_metrics,  # per-machine MAE/RMSE
    "trained_on"      : "2020-2021",
    "tested_on"       : "2022",
    "mae_hours"       : round(mae, 2),
    "rmse_hours"      : round(rmse, 2),
    "mape_pct"        : round(mape, 2),
}

with open(MODEL_PATH, "wb") as f:
    pickle.dump(model_package, f)

print(f"\n[9] Model saved -> {MODEL_PATH}")
print(f"    MAE: {mae:.1f}h  |  RMSE: {rmse:.1f}h  |  MAPE: {mape:.1f}%")
print(f"\nTraining complete -- run predict_cleaning.py to generate predictions")
print("=" * 55)