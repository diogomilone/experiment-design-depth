"""Change r5: a daily usual test with a constant bar as strict as the sequential rule (matched on its number of calls).

Usage: python3 -I -B tools/matched_bar.py <work dir>
Same series, drops and looks as M2 (the first snapshot of each elapsed day). The bar c is the smallest value on a grid
from 1.96 in steps of 0.01 at which the number of calls is at most the sequential rule's. Writes results/m2_matched.json.
"""
import json
import math
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import run_study as RS  # noqa: E402

S = RS.S
BOOT_SEED, BOOT_REPS = 20261111, 2000


def load(work):
    c = RS.con()
    rows = c.execute(f"""SELECT experiment_id, variant_id, metric_id, time_since_start, count_c, count_t,
                         mean_c, mean_t, variance_c, variance_t FROM '{work / 'asos.parquet'}'
                         ORDER BY 1, 2, 3, 4""").fetchall()
    series = {}
    for r in rows:
        series.setdefault((r[0], r[1], r[2]), []).append(r[3:])
    out = []
    for key, s in series.items():
        s = np.asarray(s, dtype=float)
        t, nc, nt, mc, mt, vc, vt = s.T
        last = np.array([vc[-1], vt[-1], nc[-1], nt[-1]])
        if not np.isfinite(last).all() or vc[-1] <= 0 or vt[-1] <= 0 or nc[-1] < 2 or nt[-1] < 2:
            continue
        diff = mt - mc
        v = vc / nc + vt / nt
        ok = (vc > 0) & (vt > 0) & (nc > 1) & (nt > 1)
        z = np.where(ok, diff / np.sqrt(np.where(ok, v, 1)), 0.0)
        dnum = np.floor(t + 1e-6)
        first = np.ones(len(t), dtype=bool)
        first[1:] = dnum[1:] != dnum[:-1]
        day = ok & first & (dnum >= 1)
        fz = z[-1]
        out.append({"key": f"{key[0]}-{key[1]}-m{key[2]}", "metric": int(key[2]), "z": z[day], "final_z": float(fz),
                    "final_sig": bool(S.two_sided_p(np.array([fz]))[0] < RS.ALPHA)})
    return out


def calls_at(series, c):
    res = []
    for r in series:
        hit = np.nonzero(np.abs(r["z"]) >= c)[0]
        call = bool(len(hit))
        sign = int(np.sign(r["z"][hit[0]])) if call else 0
        bad = call and ((not r["final_sig"]) or math.copysign(1, r["final_z"]) != sign)
        reached = call and r["final_sig"] and math.copysign(1, r["final_z"]) == sign
        res.append({"key": r["key"], "metric": r["metric"], "call": call, "bad": bool(bad), "reached": bool(reached)})
    return res


def tally(res):
    calls = sum(r["call"] for r in res)
    bad = sum(r["bad"] for r in res)
    return {"calls": calls, "unsupported": bad, "final_reached": sum(r["reached"] for r in res),
            "share": bad / calls if calls else float("nan")}


def main():
    work = Path(sys.argv[1])
    m2 = json.loads((RS.RES / "m2.json").read_text(encoding="utf-8"))
    series = load(work)
    assert [r["key"] for r in series] == [r["key"] for r in m2["rows"]], "series differ from M2"
    target = m2["msprt_0.01"]["calls"]
    # Sanity: at the usual bar the constant-bar rule is the daily usual test, so it must reproduce M2's counts.
    z975 = 1.959963984540054
    base = tally(calls_at(series, z975))
    assert (base["calls"], base["unsupported"]) == (m2["naive"]["calls"], m2["naive"]["unsupported"]), base
    c = 1.96
    while tally(calls_at(series, c))["calls"] > target:
        c = round(c + 0.01, 2)
    res = calls_at(series, c)
    seq = {r["key"]: r for r in m2["rows"]}
    tau = "msprt_0.01"

    def seq_bad(k):
        r = seq[k]
        return r[tau + "_call"] and ((not r["final_sig"]) or math.copysign(1, r["final_z"]) != r[tau + "_sign"])

    by_exp = {}
    for r in res:
        by_exp.setdefault(r["key"].split("-")[0], []).append(r)
    exps = sorted(by_exp)
    rng = np.random.default_rng(BOOT_SEED)
    boot = []
    for _ in range(BOOT_REPS):
        pick = rng.integers(0, len(exps), len(exps))
        rs = [r for i in pick for r in by_exp[exps[i]]]
        mc = sum(r["call"] for r in rs)
        mb = sum(r["bad"] for r in rs)
        sc = sum(seq[r["key"]][tau + "_call"] for r in rs)
        sb = sum(seq_bad(r["key"]) for r in rs)
        a = mb / mc if mc else float("nan")
        b = sb / sc if sc else float("nan")
        boot.append((a, b, a - b))
    boot = np.array(boot)
    ci = lambda col: [float(np.nanpercentile(boot[:, col], 2.5)), float(np.nanpercentile(boot[:, col], 97.5))]  # noqa: E731
    mt = tally(res)
    sq = m2[tau]
    sq_share = sq["unsupported"] / sq["calls"]
    out = {"bar_z": c, "bar_p": float(S.two_sided_p(np.array([c]))[0]), "target_calls": target,
           "matched": mt, "msprt": {"calls": sq["calls"], "unsupported": sq["unsupported"],
                                    "final_reached": sq["final_reached"], "share": sq_share},
           "naive_check": base,
           "by_metric": {m: tally([r for r in res if r["metric"] == m]) for m in (1, 2, 3, 4)},
           "share_ci": {"experiments": len(exps), "resamples": BOOT_REPS, "seed": BOOT_SEED,
                        "matched": [mt["share"]] + ci(0), "msprt": [sq_share] + ci(1),
                        "difference": [mt["share"] - sq_share] + ci(2)},
           "predictions": {"Q1": mt["share"] < base["share"], "Q2": sq_share <= mt["share"] - 0.05}}
    p = RS.RES / "m2_matched.json"
    p.write_text(json.dumps(out, indent=1, sort_keys=True), encoding="utf-8")
    print("wrote", p)
    print(json.dumps({k: out[k] for k in ("bar_z", "bar_p", "matched", "msprt", "share_ci", "predictions")}))


if __name__ == "__main__":
    main()
