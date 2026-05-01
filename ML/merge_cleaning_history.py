"""
Merges all Cleaning_History CSV files into Cleaning_History_Merged.csv.
Only keeps machine_id + timestamp_start columns.
Uses parallel reading to open multiple files simultaneously.
- First run  : creates the merged file from scratch
- Next runs  : appends only NEW rows (no duplicates)
"""

import pandas as pd
import os
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

# -- PATHS ---------------------------------------------------
SOURCE_FOLDER = r"C:\RawData\Eversys_Cleaned\Cleaning_History"
OUTPUT_FILE   = r"C:\DataCycle\ml\data\merged\Cleaning_History_Merged.csv"
MAX_WORKERS   = 16    # number of parallel file readers — increase if CPU allows
# ------------------------------------------------------------

KEY_COLS = ["machine_id", "timestamp_start"]


def load_existing_keys(output_file):
    """
    Load existing (machine_id, timestamp_start) as a set.
    Returns empty set if merged file doesn't exist yet (first run).
    """
    if not os.path.exists(output_file):
        print("    No existing merged file -- first run, starting fresh.")
        return set()

    print("    Loading existing keys from merged file...")
    existing_keys = set()

    for chunk in pd.read_csv(output_file, usecols=KEY_COLS, chunksize=100_000, dtype=str):
        chunk = chunk.dropna()
        existing_keys.update(zip(chunk["machine_id"], chunk["timestamp_start"]))

    print(f"    Existing rows : {len(existing_keys):,}")
    return existing_keys


def collect_source_files(source_folder):
    """Walk source folder and return all .csv file paths."""
    csv_files = []
    for root, dirs, files in os.walk(source_folder):
        for file in files:
            if file.endswith(".csv"):
                csv_files.append(os.path.join(root, file))
    return sorted(csv_files)


def read_single_file(filepath):
    """Read one file — only 2 columns. Returns DataFrame or None on error."""
    try:
        return pd.read_csv(filepath, usecols=KEY_COLS, dtype=str, low_memory=False)
    except Exception:
        return None


def read_all_files_parallel(source_files, max_workers):
    """
    Read all source files in parallel using a thread pool.
    Prints progress every 1000 files so you know it's running.
    """
    all_dfs  = []
    skipped  = 0
    done     = 0
    total    = len(source_files)

    print(f"    Reading {total:,} files using {max_workers} parallel workers...")

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(read_single_file, f): f for f in source_files}

        for future in as_completed(futures):
            result = future.result()
            done += 1

            if result is not None:
                all_dfs.append(result)
            else:
                skipped += 1

            # Progress update every 1000 files
            if done % 1000 == 0 or done == total:
                print(f"    Progress: {done:,} / {total:,} files read...")

    print(f"\n    Read    : {len(all_dfs):,} files successfully")
    if skipped > 0:
        print(f"    Skipped : {skipped:,} files (unreadable)")

    return all_dfs


# ------------------------------------------------------------
# MAIN
# ------------------------------------------------------------
if __name__ == "__main__":

    start_time = datetime.now()

    print("=" * 55)
    print("  CLEANING HISTORY -- MERGE & DEDUPLICATE")
    print("=" * 55)
    print(f"\n  Source  : {SOURCE_FOLDER}")
    print(f"  Output  : {OUTPUT_FILE}")
    print(f"  Columns : {KEY_COLS}\n")

    # Step 1 -- Load existing keys
    print("[1] Checking existing merged file...")
    existing_keys = load_existing_keys(OUTPUT_FILE)

    # Step 2 -- Find all source files
    print(f"\n[2] Scanning source folder...")
    source_files = collect_source_files(SOURCE_FOLDER)
    print(f"    Found {len(source_files):,} CSV files")

    if not source_files:
        print("\n    No CSV files found. Check SOURCE_FOLDER path.")
        exit()

    # Step 3 -- Read all files in parallel
    print(f"\n[3] Reading all source files...")
    all_dfs = read_all_files_parallel(source_files, MAX_WORKERS)

    if not all_dfs:
        print("\n    No data could be read. Exiting.")
        exit()

    # Step 4 -- Combine and deduplicate in one bulk operation
    print(f"\n[4] Combining and deduplicating...")

    all_source = pd.concat(all_dfs, ignore_index=True)
    all_source = all_source.dropna(subset=KEY_COLS)
    all_source = all_source.drop_duplicates(subset=KEY_COLS)

    print(f"    Total source rows (deduplicated) : {len(all_source):,}")

    if existing_keys:
        all_source["_key"] = list(zip(all_source["machine_id"], all_source["timestamp_start"]))
        new_rows = all_source[~all_source["_key"].isin(existing_keys)][KEY_COLS]
    else:
        new_rows = all_source[KEY_COLS]

    print(f"    Already in merged file           : {len(all_source) - len(new_rows):,}")
    print(f"    New rows to add                  : {len(new_rows):,}")

    # Step 5 -- Write new rows to merged file
    print(f"\n[5] Writing to merged file...")

    if new_rows.empty:
        print("    No new rows -- merged file is already up to date.")
    else:
        write_header = not os.path.exists(OUTPUT_FILE)
        new_rows.to_csv(OUTPUT_FILE, mode="a", header=write_header, index=False)
        print(f"    Done -- {len(new_rows):,} rows written.")

    # Step 6 -- Summary
    elapsed = round((datetime.now() - start_time).total_seconds(), 1)
    print(f"\n[6] Summary")
    print("=" * 55)
    print(f"    New rows added   : {len(new_rows):,}")
    print(f"    Output file      : {OUTPUT_FILE}")
    print(f"    Time elapsed     : {elapsed}s")
    print("=" * 55)