"""Collect the part results into results/summary.json and score the predictions as declared.

Usage: python3 -I -B tools/summarize.py
"""
import json
import math
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import stats as S  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
R = ROOT / "results"
load = lambda n: json.loads((R / f"{n}.json").read_text(encoding="utf-8"))  # noqa: E731
srm, m1, m2, m3, m4, m5, bal = (load(n) for n in ("srm", "m1", "m2", "m3", "m4", "m5", "balance"))
PRED = json.loads((ROOT / "predictions-r1.json").read_text(encoding="utf-8"))["predictions"]
SEED = json.loads((ROOT / "protocol-r1.json").read_text(encoding="utf-8"))["seed"]

out = {}

# Peeking on real experiments, plus the hybrid read added after the results.
rows = m2["rows"]
tau = "msprt_0.01"
hyb_calls = hyb_unsup = hyb_reached = 0
for r in rows:
    if r[tau + "_call"]:
        hyb_calls += 1
        ok = r["final_sig"] and math.copysign(1, r["final_z"]) == r[tau + "_sign"]
        hyb_unsup += 0 if ok else 1
        hyb_reached += 1 if ok else 0
    elif r["final_sig"]:
        hyb_calls += 1
        hyb_reached += 1
out["peek"] = {"tests": m2["tests"], "pairs": srm["asos"]["pairs"], "experiments": len({r["key"].split("-")[0] for r in rows}),
               "naive": m2["naive"], "msprt": m2[tau], "msprt_sens": {k: m2[f"msprt_{k}"] for k in ("0.003", "0.03")},
               "final_sig": m2["naive"]["final_sig"],
               "hybrid": {"calls": hyb_calls, "unsupported": hyb_unsup, "final_reached": hyb_reached},
               "by_metric": m2["by_metric"]}
# Added after the results: the same tally without the arms the split check flagged.
flagged = {r["pair"] for r in srm["asos"]["rows"] if r["flag"]}
kept = [r for r in rows if "-".join(r["key"].split("-")[:2]) not in flagged]
k_calls = [r for r in kept if r["naive_call"]]
k_uns = [r for r in k_calls if (not r["final_sig"]) or math.copysign(1, r["final_z"]) != r["naive_sign"]]
m_calls = [r for r in kept if r[tau + "_call"]]
m_uns = [r for r in m_calls if (not r["final_sig"]) or math.copysign(1, r["final_z"]) != r[tau + "_sign"]]
out["peek"]["without_flagged"] = {"tests": len(kept), "naive_calls": len(k_calls), "naive_unsupported": len(k_uns),
                                  "msprt_calls": len(m_calls), "msprt_unsupported": len(m_uns)}
n = m2["tests"]
out["peek"]["dropped"] = m2["dropped"]
out["peek"]["tests_r1"] = n + m2["dropped"]
out["peek"]["per100"] = {"naive_unsupported": 100 * m2["naive"]["unsupported"] / n,
                         "msprt_unsupported": 100 * m2[tau]["unsupported"] / n,
                         "hybrid_unsupported": 100 * hyb_unsup / n}


# Change r2: a bootstrap over experiments (arms of one experiment stay together) for the share of calls that did not
# hold, on its own random stream.
def unsup_share(rs, prefix):
    calls = [r for r in rs if r[prefix + "_call"]]
    bad = [r for r in calls if (not r["final_sig"]) or math.copysign(1, r["final_z"]) != r[prefix + "_sign"]]
    return len(bad) / len(calls) if calls else float("nan")


by_exp = {}
for r in rows:
    by_exp.setdefault(r["key"].split("-")[0], []).append(r)
exps = sorted(by_exp)
brng = np.random.default_rng([SEED, 2])
boot = []
for _ in range(2000):
    pick = brng.integers(0, len(exps), len(exps))
    rs = [r for i in pick for r in by_exp[exps[i]]]
    a, b = unsup_share(rs, "naive"), unsup_share(rs, tau)
    boot.append((a, b, a - b))
boot = np.array(boot)
ci = lambda col: [float(np.nanpercentile(boot[:, col], 2.5)), float(np.nanpercentile(boot[:, col], 97.5))]  # noqa: E731
out["peek"]["share_ci"] = {"experiments": len(exps), "resamples": len(boot),
                           "naive": [unsup_share(rows, "naive")] + ci(0),
                           "msprt": [unsup_share(rows, tau)] + ci(1),
                           "difference": [unsup_share(rows, "naive") - unsup_share(rows, tau)] + ci(2)}

# A/A replay.
out["aa"] = {"reps": m3["reps"], "users_per_day": m3["criteo"]["users_per_day"], "days": 14,
             "visit": m3["criteo"]["visit"], "conversion": m3["criteo"]["conversion"], "retail": m3["retail"]}

# Ratio metric.
out["ratio"] = m4

# Variance reduction.
out["cuped"] = m1
cv = m1["criteo"]["visit"]
out["cuped_derived"] = {
    "criteo_visit_sample_cut": 1 - cv["n_per_arm_A"] / cv["n_per_arm_raw"],
    "criteo_visit_shift": 1 - cv["adjA"] / cv["raw"],
    "criteo_visit_shift_in_se": (cv["raw"] - cv["adjA"]) / cv["adjA_se"],
}

# Segments.
out["segments"] = {k: m5[k] for k in ("slices", "segments_defined", "naive", "holm", "bh")}
valid = [r for r in m5["whole"] if r["users"] > 0 and math.isfinite(r["z"])]
out["segments"]["valid_segments"] = len(valid)
top = max(valid, key=lambda r: r["effect"] if r["users"] / 13979592 >= 0.1 else -1)
out["segments"]["top"] = top
users_per_slice = [r["users"] for r in m5["rows"]]
out["segments"]["users_per_slice_min"] = min(users_per_slice)
out["segments"]["users_per_slice_max"] = max(users_per_slice)
out["segments"]["valid_per_slice"] = sorted({r["segments"] for r in m5["rows"]})

out["srm"] = {"criteo": srm["criteo"], "hillstrom": srm["hillstrom"],
              "asos_pairs": srm["asos"]["pairs"], "asos_flagged": srm["asos"]["flagged"],
              "asos_flagged_rows": [r for r in srm["asos"]["rows"] if r["flag"]]}
out["balance"] = bal

# Readout of the e-mail test, with the power the design asked for (5% relative lift on visits).
h = m1["hillstrom"]
hv, hs = h["visit"], h["spend"]
p0 = hv["mean_c"]
out["readout"] = {
    "visit": {"lift": hv["raw"], "lo": hv["raw"] - S.Z975 * hv["raw_se"], "hi": hv["raw"] + S.Z975 * hv["raw_se"],
              "base": p0, "relative": hv["raw"] / p0},
    "spend": {"lift": hs["raw"], "lo": hs["raw"] - S.Z975 * hs["raw_se"], "hi": hs["raw"] + S.Z975 * hs["raw_se"],
              "base": hs["mean_c"]},
    "n_t": hv["nt"], "n_c": hv["nc"],
    "n_per_arm_needed_5pct": S.n_per_arm(p0 * (1 - p0), 0.05 * p0),
    "mde_relative_at_this_n": (S.Z975 + S.Z80) * math.sqrt(2 * p0 * (1 - p0) / hv["nc"]) / p0,
}
cc = m1["criteo"]["conversion"]
out["readout_criteo"] = {
    "visit_raw": cv["raw"], "visit_raw_se": cv["raw_se"], "visit_adj": cv["adjA"], "visit_adj_se": cv["adjA_se"],
    "conv_raw": cc["raw"], "conv_raw_se": cc["raw_se"], "conv_adj": cc["adjA"], "conv_adj_se": cc["adjA_se"],
}

# Score the predictions exactly as declared.
def band(v, lo=None, hi=None):
    return (lo is None or v >= lo) and (hi is None or v <= hi)

naive_sh = m2["naive"]["unsupported"] / m2["naive"]["calls"]
ms_sh = m2[tau]["unsupported"] / m2[tau]["calls"]
ms_reach = m2[tau]["final_reached"] / m2[tau]["final_sig"]
nrep = m5["naive"]["share_replicated"]
hrep = m5["holm"]["share_replicated"]
score = {
    "P1": (cv["var_removed_A"], band(cv["var_removed_A"], 0.10, 0.40), cv["var_removed_A"] < 0.05),
    "P2": (cv["var_removed_B"] - cv["var_removed_A"], cv["var_removed_B"] - cv["var_removed_A"] >= 0.03,
           cv["var_removed_B"] <= cv["var_removed_A"]),
    "P3": (hs["var_removed_A"], hs["var_removed_A"] < 0.05, hs["var_removed_A"] >= 0.10),
    "P4": (naive_sh, band(naive_sh, 0.25, 0.50), naive_sh < 0.10),
    "P5": (ms_sh, ms_sh <= 0.10, ms_sh >= naive_sh),
    "P6": (ms_reach, band(ms_reach, 0.50, 0.85), ms_reach < 0.30),
    "P7": (m3["criteo"]["visit"]["naive"]["rate"], band(m3["criteo"]["visit"]["naive"]["rate"], 0.15, 0.25),
           m3["criteo"]["visit"]["naive"]["rate"] <= 0.08),
    "P8": (m3["criteo"]["visit"]["msprt"]["rate"], m3["criteo"]["visit"]["msprt"]["rate"] <= 0.05,
           m3["criteo"]["visit"]["msprt"]["rate"] > 0.08),
    "P9": (m4["four_weeks"]["revenue_per_order"]["naive"]["rate"],
           band(m4["four_weeks"]["revenue_per_order"]["naive"]["rate"], 0.10, 0.30),
           m4["four_weeks"]["revenue_per_order"]["naive"]["rate"] <= 0.07),
    "P10": (m4["four_weeks"]["revenue_per_order"]["delta"]["rate"],
            band(m4["four_weeks"]["revenue_per_order"]["delta"]["rate"], 0.03, 0.07),
            m4["four_weeks"]["revenue_per_order"]["delta"]["rate"] > 0.08),
    "P11": (nrep, nrep <= 0.50, nrep >= 0.80),
    "P12": (hrep, hrep >= 0.80, hrep <= nrep),
    "P13": (srm["asos"]["flagged"], (not srm["criteo"]["flag"]) and (not srm["hillstrom"]["flag"]) and srm["asos"]["flagged"] >= 1,
            srm["asos"]["flagged"] == 0),
}
pred = []
for p in PRED:
    v, hit, opp = score[p["id"]]
    pred.append({**p, "value": v, "outcome": "as expected" if hit else ("the opposite" if opp else "neither")})
out["predictions"] = pred
out["predictions_tally"] = {k: sum(1 for p in pred if p["outcome"] == k) for k in ("as expected", "the opposite", "neither")}

# Change r3: the sequential rule by metric, and calls made before the last snapshot only.
def bad(r, prefix):
    return (not r["final_sig"]) or math.copysign(1, r["final_z"]) != r[prefix + "_sign"]


out["peek"]["by_metric_both"] = {}
for m in (1, 2, 3, 4):
    sub = [r for r in rows if r["metric"] == m]
    d = {}
    for prefix, name in (("naive", "naive"), (tau, "msprt")):
        calls = [r for r in sub if r[prefix + "_call"]]
        d[name] = {"calls": len(calls), "unsupported": sum(1 for r in calls if bad(r, prefix))}
    out["peek"]["by_metric_both"][m] = d


def early(r, prefix):
    return r[prefix + "_call"] and r[prefix + "_day"] < r["days"] - 1e-9


def early_share(rs, prefix):
    calls = [r for r in rs if early(r, prefix)]
    return sum(1 for r in calls if bad(r, prefix)) / len(calls) if calls else float("nan")


ec = {name: [r for r in rows if early(r, prefix)] for prefix, name in (("naive", "naive"), (tau, "msprt"))}
erng = np.random.default_rng([SEED, 3])
eb = []
for _ in range(2000):
    pick = erng.integers(0, len(exps), len(exps))
    rs = [r for i in pick for r in by_exp[exps[i]]]
    a_, b_ = early_share(rs, "naive"), early_share(rs, tau)
    eb.append((a_, b_, a_ - b_))
eb = np.array(eb)
eci = lambda col: [float(np.nanpercentile(eb[:, col], 2.5)), float(np.nanpercentile(eb[:, col], 97.5))]  # noqa: E731
out["peek"]["before_last"] = {
    "naive": {"calls": len(ec["naive"]), "unsupported": sum(1 for r in ec["naive"] if bad(r, "naive")),
              "share": [early_share(rows, "naive")] + eci(0)},
    "msprt": {"calls": len(ec["msprt"]), "unsupported": sum(1 for r in ec["msprt"] if bad(r, tau)),
              "share": [early_share(rows, tau)] + eci(1)},
    "difference": [early_share(rows, "naive") - early_share(rows, tau)] + eci(2)}

# Headline rule, as declared: most calls changed per 100 decisions among peeking, ratio metric and segments.
cands = {"peeking": out["peek"]["per100"]["naive_unsupported"],
         "ratio": 100 * (m4["four_weeks"]["revenue_per_order"]["naive"]["rate"] - m4["four_weeks"]["revenue_per_order"]["delta"]["rate"]),
         "segments": 100 * (1 - nrep) * m5["naive"]["flagged"] / (m5["slices"] * m5["segments_defined"])}
out["headline_rule"] = {"per100": cands, "winner": max(cands, key=cands.get)}
# Change r2: like for like, the peeking figure as a difference (daily check minus sequential rule), as the per-order one is.
like = dict(cands, peeking=out["peek"]["per100"]["naive_unsupported"] - out["peek"]["per100"]["msprt_unsupported"])
out["headline_rule"]["like_for_like"] = {"per100": like, "winner": max(like, key=like.get)}
(R / "summary.json").write_text(json.dumps(out, indent=1, sort_keys=True), encoding="utf-8")
print("predictions:", out["predictions_tally"])
for p in pred:
    print(p["id"], p["outcome"], round(p["value"], 4) if isinstance(p["value"], float) else p["value"])
print("headline rule:", {k: round(v, 1) for k, v in cands.items()}, "->", out["headline_rule"]["winner"])
print("like for like:", {k: round(v, 1) for k, v in like.items()}, "->", out["headline_rule"]["like_for_like"]["winner"])
print("share ci", {k: [round(x, 3) for x in v] for k, v in out["peek"]["share_ci"].items() if isinstance(v, list)})
print("by metric", out["peek"]["by_metric_both"])
print("before last", {k: v for k, v in out["peek"]["before_last"].items()})
print("per100", {k: round(v, 2) for k, v in out["peek"]["per100"].items()}, "tests", n, "dropped", m2["dropped"])
print("hybrid", out["peek"]["hybrid"], "readout", {k: out["readout"][k] for k in ("n_per_arm_needed_5pct", "mde_relative_at_this_n")})
print("top segment", top)
