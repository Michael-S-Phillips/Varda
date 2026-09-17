"""The analyses Varda offers."""

from varda.analysis.analysis import Analysis
from varda.analysis.band_parameters import BandParametersAnalysis

ANALYSES: list[type[Analysis]] = [BandParametersAnalysis]


def availableAnalyses() -> list[type[Analysis]]:
    """Registered analyses whose optional dependencies are present."""
    return [analysis for analysis in ANALYSES if analysis.isAvailable()]
