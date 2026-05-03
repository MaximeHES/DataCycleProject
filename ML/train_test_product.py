"""

Trains TWO LightGBM models to predict next 7-day product count:
  - product_model_high.pkl : high volume product types (1,2,3,5,8,10,11,12,13)
  - product_model_low.pkl  : low volume product types  (9,14,15,16,17)
Also computes per machine+product combination MAE and RMSE
from the 2022 test set, saved into the pkl for use in predictions.

Data    : Product_History_Merged.csv
Train   : 2020 - 2021
Test    : 2022
Output  : product_model_high.pkl + product_model_low.pkl
"""

import pandas as pd
import numpy as np
import pickle
import lightgbm as lgb
from sklearn.metrics import mean_absolute_error, mean_squared_error
import gc
import os
import warnings
warnings.filterwarnings("ignore")

# -- PATHS ---------------------------------------------------
DATA_PATH       = r"C:\DataCycle\ml\data\merged\Product_History_Merged.csv"
MODEL_PATH_HIGH = r"C:\DataCycle\ml\models\product_model_high.pkl"
MODEL_PATH_LOW  = r"C:\DataCycle\ml\models\product_model_low.pkl"
# ------------------------------------------------------------

EXCLUDE_TYPES  = [0, 4, 6, 7]
HIGH_VOL_TYPES = [1, 2, 3, 5, 8, 10, 11, 12, 13]
LOW_VOL_TYPES  = [9, 14, 15, 16, 17]


# ─────────────────────────────────────────────
# 1. LOAD & PARSE
# ─────────────────────────────────────────────
print("=" * 60)
print("  PRODUCT HISTORY -- TWO-TIER PREDICTION MODEL TRAINING")
print("=" * 60)

df = pd.read_csv(
    DATA_PATH,
    usecols=["machine_id", "timestamp", "prod_type"],
    dtype={"machine_id": "int32", "prod_type": "int8"},
)

df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")
df = df[~df["prod_type"].isin(EXCLUDE_TYPES)]
df = df.dropna(subset=["timestamp"])

print(f"\n[1] Data loaded")
print(f"    Rows     : {len(df):,}")
print(f"    Machines : {df['machine_id'].nunique()}")
print(f"    Period   : {df['timestamp'].min().date()} -> {df['timestamp'].max().date()}")


# ─────────────────────────────────────────────
# 2. DAILY AGGREGATION
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

print(f"\n[2] Daily aggregation")
print(f"    Total daily rows : {len(daily):,}")
print(f"    Unique combos    : {daily.groupby(['machine_id','prod_type']).ngroups}")


# ─────────────────────────────────────────────
# 3. FEATURE ENGINEERING
# ─────────────────────────────────────────────
print(f"\n[3] Engineering features...")

daily = daily.sort_values(["machine_id", "prod_type", "date"]).reset_index(drop=True)

# Target: sum of next 7 days
daily["target_7d"] = (
    daily.groupby(["machine_id", "prod_type"])["count"]
    .transform(lambda x: x.shift(-1).rolling(7, min_periods=7).sum().shift(-6))
)

# Lag features
for lag in [1, 2, 3, 7, 14]:
    daily[f"lag_{lag}"] = daily.groupby(["machine_id", "prod_type"])["count"].shift(lag)

# Rolling averages
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

# Time features
daily["day_of_week"]  = daily["date"].dt.dayofweek.astype("int8")
daily["is_weekend"]   = (daily["day_of_week"] >= 5).astype("int8")
daily["week_of_year"] = daily["date"].dt.isocalendar().week.astype("int16")
daily["month"]        = daily["date"].dt.month.astype("int8")
daily["quarter"]      = daily["date"].dt.quarter.astype("int8")

daily = daily.dropna(subset=["target_7d"])

print(f"    Rows after feature engineering : {len(daily):,}")


# ─────────────────────────────────────────────
# 4. DEFINE FEATURES
# ─────────────────────────────────────────────
FEATURE_COLS = [
    "machine_id", "prod_type",
    "lag_1", "lag_2", "lag_3", "lag_7", "lag_14",
    "rolling_7d", "rolling_14d", "rolling_30d",
    "same_day_last_week", "same_day_last_year",
    "last_7d_total", "trend",
    "day_of_week", "is_weekend",
    "week_of_year", "month", "quarter",
]

print(f"    Features used ({len(FEATURE_COLS)}) : {FEATURE_COLS}")


# ─────────────────────────────────────────────
# 5. TRAIN/TEST SPLIT
# ─────────────────────────────────────────────
train_mask = daily["date"].dt.year.isin([2020, 2021])
test_mask  = daily["date"].dt.year == 2022

print(f"\n[4] Time-based split")
print(f"    Train (2020-2021) : {train_mask.sum():,} rows")
print(f"    Test  (2022)      : {test_mask.sum():,} rows")


# ─────────────────────────────────────────────
# 6. PER-COMBO METRICS FUNCTION
# ─────────────────────────────────────────────
def compute_combo_metrics(df_test, y_pred):
    """
    Compute MAE, RMSE and test week count per machine+prod_type combo.
    Returns a DataFrame indexed by (machine_id, prod_type).
    """
    results = df_test[["machine_id", "prod_type", "target_7d"]].copy()
    results["predicted"] = y_pred
    results["abs_error"] = np.abs(results["target_7d"] - results["predicted"])
    results["sq_error"]  = (results["target_7d"] - results["predicted"]) ** 2

    combo_metrics = results.groupby(["machine_id", "prod_type"]).agg(
        combo_mae        = ("abs_error", "mean"),
        combo_rmse_sq    = ("sq_error", "mean"),
        combo_test_weeks = ("target_7d", "count"),
    ).reset_index()

    combo_metrics["combo_rmse"] = np.sqrt(combo_metrics["combo_rmse_sq"])
    combo_metrics = combo_metrics.drop(columns=["combo_rmse_sq"])
    combo_metrics["combo_mae"]  = combo_metrics["combo_mae"].round(2)
    combo_metrics["combo_rmse"] = combo_metrics["combo_rmse"].round(2)

    return combo_metrics


# ─────────────────────────────────────────────
# 7. TRAIN & EVALUATE FUNCTION
# ─────────────────────────────────────────────
def train_and_evaluate(daily, train_mask, test_mask, tier_name, prod_types):
    tier_mask       = daily["prod_type"].isin(prod_types)
    train_tier_mask = train_mask & tier_mask
    test_tier_mask  = test_mask  & tier_mask

    X_train = daily[train_tier_mask][FEATURE_COLS].fillna(0)
    y_train = daily[train_tier_mask]["target_7d"]
    X_test  = daily[test_tier_mask][FEATURE_COLS].fillna(0)
    y_test  = daily[test_tier_mask]["target_7d"]

    print(f"\n[{tier_name}] Training...")
    print(f"    Product types : {prod_types}")
    print(f"    Train rows    : {len(X_train):,}  |  Test rows : {len(X_test):,}")

    model = lgb.LGBMRegressor(
        n_estimators      = 300,
        learning_rate     = 0.05,
        max_depth         = 6,
        num_leaves        = 31,
        min_child_samples = 10,
        subsample         = 0.8,
        colsample_bytree  = 0.8,
        random_state      = 42,
        n_jobs            = 2,
        verbose           = -1,
    )

    model.fit(
        X_train, y_train,
        eval_set  = [(X_test, y_test)],
        callbacks = [
            lgb.early_stopping(50, verbose=False),
            lgb.log_evaluation(period=-1),
        ]
    )

    y_pred = np.maximum(model.predict(X_test), 0)

    # Overall tier metrics
    mae  = mean_absolute_error(y_test, y_pred)
    rmse = np.sqrt(mean_squared_error(y_test, y_pred))
    mape = np.mean(np.abs((y_test - y_pred) / y_test.clip(lower=1))) * 100

    print(f"    Done (best iteration: {model.best_iteration_})")
    print(f"\n    Tier Evaluation (2022 test data)")
    print(f"    MAE  : {mae:.1f} products/7 days")
    print(f"    RMSE : {rmse:.1f} products/7 days")
    print(f"    MAPE : {mape:.1f}%")
    print(f"    Avg actual 7-day count : {y_test.mean():.1f}")

    errors = np.abs(y_test - y_pred)
    print(f"    Within  10 products : {(errors <=  10).mean()*100:.1f}%")
    print(f"    Within  25 products : {(errors <=  25).mean()*100:.1f}%")
    print(f"    Within  50 products : {(errors <=  50).mean()*100:.1f}%")
    print(f"    Within 100 products : {(errors <= 100).mean()*100:.1f}%")

    # Per-combo metrics
    combo_metrics = compute_combo_metrics(
        daily[test_tier_mask].reset_index(drop=True),
        y_pred
    )

    print(f"\n    Per-combo metrics computed for {len(combo_metrics)} combos")
    print(f"    Combo MAE  range : {combo_metrics['combo_mae'].min():.1f} - {combo_metrics['combo_mae'].max():.1f}")
    print(f"    Combo RMSE range : {combo_metrics['combo_rmse'].min():.1f} - {combo_metrics['combo_rmse'].max():.1f}")

    # Feature importances
    importances = pd.Series(model.feature_importances_, index=FEATURE_COLS)
    importances = importances.sort_values(ascending=False)
    print(f"\n    Top Feature Importances:")
    for feat, score in importances.head(8).items():
        bar = "=" * int(score / importances.max() * 25)
        print(f"      {feat:<25} {score:>6.0f}  {bar}")

    return model, combo_metrics, round(mae, 2), round(rmse, 2), round(mape, 2)


# ─────────────────────────────────────────────
# 8. TRAIN HIGH VOLUME MODEL
# ─────────────────────────────────────────────
model_high, combo_metrics_high, mae_high, rmse_high, mape_high = train_and_evaluate(
    daily, train_mask, test_mask, "HIGH VOLUME", HIGH_VOL_TYPES
)


# ─────────────────────────────────────────────
# 9. TRAIN LOW VOLUME MODEL
# ─────────────────────────────────────────────
model_low, combo_metrics_low, mae_low, rmse_low, mape_low = train_and_evaluate(
    daily, train_mask, test_mask, "LOW VOLUME", LOW_VOL_TYPES
)


# ─────────────────────────────────────────────
# 10. SAVE MODELS TO PKL
# ─────────────────────────────────────────────
os.makedirs(os.path.dirname(MODEL_PATH_HIGH), exist_ok=True)

with open(MODEL_PATH_HIGH, "wb") as f:
    pickle.dump({
        "model"         : model_high,
        "feature_cols"  : FEATURE_COLS,
        "exclude_types" : EXCLUDE_TYPES,
        "prod_types"    : HIGH_VOL_TYPES,
        "tier"          : "high",
        "combo_metrics" : combo_metrics_high,  # per-combo MAE/RMSE
        "trained_on"    : "2020-2021",
        "tested_on"     : "2022",
        "mae"           : mae_high,
        "rmse"          : rmse_high,
        "mape_pct"      : mape_high,
        "aggregation"   : "daily",
    }, f)

with open(MODEL_PATH_LOW, "wb") as f:
    pickle.dump({
        "model"         : model_low,
        "feature_cols"  : FEATURE_COLS,
        "exclude_types" : EXCLUDE_TYPES,
        "prod_types"    : LOW_VOL_TYPES,
        "tier"          : "low",
        "combo_metrics" : combo_metrics_low,   # per-combo MAE/RMSE
        "trained_on"    : "2020-2021",
        "tested_on"     : "2022",
        "mae"           : mae_low,
        "rmse"          : rmse_low,
        "mape_pct"      : mape_low,
        "aggregation"   : "daily",
    }, f)

print(f"\n[5] Models saved")
print(f"    High : {MODEL_PATH_HIGH}")
print(f"    Low  : {MODEL_PATH_LOW}")

print(f"\n{'=' * 60}")
print(f"  FINAL SUMMARY")
print(f"{'=' * 60}")
print(f"  HIGH volume -- MAE: {mae_high}  RMSE: {rmse_high}  MAPE: {mape_high}%")
print(f"  LOW  volume -- MAE: {mae_low}  RMSE: {rmse_low}  MAPE: {mape_low}%")
print(f"\nTraining complete -- run predict_product.py to generate predictions")
print("=" * 60)