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
      f"{rate26 / 100 * (denominator_k - denominator25_k):,.0f}k comes from the larger population base alone")''',
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
      note="documented discrepancy: ask ONS which population base the counts use")
check("MYE mid-2025 16+ method reproduces 'around 4.7 million'", round(mye26_k / 1000, 1) == 4.7, 4.7,
      f"{mye26_k:,.0f}k (population {pop25:,})", blocking=False,
      note="documented discrepancy: ask ONS which population base the counts use")''',
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


if __name__ == "__main__":
    NB_DIR.mkdir(exist_ok=True)
    for name, cells in [("01_assemble_tables", ASSEMBLE), ("02_reconciliation_gate", GATE),
                        ("03_own_break", OWN_BREAK)]:
        nbf.write(nb(cells), NB_DIR / f"{name}.ipynb")
        print(f"wrote notebooks/{name}.ipynb")
