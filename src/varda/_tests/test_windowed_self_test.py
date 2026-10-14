"""The windowed Windows app has no console: the self-test writes its report
to a file, and logging doesn't try to print."""

import logging
import sys

from varda import log, main


def test_without_a_console_the_self_test_reports_to_a_file(tmp_path, monkeypatch):
    report = tmp_path / "report.txt"
    monkeypatch.setattr(sys, "argv", ["Varda", main.SELF_TEST_FLAG])
    monkeypatch.setattr(sys, "stdout", None)
    monkeypatch.setattr(sys, "stderr", None)
    monkeypatch.setenv(main.SELF_TEST_REPORT_ENV, str(report))
    main._consoleForSelfTest()
    print("PASS something")
    sys.stdout.flush()
    assert report.read_text() == "PASS something\n"


def test_with_a_console_nothing_is_redirected(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["Varda", main.SELF_TEST_FLAG])
    before = sys.stdout
    main._consoleForSelfTest()
    assert sys.stdout is before


def test_logging_needs_no_console(tmp_path, monkeypatch):
    monkeypatch.setattr(sys, "stdout", None)
    root = logging.getLogger()
    saved = root.handlers[:]
    try:
        log._initializeFullLogging(tmp_path)
        assert not any(
            type(h) is logging.StreamHandler for h in logging.getLogger().handlers
        )
    finally:
        for handler in root.handlers[:]:
            root.removeHandler(handler)
            handler.close()
        for handler in saved:
            root.addHandler(handler)
