"""Shared paths and readers for the two-table domestic abuse verification.

I keep these here so the three notebooks read the ONS workbooks the same way.
Nothing in this module derives a figure: it only locates and reads published cells.
"""

from __future__ import annotations

import hashlib
import html
import re
from pathlib import Path

import openpyxl
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
TABLES = RAW / "ons_tables"
POPULATION = RAW / "ons_population"
PAGES = RAW / "source_pages" / "2026-10-31"
PROCESSED = ROOT / "data" / "processed"

RETRIEVED = "2026-10-31"

# Every raw file I use, with the URL I downloaded it from on the retrieval date.
SOURCES = {
    "ons_tables/annualsupplementarytables_yemar2026.xlsx":
        "https://www.ons.gov.uk/file?uri=/peoplepopulationandcommunity/crimeandjustice/datasets/"
        "crimeinenglandandwalesannualsupplementarytables/march2026/annualsupplementarytablesyemar26.xlsx",
    "ons_tables/domesticabuseprevalenceandvictimcharacteristics_yemar2023.xlsx":
        "https://www.ons.gov.uk/file?uri=/peoplepopulationandcommunity/crimeandjustice/datasets/"
        "domesticabuseprevalenceandvictimcharacteristicsappendixtables/yearendingmarch2023/"
        "domesticabuseprevalenceandvictimcharacteristics2023.xlsx",
    "ons_tables/domesticabuseprevalenceandvictimcharacteristics_yemar2024.xlsx":
        "https://www.ons.gov.uk/file?uri=/peoplepopulationandcommunity/crimeandjustice/datasets/"
        "domesticabuseprevalenceandvictimcharacteristicsappendixtables/yearendingmarch2024/"
        "domesticabuseprevalenceandvictimcharacteristics2024.xlsx",
    "ons_tables/domesticabuseprevalenceandvictimcharacteristics_yemar2025.xlsx":
        "https://www.ons.gov.uk/file?uri=/peoplepopulationandcommunity/crimeandjustice/datasets/"
        "domesticabuseprevalenceandvictimcharacteristicsappendixtables/yearendingmarch2025/"
        "domesticabuseprevalenceandvictimcharacteristics2025.xlsx",
    "ons_population/mye24tablesew.xlsx":
        "https://www.ons.gov.uk/file?uri=/peoplepopulationandcommunity/populationandmigration/"
        "populationestimates/datasets/estimatesofthepopulationforenglandandwales/"
        "mid20242023localauthorityboundaries/mye24tablesew.xlsx",
    "ons_population/mye25tablesew.xlsx":
        "https://www.ons.gov.uk/file?uri=/peoplepopulationandcommunity/populationandmigration/"
        "populationestimates/datasets/estimatesofthepopulationforenglandandwales/"
        "mid20252023localauthorityboundaries/mye25tablesew.xlsx",
}

PAGE_SOURCES = {
    "ons_bulletin_crime_ew_yejune2026.html":
        "https://www.ons.gov.uk/peoplepopulationandcommunity/crimeandjustice/bulletins/crimeinenglandandwales/yearendingjune2026",
    "ons_blog_rise_in_domestic_abuse_estimates.html":
        "https://blog.ons.gov.uk/2026/10/22/a-rise-in-domestic-abuse-estimates-but-too-soon-to-identify-a-trend/",
    "ons_methodology_evaluating_new_measure_da.html":
        "https://www.ons.gov.uk/peoplepopulationandcommunity/crimeandjustice/methodologies/evaluatinganewmeasureofdomesticabuse",
    "ons_dataset_annual_supplementary_tables.html":
        "https://www.ons.gov.uk/peoplepopulationandcommunity/crimeandjustice/datasets/crimeinenglandandwalesannualsupplementarytables",
    "ons_dataset_da_prevalence_victim_characteristics.html":
        "https://www.ons.gov.uk/peoplepopulationandcommunity/crimeandjustice/datasets/domesticabuseprevalenceandvictimcharacteristicsappendixtables",
    "ons_dataset_population_estimates_ew.html":
        "https://www.ons.gov.uk/peoplepopulationandcommunity/populationandmigration/populationestimates/datasets/estimatesofthepopulationforenglandandwales",
    "ons_release_crime_ew_yejune2026.html":
        "https://www.ons.gov.uk/releases/crimeinenglandandwalesyearendingjune2026",
    "ons_release_da_overview_november2026.html":
        "https://www.ons.gov.uk/releases/domesticabuseinenglandandwalesoverviewnovember2026",
    "ons_release_combined_measure_december2026.html":
        "https://www.ons.gov.uk/releases/combinedmeasureofdomesticabusesexualvictimisationandstalkingenglandandwalesdecember2026",
    "nhse_cancer_waiting_times_landing.html":
        "https://www.england.nhs.uk/statistics/statistical-work-areas/cancer-waiting-times/",
}


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def read_sheet(workbook: Path, sheet: str, header_startswith: str) -> pd.DataFrame:
    """Read one ONS accessible table: find the header row, keep everything below it as text.

    ONS sheets put a title and notes above the table, so I locate the header by its first cell
    rather than by a fixed row number. I keep every cell as published (numbers stay numbers,
    shorthand such as [x] or [s] stays as a string) so nothing is coerced silently.
    """
    wb = openpyxl.load_workbook(workbook, read_only=True, data_only=True)
    rows = list(wb[sheet].iter_rows(values_only=True))
    wb.close()
    start = next(i for i, r in enumerate(rows)
                 if r and isinstance(r[0], str) and r[0].startswith(header_startswith))
    header = [re.sub(r"\s+", " ", str(c)).strip() if c is not None else f"_blank_{j}"
              for j, c in enumerate(rows[start])]
    body = [r for r in rows[start + 1:] if r and r[0] is not None]
    df = pd.DataFrame(body, columns=header)
    return df.loc[:, [c for c in df.columns if not c.startswith("_blank_")]]


def row(df: pd.DataFrame, label_startswith: str) -> pd.Series:
    """Return the single row whose first column starts with the label; fail if it is not unique."""
    hits = df[df.iloc[:, 0].astype(str).str.startswith(label_startswith)]
    if len(hits) != 1:
        raise ValueError(f"expected one row starting {label_startswith!r}, found {len(hits)}")
    return hits.iloc[0]


def page_text(name: str) -> str:
    """Visible text of a committed page snapshot, with tags stripped and whitespace collapsed."""
    raw = (PAGES / name).read_text(encoding="utf-8", errors="replace")
    raw = re.sub(r"(?is)<(script|style)\b.*?</\1>", " ", raw)
    text = html.unescape(re.sub(r"(?s)<[^>]+>", " ", raw))
    return re.sub(r"\s+", " ", text.replace(" ", " ")).strip()


def population_16_plus(workbook: Path) -> tuple[int, str]:
    """England and Wales population aged 16 and over from MYE2 (Persons), summed from single years.

    Returns the total and the sheet title, so the notebook can show which mid-year it is.
    """
    wb = openpyxl.load_workbook(workbook, read_only=True, data_only=True)
    ws = wb["MYE2 - Persons"]
    title, header = None, None
    for r in ws.iter_rows(values_only=True):
        if title is None:
            title = r[0]
        if r[0] == "Code":
            header = [str(c) if c is not None else None for c in r]
        elif header and r[0] == "K04000001":
            ages = {h: v for h, v in zip(header, r) if h is not None and h.rstrip("+").isdigit()}
            wb.close()
            return int(sum(v for h, v in ages.items() if int(h.rstrip("+")) >= 16)), title
    wb.close()
    raise ValueError("England and Wales row (K04000001) not found in MYE2 - Persons")
