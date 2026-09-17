"""Choosing how many components to keep after the fact, ENVI-style: forward
transforms keep everything and carry what an inverse needs; the Inverse
Transform step shows the eigenvalues and rebuilds the image from the first N."""

import numpy as np
import pytest

from varda.analysis.eigenvalue_plot import EigenvaluePlot
from varda.analysis.linear_algebra import (
    fastIca,
    inverseTransform,
    mnf,
    noiseCovariance,
    pca,
    suggestedComponents,
)
from varda.analysis.transforms import (
    InverseTransformAnalysis,
    InverseOutput,
    IcaAnalysis,
    MnfAnalysis,
    PcaAnalysis,
)
from varda.common.entities import VardaRaster
from varda.image_loading.data_sources.array_data_source import ArrayDataSource


def _planted(seed=0, rows=20, cols=30, bands=8, latent=3, noise=0.01):
    rng = np.random.default_rng(seed)
    sources = rng.normal(size=(rows * cols, latent)) * np.array([3.0, 2.0, 1.0])
    mixing = rng.normal(size=(latent, bands))
    cube = (sources @ mixing + noise * rng.normal(size=(rows * cols, bands))).reshape(
        rows, cols, bands
    )
    return cube


def _image(cube) -> VardaRaster:
    cube = cube.copy()
    cube[0, 0, :] = -1.0  # a nodata pixel
    return VardaRaster(
        ArrayDataSource(
            cube,
            wavelengths=np.linspace(1000.0, 2600.0, cube.shape[2]),
            wavelengthUnits="nm",
            bandNames=[f"b{i}" for i in range(cube.shape[2])],
            nodata=-1.0,
        ),
        name="scene",
    )


# --- linear algebra -------------------------------------------------------


def test_pca_result_carries_mean_eigenvalues_and_an_exact_inverse():
    X = _planted().reshape(-1, 8)
    result = pca(X, 8)

    np.testing.assert_allclose(result.mean, X.mean(axis=0))
    assert result.eigenvalues.shape == (8,)
    assert np.all(np.diff(result.eigenvalues) <= 0)  # descending
    np.testing.assert_allclose(
        inverseTransform(result.scores, result.inverse, result.mean, 8), X, atol=1e-8
    )


def test_truncated_inverse_reconstructs_within_the_planted_noise():
    X = _planted(noise=0.01).reshape(-1, 8)
    result = pca(X, 8)

    rebuilt = inverseTransform(result.scores, result.inverse, result.mean, 3)

    assert np.abs(rebuilt - X).max() < 0.1  # noise-level residual, not structure


def test_mnf_inverse_reconstructs_the_data():
    cube = _planted()
    X = cube.reshape(-1, 8)
    valid = np.ones(cube.shape[:2], dtype=bool)
    result = mnf(X, noiseCovariance(cube, valid), 8)

    np.testing.assert_allclose(
        inverseTransform(result.scores, result.inverse, result.mean, 8), X, atol=1e-6
    )


def test_ica_inverse_reconstructs_the_data():
    X = _planted(noise=0.0).reshape(-1, 8)
    result = fastIca(X, 3)

    np.testing.assert_allclose(
        inverseTransform(result.scores, result.inverse, result.mean, 3), X, atol=1e-6
    )


def test_suggested_components():
    # MNF eigenvalues are SNR + 1: components near 1 are noise
    assert suggestedComponents(np.array([50.0, 20.0, 5.0, 1.5, 1.1, 1.0]), "MNF") == 3
    # PCA/ICA: enough components for 99% of the variance
    assert suggestedComponents(np.array([0.7, 0.2, 0.08, 0.015, 0.005]), "PCA") == 4
    assert suggestedComponents(np.array([1.0]), "PCA") == 1


# --- forward analyses -------------------------------------------------------


@pytest.mark.parametrize("analysisClass", [PcaAnalysis, MnfAnalysis, IcaAnalysis])
def test_forward_transforms_default_to_every_component_once_prepared(analysisClass):
    image = _image(_planted())
    analysis = analysisClass()

    analysis.prepareFor(image)

    assert analysis.components.range == (1, image.bandCount)
    assert analysis.components.get() == image.bandCount


def test_forward_result_carries_what_the_inverse_needs():
    image = _image(_planted())
    analysis = PcaAnalysis()
    analysis.components.set(5)

    result = analysis.run(image, lambda p, m: None)

    transform = result.extraMetadata["transform"]
    assert transform["kind"] == "PCA"
    assert transform["sourceName"] == "scene"
    assert len(transform["mean"]) == 8
    assert np.asarray(transform["inverse"]).shape == (5, 8)
    assert len(transform["eigenvalues"]) == 5
    assert transform["sourceWavelengthUnits"] == "nm"
    assert transform["sourceBandNames"] == image.bandNames
    assert len(transform["sourceWavelengths"]) == 8


# --- inverse analysis -------------------------------------------------------


def _pcaResult(components=8) -> tuple[VardaRaster, VardaRaster]:
    image = _image(_planted())
    analysis = PcaAnalysis()
    analysis.components.set(components)
    return image, analysis.run(image, lambda p, m: None)


def test_inverse_is_filed_under_transforms_and_refuses_ordinary_images():
    assert InverseTransformAnalysis.category == "Transforms"
    image = _image(_planted())
    reason = InverseTransformAnalysis().unavailableReason(image)
    assert "PCA" in reason and "MNF" in reason
    with pytest.raises(ValueError, match="PCA"):
        InverseTransformAnalysis().run(image, lambda p, m: None)


def test_preparing_for_a_transform_result_ranges_and_suggests_the_components():
    _, pcaImage = _pcaResult()
    analysis = InverseTransformAnalysis()

    analysis.prepareFor(pcaImage)

    assert analysis.unavailableReason(pcaImage) == ""
    assert analysis.components.range == (1, 8)
    assert analysis.components.get() == suggestedComponents(
        np.asarray(pcaImage.extraMetadata["transform"]["eigenvalues"]), "PCA"
    )


def test_inverse_rebuilds_a_denoised_image_in_the_source_bands():
    image, pcaImage = _pcaResult()
    analysis = InverseTransformAnalysis()
    analysis.prepareFor(pcaImage)
    analysis.components.set(3)

    result = analysis.run(pcaImage, lambda p, m: None)

    assert result.name == "scene PCA inverse (3 components)"
    assert result.bandCount == 8
    np.testing.assert_allclose(result.wavelengths, image.wavelengths)
    assert result.wavelengthUnits == "nm"
    assert result.bandNames == image.bandNames
    data = result.getData()
    assert np.isnan(data[0, 0]).all()
    assert np.abs(data[1:] - image.getData()[1:]).max() < 0.1


def test_inverse_can_instead_keep_only_the_first_components():
    _, pcaImage = _pcaResult()
    analysis = InverseTransformAnalysis()
    analysis.prepareFor(pcaImage)
    analysis.components.set(3)
    analysis.output.set(InverseOutput.FIRST_COMPONENTS)

    result = analysis.run(pcaImage, lambda p, m: None)

    assert result.name == "scene PCA (3 components)"
    assert result.bandCount == 3
    assert result.bandNames == pcaImage.bandNames[:3]
    # still invertible later
    assert np.asarray(result.extraMetadata["transform"]["inverse"]).shape == (3, 8)


def test_preview_is_an_eigenvalue_plot_whose_cutoff_tracks_the_components(qtbot):
    _, pcaImage = _pcaResult()
    analysis = InverseTransformAnalysis()
    analysis.prepareFor(pcaImage)

    plot = analysis.createPreviewWidget(pcaImage)
    qtbot.addWidget(plot)

    assert isinstance(plot, EigenvaluePlot)
    assert plot.cutoff.value() == analysis.components.get()
    analysis.components.set(2)
    assert plot.cutoff.value() == 2
    plot.cutoff.setValue(4.4)  # dragging the line picks the nearest count
    assert analysis.components.get() == 4


def test_ordinary_analyses_have_no_preview():
    image = _image(_planted())
    assert PcaAnalysis().createPreviewWidget(image) is None
