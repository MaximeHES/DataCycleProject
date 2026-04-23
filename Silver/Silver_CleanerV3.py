import argparse
import json
import re
import sys
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd


# ==============================================================
# CONFIG
# ==============================================================

BRONZE_ROOT = Path(r"C:\RawData\Eversys")
BATCH_DIR   = Path(r"C:\RawData\_state\Eversys_Ingestion\batches")
SILVER_ROOT = Path(r"C:\RawData\Eversys_Cleaned")

CATEGORY_CLEANERS: dict = {}


# ==============================================================
# CLEANER REGISTRY
# ==============================================================

def register_cleaner(category: str):
    def decorator(fn):
        CATEGORY_CLEANERS[category] = fn
        return fn
    return decorator


# ==============================================================
# HELPERS
# ==============================================================

_TS_PATTERN = re.compile(r"(\d{4}-\d{2}-\d{2})[_ ](\d{2})_(\d{2})_(\d{2})-")


def extract_file_timestamp(filename: str):
    m = _TS_PATTERN.match(filename)
    if not m:
        return None
    try:
        return datetime.strptime(
            f"{m.group(1)} {m.group(2)}:{m.group(3)}:{m.group(4)}",
            "%Y-%m-%d %H:%M:%S",
        )
    except ValueError:
        return None


def normalize_datetime_series(series: pd.Series, col_name: str = "unknown") -> pd.Series:
    """
    Supports:
      - ISO : YYYY-MM-DD HH:MM:SS
      - EU  : DD/MM/YYYY HH:MM:SS
      - US  : MM/DD/YYYY HH:MM:SS
    Returns pandas datetime dtype.
    """
    s = series.copy()
    s = s.replace("", pd.NA)
    s = s.astype("string").str.strip()

    dt_iso = pd.to_datetime(s, errors="coerce", format="%Y-%m-%d %H:%M:%S")
    dt_eu  = pd.to_datetime(s, errors="coerce", format="%d/%m/%Y %H:%M:%S")
    dt_us  = pd.to_datetime(s, errors="coerce", format="%m/%d/%Y %H:%M:%S")

    result = dt_iso.copy()
    result[result.isna()] = dt_eu[result.isna()]
    result[result.isna()] = dt_us[result.isna()]

    invalid_mask = result.isna() & s.notna()
    if invalid_mask.any():
        print(f"  [WARNING] {invalid_mask.sum()} unparseable datetime value(s) in column '{col_name}'")
        print(s[invalid_mask].head(5).to_string())

    return result


def clean_common_strings(df: pd.DataFrame) -> pd.DataFrame:
    null_map = {"": pd.NA, "nan": pd.NA, "None": pd.NA, "NULL": pd.NA, "null": pd.NA}
    for col in df.columns:
        if df[col].dtype == "object":
            df[col] = df[col].str.strip()
            df[col] = df[col].replace(null_map)
    return df


def read_bronze_csv(file_path: Path) -> pd.DataFrame:
    return pd.read_csv(
        file_path,
        sep=";",
        encoding="utf-8-sig",
        dtype=str,
        keep_default_na=False,
        engine="python",
    )


def add_metadata(df: pd.DataFrame, source_file: Path) -> pd.DataFrame:
    file_ts = extract_file_timestamp(source_file.name)
    df["source_file"] = source_file.name
    df["file_timestamp"] = file_ts.strftime("%Y-%m-%d %H:%M:%S") if file_ts else pd.NA
    df["ingestion_timestamp"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    return df


def build_silver_path(source_file: Path, category: str) -> Path:
    file_ts = extract_file_timestamp(source_file.name)
    if not file_ts:
        raise ValueError(f"Cannot parse timestamp from filename: {source_file.name}")
    target_dir = (
        SILVER_ROOT / category
        / file_ts.strftime("%Y")
        / file_ts.strftime("%m")
        / file_ts.strftime("%d")
    )
    target_dir.mkdir(parents=True, exist_ok=True)
    return target_dir / f"{source_file.stem}_CLEANED.csv"


def require_columns(df: pd.DataFrame, cols: list[str], file_path: Path) -> None:
    missing = [c for c in cols if c not in df.columns]
    if missing:
        raise ValueError(f"Missing columns {missing} in {file_path.name}")


def convert_numeric_columns(df: pd.DataFrame, numeric_cols: list[str]) -> pd.DataFrame:
    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    return df


def _print_summary_line(label: str, cleaned: int, skipped: int, errors: int) -> None:
    print(f"  {label}: cleaned={cleaned}  skipped={skipped}  errors={errors}")


# ==============================================================
# CATEGORY CLEANERS
# ==============================================================

@register_cleaner("Product_History")
def clean_product(file_path: Path) -> pd.DataFrame:
    df = read_bronze_csv(file_path)
    df.columns = df.columns.str.replace("\ufeff", "", regex=False).str.strip()
    df = clean_common_strings(df)

    require_columns(df, ["machine_id", "timestamp", "prod_type"], file_path)

    df["timestamp"] = normalize_datetime_series(df["timestamp"], "timestamp")

    numeric_cols = [
        "machine_id", "press_before", "press_after", "press_final",
        "grind_time", "ext_time", "water_qnty", "water_temp", "prod_type",
        "double_prod", "bean_hopper", "outlet_side", "stopped",
        "milk_temp", "steam_pressure", "grind_adjust_left", "grind_adjust_right",
        "milk_time", "boiler_temp",
    ]
    df = convert_numeric_columns(df, numeric_cols)
    df = df.drop_duplicates()

    if {"water_qnty", "press_before", "press_after"}.issubset(df.columns):
        df["is_coffee_extraction"] = np.where(
            (df["water_qnty"].fillna(0) > 0)
            & ((df["press_before"].fillna(0) > 0) | (df["press_after"].fillna(0) > 0)),
            1, 0,
        )

    if {"milk_temp", "steam_pressure"}.issubset(df.columns):
        df["is_milk_event"] = np.where(
            (df["milk_temp"].fillna(0) > 0) | (df["steam_pressure"].fillna(0) > 0),
            1, 0,
        )

    return add_metadata(df, file_path)


@register_cleaner("Cleaning_History")
def clean_cleaning(file_path: Path) -> pd.DataFrame:
    df = read_bronze_csv(file_path)
    df.columns = df.columns.str.replace("\ufeff", "", regex=False).str.strip()

    for col in df.columns:
        df[col] = df[col].astype(str).str.strip().str.strip('"')

    df = clean_common_strings(df)

    require_columns(df, ["machine_id", "timestamp_end"], file_path)

    if "timestamp_start" in df.columns:
        df["timestamp_start"] = normalize_datetime_series(df["timestamp_start"], "timestamp_start")

    df["timestamp_end"] = normalize_datetime_series(df["timestamp_end"], "timestamp_end")

    composite_cols = [
        "milk_clean_temp_left", "milk_clean_temp_right",
        "milk_clean_rpm_left", "milk_clean_rpm_right",
        "milk_seq_cycle_left", "milk_seq_cycle_right",
    ]
    df = df.drop(columns=[c for c in composite_cols if c in df.columns])

    numeric_cols = [
        "machine_id", "cleaning_id", "powder_qty", "milk_clean_temp",
        "milk_clean_time", "detergent_qty", "water_qty", "error_code",
        "cleaning_status", "cleaning_type", "milk_system",
        "milk_seq_cycle_left_1", "milk_seq_cycle_left_2",
        "milk_seq_cycle_right_1", "milk_seq_cycle_right_2",
        "milk_temp_left_1", "milk_temp_left_2",
        "milk_temp_right_1", "milk_temp_right_2",
        "milk_rpm_left_1", "milk_rpm_left_2",
        "milk_rpm_right_1", "milk_rpm_right_2",
    ]
    df = convert_numeric_columns(df, numeric_cols)
    df = df.drop_duplicates()

    return add_metadata(df, file_path)


@register_cleaner("Rinse_History")
def clean_rinse(file_path: Path) -> pd.DataFrame:
    df = read_bronze_csv(file_path)
    df.columns = df.columns.str.replace("\ufeff", "", regex=False).str.strip()
    df = clean_common_strings(df)

    require_columns(df, ["machine_id", "timestamp", "rinse_type"], file_path)

    df["timestamp"] = normalize_datetime_series(df["timestamp"], "timestamp")

    numeric_cols = [
        "machine_id", "rinse_type",
        "flow_rate_left", "flow_rate_right",
        "status_left", "status_right",
        "pump_pressure", "nozzle_flow_rate_left", "nozzle_flow_rate_right",
        "nozzle_status_left", "nozzle_status_right",
    ]
    df = convert_numeric_columns(df, numeric_cols)

    sentinel_cols = [
        "flow_rate_left", "flow_rate_right",
        "nozzle_flow_rate_left", "nozzle_flow_rate_right",
    ]
    for col in sentinel_cols:
        if col in df.columns:
            df[col] = df[col].replace(65535, pd.NA)

    df = df.drop_duplicates()

    left_active = df["flow_rate_left"].fillna(0) > 0 if "flow_rate_left" in df.columns else pd.Series(False, index=df.index)
    right_active = df["flow_rate_right"].fillna(0) > 0 if "flow_rate_right" in df.columns else pd.Series(False, index=df.index)

    df["side_active"] = np.select(
        [left_active & right_active, left_active & ~right_active, ~left_active & right_active],
        ["both", "left", "right"],
        default="none",
    )

    return add_metadata(df, file_path)


@register_cleaner("Info_Message_History")
def clean_info_message(file_path: Path) -> pd.DataFrame:
    df = read_bronze_csv(file_path)
    df.columns = df.columns.str.replace("\ufeff", "", regex=False).str.strip()
    df = clean_common_strings(df)

    require_columns(df, ["machine_id", "timestamp", "number"], file_path)

    df["timestamp"] = normalize_datetime_series(df["timestamp"], "timestamp")

    if "machine_id" in df.columns:
        df["machine_id"] = pd.to_numeric(df["machine_id"], errors="coerce")
    if "type_number" in df.columns:
        df["type_number"] = pd.to_numeric(df["type_number"], errors="coerce")

    df = df.drop_duplicates()

    if "number" in df.columns:
        extracted = df["number"].astype("string").str.extract(r"([A-Za-z]+)-?(\d+)?")
        df["message_prefix"] = extracted[0].replace("nan", pd.NA)
        df["message_code"] = pd.to_numeric(extracted[1], errors="coerce")

    return add_metadata(df, file_path)


# ==============================================================
# MODE 1 — FULL SCAN
# Walks all 4 bronze category folders directly.
# Use this after wiping Eversys_Cleaned to rebuild from scratch.
# ==============================================================

def run_full_scan(dry_run: bool = False) -> dict:
    totals = {"total": 0, "cleaned": 0, "skipped": 0, "errors": 0}

    for category, cleaner in CATEGORY_CLEANERS.items():
        bronze_dir = BRONZE_ROOT / category
        if not bronze_dir.exists():
            print(f"\n[WARN] Bronze dir not found, skipping: {bronze_dir}")
            continue

        files = sorted(bronze_dir.glob("*.dat"))
        print(f"\n[{category}] {len(files)} bronze file(s) found")

        cat_cleaned = cat_skipped = cat_errors = 0

        for file_path in files:
            totals["total"] += 1
            try:
                silver_path = build_silver_path(file_path, category)

                if silver_path.exists():
                    cat_skipped += 1
                    continue

                if dry_run:
                    print(f"  [DRY-RUN] {file_path.name} -> {silver_path}")
                    cat_cleaned += 1
                    continue

                df = cleaner(file_path)
                df.to_csv(silver_path, index=False)
                print(f"  [OK] {file_path.name}")
                cat_cleaned += 1

            except Exception as e:
                cat_errors += 1
                print(f"  [ERROR] {file_path.name} | {e}")

        _print_summary_line(category, cat_cleaned, cat_skipped, cat_errors)
        totals["cleaned"] += cat_cleaned
        totals["skipped"] += cat_skipped
        totals["errors"] += cat_errors

    return totals


# ==============================================================
# MODE 2 — INCREMENTAL (batch-driven)
# Reads batch JSON files written by the bronze PS1 script.
# Marks each batch .done when all files are processed without error.
# This is the normal day-to-day mode after a full scan has run.
# ==============================================================

def find_pending_batches() -> list[Path]:
    if not BATCH_DIR.exists():
        return []
    all_batches = sorted(BATCH_DIR.glob("batch_*.json"))
    return [b for b in all_batches if not b.with_suffix(".json.done").exists()]


def load_batch(batch_path: Path) -> list[dict]:
    with open(batch_path, encoding="utf-8-sig") as f:
        payload = json.load(f)
    return payload.get("files", [])


def mark_batch_done(batch_path: Path) -> None:
    batch_path.rename(batch_path.with_suffix(".json.done"))


def process_batch(batch_path: Path, dry_run: bool = False) -> dict:
    print(f"\nProcessing batch: {batch_path.name}")

    entries = load_batch(batch_path)
    summary = {"total": len(entries), "cleaned": 0, "skipped": 0, "errors": 0, "unknown_category": 0}

    if not entries:
        print("  Empty batch — marking done")
        if not dry_run:
            mark_batch_done(batch_path)
        return summary

    print(f"  {len(entries)} file(s)")

    by_cat: dict[str, list[dict]] = {}
    for entry in entries:
        by_cat.setdefault(entry.get("category", ""), []).append(entry)

    for cat, cat_entries in by_cat.items():
        cleaner = CATEGORY_CLEANERS.get(cat)
        if cleaner is None:
            print(f"  [WARN] No cleaner registered for category '{cat}' — skipping {len(cat_entries)} file(s)")
            summary["unknown_category"] += len(cat_entries)
            continue

        cat_cleaned = cat_skipped = cat_errors = 0

        for entry in cat_entries:
            bronze_path = Path(entry["bronze_path"])
            try:
                silver_path = build_silver_path(bronze_path, cat)

                if silver_path.exists():
                    cat_skipped += 1
                    continue

                if dry_run:
                    print(f"  [DRY-RUN] {bronze_path.name} -> {silver_path}")
                    cat_cleaned += 1
                    continue

                if not bronze_path.exists():
                    raise FileNotFoundError(f"Bronze file missing: {bronze_path}")

                df = cleaner(bronze_path)
                df.to_csv(silver_path, index=False)
                print(f"  [OK] {bronze_path.name}")
                cat_cleaned += 1

            except Exception as e:
                cat_errors += 1
                print(f"  [ERROR] {bronze_path.name} | {e}")

        _print_summary_line(cat, cat_cleaned, cat_skipped, cat_errors)
        summary["cleaned"] += cat_cleaned
        summary["skipped"] += cat_skipped
        summary["errors"] += cat_errors

    if not dry_run:
        if summary["errors"] == 0:
            mark_batch_done(batch_path)
            print("  Batch marked done.")
        else:
            print(f"  Batch NOT marked done ({summary['errors']} error(s) — fix and re-run)")

    return summary


def run_incremental(dry_run: bool = False) -> dict:
    pending = find_pending_batches()
    print(f"Pending batches: {len(pending)}")

    if not pending:
        print("Nothing to do.")
        return {"total": 0, "cleaned": 0, "skipped": 0, "errors": 0}

    totals = {"total": 0, "cleaned": 0, "skipped": 0, "errors": 0}
    for batch in pending:
        summary = process_batch(batch, dry_run=dry_run)
        for k in totals:
            totals[k] += summary.get(k, 0)

    return totals


# ==============================================================
# MODE 3 — SINGLE FILE TEST
# Runs one cleaner on one input file and writes output to a custom
# directory. This is meant for CI/integration testing.
# ==============================================================

def run_single_file_test(test_file: Path, category: str, test_output_dir: Path) -> dict:
    if category not in CATEGORY_CLEANERS:
        raise ValueError(f"Unknown category: {category}")

    cleaner = CATEGORY_CLEANERS[category]

    if not test_file.exists():
        raise FileNotFoundError(f"Test input file not found: {test_file}")

    test_output_dir.mkdir(parents=True, exist_ok=True)
    output_file = test_output_dir / f"{test_file.stem}_CLEANED.csv"

    df = cleaner(test_file)
    df.to_csv(output_file, index=False)

    print(f"[OK] Test cleaned file created: {output_file}")

    return {
        "total": 1,
        "cleaned": 1,
        "skipped": 0,
        "errors": 0,
        "output_file": str(output_file),
    }


# ==============================================================
# MAIN
# ==============================================================

def main():
    parser = argparse.ArgumentParser(
        description=(
            "Eversys Silver Cleaner V3\n\n"
            "Modes:\n"
            "  --mode full         Walk all bronze folders directly. Use after wiping Eversys_Cleaned.\n"
            "  --mode incremental  Process pending batch JSON files only (default day-to-day mode).\n"
            "  --test-file         Process one specific file for CI/integration testing.\n"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--mode",
        choices=["full", "incremental"],
        default="incremental",
        help="'full' = scan all bronze folders  |  'incremental' = process pending batches (default)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be processed without writing any files",
    )
    parser.add_argument(
        "--test-file",
        type=Path,
        help="Run cleaner on one specific input file (for CI/integration testing)",
    )
    parser.add_argument(
        "--test-category",
        choices=list(CATEGORY_CLEANERS.keys()),
        help="Category of the test file (required with --test-file)",
    )
    parser.add_argument(
        "--test-output-dir",
        type=Path,
        help="Output directory for test mode (required with --test-file)",
    )

    args = parser.parse_args()

    # ----------------------------------------------------------
    # TEST MODE
    # ----------------------------------------------------------
    if args.test_file:
        if not args.test_category or not args.test_output_dir:
            parser.error("--test-file requires --test-category and --test-output-dir")

        print("=" * 56)
        print("SILVER CLEANER V3 - TEST MODE")
        print(f"  Test file   : {args.test_file}")
        print(f"  Category    : {args.test_category}")
        print(f"  Output dir  : {args.test_output_dir}")
        print("=" * 56)

        try:
            totals = run_single_file_test(
                test_file=args.test_file,
                category=args.test_category,
                test_output_dir=args.test_output_dir,
            )
        except Exception as e:
            print(f"[ERROR] Test mode failed: {e}")
            sys.exit(1)

        print()
        print("=" * 56)
        print("FINISHED")
        print(f"  Total   : {totals['total']}")
        print(f"  Cleaned : {totals['cleaned']}")
        print(f"  Skipped : {totals['skipped']}")
        print(f"  Errors  : {totals['errors']}")
        print("=" * 56)
        return

    # ----------------------------------------------------------
    # NORMAL MODES
    # ----------------------------------------------------------
    print("=" * 56)
    print("SILVER CLEANER V3")
    print(f"  Mode    : {args.mode.upper()}")
    print(f"  Dry-run : {args.dry_run}")
    print(f"  Bronze  : {BRONZE_ROOT}")
    print(f"  Silver  : {SILVER_ROOT}")
    if args.mode == "incremental":
        print(f"  Batches : {BATCH_DIR}")
    print("=" * 56)

    if args.mode == "full":
        totals = run_full_scan(dry_run=args.dry_run)
    else:
        totals = run_incremental(dry_run=args.dry_run)

    print()
    print("=" * 56)
    print("FINISHED")
    print(f"  Total   : {totals['total']}")
    print(f"  Cleaned : {totals['cleaned']}")
    print(f"  Skipped : {totals['skipped']}")
    print(f"  Errors  : {totals['errors']}")
    print("=" * 56)

    if totals["errors"] > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()