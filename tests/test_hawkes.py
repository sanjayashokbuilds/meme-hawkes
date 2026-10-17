"""Checks that the Hawkes code does what the maths says, before it touches real data."""

import numpy as np
import pytest

from meme_hawkes import hawkes

TIMES = np.array([0.5, 0.9, 1.0, 2.7, 3.1, 6.0])
MU, ALPHA, BETA, T = 0.4, 0.6, 1.5, 8.0


def test_excitation_recursion_matches_brute_force():
    brute = [sum(np.exp(-BETA * (ti - tj)) for tj in TIMES[:i]) for i, ti in enumerate(TIMES)]
    assert hawkes.excitation(TIMES, BETA) == pytest.approx(brute)


def test_log_likelihood_matches_numerical_integration():
    grid = np.linspace(0, T, 400_001)
    integral = np.trapezoid(hawkes.intensity(grid, TIMES, MU, ALPHA, BETA), grid)
    at_events = hawkes.intensity(TIMES + 1e-12, TIMES, MU, ALPHA, BETA) - ALPHA  # just after -> just before
    brute = np.sum(np.log(at_events)) - integral
    assert hawkes.log_likelihood(TIMES, T, MU, ALPHA, BETA) == pytest.approx(brute, rel=1e-4)


def test_simulation_has_the_right_average_count():
    # Theory: E[N(T)] is about mu * T / (1 - n) once the process has warmed up.
    rng = np.random.default_rng(1)
    counts = [len(hawkes.simulate(1.0, 0.5, 1.0, 500, rng)) for _ in range(30)]
    assert np.mean(counts) == pytest.approx(1.0 * 500 / (1 - 0.5), rel=0.05)


def test_fit_recovers_known_parameters():
    rng = np.random.default_rng(7)
    times = hawkes.simulate(0.3, 0.6, 1.0, 3000, rng)   # n = 0.6, about 2,250 events
    est = hawkes.fit(times, 3000)
    assert est["n"] == pytest.approx(0.6, abs=0.08)
    assert est["beta"] == pytest.approx(1.0, rel=0.3)
    assert est["mu"] == pytest.approx(0.3, rel=0.25)


def test_rescaled_gaps_pass_with_true_model_and_fail_with_wrong_one():
    rng = np.random.default_rng(3)
    times = hawkes.simulate(0.3, 0.6, 1.0, 3000, rng)
    true = {"mu": 0.3, "alpha": 0.6, "beta": 1.0}
    poisson = {"mu": len(times) / 3000, "alpha": 1e-9, "beta": 1.0}  # no self-excitation
    assert hawkes.goodness_of_fit(times, true) > 0.05
    assert hawkes.goodness_of_fit(times, poisson) < 0.01  # the test can tell the difference


def test_rolling_branching_ratio_rises_when_excitation_rises():
    rng = np.random.default_rng(5)
    calm = hawkes.simulate(0.5, 0.2, 1.0, 600, rng)              # n = 0.2
    frenzy = 600 + hawkes.simulate(0.2, 0.8, 1.0, 600, rng)      # n = 0.8
    rolling = hawkes.rolling_branching_ratio(np.concatenate([calm, frenzy]), window=300, step=300)
    n = [r["n"] for r in rolling]
    assert n[0] < 0.4 and n[-1] > 0.6
