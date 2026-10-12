"""The redraw busy indicator and the busy dialog built on it."""

import pytest
from PyQt6.QtGui import QColor, QImage, QPainter

from varda.branding.loader import (
    BusyDialog,
    RedrawSpinner,
    loadLoaderSpec,
    paintRedraw,
    visibleInterval,
)

SPEC = loadLoaderSpec()


def test_the_stroke_draws_on_then_undraws_from_its_start():
    period = SPEC["period"]
    assert visibleInterval(0.0, period) == (0.0, 0.0)
    start, end = visibleInterval(period / 4, period)  # halfway through drawing on
    assert start == 0.0 and end == pytest.approx(0.5, abs=1e-6)
    assert visibleInterval(period / 2 - 1e-9, period)[1] == pytest.approx(1.0, abs=1e-6)
    start, end = visibleInterval(3 * period / 4, period)  # halfway through undrawing
    assert start == pytest.approx(0.5, abs=1e-6) and end == 1.0
    assert visibleInterval(period, period) == visibleInterval(0.0, period)


def _paint(size: int, t: float) -> QImage:
    image = QImage(size, size, QImage.Format.Format_ARGB32)
    image.fill(QColor(0, 0, 0, 0))
    painter = QPainter(image)
    paintRedraw(painter, SPEC, size, t, dark=True)
    painter.end()
    return image


def _inked(image: QImage) -> int:
    return sum(
        image.pixelColor(x, y).alpha() > 128
        for x in range(image.width())
        for y in range(image.height())
    )


def test_more_of_the_v_is_drawn_as_the_stroke_grows():
    period = SPEC["period"]
    early, full = _paint(64, period * 0.1), _paint(64, period * 0.49)
    assert 0 < _inked(early) < _inked(full)


def test_the_track_shows_only_above_24_px():
    blank = 0.0  # nothing of the stroke is visible at t = 0
    assert any(
        _paint(48, blank).pixelColor(x, y).alpha() > 0
        for x in range(48)
        for y in range(48)
    )
    assert not any(
        _paint(24, blank).pixelColor(x, y).alpha() > 0
        for x in range(24)
        for y in range(24)
    )


def test_the_spinner_animates_only_while_visible(qtbot):
    spinner = RedrawSpinner(32)
    qtbot.addWidget(spinner)
    assert spinner.sizeHint().width() == 32
    assert not spinner.isAnimating()
    spinner.show()
    qtbot.waitExposed(spinner)
    assert spinner.isAnimating()
    spinner.hide()
    assert not spinner.isAnimating()


def test_busy_dialog_shows_progress_only_when_it_has_a_range(qtbot):
    dialog = BusyDialog("Working…", title="Analysis")
    qtbot.addWidget(dialog)
    assert dialog.windowTitle() == "Analysis"
    assert not dialog.progressBar.isVisibleTo(dialog)  # busy, no percentage
    dialog.setValue(40)
    assert dialog.progressBar.isVisibleTo(dialog) and dialog.progressBar.value() == 40
    dialog.setLabelText("Halfway")
    assert dialog.label.text() == "Halfway"
    assert dialog.findChild(RedrawSpinner) is not None


def test_a_delayed_dialog_stays_hidden_when_the_work_finishes_first(qtbot):
    quick = BusyDialog("Loading…")
    qtbot.addWidget(quick)
    quick.showAfter(50)
    quick.close()
    qtbot.wait(120)
    assert not quick.isVisible()
    slow = BusyDialog("Loading…")
    qtbot.addWidget(slow)
    slow.showAfter(50)
    qtbot.waitUntil(slow.isVisible, timeout=1000)
