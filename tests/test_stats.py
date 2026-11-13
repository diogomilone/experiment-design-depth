"""Tests for tools/stats.py and the replay shortcut in tools/run_study.py. Run: python3 -B tests/test_stats.py"""
import math
import sys
import unittest
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))
import stats as S  # noqa: E402
import run_study as R  # noqa: E402


class Stats(unittest.TestCase):
    def test_lin_matches_least_squares(self):
        rng = np.random.default_rng(1)
        n = 5000
        x = rng.normal(size=(n, 3))
        t = rng.random(n) < 0.4
        y = 1 + x @ [0.5, -1, 2] + 0.3 * t + rng.normal(size=n)
        r = S.lin_ate(S.gram(x[t], y[t]), S.gram(x[~t], y[~t]))
        # Lin's estimator: regress y on [1, t, xc, t*xc]; the coefficient on t is the estimate.
        xc = x - x.mean(0)
        D = np.column_stack([np.ones(n), t, xc, xc * t[:, None]])
        b = np.linalg.lstsq(D, y, rcond=None)[0]
        self.assertAlmostEqual(r["adj"], b[1], places=9)
        self.assertAlmostEqual(r["raw"], y[t].mean() - y[~t].mean(), places=12)
        self.assertLess(r["adj_var"], r["raw_var"])

    def test_delta_equals_naive_when_one_event_per_unit(self):
        rng = np.random.default_rng(2)
        v = (rng.random(20000) < 0.3).astype(float)
        c = v * (rng.random(20000) < 0.1)
        nv = S.ratio_naive_var(c.sum(), (c * c).sum(), v.sum())
        dv = S.ratio_delta_var(len(v), c.sum(), v.sum(), (c * c).sum(), (v * v).sum(), (c * v).sum())
        self.assertAlmostEqual(math.sqrt(nv / dv), 1.0, delta=1e-3)

    def test_delta_wider_with_clustered_events(self):
        rng = np.random.default_rng(3)
        n = 3000
        orders = rng.poisson(3, n) + 1
        level = rng.lognormal(3, 1, n)  # each customer has their own order size
        num = orders * level
        num_sq = orders * level ** 2
        nv = S.ratio_naive_var(num.sum(), num_sq.sum(), orders.sum())
        dv = S.ratio_delta_var(n, num.sum(), orders.sum(), (num ** 2).sum(), (orders ** 2).sum(), (num * orders).sum())
        self.assertGreater(dv, nv)

    def test_msprt_keeps_error_rate_when_peeking(self):
        rng = np.random.default_rng(4)
        reps, looks, per = 4000, 30, 200
        a = rng.normal(size=(reps, looks, per)).sum(2).cumsum(1)
        b = rng.normal(size=(reps, looks, per)).sum(2).cumsum(1)
        n = per * np.arange(1, looks + 1)
        diff = (a - b) / n
        v = 2.0 / n
        naive = (S.two_sided_p(diff / np.sqrt(v)) < 0.05).any(1).mean()
        ms = S.msprt_reject(diff, v, (0.05) ** 2).any(1).mean()
        self.assertGreater(naive, 0.15)
        self.assertLess(ms, 0.05)

    def test_msprt_as_implemented_with_estimated_variance(self):
        # Change r2: the study plugs in the observed variance and sets the mixing scale from the observed rate at each
        # look. On A/A Bernoulli streams with 14 looks, false alarms must stay at or under 5% for the study's scale and
        # for one ten times larger.
        rng = np.random.default_rng(7)
        reps, looks, per, rate = 4000, 14, 2000, 0.1
        sa = rng.binomial(per, rate, size=(reps, looks)).cumsum(1)
        sb = rng.binomial(per, rate, size=(reps, looks)).cumsum(1)
        n = per * np.arange(1, looks + 1)
        pa, pb = sa / n, sb / n
        v = pa * (1 - pa) / n + pb * (1 - pb) / n
        pbar = (sa + sb) / (2 * n)
        for tau_m in (0.01, 0.1):
            ms = S.msprt_reject(pa - pb, v, (tau_m ** 2) * pbar * (1 - pbar)).any(1).mean()
            self.assertLessEqual(ms, 0.05, tau_m)
        naive = (S.two_sided_p((pa - pb) / np.sqrt(v)) < 0.05).any(1).mean()
        self.assertGreater(naive, 0.15)

    def test_holm_bh(self):
        p = np.array([0.001, 0.01, 0.02, 0.04, 0.5])
        self.assertEqual(S.holm(p).tolist(), [True, True, False, False, False])
        self.assertEqual(S.bh(p).tolist(), [True, True, True, True, False])

    def test_n_per_arm(self):
        # 2 * (1.96 + 0.8416)^2 * 1 / 0.1^2 is about 1570
        self.assertAlmostEqual(S.n_per_arm(1.0, 0.1), 1569.8, delta=0.5)

    def test_wilson(self):
        lo, hi = S.wilson(5, 100)
        self.assertTrue(lo < 0.05 < hi)


class Replay(unittest.TestCase):
    def test_hypergeometric_shortcut_matches_explicit_relabelling(self):
        rng = np.random.default_rng(5)
        days, per = 5, 400
        y = (rng.random(days * per) < 0.2).astype(int)
        day = np.repeat(np.arange(days), per)
        n_d = np.bincount(day, minlength=days)
        s_d = np.bincount(day, weights=y, minlength=days).astype(np.int64)
        reps = 3000
        fast = R.aa_binary(n_d.astype(np.int64), s_d, reps, np.random.default_rng(6), 0.01)
        L = rng.random((reps, len(y))) < 0.5
        slow = []
        for r in range(reps):
            nA = np.bincount(day[L[r]], minlength=days).cumsum()
            sA = np.bincount(day[L[r]], weights=y[L[r]], minlength=days).cumsum()
            cn, cs = n_d.cumsum(), s_d.cumsum()
            pA, pB = sA / nA, (cs - sA) / (cn - nA)
            z = (pA - pB) / np.sqrt(pA * (1 - pA) / nA + pB * (1 - pB) / (cn - nA))
            slow.append((S.two_sided_p(z) < 0.05).any())
        self.assertAlmostEqual(fast["naive"].mean(), np.mean(slow), delta=0.03)


if __name__ == "__main__":
    unittest.main(verbosity=1)
