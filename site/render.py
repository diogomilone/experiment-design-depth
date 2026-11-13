"""Render the four pages: index.html (entry), peeking.html, design-choices.html and method.html.

Every number comes from results/ or assumptions.json, and the claims the text makes are asserted here, so a change in
the results fails the build instead of leaving the text stale. After writing, every number in each page's visible text
is checked against the numbers this file formatted (or a short list of literal constants), and the check is written to
_private/checks/numbers-r1.txt when that folder exists.
Usage: python3 -I -B site/render.py
"""
import html
import json
import math
import re
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
S = json.loads((ROOT / "results" / "summary.json").read_text(encoding="utf-8"))
RO = json.loads((ROOT / "results" / "readout.json").read_text(encoding="utf-8"))
L1 = json.loads((ROOT / "results" / "look1-check.json").read_text(encoding="utf-8"))
R1 = json.loads((ROOT / "results" / "r1-summary.json").read_text(encoding="utf-8"))
R3 = json.loads((ROOT / "results" / "r3-summary.json").read_text(encoding="utf-8"))
MB = json.loads((ROOT / "results" / "m2_matched.json").read_text(encoding="utf-8"))
_M2 = {x["key"]: x for x in json.loads((ROOT / "results" / "m2.json").read_text(encoding="utf-8"))["rows"]}
_M2R3 = {x["key"]: x for x in json.loads((ROOT / "results" / "r3-m2.json").read_text(encoding="utf-8"))["rows"]}
AS = json.loads((ROOT / "assumptions.json").read_text(encoding="utf-8"))
CSS = (ROOT / "site" / "page.css").read_text(encoding="utf-8")
STUDY_TITLE = "Experiment design: which choices change the call"
BASE_URL = "https://diogotravassos.dev/experiment-design-depth/"
MINUS = "−"
SEEN = set()


def e(t):
    return html.escape(str(t), quote=True)


def reg(s):
    for tok in re.findall(r"\d[\d,]*(?:\.\d+)?", s):
        SEEN.add(tok.replace(",", ""))
    return s


def num(v, d=0):
    return reg(f"{v:,.{d}f}")


def pct(v, d=0):
    return reg(f"{100 * v:.{d}f}") + "%"


def pts(v, d=2):
    """A difference of two rates, in percentage points."""
    return reg(f"{100 * v:.{d}f}")


def usd(v):
    if v >= 1e6:
        return "US$" + reg(f"{v / 1e6:.1f}") + " million"
    return "US$" + reg(f"{v:,.0f}")


def round_to(v, step):
    return step * round(v / step)


# ---------------------------------------------------------------- numbers the text rests on
P = S["peek"]
NV, SQ, HY = P["naive"], P["msprt"], P["hybrid"]
FIN = P["final_sig"]
TESTS, PAIRS = P["tests"], P["pairs"]
AA = S["aa"]
AV, AC, AR = AA["visit"], AA["conversion"], AA["retail"]
RA = S["ratio"]
R4, R12 = RA["four_weeks"], RA["twelve_weeks"]
CV = S["cuped"]["criteo"]["visit"]
CC = S["cuped"]["criteo"]["conversion"]
HV, HS = S["cuped"]["hillstrom"]["visit"], S["cuped"]["hillstrom"]["spend"]
CD = S["cuped_derived"]
SG = S["segments"]
BAL = S["balance"]
RD = S["readout"]
SRM = S["srm"]
PRED = S["predictions"]
TALLY = S["predictions_tally"]

assert (NV["calls"], NV["unsupported"]) == (219, 117) and (SQ["calls"], SQ["unsupported"]) == (91, 27)
assert TESTS == 381 and PAIRS == 99 and FIN == 105 and P["dropped"] == 15 and P["tests_r1"] == R1["peek"]["tests"] == 396
assert S["headline_rule"]["winner"] == "peeking" and S["headline_rule"]["like_for_like"]["winner"] == "peeking"
assert L1["study_seed_first_look"] == AV["naive_by_look"][0] and min(L1["other_seeds_all_looks"]) > 0.15
assert AV["naive"]["rate"] > 3 * AV["fixed"]["rate"] and AV["msprt"]["rate"] < 0.01
assert R4["revenue_per_order"]["naive"]["rate"] > 0.2 and R4["revenue_per_order"]["delta"]["hi"] > 0.05 > R4["revenue_per_order"]["delta"]["lo"]
assert 0.25 < CD["criteo_visit_sample_cut"] < 0.30 and 0.75 < CD["criteo_visit_sample_cut"] * AS["test_weeks"]["value"] < 1.5
assert SG["naive"]["share_replicated"] > 0.99 and SG["holm"]["share_replicated"] == 1.0
assert RO["conversion"]["lo"] > 0 and RD["visit"]["lo"] > 0 and RD["spend"]["lo"] > 0 and not SRM["hillstrom"]["flag"]

TESTS_R1, DROPPED = P["tests_r1"], P["dropped"]
per100_naive = P["per100"]["naive_unsupported"]
per100_seq = P["per100"]["msprt_unsupported"]
assert per100_seq == P["per100"]["hybrid_unsupported"] and SQ["unsupported"] == HY["unsupported"]
r1_naive, r1_seq = R1["peek"]["per100"]["naive_unsupported"], R1["peek"]["per100"]["msprt_unsupported"]
avoided = (per100_naive - per100_seq) / 100 * AS["tests_per_year"]["value"]
assert round(avoided) == 24
ships = avoided * AS["ship_share"]["value"]
worth = ships * AS["cost_wrong_ship_usd"]["value"]
worth_lo = avoided * AS["ship_share"]["low"] * AS["cost_wrong_ship_usd"]["low"]
worth_hi = avoided * AS["ship_share"]["high"] * AS["cost_wrong_ship_usd"]["high"]
BL, BM = P["before_last"], P["by_metric_both"]
assert BL["naive"]["unsupported"] == NV["unsupported"] and BL["msprt"]["calls"] == SQ["calls"]
assert all(d["msprt"]["unsupported"] / d["msprt"]["calls"] < d["naive"]["unsupported"] / d["naive"]["calls"]
           for d in BM.values()) and BL["difference"][1] > 0
replay_gap = 100 * (AV["naive"]["rate"] - AV["msprt"]["rate"])
end_calls = HY["calls"] - SQ["calls"]
assert end_calls == HY["final_reached"] - SQ["final_reached"]
CI = P["share_ci"]
assert CI["difference"][1] > 0 and CI["experiments"] == P["experiments"]
HR = S["headline_rule"]
LFL = HR["like_for_like"]["per100"]
r12_gap = 100 * (R12["revenue_per_order"]["naive"]["rate"] - R12["revenue_per_order"]["delta"]["rate"])
look1_se = (0.05 - L1["study_seed_first_look"]) / math.sqrt(0.05 * 0.95 / AA["reps"])
assert look1_se > 3
AH = AV["hybrid_045"]
assert AH["rate"] <= 0.05 and AC["hybrid_045"]["rate"] <= 0.05 and AV["msprt_by_look"][-1] == AV["msprt"]["rate"]
seq_hold = 1 - SQ["unsupported"] / SQ["calls"]
nv_hold = 1 - NV["unsupported"] / NV["calls"]
weeks_saved = CD["criteo_visit_sample_cut"] * AS["test_weeks"]["value"]
smd_mult = BAL["max_abs_smd"] / BAL["smd_se_if_randomised"]
planned = [r for r in SRM["asos_flagged_rows"] if abs(r["share_t"] - 0.5) > 0.1]
close = [r for r in SRM["asos_flagged_rows"] if abs(r["share_t"] - 0.5) <= 0.1]
far_close = max(abs(r["share_t"] - 0.5) for r in close)
top = SG["top"]
top_share = top["users"] / (CV["nt"] + CV["nc"])
ret = R4["revenue_per_order"]
WF = P["without_flagged"]
# Change r5: a daily usual test at a fixed bar as strict as the sequential rule (matched on its calls).
MT, MCI = MB["matched"], MB["share_ci"]
assert MT["calls"] <= SQ["calls"] and MB["msprt"]["unsupported"] == SQ["unsupported"]
assert MCI["difference"][1] < 0 < MCI["difference"][2] and MB["predictions"] == {"Q1": True, "Q2": False}
miss_seq, miss_nv = FIN - SQ["final_reached"], FIN - NV["final_reached"]
missed_extra = (NV["final_reached"] - SQ["final_reached"]) / TESTS * AS["tests_per_year"]["value"]
offset = missed_extra * AS["ship_share"]["value"] * AS["cost_wrong_ship_usd"]["value"]
assert round(missed_extra) == 10 and offset < worth
# Change r4: the daily look moved from whole-day snapshots to the first snapshot of each day.
R3P = R3["peek"]
R3N, R3S = R3P["naive"], R3P["msprt"]
assert (R3N["calls"], R3N["unsupported"], R3S["calls"], R3S["unsupported"]) == (158, 80, 71, 22)
NOLOOK = sum(1 for x in _M2R3.values() if x["looks"] == 0)
WHOLE = [k for k, x in _M2R3.items() if x["looks"] > 0]
MOVED_LOOKS = sum(_M2[k]["looks"] != _M2R3[k]["looks"] for k in WHOLE)
MOVED_CALLS = sum(any(_M2[k].get(f) != _M2R3[k].get(f) for f in ("naive_call", "naive_day", "msprt_0.01_call"))
                  for k in WHOLE)
assert NOLOOK == 96 and len(WHOLE) == 285 and min(x["looks"] for x in _M2.values()) > 0 and len(_M2) == TESTS
r3_naive, r3_seq = R3P["per100"]["naive_unsupported"], R3P["per100"]["msprt_unsupported"]
BMG = {m: 100 * (d["naive"]["unsupported"] / d["naive"]["calls"] - d["msprt"]["unsupported"] / d["msprt"]["calls"])
       for m, d in BM.items()}
gap_lo, gap_hi = min(BMG.values()), max(BMG.values())
assert gap_lo > 0 and min(BMG, key=BMG.get) == "2"
P6, P6R3 = (next(p for p in L if p["id"] == "P6") for L in (PRED, R3["predictions"]))
assert P6["outcome"] == "as expected" and P6R3["outcome"] == "neither"
assert [p["id"] for p, q in zip(PRED, R3["predictions"]) if p["outcome"] != q["outcome"]] == ["P6"]
assert S["headline_rule"]["like_for_like"]["per100"]["peeking"] > S["headline_rule"]["like_for_like"]["per100"]["ratio"]
# Integers the text uses straight from the results (registered for the number check).
for _v in ([TESTS, PAIRS, FIN, AA["reps"], AA["days"], AR["days"], AR["customers"], P["experiments"], SG["slices"],
           SG["slices"] - 1, SG["valid_per_slice"][0], R4["orders_per_customer_max"], NV["opposite_sign"],
           P["msprt_sens"]["0.003"]["calls"], P["msprt_sens"]["0.003"]["unsupported"], P["msprt_sens"]["0.03"]["calls"],
           P["msprt_sens"]["0.03"]["unsupported"], SRM["asos_flagged"], len(planned), len(close), len(PRED),
           TALLY["as expected"], TALLY["the opposite"], TALLY["neither"], RA["reps"], HY["calls"], HY["unsupported"],
           HY["final_reached"], NV["calls"], NV["unsupported"], SQ["calls"], SQ["unsupported"], NV["final_reached"],
           SQ["final_reached"], AS["tests_per_year"]["value"], AS["test_weeks"]["value"], AS["engineer_weeks"]["value"], AS["analyst_weeks"]["value"],
           TESTS_R1, DROPPED, end_calls, CI["experiments"], BL["naive"]["calls"], NV["calls"] - BL["naive"]["calls"],
           NOLOOK, len(WHOLE), MOVED_LOOKS, MOVED_CALLS, R3N["calls"], R3N["unsupported"], R3S["calls"],
           R3S["unsupported"], AA["reps"], 500000, MT["calls"], MT["unsupported"], MT["final_reached"], miss_seq,
           miss_nv]
           + [d[k][f] for d in BM.values() for k in ("naive", "msprt") for f in ("calls", "unsupported")]
           + list(WF.values())
           + [d[k] for d in P["by_metric"].values() for k in ("naive_calls", "naive_unsupported", "final_sig")]):
    reg(f"{_v:,}")

# ---------------------------------------------------------------- shared page parts
HEAD = ('<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,'
        'initial-scale=1"><meta name="color-scheme" content="light dark"><meta name="robots" content="noindex">'
        '<meta name="description" content="{desc}"><title>{title}</title><link rel="icon" href="data:,">'
        '<link rel="preload" href="vendor/viz-design-system/assets/fonts/newsreader-latin-500-normal.woff2" as="font" type="font/woff2" crossorigin>'
        '<link rel="preload" href="vendor/viz-design-system/assets/fonts/public-sans-latin-400-normal.woff2" as="font" type="font/woff2" crossorigin>'
        '<link rel="preload" href="vendor/viz-design-system/assets/fonts/public-sans-latin-600-normal.woff2" as="font" type="font/woff2" crossorigin>'
        '<link rel="stylesheet" href="vendor/viz-design-system/tokens.css"><link rel="stylesheet" href="vendor/viz-design-system/kit/kit.css">'
        '<link rel="stylesheet" href="vendor/viz-design-system/kit/takeaway.css"><link rel="stylesheet" href="vendor/viz-design-system/kit/wayfinding.css">'
        '<style>{css}</style><script src="vendor/viz-design-system/kit/kit.js"></script>'
        '<script src="vendor/viz-design-system/kit/takeaway.js"></script>'
        '<script src="vendor/viz-design-system/kit/wayfinding.js" defer></script></head><body>')
SITE_HEADER = ('<a class="kit-skip" href="#main">Skip to content</a><header class="site"><div class="kit-wrap site-row">'
               '<p class="site-id"><a class="site-name" href="../">Diogo Travassos</a><span class="site-role">Data '
               'leadership · Analytics · Decision-making</span></p><nav aria-label="Site"><a href="../#studies">Studies</a>'
               '<a href="https://www.linkedin.com/in/diogo-travassos/">LinkedIn</a><a href="mailto:hello@diogotravassos.dev">'
               'Email</a><button class="theme-toggle" type="button" data-theme-toggle>Theme: auto</button></nav></div></header>')
FOOTER = ('</main><footer class="site"><div class="kit-wrap"><p><span>Public data</span><a href="../#studies">Back to all '
          'studies</a></p></div></footer></body></html>\n')
NEXT = ('<nav class="next-study kit-wrap" data-next-study aria-label="Next study"><a href="../#studies">All studies</a>'
        '</nav>')
PAGES = [("index.html", "The answer"), ("peeking.html", "Peeking"), ("design-choices.html", "Three more choices"),
         ("method.html", "Method and checks")]


def page_links(current):
    items = "".join(f'<a href="{f}"{" aria-current=\"page\"" if f == current else ""}>{e(t)}</a>' for f, t in PAGES)
    return f'<nav class="study-pages kit-wrap" aria-label="Pages of this study">{items}</nav>'


def hero(h1, dek, limit, current):
    return ((page_links(current) if current != "index.html" else "") +
            f'<section class="hero kit-wrap" aria-labelledby="hero-title"><p class="hero-tags"><span class="tag tag-data">'
            f'Public data</span></p><p class="hero-piece">{e(STUDY_TITLE)}</p><h1 id="hero-title">{e(h1)}</h1>'
            + "".join(f'<p class="hero-dek">{d}</p>' for d in dek)
            + (f'<p class="hero-dek limit-line"><strong>Main limit:</strong> {limit}</p>' if limit else "")
            + '</section>')


def section_bar(sections):
    nav = "".join(f'<a href="#{i}">{e(t)}</a>' for i, t in sections)
    return (f'<div class="kit-section-bar"><nav class="page-nav" aria-label="Page sections">{nav}</nav>'
            '<span class="kit-progress" aria-hidden="true"></span></div>')


def block(sid, title, body):
    return (f'<section id="{sid}" class="block kit-wrap" aria-labelledby="{sid}-title"><h2 id="{sid}-title">{e(title)}'
            f'</h2>{body}</section>')


def table(caption, head, rows, cls="data"):
    th = "".join(f'<th scope="col"{" class=\"num\"" if i else ""}>{h}</th>' for i, h in enumerate(head))
    body = "".join("<tr>" + f'<th scope="row">{r[0]}</th>' + "".join(f'<td class="num">{c}</td>' for c in r[1:]) + "</tr>"
                   for r in rows)
    return (f'<div class="table-scroll"><table class="{cls}"><caption>{caption}</caption><thead><tr>{th}</tr></thead>'
            f'<tbody>{body}</tbody></table></div>')


def write(name, title, desc, body):
    page = HEAD.format(desc=e(desc), title=e(title), css=CSS) + SITE_HEADER + '<main id="main">' + body + FOOTER
    (ROOT / name).write_text(page, encoding="utf-8")
    print(f"wrote {name} ({len(page):,} bytes)")
    return page


# ---------------------------------------------------------------- the chart that proves the headline
def calls_svg(fid, animated):
    rows = [("Checked daily, usual 5% test", NV["calls"], NV["unsupported"], True),
            ("Checked daily, sequential rule", SQ["calls"], SQ["unsupported"], False),
            ("Checked daily, fixed bar as strict", MT["calls"], MT["unsupported"], False)]
    Wd, left, right, top_pad = 380, 4, 78, 8
    span = Wd - left - right
    x = lambda v: left + v / NV["calls"] * span  # noqa: E731
    H = top_pad + 74 * len(rows) + 24
    cls_key = "tk-mark tk-key" if animated else "bar-key"
    cls_mark = "tk-mark" if animated else "bar"
    out = [f'<svg viewBox="0 0 {Wd} {H}" role="img" aria-labelledby="{fid}-t" data-readout-default="Each row is one way '
           f'of stopping: the track is every call it made, the solid bar the calls that did not hold at the last '
           f'recorded snapshot. Point at a row to read it.">',
           f'<title id="{fid}-t">Calls that did not hold at the last snapshot, out of all calls, for two ways of stopping, on '
           f'{TESTS} tests</title>']
    for r, (lab, calls, bad, key) in enumerate(rows):
        y = top_pad + 18 + r * 74
        rd = (f"{lab}: {calls} calls on {TESTS} tests; {bad} did not hold at the last snapshot ({pct(bad / calls)} of its "
              f"calls).")
        out.append(f'<g class="tk-row pt{" is-key" if key else ""}" tabindex="0" data-readout="{e(rd)}"><title>{e(rd)}'
                   f'</title><text class="lab" x="{left}" y="{y}">{e(lab)}</text>'
                   f'<rect class="track" x="{left}" y="{y + 8}" width="{x(calls) - left:.1f}" height="22" rx="2"/>'
                   f'<rect class="{cls_key if key else cls_mark}" x="{left}" y="{y + 8}" width="{x(bad) - left:.1f}" '
                   f'height="22" rx="2"/>'
                   f'<text class="val{" tk-key-value" if key and animated else ""}" x="{x(calls) + 8:.1f}" y="{y + 24}">'
                   f'{bad} of {calls}</text></g>')
    out.append(f'<text class="tick" x="{left}" y="{H - 4}">Solid bar: did not hold. Track: all calls.</text>')
    out.append("</svg>")
    return "".join(out)


def aa_svg():
    """False alarms of the daily check as looks accumulate, A/A replay on visits."""
    ys = AV["naive_by_look"]
    Wd, Ht, l, r_, t_, b_ = 440, 250, 40, 112, 16, 34
    x = lambda k: l + (k - 1) / (len(ys) - 1) * (Wd - l - r_)  # noqa: E731
    y = lambda v: t_ + (1 - v / 0.25) * (Ht - t_ - b_)  # noqa: E731
    out = [f'<svg class="aa" viewBox="0 0 {Wd} {Ht}" role="img" aria-labelledby="aa-t" data-readout-default="Each point '
           f'is the share of {AA["reps"]:,} random relabellings where the daily check had flagged a difference by that '
           f'day. Point at one to read it.">', '<title id="aa-t">False alarms of the daily check by number of daily looks, '
           'and of the sequential rule, with one look at the end for comparison</title>']
    for v in (0, 0.05, 0.10, 0.15, 0.20, 0.25):
        out.append(f'<line class="grid" x1="{l}" x2="{Wd - r_}" y1="{y(v):.1f}" y2="{y(v):.1f}"/>'
                   f'<text class="tick" x="{l - 6}" y="{y(v) + 4:.1f}" text-anchor="end">{round(100 * v)}%</text>')
    for k in (1, 7, 14):
        out.append(f'<text class="tick" x="{x(k):.1f}" y="{Ht - 14}" text-anchor="middle">{k}</text>')
    out.append(f'<text class="tick" x="{(l + Wd - r_) / 2:.1f}" y="{Ht - 1}" text-anchor="middle">daily looks so far'
               f'</text>')
    pts_ = " ".join(f"{x(k + 1):.1f},{y(v):.1f}" for k, v in enumerate(ys))
    out.append(f'<polyline class="ser" points="{pts_}"/>')
    for k, v in enumerate(ys):
        rd = f"After {k + 1} daily look{'s' if k else ''}: the daily check had flagged a difference in {pct(v, 1)} of relabellings."
        out.append(f'<g class="pt" tabindex="0" data-readout="{e(rd)}"><title>{e(rd)}</title><circle class="mk" '
                   f'cx="{x(k + 1):.1f}" cy="{y(v):.1f}" r="4"/></g>')
    ms = AV["msprt_by_look"]
    pts2 = " ".join(f"{x(k + 1):.1f},{y(v):.1f}" for k, v in enumerate(ms))
    out.append(f'<polyline class="ser2" points="{pts2}"/>')
    for k, v in enumerate(ms):
        rd = (f"After {k + 1} daily look{'s' if k else ''}: the sequential rule had flagged a difference in "
              f"{pct(v, 2)} of relabellings.")
        out.append(f'<g class="pt" tabindex="0" data-readout="{e(rd)}"><title>{e(rd)}</title><circle class="mk2" '
                   f'cx="{x(k + 1):.1f}" cy="{y(v):.1f}" r="3"/></g>')
    v = AV["fixed"]["rate"]
    out.append(f'<line class="ref" x1="{l}" x2="{Wd - r_}" y1="{y(v):.1f}" y2="{y(v):.1f}"/>'
               f'<text class="lab" x="{Wd - r_ + 6}" y="{y(v) + 4:.1f}">one look, {pct(v, 1)}</text>')
    out.append(f'<text class="lab" x="{Wd - r_ + 6}" y="{y(ms[-1]) + 4:.1f}">sequential, {pct(ms[-1], 1)}</text>')
    out.append(f'<text class="lab key-lab" x="{Wd - r_ + 6}" y="{y(ys[-1]) + 4:.1f}">daily, {pct(ys[-1], 1)}</text>')
    out.append("</svg>")
    return "".join(out)


def ratio_svg():
    rows = [("Four weeks, order as unit", ret["naive"], True), ("Four weeks, customer as unit", ret["delta"], False),
            ("Twelve weeks, order as unit", R12["revenue_per_order"]["naive"], False),
            ("Twelve weeks, customer as unit", R12["revenue_per_order"]["delta"], False)]
    Wd, l, rr = 400, 4, 60
    x = lambda v: l + v / 0.45 * (Wd - l - rr)  # noqa: E731
    H = 10 + 52 * len(rows) + 10
    out = [f'<svg viewBox="0 0 {Wd} {H}" role="img" aria-labelledby="rt-t" data-readout-default="Share of '
           f'{RA["reps"]:,} random splits of the store\'s customers that flagged a difference in revenue per order. '
           f'Point at a bar to read it.">', '<title id="rt-t">False alarms on revenue per order, order as the unit '
           'against customer as the unit</title>']
    for i, (lab, d, key) in enumerate(rows):
        y = 10 + i * 52
        rd = (f"{lab}: {pct(d['rate'], 1)} of random splits flagged a difference (95% interval {pct(d['lo'], 1)} to "
              f"{pct(d['hi'], 1)}). A correct test flags 5%.")
        out.append(f'<g class="pt{" is-key" if key else ""}" tabindex="0" data-readout="{e(rd)}"><title>{e(rd)}</title>'
                   f'<text class="lab" x="{l}" y="{y + 12}">{e(lab)}</text><rect class="{"bar-key" if key else "bar"}" '
                   f'x="{l}" y="{y + 18}" width="{x(d["rate"]) - l:.1f}" height="18" rx="2"/><text class="val" '
                   f'x="{x(d["rate"]) + 8:.1f}" y="{y + 32}">{pct(d["rate"], 1)}</text></g>')
    for i in range(len(rows)):  # the 5% mark, drawn beside each bar only, clear of the labels
        out.append(f'<line class="ref" x1="{x(0.05):.1f}" x2="{x(0.05):.1f}" y1="{10 + i * 52 + 18}" y2="{10 + i * 52 + 39}"/>')
    out.append("</svg>")
    return "".join(out)


def replay_svg(fid, animated):
    """The takeaway: false alarms on the no-effect replay, three ways of deciding."""
    rows = [("Checked daily, usual bar", AV["naive"]["rate"], True), ("One look at the end", AV["fixed"]["rate"], False),
            ("Checked daily, sequential rule", AV["msprt"]["rate"], False)]
    Wd, left, right, top_pad, top_v = 380, 4, 64, 8, 0.25
    span = Wd - left - right
    x = lambda v: left + v / top_v * span  # noqa: E731
    H = top_pad + 74 * len(rows) + 24
    cls_key = "tk-mark tk-key" if animated else "bar-key"
    cls_mark = "tk-mark" if animated else "bar"
    out = [f'<svg viewBox="0 0 {Wd} {H}" role="img" aria-labelledby="{fid}-t" data-readout-default="Each row is one way '
           f'of deciding: the solid bar is the share of {AA["reps"]:,} random splits, with no real difference, that '
           f'raised a false alarm. Point at a row to read it.">',
           f'<title id="{fid}-t">False alarms in {AA["reps"]:,} random splits with no real difference, for three ways '
           f'of deciding</title>']
    for r, (lab, v, key) in enumerate(rows):
        y = top_pad + 18 + r * 74
        rd = f"{lab}: a false alarm in {pct(v, 1)} of {AA['reps']:,} random splits with no real difference."
        out.append(f'<g class="tk-row pt{" is-key" if key else ""}" tabindex="0" data-readout="{e(rd)}"><title>{e(rd)}'
                   f'</title><text class="lab" x="{left}" y="{y}">{e(lab)}</text>'
                   f'<rect class="track" x="{left}" y="{y + 8}" width="{span:.1f}" height="22" rx="2"/>'
                   f'<rect class="{cls_key if key else cls_mark}" x="{left}" y="{y + 8}" width="{max(x(v) - left, 1.5):.1f}" '
                   f'height="22" rx="2"/>'
                   f'<text class="val{" tk-key-value" if key and animated else ""}" x="{left + span + 8:.1f}" '
                   f'y="{y + 24}">{pct(v, 1)}</text></g>')
    out.append(f'<text class="tick" x="{left}" y="{H - 4}">Solid bar: share of splits with a false alarm. Track: 25%.'
               f'</text>')
    out.append("</svg>")
    return "".join(out)


# ================================================================ entry page
H1 = (f"On {AA['reps']:,} no-effect splits of ad traffic, daily checks at the usual bar raised false alarms in "
      f"{pct(AV['naive']['rate'], 1)}; one look, {pct(AV['fixed']['rate'])}. If you check daily, raise the bar.")
assert len(H1.split()) <= 30, len(H1.split())
assert len(H1.split(". ")[0].split()) <= 28 and len(H1.split(". ")[1].split()) <= 10
assert AV["naive"]["rate"] > 0.2 and abs(AV["fixed"]["rate"] - 0.05) < 0.001 and AV["msprt"]["rate"] < 0.01
EVEN = 0.05 / AA["days"]
assert abs(EVEN - 0.00357) < 0.0001

DEK = [f"A false alarm is a test reporting a difference that is not there, and acting on one ships a change that does "
       f"nothing. To count them, {num(13979592 / 1e6)} million visitors from public advertising tests were split into "
       f"two groups at random {AA['reps']:,} times, so no real difference existed. Each split was checked daily "
       f"for {AA['days']} days. The usual bar for a difference, 5%, is built for one look at the end; checked daily, "
       f"it raised a false alarm in {pct(AV['naive']['rate'], 1)} of splits. A sequential rule, which asks for much "
       f"stronger evidence in the first days, raised one in {pct(AV['msprt']['rate'], 1)}.",
       f"So a team that checks daily should raise the bar early, or decide once at the end. The raised bar can be a "
       f"sequential rule, or the 5% split evenly across the planned looks: {pct(EVEN, 2)} at each of {AA['days']} "
       f"daily looks.",
       f"Real experiments, where the truth is not known, point the same way. The {TESTS} readings are each one metric of "
       f"one tested version, from a fashion retailer's {P['experiments']} experiments. Daily checks at the usual bar "
       f"made {NV['calls']} calls to ship or drop a change. Pooled over four metrics, the usual test on each "
       f"experiment's full data did not confirm {pct(1 - nv_hold)} of them, against {pct(1 - seq_hold)} for the "
       f"sequential rule. That later test shares data with the early call, so it favours any stricter bar."]
LIMIT = f"the {pct(AV['naive']['rate'], 1)} is set mostly by the {AA['days']} daily looks, and it was made the main result after the results."

takeaway = (f'<div class="kit-wrap"><figure class="chart takeaway tk-bars" id="takeaway"><figcaption>Checked daily for '
            f'{AA["days"]} days at the usual bar, {pct(AV["naive"]["rate"], 1)} of splits with no real difference '
            f'raised a false alarm. One look at the end: {pct(AV["fixed"]["rate"])}. A sequential rule: '
            f'{pct(AV["msprt"]["rate"], 1)}.</figcaption><p class="chart-unit">Share of {AA["reps"]:,} random splits '
            f'of {num(13979592 / 1e6)} million advertising visitors that flagged a difference in visits, where none '
            f'existed.</p><div class="chart-plot">{replay_svg("tk", True)}</div><p class="limitation"><strong>Main '
            f'limit:</strong> {LIMIT[0].upper() + LIMIT[1:]}</p><p class="takeaway-source">The day-by-day curve: <a '
            f'href="peeking.html#aa-fig">peeking page</a>.</p></figure></div>')

ENTRY_SECTIONS = [("do", "What to do"), ("worth", "Worth"), ("team", "With a team"), ("numbers", "Three numbers"),
                  ("readout", "One test"), ("limit", "The main limit"), ("change", "What would change it"),
                  ("pages", "Detail pages")]
n_had = round_to(min(RD["n_t"], RD["n_c"]), 100)

do = block("do", "What to do", (
    '<p>Write the stopping rule into the test plan before launch. For daily looks, use a sequential rule or the 5% '
    'split evenly across the planned looks; otherwise decide once at the planned end.</p>'
    '<p>For per-order metrics such as revenue per order, count customers, not orders: one customer\'s orders rise and '
    'fall together. Adjusting for what customers did before a test stays a trial, not a rule (design-choices page).</p>'))

numbers = block("numbers", "The three numbers that matter", (
    f'<ul class="notes"><li><strong>{pct(AV["naive"]["rate"], 1)} against {pct(AV["fixed"]["rate"])}.</strong> False '
    f'alarms in {AA["reps"]:,} no-effect splits, checked daily at the usual bar against one look at the end.</li>'
    f'<li><strong>{pct(1 - nv_hold)} against {pct(1 - seq_hold)}.</strong> Real-test calls the full-data test did not '
    f'confirm, usual bar against sequential rule, four metrics pooled. A fixed bar as strict, tuned on these tests '
    f'after the results, gave {pct(MT["share"])}.</li>'
    f'<li><strong>{pct(ret["naive"]["rate"])} against {pct(ret["delta"]["rate"])}.</strong> False alarms on revenue '
    f'per order in random splits of a real store\'s customers, counting orders against counting customers.</li></ul>'))

readout = block("readout", "One test, read out", (
    f'<p>A public e-mail test: the women\'s e-mail against none, about {num(n_had)} customers each. Visits '
    f'rose {pts(RD["visit"]["lift"], 1)} points, a {pct(RD["visit"]["relative"])} lift (95% interval '
    f'{pts(RD["visit"]["lo"], 1)} to {pts(RD["visit"]["hi"], 1)} points), and conversion, the guardrail, rose too. The '
    f'test had {pct(n_had / RD["n_per_arm_needed_5pct"])} of the customers the design\'s 5% target needed. Read as one '
    f'call, chosen after the results: ship the women\'s e-mail.</p>'))

net_per100 = avoided - missed_extra
net = net_per100 * AS["ship_share"]["value"] * AS["cost_wrong_ship_usd"]["value"]
net_lo = net_per100 * AS["ship_share"]["low"] * AS["cost_wrong_ship_usd"]["low"]
net_hi = net_per100 * AS["ship_share"]["high"] * AS["cost_wrong_ship_usd"]["high"]
assert AS["ship_share"]["value"] == 0.5 and AS["tests_per_year"]["value"] == 100 and 0 < net < worth
worth_block = block("worth", "What it is worth", (
    f'<p>Per 100 readings, the sequential rule left about {num(avoided)} fewer calls that the full-data test did not '
    f'confirm, and reached about {num(missed_extra)} fewer of its findings. Assume a team runs '
    f'{AS["tests_per_year"]["value"]} tests a year, each on one main metric, and that the full-data test is right. If '
    f'half of those calls and findings are ships worth {usd(AS["cost_wrong_ship_usd"]["value"])} each, the net is about {usd(round_to(net, 10000))} a year, between {usd(round_to(net_lo, 1000))} '
    f'and {usd(round_to(net_hi, 100000))} across the assumed ranges.</p>'))

team = block("team", "How I would put this to work with a team", (
    '<ol class="notes"><li><strong>Week one.</strong> The analytics lead writes the stopping rule into each test plan; '
    'the product manager signs it before launch.</li>'
    '<li><strong>Week two.</strong> A data engineer puts the raised bar on the dashboard.</li>'
    f'<li><strong>Weeks three and four.</strong> The analyst replays the team\'s past tests day by day and counts the '
    f'findings the raised bar misses against one look at the end (here {miss_seq} of {FIN}). The product lead decides '
    f'whether fewer unconfirmed calls are worth those misses.</li>'
    '<li><strong>Every test after that.</strong> Per-order metrics use the customer as the unit; segment cuts not '
    'named in the plan are leads, not results.</li></ol>'
    f'<p>About {AS["engineer_weeks"]["value"]} engineer-week and {AS["analyst_weeks"]["value"]} analyst-weeks, '
    f'assumed.</p>'))

bm_shares = [d["msprt"]["unsupported"] / d["msprt"]["calls"] for d in BM.values()]
other = L1["other_seeds_all_looks"]
assert AV["naive"]["rate"] < min(other)
limit = block("limit", "The main limit", (
    f'<p>The design made the real-test count the main result instead, since the replay\'s size is set by its looks. Ten other random seeds gave {pct(min(other), 1)} to '
    f'{pct(max(other), 1)}, so {pct(AV["naive"]["rate"], 1)} is the low end, and the days are simulated. The even '
    f'split was not tested here; it holds false alarms to 5% by arithmetic. Spending plans such as '
    f'Pocock\'s are the usual, less strict choice. On the real tests, a fixed bar as strict did about as well, and by metric the sequential rule\'s share runs from {pct(min(bm_shares))} to '
    f'{pct(max(bm_shares))}. A higher bar also reaches fewer findings: {SQ["final_reached"]} of the {FIN} the full '
    f'data showed, against {NV["final_reached"]} for the usual daily check. The money leaves out set-up time and the cost of waiting. The e-mail test is one public test read after its '
    f'data.</p>'))

change = block("change", "What would change the conclusion", (
    f'<ul class="notes"><li>If random splits of a team\'s own traffic put the chosen bar\'s 95% false-alarm interval '
    f'above 5% (sequential rule here: {pct(AV["msprt"]["lo"], 1)} to {pct(AV["msprt"]["hi"], 1)}), decide once at the '
    f'end.</li>'
    f'<li>If replaying past tests daily shows the raised bar missing over half of what one final look finds (here '
    f'{miss_seq} of {FIN}), decide once at the end. That threshold was chosen after the results.</li></ul>'))

pages = block("pages", "Detail pages", (
    '<p><a href="peeking.html"><strong>Peeking</strong></a>, <a href="design-choices.html"><strong>Three more '
    'choices</strong></a> and <a href="method.html"><strong>Method and checks</strong></a>.</p>'
    '<p>Earlier, on simulated data: <a href="../driver-incentives-test-to-decision/">Driver incentives, from test to '
    'decision</a>.</p>'))

entry_body = (hero(H1, DEK, "", "index.html") + takeaway + page_links("index.html") + section_bar(ENTRY_SECTIONS) + do
              + worth_block + team + numbers + readout + limit + change + NEXT + pages)

pages_written = {"index.html": write("index.html", STUDY_TITLE, "How often checking a test every day raises false "
                                     "alarms, what bar to use instead, and how real experiments, the per-order unit and "
                                     "adjustment change the call.", entry_body)}

# ================================================================ peeking page
PH1 = (f"On {TESTS} readings from {P['experiments']} experiments, a stricter daily bar, sequential or fixed, cut the "
       f"calls the last snapshot did not confirm from {NV['unsupported']} to {SQ['unsupported']} or "
       f"{MT['unsupported']}.")
assert len(PH1.split()) <= 28
PSECT = [("plain", "In plain words"), ("calls", "The calls"), ("replay", "The relabelling replay"),
         ("surprises", "What did not go as expected"), ("next", "What is blocked")]
p_plain = block("plain", "In plain words", (
    '<p>A team launches a change to half its visitors and opens the dashboard the next morning. The difference looks '
    'significant, so someone asks to ship. The usual 5% test assumes one look at the end. Every extra look is another '
    'chance for noise to cross the line.</p>'
    '<p>A sequential rule is a test built to be looked at every day. It asks for stronger evidence early, so noise '
    'rarely crosses its line. The price is that it waits longer on small real effects.</p>'
    f'<p>The records here are public. A large online fashion retailer published {P["experiments"]} of its experiments, '
    f'{PAIRS} test arms against control, four unnamed metrics each, with running totals every half day. Each test was '
    f'read once a day, at that day\'s first snapshot, under each rule, and every call was compared with the usual test at the last snapshot. Of these, {DROPPED} '
    f'arm and metric series carry no variances in the records and cannot be tested, which leaves {TESTS} tests, each '
    f'one metric of one arm.</p>'))
crow = lambda lab, d, reached: [lab, num(d["calls"]), num(d["calls"] - d["unsupported"]), num(d["unsupported"]),  # noqa: E731
                                f'{reached} of {FIN}']
p_calls = block("calls", "The calls", (
    f'<figure class="chart" id="calls-fig"><figcaption>Checking every day made {NV["calls"]} calls, and '
    f'{NV["unsupported"]} did not hold at the last snapshot. The sequential rule made {SQ["calls"]}, and {SQ["unsupported"]} '
    f'did not hold.</figcaption><p class="chart-unit">Calls that did not hold at the last snapshot, out of all calls, on '
    f'{TESTS} tests.</p><div class="chart-plot">{calls_svg("cf", False)}</div></figure>'
    + table(f"Calls on {TESTS} tests ({PAIRS} arms, up to 4 metrics). Held: the test at the last snapshot was also "
            f"significant, in the same direction.",
            ["Way of stopping", "Calls", "Held", "Did not hold", "Last-snapshot results reached"],
            [crow("Checked daily, usual 5% test", NV, NV["final_reached"]),
             crow("Checked daily, sequential rule", SQ, SQ["final_reached"]),
             crow("Checked daily, fixed bar as strict (added after the results)", MT, MT["final_reached"]),
             ["One look at the last snapshot (the yardstick itself)", num(FIN), num(FIN), "0 by definition",
              f"{FIN} of {FIN}"],
             crow("Sequential rule early, one look at the end (read after the results)", HY, HY["final_reached"])])
    + f'<p>In a check added after the results, resampling whole experiments {CI["resamples"]:,} times (arms of one '
    f'experiment share a control), the daily check\'s share of calls that did not hold is {pct(CI["naive"][0])} '
    f'(95% interval {pct(CI["naive"][1])} to {pct(CI["naive"][2])}), the sequential rule\'s {pct(CI["msprt"][0])} '
    f'({pct(CI["msprt"][1])} to {pct(CI["msprt"][2])}), and the gap {pts(CI["difference"][0], 0)} points '
    f'({pts(CI["difference"][1], 0)} to {pts(CI["difference"][2], 0)}). In the combined row, the calls made at the end '
    f'hold by definition; the cost is that {end_calls} of them wait for the planned end.</p>'
    f'<p>In a change added after the results, a daily check with a fixed bar (a z of at least {num(MB["bar_z"], 2)}, '
    f'p under {num(MB["bar_p"], 4)} at each look), the least strict bar on a grid of 0.01 that makes no more calls than '
    f'the sequential rule, made {MT["calls"]} calls, and {MT["unsupported"]} did not hold: {pct(MT["share"])} (95% '
    f'interval {pct(MCI["matched"][1])} to {pct(MCI["matched"][2])}, resampling whole experiments) against '
    f'{pct(MCI["msprt"][0])}, a difference of {pts(MCI["difference"][0], 0)} point ({MINUS}{pts(-MCI["difference"][1], 0)} '
    f'to {pts(MCI["difference"][2], 0)}). On the real tests, then, the gap comes from strictness; the replay shows why '
    f'a daily check needs it. The fixed bar was not replayed.</p>'
    f'<p class="change-note"><strong>Change after the first results.</strong> The first version counted the {DROPPED} '
    f'series without variances as tests with no call, {TESTS_R1} tests in all, although the design said to drop them. '
    f'They are now dropped. No call changed; per 100 tests, the calls that did not hold moved from '
    f'{num(r1_naive, 1)} to {num(r3_naive, 1)} for the daily check and from {num(r1_seq, 1)} to '
    f'{num(r3_seq, 1)} for the sequential rule.</p>'
    f'<p class="change-note"><strong>Another change after the results.</strong> The daily look was first taken only at '
    f'whole-day snapshots, so the {NOLOOK} series recorded at half-day offsets had no looks. It is now each day\'s '
    f'first snapshot. The daily check\'s calls went from {R3N["calls"]}, {R3N["unsupported"]} of them not holding, to '
    f'{NV["calls"]} and {NV["unsupported"]}; the sequential rule\'s from {R3S["calls"]} and {R3S["unsupported"]} to '
    f'{SQ["calls"]} and {SQ["unsupported"]}. Per 100 tests, calls that did not hold moved from {num(r3_naive, 1)} to '
    f'{num(per100_naive, 1)} and from {num(r3_seq, 1)} to {num(per100_seq, 1)}. The method page has the details.</p>'
    f'<p class="change-note"><strong>A further change after the results.</strong> The comparison above mixes being '
    f'built for daily checks with being stricter, so a daily check with a fixed bar as strict was added (table, fourth '
    f'row). The prediction that the sequential rule would beat it by 5 points or more missed.</p>'
    + f'<p>Of the daily check\'s {NV["unsupported"]} calls that did not hold, {NV["opposite_sign"]} pointed the wrong '
    f'way; the rest faded below significance. When either rule did call a result that held, it did so with about '
    f'{pct(NV["median_frac_n_when_reached"])} of the final users in, for the daily check, and '
    f'{pct(SQ["median_frac_n_when_reached"])} for the sequential rule.</p>'
    f'<p>The sequential rule has one setting, how large an effect it expects. It was fixed before the run at a hundredth '
    f'of a standard deviation. At a third of that it made {P["msprt_sens"]["0.003"]["calls"]} calls with '
    f'{P["msprt_sens"]["0.003"]["unsupported"]} not holding; at three times it made '
    f'{P["msprt_sens"]["0.03"]["calls"]} with {P["msprt_sens"]["0.03"]["unsupported"]}. The call does not hinge on '
    f'the setting.</p>'
    + table("By metric (metrics are unnamed in the records); the main figures sum all four",
            ["Metric", "Daily check: calls", "Did not hold", "Sequential rule: calls", "Did not hold",
             "Significant at the last snapshot"],
            [[f"Metric {m}", num(d["naive_calls"]), num(d["naive_unsupported"]), num(BM[m]["msprt"]["calls"]),
              num(BM[m]["msprt"]["unsupported"]), num(d["final_sig"])]
             for m, d in sorted(P["by_metric"].items())])
    + f'<p>In checks added after the results, the sequential rule\'s share of calls that did not hold is lower on all '
    f'four metrics, but on metric 2 only just: {BM["2"]["msprt"]["unsupported"]} of {BM["2"]["msprt"]["calls"]} against '
    f'{BM["2"]["naive"]["unsupported"]} of {BM["2"]["naive"]["calls"]}; metric 2 accounts for '
    f'{BM["2"]["msprt"]["unsupported"]} of the sequential rule\'s {SQ["unsupported"]} calls that did not hold. Of the '
    f'daily check\'s calls, {NV["calls"] - BL["naive"]["calls"]} first come at the last snapshot, where the daily '
    f'look is the last-snapshot test and holds by definition. Without them the daily check\'s share is '
    f'{pct(BL["naive"]["share"][0])} ({BL["naive"]["unsupported"]} of {BL["naive"]["calls"]}) against '
    f'{pct(BL["msprt"]["share"][0])}, a gap of {pts(BL["difference"][0], 0)} points (95% interval '
    f'{pts(BL["difference"][1], 0)} to {pts(BL["difference"][2], 0)}).</p>'))
p_replay = block("replay", "The relabelling replay: each rule's false alarms, measured", (
    f'<p>The real tests cannot say which calls were false. A replay can. The replay takes the {num(13979592)} users of '
    f'the Criteo advertising tests, puts them in one random arrival order and cuts it into {AA["days"]} simulated days '
    f'of about {num(round_to(AA["users_per_day"], 1000))} users. It then discards the real arms and relabels every user '
    f'A or B at random, {AA["reps"]:,} times. Any difference found is a false alarm by construction.</p>'
    f'<figure class="chart" id="aa-fig"><figcaption>The daily check\'s false alarms climb with every look, to '
    f'{pct(AV["naive"]["rate"], 1)} after two weeks. The sequential rule creeps up to only {pct(AV["msprt"]["rate"], 1)}.'
    f'</figcaption><p class="chart-unit">Share of {AA["reps"]:,} random relabellings that flagged a difference in '
    f'visits, by daily looks so far.</p><div class="chart-plot">{aa_svg()}</div></figure>'
    + table(f"False alarms in {AA['reps']:,} random relabellings, with 95% intervals",
            ["Rule", "Visits", "Conversions", "Store revenue per customer"],
            [[lab, f'{pct(AV[k]["rate"], 1)} ({pct(AV[k]["lo"], 1)} to {pct(AV[k]["hi"], 1)})',
              f'{pct(AC[k]["rate"], 1)} ({pct(AC[k]["lo"], 1)} to {pct(AC[k]["hi"], 1)})',
              (f'{pct(AR[k]["rate"], 1)} ({pct(AR[k]["lo"], 1)} to {pct(AR[k]["hi"], 1)})' if k in AR else "not run")]
             for lab, k in (("Daily check, usual 5% test", "naive"), ("One look at the end", "fixed"),
                            ("Sequential rule", "msprt"),
                            ("Sequential rule early, one look at the end (read after the results)", "hybrid"),
                            ("The same, end test at 4.5% (added after the results)", "hybrid_045"))])
    + f'<p>The first look, at {pct(L1["study_seed_first_look"], 1)}, is a rare draw: about '
    f'{num(look1_se, 1)} standard errors below 5%. In a check '
    f'added after the results, ten other seeds put the first look between {pct(min(L1["other_seeds_first_look"]), 1)} '
    f'and {pct(max(L1["other_seeds_first_look"]), 1)}, and the two-week total between '
    f'{pct(min(L1["other_seeds_all_looks"]), 1)} and {pct(max(L1["other_seeds_all_looks"]), 1)}.</p>'
    f'<p>The store column repeats the replay on a UK online store\'s {num(AR["customers"])} customers over '
    f'{AR["days"]} real days, with daily looks from the end of the first week. Revenue per customer is skewed, and the '
    f'daily check still flagged {pct(AR["naive"]["rate"], 1)} of runs.</p>'
    f'<p>The sequential rule\'s guarantee assumes the variance and the expected effect size are known. Here both are '
    f'estimated from the data at each look, an approximation, so its false alarms are measured rather than assumed: '
    f'{pct(AV["msprt"]["rate"], 1)} on visits and {pct(AC["msprt"]["rate"], 2)} on conversions, and under 5% in a unit '
    f'test on simulated yes-or-no streams with the same settings. That supports the rule on these metrics; it does not '
    f'prove it on others, such as skewed revenue or effects that change over a test, so a team should repeat the replay '
    f'on its own metrics before adopting it. Versions with a proven guarantee for estimated variances also exist.</p>'
    f'<p>The combination in the last two rows is the candidate I would validate on a team\'s own traffic before running '
    f'it. Its two parts each spend up to 5%, so it carries no single 5% guarantee: on visits it flagged '
    f'{pct(AV["hybrid"]["rate"], 1)} ({pct(AV["hybrid"]["lo"], 1)} to {pct(AV["hybrid"]["hi"], 1)}). With the end test '
    f'at 4.5%, a change added after the results, it flagged {pct(AH["rate"], 1)} on visits and '
    f'{pct(AC["hybrid_045"]["rate"], 1)} on conversions. Both are below 5% as observed, but their intervals cross it (up '
    f'to {pct(AH["hi"], 1)} and {pct(AC["hybrid_045"]["hi"], 1)}), and they reuse the same draws, so this is a '
    f'calibration, not proof of a 5% guarantee. The daily check is about four times worse. The arrival order is simulated, since the data carry no dates: one order, cut into equal '
    f'days.</p>'))
p_surprise = block("surprises", "What did not go as expected", (
    f'<ul class="notes"><li>The prediction was that a quarter to a half of the daily check\'s calls would not hold. It was '
    f'{pct(NV["unsupported"] / NV["calls"], 1)}, just past the top of that range.</li>'
    f'<li>The prediction was that the sequential rule\'s calls would hold nine times in ten. Only {pct(1 - SQ["unsupported"] / SQ["calls"])} '
    f'held. The yardstick is itself a 5% test, and some real effects may shrink over a test, which no stopping rule '
    f'can see coming.</li>'

    f'<li>A check on the split between arms flagged {SRM["asos_flagged"]} of the {PAIRS} arms against an even split. '
    f'Three look like planned uneven splits ({", ".join(pct(r["share_t"]) for r in sorted(planned, key=lambda r: r["share_t"]))} '
    f'in the test arm); the other {len(close)} are within {pts(far_close, 1)} points of half. The records do not say '
    f'which splits were planned. Without the {SRM["asos_flagged"]} flagged arms, a check added after the results, the '
    f'daily check made {WF["naive_calls"]} calls and {WF["naive_unsupported"]} did not hold. The sequential rule made '
    f'{WF["msprt_calls"]}, and {WF["msprt_unsupported"]} did not hold.</li></ul>'))
p_next = block("next", "What is blocked", (
    '<p>A replay of real experiments, read day by day with their real user-level arms, would settle how often early '
    'calls hold when effects change over a test; a relabelling replay of the same logs would count false alarms on '
    'real traffic. Both need user-level logs, which these records do not publish. The arrival order in the replay here '
    'is simulated for the same reason.</p>'))
peek_body = (hero(PH1, [f"The records: {PAIRS} test arms from {P['experiments']} public experiments, up to four metrics each, "
                        f"read once a day."], "", "peeking.html") + section_bar(PSECT) + p_plain + p_calls + p_replay +
             p_surprise + p_next + NEXT)
pages_written["peeking.html"] = write("peeking.html", "Peeking: daily checks against a sequential rule",
                                      f"Daily checks against a sequential stopping rule on {TESTS} real online tests, and "
                                      "a relabelling replay that measures each rule's false alarms.", peek_body)

# ================================================================ design choices page
DH1 = (f"Counting each order as independent flagged a difference in {pct(ret['naive']['rate'])} of random splits of a "
       f"real store's customers, against {pct(ret['delta']['rate'])} with customers as the unit.")
assert len(DH1.split()) <= 28, len(DH1.split())
DSECT = [("plain", "In plain words"), ("ratio", "Per-order metrics"), ("adjust", "Pre-test adjustment"),
         ("segments", "Segments"), ("readout", "One test, read out")]
d_plain = block("plain", "In plain words", (
    '<p>Three more choices sit in every test plan. One is the unit. A test splits customers, but revenue per '
    'order counts orders, and one customer\'s orders look alike. Treating them as independent makes the interval too '
    'narrow.</p>'
    '<p>Another is noise. Much of the spread in a metric is there before the test starts. Adjusting for it, the idea '
    'behind CUPED, shrinks the interval without bias.</p>'
    '<p>The last is slicing. After a test, people cut the result by segment and report the ones that look different. '
    'With enough cuts, some will by chance.</p>'))
d_ratio = block("ratio", "Per-order metrics: the customer is the unit", (
    f'<p>The data are the Online Retail II records of a UK online store: real customers, real dates, repeat orders, but '
    f'no experiment. So the test is an A/A test: customers split at random {RA["reps"]:,} times, where any difference '
    f'is a false alarm. In four weeks, {num(R4["customers"])} customers placed {num(R4["orders"])} orders, up to '
    f'{R4["orders_per_customer_max"]} each.</p>'
    f'<figure class="chart" id="ratio-fig"><figcaption>Counting orders as independent flagged a difference in '
    f'{pct(ret["naive"]["rate"])} of random splits in four weeks and {pct(R12["revenue_per_order"]["naive"]["rate"])} '
    f'in twelve. With the customer as the unit it stayed near 5%.</figcaption><p class="chart-unit">False alarms on '
    f'revenue per order, share of {RA["reps"]:,} random splits; the line marks 5%.</p><div class="chart-plot">'
    f'{ratio_svg()}</div></figure>'
    + table(f"False alarms in {RA['reps']:,} random splits of customers (a correct test flags 5%)",
            ["Window and metric", "Order as unit", "Customer as unit", "Order-level interval, share of correct width"],
            [[f"{w}, {m.replace('_', ' ')}", pct(d[m]["naive"]["rate"], 1), pct(d[m]["delta"]["rate"], 1),
              pct(d[m]["median_se_ratio_naive_over_delta"])]
             for w, d in (("Four weeks", R4), ("Twelve weeks", R12)) for m in ("revenue_per_order", "units_per_order")])
    + f'<p>The longer the test, the more repeat orders, and the worse the order-level interval: it was '
    f'{pct(ret["median_se_ratio_naive_over_delta"])} of the correct width in four weeks and '
    f'{pct(R12["revenue_per_order"]["median_se_ratio_naive_over_delta"])} in twelve. A check on the advertising data, '
    f'where nobody visits twice, gave the same interval both ways, as it must: the delta method only matters when a '
    f'unit has more than one event.</p>'))
d_adjust = block("adjust", "Adjusting for pre-test data", (
    f'<p>The Criteo data hold {num(13979592)} users from randomised advertising tests, {pct(SRM["criteo"]["share"])} '
    f'shown ads, with 12 anonymised features measured before the test. Adjusting visits for those features removed '
    f'{pct(CV["var_removed_A"], 1)} of the noise. The users needed per arm to detect a 5% lift fell from '
    f'{num(round_to(CV["n_per_arm_raw"], 100))} to {num(round_to(CV["n_per_arm_A"], 100))}.</p>'
    + table("Share of noise removed by adjusting for pre-test data",
            ["Data and metric", "Adjusted for", "Noise removed"],
            [["Criteo, visits", "12 features, straight line", pct(CV["var_removed_A"], 1)],
             ["Criteo, visits", "12 features, binned prediction from the other half", pct(CV["var_removed_B"], 1)],
             ["Criteo, conversions", "12 features, straight line", pct(CC["var_removed_A"], 1)],
             ["Criteo, conversions", "12 features, binned prediction from the other half", pct(CC["var_removed_B"], 1)],
             ["E-mail test, spend", "prior spend", pct(HS["var_removed_A"], 2)],
             ["E-mail test, spend", "all pre-test fields", pct(HS["var_removed_B"], 2)],
             ["E-mail test, visits", "prior spend", pct(HV["var_removed_A"], 1)],
             ["E-mail test, visits", "all pre-test fields", pct(HV["var_removed_B"], 1)]])
    + f'<p>The classic version, adjusting for the same metric before the test, did almost nothing on the e-mail test: '
    f'prior spend removed {pct(HS["var_removed_A"], 2)} of the noise in spend. Adjustment only pays where the pre-test '
    f'data predict the outcome.</p>'
    f'<p>One result was not planned for. On Criteo the adjustment moved the estimate itself: the lift in visits fell '
    f'from {pts(CV["raw"])} to {pts(CV["adjA"])} points, a {pct(CD["criteo_visit_shift"])} drop, '
    f'about {num(CD["criteo_visit_shift_in_se"])} times its standard error. In one clean randomised test that should not happen. A '
    f'balance check, added after the results, found the arms differ before the test by up to '
    f'{num(BAL["max_abs_smd"], 3)} standard deviations. That passes the common rule of thumb of 0.1, yet it is '
    f'{num(smd_mult)} times what chance would leave. The publisher built these data from several tests and sampled '
    f'them unevenly, so the share shown ads likely differs by source test.</p>'
    f'<p>These data cannot say which estimate is right. The adjustment removes differences in the 12 features, not '
    f'differences between source tests that the features miss, so neither number is trusted until the arms are checked '
    f'at the source. The {pct(CD["criteo_visit_sample_cut"])} saving in users is a calculation on these published data, '
    f'and it is why adjustment is a trial in the plan, not yet a rule. Balance is better judged against chance than '
    f'against 0.1.</p>'))
d_seg = block("segments", "Segment effects: does a correction change the call?", (
    f'<p>Each of the 12 features was cut into fifths, which left {SG["valid_per_slice"][0]} usable segments. Each '
    f'segment was tested against the rest of the users on {SG["slices"]} random slices of about '
    f'{num(round_to(SG["users_per_slice_min"], 1000))} users, the size of a large test. A segment found on one slice '
    f'counts as real if the other {SG["slices"] - 1} slices show the same direction at 5%.</p>'
    + table(f"Segments flagged per slice, and how many held on the other {SG['slices'] - 1}",
            ["Rule", "Flagged per slice", "Held elsewhere"],
            [["Each segment at 5%", num(SG["naive"]["flagged_per_slice"], 1), pct(SG["naive"]["share_replicated"], 1)],
             ["Holm correction", num(SG["holm"]["flagged_per_slice"], 1), pct(SG["holm"]["share_replicated"], 1)],
             ["False discovery rate, 5%", num(SG["bh"]["flagged_per_slice"], 1), pct(SG["bh"]["share_replicated"], 1)]])
    + f'<p>The prediction was that half the uncorrected finds would fail. Nearly all held, and the correction changed almost no call. '
    f'The lift here is concentrated: in the lowest fifth of one feature, {pct(top_share)} of users, ads lifted visits '
    f'by {pts(top["effect"], 1)} points, against {pts(top["rest"], 2)} points for everyone else. When effects differ this '
    f'much, a correction costs little and finds the same segments. The features are anonymised, and part of the '
    f'difference may be which source test a user came from. So these data cannot test the rule in the plan, that '
    f'unplanned cuts are leads, not results: they test it only where effects are this large.</p>'))
rv, rs, rc = RD["visit"], RD["spend"], RO["conversion"]
d_read = block("readout", "One test, read out", (
    f'<p>The MineThatData e-mail test sent {num(RD["n_t"])} customers a women\'s e-mail and held out '
    f'{num(RD["n_c"])}. The data are public and older than this study, so the test was not '
    f'planned here. The study\'s design, written before any result, fixed a two-sided 5% test, 80% power, a 5% lift in '
    f'visits, a check on the split and conversion as the guardrail. Reading this test as one ship call with them was '
    f'chosen after the results. '
    f'Detecting a 5% lift on its {pct(rv["base"], 1)} visit rate needs '
    f'{num(round_to(RD["n_per_arm_needed_5pct"], 100))} users per arm, so this test could see lifts of '
    f'{pct(RD["mde_relative_at_this_n"], 1)} or more.</p>'
    + table("The readout, with 95% intervals", ["Metric", "Control", "Lift", "95% interval"],
            [["Visits", pct(rv["base"], 1), f"+{pts(rv['lift'], 1)} points", f"{pts(rv['lo'], 1)} to {pts(rv['hi'], 1)}"],
             ["Spend per customer", f"US${rs['base']:.2f}", f"+US${reg(f'{rs['lift']:.2f}')}",
              f"US${reg(f'{rs['lo']:.2f}')} to US${reg(f'{rs['hi']:.2f}')}"],
             ["Conversion (guardrail)", pct(rc["c"], 2), f"+{pts(rc['lift'], 2)} points",
              f"{pts(rc['lo'], 2)} to {pts(rc['hi'], 2)}"]])
    + f'<p>The split passed (chance of a gap this size {num(SRM["hillstrom"]["p"], 2)}), the guardrail rose, and '
    f'adjusting for prior spend changed nothing. The call: ship the women\'s e-mail. The observed lift, '
    f'{pct(rv["relative"])}, was far above what the test was built to detect.</p>'))
dc_body = (hero(DH1, ["Also on this page: the adjustment for pre-test data, segment effects, and one public test "
                      "read out."], "", "design-choices.html") + section_bar(DSECT) + d_plain + d_ratio + d_adjust +
           d_seg + d_read + NEXT)
reg(f"{RD['spend']['base']:.2f}")
pages_written["design-choices.html"] = write("design-choices.html", "Three more design choices",
                                             "Per-order metrics, adjustment for pre-test data and segment effects, "
                                             "measured on public data, and one public test read out.",
                                             dc_body)

# ================================================================ method page
MH1 = (f"Counting orders as independent added {num(HR['per100']['ratio'])} false alarms per 100 random splits of one "
       f"store over four weeks.")
assert len(MH1.split()) <= 28
MSECT = [("data", "Data"), ("parts", "What each part does"), ("predictions", "Predictions"),
         ("changes", "Changes"), ("checks", "Checks"), ("glossary", "Glossary"), ("downloads", "Reproduce")]
m_data = block("data", "Data and licences", table(
    "Four public datasets", ["Dataset", "Rows", "Licence", "Used for"],
    [["Criteo uplift, version 2.1 (Criteo AI Lab)", num(13979592), "CC BY-NC-SA 4.0, non-commercial: fine for this "
      "page, not for a product", "adjustment, segments, the relabelling replay"],
     ["ASOS Digital Experiments (Liu and others, ASOS and Imperial College)", num(24153), "CC BY 4.0",
      "daily checks against the sequential rule"],
     ["Online Retail II (UCI repository)", num(1067371), "CC BY 4.0", "per-order metrics, store replay"],
     ["MineThatData e-mail test (Kevin Hillstrom)", num(64000), "shared publicly for analysis, credited, not copied "
      "here", "classic adjustment, the readout"]]) +
    '<p>The data files are not copied here; the README gives the sources and checksums. Large files were read in '
    'chunks of a million rows with DuckDB, never whole.</p>')
m_parts = block("parts", "What each part does", (
    f'<ul class="notes"><li><strong>Daily checks.</strong> For each of the {TESTS} tests, a two-sided Welch test on the '
    f'running means at the first snapshot of each day (a Welch-style z test, normal approximation). The daily check calls at the first p under 0.05. The sequential rule is a '
    f'mixture sequential probability ratio test that calls when the ratio reaches 20, with the mixing scale fixed at '
    f'0.01 standard deviations. It plugs in the observed variances and standard deviation at each look, a '
    f'large-sample approximation of a rule whose guarantee assumes both known; its false alarms are measured by the '
    f'replay. In a change added after the results, a third rule calls at a fixed bar as strict as the sequential '
    f'rule (a z of at least {num(MB["bar_z"], 2)}, matched on its number of calls). The yardstick is the same Welch '
    f'test at the last snapshot.</li>'
    f'<li><strong>Relabelling replay.</strong> One seeded arrival order, {AA["days"]} equal days, {AA["reps"]:,} '
    f'relabellings. Each user is A or B with even odds; done exactly per day by a binomial draw of the arm size and a '
    f'hypergeometric draw of its visits. A test checks this against explicit relabelling.</li>'
    f'<li><strong>Per-order metrics.</strong> Orders are invoices, cancellations dropped, four weeks from 3 to 30 '
    f'October 2011 and twelve weeks from 8 August. The order-level test is a Welch test on order values; the delta '
    f'method uses customer sums.</li>'
    f'<li><strong>Adjustment.</strong> Separate straight-line fits per arm, centred on the pooled mean of the features. '
    f'The binned version predicts each user from 20 bins per feature, fitted on the other half of the data.</li>'
    f'<li><strong>Segments.</strong> Cuts at the 20th to 80th percentiles; each segment against the rest, difference of '
    f'the arm differences; Holm and Benjamini-Hochberg at 5%.</li></ul>'
    f'<p>How much each choice moves, per 100 decisions: checking daily at the usual bar left '
    f'{num(HR["per100"]["peeking"], 1)} calls per 100 real readings that the last-snapshot test did not confirm, '
    f'{num(LFL["peeking"], 1)} more than the sequential rule (compared like for like, added after the results); '
    f'counting orders as independent added {num(HR["per100"]["ratio"], 1)} false alarms per 100 no-effect splits at '
    f'four weeks and {num(r12_gap)} at twelve; uncorrected segments, {num(HR["per100"]["segments"], 1)}. On the '
    f'no-effect replay, daily checks at the usual bar raised about {num(replay_gap)} more false alarms per 100 splits '
    f'than the sequential rule ({pct(AV["naive"]["rate"], 1)} against {pct(AV["msprt"]["rate"], 1)}).</p>'))
for _p in PRED:  # the declared expectations are quoted verbatim
    reg(_p["expected"])
PLAIN = {"P1": "Criteo visits: noise removed by straight-line adjustment, expected 10% to 40%",
         "P2": "Criteo visits: binned prediction removes at least 3 points more noise than the straight line",
         "P3": "E-mail test spend: noise removed by prior spend alone, expected under 5%",
         "P4": "Daily check: share of its calls that do not hold, expected 25% to 50%",
         "P5": "Sequential rule: share of its calls that do not hold, expected 10% or less",
         "P6": "Sequential rule: share of last-snapshot results it reaches, expected 50% to 85%",
         "P7": "Replay: daily check's false alarms over 14 looks, expected 15% to 25%",
         "P8": "Replay: sequential rule's false alarms, expected 5% or less",
         "P9": "Store: false alarms counting orders as independent, expected 10% to 30%",
         "P10": "Store: false alarms with the customer as the unit, expected 3% to 7%",
         "P11": "Segments found at 5% that hold elsewhere, expected 50% or less",
         "P12": "Segments found after the Holm correction that hold elsewhere, expected 80% or more",
         "P13": "Split check: Criteo and the e-mail test pass, at least one ASOS arm flagged"}
for _t in PLAIN.values():
    reg(_t)
OUTC = {"as expected": "As expected", "the opposite": "The opposite", "neither": "Neither"}


def show(v, pid=""):
    if pid == "P2":  # a difference of two shares, in points
        return (MINUS if v < 0 else "+") + pts(abs(v), 1) + " points"
    if isinstance(v, float) and abs(v) < 2:
        return pct(v, 2) if abs(v) < 0.01 else pct(v, 1)
    return num(v)


m_pred = block("predictions", "Predictions written down before the first run", (
    f'<p>{TALLY["as expected"]} of {len(PRED)} came out as expected, {TALLY["the opposite"]} the opposite, and '
    f'{TALLY["neither"]} in between. One outcome moved with the daily-look change below: the sequential rule\'s share '
    f'of last-snapshot results reached was {pct(P6R3["value"])}, in between, and is now {pct(P6["value"])}, as '
    f'expected.</p>'
    + table("Each prediction, its result and the outcome", ["What was predicted", "Result", "Outcome"],
            [[e(PLAIN[p["id"]]), show(p["value"], p["id"]), OUTC[p["outcome"]]] for p in PRED])))
m_change = block("changes", "Changes made after the first results", (
    f'<ul class="notes">'
    f'<li><strong>Series without variances.</strong> {DROPPED} arm and metric series carry no variances in the records. '
    f'The first version counted them as tests with no call ({TESTS_R1} tests); the design said to drop such series, and '
    f'they are now dropped ({TESTS} tests). No call changed. Per 100 tests, calls that did not hold moved from '
    f'{num(r1_naive, 1)} to {num(r3_naive, 1)} for the daily check and from {num(r1_seq, 1)} to {num(r3_seq, 1)} '
    f'for the sequential rule; the money figures moved with them.</li>'
    f'<li><strong>The daily look.</strong> It was first taken only at whole-day snapshots, as the design said, which the {NOLOOK} series '
    f'recorded at half-day offsets never reach. It is now the first snapshot of each day, so every series is read '
    f'daily. This also added looks to {MOVED_LOOKS} of the other {len(WHOLE)} series, which skip a day or start at a '
    f'half day, and changed a call or its day on {MOVED_CALLS}. The daily check\'s calls went from {R3N["calls"]}, '
    f'{R3N["unsupported"]} not holding, to {NV["calls"]} and {NV["unsupported"]}; the sequential rule\'s from '
    f'{R3S["calls"]} and {R3S["unsupported"]} to {SQ["calls"]} and {SQ["unsupported"]}. The gap in shares stays '
    f'clear of zero ({pts(CI["difference"][1], 0)} to {pts(CI["difference"][2], 0)} points), the sequential rule is '
    f'lower on all four metrics, and the gap counting only calls before the last snapshot also excludes zero.</li>'
    f'<li><strong>A daily check as strict.</strong> A third rule on the same looks: the usual test at a fixed bar '
    f'matched to the sequential rule\'s number of calls. Its share of calls that did not hold was predicted to be '
    f'below the daily check\'s (held: {pct(MT["share"])} against {pct(1 - nv_hold)}) and above the sequential rule\'s '
    f'by 5 points or more (missed: {pct(1 - seq_hold)}, difference {MINUS}{pts(-MCI["difference"][1], 0)} to '
    f'{pts(MCI["difference"][2], 0)} points). So the real-test gap is credited to strictness.</li>'
    f'<li><strong>By metric and before the last snapshot.</strong> The sequential rule\'s calls on each metric, and the '
    f'shares counting only calls before the last snapshot, with their own interval.</li>'
    f'<li><strong>New outputs from the same draws.</strong> The sequential rule\'s false alarms by look, and the '
    f'combined rule with its end test at 4.5%. Every earlier replay number is unchanged.</li>'
    f'<li><strong>New checks.</strong> An interval for the share of calls that did not hold, resampling whole '
    f'experiments, and a unit test of the sequential rule with the variance estimated at each look.</li>'
    f'<li><strong>Stopping and the per-order unit, like for like.</strong> Stopping\'s difference from the '
    f'sequential rule, beside the per-order metric\'s extra false alarms, as given above.</li></ul>'))
m_checks = block("checks", "Checks", (
    '<ul class="notes"><li>Unit tests: the adjustment matches a least-squares fit, the delta method equals the simple '
    'interval when each unit has one event and is wider when events cluster, the sequential rule holds its error rate '
    'under daily looks with the variance known and with it estimated at each look, and the replay shortcut matches '
    'explicit relabelling.</li>'
    '<li>The split between arms: Criteo against its stated share, the e-mail test against equal thirds, each retailer '
    'arm against an even split.</li></ul>'))
m_gloss = block("glossary", "Glossary", (
    '<dl class="glossary"><dt>Usual test</dt><dd>The standard 5% significance test (here Welch\'s), built for '
    'one look at the planned end.</dd><dt>Significant at 5%</dt><dd>If there were no real effect, a difference at least this large '
    'would turn up in under 5% of tests.</dd><dt>Sequential rule</dt><dd>A test designed to be checked as often as you like '
    'while keeping its false alarms at 5% or less; here an approximation, with its false alarms measured.</dd><dt>Relabelling replay</dt><dd>Real users with the arms thrown '
    'away and redrawn at random; any difference found is a false alarm. Also called an A/A test.</dd><dt>Delta method'
    '</dt><dd>The interval for a ratio such as revenue per order, computed with the customer as the unit.</dd><dt>CUPED'
    '</dt><dd>Adjusting a test\'s metric for data from before the test, to cut its noise.</dd><dt>Holm correction</dt>'
    '<dd>A stricter bar when many segments are tested, so chance finds are rarer.</dd><dt>Guardrail</dt><dd>A metric '
    'that must not get worse for a change to ship.</dd><dt>Did not hold</dt><dd>An early call that the same test at the '
    'last recorded snapshot did not confirm: no longer significant at 5%, or significant the other way.</dd></dl>'))
m_down = block("downloads", "Reproduce and download", (
    '<p>The code, the results and the predictions are in this folder: <a href="README.md">README</a>, '
    '<a href="predictions-r1.json">predictions</a>, <a href="results/summary.json">results summary</a>, '
    '<a href="assumptions.json">money assumptions</a>. '
    'Every random draw is seeded. Python 3.12 with DuckDB, NumPy and SciPy.</p>'))
meth_body = (hero(MH1, [f"Over twelve weeks it added {num(r12_gap)}. Data, method, the predictions and how they came out, the changes made after the results, the "
                        "checks, a glossary and the downloads."], "", "method.html") + section_bar(MSECT) + m_data + m_parts
             + m_pred + m_change + m_checks +
             m_gloss + m_down + NEXT)
pages_written["method.html"] = write("method.html", "Method and checks", "Data, method, predictions, checks and "
                                     "downloads for the experiment design study.", meth_body)


# ---------------------------------------------------------------- number check over the visible text
class Text(HTMLParser):
    def __init__(self):
        super().__init__()
        self.skip, self.out = 0, []

    def handle_starttag(self, tag, attrs):
        if tag in ("style", "script", "title"):
            self.skip += 1

    def handle_endtag(self, tag):
        if tag in ("style", "script", "title"):
            self.skip -= 1

    def handle_data(self, data):
        if not self.skip:
            self.out.append(data)


LITERAL = {"0", "1", "2", "3", "4", "5", "7", "8", "10", "12", "14", "20", "30", "80", "100", "2011", "2.1", "4.0",
           "3.12", "0.1", "0.01", "0.05", "4.5", "95"}
problems = []
for name, page in pages_written.items():
    t = Text()
    t.feed(page)
    text = " ".join(t.out)
    for tok in re.findall(r"\d[\d,]*(?:\.\d+)?", text):
        k = tok.replace(",", "")
        if k not in SEEN and k not in LITERAL:
            problems.append(f"{name}: {tok}")
chk = ROOT / "_private" / "checks"
if chk.exists():
    (chk / "numbers-r1.txt").write_text("\n".join(problems + [f"VERDICT: {'PASS' if not problems else 'FAIL'}"]) + "\n",
                                        encoding="utf-8")
print("number check:", "PASS" if not problems else "FAIL " + "; ".join(problems[:20]))
