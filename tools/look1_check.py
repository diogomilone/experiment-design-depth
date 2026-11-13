"""Added after the results: is the replay's low first-look false-alarm rate (visits) a property of the data or of the draw?

Same arrival order and day totals as tools/run_study.py m3; the relabelling repeated with ten other seeds (0 to 9).
Usage: python3 -I -B tools/look1_check.py <work dir>
"""
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import run_study as R  # noqa: E402

work = Path(sys.argv[1]).resolve()
days = R.PROTO["M3_aa_replay"]["days"]
reps = R.PROTO["M3_aa_replay"]["replications"]
rng = np.random.default_rng(R.SEED)
N = 13979592
day_of = (rng.permutation(N) * days // N).astype(np.int64)
n_d, s_d = np.zeros(days), np.zeros(days)
for d in R.criteo_chunks(work, ["visit"]):
    dd = day_of[d["rid"]]
    n_d += np.bincount(dd, minlength=days)
    s_d += np.bincount(dd, weights=d["visit"].astype(float), minlength=days)
n_d, s_d = n_d.astype(np.int64), s_d.astype(np.int64)
study = R.aa_binary(n_d, s_d, reps, rng, 0.01)
other = [R.aa_binary(n_d, s_d, reps, np.random.default_rng(k), 0.01) for k in range(10)]
out = {"study_seed_first_look": study["naive_by_look"][0], "study_seed_all_looks": float(study["naive"].mean()),
       "other_seeds_first_look": [o["naive_by_look"][0] for o in other],
       "other_seeds_all_looks": [float(o["naive"].mean()) for o in other]}
(R.RES / "look1-check.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
print(json.dumps(out))
