"""Continuous colormaps are sampled at spread-out positions, not adjacent entries."""

import matplotlib

from varda.plotting.pixel_spectra_plot import (
    CONTINUOUS_STEPS,
    ColorScheme,
    paletteColor,
)


def _rgb(color):
    return (color.r, color.g, color.b)


def test_classic_continuous_maps_are_offered():
    names = {scheme.value for scheme in ColorScheme}
    classics = {
        "viridis",
        "plasma",
        "inferno",
        "magma",
        "cividis",
        "turbo",
        "Spectral",
        "coolwarm",
    }
    assert classics <= names


def test_continuous_map_is_sampled_across_its_range_then_cycles():
    cmap = matplotlib.colormaps["viridis"]
    first = paletteColor(ColorScheme.VIRIDIS, 0)
    second = paletteColor(ColorScheme.VIRIDIS, 1)
    last = paletteColor(ColorScheme.VIRIDIS, CONTINUOUS_STEPS - 1)

    assert _rgb(first) == tuple(float(v) for v in cmap(0.0)[:3])
    assert _rgb(second) == tuple(
        float(v) for v in cmap(1.0 / (CONTINUOUS_STEPS - 1))[:3]
    )
    assert _rgb(last) == tuple(float(v) for v in cmap(1.0)[:3])
    assert paletteColor(ColorScheme.VIRIDIS, CONTINUOUS_STEPS) == first


def test_qualitative_maps_still_cycle_by_entry():
    cmap = matplotlib.colormaps["tab10"]
    assert _rgb(paletteColor(ColorScheme.TAB10, 3)) == tuple(
        float(v) for v in cmap(3)[:3]
    )
    assert paletteColor(ColorScheme.TAB10, 10) == paletteColor(ColorScheme.TAB10, 0)
