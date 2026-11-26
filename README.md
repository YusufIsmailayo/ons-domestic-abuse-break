# Domestic abuse prevalence across a survey break: verification before writing

A two-table check (Python, pandas, Parquet, Jupyter) that I ran before writing about the ONS's
year ending March 2026 domestic abuse estimates. The ONS reported a significant increase in
domestic abuse prevalence and, in the same release, said it is too early to read it as a trend,
because the survey changed in the same period. I wanted every figure confirmed against the ONS's
own tables before writing a word.

**Status: reconciliation gate PASSES (58 of 58 blocking checks), re-checked on 26 November 2026 against the ONS's
25 November release: no figure revised. Tables and chart built. No article yet.**

## The ONS's assessment, which everything here is held to

The YE March 2026 increase *includes real change*. Changes to the questionnaire and how the survey
was run at the start of that year likely affected its size, by an amount that cannot yet be measured.
Nothing in this repository estimates that amount, and nothing here suggests the increase is only a
survey effect. The exact ONS wording is in `data/processed/ons_wording.csv`, taken from the committed
bulletin snapshot.

## Run order

```
pip install -r requirements.txt
cd notebooks
jupyter nbconvert --to notebook --execute --inplace 01_assemble_tables.ipynb 02_reconciliation_gate.ipynb 03_own_break.ipynb 04_chart.ipynb
```

`02_reconciliation_gate.ipynb` raises on any failed blocking check, so a scripted run exits non-zero.
It writes `data/processed/gate_status.json` with hashes of the two tables, and `04_chart` refuses to
run unless those hashes match.

The notebooks are generated from `src/build_notebooks.py`; shared readers are in `src/common.py`.

| Notebook | What it does |
|---|---|
| `01_assemble_tables` | source manifest with SHA-256; Table 1 (new questions) and Table 2 (old questions) as separate Parquet files |
| `02_reconciliation_gate` | rebuilds 9.6%, 7.8%, the partner and family figures, around 4.7m and around 3.8m; checks significance flags and bulletin wording; checks the two bases can't be joined; fails on any revision in the YE March 2026 edition of the domestic abuse tables (25 November 2026) |
| `03_own_break` | recomputes, from my Cancer Waiting Times pipeline, the rows I set aside at NHS England's October 2023 standards change |
| `04_chart` | the article's chart (`charts/domestic_abuse_two_question_sets.png` and `.svg`) and alt text generated from the same numbers |

## The two tables

| | Table 1: `table1_new_questions` | Table 2: `table2_old_questions` |
|---|---|---|
| Questions | new, first asked April 2023 | in use from April 2004 |
| Age band | 16 and over | long run 16 to 59; a 16+ run for YE Mar 2022 to 2024 kept for reference only |
| Years | YE Mar 2024, 2025 (split sample), 2026 (full sample) | YE Mar 2005 to YE Mar 2024, with YE Mar 2008 and 2021 as explicit gaps |
| Intervals | published for YE Mar 2026 only (A9a) | not published in this table |
| Source | Annual supplementary tables YE Mar 2026, A9a and A9c | Domestic abuse prevalence and victim characteristics YE Mar 2024, Tables 4 and 1b |

The two tables are never stacked. The ONS states the old and new questions are not comparable: the
new questions count someone as a victim from one abusive behaviour, in line with the Domestic Abuse Act
2021, and cover more types of abuse. In YE March 2024 both sets were asked, to different halves of the
sample, and the ONS didn't link them into one series.

## What verification changed

- **There are two breaks, not one.** The question set changed in April 2023, with a split-sample trial
  until March 2025. In April 2025 the new questions went to everyone, on new survey software, with
  self-completion on a tablet. The published 7.8% to 9.6% comparison is new questions against new questions;
  it crosses the April 2025 change, not the April 2023 one.
- **The old series is ages 16 to 59**, not 16 and over, and has its own gaps (YE Mar 2008, YE Mar 2021) and
  part-year collections (YE Mar 2022: six months; YE Mar 2023: eight months).
- **The December 2026 release is about the combined measure** of domestic abuse, sexual victimisation and
  stalking (provisional 2 December 2026). The ONS has not announced a comparability evaluation for the domestic
  abuse series itself. The domestic abuse overview is due 25 November 2026.
- **Counts:** the ONS says counts are prevalence times the mid-year population aged 16 and over. The published
  mid-year estimates don't reproduce the ONS's own counts (they give 3,945k for YE Mar 2025 against a
  published 3,786k). The gate therefore rebuilds the YE Mar 2026 count from the population implied by the
  same release's Worksheet A8 (4,670k, "around 4.7 million"). The ONS has since explained the discrepancy (email of
  11 November 2026): its counts use a population it adjusts from the mid-year estimates for each quarter, and that
  population isn't published. `reconciliation.csv` records this. I quote the ONS's counts rather than recompute them. The 4,670k rebuild
  assumed the domestic abuse count uses the same base as A8's combined measure. The YE March 2026 edition of the
  domestic abuse tables (25 November 2026) now publishes the count, 4,670k, which matches the rebuild, so the
  assumption holds. The gate checks this.
- **Sexual victimisation questions:** the ONS blog places them at April 2025, while note 4 to Worksheet A8 says
  October 2025. The ONS has confirmed both are right (email of 11 November 2026): the old questions were removed in
  April 2025 and the new ones introduced in October 2025, with none in between. This doesn't affect the domestic
  abuse figures.

## The chart

The old-questions series (ages 16 to 59) is a line that stops at YE March 2024, broken at its two gaps. The
new-questions estimates (ages 16 and over) are separate points: open for the split-sample years, filled for
the full-sample year with its 95% confidence interval. A rule marks April 2023 and the 2025/26 survey year is
shaded. There's no trend line and no bridge anywhere. The ONS assessment is printed next to the shaded year,
so it stays with the chart when the chart is shared without its caption. Colours are slots 1 and 2 of a
palette validated for colour-vision deficiency, and the two series also differ by mark (line against points).

## The break in my own loads

NHS England changed the cancer waiting times standards from October 2023 data, and says earlier 31-day and
62-day statistics "are not directly comparable" with later ones. My Cancer Waiting Times pipeline loads the
monthly combined files from April 2022 and keeps only October 2023 onwards. That sets aside 305,174 of 765,412
provider rows (39.9%), 18 months from April 2022 to September 2023. The rows either side of the break carry
identical standard names, so nothing in the file itself marks the break; the warning lives only on the
publisher's page. `03_own_break` recomputes this from the pipeline's Bronze files.

## Sources

ONS (Crown copyright, Open Government Licence v3.0) and NHS England (Open Government Licence v3.0). Every
file's URL and SHA-256 is in `data/processed/source_manifest.csv`. Page snapshots retrieved 31 October 2026
are committed in `data/raw/source_pages/2026-10-31/` because what the pages said on that date is part of
the evidence. Snapshots of the 25 November 2026 release (the overview bulletin, the prevalence and trends
article, the research update, the release and dataset pages) were retrieved on 26 November 2026 and are in
`data/raw/source_pages/2026-11-26/`.
