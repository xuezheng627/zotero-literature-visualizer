#!/usr/bin/env python3
"""Bridge zotero-literature-visualizer metadata with sciencedirect-live-session-fetcher.

This helper does not download PDFs itself. It prepares the CSV consumed by the
ScienceDirect live-session fetcher and imports that fetcher's result CSVs back
into the review metadata after the user has completed an authorized browser
session.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import shutil
from pathlib import Path
from typing import Any


FIELDS = ["number", "doi", "title", "year", "journal", "note", "formatted"]


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def papers_from_payload(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, dict) and isinstance(payload.get("papers"), list):
        return payload["papers"]
    if isinstance(payload, list):
        return payload
    raise SystemExit("Expected JSON list or object with papers[]")


def doi_of(paper: dict[str, Any]) -> str:
    return str(paper.get("doi") or paper.get("doi_url", "")).replace("https://doi.org/", "").strip()


def is_elsevier(paper: dict[str, Any]) -> bool:
    doi = doi_of(paper).lower()
    blob = " ".join(
        str(paper.get(key, ""))
        for key in ("publisher", "homepage_url", "if_evidence_url", "official_if_evidence_url", "doi_url", "landing_page_url")
    ).lower()
    return doi.startswith("10.1016/") or "elsevier" in blob or "sciencedirect.com" in blob


def has_local_pdf(paper: dict[str, Any]) -> bool:
    for key in ("local_pdf", "local_pdf_path", "pdf_path", "downloaded_pdf"):
        value = str(paper.get(key) or "").strip()
        if value and Path(value).exists():
            return True
    return False


def slug(text: str, max_len: int = 92) -> str:
    value = text.encode("ascii", "ignore").decode("ascii")
    value = re.sub(r"[^A-Za-z0-9]+", "-", value.lower()).strip("-")
    return (value[:max_len].strip("-") or "paper")


def prepare_csv(args: argparse.Namespace) -> None:
    run_dir = Path(args.run_dir)
    source = Path(args.source) if args.source else run_dir / "metadata" / "verified-high-if-papers.json"
    papers = papers_from_payload(read_json(source))
    rows: list[dict[str, str]] = []
    for index, paper in enumerate(papers, start=1):
        if not is_elsevier(paper):
            continue
        if args.missing_only and has_local_pdf(paper):
            continue
        doi = doi_of(paper)
        if not doi:
            continue
        rows.append(
            {
                "number": str(paper.get("rank") or paper.get("original_verified_rank") or index),
                "doi": doi,
                "title": str(paper.get("title") or ""),
                "year": str(paper.get("publication_year") or str(paper.get("publication_date") or "")[:4]),
                "journal": str(paper.get("journal") or ""),
                "note": str(paper.get("landing_page_url") or paper.get("doi_url") or f"https://doi.org/{doi}"),
                "formatted": str(paper.get("title") or ""),
            }
        )
    output = Path(args.output) if args.output else run_dir / "sciencedirect-fetch-input.csv"
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    print(f"wrote {len(rows)} rows to {output}")


def is_pdf(path: Path) -> bool:
    try:
        return path.exists() and path.open("rb").read(5) == b"%PDF-"
    except OSError:
        return False


def import_results(args: argparse.Namespace) -> None:
    run_dir = Path(args.run_dir)
    target = Path(args.target) if args.target else run_dir / "metadata" / "verified-high-if-papers.json"
    payload = read_json(target)
    papers = papers_from_payload(payload)
    by_doi = {doi_of(paper).lower(): paper for paper in papers if doi_of(paper)}
    pdf_dir = run_dir / "pdfs"
    pdf_dir.mkdir(parents=True, exist_ok=True)
    imported = 0
    for result_path in [Path(item) for item in args.results]:
        with result_path.open("r", encoding="utf-8-sig", newline="") as handle:
            for row in csv.DictReader(handle):
                if row.get("status") != "downloaded":
                    continue
                doi = (row.get("doi") or "").lower().strip()
                paper = by_doi.get(doi)
                source = Path(row.get("pdf_path") or "")
                if not paper or not is_pdf(source):
                    continue
                rank = int(paper.get("rank") or paper.get("original_verified_rank") or row.get("number") or 0)
                target_pdf = pdf_dir / f"verified-{rank:03d}-{slug(row.get('title') or paper.get('title') or doi)}.pdf"
                if not target_pdf.exists():
                    shutil.copy2(source, target_pdf)
                paper["local_pdf"] = str(target_pdf)
                paper["local_pdf_path"] = str(target_pdf)
                paper["access_status"] = "full-text pdf downloaded and checked via ScienceDirect live session fetcher"
                paper["pdf_source"] = "sciencedirect-live-session-fetcher authorized browser session"
                imported += 1
    write_json(target, payload)
    print(f"imported {imported} downloaded PDFs into {target}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Bridge SLR metadata with ScienceDirect live-session fetcher.")
    sub = parser.add_subparsers(dest="command", required=True)
    prep = sub.add_parser("prepare-csv", help="Create ScienceDirect fetcher input CSV from review metadata.")
    prep.add_argument("--run-dir", required=True)
    prep.add_argument("--source", default="")
    prep.add_argument("--output", default="")
    prep.add_argument("--missing-only", action="store_true")
    prep.set_defaults(func=prepare_csv)

    imp = sub.add_parser("import-results", help="Import ScienceDirect fetcher devtools_results.csv files into metadata.")
    imp.add_argument("--run-dir", required=True)
    imp.add_argument("--target", default="")
    imp.add_argument("--results", nargs="+", required=True)
    imp.set_defaults(func=import_results)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    args.func(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
