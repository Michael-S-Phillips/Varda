"""Exporting a spectral plot for publication (PNG, SVG, PDF) or as data (CSV)."""

import csv

import numpy as np
import pyqtgraph as pg
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


def _data_rows(path) -> list[list[str]]:
    return [r for r in csv.reader(path.open()) if not r[0].startswith("#")]


def test_csv_writes_a_scaled_curves_own_values_and_records_its_scale(plot, tmp_path):
    library = plot.addReferenceSpectrum("library", X * 1000, 0.2 + 0.1 * X)
    assert library.config.scale.value != 1.0  # overlaid on the last curve
    path = exportPlot(plot, tmp_path / "spectra.csv")
    comments = [line for line in path.read_text().splitlines() if line[0] == "#"]
    assert any(
        "library" in line
        and f"scale={library.config.scale.value:.10g}" in line
        and f"offset={library.config.offset.value:.10g}" in line
        for line in comments
    )
    rows = _data_rows(path)
    assert rows[0] == ["wavelength_um", "pixel A", "pixel B", "library"]
    assert float(rows[1][3]) == pytest.approx(0.2 + 0.1 * X[0])


def test_csv_has_no_comments_when_nothing_is_scaled(plot, tmp_path):
    text = exportPlot(plot, tmp_path / "spectra.csv").read_text()
    assert "#" not in text


def test_csv_writes_the_spread_and_n_behind_a_mean(qtbot, tmp_path):
    widget = VardaPlotWidget()
    qtbot.addWidget(widget)
    mean, std, n = np.sin(X), np.full(X.size, 0.1), np.full(X.size, 9)
    n[0] = 8
    widget.plotWithFill(
        X,
        mean,
        mean - std,
        mean + std,
        pg.mkBrush("#80808080"),
        name="box",
        std=std,
        count=n,
    )
    widget.plot(X, np.cos(X), name="pixel")
    rows = list(csv.reader(exportPlot(widget, tmp_path / "s.csv").open()))
    assert rows[0] == ["x", "box", "box std", "box n", "pixel"]
    assert [float(v) for v in rows[1][2:4]] == [0.1, 8]


def test_long_csv_writes_the_spread_and_n_too(qtbot, tmp_path):
    widget = VardaPlotWidget()
    qtbot.addWidget(widget)
    std, n = np.full(X.size, 0.1), np.full(X.size, 9)
    widget.plotWithFill(
        X, X, X - std, X + std, pg.mkBrush("#80808080"), name="a", std=std, count=n
    )
    widget.plot(X[::2], X[::2], name="b")
    rows = list(csv.reader(exportPlot(widget, tmp_path / "s.csv").open()))
    assert rows[0] == ["curve", "x", "y", "std", "n"]
    assert rows[1][3:] == ["0.1", "9"]
    assert rows[-1][3:] == ["", ""]
