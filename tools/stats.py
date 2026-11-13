"""Small, dependency-light statistics used by every part of the study.

Every function here is tested in tests/test_stats.py.
"""
import math

import numpy as np
from scipy import stats as st

Z975 = st.norm.ppf(0.975)
Z80 = st.norm.ppf(0.80)


def two_sided_p(z):
    return 2.0 * st.norm.sf(np.abs(z))


def welch_z(mean_t, var_t, n_t, mean_c, var_c, n_c):
    """z statistic for a difference of two means from summary numbers (works on arrays)."""
    se = np.sqrt(var_t / n_t + var_c / n_c)
    return (mean_t - mean_c) / se


def msprt_lambda(diff, v, tau2):
    """Normal-mixture sequential probability ratio for a difference of means.

    diff: observed difference; v: its variance; tau2: variance of the mixing normal on the true difference.
    With a known variance and a fixed mixing variance, stopping when the ratio reaches 1/alpha keeps the false-positive
    rate at alpha or less however often one looks. The study plugs in estimated variances and sets the mixing scale
    from the observed spread at each look, a large-sample approximation; its false-alarm rate is measured directly by
    the relabelling replay and by a unit test on simulated streams.
    Returned on the log scale to avoid overflow.
    """
    return 0.5 * np.log(v / (v + tau2)) + (diff ** 2) * tau2 / (2.0 * v * (v + tau2))


def msprt_reject(diff, v, tau2, alpha=0.05):
    return msprt_lambda(diff, v, tau2) >= math.log(1.0 / alpha)


def wilson(k, n, z=Z975):
    if n == 0:
        return (float("nan"), float("nan"))
    p = k / n
    den = 1 + z * z / n
    c = (p + z * z / (2 * n)) / den
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return (c - h, c + h)


def n_per_arm(sigma2, delta, alpha_z=Z975, power_z=Z80):
    """Users per arm for a two-sided test of a difference of means with equal arms."""
    return 2.0 * (alpha_z + power_z) ** 2 * sigma2 / delta ** 2


def holm(p, alpha=0.05):
    p = np.asarray(p, dtype=float)
    order = np.argsort(p)
    m = len(p)
    keep = np.zeros(m, dtype=bool)
    for rank, i in enumerate(order):
        if p[i] <= alpha / (m - rank):
            keep[i] = True
        else:
            break
    return keep


def bh(p, alpha=0.05):
    p = np.asarray(p, dtype=float)
    m = len(p)
    order = np.argsort(p)
    thresh = alpha * np.arange(1, m + 1) / m
    below = p[order] <= thresh
    keep = np.zeros(m, dtype=bool)
    if below.any():
        k = np.max(np.nonzero(below)[0])
        keep[order[: k + 1]] = True
    return keep


def moments_from_gram(M):
    """From G = Z'Z with Z = [1, x_1..x_k, y], return n, mean x, mean y, slope beta, residual variance and raw var(y).

    Regression of y on x with an intercept, solved from the centred cross-products.
    """
    n = M[0, 0]
    s = M[0, 1:] / n
    C = M[1:, 1:] / n - np.outer(s, s)
    k = C.shape[0] - 1
    Cxx, Cxy, Cyy = C[:k, :k], C[:k, k], C[k, k]
    beta = np.linalg.solve(Cxx + 1e-12 * np.eye(k), Cxy) if k else np.zeros(0)
    resid = Cyy - Cxy @ beta if k else Cyy
    dof = n / (n - 1 - k)
    return {"n": n, "mx": s[:k], "my": s[k], "beta": beta, "res_var": resid * dof, "var_y": Cyy * n / (n - 1)}


def lin_ate(Gt, Gc):
    """Difference in means and the covariate-adjusted (separate slopes, centred at the pooled mean) estimate.

    Gt, Gc: Gram matrices [1, x, y]'[1, x, y] for treated and control. Returns estimates and their variances.
    """
    t, c = moments_from_gram(Gt), moments_from_gram(Gc)
    nt, nc = t["n"], c["n"]
    xbar = (nt * t["mx"] + nc * c["mx"]) / (nt + nc)
    raw = t["my"] - c["my"]
    raw_var = t["var_y"] / nt + c["var_y"] / nc
    mu_t = t["my"] + (xbar - t["mx"]) @ t["beta"]
    mu_c = c["my"] + (xbar - c["mx"]) @ c["beta"]
    adj = mu_t - mu_c
    adj_var = t["res_var"] / nt + c["res_var"] / nc
    return {"raw": float(raw), "raw_var": float(raw_var), "adj": float(adj), "adj_var": float(adj_var),
            "nt": float(nt), "nc": float(nc), "mean_t": float(t["my"]), "mean_c": float(c["my"]),
            "var_c": float(c["var_y"]), "var_t": float(t["var_y"]),
            "res_var_c": float(c["res_var"]), "res_var_t": float(t["res_var"])}


def gram(X, y):
    Z = np.column_stack([np.ones(len(y)), X, y]).astype(np.float64, copy=False)
    return Z.T @ Z


def ratio_naive_var(sum_num, sum_sq_unit, sum_den):
    """Variance of a per-event mean that treats every event as independent.

    sum_num: total of the per-event values; sum_sq_unit: total of their squares; sum_den: number of events.
    """
    mean = sum_num / sum_den
    var = (sum_sq_unit - sum_den * mean ** 2) / (sum_den - 1)
    return var / sum_den


def ratio_delta_var(n, s_num, s_den, s_num2, s_den2, s_numden):
    """Delta-method variance of sum(num)/sum(den) where the unit of randomisation holds num and den.

    Inputs are sums over the n units of num, den, num^2, den^2 and num*den.
    """
    mx, my = s_den / n, s_num / n
    vx = (s_den2 - n * mx ** 2) / (n - 1)
    vy = (s_num2 - n * my ** 2) / (n - 1)
    cxy = (s_numden - n * mx * my) / (n - 1)
    r = my / mx
    return (vy - 2 * r * cxy + r * r * vx) / (n * mx * mx)


def chisq_p(observed, expected):
    observed = np.asarray(observed, dtype=float)
    expected = np.asarray(expected, dtype=float)
    stat = float(((observed - expected) ** 2 / expected).sum())
    return stat, float(st.chi2.sf(stat, len(observed) - 1))
