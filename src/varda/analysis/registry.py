"""The analyses Varda offers."""

from varda.analysis.analysis import Analysis
from varda.analysis.band_parameters import BandParametersAnalysis
from varda.analysis.classification import (
    CnnClassificationAnalysis,
    MlpClassificationAnalysis,
    VitClassificationAnalysis,
)
from varda.analysis.continuum import ContinuumRemovalAnalysis
from varda.analysis.derivatives import (
    SpatialGradientAnalysis,
    SpectralDerivativeAnalysis,
    SpectralSlopeAnalysis,
)
from varda.analysis.filtering import IovfAnalysis
from varda.analysis.mapping import (
    MtmfAnalysis,
    PixelPurityAnalysis,
    SamMappingAnalysis,
    UnmixingAnalysis,
)
from varda.analysis.statistics import SpatialEntropyAnalysis, SpectralEntropyAnalysis
from varda.analysis.transforms import (
    IcaAnalysis,
    InverseTransformAnalysis,
    MnfAnalysis,
    PcaAnalysis,
)

# Menu order: categories appear in first-appearance order, entries in list order.
ANALYSES: list[type[Analysis]] = [
    BandParametersAnalysis,
    ContinuumRemovalAnalysis,
    IovfAnalysis,
    PcaAnalysis,
    MnfAnalysis,
    IcaAnalysis,
    InverseTransformAnalysis,
    SpectralEntropyAnalysis,
    SpatialEntropyAnalysis,
    SpectralDerivativeAnalysis,
    SpectralSlopeAnalysis,
    SpatialGradientAnalysis,
    MlpClassificationAnalysis,
    CnnClassificationAnalysis,
    VitClassificationAnalysis,
    PixelPurityAnalysis,
    SamMappingAnalysis,
    UnmixingAnalysis,
    MtmfAnalysis,
]


def availableAnalyses() -> list[type[Analysis]]:
    """Registered analyses whose optional dependencies are present."""
    return [analysis for analysis in ANALYSES if analysis.isAvailable()]
