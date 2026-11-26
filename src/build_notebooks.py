"""Regenerate the three notebooks from the cell text below.

I write the notebooks from here so their code is reviewable as plain Python in git.
Run: python src/build_notebooks.py, then execute them in order (see README).
"""

from pathlib import Path

import nbformat as nbf

NB_DIR = Path(__file__).resolve().parents[1] / "notebooks"

SETUP = '''\
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path.cwd().parent / "src"))
from common import (PAGES, PAGE_SOURCES, POPULATION, PROCESSED, RAW, RETRIEVED, SOURCES, TABLES,
                    page_text, population_16_plus, read_sheet, row, sha256)

pd.set_option("display.width", 200)
pd.set_option("display.max_columns", None)
PROCESSED.mkdir(parents=True, exist_ok=True)'''

SENSITIVITY = '''\
**What these figures are.** Each estimate is the share of people aged 16 and over (or 16 to 59) in
England and Wales who told the Crime Survey for England and Wales they had experienced domestic abuse
in the previous 12 months. They describe millions of people's experience, and I treat them that way.

**The ONS's assessment, which I hold every table and label to.** The year ending March 2026 increase
*includes real change*. Changes to the survey at the start of that year likely affected its size, by an
amount that cannot yet be measured. Nothing in this project estimates that amount, and nothing here
should be read as suggesting the increase is only a survey effect.'''


def nb(cells):
    book = nbf.v4.new_notebook()
    book.metadata["kernelspec"] = {"name": "python3", "display_name": "Python 3", "language": "python"}
    book.cells = [nbf.v4.new_markdown_cell(c[3:]) if c.startswith("md:") else nbf.v4.new_code_cell(c)
                  for c in cells]
    return book


ASSEMBLE = [
    '''md:# 01 Assemble the two tables

I build two tables from the ONS's own workbooks and keep them as two files. They sit on different
question sets and different age bands, and I don't want any later step to join them by accident:

1. `table1_new_questions` uses the new domestic abuse questions, ages 16 and over, for YE March 2024 to YE March 2026.
   YE March 2026 is the first full-sample year and the only one with published confidence intervals.
2. `table2_old_questions` uses the questions in use from April 2004. The long-run series is ages 16 to 59 (YE March 2005
   to YE March 2024). A short 16+ run (YE March 2022 to 2024) is included for reference only.

Reference period, questions basis, sample design and age band are explicit columns in both tables.''',
    "md:" + SENSITIVITY,
    SETUP,
    '''md:## Source manifest

I record every raw file and page snapshot with its size and SHA-256, so anyone can tell whether the ONS
still serves the bytes I verified against on the retrieval date.''',
    '''\
manifest = pd.DataFrame(
    [{"path": f"data/raw/{rel}", "kind": "table", "source_url": url, "retrieved": RETRIEVED,
      "bytes": (RAW / rel).stat().st_size, "sha256": sha256(RAW / rel)} for rel, url in SOURCES.items()]
    + [{"path": f"data/raw/source_pages/{RETRIEVED}/{name}", "kind": "page snapshot", "source_url": url,
        "retrieved": RETRIEVED, "bytes": (PAGES / name).stat().st_size, "sha256": sha256(PAGES / name)}
       for name, url in PAGE_SOURCES.items()]
)

# Files from my re-check against the 25 November 2026 release, each with its own retrieval date.
from common import PAGES_RECHECK, RECHECK_PAGE_SOURCES, RECHECK_SOURCES, RECHECKED
manifest = pd.concat([manifest, pd.DataFrame(
    [{"path": f"data/raw/{rel}", "kind": "table", "source_url": url, "retrieved": RECHECKED,
      "bytes": (RAW / rel).stat().st_size, "sha256": sha256(RAW / rel)} for rel, url in RECHECK_SOURCES.items()]
    + [{"path": f"data/raw/source_pages/{RECHECKED}/{name}", "kind": "page snapshot", "source_url": url,
        "retrieved": RECHECKED, "bytes": (PAGES_RECHECK / name).stat().st_size, "sha256": sha256(PAGES_RECHECK / name)}
       for name, url in RECHECK_PAGE_SOURCES.items()]
)], ignore_index=True)
manifest.to_parquet(PROCESSED / "source_manifest.parquet", index=False)
manifest.to_csv(PROCESSED / "source_manifest.csv", index=False)
manifest.assign(sha256=manifest.sha256.str[:16])[["path", "kind", "bytes", "sha256"]]''',
    '''md:## Table 1: new questions, ages 16 and over

From the *Crime in England and Wales: Annual supplementary tables*, YE March 2026 edition (domestic abuse
sheets added 22 October 2026):

* **A9a**: YE March 2026 estimates with 95% confidence intervals.
* **A9c**: YE March 2024, 2025 and 2026 on the new questions, with the ONS's significance test of 2026 against 2025.

YE March 2024 and 2025 come from the split-sample trial, where about half of respondents answered the new
questions. From April 2025 everyone did, on new survey software, with the self-completion section on a tablet
rather than a laptop. I record that in the `sample_design` and `survey_implementation` columns rather than
smoothing over it.''',
    '''\
AST = TABLES / "annualsupplementarytables_yemar2026.xlsx"
a9a = read_sheet(AST, "Table A9a", "Type of abuse")
a9c = read_sheet(AST, "Table A9c", "Type of abuse")

# My short name for each measure -> the row label the ONS uses in A9a and A9c.
MEASURES = {"any domestic abuse": "Any domestic abuse",
            "any partner abuse": "Any partner abuse",
            "any family abuse": "Any family abuse"}

# One entry per survey year on the new questions. The two set-ups are described in the ONS blog and bulletin.
NEW_YEARS = [
    ("Apr 2023 to Mar 2024", "2024-03", "split sample: about half of respondents",
     "set-up before April 2025"),
    ("Apr 2024 to Mar 2025", "2025-03", "split sample: about half of respondents",
     "set-up before April 2025"),
    ("Apr 2025 to Mar 2026", "2026-03", "full sample",
     "from April 2025: new survey software; self-completion on tablet (was laptop); minor wording changes; "
     "relationship-status question set-up corrected"),
]


def col(df, startswith, endswith=""):
    hits = [c for c in df.columns if c.startswith(startswith) and c.endswith(endswith)]
    if len(hits) != 1:
        raise ValueError(f"expected one column starting {startswith!r}, found {hits}")
    return hits[0]


bases = row(a9c, "Unweighted base")
sig_col = col(a9c, "Apr 2025 to Mar 2026 compared with", "All")
records = []
for period, year_ending, sample, implementation in NEW_YEARS:
    est_col = col(a9c, f"{period} All")
    for measure, label in MEASURES.items():
        r = row(a9c, label)
        rec = dict(reference_period=period, year_ending=year_ending,
                   questions_basis="new questions (first asked April 2023)",
                   sample_design=sample, survey_implementation=implementation,
                   age_band="16 and over", sex="All", measure=measure,
                   estimate_pct=float(r[est_col]), ci_lower_pct=np.nan, ci_upper_pct=np.nan,
                   ci_published=False, change_vs_previous_year=None,
                   unweighted_base=int(bases[est_col]),
                   source_file=AST.name, source_table="A9c")
        if year_ending == "2026-03":
            # For YE March 2026 I take the estimate and its interval from A9a, where the interval is published.
            ra = row(a9a, label)
            rec.update(estimate_pct=float(ra["All in the last year Estimate"]),
                       ci_lower_pct=float(ra["All in the last year Confidence interval Lower bound"]),
                       ci_upper_pct=float(ra["All in the last year Confidence interval Upper bound"]),
                       ci_published=True, change_vs_previous_year=r[sig_col], source_table="A9a (CI), A9c (test)")
        records.append(rec)

table1 = pd.DataFrame(records)
table1.round(2)''',
    '''md:## Table 2: old questions

From *Domestic abuse prevalence and victim characteristics*, YE March 2024 edition. That's the last edition to
carry the old-questions series. The YE March 2025 edition moved to the new questions only.

* **Table 4** is the long-run series for ages 16 to 59. The ONS keeps this age band because the self-completion
  section had an upper age limit of 59 until October 2021.
* **Table 1b** is the old questions for ages 16 and over, YE March 2022 to 2024. I keep it for reference only.
  It is not part of the long run, and it is not comparable with Table 1. The new questions count a person as a
  victim from one abusive behaviour, in line with the Domestic Abuse Act 2021 definition, and cover more types
  of abuse. The ONS states the two sets of estimates are not comparable.

The long run has gaps of its own, and I keep them as rows with no estimate rather than letting a line run across
them: YE March 2008 (comparable questions not asked) and YE March 2021 (domestic abuse questions excluded from the
telephone survey during the pandemic).''',
    '''\
DAPVC24 = TABLES / "domesticabuseprevalenceandvictimcharacteristics_yemar2024.xlsx"
t4 = read_sheet(DAPVC24, "Table 4", "Type of abuse")
t1b = read_sheet(DAPVC24, "Table 1b", "Type of abuse")

OLD_MEASURES = {"any domestic abuse": "Any domestic abuse (",
                "any partner abuse": "Any partner abuse (",
                "any family abuse": "Any family abuse ("}

# Collection notes by year ending, paraphrasing the ONS notes to Table 4 (note numbers in brackets).
ADJUSTED = ("calculated from the original questions with an adjustment to make them comparable with the "
            "questions used from YE March 2013 (note 3)")
OLD_NOTES = {
    "2005-03": ADJUSTED + "; a manual adjustment was also applied to this year (note 5)",
    **{f"{y}-03": ADJUSTED for y in (2006, 2007, 2009, 2010)},
    **{f"{y}-03": ADJUSTED + "; smaller sample, split-sample experiment (note 7)" for y in (2011, 2012)},
    "2013-03": "smaller sample, split-sample experiment (note 7)",
    "2018-03": "smaller sample, split-sample experiment (note 8)",
    "2019-03": "smaller sample, split-sample experiment (note 8)",
    "2020-03": "face-to-face survey suspended 17 March 2020 (note 9)",
    "2022-03": "six months of interviews, October 2021 to March 2022 (note 10)",
    "2023-03": "eight months of interviews; October 2022 to January 2023 excluded after a survey error (note 11)",
    "2024-03": "old questions asked of about half of respondents during the split-sample trial of the new questions",
}
GAPS = {
    "2008-03": ("Apr 2007 to Mar 2008", "not available: comparable questions were not asked this year (note 6)"),
    "2021-03": ("Apr 2020 to Mar 2021", "not collected: domestic abuse questions were excluded from the telephone "
                                        "survey that replaced face-to-face interviews during the pandemic (note 9)"),
}


def period_columns(df):
    out = {}
    for c in df.columns:
        if " compared with " in c:
            continue
        parts = c.split(" ")
        if len(parts) >= 5 and parts[0] in ("Apr", "Oct") and parts[2] == "to" and parts[3] == "Mar":
            out[c] = (" ".join(parts[:5]), f"{parts[4]}-03")
    return out


def old_rows(df, table, age_band, long_run, sex_suffix=""):
    recs = []
    base = row(df, "Unweighted base")
    for c, (period, year_ending) in period_columns(df).items():
        if sex_suffix and not c.split(" [")[0].endswith(sex_suffix):
            continue
        for measure, label in OLD_MEASURES.items():
            v = row(df, label)[c]
            published = isinstance(v, (int, float))
            recs.append(dict(
                reference_period=period, year_ending=year_ending,
                questions_basis="old questions (in use from April 2004)",
                age_band=age_band, sex="All", measure=measure, long_run_series=long_run,
                estimate_pct=float(v) if published else np.nan,
                status="published" if published else GAPS[year_ending][1],
                collection_note=OLD_NOTES.get(year_ending, ""),
                unweighted_base=int(base[c]) if published else pd.NA,
                source_file=DAPVC24.name, source_table=table))
    return recs


recs = old_rows(t4, "Table 4", "16 to 59", True) + old_rows(t1b, "Table 1b", "16 and over", False, " All")

# YE March 2021 has no column in Table 4 at all, so I add it explicitly as a gap row.
for measure in OLD_MEASURES:
    recs.append(dict(reference_period=GAPS["2021-03"][0], year_ending="2021-03",
                     questions_basis="old questions (in use from April 2004)", age_band="16 to 59", sex="All",
                     measure=measure, long_run_series=True, estimate_pct=np.nan, status=GAPS["2021-03"][1],
                     collection_note="", unweighted_base=pd.NA, source_file=DAPVC24.name,
                     source_table="Table 4 (no column; note 9)"))

table2 = (pd.DataFrame(recs)
          .astype({"unweighted_base": "Int64"})
          .sort_values(["long_run_series", "measure", "year_ending"], ascending=[False, True, True])
          .reset_index(drop=True))
table2[table2.measure.eq("any domestic abuse")].round(2)''',
    '''md:## Structural checks before saving

The two tables must not share a questions basis, and the long run must be one age band. If either fails, I
stop here rather than write files a chart could read.''',
    '''\
assert set(table1.questions_basis).isdisjoint(table2.questions_basis), "a questions basis appears in both tables"
assert set(table1.age_band) == {"16 and over"}
assert set(table2.loc[table2.long_run_series, "age_band"]) == {"16 to 59"}
assert not table2.loc[table2.long_run_series].duplicated(["measure", "year_ending"]).any()
assert table2.loc[table2.estimate_pct.isna(), "year_ending"].unique().tolist() == ["2008-03", "2021-03"]

for name, df in [("table1_new_questions", table1), ("table2_old_questions", table2)]:
    df.to_parquet(PROCESSED / f"{name}.parquet", index=False)
    df.to_csv(PROCESSED / f"{name}.csv", index=False)
    print(f"wrote {name}: {len(df)} rows")''',
]


GATE = [
    '''md:# 02 Reconciliation gate

Before anything is derived from these tables, I rebuild the ONS's own published headline from them and
confirm it matches at the precision the ONS published. The gate raises an error if any blocking check fails,
so a scripted run stops here and the chart notebook never runs.

Blocking checks cover the headline percentages, the counts, the significance results, the wording in the
committed bulletin snapshot and the structure of the two tables. Informational checks record things I found
along the way. They don't stop the run, but each one is written to `reconciliation.csv`.''',
    "md:" + SENSITIVITY,
    SETUP,
    '''\
table1 = pd.read_parquet(PROCESSED / "table1_new_questions.parquet")
table2 = pd.read_parquet(PROCESSED / "table2_old_questions.parquet")
AST = TABLES / "annualsupplementarytables_yemar2026.xlsx"
DAPVC25 = TABLES / "domesticabuseprevalenceandvictimcharacteristics_yemar2025.xlsx"
DAPVC23 = TABLES / "domesticabuseprevalenceandvictimcharacteristics_yemar2023.xlsx"
bulletin = page_text("ons_bulletin_crime_ew_yejune2026.html")

results = []


def check(name, passed, expected, got, blocking=True, note=""):
    results.append(dict(check=name, blocking=blocking, passed=bool(passed),
                        expected=str(expected), got=str(got), note=note))
    flag = "PASS" if passed else ("FAIL" if blocking else "NOTE")
    print(f"[{flag}] {name}: expected {expected}, got {got}")


def est(year_ending, measure):
    s = table1[(table1.year_ending == year_ending) & (table1.measure == measure)]
    assert len(s) == 1
    return s.iloc[0]''',
    '''md:## 1. Headline percentages at published precision

The ONS publishes these to one decimal place in the bulletin. I round the unrounded table values once, at
the point of comparison, and nowhere else.''',
    '''\
PUBLISHED = {("2026-03", "any domestic abuse"): 9.6, ("2026-03", "any partner abuse"): 7.9,
             ("2026-03", "any family abuse"): 2.8, ("2025-03", "any domestic abuse"): 7.8,
             ("2025-03", "any partner abuse"): 6.1, ("2025-03", "any family abuse"): 2.7}
for (ye, m), published in PUBLISHED.items():
    got = est(ye, m).estimate_pct
    check(f"{m}, YE {ye}, rounds to bulletin figure", round(got, 1) == published, published, f"{got:.4f}")

# The partner and family figures are not parts of the total: some people experience both, so they overlap.
# I show that rather than let anyone try to rebuild 9.6% by adding them.
p, f, a = (est("2026-03", m).estimate_pct for m in ("any partner abuse", "any family abuse", "any domestic abuse"))
check("partner + family exceeds any domestic abuse (overlap, so no sum-of-parts rebuild)", p + f > a,
      f"> {a:.2f}", f"{p + f:.2f}", blocking=False)''',
    '''md:## 2. The two YE March 2026 sheets agree, and earlier releases agree with this one

A9a (with intervals) and A9c (time series) are separate sheets in one workbook, so I check they carry the same
YE March 2026 numbers. Then I compare YE March 2024 and 2025 with the figures first published in the YE March 2025
edition, to see whether anything was revised between releases.''',
    '''\
a9a = read_sheet(AST, "Table A9a", "Type of abuse")
a9c = read_sheet(AST, "Table A9c", "Type of abuse")
c26 = next(c for c in a9c.columns if c.startswith("Apr 2025 to Mar 2026 All"))
for label in ("Any domestic abuse", "Any partner abuse", "Any family abuse"):
    x, y = float(row(a9a, label)["All in the last year Estimate"]), float(row(a9c, label)[c26])
    check(f"A9a and A9c agree for {label.lower()}, YE 2026-03", x == y, f"{x:.10f}", f"{y:.10f}")

t2_25 = read_sheet(DAPVC25, "Table 2", "Type of abuse")
for period, ye in (("Apr 2023 to Mar 2024", "2024-03"), ("Apr 2024 to Mar 2025", "2025-03")):
    first = float(row(t2_25, "Any domestic abuse")[next(c for c in t2_25.columns if c.startswith(f"{period} All"))])
    now = est(ye, "any domestic abuse").estimate_pct
    check(f"any domestic abuse YE {ye}: unchanged since the YE March 2025 edition", abs(first - now) < 1e-9,
          f"{first:.10f}", f"{now:.10f}", blocking=False)''',
    '''md:## 3. The ONS's significance tests match what the bulletin says

The bulletin says the overall and partner increases are significant and that family abuse shows no significant
difference. A9c carries the test result for each.''',
    '''\
for m, expected in (("any domestic abuse", "[s]"), ("any partner abuse", "[s]"), ("any family abuse", "[ns]")):
    got = est("2026-03", m).change_vs_previous_year
    check(f"{m}: YE 2026-03 vs 2025-03 significance flag", got == expected, expected, got)''',
    '''md:## 3b. Figures by sex

The article opens on the figures for women and men, so I hold them to the same standard as the headline. The bulletin
states them to one decimal place. I take YE March 2026 from A9a and check A9c carries the same values, take YE March 2025
from A9c, and check the ONS's significance test for each. If a later release revises any of them, the gate stops here.''',
    '''\
c25 = {s: next(c for c in a9c.columns if c.startswith(f"Apr 2024 to Mar 2025 {s}")) for s in ("Women", "Men")}
c26_sex = {s: next(c for c in a9c.columns if c.startswith(f"Apr 2025 to Mar 2026 {s}")) for s in ("Women", "Men")}
sig = {s: next(c for c in a9c.columns if "statistically significant difference" in c and c.endswith(f" {s}"))
       for s in ("Women", "Men")}

# Published in the bulletin text: (YE March 2025, YE March 2026). All four rises are reported as significant.
BY_SEX = {("Any domestic abuse", "Women"): (9.1, 11.5), ("Any domestic abuse", "Men"): (6.5, 7.6),
          ("Any partner abuse", "Women"): (7.3, 9.5), ("Any partner abuse", "Men"): (4.9, 6.3)}
for (label, sex), (pub25, pub26) in BY_SEX.items():
    v26 = float(row(a9a, label)[f"{sex} in the last year Estimate"])
    v26c = float(row(a9c, label)[c26_sex[sex]])
    v25 = float(row(a9c, label)[c25[sex]])
    flag = str(row(a9c, label)[sig[sex]]).strip()
    name = f"{label.lower()}, {sex.lower()}"
    check(f"{name}, YE 2026-03, rounds to bulletin figure", round(v26, 1) == pub26, pub26, f"{v26:.4f}")
    check(f"{name}, YE 2026-03: A9a and A9c agree", v26 == v26c, f"{v26:.10f}", f"{v26c:.10f}")
    check(f"{name}, YE 2025-03, rounds to bulletin figure", round(v25, 1) == pub25, pub25, f"{v25:.4f}")
    check(f"{name}: YE 2026-03 vs 2025-03 significance flag", flag == "[s]", "[s]", flag)''',
    '''md:## 4. Counts

The ONS's note says counts are "derived by multiplying the prevalence rate by the population aged 16 years and
over in England and Wales" from the mid-year estimates. I tried that with the published mid-year estimates, and it
does not reproduce the ONS's own published counts. Section 4b records that. So I rebuild the counts from the
ONS's own published rate and count pairs instead:

* **YE March 2025**: the count is published directly (Table 3 of the YE March 2025 edition), so I check it rounds to "around 3.8 million".
* **YE March 2026**: no table publishes a domestic abuse count; it appears only in the bulletin text. Worksheet A8 of
  the same release publishes a rate *and* a count for the combined measure, on the same population base (A8 note 5).
  That pair gives the population the ONS used, and I apply it to the domestic abuse rate. It is a different measure,
  so the rebuild is not circular.''',
    '''\
t3_25 = read_sheet(DAPVC25, "Table 3", "Type of abuse")
any25 = t3_25[(t3_25.iloc[:, 0] == "Any domestic abuse") & (t3_25.Sex == "All")].iloc[0]
count25_k = float(any25["Victims in the last year (000s)"])
check("YE 2025-03 count rounds to 'around 3.8 million'", round(count25_k / 1000, 1) == 3.8, 3.8, f"{count25_k:,.0f}k")

wb_rows = read_sheet(AST, "Worksheet A8", "Abuse type")   # first table in the sheet is A8a (rates)
a8_rate = float(wb_rows.iloc[0, 1])
a8_count_k = float(wb_rows[wb_rows.iloc[:, 0].astype(str).str.startswith("Any domestic abuse")].iloc[1, 1])
denominator_k = a8_count_k / (a8_rate / 100)
# The A8 count is rounded to the nearest thousand, so the population it implies has a small range.
denom_range = [(a8_count_k + d) / (a8_rate / 100) for d in (-0.5, 0.5)]
rate26 = est("2026-03", "any domestic abuse").estimate_pct
count26_k = rate26 / 100 * denominator_k
count_range = [rate26 / 100 * d for d in denom_range]
check("YE 2026-03 count rebuilt from A8's population rounds to 'around 4.7 million'",
      all(round(c / 1000, 1) == 4.7 for c in count_range), 4.7,
      f"{count26_k:,.0f}k (range {count_range[0]:,.0f}k to {count_range[1]:,.0f}k)",
      note=f"population implied by A8: {denominator_k:,.0f}k aged 16+")

denominator25_k = count25_k / (est("2025-03", "any domestic abuse").estimate_pct / 100)
print(f"\\nPopulation implied by the ONS's own counts: YE 2025-03 {denominator25_k:,.0f}k, YE 2026-03 {denominator_k:,.0f}k")
print(f"Difference between the two published counts: {count26_k - count25_k:,.0f}k, of which about "
      f"{rate26 / 100 * (denominator_k - denominator25_k):,.0f}k comes from the larger population base alone (assumes the domestic abuse count uses A8's population base, which the ONS hasn't confirmed)")''',
    '''md:### 4b. What the published mid-year estimates give (informational)

I record this, but it doesn't block the gate. Summing single years of age 16 and over from MYE2 gives a population
about 2 million larger than the one the ONS's own counts imply. The ONS's counts are probably based on a different
population (for example, the household population the survey samples), but I haven't confirmed that. It's a
question for crimestatistics@ons.gov.uk, and the article should quote the ONS's counts, not this method.''',
    '''\
pop24, title24 = population_16_plus(POPULATION / "mye24tablesew.xlsx")
pop25, title25 = population_16_plus(POPULATION / "mye25tablesew.xlsx")
mye25_k = est("2025-03", "any domestic abuse").estimate_pct / 100 * pop24 / 1000
mye26_k = rate26 / 100 * pop25 / 1000
check("MYE mid-2024 16+ method reproduces the YE 2025-03 published count", abs(mye25_k - count25_k) < 1,
      f"{count25_k:,.0f}k", f"{mye25_k:,.0f}k (population {pop24:,})", blocking=False,
      note="explained by the ONS (email, 11 Nov 2026): counts use an adjusted population base that isn't published")
check("MYE mid-2025 16+ method reproduces 'around 4.7 million'", round(mye26_k / 1000, 1) == 4.7, 4.7,
      f"{mye26_k:,.0f}k (population {pop25:,})", blocking=False,
      note="explained by the ONS (email, 11 Nov 2026): counts use an adjusted population base that isn't published")''',
    '''md:## 5. The bulletin snapshot says what the tables say

These are the exact phrases in the committed snapshot of the bulletin (retrieved 31 October 2026). I also keep
the ONS's assessment word for word in `ons_wording.csv`, so any label or caption quotes it from the snapshot
rather than from memory.''',
    '''\
PHRASES = {
    "headline 9.6% and count": "Around 9.6% of people aged 16 years and over experienced domestic abuse in the last "
                               "year (around 4.7 million people)",
    "previous year 7.8% and count": "(7.8%; around 3.8 million people)",
    "partner abuse 7.9% vs 6.1%": "significant increase in partner abuse (7.9%) compared with the previous year (6.1%)",
    "family abuse 2.8% vs 2.7%": "(2.8% in YE March 2026 compared with 2.7% in YE March 2025)",
    "ONS assessment: real change": "our best assessment is that this increase also includes real change rather than "
                                   "solely being the result of sampling uncertainty and question changes",
    "ONS assessment: survey changes": "Changes to the questionnaire and its implementation at the start of the survey "
                                      "year have likely affected the scale of the increase in our prevalence estimates",
    "ONS assessment: too early": "it is too early to say whether this increase will come to represent a new, higher "
                                "level of prevalence",
}
for name, phrase in PHRASES.items():
    check(f"bulletin snapshot contains: {name}", phrase in bulletin, "present", "present" if phrase in bulletin else "missing")

wording = pd.DataFrame([{"key": k, "text": v, "source": "ons_bulletin_crime_ew_yejune2026.html", "retrieved": RETRIEVED}
                        for k, v in PHRASES.items() if k.startswith("ONS assessment")])
wording.to_csv(PROCESSED / "ons_wording.csv", index=False)''',
    '''md:## 6. The two bases stay apart

The break is the point of this piece, so the gate checks the tables can't be joined by accident: separate questions
bases, one age band per long run, the old series ending at YE March 2024 and its two gaps kept as gaps. I also
compare the old series between the YE March 2023 and 2024 editions, to check for revisions (informational).''',
    '''\
check("questions bases are disjoint between the tables",
      set(table1.questions_basis).isdisjoint(table2.questions_basis), "disjoint",
      sorted(set(table1.questions_basis) | set(table2.questions_basis)))
long_run = table2[table2.long_run_series & table2.measure.eq("any domestic abuse")]
check("long-run old series is ages 16 to 59 only", set(long_run.age_band) == {"16 to 59"}, {"16 to 59"}, set(long_run.age_band))
check("long-run old series runs YE 2005-03 to YE 2024-03",
      (long_run.year_ending.min(), long_run.year_ending.max()) == ("2005-03", "2024-03"),
      ("2005-03", "2024-03"), (long_run.year_ending.min(), long_run.year_ending.max()))
check("YE 2008-03 and 2021-03 kept as gaps with no estimate",
      long_run.loc[long_run.estimate_pct.isna(), "year_ending"].tolist() == ["2008-03", "2021-03"],
      ["2008-03", "2021-03"], long_run.loc[long_run.estimate_pct.isna(), "year_ending"].tolist())
last_old = long_run.dropna(subset=["estimate_pct"]).iloc[-1]
check("last old-questions estimate (16 to 59, YE 2024-03) as published", round(last_old.estimate_pct, 2) == 5.35,
      5.35, f"{last_old.estimate_pct:.4f}")

t4_23 = read_sheet(DAPVC23, "Table 4", "Type of abuse")
r23 = row(t4_23, "Any domestic abuse (")
diffs = []
for c in t4_23.columns[1:]:
    if " compared with " in c or not isinstance(r23[c], (int, float)):
        continue
    ye = f"{c.split(' ')[4]}-03"
    now = long_run.loc[long_run.year_ending == ye, "estimate_pct"]
    if len(now):
        diffs.append(abs(float(r23[c]) - float(now.iloc[0])))
check("old series unchanged between the YE 2023 and YE 2024 editions", max(diffs) < 1e-9, 0, f"max diff {max(diffs):.2e}",
      blocking=False)''',
    '''md:## 7. The YE March 2026 edition of the domestic abuse tables (published 25 November 2026)

The ONS published a new edition of *Domestic abuse prevalence and victim characteristics* with its November overview.
Its Table 2 carries the new-questions series for YE March 2024 to 2026. I check every figure the gate already holds
against it at full precision. Any difference is a revision, and a revision fails the gate: the article must not
go out on a number the ONS has since changed.

The new edition names some rows and columns differently ("Partner abuse" rather than "Any partner abuse", "Female"
and "Male" rather than "Women" and "Men"), so I map the labels explicitly rather than match loosely.

Its Table 3 also publishes the YE March 2026 count for the first time. Section 4 rebuilt that count from Worksheet A8's
population, on the assumption that the domestic abuse count uses the same population base. If the published count
matches the rebuild, the assumption holds.''',
    '''\
from common import RECHECKED

DAPVC26 = TABLES / "domesticabuseprevalenceandvictimcharacteristics_yemar2026.xlsx"
t2_26 = read_sheet(DAPVC26, "Table 2", "Type of abuse")
t3_26 = read_sheet(DAPVC26, "Table 3", "Type of abuse")

# The gate's names -> the labels the new edition uses.
NEW_LABEL = {"any domestic abuse": "Any domestic abuse", "any partner abuse": "Partner abuse",
             "any family abuse": "Family abuse", "Any domestic abuse": "Any domestic abuse",
             "Any partner abuse": "Partner abuse"}
NEW_SEX = {"All": "All", "Women": "Female", "Men": "Male"}
PERIOD = {"2024-03": "Apr 2023 to Mar 2024", "2025-03": "Apr 2024 to Mar 2025", "2026-03": "Apr 2025 to Mar 2026"}
TOL = 1e-9


def new_edition(label, year_ending, sex="All"):
    prefix = f"{PERIOD[year_ending]} {NEW_SEX[sex]}"
    col = next(c for c in t2_26.columns if c.startswith(prefix))
    return float(row(t2_26, NEW_LABEL[label])[col])


def unchanged(name, held, new):
    check(f"{name}: unchanged in the YE March 2026 edition", abs(new - held) < TOL, f"{held:.10f}", f"{new:.10f}",
          note=f"Table 2, retrieved {RECHECKED}")


for ye in ("2025-03", "2026-03"):
    for m in ("any domestic abuse", "any partner abuse", "any family abuse"):
        unchanged(f"{m}, YE {ye}", est(ye, m).estimate_pct, new_edition(m, ye))

for (label, sex) in BY_SEX:
    name = f"{label.lower()}, {sex.lower()}"
    unchanged(f"{name}, YE 2025-03", float(row(a9c, label)[c25[sex]]), new_edition(label, "2025-03", sex))
    unchanged(f"{name}, YE 2026-03", float(row(a9a, label)[f"{sex} in the last year Estimate"]),
              new_edition(label, "2026-03", sex))

unchanged("any domestic abuse, YE 2024-03", est("2024-03", "any domestic abuse").estimate_pct,
          new_edition("any domestic abuse", "2024-03"))

any26 = t3_26[(t3_26.iloc[:, 0] == "Any domestic abuse") & (t3_26.Sex == "All")].iloc[0]
published26_k = float(any26["Victims in the last year (000s)"])
# The published count is rounded to the nearest thousand; the rebuild has a small range from A8's own rounding.
check("YE 2026-03 count now published (Table 3) matches the rebuild from A8's population",
      min(count_range) - 0.5 <= published26_k <= max(count_range) + 0.5, f"{count26_k:,.0f}k",
      f"{published26_k:,.0f}k", note="confirms the domestic abuse count uses the same population base as A8")''',
    '''md:## Verdict''',
    '''\
recon = pd.DataFrame(results)
recon.to_csv(PROCESSED / "reconciliation.csv", index=False)
recon.to_parquet(PROCESSED / "reconciliation.parquet", index=False)

headline = pd.DataFrame([
    dict(figure="any domestic abuse, YE March 2026", published="9.6%", rebuilt=f"{rate26:.4f}%"),
    dict(figure="any domestic abuse, YE March 2025", published="7.8%",
         rebuilt=f"{est('2025-03', 'any domestic abuse').estimate_pct:.4f}%"),
    dict(figure="people, YE March 2026", published="around 4.7 million", rebuilt=f"{count26_k:,.0f}k"),
    dict(figure="people, YE March 2025", published="around 3.8 million", rebuilt=f"{count25_k:,.0f}k"),
])
headline.to_csv(PROCESSED / "headline_rebuilt.csv", index=False)

failed = recon[recon.blocking & ~recon.passed]
notes = recon[~recon.blocking & ~recon.passed]
print(f"{recon.blocking.sum()} blocking checks, {len(failed)} failed; "
      f"{(~recon.blocking).sum()} informational, {len(notes)} recorded as notes")
if len(failed):
    raise RuntimeError("Reconciliation gate FAILED:\\n" + failed[["check", "expected", "got"]].to_string(index=False))

# The chart notebook reads this file and checks the table hashes, so it can't run against tables the gate didn't see.
status = {"gate": "passed", "retrieved": RETRIEVED,
          "inputs": {n: sha256(PROCESSED / f"{n}.parquet") for n in ("table1_new_questions", "table2_old_questions")}}
(PROCESSED / "gate_status.json").write_text(json.dumps(status, indent=2))
print("Reconciliation gate PASSED")
headline''',
]


OWN_BREAK = [
    '''md:# 03 The break I hit in my own loads

The article says I stack monthly publications, which is why this ONS warning stopped me. This notebook
backs that sentence with a number from my own pipeline, recomputed from its files rather than copied from its README.

The break: NHS England changed the cancer waiting times standards from October 2023 data. Its Cancer Waiting
Times page says statistics before October 2023 for the 31-day and 62-day standards "are not directly comparable"
with those after. My Cancer Waiting Times pipeline (`~/Documents/cancer_waiting_time`) loads the monthly combined
files from April 2022 and keeps only October 2023 onwards.''',
    SETUP,
    '''\
import subprocess

CWT = Path.home() / "Documents" / "cancer_waiting_time"
bronze_files = sorted((CWT / "data" / "bronze").glob("cwt_bronze_*.parquet"))
assert bronze_files, f"no Bronze files under {CWT}; this notebook needs the cancer pipeline checked out there"

try:
    cwt_commit = subprocess.run(["git", "-C", str(CWT), "rev-parse", "HEAD"], capture_output=True, text=True,
                                check=True).stdout.strip()
except (subprocess.CalledProcessError, FileNotFoundError):
    cwt_commit = "unknown"

# I apply exactly the two filters my cancer pipeline's Silver notebook applies, in the same order.
df = pd.concat([pd.read_parquet(f) for f in bronze_files], ignore_index=True)
provider = df[df["Basis"] == "Provider"].copy()
provider["period_date"] = pd.to_datetime(provider["Period"], format="mixed", dayfirst=True)
before = provider[provider["period_date"] < "2023-10-01"]
after = provider[provider["period_date"] >= "2023-10-01"]

months = lambda d: d["period_date"].dt.to_period("M")
facts = pd.DataFrame([
    dict(fact="raw rows loaded (all bases)", value=len(df)),
    dict(fact="provider-basis rows", value=len(provider)),
    dict(fact="provider rows before October 2023 (set aside)", value=len(before)),
    dict(fact="share of provider rows set aside (%)", value=round(100 * len(before) / len(provider), 1)),
    dict(fact="months set aside", value=months(before).nunique()),
    dict(fact="first month set aside", value=str(months(before).min())),
    dict(fact="last month set aside", value=str(months(before).max())),
    dict(fact="provider rows kept, October 2023 onwards", value=len(after)),
    dict(fact="months kept", value=months(after).nunique()),
]).assign(source=f"cancer_waiting_time Bronze, commit {cwt_commit[:7]}")
facts''',
    '''md:## Checks

The counts have to match my cancer pipeline's own audit trail (1,076,865 rows loaded, 460,238 kept). The
publisher's statement has to be in the committed snapshot of the NHS England page.

One more thing I check, because it matters for the article: the rows before and after the break use the
**same** standard names. Nothing in the file itself marks the break. The warning is only on the web page,
which is why I snapshot pages.''',
    '''\
assert len(df) == 1_076_865, len(df)
assert len(after) == 460_238, len(after)
assert len(provider) == len(before) + len(after)

nhse = page_text("nhse_cancer_waiting_times_landing.html")
statement = ("statistics from before October 2023 for 31 day and 62 day are not directly comparable to those "
             "after October 2023 due to the introduction of new standards")
assert statement in nhse, "NHS England's comparability statement is not in the snapshot"

same_labels = set(before["Standard_or_Item"]) == set(after["Standard_or_Item"])
print("Standard names identical before and after the break:", same_labels)
print(sorted(after["Standard_or_Item"].unique()))

facts = pd.concat([facts, pd.DataFrame([
    dict(fact="standard names identical either side of the break", value=same_labels,
         source="cancer_waiting_time Bronze"),
    dict(fact="NHS England comparability statement", value=statement,
         source="nhse_cancer_waiting_times_landing.html, retrieved " + RETRIEVED),
])], ignore_index=True)
facts.astype({"value": str}).to_csv(PROCESSED / "own_break.csv", index=False)
facts''',
]


CHART = [
    '''md:# 04 The chart: a gap that is not bridged

This chart argues through a gap. The old-questions series is drawn as a line that stops where those questions
stop. The new-questions estimates are separate points, not joined to the line or to each other. There's no trend
line, no dotted bridge and no line across the two gaps in the old series. Joining any of them would commit the
error the article is about.

Two boundaries are marked, because there are two:

* **April 2023**: the new questions start, asked of about half the sample (a split-sample trial).
* **April 2025**: the new questions go to everyone, on new survey software, with the self-completion section on
  a tablet instead of a laptop. This survey year is shaded.

The ONS's assessment sits on the chart next to the shaded year, not only in the caption. Charts get screenshotted
and shared without their captions, so the chart has to carry its own guardrail.''',
    "md:" + SENSITIVITY,
    SETUP + '''

import matplotlib.pyplot as plt
from matplotlib.lines import Line2D

CHARTS = PROCESSED.parent.parent / "charts"
CHARTS.mkdir(exist_ok=True)''',
    '''md:## The gate must have passed on exactly these tables''',
    '''\
status = json.loads((PROCESSED / "gate_status.json").read_text())
assert status["gate"] == "passed", "reconciliation gate has not passed"
for name, digest in status["inputs"].items():
    assert sha256(PROCESSED / f"{name}.parquet") == digest, f"{name} changed since the gate ran; re-run 02 first"

table1 = pd.read_parquet(PROCESSED / "table1_new_questions.parquet")
table2 = pd.read_parquet(PROCESSED / "table2_old_questions.parquet")
wording = pd.read_csv(PROCESSED / "ons_wording.csv").set_index("key").text

# The on-chart label is my plain-English version of the ONS's assessment. I check the ONS sentences it rests on
# are the ones in the committed bulletin snapshot, so the label can't drift from what the ONS said.
assert "includes real change" in wording["ONS assessment: real change"]
assert "likely affected the scale of the increase" in wording["ONS assessment: survey changes"]
VERDICT = ("ONS assessment: the increase includes real change. Changes to the survey likely affected its size, "
           "by an amount that cannot yet be measured.")
print(VERDICT)''',
    '''md:## Data for the chart

Only the overall measure (any domestic abuse). The old series is the long run for ages 16 to 59; the 16+ reference
rows in Table 2 are not plotted. I place each survey year at its midpoint (a year running April to March is drawn
at the October in the middle), so the April 2023 and April 2025 boundaries fall between the right points.''',
    '''\
def midpoint(year_ending):  # "2024-03" covers April 2023 to March 2024 -> drawn at October 2023
    return int(year_ending[:4]) - 1 + 9.5 / 12

old = (table2[table2.long_run_series & table2.measure.eq("any domestic abuse")]
       .assign(x=lambda d: d.year_ending.map(midpoint)).sort_values("x"))
new = (table1[table1.measure.eq("any domestic abuse")]
       .assign(x=lambda d: d.year_ending.map(midpoint)).sort_values("x"))

# The old series is split wherever an estimate is missing, so no segment crosses a gap.
segments, current = [], []
for _, r in old.iterrows():
    if np.isnan(r.estimate_pct):
        segments.append(current); current = []
    else:
        current.append((r.x, r.estimate_pct))
segments.append(current)
segments = [s for s in segments if s]
print([f"{s[0][0]:.0f} to {s[-1][0]:.0f} ({len(s)} points)" for s in segments])
new[["year_ending", "sample_design", "estimate_pct", "ci_lower_pct", "ci_upper_pct"]].round(2)''',
    '''md:## Draw''',
    '''\
INK, INK_2, INK_3 = "#0b0b0b", "#52514e", "#8a8984"
OLD_C, NEW_C = "#2a78d6", "#eb6834"          # reference palette slots 1 and 2
BAND, RULE, GRID = "#ecebe7", "#52514e", "#e6e5e1"
APR_2023, APR_2025, MAR_2026 = 2023 + 3 / 12, 2025 + 3 / 12, 2026 + 3 / 12

plt.rcParams.update({"font.family": "Arial", "font.size": 11, "text.color": INK,
                     "axes.labelcolor": INK_2, "xtick.color": INK_2, "ytick.color": INK_2})
fig, ax = plt.subplots(figsize=(11, 6.6), dpi=200)
fig.patch.set_facecolor("white")
ax.set_facecolor("white")

# The shaded survey year: April 2025 to March 2026, collected under the new set-up.
ax.axvspan(APR_2025, MAR_2026, color=BAND, lw=0, zorder=0)
# April 2023: the new questions begin on half the sample. A plain rule, not dotted, so it can't read as a bridge.
# It stops below the text block at the top so it never runs through the ONS assessment.
ax.plot([APR_2023, APR_2023], [0, 10.1], color=RULE, lw=1, zorder=1)

# Old questions: a line in separate segments that stops dead at its last published year.
for seg in segments:
    xs, ys = zip(*seg)
    ax.plot(xs, ys, color=OLD_C, lw=2, solid_capstyle="round", zorder=3)
    ax.scatter(xs, ys, s=22, color=OLD_C, edgecolor="white", linewidth=1.5, zorder=4)
last = old.dropna(subset=["estimate_pct"]).iloc[-1]
ax.scatter([last.x], [last.estimate_pct], s=60, color=OLD_C, edgecolor="white", linewidth=2, zorder=5)

# New questions: unconnected points. Open = split sample (about half of respondents); filled = full sample.
for _, r in new.iterrows():
    full = r.sample_design == "full sample"
    if r.ci_published:
        ax.plot([r.x, r.x], [r.ci_lower_pct, r.ci_upper_pct], color=NEW_C, lw=2, solid_capstyle="round", zorder=5)
    ax.scatter([r.x], [r.estimate_pct], s=70, zorder=6, linewidth=2,
               color=NEW_C if full else "white", edgecolor=NEW_C)

# Values on the end points only: where the old series stops, and each new estimate.
ax.annotate(f"{last.estimate_pct:.1f}%", (last.x, last.estimate_pct), xytext=(0, -16), textcoords="offset points",
            ha="center", fontsize=10, color=INK_2)
for _, r in new.iterrows():
    dx = 14 if r.ci_published else 0
    dy = 0 if r.ci_published else 11
    ax.annotate(f"{r.estimate_pct:.1f}%", (r.x, r.estimate_pct), xytext=(dx, dy), textcoords="offset points",
                ha="left" if r.ci_published else "center", va="center" if r.ci_published else "bottom",
                fontsize=10, color=INK_2)

# Direct labels for the two series.
ax.text(2008.9, 7.75, "Old questions, ages 16 to 59", color=INK, fontsize=11, fontweight="bold")
ax.text(2008.9, 7.32, "Questions in use from April 2004. Last published year: to March 2024",
        color=INK_2, fontsize=9.5)
# Level with the first new-questions point but on the far side of the April 2023 rule, where there is room.
ax.text(APR_2023 - 0.2, 8.0, "New questions, ages 16 and over", color=INK, fontsize=11,
        fontweight="bold", ha="right", va="center")

# The two gaps inside the old series, named where they are.
ax.text(midpoint("2008-03"), 4.55, "No comparable\\nquestions", ha="center", va="top", fontsize=8.5, color=INK_3)
ax.text(midpoint("2021-03"), 4.55, "Not collected\\n(pandemic)", ha="center", va="top", fontsize=8.5, color=INK_3)

# April 2023 note, left of its rule.
ax.text(APR_2023 - 0.2, 3.35,
        "April 2023: new questions start, asked of\\nabout half the sample. In the year to March 2024\\n"
        "both sets were asked, to different halves.\\nONS: the two are not comparable.",
        ha="right", va="top", fontsize=9, color=INK_2, linespacing=1.35)

# The shaded year and the ONS assessment, kept together so a screenshot keeps both.
ax.text(APR_2025 - 0.25, 12.35,
        "Shaded: from April 2025 everyone got the new questions, on new survey\\n"
        "software, with the self-completion section on a tablet, not a laptop.",
        ha="right", va="top", fontsize=9.5, color=INK_2, linespacing=1.35)
ax.text(APR_2025 - 0.25, 11.25,
        "ONS assessment: the increase includes real change. Changes to the survey\\n"
        "likely affected its size, by an amount that cannot yet be measured.",
        ha="right", va="top", fontsize=10, color=INK, fontweight="bold", linespacing=1.35)

# Axes: zero baseline, recessive grid, one y scale.
ax.set_ylim(0, 12.6)
ax.set_xlim(2003.9, 2026.75)
ax.set_yticks(range(0, 13, 2))
ax.set_yticklabels([f"{t}%" for t in range(0, 13, 2)])
ticks = ["2005-03", "2010-03", "2015-03", "2020-03", "2026-03"]
ax.set_xticks([midpoint(t) for t in ticks])
ax.set_xticklabels([f"{int(t[:4]) - 1}/{t[2:4]}" for t in ticks])
ax.set_xlabel("Survey year (April to March)", fontsize=10, labelpad=8)
ax.grid(axis="y", color=GRID, lw=0.8, zorder=0)
ax.tick_params(length=0, labelsize=10)
for side in ("top", "right", "left"):
    ax.spines[side].set_visible(False)
ax.spines["bottom"].set_color(INK_3)

legend = [Line2D([0], [0], color=OLD_C, lw=2, marker="o", markersize=5, markeredgecolor="white",
                 label="Old questions, ages 16 to 59"),
          Line2D([0], [0], color="none", marker="o", markersize=8, markerfacecolor="white",
                 markeredgecolor=NEW_C, markeredgewidth=2, label="New questions, half the sample"),
          Line2D([0], [0], color=NEW_C, lw=2, marker="o", markersize=8, markerfacecolor=NEW_C,
                 markeredgecolor=NEW_C, label="New questions, full sample (line: 95% confidence interval)")]
ax.legend(handles=legend, loc="lower left", frameon=False, fontsize=9.5, labelcolor=INK_2, handlelength=1.6,
          borderaxespad=0.2)

fig.text(0.055, 0.965, "Domestic abuse in the last year, England and Wales", fontsize=15, fontweight="bold",
         color=INK, ha="left")
fig.text(0.055, 0.925, "% of people who told the Crime Survey for England and Wales they experienced domestic abuse "
         "in the previous 12 months.\\nThe two question sets are drawn apart: the ONS says they are not comparable.",
         fontsize=10.5, color=INK_2, ha="left", va="top", linespacing=1.35)
fig.text(0.055, 0.02,
         "Source: ONS, Crime in England and Wales: year ending June 2026, Annual supplementary tables A9a and A9c; "
         "Domestic abuse prevalence and victim characteristics,\\nyear ending March 2024, Table 4. Retrieved "
         "31 October 2026. Old and new series differ in questions, definition and age band.",
         fontsize=8.5, color=INK_3, ha="left", va="bottom", linespacing=1.35)
fig.subplots_adjust(left=0.055, right=0.985, top=0.83, bottom=0.17)

for ext in ("png", "svg"):
    fig.savefig(CHARTS / f"domestic_abuse_two_question_sets.{ext}", facecolor="white")
plt.show()''',
    '''md:## Alt text, generated from the same numbers''',
    '''\
o = old.dropna(subset=["estimate_pct"])
n26 = new[new.year_ending.eq("2026-03")].iloc[0]
n = new.set_index("year_ending").estimate_pct
alt = (
    "Chart of the share of people in England and Wales who reported domestic abuse in the previous 12 months. "
    f"A line shows the old survey questions, for ages 16 to 59, from {o.estimate_pct.iloc[0]:.1f}% in 2004/05 to "
    f"{o.estimate_pct.iloc[-1]:.1f}% in 2023/24, where it ends. It has gaps for 2007/08 (no comparable questions) "
    "and 2020/21 (not collected during the pandemic). Separate points, not joined to the line or to each other, "
    f"show the new questions for ages 16 and over: {n['2024-03']:.1f}% in 2023/24 and {n['2025-03']:.1f}% in "
    f"2024/25 from about half the sample, and {n26.estimate_pct:.1f}% in 2025/26 from the full sample "
    f"(95% confidence interval {n26.ci_lower_pct:.1f}% to {n26.ci_upper_pct:.1f}%). A vertical line marks April 2023, "
    "when the new questions began; the ONS says the two question sets are not comparable. The 2025/26 survey year is "
    "shaded: from April 2025 everyone got the new questions, on new survey software and a tablet. " + VERDICT
)
(CHARTS / "domestic_abuse_two_question_sets_alt.txt").write_text(alt + "\\n")
print(alt)''',
]


if __name__ == "__main__":
    NB_DIR.mkdir(exist_ok=True)
    for name, cells in [("01_assemble_tables", ASSEMBLE), ("02_reconciliation_gate", GATE),
                        ("03_own_break", OWN_BREAK), ("04_chart", CHART)]:
        nbf.write(nb(cells), NB_DIR / f"{name}.ipynb")
        print(f"wrote notebooks/{name}.ipynb")
