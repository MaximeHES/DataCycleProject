from src.logger import Logger


def test_logger_creates_log_file(tmp_path):
    log_file = tmp_path / "app.log"

    logger = Logger(
        log_file_path=log_file,
        app_name="test_app",
        environment="test",
        version="1.0"
    )

    logger.log_message("hello test")

    assert log_file.exists()
    content = log_file.read_text(encoding="utf-8")
    assert "hello test" in content
