from pathlib import Path
import pandas as pd


def test_product_file_exists_and_valid():
    file_path = Path("tests/sample_data/cleaned_product_sample.csv")
    assert file_path.exists()

    df = pd.read_csv(file_path)
    assert not df.empty

    required_columns = [
        "machine_id",
        "timestamp",
        "prod_type",
        "source_file",
        "file_timestamp"
    ]

    for col in required_columns:
        assert col in df.columns

    ts = pd.to_datetime(df["timestamp"], errors="coerce")
    assert ts.notna().all()

    important_columns = ["machine_id", "timestamp", "source_file"]
    for col in important_columns:
        assert df[col].notna().all()


def test_cleaning_file_exists_and_valid():
    file_path = Path("tests/sample_data/cleaned_cleaning_sample.csv")
    assert file_path.exists()

    df = pd.read_csv(file_path)
    assert not df.empty

    required_columns = [
        "machine_id",
        "timestamp_start",
        "timestamp_end",
        "source_file",
        "file_timestamp"
    ]

    for col in required_columns:
        assert col in df.columns

    start_ts = pd.to_datetime(df["timestamp_start"], errors="coerce")
    end_ts = pd.to_datetime(df["timestamp_end"], errors="coerce")

    assert start_ts.notna().all()
    assert end_ts.notna().all()

    important_columns = ["machine_id", "timestamp_start", "timestamp_end"]
    for col in important_columns:
        assert df[col].notna().all()


def test_rinse_file_exists_and_valid():
    file_path = Path("tests/sample_data/cleaned_rinse_sample.csv")
    assert file_path.exists()

    df = pd.read_csv(file_path)
    assert not df.empty

    required_columns = [
        "machine_id",
        "timestamp",
        "rinse_type",
        "source_file",
        "file_timestamp"
    ]

    for col in required_columns:
        assert col in df.columns

    ts = pd.to_datetime(df["timestamp"], errors="coerce")
    assert ts.notna().all()

    important_columns = ["machine_id", "timestamp", "rinse_type"]
    for col in important_columns:
        assert df[col].notna().all()


def test_info_message_file_exists_and_valid():
    file_path = Path("tests/sample_data/cleaned_info_message_sample.csv")
    assert file_path.exists()

    df = pd.read_csv(file_path)
    assert not df.empty

    required_columns = [
        "machine_id",
        "timestamp",
        "number",
        "typography",
        "message_code",
        "source_file",
        "file_timestamp"
    ]

    for col in required_columns:
        assert col in df.columns

    ts = pd.to_datetime(df["timestamp"], errors="coerce")
    assert ts.notna().all()

    important_columns = ["machine_id", "timestamp", "number"]
    for col in important_columns:
        assert df[col].notna().all()
