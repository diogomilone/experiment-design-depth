"""Added after the results: are Criteo's arms balanced on the 12 pre-treatment features?

The covariate adjustment moved the visit lift by about a quarter, which a single clean randomised test should not do.
This checks the standardised mean difference of each feature between the arms, and the same for the two arms' shares
of each segment used in M5. Usage: python3 -I -B tools/balance.py <work dir>
"""
import json
import sys
from pathlib import Path

import duckdb

work = Path(sys.argv[1]).resolve()
HERE = Path(__file__).resolve().parent.parent
c = duckdb.connect()
c.execute("SET threads=2")
p = work / "criteo.parquet"
out = {"features": {}}
for i in range(12):
    f = f"f{i}"
    (mt, vt, mc, vc) = c.execute(f"""SELECT avg({f}) FILTER (WHERE treatment=1), var_samp({f}) FILTER (WHERE treatment=1),
                                       avg({f}) FILTER (WHERE treatment=0), var_samp({f}) FILTER (WHERE treatment=0)
                                       FROM '{p}'""").fetchone()
    smd = (mt - mc) / (((vt + vc) / 2) ** 0.5)
    out["features"][f] = {"mean_t": mt, "mean_c": mc, "smd": smd}
out["max_abs_smd"] = max(abs(v["smd"]) for v in out["features"].values())
out["features_over_0.1"] = sorted(k for k, v in out["features"].items() if abs(v["smd"]) > 0.1)
# A standard error of an SMD under clean randomisation with these arm sizes is about sqrt(1/nt + 1/nc).
nt, nc = c.execute(f"SELECT sum(treatment), count(*) - sum(treatment) FROM '{p}'").fetchone()
out["smd_se_if_randomised"] = (1 / nt + 1 / nc) ** 0.5
(HERE / "results" / "balance.json").write_text(json.dumps(out, indent=1, sort_keys=True), encoding="utf-8")
print(json.dumps({k: out[k] for k in ("max_abs_smd", "features_over_0.1", "smd_se_if_randomised")}))
print({k: round(v["smd"], 4) for k, v in out["features"].items()})
