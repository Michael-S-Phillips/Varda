"""Deprecations name their version, and Varda's tests refuse to use them."""

import warnings

import pytest

from varda.common.deprecation import VardaDeprecationWarning, warnDeprecated
from varda.utilities.debug import generate_random_image


def _old() -> None:
    warnDeprecated("_old()", since="0.3.1", instead="_new()")


def test_the_warning_names_the_version_and_the_replacement():
    with pytest.warns(
        VardaDeprecationWarning, match=r"since Varda 0\.3\.1.*use _new\(\)"
    ):
        _old()


def test_the_warning_blames_the_caller():
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        _old()
    assert caught[0].filename == __file__


def test_varda_tests_fail_on_deprecated_calls():
    with pytest.raises(VardaDeprecationWarning):
        _old()


def test_the_raster_property_is_deprecated():
    image = generate_random_image((10, 10, 10))
    with pytest.warns(VardaDeprecationWarning, match="VardaRaster.raster"):
        assert image.raster.shape == (10, 10, 10)
