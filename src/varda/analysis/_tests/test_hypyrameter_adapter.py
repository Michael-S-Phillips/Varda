"""Driving HyPyRameter's parameter library on an in-memory cube (optional extra)."""

import numpy as np
import pytest

hypyrameter = pytest.importorskip("hypyrameter")

from hypyrameter import utils as hpu  # noqa: E402

from varda.analysis.hypyrameter_adapter import (  # noqa: E402
    HYPYRAMETER_AVAILABLE,
    computeParameterCube,
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


def test_parameter_names_are_hypyrameters_parameter_methods_only():
    names = parameterNames()
    assert "R550" in names and "BD1900_2" in names and "OLINDEX3" in names
    assert len(names) == len(set(names))
    for utility in ("run", "calculateParams", "determineValidParams", "denoiser"):
        assert utility not in names


def test_valid_parameters_respect_the_wavelength_range():
    _data, wavelengths = _cube()
    valid = validParameterNames(wavelengths)
    assert "R550" in valid and "BD1900_2" in valid
    assert "BR3500" not in valid  # needs 3500 nm

    narrow = validParameterNames(np.arange(1000.0, 1101.0, 10.0))
    assert set(narrow) < set(valid)  # a narrow range supports strictly fewer
    assert "R1080" in narrow and "R550" not in narrow


def test_computed_parameter_matches_hypyrameters_own_function():
    cube, wavelengths = _cube()
    result = computeParameterCube(cube, wavelengths, ["R550", "BD1900_2"])

    assert result.shape == (6, 5, 2)
    np.testing.assert_allclose(
        result[:, :, 0], hpu.getBand(cube, list(wavelengths), 550)
    )


def test_progress_is_reported_per_parameter():
    cube, wavelengths = _cube()
    seen = []
    computeParameterCube(
        cube,
        wavelengths,
        ["R550", "R637"],
        reportProgress=lambda p, m: seen.append((p, m)),
    )
    assert [m for _p, m in seen] == ["R550", "R637"]
    assert seen[-1][0] == 100
