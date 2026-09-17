"""The analyses Varda offers."""

from varda.analysis.analysis import Analysis
from varda.analysis.band_parameters import BandParametersAnalysis
from varda.analysis.derivatives import (
    SpatialGradientAnalysis,
    SpectralDerivativeAnalysis,
    SpectralSlopeAnalysis,
)
from varda.analysis.statistics import SpatialEntropyAnalysis, SpectralEntropyAnalysis
from varda.analysis.transforms import IcaAnalysis, MnfAnalysis, PcaAnalysis

# Menu order: categories appear in first-appearance order, entries in list order.
ANALYSES: list[type[Analysis]] = [
    BandParametersAnalysis,
    PcaAnalysis,
    MnfAnalysis,
    IcaAnalysis,
    SpectralEntropyAnalysis,
    SpatialEntropyAnalysis,
    SpectralDerivativeAnalysis,
    SpectralSlopeAnalysis,
    SpatialGradientAnalysis,
]


def availableAnalyses() -> list[type[Analysis]]:
    """Registered analyses whose optional dependencies are present."""
    return [analysis for analysis in ANALYSES if analysis.isAvailable()]
