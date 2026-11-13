"""Run one part of the study and write its result JSON under results/.

Usage: python3 -I -B tools/run_study.py <part> <work dir> [--reps N]
parts: srm, m1, m2, m3, m4, m5, readout. <work dir> holds the parquet files made by tools/prepare.py.
Large files are read in chunks of one million rows through DuckDB, never whole.
"""
import argparse
import json
import math
import sys
from pathlib import Path

import duckdb
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import stats as S  # noqa: E402

HERE = Path(__file__).resolve().parent.parent
RES = HERE / "results"
PROTO = json.loads((HERE / "protocol-r1.json").read_text(encoding="utf-8"))
ALPHA = PROTO["alpha"]
SEED = PROTO["seed"]
FEAT = [f"f{i}" for i in range(12)]
CHUNK = 1_000_000


def con():
    c = duckdb.connect()
    c.execute("SET threads=2")
    c.execute("SET memory_limit='1000MB'")
    return c


def criteo_chunks(work, cols):
    c = con()
    path = work / "criteo.parquet"
    n = c.execute(f"SELECT count(*) FROM '{path}'").fetchone()[0]
    sel = ", ".join(["rid"] + cols)
    for a in range(0, n, CHUNK):
        d = c.execute(f"SELECT {sel} FROM '{path}' WHERE rid >= {a} AND rid < {a + CHUNK} ORDER BY rid").fetchnumpy()
        yield {k: np.asarray(v) for k, v in d.items()}


def save(name, obj):
    RES.mkdir(parents=True, exist_ok=True)
    p = RES / f"{name}.json"
    p.write_text(json.dumps(obj, indent=1, sort_keys=True), encoding="utf-8")
    print("wrote", p)


# ---------------------------------------------------------------- sample-ratio checks
def part_srm(work):
    c = con()
    out = {}
    nt, n = c.execute(f"SELECT sum(treatment), count(*) FROM '{work / 'criteo.parquet'}'").fetchone()
    exp = PROTO["srm"]["criteo_expected_share"]
    stat, p = S.chisq_p([nt, n - nt], [exp * n, (1 - exp) * n])
    out["criteo"] = {"n": int(n), "treated": int(nt), "share": nt / n, "expected": exp, "chi2": stat, "p": p,
                     "flag": p < PROTO["srm"]["flag_p"]}
    rows = c.execute(f"SELECT segment, count(*) FROM '{work / 'hillstrom.parquet'}' GROUP BY 1 ORDER BY 1").fetchall()
    obs = [r[1] for r in rows]
    stat, p = S.chisq_p(obs, [sum(obs) / 3] * 3)
    out["hillstrom"] = {"arms": {r[0]: int(r[1]) for r in rows}, "chi2": stat, "p": p, "flag": p < PROTO["srm"]["flag_p"]}
    a = c.execute(f"""SELECT experiment_id, variant_id, count_c, count_t FROM (
        SELECT *, row_number() OVER (PARTITION BY experiment_id, variant_id ORDER BY time_since_start DESC) rn
        FROM '{work / 'asos.parquet'}' WHERE metric_id = 1) WHERE rn = 1 ORDER BY 1, 2""").fetchall()
    flags = []
    for e, v, cc, ct in a:
        stat, p = S.chisq_p([cc, ct], [(cc + ct) / 2] * 2)
        flags.append({"pair": f"{e}-{v}", "count_c": cc, "count_t": ct, "share_t": ct / (cc + ct), "p": p,
                      "flag": p < PROTO["srm"]["flag_p"]})
    out["asos"] = {"pairs": len(flags), "flagged": sum(f["flag"] for f in flags), "rows": flags}
    save("srm", out)


# ---------------------------------------------------------------- M1 variance reduction
def criteo_bins(work, q):
    c = con()
    path = work / "criteo.parquet"
    edges = {}
    for f in FEAT:
        qs = c.execute(f"SELECT quantile_cont({f}, {list(q)}) FROM '{path}'").fetchone()[0]
        edges[f] = np.unique(np.asarray(qs, dtype=np.float64))
    return edges


def part_m1(work):
    proto = PROTO["M1_variance_reduction"]
    out = {"criteo": {}, "hillstrom": {}}
    # Criteo, adjustment A (linear) and the folds' bin statistics for adjustment B, in one pass.
    edges = criteo_bins(work, [i / 20 for i in range(1, 20)])
    nb = {f: len(edges[f]) + 1 for f in FEAT}
    outcomes = proto["criteo"]["outcomes"]
    G = {(y, arm): np.zeros((14, 14)) for y in outcomes for arm in (0, 1)}
    bstat = {(y, fold, f): np.zeros((2, nb[f])) for y in outcomes for fold in (0, 1) for f in FEAT}
    for d in criteo_chunks(work, FEAT + ["treatment"] + outcomes):
        X = np.column_stack([d[f].astype(np.float64) for f in FEAT])
        fold = (d["rid"] % 2).astype(int)
        bidx = {f: np.searchsorted(edges[f], d[f].astype(np.float64), side="right") for f in FEAT}
        for y in outcomes:
            yy = d[y].astype(np.float64)
            for arm in (0, 1):
                m = d["treatment"] == arm
                G[(y, arm)] += S.gram(X[m], yy[m])
            for fo in (0, 1):
                m = fold == fo
                for f in FEAT:
                    bstat[(y, fo, f)][0] += np.bincount(bidx[f][m], minlength=nb[f])
                    bstat[(y, fo, f)][1] += np.bincount(bidx[f][m], weights=yy[m], minlength=nb[f])
    # Adjustment B: cross-fitted additive bin-mean prediction, then one covariate.
    GB = {(y, arm): np.zeros((3, 3)) for y in outcomes for arm in (0, 1)}
    for d in criteo_chunks(work, FEAT + ["treatment"] + outcomes):
        fold = (d["rid"] % 2).astype(int)
        bidx = {f: np.searchsorted(edges[f], d[f].astype(np.float64), side="right") for f in FEAT}
        for y in outcomes:
            yy = d[y].astype(np.float64)
            pred = np.zeros(len(yy))
            for fo in (0, 1):
                m = fold == fo
                other = 1 - fo
                tot_n = bstat[(y, other, FEAT[0])][0].sum()
                tot_s = bstat[(y, other, FEAT[0])][1].sum()
                base = tot_s / tot_n
                p = np.full(m.sum(), base)
                for f in FEAT:
                    cnt, sm = bstat[(y, other, f)]
                    mean_b = np.where(cnt > 0, sm / np.maximum(cnt, 1), base)
                    p += mean_b[bidx[f][m]] - base
                pred[m] = p
            for arm in (0, 1):
                m = d["treatment"] == arm
                GB[(y, arm)] += S.gram(pred[m][:, None], yy[m])
    for y in outcomes:
        A = S.lin_ate(G[(y, 1)], G[(y, 0)])
        B = S.lin_ate(GB[(y, 1)], GB[(y, 0)])
        delta = proto["criteo"]["mde_relative"] * A["mean_c"]
        sig_raw = (A["var_t"] + A["var_c"]) / 2
        sig_A = (A["res_var_t"] + A["res_var_c"]) / 2
        sig_B = (B["res_var_t"] + B["res_var_c"]) / 2
        out["criteo"][y] = {
            "nt": A["nt"], "nc": A["nc"], "mean_t": A["mean_t"], "mean_c": A["mean_c"],
            "raw": A["raw"], "raw_se": math.sqrt(A["raw_var"]),
            "adjA": A["adj"], "adjA_se": math.sqrt(A["adj_var"]),
            "adjB": B["adj"], "adjB_se": math.sqrt(B["adj_var"]),
            "var_removed_A": 1 - A["adj_var"] / A["raw_var"], "var_removed_B": 1 - B["adj_var"] / B["raw_var"],
            "mde_abs": delta,
            "n_per_arm_raw": S.n_per_arm(sig_raw, delta), "n_per_arm_A": S.n_per_arm(sig_A, delta),
            "n_per_arm_B": S.n_per_arm(sig_B, delta),
        }
    # MineThatData: classic CUPED on pre-period spend, then all pre-period fields.
    c = con()
    h = c.execute(f"SELECT * FROM '{work / 'hillstrom.parquet'}'").fetchnumpy()
    t_name, c_name = proto["hillstrom"]["arms"]
    seg = np.asarray(h["segment"])
    keep = (seg == t_name) | (seg == c_name)
    treat = (seg[keep] == t_name)
    cols_B = []
    for k in proto["hillstrom"]["adjust_B"]:
        v = np.asarray(h[k])[keep]
        if v.dtype.kind in "OUS":
            levels = sorted(set(v.tolist()))
            for lv in levels[1:]:
                cols_B.append((v == lv).astype(float))
        else:
            cols_B.append(v.astype(float))
    XB = np.column_stack(cols_B)
    XA = np.asarray(h["history"], dtype=float)[keep][:, None]
    for y in proto["hillstrom"]["outcomes"]:
        yy = np.asarray(h[y], dtype=float)[keep]
        A = S.lin_ate(S.gram(XA[treat], yy[treat]), S.gram(XA[~treat], yy[~treat]))
        B = S.lin_ate(S.gram(XB[treat], yy[treat]), S.gram(XB[~treat], yy[~treat]))
        out["hillstrom"][y] = {"nt": A["nt"], "nc": A["nc"], "mean_t": A["mean_t"], "mean_c": A["mean_c"],
                               "raw": A["raw"], "raw_se": math.sqrt(A["raw_var"]),
                               "adjA": A["adj"], "adjA_se": math.sqrt(A["adj_var"]),
                               "adjB": B["adj"], "adjB_se": math.sqrt(B["adj_var"]),
                               "var_removed_A": 1 - A["adj_var"] / A["raw_var"],
                               "var_removed_B": 1 - B["adj_var"] / B["raw_var"]}
    save("m1", out)


# ---------------------------------------------------------------- M2 peeking on ASOS
def part_m2(work):
    proto = PROTO["M2_peeking"]
    c = con()
    rows = c.execute(f"""SELECT experiment_id, variant_id, metric_id, time_since_start, count_c, count_t,
                         mean_c, mean_t, variance_c, variance_t FROM '{work / 'asos.parquet'}'
                         ORDER BY 1, 2, 3, 4""").fetchall()
    series = {}
    for r in rows:
        series.setdefault((r[0], r[1], r[2]), []).append(r[3:])
    taus = [proto["msprt"]["tau_sd_multiple"]] + proto["msprt"]["sensitivity"]
    tests, dropped, dropped_keys = [], 0, []
    for key, s in series.items():
        s = np.asarray(s, dtype=float)
        t, nc, nt, mc, mt, vc, vt = s.T
        # Change r2: a missing last-snapshot variance or count is dropped and counted too (r1 tested <= 0 only,
        # which a missing value passes).
        last = np.array([vc[-1], vt[-1], nc[-1], nt[-1]])
        if not np.isfinite(last).all() or vc[-1] <= 0 or vt[-1] <= 0 or nc[-1] < 2 or nt[-1] < 2:
            dropped += 1
            dropped_keys.append(f"{key[0]}-{key[1]}-m{key[2]}")
            continue
        diff = mt - mc
        v = vc / nc + vt / nt
        ok = (vc > 0) & (vt > 0) & (nc > 1) & (nt > 1)
        z = np.where(ok, diff / np.sqrt(np.where(ok, v, 1)), 0.0)
        p = S.two_sided_p(z)
        # Change r4: one look per elapsed day, at the first snapshot of that day (r1 to r3 looked only at whole-day
        # times, which series recorded at half-day offsets never reach).
        dnum = np.floor(t + 1e-6)
        first = np.ones(len(t), dtype=bool)
        first[1:] = dnum[1:] != dnum[:-1]
        day = ok & first & (dnum >= 1)
        fz, fp = z[-1], p[-1]
        rec = {"key": f"{key[0]}-{key[1]}-m{key[2]}", "metric": int(key[2]), "days": float(t[-1]),
               "looks": int(day.sum()), "final_z": float(fz), "final_p": float(fp), "final_sig": bool(fp < ALPHA)}
        hit = np.nonzero(day & (p < ALPHA))[0]
        rec["naive_call"] = bool(len(hit))
        if len(hit):
            i = hit[0]
            rec["naive_day"] = float(t[i])
            rec["naive_sign"] = int(np.sign(z[i]))
            rec["naive_frac_n"] = float((nc[i] + nt[i]) / (nc[-1] + nt[-1]))
        for tau_m in taus:
            sd = np.sqrt((vc + vt) / 2)
            lam = np.where(day, S.msprt_lambda(diff, np.where(ok, v, 1), (tau_m * sd) ** 2), -np.inf)
            hit = np.nonzero(lam >= math.log(1 / ALPHA))[0]
            k = f"msprt_{tau_m}"
            rec[k + "_call"] = bool(len(hit))
            if len(hit):
                i = hit[0]
                rec[k + "_day"] = float(t[i])
                rec[k + "_sign"] = int(np.sign(diff[i]))
                rec[k + "_frac_n"] = float((nc[i] + nt[i]) / (nc[-1] + nt[-1]))
        tests.append(rec)

    def tally(prefix):
        calls = [r for r in tests if r[prefix + "_call"]]
        unsup = [r for r in calls if (not r["final_sig"]) or np.sign(r["final_z"]) != r[prefix + "_sign"]]
        flip = [r for r in calls if r["final_sig"] and np.sign(r["final_z"]) != r[prefix + "_sign"]]
        final = [r for r in tests if r["final_sig"]]
        reached = [r for r in final if r[prefix + "_call"] and r[prefix + "_sign"] == np.sign(r["final_z"])]
        fr = [r[prefix + "_frac_n"] for r in reached]
        return {"calls": len(calls), "unsupported": len(unsup), "opposite_sign": len(flip),
                "final_sig": len(final), "final_reached": len(reached),
                "median_frac_n_when_reached": float(np.median(fr)) if fr else None}

    out = {"tests": len(tests), "dropped": dropped, "dropped_keys": dropped_keys, "naive": tally("naive")}
    for tau_m in taus:
        out[f"msprt_{tau_m}"] = tally(f"msprt_{tau_m}")
    out["by_metric"] = {}
    for m in (1, 2, 3, 4):
        sub = [r for r in tests if r["metric"] == m]
        calls = [r for r in sub if r["naive_call"]]
        out["by_metric"][m] = {"tests": len(sub), "naive_calls": len(calls),
                               "naive_unsupported": sum(1 for r in calls if (not r["final_sig"]) or np.sign(r["final_z"]) != r["naive_sign"]),
                               "final_sig": sum(r["final_sig"] for r in sub)}
    out["rows"] = tests
    save("m2", out)


# ---------------------------------------------------------------- M3 A/A replay
def aa_binary(n_d, s_d, reps, rng, tau_m):
    """Exact random relabelling of a binary metric, day by day, vectorised over replications."""
    days = len(n_d)
    nA = rng.binomial(n_d[None, :].repeat(reps, 0), 0.5)
    sA = rng.hypergeometric(s_d[None, :].repeat(reps, 0), (n_d - s_d)[None, :].repeat(reps, 0), nA)
    cnA, csA = nA.cumsum(1), sA.cumsum(1)
    cn, cs = n_d.cumsum(), s_d.cumsum()
    cnB, csB = cn[None, :] - cnA, cs[None, :] - csA
    pA, pB = csA / cnA, csB / cnB
    v = pA * (1 - pA) / cnA + pB * (1 - pB) / cnB
    z = (pA - pB) / np.sqrt(v)
    p = S.two_sided_p(z)
    pbar = cs / cn
    tau2 = (tau_m ** 2) * pbar * (1 - pbar)
    lam = S.msprt_lambda(pA - pB, v, tau2[None, :])
    hitm = lam >= math.log(1 / ALPHA)
    ms = hitm.any(1)
    # Added after the results: the sequential rule for early stops, then one fixed test at the planned end.
    # Change r2 adds two outputs from the same draws: the sequential rule's cumulative rate by look, and the combined
    # rule with its end test at 4.5%.
    return {"naive": (p < ALPHA).any(1), "fixed": p[:, -1] < ALPHA, "msprt": ms, "hybrid": ms | (p[:, -1] < ALPHA),
            "hybrid_045": ms | (p[:, -1] < 0.045),
            "naive_by_look": [float((p[:, : k + 1] < ALPHA).any(1).mean()) for k in range(days)],
            "msprt_by_look": [float(hitm[:, : k + 1].any(1).mean()) for k in range(days)]}


def summarize_rate(flags):
    k, n = int(flags.sum()), len(flags)
    lo, hi = S.wilson(k, n)
    return {"k": k, "n": n, "rate": k / n, "lo": lo, "hi": hi}


def part_m3(work, reps):
    proto = PROTO["M3_aa_replay"]
    days = proto["days"]
    rng = np.random.default_rng(SEED)
    c = con()
    N = c.execute(f"SELECT count(*) FROM '{work / 'criteo.parquet'}'").fetchone()[0]
    order = rng.permutation(N)  # arrival position of each rid
    day_of = (order * days // N).astype(np.int64)
    out = {"criteo": {}}
    tot = {m: np.zeros(days) for m in proto["metrics"]}
    n_d = np.zeros(days)
    for d in criteo_chunks(work, proto["metrics"]):
        dd = day_of[d["rid"]]
        n_d += np.bincount(dd, minlength=days)
        for m in proto["metrics"]:
            tot[m] += np.bincount(dd, weights=d[m].astype(float), minlength=days)
    n_d = n_d.astype(np.int64)
    tau_m = PROTO["M2_peeking"]["msprt"]["tau_sd_multiple"]
    for m in proto["metrics"]:
        r = aa_binary(n_d, tot[m].astype(np.int64), reps, rng, tau_m)
        out["criteo"][m] = {k: summarize_rate(r[k]) for k in ("naive", "fixed", "msprt", "hybrid", "hybrid_045")}
        out["criteo"][m]["naive_by_look"] = r["naive_by_look"]
        out["criteo"][m]["msprt_by_look"] = r["msprt_by_look"]
    out["criteo"]["users_per_day"] = int(n_d[0])
    # Secondary: Online Retail II, real days, revenue per customer, explicit relabelling.
    sec = proto["secondary"]
    lo_d, hi_d = sec["window"]
    rows = c.execute(f"""SELECT customer_id, CAST(date_diff('day', DATE '{lo_d}', CAST(invoice_date AS DATE)) AS INT) d,
                         sum(quantity * price) rev FROM '{work / 'retail.parquet'}'
                         WHERE customer_id IS NOT NULL AND invoice NOT LIKE 'C%' AND quantity > 0 AND price > 0
                         AND invoice_date >= TIMESTAMP '{lo_d}' AND invoice_date < TIMESTAMP '{hi_d}' + INTERVAL 1 DAY
                         GROUP BY 1, 2""").fetchall()
    cust = sorted({r[0] for r in rows})
    ix = {cid: i for i, cid in enumerate(cust)}
    nd = sec["days"]
    daily = np.zeros((len(cust), nd))
    for cid, d, rev in rows:
        daily[ix[cid], d] += rev
    first = np.argmax(daily > 0, axis=1)
    entered = (np.arange(nd)[None, :] >= first[:, None]).astype(float)
    C = daily.cumsum(1)
    rng2 = np.random.default_rng(SEED + 1)
    L = (rng2.random((reps, len(cust))) < 0.5).astype(float)
    nA, nB = L @ entered, (1 - L) @ entered
    sA, sB = L @ C, (1 - L) @ C
    qA, qB = L @ (C ** 2), (1 - L) @ (C ** 2)
    mA, mB = sA / nA, sB / nB
    vA = (qA - nA * mA ** 2) / (nA - 1)
    vB = (qB - nB * mB ** 2) / (nB - 1)
    v = vA / nA + vB / nB
    z = (mA - mB) / np.sqrt(v)
    p = S.two_sided_p(z)
    look = np.zeros(nd, dtype=bool)
    look[6:] = True  # daily looks from the end of the first week
    tau2 = (tau_m ** 2) * (vA + vB) / 2
    lam = S.msprt_lambda(mA - mB, v, tau2)
    out["retail"] = {"customers": len(cust), "days": nd,
                     "naive": summarize_rate(((p < ALPHA) & look[None, :]).any(1)),
                     "fixed": summarize_rate(p[:, -1] < ALPHA),
                     "msprt": summarize_rate(((lam >= math.log(1 / ALPHA)) & look[None, :]).any(1)),
                     "hybrid": summarize_rate(((lam >= math.log(1 / ALPHA)) & look[None, :]).any(1) | (p[:, -1] < ALPHA))}
    out["reps"] = reps
    save("m3", out)


# ---------------------------------------------------------------- M4 ratio metric
def retail_units(c, work, lo_d, hi_d):
    rows = c.execute(f"""WITH o AS (SELECT customer_id, invoice, sum(quantity * price) rev, sum(quantity) units
                         FROM '{work / 'retail.parquet'}'
                         WHERE customer_id IS NOT NULL AND invoice NOT LIKE 'C%' AND quantity > 0 AND price > 0
                         AND invoice_date >= TIMESTAMP '{lo_d}' AND invoice_date < TIMESTAMP '{hi_d}' + INTERVAL 1 DAY
                         GROUP BY 1, 2)
                         SELECT customer_id, count(*) orders, sum(rev), sum(rev * rev), sum(units), sum(units * units)
                         FROM o GROUP BY 1 ORDER BY 1""").fetchall()
    return np.asarray([r[1:] for r in rows], dtype=float)


def aa_ratio(U, reps, rng):
    o, r, r2, u, u2 = U.T
    L = (rng.random((reps, len(o))) < 0.5).astype(float)
    res = {}
    for name, num, num2 in (("revenue_per_order", r, r2), ("units_per_order", u, u2)):
        stats_arm = []
        for W in (L, 1 - L):
            n = W.sum(1)
            so, sn, sq = W @ o, W @ num, W @ num2
            nv = S.ratio_naive_var(sn, sq, so)
            dv = S.ratio_delta_var(n, sn, so, W @ (num ** 2), W @ (o ** 2), W @ (num * o))
            stats_arm.append((sn / so, nv, dv))
        (ra, nva, dva), (rb, nvb, dvb) = stats_arm
        zn = (ra - rb) / np.sqrt(nva + nvb)
        zd = (ra - rb) / np.sqrt(dva + dvb)
        res[name] = {"naive": summarize_rate(S.two_sided_p(zn) < ALPHA),
                     "delta": summarize_rate(S.two_sided_p(zd) < ALPHA),
                     "median_se_ratio_naive_over_delta": float(np.median(np.sqrt((nva + nvb) / (dva + dvb))))}
    return res


def part_m4(work, reps):
    proto = PROTO["M4_ratio"]
    c = con()
    out = {}
    for label, (lo_d, hi_d) in (("four_weeks", proto["window"]), ("twelve_weeks", proto["sensitivity_window"])):
        U = retail_units(c, work, lo_d, hi_d)
        rng = np.random.default_rng(SEED + 2)
        o = U[:, 0]
        out[label] = {"window": [lo_d, hi_d], "customers": int(len(U)), "orders": int(o.sum()),
                      "orders_per_customer_mean": float(o.mean()), "orders_per_customer_max": int(o.max()),
                      "share_orders_from_top_decile_customers": float(np.sort(o)[::-1][: max(1, len(o) // 10)].sum() / o.sum()),
                      "revenue_per_order": float(U[:, 1].sum() / o.sum()),
                      **aa_ratio(U, reps, rng)}
    # Check: Criteo conversion per visit, at most one visit per user, so both variances must coincide.
    g = c.execute(f"""SELECT treatment, count(*) n, sum(visit) v, sum(conversion) cv,
                      sum(conversion * conversion) cv2, sum(visit * visit) v2, sum(conversion * visit) cvv, max(visit) mx
                      FROM '{work / 'criteo.parquet'}' GROUP BY 1 ORDER BY 1""").fetchall()
    chk = {}
    for t, n, v, cv, cv2, v2, cvv, mx in g:
        nv = S.ratio_naive_var(float(cv), float(cv2), float(v))
        dv = S.ratio_delta_var(float(n), float(cv), float(v), float(cv2), float(v2), float(cvv))
        chk[int(t)] = {"users": int(n), "visits": int(v), "conversions": int(cv), "max_visit": int(mx),
                       "naive_se": math.sqrt(nv), "delta_se": math.sqrt(dv), "ratio": math.sqrt(nv / dv)}
    out["criteo_conversion_per_visit_check"] = chk
    out["reps"] = reps
    save("m4", out)


# ---------------------------------------------------------------- M5 segments
def part_m5(work):
    proto = PROTO["M5_segments"]
    edges = criteo_bins(work, proto["cuts"])
    K = proto["slices"]
    c = con()
    N = c.execute(f"SELECT count(*) FROM '{work / 'criteo.parquet'}'").fetchone()[0]
    rng = np.random.default_rng(SEED + 3)
    slice_of = rng.integers(0, K, size=N).astype(np.int64)
    nb = {f: len(edges[f]) + 1 for f in FEAT}
    cnt = {f: np.zeros((K, nb[f], 2)) for f in FEAT}
    vis = {f: np.zeros((K, nb[f], 2)) for f in FEAT}
    for d in criteo_chunks(work, FEAT + ["treatment", "visit"]):
        s = slice_of[d["rid"]]
        t = d["treatment"].astype(np.int64)
        y = d["visit"].astype(float)
        for f in FEAT:
            b = np.searchsorted(edges[f], d[f].astype(np.float64), side="right")
            idx = (s * nb[f] + b) * 2 + t
            cnt[f] += np.bincount(idx, minlength=K * nb[f] * 2).reshape(K, nb[f], 2)
            vis[f] += np.bincount(idx, weights=y, minlength=K * nb[f] * 2).reshape(K, nb[f], 2)

    def seg_z(n_seg, y_seg, n_all, y_all):
        """Segment against the rest: difference of the arm differences. Arrays [..., arm]."""
        n_r, y_r = n_all - n_seg, y_all - y_seg
        with np.errstate(divide="ignore", invalid="ignore"):
            ps, pr = y_seg / n_seg, y_r / n_r
            eff_s = ps[..., 1] - ps[..., 0]
            eff_r = pr[..., 1] - pr[..., 0]
            v = (ps * (1 - ps) / n_seg).sum(-1) + (pr * (1 - pr) / n_r).sum(-1)
            z = (eff_s - eff_r) / np.sqrt(v)
        return z, eff_s, eff_r

    segs = [(f, b) for f in FEAT for b in range(nb[f])]
    per_slice = []
    for k in range(K):
        zs, zh, sizes = [], [], []
        for f, b in segs:
            n_k, y_k = cnt[f][k], vis[f][k]
            n_all_k, y_all_k = n_k.sum(0), y_k.sum(0)
            z, _, _ = seg_z(n_k[b], y_k[b], n_all_k, y_all_k)
            n_h, y_h = cnt[f].sum(0) - n_k, vis[f].sum(0) - y_k
            z2, _, _ = seg_z(n_h[b], y_h[b], n_h.sum(0), y_h.sum(0))
            zs.append(float(z))
            zh.append(float(z2))
            sizes.append(float(n_k[b].sum()))
        zs, zh = np.asarray(zs), np.asarray(zh)
        valid = np.isfinite(zs) & np.isfinite(zh) & (np.asarray(sizes) > 0)
        p = np.where(valid, S.two_sided_p(np.where(valid, zs, 0)), 1.0)
        rep = valid & (np.sign(zh) == np.sign(zs)) & (S.two_sided_p(np.where(valid, zh, 0)) < ALPHA)
        rules = {"naive": p < ALPHA, "holm": S.holm(p, ALPHA), "bh": S.bh(p, ALPHA)}
        per_slice.append({"slice": k, "segments": int(valid.sum()),
                          "users": int(sum(cnt[FEAT[0]][k].sum() for _ in [0])),
                          **{r: {"flagged": int(m.sum()), "replicated": int((m & rep).sum())} for r, m in rules.items()},
                          "holdout_sig_any": int((valid & (S.two_sided_p(np.where(valid, zh, 0)) < ALPHA)).sum())})
    out = {"slices": K, "segments_defined": len(segs), "rows": per_slice}
    for r in ("naive", "holm", "bh"):
        fl = sum(s[r]["flagged"] for s in per_slice)
        rp = sum(s[r]["replicated"] for s in per_slice)
        out[r] = {"flagged": fl, "replicated": rp, "share_replicated": rp / fl if fl else None,
                  "flagged_per_slice": fl / K}
    # Whole-data segment effects for the page's table (visit, treated minus control, per segment).
    whole = []
    for f, b in segs:
        n, y = cnt[f].sum(0), vis[f].sum(0)
        z, es, er = seg_z(n[b], y[b], n.sum(0), y.sum(0))
        whole.append({"feature": f, "bin": b, "users": float(n[b].sum()), "effect": float(es), "rest": float(er),
                      "z": float(z)})
    out["whole"] = whole
    save("m5", out)


# ---------------------------------------------------------------- readout of the e-mail test
def part_readout(work):
    """The worked readout: the declared guardrail (conversion) for the women's e-mail against no e-mail."""
    c = con()
    t_name, c_name = PROTO["M1_variance_reduction"]["hillstrom"]["arms"]
    rows = c.execute(f"""SELECT segment, count(*), sum(conversion), sum(visit) FROM '{work / 'hillstrom.parquet'}'
                         WHERE segment IN ('{t_name}', '{c_name}') GROUP BY 1""").fetchall()
    d = {r[0]: (r[1], r[2], r[3]) for r in rows}
    (nt, ct, vt), (nc, cc, vc) = d[t_name], d[c_name]
    pt, pc = ct / nt, cc / nc
    se = math.sqrt(pt * (1 - pt) / nt + pc * (1 - pc) / nc)
    save("readout", {"conversion": {"t": pt, "c": pc, "lift": pt - pc, "se": se,
                                    "lo": pt - pc - S.Z975 * se, "hi": pt - pc + S.Z975 * se},
                     "arms": [t_name, c_name], "n": [nt, nc]})


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("part")
    ap.add_argument("work")
    ap.add_argument("--reps", type=int, default=2000)
    a = ap.parse_args()
    work = Path(a.work).resolve()
    {"srm": lambda: part_srm(work), "m1": lambda: part_m1(work), "m2": lambda: part_m2(work),
     "m3": lambda: part_m3(work, a.reps), "m4": lambda: part_m4(work, a.reps), "m5": lambda: part_m5(work),
     "readout": lambda: part_readout(work)}[a.part]()


if __name__ == "__main__":
    main()
