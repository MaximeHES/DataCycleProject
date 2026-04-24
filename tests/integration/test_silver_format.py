from pathlib import Path
import subprocess
import pandas as pd
import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SILVER_SCRIPT = PROJECT_ROOT / "Silver" / "Silver_CleanerV3.py"
OUTPUT_DIR = PROJECT_ROOT / "tests" / "output"


TEST_CASES = [
    {
        "name": "product",
        "input_file": PROJECT_ROOT / "tests/sample_data/raw/product/2022-05-15_08_35_00-Product_History.dat",
        "category": "Product_History",
        "timestamp_columns": ["timestamp"],
        "required_columns": [
            "machine_id",
            "timestamp",
            "prod_type",
            "source_file",
            "file_timestamp",
            "ingestion_timestamp",
        ],
        "not_null_columns": [
            "machine_id",
            "timestamp",
            "prod_type",
            "source_file",
        ],
    },
    {
        "name": "cleaning",
        "input_file": PROJECT_ROOT / "tests/sample_data/raw/cleaning/2022-01-08_20_20_00-Cleaning_History.dat",
        "category": "Cleaning_History",
        "timestamp_columns": ["timestamp_end"],
        "required_columns": [
            "machine_id",
            "timestamp_end",
            "source_file",
            "file_timestamp",
            "ingestion_timestamp",
        ],
        "not_null_columns": [
            "machine_id",
            "timestamp_end",
            "source_file",
        ],
    },
    {
        "name": "rinse",
        "input_file": PROJECT_ROOT / "tests/sample_data/raw/rinse/2021-07-07_12_45_00-Rinse_History.dat",
        "category": "Rinse_History",
        "timestamp_columns": ["timestamp"],
        "required_columns": [
            "machine_id",
            "timestamp",
            "rinse_type",
            "source_file",
            "file_timestamp",
            "ingestion_timestamp",
        ],
        "not_null_columns": [
            "machine_id",
            "timestamp",
            "rinse_type",
            "source_file",
        ],
    },
    {
        "name": "info_message",
        "input_file": PROJECT_ROOT / "tests/sample_data/raw/info_message/2023-04-15_19_45_00-Info_Message_History.dat",
        "category": "Info_Message_History",
        "timestamp_columns": ["timestamp"],
        "required_columns": [
            "machine_id",
            "timestamp",
            "number",
            "message_prefix",
            "message_code",
            "source_file",
            "file_timestamp",
            "ingestion_timestamp",
        ],
        "not_null_columns": [
            "machine_id",
            "timestamp",
            "number",
            "source_file",
        ],
    },
]


@pytest.mark.parametrize("case", TEST_CASES, ids=[c["name"] for c in TEST_CASES])
def test_silver_format(case):
    input_file = case["input_file"]
    output_file = OUTPUT_DIR / f"{input_file.stem}_CLEANED.csv"

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    if output_file.exists():
        output_file.unlink()

    result = subprocess.run(
        [
            "python",
            str(SILVER_SCRIPT),
            "--test-file", str(input_file),
            "--test-category", case["category"],
            "--test-output-dir", str(OUTPUT_DIR),
        ],
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert output_file.exists(), f"Missing output: {output_file}"

    df = pd.read_csv(output_file)

    assert not df.empty, f"Empty output for {case['name']}"

    for col in case["required_columns"]:
        assert col in df.columns, f"{case['name']} missing column: {col}"

    for col in case["timestamp_columns"]:
        ts = pd.to_datetime(df[col], errors="coerce")
        assert ts.notna().all(), f"{case['name']} invalid timestamps in {col}"

    for col in case["not_null_columns"]:
        assert df[col].notna().all(), f"{case['name']} null values in {col}"