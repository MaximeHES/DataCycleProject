"""
Merges all Product_History CSV files into Product_History_Merged.csv.
Only keeps machine_id, timestamp, prod_type columns.
- First run  : creates the merged file from scratch
- Next runs  : appends only NEW rows (no duplicates)
"""

import pandas as pd
import os
import gc
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

# -- PATHS ---------------------------------------------------
SOURCE_FOLDER = r"C:\RawData\Eversys_Cleaned\Product_History"
OUTPUT_FILE   = r"C:\DataCycle\ml\data\merged\Product_History_Merged.csv"
MAX_WORKERS   = 32
BATCH_SIZE    = 15_000   # files per batch -- lower = less RAM, slightly slower
# ------------------------------------------------------------

KEY_COLS = ["machine_id", "timestamp", "prod_type"]


def load_existing_keys(output_file):
    """
    Load existing (machine_id, timestamp, prod_type) as a set.
    Returns empty set if merged file doesn't exist yet (first run).
    """
    if not os.path.exists(output_file):
        print("    No existing merged file -- first run, starting fresh.")
        return set()

    print("    Loading existing keys from merged file...")
    existing_keys = set()

    for chunk in pd.read_csv(output_file, usecols=KEY_COLS, chunksize=100_000, dtype=str):
        chunk = chunk.dropna()
        existing_keys.update(zip(chunk["machine_id"], chunk["timestamp"], chunk["prod_type"]))

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
    """Read one file -- only 3 columns. Returns DataFrame or None on error."""
    try:
        return pd.read_csv(filepath, usecols=KEY_COLS, dtype=str, low_memory=False)
    except Exception:
        return None


def read_batch_parallel(batch, max_workers):
    """Read a batch of files in parallel. Returns combined DataFrame."""
    all_dfs = []

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(read_single_file, f): f for f in batch}
        for future in as_completed(futures):
            result = future.result()
            if result is not None:
                all_dfs.append(result)

    if not all_dfs:
        return pd.DataFrame(columns=KEY_COLS)

    combined = pd.concat(all_dfs, ignore_index=True)
    combined = combined.dropna(subset=KEY_COLS)
    combined = combined.drop_duplicates(subset=KEY_COLS)
    return combined


# ------------------------------------------------------------
# MAIN
# ------------------------------------------------------------
if __name__ == "__main__":

    start_time = datetime.now()

    print("=" * 55)
    print("  PRODUCT HISTORY -- MERGE & DEDUPLICATE")
    print("=" * 55)
    print(f"\n  Source     : {SOURCE_FOLDER}")
    print(f"  Output     : {OUTPUT_FILE}")
    print(f"  Columns    : {KEY_COLS}")
    print(f"  Batch size : {BATCH_SIZE:,} files\n")

    # Step 1 -- Load existing keys
    print("[1] Checking existing merged file...")
    existing_keys = load_existing_keys(OUTPUT_FILE)

    # Step 2 -- Find all source files
    print(f"\n[2] Scanning source folder...")
    source_files = collect_source_files(SOURCE_FOLDER)
    total_files  = len(source_files)
    print(f"    Found {total_files:,} CSV files")

    if not source_files:
        print("\n    No CSV files found. Check SOURCE_FOLDER path.")
        exit()

    # Step 3 -- Process files in batches
    print(f"\n[3] Processing files in batches of {BATCH_SIZE:,}...")

    total_new    = 0
    files_done   = 0
    write_header = not os.path.exists(OUTPUT_FILE)
    batches      = [source_files[i:i + BATCH_SIZE] for i in range(0, total_files, BATCH_SIZE)]

    for batch_num, batch in enumerate(batches, 1):
        # Read batch in parallel
        batch_df = read_batch_parallel(batch, MAX_WORKERS)

        # Filter out already known rows
        if not batch_df.empty:
            batch_df["_key"] = list(zip(
                batch_df["machine_id"],
                batch_df["timestamp"],
                batch_df["prod_type"]
            ))
            new_rows = batch_df[~batch_df["_key"].isin(existing_keys)][KEY_COLS]

            if not new_rows.empty:
                # Update known keys
                existing_keys.update(zip(
                    new_rows["machine_id"],
                    new_rows["timestamp"],
                    new_rows["prod_type"]
                ))
                # Write to merged file
                new_rows.to_csv(OUTPUT_FILE, mode="a", header=write_header, index=False)
                write_header = False
                total_new += len(new_rows)

        # Discard batch from memory
        del batch_df
        gc.collect()

        files_done += len(batch)
        print(f"    Batch {batch_num}/{len(batches)} -- {files_done:,}/{total_files:,} files -- {total_new:,} new rows so far")

    # Step 4 -- Summary
    elapsed = round((datetime.now() - start_time).total_seconds(), 1)
    print(f"\n[4] Summary")
    print("=" * 55)
    print(f"    New rows added   : {total_new:,}")
    print(f"    Total keys known : {len(existing_keys):,}")
    print(f"    Output file      : {OUTPUT_FILE}")
    print(f"    Time elapsed     : {elapsed}s")
    print("=" * 55)