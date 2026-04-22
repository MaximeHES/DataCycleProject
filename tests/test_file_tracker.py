from src.file_tracker import FileTracker
from src.logger import Logger


def make_logger(tmp_path):
    return Logger(
        log_file_path=tmp_path / "test.log",
        app_name="test_app",
        environment="test",
        version="1.0"
    )


def test_tracking_file_created_with_defaults(tmp_path):
    tracking_file = tmp_path / "tracking.json"
    logger = make_logger(tmp_path)

    tracker = FileTracker(str(tracking_file), logger)
    data = tracker.load_tracking()

    assert tracking_file.exists()
    assert "Product_History" in data
    assert "Info_Message_History" in data
    assert "Cleaning_History" in data
    assert "Rinse_History" in data
