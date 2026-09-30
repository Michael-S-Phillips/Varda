"""Repository-wide pytest fixtures.

The per-package ``_tests/conftest.py`` files put Qt in offscreen mode; this one
keeps the GUI tests from segfaulting.
"""

import gc

import pytest
from PyQt6.QtWidgets import QApplication


@pytest.fixture(autouse=True, scope="session")
def _freezeImportTimeHeap():
    """Park everything allocated before the first test (imported modules, Qt,
    numpy, torch) in the permanent generation so the per-test collections
    below only walk what the tests themselves create."""
    gc.collect()
    gc.freeze()
    yield
    gc.unfreeze()


@pytest.fixture(autouse=True)
def _collectQtGarbageAtASafePoint():
    """Free leaked Qt objects after each test, not in the middle of event
    dispatch.

    Widgets that a test leaves behind in reference cycles are only freed by the
    cyclic garbage collector, which otherwise runs whenever allocation counts
    happen to cross a threshold — including while Qt is delivering posted
    events to those very objects (a use-after-free segfault whose timing
    shifts with every unrelated change in what gets imported). Collecting here,
    then draining the event queue, makes each test's leftovers die at a known
    safe point.
    """
    yield
    gc.collect()
    app = QApplication.instance()
    if app is not None:
        app.processEvents()
        app.processEvents()
