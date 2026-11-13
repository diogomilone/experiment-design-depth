# Experiment design: which choices change the call

On real experiment data, which common design choices change a ship or no-ship call, and by how much? This study
measures five: stopping at the first significant daily check against a sequential rule, adjusting for pre-test data
(CUPED with covariates), the unit of a per-order metric (the delta method), correcting segment cuts for how many were
tried, and the sample-ratio check. The follow-up is a relabelling replay (an A/A test) that measures each stopping
rule's false alarms on 14 million real users. The pages are `index.html` (entry), `peeking.html`,
`design-choices.html` and `method.html`.

## Data

None of the data files is copied here. Each is fetched from its publisher; sha256 of the files used:

- Criteo uplift prediction dataset, version 2.1 (Criteo AI Lab; Diemert, Betlei, Renaudin and Amini, "A Large Scale
  Benchmark for Uplift Modeling", 2018). 13,979,592 users, file `criteo-research-uplift-v2.1.csv.gz` from
  https://huggingface.co/datasets/criteo/criteo-uplift (the publisher's own copy), sha256
  `2716e1bf0fd157a93b5bf86924d9088419dfbac2022c6cd90030220634f616dc`. Licence CC BY-NC-SA 4.0: non-commercial use only,
  so this study is shared under the same terms.
- ASOS Digital Experiments Dataset (C. H. Bryan Liu and others, Imperial College London and ASOS.com),
  https://osf.io/64jsb/, file `asos_digital_experiments_dataset.csv`, sha256
  `aa0cc3f8304fac545f232ec0bc363373f932919f6e72e28908958bc10651ce22`. Licence CC BY 4.0.
- Online Retail II (Daqing Chen, UCI Machine Learning Repository), https://archive.ics.uci.edu/dataset/502/online+retail+ii,
  file `online+retail+ii.zip`, sha256 `572e36277c2390fbfde10664750731e0a86f55e33470d91919085f0408e67bfb`. Licence CC BY 4.0.
- MineThatData e-mail analytics challenge (Kevin Hillstrom, 2008),
  http://www.minethatdata.com/Kevin_Hillstrom_MineThatData_E-MailAnalytics_DataMiningChallenge_2008.03.20.csv, sha256
  `0e5893329d8b93cefecc571777672028290ab69865718020c78c7284f291aece`. Shared publicly for analysis; credited here and not
  redistributed.

## Reproduce

Python 3.12 with DuckDB 2.0, NumPy 2.5, SciPy 1.18 and openpyxl 3.1. Put the four files in `<raw>/criteo/`,
`<raw>/asos/`, `<raw>/retail/` (unzipped) and `<raw>/hillstrom/` (file names `criteo-research-uplift-v2.1.csv.gz`,
`asos_digital_experiments_dataset.csv`, `online_retail_II.xlsx`, `hillstrom.csv`), then:

```
python3 -I -B tools/prepare.py <raw> <work>
python3 -B tests/test_stats.py
python3 -I -B tools/run_study.py srm <work>
python3 -I -B tools/run_study.py m1 <work>
python3 -I -B tools/run_study.py m2 <work>
python3 -I -B tools/run_study.py m3 <work>
python3 -I -B tools/run_study.py m4 <work>
python3 -I -B tools/run_study.py m5 <work>
python3 -I -B tools/run_study.py readout <work>
python3 -I -B tools/balance.py <work>
python3 -I -B tools/matched_bar.py <work>
python3 -I -B tools/look1_check.py <work>
python3 -I -B tools/summarize.py
python3 -I -B site/render.py
```

Every random draw uses the seed in `protocol-r1.json`, so the results reproduce exactly. Large files are
read in chunks of one million rows through DuckDB, never whole.

## Files

- `DESIGN-r1.md`, `protocol-r1.json`, `predictions-r1.json`: the design, the frozen settings and the 13 predictions,
  committed before the first scored run.
- `results/r1-summary.json`, `results/r3-summary.json`, `results/r3-m2.json`: the results before each change listed on
  the method page, kept beside the current ones.
- `tools/stats.py`: the tests and estimators (Welch test, mixture sequential test, delta method, adjustment, Holm and
  Benjamini-Hochberg). `tools/run_study.py`: one part per command, each writing `results/<part>.json`.
  `tools/balance.py`: the balance check on the Criteo arms, added after the results. `tools/matched_bar.py`: the
  daily check at a fixed bar as strict as the sequential rule, added after the results. `tools/summarize.py`: collects
  `results/summary.json` and scores the predictions as declared.
- `assumptions.json`: the assumed money figures behind "What it is worth". None comes from the data.
- `site/render.py`, `site/page.css`: the four pages. Every number comes from `results/` or `assumptions.json`.
- `vendor/viz-design-system/`: the chart kit (version 2.3.0) with its licences.

## What was chosen after the results

Each of these is labelled "added after the results" or "chosen after the results" wherever it appears:

- the combined stopping rule (sequential rule for early stops, one fixed test at the planned end);
- the balance check on the Criteo arms;
- making the no-effect replay the main result;
- the daily check at a fixed bar as strict as the sequential rule (`results/m2_matched.json`);
- the e-mail test read as one test from plan to ship call;
- the peeking tally without the arms the split check flagged;
- the first look of the replay under ten other seeds (`tools/look1_check.py`);
- the changes listed on the method page: the daily look taken at the first snapshot of each day, so series recorded at
  half-day offsets are read too; dropping the 15 peeking series that carry no variances (as the design already said
  for series with zero variance), the money figure counted per test with an assumed share of ships, the sequential
  rule's false alarms by look and the combined rule with its end test at 4.5%, an interval for the share of calls that
  did not hold resampling whole experiments, a unit test of the sequential rule with the variance estimated at each
  look, and stopping compared with the per-order unit like for like;
- the sequential rule's calls by metric, the shares counting only calls before the last
  snapshot with their own interval, and the money figure as a gross cost scenario with a range on the assumed share of
  ships.

The sequential rule plugs in the observed variances and sets its mixing scale from the observed spread at each look.
That is a large-sample approximation of a rule whose guarantee assumes both known, so its false alarms are measured
(the relabelling replay and the unit test) rather than assumed.
