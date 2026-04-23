from pathlib import Path
import subprocess
import pandas as pd


def test_silver_product_format():
    print("RUNNING TEST FILE:", __file__)

    project_root = Path(__file__).resolve().parents[2]

    input_file = project_root / "tests" / "sample_data" / "raw" / "product" / "2022-05-15_08_35_00-Product_History.dat"
    output_dir = project_root / "tests" / "output"
    output_file = output_dir / "2022-05-15_08_35_00-Product_History_CLEANED.csv"
    silver_script = project_root / "Silver" / "Silver_CleanerV3.py"

    # Ensure output directory exists
    output_dir.mkdir(parents=True, exist_ok=True)

    # Force deletion of previous output
    if output_file.exists():
        print("Deleting old output file...")
        output_file.unlink()

    # Run the real Silver script
    result = subprocess.run(
        [
            "python",
            str(silver_script),
            "--test-file", str(input_file),
            "--test-category", "Product_History",
            "--test-output-dir", str(output_dir),
        ],
        capture_output=True,
        text=True
    )

    print("STDOUT:\n", result.stdout)
    print("STDERR:\n", result.stderr)

    # Check script execution
    assert result.returncode == 0, "Silver script execution failed"

    # Check output file exists
    assert output_file.exists(), f"Output file not found: {output_file}"

    print(f"Reading generated file: {output_file}")

    df = pd.read_csv(output_file)

    print("GENERATED COLUMNS:", list(df.columns))

    # Check file is not empty
    assert not df.empty, "Generated file is empty"

    required_columns = [
        "machine_id",
        "timestamp",
        "source_file",
        "file_timestamp"
    ]

    for col in required_columns:
        assert col in df.columns, f"Missing required column: {col}"

    # Timestamp validation
    ts = pd.to_datetime(df["timestamp"], errors="coerce")
    assert ts.notna().all(), "Invalid timestamps found"

    # Important columns not null
    important_columns = ["timestamp", "source_file"]

    for col in important_columns:
        assert df[col].notna().all(), f"Column {col} contains null values"