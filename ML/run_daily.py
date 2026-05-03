"""
Daily pipeline orchestrator.
Runs every day at 02:00 via Windows Task Scheduler.
Order:
  1. merge_cleaning_history.py   (90s pause after)
  2. predict_cleaning.py         (30s pause after)
  3. load_cleaning_to_sql.py
Logs each script to its own timestamped file.
Generates a summary log on success.
Stops on failure.
"""

import subprocess
import sys
import time
import os
from datetime import datetime

# -- PATHS ---------------------------------------------------
SCRIPTS_DIR = r"C:\DataCycle\ml\scripts"
LOGS_DIR    = r"C:\DataCycle\ml\logs"
OUTPUT_DIR  = r"C:\DataCycle\ml\output"
# ------------------------------------------------------------

PIPELINE = [
    {"script": "merge_cleaning_history.py", "pause_after": 90},
    {"script": "predict_cleaning.py",        "pause_after": 30},
    {"script": "load_cleaning_to_sql.py",    "pause_after": 0},
]

LOG_PREFIX = {
    "merge_cleaning_history.py" : "merge_cleaning",
    "predict_cleaning.py"       : "predict_cleaning",
    "load_cleaning_to_sql.py"   : "load_cleaning_sql",
}


def timestamp():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def run_script(script_name, log_path):
    script_path = os.path.join(SCRIPTS_DIR, script_name)

    print(f"\n[{timestamp()}] Starting {script_name}")
    print(f"[{timestamp()}] Log -> {os.path.basename(log_path)}")
    print("-" * 55)

    try:
        with open(log_path, "w", encoding="utf-8") as log_file:
            log_file.write(f"Script  : {script_name}\n")
            log_file.write(f"Started : {timestamp()}\n")
            log_file.write("=" * 55 + "\n\n")
            log_file.flush()

            process = subprocess.Popen(
                [sys.executable, script_path],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
            )

            for line in process.stdout:
                print(line, end="")
                log_file.write(line)
                log_file.flush()

            process.wait()

            log_file.write("\n" + "=" * 55 + "\n")
            log_file.write(f"Finished  : {timestamp()}\n")
            log_file.write(f"Exit code : {process.returncode}\n")

        if process.returncode != 0:
            print(f"\n[{timestamp()}] FAILED -- {script_name} exited with code {process.returncode}")
            return False

        print(f"\n[{timestamp()}] Completed -- {script_name}")
        return True

    except Exception as e:
        print(f"\n[{timestamp()}] ERROR -- {script_name}: {e}")
        try:
            with open(log_path, "a", encoding="utf-8") as log_file:
                log_file.write(f"\nERROR: {e}\n")
        except Exception:
            pass
        return False


if __name__ == "__main__":

    run_start = datetime.now()
    date_str  = run_start.strftime("%Y-%m-%d_%H-%M")

    print("=" * 55)
    print("  DAILY PIPELINE -- START")
    print("=" * 55)
    print(f"  Started : {timestamp()}")
    print(f"  Scripts : {SCRIPTS_DIR}")
    print(f"  Logs    : {LOGS_DIR}")
    print(f"  Output  : {OUTPUT_DIR}")
    print("=" * 55)

    os.makedirs(LOGS_DIR,   exist_ok=True)
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    for i, step in enumerate(PIPELINE):
        script      = step["script"]
        pause_after = step["pause_after"]
        log_path    = os.path.join(LOGS_DIR, f"{LOG_PREFIX[script]}_{date_str}.txt")

        success = run_script(script, log_path)

        if not success:
            print(f"\n{'=' * 55}")
            print(f"  DAILY PIPELINE STOPPED")
            print(f"  Failed script : {script}")
            print(f"  Check log     : {os.path.basename(log_path)}")
            print(f"  Time elapsed  : {round((datetime.now() - run_start).total_seconds())}s")
            print(f"{'=' * 55}")
            sys.exit(1)

        if pause_after > 0 and i < len(PIPELINE) - 1:
            print(f"[{timestamp()}] Waiting {pause_after}s before next script...")
            time.sleep(pause_after)

    elapsed  = round((datetime.now() - run_start).total_seconds())
    run_end  = datetime.now()

    print(f"\n{'=' * 55}")
    print(f"  DAILY PIPELINE -- DONE")
    print(f"  Total time : {elapsed}s ({elapsed // 60}m {elapsed % 60}s)")
    print(f"  Outputs    : {OUTPUT_DIR}")
    print(f"  Logs saved : {LOGS_DIR}")
    print(f"{'=' * 55}")

    summary_path = os.path.join(LOGS_DIR, f"daily_summary_{date_str}.txt")
    with open(summary_path, "w", encoding="utf-8") as f:
        f.write("=" * 55 + "\n")
        f.write("  DAILY PIPELINE -- SUMMARY\n")
        f.write("=" * 55 + "\n\n")
        f.write(f"  Status     : SUCCESS\n")
        f.write(f"  Started    : {run_start.strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"  Finished   : {run_end.strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"  Total time : {elapsed}s ({elapsed // 60}m {elapsed % 60}s)\n\n")
        f.write("  Scripts run:\n")
        for step in PIPELINE:
            script   = step["script"]
            log_name = f"{LOG_PREFIX[script]}_{date_str}.txt"
            f.write(f"    - {script:<40} -> {log_name}\n")
        f.write(f"\n  Outputs : {OUTPUT_DIR}\n")
        f.write(f"  Logs    : {LOGS_DIR}\n")
        f.write("\n" + "=" * 55 + "\n")

    print(f"[{timestamp()}] Summary log -> {os.path.basename(summary_path)}")