"""Prepare: pick the wavelength window with a range slider."""

import pytest

from synthetic_scene import WAVELENGTHS, syntheticScene
from varda.workspaces.spectral_hourglass.hourglass_model import HourglassModel
from varda.workspaces.spectral_hourglass.pipeline_panel import PreparePage


@pytest.fixture
def page(qtbot):
    image, _ = syntheticScene()
    widget = PreparePage(HourglassModel(image), run=lambda settings=None: None)
    qtbot.addWidget(widget)
    return widget


def test_a_micrometre_image_keeps_its_own_unit_on_the_slider(qtbot):
    image, _ = syntheticScene(units="µm")
    widget = PreparePage(HourglassModel(image), run=lambda settings=None: None)
    qtbot.addWidget(widget)
    lo, hi = widget.rangeSlider.value()
    assert (lo, hi) == pytest.approx(
        (WAVELENGTHS.min() / 1000, WAVELENGTHS.max() / 1000)
    )
    assert "µm" in widget.bandCountLabel.text()


def test_the_slider_spans_the_image_and_starts_at_full_range(page):
    lo, hi = page.rangeSlider.value()
    assert lo == pytest.approx(WAVELENGTHS.min()) and hi == pytest.approx(
        WAVELENGTHS.max()
    )
    assert "80 of 80 bands" in page.bandCountLabel.text()
    page.runButton.click()
    assert page.model.settings.wavelengthRange is None  # full range: no limit


def test_narrowing_the_slider_limits_the_bands(page):
    page.setWavelengthRange(1200.0, 2400.0)
    kept = int(((WAVELENGTHS >= 1200.0) & (WAVELENGTHS <= 2400.0)).sum())
    assert f"{kept} of 80 bands" in page.bandCountLabel.text()
    assert "nm" in page.bandCountLabel.text()
    page.runButton.click()
    assert page.model.settings.wavelengthRange == pytest.approx(
        (1200.0, 2400.0), abs=1.0
    )


def test_the_summary_shows_what_iovf_replaced(qtbot):
    image, _ = syntheticScene()
    model = HourglassModel(image)
    model.settings.useIovf = True
    model.applyPrepared(model.prepareTask()(lambda p, m: None))
    widget = PreparePage(model, run=lambda settings=None: None)
    qtbot.addWidget(widget)
    widget.refresh()
    assert model.prepared is not None
    record = model.prepared.iovf
    assert record is not None
    text = widget.summary.text()
    assert f"IOVF replaced {record['replacedTotal']:,} values" in text
    assert f"in {record['rounds']} round" in text
