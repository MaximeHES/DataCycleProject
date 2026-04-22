from pathlib import Path
import subprocess
import pandas as pd


def test_silver_product_format():
    project_root = Path(__file__).resolve().parents[2]

    input_file = project_root / "tests" / "sample_data" / "raw" / "product" / "2023-01-06_01_20_00-Product_History.dat"
    output_dir = project_root / "tests" / "output"
    output_dir.mkdir(parents=True, exist_ok=True)

    output_file = output_dir / "2023-01-06_01_20_00-Product_History_CLEANED.csv"

    if output_file.exists():
        output_file.unlink()

    silver_script = project_root / "Silver" / "silver_cleaner.py"

    result = subprocess.run(
        [
            "python",
            str(silver_script),
            "--input",
            str(input_file),
            "--output",
            str(output_dir)
        ],
        capture_output=True,
        text=True
    )

    assert result.returncode == 0, (
        f"Silver script failed.\n"
        f"STDOUT:\n{result.stdout}\n"
        f"STDERR:\n{result.stderr}"
    )

    assert output_file.exists(), "Expected cleaned CSV was not created."

    df = pd.read_csv(output_file)

    assert not df.empty, "Generated cleaned CSV is empty."

    required_columns = [
        "machine_id",
        "timestamp",
        "source_file",
        "file_timestamp"
    ]

    for col in required_columns:
        assert col in df.columns, f"Missing required column: {col}"

    ts = pd.to_datetime(df["timestamp"], errors="coerce")
    assert ts.notna().all(), "Some timestamps are invalid."

    important_columns = [
        "machine_id",
        "timestamp",
        "source_file"
    ]

    for col in important_columns:
        assert df[col].notna().all(), f"Column {col} contains null values."
