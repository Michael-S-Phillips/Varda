"""Varda logs its own messages in detail; other libraries only their warnings."""

import importlib
import logging

import pytest

import varda.log


@pytest.fixture
def restoreLogging():
    root, ours = logging.getLogger(), logging.getLogger("varda")
    saved = (root.level, root.handlers[:], ours.level, ours.handlers[:], ours.propagate)
    yield
    for handler in ours.handlers + root.handlers:
        if handler not in saved[1] + saved[3]:
            handler.close()
    root.setLevel(saved[0])
    root.handlers[:] = saved[1]
    ours.setLevel(saved[2])
    ours.handlers[:] = saved[3]
    ours.propagate = saved[4]


def _logText(folder) -> str:
    for handler in logging.getLogger("varda").handlers:
        handler.flush()
    (logFile,) = folder.glob("Varda.*.log")
    return logFile.read_text()


def test_importing_the_module_configures_nothing(restoreLogging):
    root = logging.getLogger()
    root.handlers[:] = []
    importlib.reload(varda.log)
    assert root.handlers == []


def test_varda_messages_are_detailed_and_library_chatter_is_quiet(
    tmp_path, restoreLogging
):
    varda.log._initializeFullLogging(tmp_path)
    logging.getLogger("varda.analysis").debug("our detail")
    logging.getLogger("rasterio.env").debug("library detail")
    logging.getLogger("rasterio.env").warning("library warning")
    text = _logText(tmp_path)
    assert "our detail" in text
    assert "library detail" not in text
    assert "library warning" in text


def test_messages_from_the_entry_script_count_as_varda(tmp_path, restoreLogging):
    varda.log._initializeFullLogging(tmp_path)
    exec(  # a module named __main__, as the packaged app's entry script is
        "import varda.log\nvarda.log.info('started')",
        {"__name__": "__main__"},
    )
    assert "started" in _logText(tmp_path)
