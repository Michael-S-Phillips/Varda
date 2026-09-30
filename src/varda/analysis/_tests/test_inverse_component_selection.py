"""Inverse Transform can rebuild from any subset of components, not just the
first N — e.g. dropping MNF 1 (albedo) or keeping a middle range."""

import numpy as np

from varda.analysis.linear_algebra import (
    describeComponentSelection,
    inverseTransform,
    pca,
)
from varda.analysis.transforms import (
    InverseOutput,
    InverseTransformAnalysis,
    PcaAnalysis,
)
from varda.common.entities import VardaRaster
from varda.image_loading.data_sources.array_data_source import ArrayDataSource


def _planted(seed=0, rows=20, cols=30, bands=8, latent=3):
    rng = np.random.default_rng(seed)
    sources = rng.normal(size=(rows * cols, latent)) * np.array([3.0, 2.0, 1.0])
    return (sources @ rng.normal(size=(latent, bands))).reshape(rows, cols, bands)


def _pcaResult() -> tuple[VardaRaster, VardaRaster]:
    image = VardaRaster(ArrayDataSource(_planted()), name="scene")
    analysis = PcaAnalysis()
    analysis.components.set(8)
    return image, analysis.run(image, lambda p, m: None)


def test_inverse_transform_accepts_an_explicit_component_subset():
    X = _planted().reshape(-1, 8)
    result = pca(X, 8)

    rebuilt = inverseTransform(result.scores, result.inverse, result.mean, [1, 2])

    expected = result.scores[:, [1, 2]] @ result.inverse[[1, 2]] + result.mean
    np.testing.assert_allclose(rebuilt, expected)


def test_describe_component_selection():
    assert describeComponentSelection([0, 1, 2]) == "3 components"
    assert describeComponentSelection([1, 2, 3, 4]) == "components 2-5"
    assert describeComponentSelection([0, 2, 3, 5]) == "components 1, 3-4, 6"
    assert describeComponentSelection([4]) == "component 5"


def test_preparing_offers_every_component_with_the_first_n_ticked():
    _, pcaImage = _pcaResult()
    analysis = InverseTransformAnalysis()

    analysis.prepareFor(pcaImage)

    assert analysis.keep.choices == pcaImage.bandNames
    assert analysis.keep.get() == pcaImage.bandNames[: analysis.components.get()]


def test_changing_the_count_reselects_the_first_n():
    _, pcaImage = _pcaResult()
    analysis = InverseTransformAnalysis()
    analysis.prepareFor(pcaImage)

    analysis.components.set(2)

    assert analysis.keep.get() == pcaImage.bandNames[:2]


def test_inverse_uses_only_the_ticked_components():
    _, pcaImage = _pcaResult()
    analysis = InverseTransformAnalysis()
    analysis.prepareFor(pcaImage)
    analysis.keep.set(pcaImage.bandNames[1:3])  # drop component 1

    result = analysis.run(pcaImage, lambda p, m: None)

    info = pcaImage.extraMetadata["transform"]
    scores = np.asarray(pcaImage.getData(), dtype=np.float64).reshape(-1, 8)
    expected = inverseTransform(
        scores, np.asarray(info["inverse"]), np.asarray(info["mean"]), [1, 2]
    ).reshape(20, 30, 8)
    np.testing.assert_allclose(result.getData(), expected, rtol=1e-5, atol=1e-6)
    assert result.name == "scene PCA inverse (components 2-3)"


def test_first_components_output_keeps_the_ticked_ones():
    _, pcaImage = _pcaResult()
    analysis = InverseTransformAnalysis()
    analysis.prepareFor(pcaImage)
    analysis.keep.set([pcaImage.bandNames[1], pcaImage.bandNames[3]])
    analysis.output.set(InverseOutput.FIRST_COMPONENTS)

    result = analysis.run(pcaImage, lambda p, m: None)

    assert result.bandNames == [pcaImage.bandNames[1], pcaImage.bandNames[3]]
    assert result.name == "scene PCA (components 2, 4)"
    np.testing.assert_array_equal(
        result.getData(), pcaImage.getData()[:, :, [1, 3]].astype(np.float32)
    )
    kept = result.extraMetadata["transform"]
    assert np.asarray(kept["inverse"]).shape == (2, 8)


def test_nothing_ticked_is_refused_with_a_reason():
    _, pcaImage = _pcaResult()
    analysis = InverseTransformAnalysis()
    analysis.prepareFor(pcaImage)
    analysis.keep.set([])

    assert "component" in analysis.unavailableReason(pcaImage).lower()
