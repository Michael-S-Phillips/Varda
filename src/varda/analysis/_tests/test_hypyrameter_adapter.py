"""Driving HyPyRameter's parameter library on an in-memory cube (optional extra)."""

import numpy as np
import pytest

hypyrameter = pytest.importorskip("hypyrameter")

from varda.analysis.hypyrameter_adapter import (  # noqa: E402
    HYPYRAMETER_AVAILABLE,
    computeParameterCube,
    parameterDescription,
    parameterNames,
    toNanometres,
    validParameterNames,
)


def _cube():
    rng = np.random.default_rng(0)
    wavelengths = np.arange(400.0, 2601.0, 10.0)  # 221 bands, 400..2600 nm
    cube = 0.2 + 0.1 * rng.random((6, 5, wavelengths.size))
    return cube, wavelengths


def test_available_flag_is_true_when_installed():
    assert HYPYRAMETER_AVAILABLE


def test_micrometre_wavelengths_are_converted_to_nanometres():
    np.testing.assert_allclose(toNanometres([1.0, 2.5]), [1000.0, 2500.0])
    np.testing.assert_allclose(toNanometres([1000.0, 2500.0]), [1000.0, 2500.0])


def test_parameter_names_come_from_the_registry_with_descriptions():
    names = parameterNames()
    assert "R550" in names and "BD1900_2" in names and "OLINDEX3" in names
    assert len(names) == len(set(names))
    assert "1930" in parameterDescription("BD1900_2")


def test_valid_parameters_respect_the_wavelength_range():
    _data, wavelengths = _cube()
    valid = validParameterNames(wavelengths)
    assert "R550" in valid and "BD1900_2" in valid
    assert "BR3500" not in valid  # needs 3500 nm

    narrow = validParameterNames(np.arange(1000.0, 1101.0, 10.0))
    assert set(narrow) < set(valid)  # a narrow range supports strictly fewer
    assert "R1080" in narrow and "R550" not in narrow


def test_computed_parameters_match_hypyrameter_and_keep_nan_pixels():
    cube, wavelengths = _cube()
    cube[0, 0, :] = np.nan
    result = computeParameterCube(cube, wavelengths, ["R550", "BD1900_2"])

    assert result.shape == (6, 5, 2) and result.dtype == np.float32
    np.testing.assert_allclose(
        result, hypyrameter.compute(cube, wavelengths, ["R550", "BD1900_2"])
    )
    assert np.isnan(result[0, 0]).all() and np.isfinite(result[1:, 1:]).all()


def test_progress_is_reported_per_parameter_in_percent():
    cube, wavelengths = _cube()
    seen = []
    computeParameterCube(
        cube,
        wavelengths,
        ["R550", "R637"],
        reportProgress=lambda p, m: seen.append((p, m)),
    )
    assert seen == [(0, "R550"), (50, "R637"), (100, "done")]
