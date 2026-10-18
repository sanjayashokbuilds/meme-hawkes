"""Checks for the fading-background models."""

import numpy as np
import pytest

from meme_hawkes import fading, hawkes
from meme_hawkes import multivariate as mv

TIMES = np.array([0.5, 0.9, 1.0, 2.7, 3.1, 6.0])
T = 8.0


def test_log_likelihood_matches_brute_force():
    mu0, mu1, gamma, alpha, beta = 0.2, 1.5, 0.4, 0.6, 1.5

    def lam(t):
        past = TIMES[TIMES < t]
        return mu0 + mu1 * np.exp(-gamma * t) + alpha * np.exp(-beta * (t - past)).sum()

    grid = np.linspace(0, T, 200_001)
    brute = sum(np.log(lam(t)) for t in TIMES) - np.trapezoid([lam(t) for t in grid], grid)
    assert fading.log_likelihood(TIMES, T, mu0, mu1, gamma, alpha, beta) == pytest.approx(brute, rel=1e-4)


def test_no_fading_reduces_to_the_constant_model():
    # mu1 = 0: the background is just mu0, as in Stage 3.
    assert fading.log_likelihood(TIMES, T, 0.4, 0.0, 1.0, 0.6, 1.5) == pytest.approx(
        hawkes.log_likelihood(TIMES, T, 0.4, 0.6, 1.5))


def test_two_type_version_reduces_to_stage_4_model():
    types = np.array([0, 1, 0, 0, 1, 1])
    mu, alpha = np.array([0.3, 0.2]), np.array([[0.4, 0.1], [0.7, 0.3]])
    assert fading.log_likelihood_2(TIMES, types, T, mu, np.zeros(2), 1.0, alpha, 1.5) == pytest.approx(
        mv.log_likelihood(TIMES, types, T, mu, alpha, 1.5))


def test_fading_fit_recovers_n_where_constant_fit_is_fooled():
    # A launch burst that fades (half-life ~70 s) plus moderate self-excitation, n = 0.4.
    rng = np.random.default_rng(21)
    times = fading.simulate(0.05, 3.0, 0.01, 0.8, 2.0, 3000, rng)
    constant = hawkes.fit(times, 3000)
    fades = fading.fit(times, 3000)
    assert fades["n"] == pytest.approx(0.4, abs=0.1)
    assert constant["n"] > fades["n"] + 0.15       # the constant model mistakes the burst for excitation
    assert fading.goodness_of_fit(times, fades) > 0.05
