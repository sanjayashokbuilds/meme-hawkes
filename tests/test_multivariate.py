"""Checks that the multivariate Hawkes code matches the maths, before real data."""

import numpy as np
import pytest

from meme_hawkes import hawkes, multivariate as mv

TIMES = np.array([0.5, 0.9, 1.0, 2.7, 3.1, 6.0])
TYPES = np.array([0, 1, 0, 0, 1, 1])
MU = np.array([0.3, 0.2])
ALPHA = np.array([[0.4, 0.1], [0.7, 0.3]])  # row = excited type, column = exciting type
BETA, T = 1.5, 8.0


def brute_intensity(t, i):
    past = TIMES < t
    return MU[i] + sum(ALPHA[i, j] * np.exp(-BETA * (t - tk)) for tk, j in zip(TIMES[past], TYPES[past]))


def test_log_likelihood_matches_brute_force():
    grid = np.linspace(0, T, 200_001)
    integral = sum(np.trapezoid([brute_intensity(t, i) for t in grid], grid) for i in range(2))
    log_terms = sum(np.log(brute_intensity(t, i)) for t, i in zip(TIMES, TYPES))
    assert mv.log_likelihood(TIMES, TYPES, T, MU, ALPHA, BETA) == pytest.approx(log_terms - integral, rel=1e-4)


def test_one_type_reduces_to_the_univariate_model():
    types = np.zeros(len(TIMES), dtype=int)
    multi = mv.log_likelihood(TIMES, types, T, np.array([0.4]), np.array([[0.6]]), BETA)
    assert multi == pytest.approx(hawkes.log_likelihood(TIMES, T, 0.4, 0.6, BETA))


def test_fit_recovers_cross_excitation():
    rng = np.random.default_rng(11)
    alpha = np.array([[0.4, 0.0], [1.0, 0.6]])  # type 0 excites type 1 strongly; not the reverse
    times, types = mv.simulate([0.05, 0.1], alpha, 2.0, 4000, rng)
    est = mv.fit(times, types, 4000)
    assert est["branching"][1, 0] == pytest.approx(0.5, abs=0.12)
    assert est["branching"][0, 1] < 0.08


def test_no_cross_excitation_is_not_invented():
    rng = np.random.default_rng(12)
    alpha = np.array([[0.8, 0.0], [0.0, 0.8]])  # two independent streams
    times, types = mv.simulate([0.1, 0.1], alpha, 2.0, 4000, rng)
    est = mv.fit(times, types, 4000)
    assert est["branching"][1, 0] < 0.08 and est["branching"][0, 1] < 0.08


def test_goodness_of_fit_passes_with_the_true_model():
    rng = np.random.default_rng(13)
    alpha = np.array([[0.4, 0.0], [1.0, 0.6]])
    times, types = mv.simulate([0.05, 0.1], alpha, 2.0, 4000, rng)
    p = mv.goodness_of_fit(times, types, {"mu": np.array([0.05, 0.1]), "alpha": alpha, "beta": 2.0})
    assert min(p) > 0.05
