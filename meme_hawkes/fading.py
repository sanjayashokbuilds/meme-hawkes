"""Hawkes models whose background rate fades after launch.

The Stage 4 models assume a constant background rate mu. On a new token that's
implausible: interest explodes at launch and dies away. A constant-mu model can
only explain that early burst as self-excitation, which pushes the branching
ratio towards 1 (the "apparent criticality" warned about by Filimonov & Sornette).

Here the background rate is allowed to fade:
    mu(t) = mu0 + mu1 * exp(-gamma * t)
    mu0    long-run background rate
    mu1    extra launch-time interest, fading at rate gamma (half-life ln2 / gamma)
Everything else (alpha, beta, the branching matrix) means the same as before.
"""

import numpy as np
from scipy import optimize, stats

from . import multivariate as mv
from .hawkes import excitation


def background(t, mu0, mu1, gamma):
    return mu0 + mu1 * np.exp(-gamma * np.asarray(t, float))


def background_integral(t, mu0, mu1, gamma):
    """Expected number of background events from 0 to t."""
    return mu0 * t + mu1 / gamma * (1.0 - np.exp(-gamma * t))


# ---------- one type of event ---------------------------------------------------------------

def log_likelihood(times, T, mu0, mu1, gamma, alpha, beta) -> float:
    lam = background(times, mu0, mu1, gamma) + alpha * excitation(times, beta)
    expected = background_integral(T, mu0, mu1, gamma) + (alpha / beta) * np.sum(1 - np.exp(-beta * (T - times)))
    return float(np.sum(np.log(lam)) - expected)


def fit(times, T) -> dict:
    """MLE over (log mu0, log mu1, log gamma, log beta, logit n), with wide bounds."""
    times = np.asarray(times, float)
    rate = len(times) / T

    def unpack(x):
        mu0, mu1, gamma, beta = np.exp(x[:4])
        n = 1 / (1 + np.exp(-x[4]))
        return mu0, mu1, gamma, n * beta, beta

    def objective(x):
        value = -log_likelihood(times, T, *unpack(x))
        return value if np.isfinite(value) else 1e12

    bounds = [(-20, 5), (-20, 8), (-12, 3), (-10, 6), (-15, 15)]
    best = None
    for n0 in (0.2, 0.6):
        for beta0 in (0.1, 1.0, 10.0):
            for gamma0 in (0.001, 0.05):
                x0 = [np.log(rate * 0.3), np.log(rate * 3), np.log(gamma0), np.log(beta0), np.log(n0 / (1 - n0))]
                result = optimize.minimize(objective, x0, method="L-BFGS-B", bounds=bounds)
                if best is None or result.fun < best.fun:
                    best = result
    mu0, mu1, gamma, alpha, beta = unpack(best.x)
    return {"mu0": mu0, "mu1": mu1, "gamma": gamma, "alpha": alpha, "beta": beta, "n": alpha / beta,
            "log_likelihood": -best.fun, "n_params": 5, "T": T}


def simulate(mu0, mu1, gamma, alpha, beta, T, rng) -> np.ndarray:
    """Ogata thinning. Both the background and the excitation only fall between
    events, so the intensity right now still bounds the near future."""
    times, t, excess = [], 0.0, 0.0
    while True:
        bound = background(t, mu0, mu1, gamma) + excess
        wait = rng.exponential(1.0 / bound)
        t += wait
        if t > T:
            return np.array(times)
        excess *= np.exp(-beta * wait)
        if rng.uniform() * bound <= background(t, mu0, mu1, gamma) + excess:
            times.append(t)
            excess += alpha


def goodness_of_fit(times, p) -> float:
    times = np.asarray(times, float)
    k = np.arange(len(times))
    cumulative = (background_integral(times, p["mu0"], p["mu1"], p["gamma"])
                  + (p["alpha"] / p["beta"]) * (k - excitation(times, p["beta"])))
    return float(stats.kstest(np.diff(np.concatenate([[0.0], cumulative])), "expon").pvalue)


# ---------- two types of event (early, ordinary) -------------------------------------------

def log_likelihood_2(times, types, T, mu0, mu1, gamma, alpha, beta) -> float:
    a = mv.excitation(times, types, beta, len(mu0))
    lam = mu0[types] + mu1[types] * np.exp(-gamma * times) + np.einsum("kj,kj->k", alpha[types], a)
    leftover = 1.0 - np.exp(-beta * (T - times))
    per_type = np.bincount(types, weights=leftover, minlength=len(mu0))
    expected = (mu0.sum() * T + mu1.sum() / gamma * (1 - np.exp(-gamma * T))
                + (alpha / beta * per_type[None, :]).sum())
    return float(np.sum(np.log(lam)) - expected)


def fit_2(times, types, T, d: int = 2) -> dict:
    """Two-type model with a fading background per type (shared fade rate gamma)."""
    times, types = np.asarray(times, float), np.asarray(types, int)
    counts = np.bincount(types, minlength=d)

    def unpack(x):
        return (np.exp(x[:d]), np.exp(x[d:2 * d]), np.exp(x[2 * d]),
                np.exp(x[2 * d + 1:2 * d + 1 + d * d]).reshape(d, d), np.exp(x[-1]))

    def objective(x):
        mu0, mu1, gamma, alpha, beta = unpack(x)
        branching = alpha / beta
        if not np.all(np.isfinite(branching)) or np.max(np.abs(np.linalg.eigvals(branching))) >= 0.999:
            return 1e12
        value = -log_likelihood_2(times, types, T, mu0, mu1, gamma, alpha, beta)
        return value if np.isfinite(value) else 1e12

    bounds = [(-20, 5)] * d + [(-20, 8)] * d + [(-12, 3)] + [(-20, 6)] * (d * d) + [(-10, 6)]
    best = None
    for n0 in (0.1, 0.4):
        for beta0 in (0.1, 1.0, 10.0):
            for gamma0 in (0.001, 0.05):
                rates = np.maximum(counts / T, 1e-6)
                x0 = np.concatenate([np.log(rates * 0.3), np.log(rates * 3), [np.log(gamma0)],
                                     np.log(np.full((d, d), n0 * beta0 / d)).ravel(), [np.log(beta0)]])
                result = optimize.minimize(objective, x0, method="L-BFGS-B", bounds=bounds)
                if best is None or result.fun < best.fun:
                    best = result
    mu0, mu1, gamma, alpha, beta = unpack(best.x)
    branching = alpha / beta
    return {"mu0": mu0, "mu1": mu1, "gamma": gamma, "alpha": alpha, "beta": beta, "branching": branching,
            "spectral_radius": float(np.max(np.abs(np.linalg.eigvals(branching)))),
            "log_likelihood": -best.fun, "n_params": 2 * d + 2 + d * d, "T": T}


def goodness_of_fit_2(times, types, p) -> list[float]:
    times, types = np.asarray(times, float), np.asarray(types, int)
    d = len(p["mu0"])
    a = mv.excitation(times, types, p["beta"], d)
    before = np.vstack([np.zeros(d), np.cumsum(np.eye(d)[types], axis=0)[:-1]])
    bg = p["mu0"][None, :] * times[:, None] + (p["mu1"] / p["gamma"])[None, :] * (1 - np.exp(-p["gamma"] * times))[:, None]
    cumulative = bg + (before - a) @ (p["alpha"] / p["beta"]).T
    out = []
    for i in range(d):
        own = cumulative[types == i, i]
        gaps = np.diff(np.concatenate([[0.0], own]))
        out.append(float(stats.kstest(gaps, "expon").pvalue) if len(gaps) > 5 else float("nan"))
    return out
