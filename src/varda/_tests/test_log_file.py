"""Full logging must actually write to the log file it creates."""

import logging

from varda import log


def test_full_logging_writes_records_to_the_new_log_file(tmp_path):
    root = logging.getLogger()
    before = list(root.handlers)
    try:
        log._initializeFullLogging(logFolder=tmp_path)
        logging.getLogger("varda.test").info("hello log file")

        (logFile,) = tmp_path.glob("Varda.*.log")
        assert "hello log file" in logFile.read_text()
    finally:
        for handler in list(root.handlers):
            if handler not in before:
                root.removeHandler(handler)
                handler.close()
        for handler in before:
            if handler not in root.handlers:
                root.addHandler(handler)
