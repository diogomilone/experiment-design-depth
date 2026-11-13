# Design, round 1: which experiment design choices change the call, and by how much

Committed before any scored run. Anything decided after the results is labelled "added after the results" on the page.

## Question

Not "how do I read one test" (the older `experiment-readout` and `marketplace-experiments` studies answer that on one
simulated ride-hailing market) but: on real experiment data, which of five common design choices changes the ship or
no-ship call, and by how much? Each choice is measured against the default a practitioner would use.

## Data (all public; licences in README.md)

| Set | What it is | Used for |
|---|---|---|
| Criteo uplift v2.1 | 13,979,592 users from randomised advertising incrementality tests, 85% treated; 12 pre-treatment features; visit and conversion | variance reduction, segment effects, the A/A replay, sample-ratio check |
| ASOS Digital Experiments | 99 real experiment-variant pairs from 78 online experiments, 4 metrics, cumulative counts, means and variances every half day | peeking against a sequential rule, sample-ratio check |
| Online Retail II (UCI) | 1,067,371 invoice lines of a UK online store, real customers, real dates, repeat orders | per-order ratio metric (arms assigned at random to customers: an A/A test) |
| MineThatData e-mail test | 64,000 customers in three randomised arms, with pre-period spend | classic variance reduction with a pre-period metric, sample-ratio check |

## The five measurements, each with its default

M1. Variance reduction. Default: compare raw means. Alternative: regression adjustment on pre-treatment data
(CUPED with covariates, separate slopes per arm). Criteo: outcome visit (primary), conversion (secondary); adjustment
A = the 12 features, linear; adjustment B = a cross-fitted prediction from the 12 features cut into 20 quantile bins each
(additive), used as one covariate. MineThatData: outcome visit and spend, women's e-mail against no e-mail; adjustment
A = pre-period spend alone (classic CUPED); B = all pre-period fields. Reported: the share of variance removed, which
is the share of sample the test no longer needs at equal power; and the users needed per arm for 80% power at a 5%
relative lift on visit, two-sided 5%.

M2. Peeking on real experiments (ASOS). Default: look every day, ship at the first two-sided p < 0.05 (Welch z on the
cumulative means). Alternative: a mixture sequential probability ratio test (mSPRT), always-valid, stop when the
likelihood ratio reaches 1/alpha = 20; mixture scale tau = 0.01 pooled standard deviations (sensitivity 0.003 and
0.03). Looks at whole days only. Reference: the two-sided test at the last snapshot. Counted per pair and metric: calls
by each rule, calls the final test does not support (final p >= 0.05 or opposite sign), and the share of final-sample
significant results each rule reaches. Pairs and metrics with zero variance in either arm at the last snapshot are
dropped and counted.

M3. A/A replay (the follow-up). Criteo, all users, one seeded random arrival order cut into 14 equal days. Each of
2,000 replications relabels every user to A or B with probability 1/2 (done exactly by a binomial draw of each day's
arm size and a hypergeometric draw of its successes; a test checks it against explicit relabelling). Metrics visit
and conversion. Reported: false-positive rate of the daily naive peek, the fixed-horizon test at day 14, and the mSPRT,
with 95% Wilson intervals. Secondary: the same on Online Retail II with real days (28) and revenue per customer,
explicit relabelling, 2,000 replications.

M4. Ratio metric (Online Retail II). Window: four weeks, 2011-10-03 to 2011-10-30; customers with an id; invoices
whose number starts with C (cancellations) dropped; order = invoice. Metrics revenue per order and units per order.
Unit of randomisation: the customer. Default: a t-test on order-level values, as if orders were independent.
Alternative: the delta method on customer-level sums. 2,000 random 50/50 relabelings of customers. Reported: false-positive
rate at 5% for each, median ratio of the naive standard error to the delta-method one. Sensitivity: a twelve-week
window ending 2011-10-30. Check: on Criteo, conversion per visit (each user visits at most once in the data) the two
intervals must coincide.

M5. Segment effects (Criteo, visit). Segments: each feature cut at its 20th, 40th, 60th and 80th percentiles (ties may
leave fewer bins); each bin is a segment tested against the rest of the users (difference of the two arm differences,
z-test). Default: report every segment with p < 0.05. Alternatives: Holm at 5% and Benjamini-Hochberg at 5%. Discovery
on 28 disjoint random slices of the users (about 500,000 each); for each slice, a flagged segment replicates if the
same comparison on the other 27 slices has the same sign and p < 0.05. Reported per rule: segments flagged per slice and
the share that replicate.

Pre-checks: sample-ratio mismatch (chi-square, flag at p < 0.001) on Criteo against its stated 0.85, MineThatData
against equal thirds, ASOS pairs against 1:1 at the last snapshot. Guardrail in the decision rule: conversion may not
fall by more than its own 95% interval allows below zero.

## Headline rule (declared now)

The headline is the measurement whose design choice changes the most calls per 100 decisions, among M2 (naive-peek
calls the full sample does not support), M4 (extra false positives of the naive interval) and M5 (flagged segments that
do not replicate). M1 is reported as sample saved; M3 is excluded from the headline because its size is set mostly by
the number of looks the replay chose.

## Limits known in advance

Criteo's data were sub-sampled non-uniformly by the publisher, so its effect sizes are not a real campaign's. ASOS
metrics are anonymised, so their direction (good or bad) is unknown and "a call" means "a significant difference".
The ratio-metric test is an A/A test on a store with no experiment. One arrival order for the Criteo replay.
