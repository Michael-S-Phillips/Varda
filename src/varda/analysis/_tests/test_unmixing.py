"""Mapping endmembers: spectral angles, linear unmixing and MTMF."""

import numpy as np
import pytest
from scipy.optimize import nnls

from varda.analysis import unmixing
from varda.analysis.unmixing import (
    Constraint,
    UnmixingReport,
    linearUnmix,
    mixtureTunedMatchedFilter,
    spectralAngles,
)


def _endmembers(bands=30):
    x = np.linspace(0, 1, bands)
    return np.stack(
        [
            0.5 + 0.0 * x,
            0.6 - 0.3 * np.exp(-0.5 * ((x - 0.3) / 0.05) ** 2),
            0.2 + 0.4 * x,
        ]
    )


def test_spectral_angle_is_zero_for_scaled_copies_and_nan_for_missing():
    E = _endmembers()
    X = np.vstack([2.0 * E[1], E[0], np.full(E.shape[1], np.nan)])
    angles = spectralAngles(X, E)
    assert angles.shape == (3, 3)
    assert angles[0, 1] == pytest.approx(0.0, abs=1e-7)
    assert angles[1, 0] == pytest.approx(0.0, abs=1e-7)
    assert angles[0, 0] > 0.05
    assert np.isnan(angles[2]).all()


def test_unconstrained_unmixing_recovers_exact_mixtures():
    E = _endmembers()
    rng = np.random.default_rng(0)
    A = rng.dirichlet(np.ones(3), size=200)
    X = A @ E
    abundances, rmse = linearUnmix(X, E, Constraint.NONE)
    np.testing.assert_allclose(abundances, A, atol=1e-8)
    assert rmse.max() < 1e-8


def test_sum_to_one_abundances_sum_to_one():
    E = _endmembers()
    rng = np.random.default_rng(1)
    X = rng.dirichlet(np.ones(3), size=100) @ E + 0.01 * rng.normal(
        size=(100, E.shape[1])
    )
    abundances, _ = linearUnmix(X, E, Constraint.SUM_TO_ONE)
    np.testing.assert_allclose(abundances.sum(axis=1), 1.0, atol=1e-9)


def test_fully_constrained_matches_nnls_with_a_heavy_sum_to_one_row():
    E = _endmembers()
    rng = np.random.default_rng(2)
    A = rng.dirichlet(np.ones(3) * 0.5, size=60)
    X = A @ E + 0.02 * rng.normal(size=(60, E.shape[1]))
    abundances, rmse = linearUnmix(X, E, Constraint.FULLY_CONSTRAINED)

    assert abundances.min() >= -1e-6
    np.testing.assert_allclose(abundances.sum(axis=1), 1.0, atol=1e-9)
    delta = 1e4
    Eaug = np.vstack([E.T, delta * np.ones(3)])
    for i in range(0, 60, 7):
        expected, _ = nnls(Eaug, np.append(X[i], delta))
        np.testing.assert_allclose(abundances[i], expected, atol=1e-4)
    assert rmse.shape == (60,)


def test_unmixing_leaves_missing_pixels_nan():
    E = _endmembers()
    X = np.vstack([E[0], np.full(E.shape[1], np.nan)])
    for constraint in Constraint:
        abundances, rmse = linearUnmix(X, E, constraint)
        assert np.isnan(abundances[1]).all() and np.isnan(rmse[1])
        assert np.isfinite(abundances[0]).all()


def test_mtmf_scores_targets_and_flags_infeasible_false_positives():
    """In noise-whitened space: background clutter, a subpixel target and a
    pixel that is bright along the target direction but off the mixing line."""
    rng = np.random.default_rng(3)
    k = 6
    background = rng.normal(size=(4000, k)) * np.array([5, 3, 2, 1, 1, 1.0])
    target = np.array([12.0, 0, 0, 8, 0, 0])
    X = background.copy()
    X[0] = 0.6 * target + 0.4 * background[0]  # 60% target
    impostor = 0.6 * target.copy()
    impostor[[4, 5]] += 25.0  # same MF direction, far off the mixing cone
    X[1] = impostor

    mf, infeasibility = mixtureTunedMatchedFilter(X, target[None, :])

    assert mf.shape == (4000, 1) and infeasibility.shape == (4000, 1)
    assert mf[0, 0] == pytest.approx(0.6, abs=0.15)
    assert abs(np.median(mf[2:, 0])) < 0.05
    assert infeasibility[1, 0] > 3 * infeasibility[0, 0]


def test_fully_constrained_is_exact_for_similar_endmembers():
    """Endmembers that differ only by weak absorptions make the problem
    ill-conditioned; the abundances must still match NNLS closely."""
    rng = np.random.default_rng(5)
    x = np.linspace(0, 1, 120)
    base = 0.3 + 0.1 * x
    E = np.stack(
        [
            base * (1 - d * np.exp(-0.5 * ((x - c) / 0.03) ** 2))
            for d, c in [(0, 0.5), (0.05, 0.3), (0.04, 0.6), (0.08, 0.45), (0.03, 0.8)]
        ]
    )
    A = rng.dirichlet(np.ones(5) * 0.5, size=300)
    X = A @ E + 0.002 * rng.normal(size=(300, x.size))
    abundances, _ = linearUnmix(X, E, Constraint.FULLY_CONSTRAINED)
    delta = 1e4
    Eaug = np.vstack([E.T, delta * np.ones(5)])
    for i in range(0, 300, 13):
        expected, _ = nnls(Eaug, np.append(X[i], delta))
        np.testing.assert_allclose(abundances[i], expected, atol=1e-3)


def _manyEndmembers(count=12, bands=60):
    x = np.linspace(0, 1, bands)
    return np.stack(
        [
            0.4 + 0.1 * x - 0.2 * np.exp(-0.5 * ((x - c) / 0.04) ** 2)
            for c in np.linspace(0.05, 0.95, count)
        ]
    )


def test_admm_unmixing_reports_how_many_pixels_converged():
    """Beyond ten endmembers FCLS is solved iteratively (ADMM): the report
    gives the solver, iterations and the share of pixels that converged."""
    E = _manyEndmembers()
    rng = np.random.default_rng(2)
    X = rng.dirichlet(np.ones(12), size=200) @ E
    X[3] = np.nan
    report = UnmixingReport()
    linearUnmix(X, E, Constraint.FULLY_CONSTRAINED, report=report)
    assert report.solver == "ADMM"
    assert report.pixels == 199
    assert report.pixelsConverged == 199 and report.fractionConverged == 1.0
    assert 1 <= report.iterations <= report.maxIterations


def test_admm_that_runs_out_of_iterations_says_so(monkeypatch):
    monkeypatch.setattr(unmixing, "_ADMM_ITERATIONS", 2)
    E = _manyEndmembers()
    rng = np.random.default_rng(2)
    X = rng.dirichlet(0.2 * np.ones(12), size=50) @ E  # abundances at 0
    X += 0.01 * rng.normal(size=X.shape)
    report = UnmixingReport()
    linearUnmix(X, E, Constraint.FULLY_CONSTRAINED, report=report)
    assert report.iterations == 2 and report.maxIterations == 2
    assert report.pixelsConverged < report.pixels == 50
    assert report.fractionConverged < 1.0


def test_few_endmembers_are_solved_exactly():
    E = _endmembers()
    X = np.random.default_rng(0).dirichlet(np.ones(3), size=20) @ E
    report = UnmixingReport()
    linearUnmix(X, E, Constraint.FULLY_CONSTRAINED, report=report)
    assert report.solver == "exact" and report.fractionConverged == 1.0
