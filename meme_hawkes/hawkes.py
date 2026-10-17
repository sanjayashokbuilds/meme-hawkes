"""Univariate Hawkes process with an exponential kernel, written from scratch.

Intensity (expected events per second right now):
    lambda(t) = mu + sum over past events t_i < t of  alpha * exp(-beta * (t - t_i))

    mu     background rate: events that happen "on their own"
    alpha  jump in the rate right after each event
    beta   how fast that jump fades (memory is about 1/beta seconds)
    n      branching ratio = alpha / beta: the average number of events each event triggers

See docs/CONCEPTS.md sections 3-9 for the plain-English version of everything here.
"""

import numpy as np
from scipy import optimize, stats


def excitation(times: np.ndarray, beta: float) -> np.ndarray:
    """A[i] = sum over j < i of exp(-beta * (t_i - t_j)): leftover excitation just before event i.

    Summing over all past events would take n^2 steps. Instead we carry it forward:
    the excitation just before event i is the excitation just before event i-1,
    plus 1 for event i-1 itself, all decayed over the gap between them.
    """
    a = np.zeros(len(times))
    decay = np.exp(-beta * np.diff(times))
    for i in range(1, len(times)):
        a[i] = decay[i - 1] * (1.0 + a[i - 1])
    return a


def intensity(grid: np.ndarray, times: np.ndarray, mu: float, alpha: float, beta: float) -> np.ndarray:
    """lambda(t) at each time in grid (for plots; does the full sum, so keep inputs modest)."""
    lag = np.asarray(grid, float)[:, None] - np.asarray(times, float)[None, :]
    past = lag > 0
    return mu + alpha * (np.exp(-beta * np.where(past, lag, 0.0)) * past).sum(axis=1)


def log_likelihood(times: np.ndarray, T: float, mu: float, alpha: float, beta: float) -> float:
    """log L = sum of log lambda(t_i)  -  integral of lambda from 0 to T.

    First term rewards a high rate where events happened; second penalises
    expecting events that didn't happen. For the exponential kernel the
    integral has a closed form, so no numerical integration is needed.
    """
    lam = mu + alpha * excitation(times, beta)
    expected_events = mu * T + (alpha / beta) * np.sum(1.0 - np.exp(-beta * (T - times)))
    return float(np.sum(np.log(lam)) - expected_events)


def fit(times: np.ndarray, T: float) -> dict:
    """Maximum likelihood estimates of mu, alpha, beta (and n = alpha / beta).

    The optimiser searches over (log mu, log beta, logit n) instead of the raw
    parameters. Any values it tries then map to mu > 0, beta > 0 and 0 < n < 1,
    so it can never wander into an impossible or explosive model.
    Several starting points guard against stopping at a poor local optimum.
    """
    times = np.asarray(times, float)
    rate = len(times) / T

    def unpack(x):
        mu, beta, n = np.exp(x[0]), np.exp(x[1]), 1.0 / (1.0 + np.exp(-x[2]))
        return mu, n * beta, beta

    def negative_log_likelihood(x):
        return -log_likelihood(times, T, *unpack(x))

    best = None
    for n0 in (0.2, 0.5, 0.8):
        for beta0 in (0.1, 1.0, 10.0):
            x0 = [np.log(rate * (1 - n0)), np.log(beta0), np.log(n0 / (1 - n0))]
            result = optimize.minimize(negative_log_likelihood, x0, method="L-BFGS-B")
            if best is None or result.fun < best.fun:
                best = result
    mu, alpha, beta = unpack(best.x)
    return {"mu": mu, "alpha": alpha, "beta": beta, "n": alpha / beta,
            "log_likelihood": -best.fun, "n_events": len(times), "T": T}


def simulate(mu: float, alpha: float, beta: float, T: float, rng: np.random.Generator) -> np.ndarray:
    """Generate event times on [0, T] by Ogata's thinning.

    Between events the intensity only decays, so its current value is an upper
    bound until the next event. Propose a time at that bound, then accept it
    with probability (true intensity) / (bound), like rejection sampling.
    """
    times, t, excess = [], 0.0, 0.0  # excess = alpha-terms of lambda at time t
    while True:
        bound = mu + excess
        wait = rng.exponential(1.0 / bound)
        t += wait
        if t > T:
            return np.array(times)
        excess *= np.exp(-beta * wait)
        if rng.uniform() * bound <= mu + excess:
            times.append(t)
            excess += alpha


def rescaled_gaps(times: np.ndarray, mu: float, alpha: float, beta: float) -> np.ndarray:
    """Time-rescaling: the expected number of events between consecutive events.

    If the model is right, these gaps are independent Exponential(1) draws.
    Lambda(t_k) = mu * t_k + (alpha / beta) * (k - A_k), with A_k from excitation().
    """
    times = np.asarray(times, float)
    k = np.arange(len(times))
    cumulative = mu * times + (alpha / beta) * (k - excitation(times, beta))
    return np.diff(np.concatenate([[0.0], cumulative]))


def goodness_of_fit(times: np.ndarray, params: dict) -> float:
    """p-value of a Kolmogorov-Smirnov test of the rescaled gaps against Exponential(1).

    Small (say below 0.05) means the model doesn't describe the timing well.
    """
    gaps = rescaled_gaps(times, params["mu"], params["alpha"], params["beta"])
    return float(stats.kstest(gaps, "expon").pvalue)


def rolling_branching_ratio(times: np.ndarray, window: float, step: float, min_events: int = 30) -> list[dict]:
    """Branching ratio re-estimated on a sliding window, using only the past.

    At each check time t (every `step` seconds), fit the model to the events in
    [t - window, t]. Each estimate only uses data available at time t, so it can
    be used as a real-time warning signal without peeking at the future.
    Windows with fewer than min_events events give no estimate.
    Edge effect, accepted for simplicity: excitation left over from events just
    before the window is ignored.
    """
    times = np.asarray(times, float)
    out = []
    for t in np.arange(window, times[-1] + step, step) if len(times) else []:
        inside = times[(times > t - window) & (times <= t)]
        row = {"t": float(t), "events": len(inside), "n": np.nan}
        if len(inside) >= min_events:
            row["n"] = fit(inside - (t - window), window)["n"]
        out.append(row)
    return out
