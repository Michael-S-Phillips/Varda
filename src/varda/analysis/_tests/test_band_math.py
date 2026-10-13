"""Band math: an expression over bands, checked before reading, evaluated in chunks."""

import numpy as np
import pytest
from PyQt6.QtCore import QSettings

from varda.analysis import band_math
from varda.analysis.band_math import (
    BandMathAnalysis,
    BandMathHelp,
    ExpressionError,
    checkExpression,
    evaluateExpression,
)
from varda.analysis.registry import ANALYSES
from varda.common.entities import VardaRaster
from varda.image_loading.data_sources.array_data_source import ArrayDataSource

WL = np.arange(2000.0, 2401.0, 10.0)  # 41 bands, nm


def _image(units="nm", nodata=None) -> VardaRaster:
    rng = np.random.default_rng(0)
    cube = 0.2 + rng.random((30, 20, WL.size))
    if nodata is not None:
        cube[0, 0, :] = nodata
    wavelengths = WL / 1000 if units == "µm" else WL
    return VardaRaster(
        ArrayDataSource(
            cube, wavelengths=wavelengths, wavelengthUnits=units, nodata=nodata
        ),
        name="scene",
    )


def test_wavelength_and_band_number_references_resolve_to_bands():
    image = _image()
    _, refs = checkExpression("R2300 / R2205 + b1", image)
    assert refs == {"R2300": 30, "R2205": 20, "b1": 0}  # nearest band; b is 1-based


def test_references_are_checked_before_any_data_is_read():
    image = _image()
    with pytest.raises(ExpressionError, match="b99"):
        checkExpression("b99 * 2", image)
    with pytest.raises(ExpressionError, match="R5000"):
        checkExpression("R5000", image)  # far outside 2000-2400 nm
    with pytest.raises(ExpressionError, match="unknown"):
        checkExpression("foo + 1", image)
    with pytest.raises(ExpressionError, match="not allowed"):
        checkExpression("__import__('os')", image)
    no_axis = VardaRaster(ArrayDataSource(np.ones((3, 3, 4))), name="bands")
    with pytest.raises(ExpressionError, match="wavelengths"):
        checkExpression("R2300", no_axis)
    assert checkExpression("b2 - b1", no_axis)[1] == {"b2": 1, "b1": 0}


def test_the_result_matches_numpy_and_does_not_depend_on_the_unit():
    image = _image()
    cube = image.getData()
    expected = cube[:, :, 30] / cube[:, :, 20]
    result = evaluateExpression("R2300 / R2205", image)
    np.testing.assert_allclose(result, expected, rtol=1e-6)
    np.testing.assert_allclose(
        evaluateExpression("R2300 / R2205", _image("µm")), expected, rtol=1e-6
    )


def test_chunks_give_the_same_answer_as_one_pass(monkeypatch):
    image = _image()
    whole = evaluateExpression("sqrt(b5) * (b3 > 0.7)", image)
    monkeypatch.setattr(band_math, "CHUNK_ROWS", 7)
    np.testing.assert_array_equal(
        evaluateExpression("sqrt(b5) * (b3 > 0.7)", image), whole
    )


def test_where_comparisons_and_no_data():
    image = _image(nodata=-9999.0)
    result = evaluateExpression("where(b1 > 0.7, 1, 0)", image)
    assert np.isnan(result[0, 0])  # nodata in, NaN out
    assert set(np.unique(result[1:])) <= {0.0, 1.0}
    assert np.isnan(evaluateExpression("b1 / 0", image)[1, 1])  # non-finite becomes NaN


def test_the_analysis_reports_problems_before_running():
    analysis = BandMathAnalysis()
    image = _image()
    analysis.expression.set("R2300 / ")
    assert "syntax" in analysis.unavailableReason(image)
    analysis.expression.set("R2300 / R2205")
    assert analysis.unavailableReason(image) == ""
    result = analysis.run(image, lambda p, m: None)
    assert result.bandNames == ["R2300 / R2205"] and result.bandCount == 1
    assert BandMathAnalysis in ANALYSES


def test_expressions_can_be_saved_and_reused(qtbot, tmp_path):
    settings = QSettings(str(tmp_path / "varda.ini"), QSettings.Format.IniFormat)
    analysis = BandMathAnalysis()
    analysis.expression.set("R2300 / R2205")
    helpBox = BandMathHelp(analysis, _image(), settings)
    qtbot.addWidget(helpBox)
    assert "R2300 → band 31" in helpBox.referencesLabel.text()
    helpBox.saveButton.click()
    analysis.expression.set("b1")
    again = BandMathHelp(analysis, _image(), settings)
    qtbot.addWidget(again)
    again.savedBox.setCurrentText("R2300 / R2205")
    assert analysis.expression.get() == "R2300 / R2205"
