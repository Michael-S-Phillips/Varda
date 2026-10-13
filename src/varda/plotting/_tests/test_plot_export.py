"""Exporting a spectral plot for publication (PNG, SVG, PDF) or as data (CSV)."""

import csv

import numpy as np
import pytest
from PyQt6.QtGui import QImage

from varda.common.spectral_axis import SpectralUnit
from varda.plotting import plot as plot_module
from varda.plotting.plot import VardaPlotWidget
from varda.plotting.plot_export import exportPlot

X = np.linspace(1.0, 2.5, 50)


@pytest.fixture
def plot(qtbot):
    widget = VardaPlotWidget()
    qtbot.addWidget(widget)
    widget.resize(600, 400)
    widget.setSpectralUnit(SpectralUnit.MICROMETRE)
    widget.plot(X, np.sin(X), name="pixel A")
    widget.plot(X, np.cos(X), name="pixel B")
    return widget


def test_png_is_high_resolution(plot, tmp_path):
    path = exportPlot(plot, tmp_path / "spectra.png")
    image = QImage(str(path))
    assert not image.isNull() and image.width() >= 2000


def test_svg_and_pdf_are_vector_files(plot, tmp_path):
    svg = exportPlot(plot, tmp_path / "spectra.svg")
    assert "<svg" in svg.read_text()
    pdf = exportPlot(plot, tmp_path / "spectra.pdf")
    assert pdf.read_bytes().startswith(b"%PDF") and pdf.stat().st_size > 1000


def test_csv_has_one_column_per_curve_when_they_share_wavelengths(plot, tmp_path):
    path = exportPlot(plot, tmp_path / "spectra.csv")
    rows = list(csv.reader(path.open()))
    assert rows[0] == ["wavelength_um", "pixel A", "pixel B"]
    assert len(rows) == 1 + X.size
    assert float(rows[1][2]) == pytest.approx(np.cos(X[0]))


def test_csv_is_long_when_curves_have_different_wavelengths(qtbot, tmp_path):
    widget = VardaPlotWidget()
    qtbot.addWidget(widget)
    widget.plot(X, np.sin(X), name="a")
    widget.plot(X[::2], np.cos(X[::2]), name="b")
    rows = list(csv.reader(exportPlot(widget, tmp_path / "s.csv").open()))
    assert rows[0] == ["curve", "x", "y"]
    assert len(rows) == 1 + X.size + X[::2].size


def test_an_unknown_suffix_is_rejected(plot, tmp_path):
    with pytest.raises(ValueError, match="png"):
        exportPlot(plot, tmp_path / "spectra.bmp")


def test_the_export_button_saves_with_the_chosen_format(plot, tmp_path, monkeypatch):
    target = tmp_path / "spectra"  # no suffix: taken from the chosen filter
    monkeypatch.setattr(
        plot_module.QFileDialog,
        "getSaveFileName",
        lambda *a, **k: (str(target), "CSV data (*.csv)"),
    )
    plot.exportWithDialog()
    assert (tmp_path / "spectra.csv").is_file()
