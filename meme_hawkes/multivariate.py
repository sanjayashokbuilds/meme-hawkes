"""Multivariate Hawkes process with exponential kernels, written from scratch.

Several types of event (here: trades by early-slot wallets, and by ordinary
wallets). Each type has its own intensity, and every type can excite every type:

    lambda_i(t) = mu_i + sum over types j of  alpha[i, j] * sum over past type-j events of exp(-beta * (t - t_k))

    mu[i]        background rate of type i
    alpha[i, j]  jump in type i's rate right after a type-j event
    beta         how fast every jump fades (shared by all pairs, to keep the
                 number of parameters small enough for one token's data)

The branching matrix N = alpha / beta: N[i, j] is the average number of type-i
events directly triggered by one type-j event. Our headline number is
N[ordinary, early]: how many ordinary trades each early-wallet trade sets off.
The largest eigenvalue of N (its spectral radius) plays the role of the
univariate branching ratio: below 1 the process is stable.
"""

import numpy as np
from scipy import optimize, stats


def excitation(times: np.ndarray, types: np.ndarray, beta: float, n_types: int) -> np.ndarray:
    """A[k, j] = sum over earlier type-j events of exp(-beta * (t_k - t)): the same
    running-total trick as the univariate model, kept separately for each type."""
    a = np.zeros((len(times), n_types))
    decay = np.exp(-beta * np.diff(times))
    for k in range(1, len(times)):
        a[k] = decay[k - 1] * a[k - 1]
        a[k, types[k - 1]] += decay[k - 1]
    return a


def log_likelihood(times, types, T, mu, alpha, beta) -> float:
    """Sum over events of log lambda_{type}(t)  minus  the expected number of events of every type."""
    a = excitation(times, types, beta, len(mu))
    lam = mu[types] + np.einsum("kj,kj->k", alpha[types], a)
    leftover = 1.0 - np.exp(-beta * (T - times))           # how much of each event's bump fell inside [0, T]
    per_type = np.bincount(types, weights=leftover, minlength=len(mu))
    expected = mu.sum() * T + (alpha / beta * per_type[None, :]).sum()
    return float(np.sum(np.log(lam)) - expected)


def fit(times, types, T, n_types=2) -> dict:
    """Maximum likelihood over (log mu, log alpha, log beta).

    Unlike the univariate fit, stability (spectral radius < 1) isn't built into
    the parameters; candidates that break it get a large penalty instead.
    """
    times, types = np.asarray(times, float), np.asarray(types, int)
    counts = np.bincount(types, minlength=n_types)
    d = n_types

    def unpack(x):
        return np.exp(x[:d]), np.exp(x[d:d + d * d]).reshape(d, d), np.exp(x[-1])

    def objective(x):
        mu, alpha, beta = unpack(x)
        if np.max(np.abs(np.linalg.eigvals(alpha / beta))) >= 0.999:
            return 1e12
        return -log_likelihood(times, types, T, mu, alpha, beta)

    best = None
    for n0 in (0.1, 0.4):
        for beta0 in (0.1, 1.0, 10.0):
            mu0 = np.maximum(counts / T * (1 - n0), 1e-6)
            alpha0 = np.full((d, d), n0 * beta0 / d)
            x0 = np.concatenate([np.log(mu0), np.log(alpha0).ravel(), [np.log(beta0)]])
            result = optimize.minimize(objective, x0, method="L-BFGS-B")
            if best is None or result.fun < best.fun:
                best = result
    mu, alpha, beta = unpack(best.x)
    branching = alpha / beta
    return {"mu": mu, "alpha": alpha, "beta": beta, "branching": branching,
            "spectral_radius": float(np.max(np.abs(np.linalg.eigvals(branching)))),
            "log_likelihood": -best.fun, "counts": counts, "T": T}


def simulate(mu, alpha, beta, T, rng) -> tuple[np.ndarray, np.ndarray]:
    """Ogata thinning for several types: bound the total intensity, propose, accept,
    then pick which type happened in proportion to each type's intensity."""
    mu, alpha = np.asarray(mu, float), np.asarray(alpha, float)
    d = len(mu)
    times, types, t, excess = [], [], 0.0, np.zeros(d)   # excess[i] = alpha-terms of lambda_i at time t
    while True:
        bound = (mu + excess).sum()
        wait = rng.exponential(1.0 / bound)
        t += wait
        if t > T:
            return np.array(times), np.array(types, dtype=int)
        excess *= np.exp(-beta * wait)
        lam = mu + excess
        if rng.uniform() * bound <= lam.sum():
            i = rng.choice(d, p=lam / lam.sum())
            times.append(t)
            types.append(i)
            excess += alpha[:, i]


def goodness_of_fit(times, types, params) -> list[float]:
    """KS p-value per type: each type's rescaled gaps should look Exponential(1)."""
    times, types = np.asarray(times, float), np.asarray(types, int)
    mu, alpha, beta = params["mu"], params["alpha"], params["beta"]
    a = excitation(times, types, beta, len(mu))
    # cumulative count of each type strictly before event k
    before = np.vstack([np.zeros(len(mu)), np.cumsum(np.eye(len(mu))[types], axis=0)[:-1]])
    # Lambda_i(t_k) = mu_i t_k + sum_j alpha_ij / beta * (count_j before t_k - A[k, j])
    cumulative = mu[None, :] * times[:, None] + (before - a) @ (alpha / beta).T
    p = []
    for i in range(len(mu)):
        own = cumulative[types == i, i]
        gaps = np.diff(np.concatenate([[0.0], own]))
        p.append(float(stats.kstest(gaps, "expon").pvalue) if len(gaps) > 5 else float("nan"))
    return p
