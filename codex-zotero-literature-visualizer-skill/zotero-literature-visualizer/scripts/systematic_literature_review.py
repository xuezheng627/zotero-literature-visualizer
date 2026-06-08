#!/usr/bin/env python3
"""Collect and finalize systematic literature review metadata.

This script does not call an LLM and does not bypass paywalls. It gathers open
metadata, records OA/PDF availability as metadata, prepares official Impact
Factor evidence templates, filters papers after official evidence is supplied,
and creates manual/authorized-browser PDF access queues.
"""

from __future__ import annotations

import argparse
from collections import Counter
import csv
import datetime as dt
import hashlib
import html
import json
import os
import re
import shutil
import sqlite3
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any


OPENALEX_WORKS = "https://api.openalex.org/works"
OPENALEX_SOURCES = "https://api.openalex.org/sources"
UNPAYWALL = "https://api.unpaywall.org/v2"
USER_AGENT = "CodexSystematicLiteratureReview/1.0"
DEFAULT_MIN_IF = 5.0
DEFAULT_YEARS = 1


def today() -> dt.date:
    return dt.datetime.now(dt.timezone.utc).date()


def clean_text(value: Any) -> str:
    if isinstance(value, list):
        value = " ".join(str(item) for item in value if item)
    if not isinstance(value, str):
        return ""
    value = html.unescape(value)
    value = re.sub(r"<[^>]+>", " ", value)
    value = re.sub(r"\s+", " ", value)
    return value.strip()


def slugify(value: str, fallback: str = "literature-review") -> str:
    value = clean_text(value).lower()
    value = re.sub(r"[^a-z0-9\u4e00-\u9fff]+", "-", value)
    value = value.strip("-")
    return value[:80] or fallback


def normalize_doi(value: Any) -> str:
    if not isinstance(value, str):
        return ""
    doi = value.strip().lower()
    doi = re.sub(r"^https?://(dx\.)?doi\.org/", "", doi)
    return doi.strip()


def doi_url(doi: str) -> str:
    return f"https://doi.org/{doi}" if doi else ""


def read_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    with path.open("r", encoding="utf-8-sig") as handle:
        return json.load(handle)


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
        handle.write("\n")


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key, "") for key in fieldnames})


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def http_get(url: str, *, accept: str = "application/json", retries: int = 3, sleep: float = 0.8) -> bytes:
    headers = {
        "User-Agent": USER_AGENT,
        "Accept": accept,
    }
    last_error: str | None = None
    for attempt in range(1, retries + 1):
        request = urllib.request.Request(url, headers=headers)
        try:
            with urllib.request.urlopen(request, timeout=45) as response:
                return response.read()
        except urllib.error.HTTPError as exc:
            last_error = f"HTTP {exc.code} for {url}"
            if exc.code in {429, 500, 502, 503, 504} and attempt < retries:
                retry_after = exc.headers.get("Retry-After")
                wait = float(retry_after) if retry_after and retry_after.isdigit() else sleep * attempt
                time.sleep(wait)
                continue
            raise RuntimeError(last_error) from exc
        except (urllib.error.URLError, TimeoutError) as exc:
            last_error = f"{type(exc).__name__}: {exc}"
            if attempt < retries:
                time.sleep(sleep * attempt)
                continue
            raise RuntimeError(last_error) from exc
    raise RuntimeError(last_error or f"Failed to fetch {url}")


def http_json(url: str, *, retries: int = 3, sleep: float = 0.8) -> Any:
    raw = http_get(url, retries=retries, sleep=sleep)
    return json.loads(raw.decode("utf-8"))


def inverted_abstract(index: Any) -> str:
    if not isinstance(index, dict):
        return ""
    positions: list[tuple[int, str]] = []
    for word, indexes in index.items():
        if not isinstance(indexes, list):
            continue
        for position in indexes:
            if isinstance(position, int):
                positions.append((position, word))
    positions.sort(key=lambda pair: pair[0])
    return clean_text(" ".join(word for _, word in positions))


def unique_strings(values: list[str]) -> list[str]:
    seen: set[str] = set()
    unique: list[str] = []
    for value in values:
        text = clean_text(value)
        key = text.lower()
        if text and key not in seen:
            unique.append(text)
            seen.add(key)
    return unique


def parse_keyword_group_specs(specs: list[str]) -> dict[str, list[str]]:
    """Parse CLI specs like domain=building|architecture|construction."""
    groups: dict[str, list[str]] = {}
    for spec in specs:
        if "=" not in spec:
            raise SystemExit(f"Invalid --keyword-group value: {spec!r}. Use name=term1|term2.")
        name, raw_terms = spec.split("=", 1)
        group_name = clean_text(name)
        terms = unique_strings(re.split(r"[|;]", raw_terms))
        if not group_name or not terms:
            raise SystemExit(f"Invalid --keyword-group value: {spec!r}.")
        groups[group_name] = terms
    return groups


def years_ago(end: dt.date, years: int) -> dt.date:
    try:
        return end.replace(year=end.year - years)
    except ValueError:
        return end - dt.timedelta(days=365 * years)


def default_keyword_groups() -> dict[str, list[str]]:
    return {
        "construction": [
            "prefabricated building",
            "prefabricated construction",
            "prefab",
            "precast construction",
            "modular building",
            "modular construction",
            "modular integrated construction",
            "off-site construction",
            "offsite construction",
        ],
        "lca": [
            "life cycle assessment",
            "life-cycle assessment",
            "LCA",
            "embodied carbon",
            "carbon footprint",
        ],
        "optimization": [
            "multi-objective optimization",
            "multiobjective optimization",
            "Pareto",
            "NSGA-II",
            "multi-criteria optimization",
        ],
    }


def default_config(
    topic: str,
    mailto: str = "",
    *,
    years: int = DEFAULT_YEARS,
    min_if: float = DEFAULT_MIN_IF,
    keyword_groups: dict[str, list[str]] | None = None,
    queries: list[str] | None = None,
) -> dict[str, Any]:
    end = today()
    start = years_ago(end, max(1, int(years)))
    groups = keyword_groups or default_keyword_groups()
    group_names = list(groups)
    required_groups = [group_names[0]] if len(group_names) > 1 else group_names
    optional_groups = group_names[1:] if len(group_names) > 1 else []
    return {
        "topic": topic,
        "language": "zh-en",
        "mailto": mailto,
        "from_date": start.isoformat(),
        "to_date": end.isoformat(),
        "min_impact_factor": float(min_if),
        "query_logic": "first keyword group AND any later keyword group; override with `queries` for custom searches",
        "include_reviews": True,
        "keyword_groups": groups,
        "required_groups": required_groups,
        "optional_groups": optional_groups,
        "queries": unique_strings(queries or []),
    }


def init_config(args: argparse.Namespace) -> None:
    mailto = args.mailto or os.environ.get("LITERATURE_REVIEW_EMAIL", "")
    keyword_groups = parse_keyword_group_specs(args.keyword_group) if args.keyword_group else None
    payload = default_config(
        args.topic,
        mailto,
        years=args.years,
        min_if=args.min_if,
        keyword_groups=keyword_groups,
        queries=args.query,
    )
    output = Path(args.output)
    write_json(output, payload)
    print(str(output.resolve()))


def openalex_url(path: str, params: dict[str, str], mailto: str = "") -> str:
    if mailto:
        params = {**params, "mailto": mailto}
    return path + "?" + urllib.parse.urlencode(params)


def query_terms(config: dict[str, Any]) -> list[str]:
    explicit_queries = unique_strings([str(item) for item in config.get("queries", []) if item])
    if explicit_queries:
        return explicit_queries
    groups = config.get("keyword_groups", {})
    if not isinstance(groups, dict) or not groups:
        return unique_strings([clean_text(config.get("topic"))])
    group_names = list(groups)
    first_group = [str(item) for item in groups.get(group_names[0], []) if item]
    other_terms: list[str] = []
    for name in group_names[1:]:
        other_terms.extend(str(item) for item in groups.get(name, []) if item)
    if not other_terms:
        return unique_strings(first_group)
    terms: list[str] = []
    for base_term in first_group:
        for other_term in other_terms:
            terms.append(f"{base_term} {other_term}")
    return unique_strings(terms)


def text_hits(text: str, terms: list[str]) -> list[str]:
    text_l = text.lower()
    hits: list[str] = []
    for term in terms:
        term_l = term.lower()
        if term_l in text_l:
            hits.append(term)
    return hits


def classify_candidate(work: dict[str, Any], config: dict[str, Any]) -> dict[str, Any]:
    title = clean_text(work.get("title") or work.get("display_name"))
    abstract = inverted_abstract(work.get("abstract_inverted_index"))
    concepts = [
        clean_text(item.get("display_name"))
        for item in work.get("concepts", [])
        if isinstance(item, dict) and clean_text(item.get("display_name"))
    ]
    topics = [
        clean_text(item.get("display_name"))
        for item in work.get("topics", [])
        if isinstance(item, dict) and clean_text(item.get("display_name"))
    ]
    blob = " ".join([title, abstract, " ".join(concepts), " ".join(topics)]).lower()
    groups_raw = config.get("keyword_groups", {})
    groups = groups_raw if isinstance(groups_raw, dict) else {}
    group_hits = {
        str(name): text_hits(blob, [str(item) for item in terms if item])
        for name, terms in groups.items()
        if isinstance(terms, list)
    }
    matched_groups = [name for name, hits in group_hits.items() if hits]
    required_groups = [str(item) for item in config.get("required_groups", []) if item]
    optional_groups = [str(item) for item in config.get("optional_groups", []) if item]
    if not required_groups and group_hits:
        required_groups = [next(iter(group_hits))]
        optional_groups = [name for name in group_hits if name not in required_groups]
    if not group_hits:
        cross_theme = True
        all_group_match = True
    elif optional_groups:
        cross_theme = all(group_hits.get(name) for name in required_groups) and any(group_hits.get(name) for name in optional_groups)
        all_group_match = all(bool(hits) for hits in group_hits.values())
    else:
        cross_theme = all(group_hits.get(name) for name in required_groups)
        all_group_match = cross_theme
    construction_hits = group_hits.get("construction", [])
    lca_hits = group_hits.get("lca", [])
    optimization_hits = group_hits.get("optimization", [])
    all_three = bool(construction_hits and lca_hits and optimization_hits) if {"construction", "lca", "optimization"} <= set(group_hits) else all_group_match
    score = sum(len(hits) * 2 for hits in group_hits.values()) + len(matched_groups) * 2
    if all_group_match:
        score += 8
    elif cross_theme:
        score += 4
    title_l = title.lower()
    type_value = clean_text(work.get("type"))
    type_crossref = clean_text(work.get("type_crossref"))
    is_review = (
        "review" in type_value.lower()
        or "review" in type_crossref.lower()
        or re.search(r"\b(review|systematic review|bibliometric)\b", title_l) is not None
    )
    return {
        "abstract": abstract,
        "concepts": concepts,
        "topics": topics,
        "construction_hits": construction_hits,
        "lca_hits": lca_hits,
        "optimization_hits": optimization_hits,
        "matched_groups": matched_groups,
        "keyword_hits": group_hits,
        "cross_theme": cross_theme,
        "all_three_themes": all_three,
        "relevance_score": score,
        "article_type": "review article" if is_review else "research article",
    }


def author_string(work: dict[str, Any], max_authors: int = 8) -> str:
    names: list[str] = []
    for authorship in work.get("authorships", [])[:max_authors]:
        if not isinstance(authorship, dict):
            continue
        author = authorship.get("author")
        if isinstance(author, dict):
            name = clean_text(author.get("display_name"))
            if name:
                names.append(name)
    if len(work.get("authorships", [])) > max_authors:
        names.append("et al.")
    return "; ".join(names)


def primary_source(work: dict[str, Any]) -> dict[str, Any]:
    location = work.get("primary_location") if isinstance(work.get("primary_location"), dict) else {}
    source = location.get("source") if isinstance(location.get("source"), dict) else {}
    return source


def best_pdf_url(work: dict[str, Any]) -> tuple[str, str]:
    for location_key in ("best_oa_location", "primary_location"):
        location = work.get(location_key)
        if isinstance(location, dict):
            pdf = clean_text(location.get("pdf_url"))
            if pdf:
                return pdf, f"OpenAlex {location_key}"
    for location in work.get("locations", []) or []:
        if not isinstance(location, dict):
            continue
        pdf = clean_text(location.get("pdf_url"))
        if pdf:
            return pdf, "OpenAlex locations"
    return "", ""


def fetch_source(source_id: str, mailto: str, cache: dict[str, dict[str, Any]]) -> dict[str, Any]:
    if not source_id:
        return {}
    if source_id in cache:
        return cache[source_id]
    if source_id.startswith("https://openalex.org/"):
        source_key = source_id.rstrip("/").rsplit("/", 1)[-1]
        url = f"{OPENALEX_SOURCES}/{urllib.parse.quote(source_key)}"
    elif source_id.startswith("https://api.openalex.org/sources/"):
        url = source_id
    else:
        url = f"{OPENALEX_SOURCES}/{urllib.parse.quote(source_id)}"
    if mailto:
        url += ("&" if "?" in url else "?") + urllib.parse.urlencode({"mailto": mailto})
    try:
        payload = http_json(url, retries=2)
    except Exception as exc:  # noqa: BLE001
        payload = {"id": source_id, "error": str(exc)}
    cache[source_id] = payload
    return payload


def unpaywall_pdf(doi: str, email: str) -> tuple[str, str]:
    if not doi or not email:
        return "", ""
    url = f"{UNPAYWALL}/{urllib.parse.quote(doi)}?" + urllib.parse.urlencode({"email": email})
    try:
        payload = http_json(url, retries=2)
    except Exception:
        return "", ""
    best = payload.get("best_oa_location") if isinstance(payload.get("best_oa_location"), dict) else {}
    pdf = clean_text(best.get("url_for_pdf"))
    landing = clean_text(best.get("url"))
    return pdf, landing


def normalize_work(work: dict[str, Any], config: dict[str, Any], source_cache: dict[str, dict[str, Any]]) -> dict[str, Any] | None:
    title = clean_text(work.get("title") or work.get("display_name"))
    if not title:
        return None
    classification = classify_candidate(work, config)
    if not classification["cross_theme"]:
        return None
    source = primary_source(work)
    source_id = clean_text(source.get("id"))
    source_full = fetch_source(source_id, clean_text(config.get("mailto")), source_cache) if source_id else {}
    summary_stats = source_full.get("summary_stats") if isinstance(source_full.get("summary_stats"), dict) else {}
    openalex_proxy = summary_stats.get("2yr_mean_citedness", "")
    if isinstance(openalex_proxy, (int, float)):
        openalex_proxy_value: str | float = round(float(openalex_proxy), 3)
    else:
        openalex_proxy_value = ""
    source_issn = source_full.get("issn") if isinstance(source_full.get("issn"), list) else source.get("issn", [])
    if not isinstance(source_issn, list):
        source_issn = []
    doi = normalize_doi(work.get("doi"))
    pdf_url, pdf_source = best_pdf_url(work)
    unpaywall_url = ""
    if doi and not pdf_url:
        pdf_url, unpaywall_url = unpaywall_pdf(doi, clean_text(config.get("mailto")))
        if pdf_url:
            pdf_source = "Unpaywall best_oa_location"
    open_access = work.get("open_access") if isinstance(work.get("open_access"), dict) else {}
    return {
        "openalex_id": clean_text(work.get("id")),
        "doi": doi,
        "doi_url": doi_url(doi),
        "title": title,
        "publication_year": work.get("publication_year", ""),
        "publication_date": clean_text(work.get("publication_date")),
        "authors": author_string(work),
        "journal": clean_text(source.get("display_name") or source_full.get("display_name")),
        "source_id": source_id,
        "issn_l": clean_text(source_full.get("issn_l") or source.get("issn_l")),
        "issn": "; ".join(clean_text(item) for item in source_issn if clean_text(item)),
        "publisher": clean_text(source_full.get("host_organization_name") or source.get("host_organization_name")),
        "homepage_url": clean_text(source_full.get("homepage_url")),
        "landing_page_url": clean_text(work.get("doi")) or doi_url(doi) or clean_text(work.get("id")),
        "openalex_url": clean_text(work.get("id")),
        "is_oa": open_access.get("is_oa", ""),
        "oa_status": clean_text(open_access.get("oa_status")),
        "pdf_url": pdf_url,
        "pdf_source": pdf_source,
        "unpaywall_landing_url": unpaywall_url,
        "article_type": classification["article_type"],
        "abstract": classification["abstract"],
        "concepts": "; ".join(classification["concepts"]),
        "topics": "; ".join(classification["topics"]),
        "construction_hits": "; ".join(classification["construction_hits"]),
        "lca_hits": "; ".join(classification["lca_hits"]),
        "optimization_hits": "; ".join(classification["optimization_hits"]),
        "matched_groups": "; ".join(classification["matched_groups"]),
        "keyword_hits": "; ".join(
            f"{name}: {', '.join(hits)}"
            for name, hits in classification["keyword_hits"].items()
            if hits
        ),
        "all_three_themes": classification["all_three_themes"],
        "relevance_score": classification["relevance_score"],
        "cited_by_count": work.get("cited_by_count", ""),
        "openalex_2yr_mean_citedness_proxy": openalex_proxy_value,
        "official_impact_factor": "",
        "official_if_year": "",
        "if_evidence_url": "",
        "if_evidence_note": "",
        "if_verified_date": "",
        "if_status": "official verification needed",
        "access_status": "oa-pdf-available" if pdf_url else "non-oa-or-no-pdf-url",
        "local_pdf": "",
    }


def collect(args: argparse.Namespace) -> None:
    config = read_json(Path(args.config), {})
    if not config:
        raise SystemExit(f"Missing or invalid config: {args.config}")
    output_dir = Path(args.output_dir)
    metadata_dir = output_dir / "metadata"
    metadata_dir.mkdir(parents=True, exist_ok=True)
    per_page = max(1, min(args.rows_per_query, 200))
    max_results = max(1, args.max_results)
    filters = [
        f"from_publication_date:{config['from_date']}",
        f"to_publication_date:{config['to_date']}",
        "type:article",
        "primary_location.source.type:journal",
    ]
    works_by_key: dict[str, dict[str, Any]] = {}
    errors: list[dict[str, str]] = []
    source_cache: dict[str, dict[str, Any]] = {}
    for term in query_terms(config):
        if len(works_by_key) >= max_results * 4:
            break
        cursor = "*"
        fetched_for_term = 0
        while fetched_for_term < args.max_pages_per_query * per_page:
            params = {
                "search": term,
                "filter": ",".join(filters),
                "per-page": str(per_page),
                "cursor": cursor,
            }
            url = openalex_url(OPENALEX_WORKS, params, clean_text(config.get("mailto")))
            try:
                payload = http_json(url)
            except Exception as exc:  # noqa: BLE001
                errors.append({"source": "OpenAlex", "term": term, "error": str(exc)})
                break
            for work in payload.get("results", []):
                if not isinstance(work, dict):
                    continue
                paper = normalize_work(work, config, source_cache)
                if not paper:
                    continue
                paper["query_term"] = term
                key = paper["doi"] or paper["openalex_id"] or paper["title"].lower()
                existing = works_by_key.get(key)
                if not existing or float(paper.get("relevance_score") or 0) > float(existing.get("relevance_score") or 0):
                    works_by_key[key] = paper
            fetched_for_term += per_page
            cursor = clean_text(payload.get("meta", {}).get("next_cursor"))
            if not cursor:
                break
            time.sleep(args.sleep)
    papers = sorted(
        works_by_key.values(),
        key=lambda item: (
            bool(item.get("all_three_themes")),
            float(item.get("relevance_score") or 0),
            int(item.get("cited_by_count") or 0),
            str(item.get("publication_date") or ""),
        ),
        reverse=True,
    )[:max_results]
    candidate_fields = candidate_fieldnames()
    write_json(metadata_dir / "all-candidates.json", {"config": config, "papers": papers, "errors": errors})
    write_csv(metadata_dir / "all-candidates.csv", papers, candidate_fields)
    evidence_rows = journal_evidence_rows(papers)
    write_csv(metadata_dir / "journal-if-evidence.csv", evidence_rows, evidence_fieldnames())
    write_if_needed(output_dir / "if-verification-needed.md", papers, evidence_rows, config)
    print(str((metadata_dir / "all-candidates.json").resolve()))


def candidate_fieldnames() -> list[str]:
    return [
        "openalex_id",
        "doi",
        "doi_url",
        "title",
        "publication_year",
        "publication_date",
        "authors",
        "journal",
        "source_id",
        "issn_l",
        "issn",
        "publisher",
        "homepage_url",
        "landing_page_url",
        "openalex_url",
        "is_oa",
        "oa_status",
        "pdf_url",
        "pdf_source",
        "unpaywall_landing_url",
        "article_type",
        "construction_hits",
        "lca_hits",
        "optimization_hits",
        "matched_groups",
        "keyword_hits",
        "all_three_themes",
        "relevance_score",
        "cited_by_count",
        "openalex_2yr_mean_citedness_proxy",
        "official_impact_factor",
        "official_if_year",
        "if_evidence_url",
        "if_evidence_note",
        "if_verified_date",
        "if_status",
        "access_status",
        "local_pdf",
        "abstract",
        "concepts",
        "topics",
        "query_term",
    ]


def evidence_fieldnames() -> list[str]:
    return [
        "journal",
        "source_id",
        "issn_l",
        "issn",
        "publisher",
        "homepage_url",
        "openalex_2yr_mean_citedness_proxy",
        "candidate_paper_count",
        "official_impact_factor",
        "official_if_year",
        "evidence_url",
        "evidence_note",
        "verified_date",
        "verified_by",
    ]


def journal_evidence_rows(papers: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_source: dict[str, dict[str, Any]] = {}
    for paper in papers:
        key = clean_text(paper.get("source_id")) or clean_text(paper.get("journal")).lower()
        if not key:
            continue
        row = by_source.setdefault(
            key,
            {
                "journal": paper.get("journal", ""),
                "source_id": paper.get("source_id", ""),
                "issn_l": paper.get("issn_l", ""),
                "issn": paper.get("issn", ""),
                "publisher": paper.get("publisher", ""),
                "homepage_url": paper.get("homepage_url", ""),
                "openalex_2yr_mean_citedness_proxy": paper.get("openalex_2yr_mean_citedness_proxy", ""),
                "candidate_paper_count": 0,
                "official_impact_factor": "",
                "official_if_year": "",
                "evidence_url": "",
                "evidence_note": "",
                "verified_date": "",
                "verified_by": "",
            },
        )
        row["candidate_paper_count"] = int(row.get("candidate_paper_count") or 0) + 1
    return sorted(by_source.values(), key=lambda item: (-int(item.get("candidate_paper_count") or 0), clean_text(item.get("journal")).lower()))


def write_if_needed(path: Path, papers: list[dict[str, Any]], evidence_rows: list[dict[str, Any]], config: dict[str, Any]) -> None:
    lines = [
        "# Impact Factor Verification Needed",
        "",
        f"Topic: {config.get('topic', '')}",
        f"Date window: {config.get('from_date', '')} to {config.get('to_date', '')}",
        "",
        "Use official journal or publisher pages only. Fill `metadata/journal-if-evidence.csv`, then run `finalize`.",
        "",
        "## Journals",
        "",
    ]
    for row in evidence_rows:
        lines.extend(
            [
                f"### {row.get('journal', '')}",
                "",
                f"- Source ID: {row.get('source_id', '')}",
                f"- ISSN-L: {row.get('issn_l', '')}",
                f"- ISSN: {row.get('issn', '')}",
                f"- Publisher: {row.get('publisher', '')}",
                f"- Homepage: {row.get('homepage_url', '')}",
                f"- OpenAlex 2yr mean citedness proxy: {row.get('openalex_2yr_mean_citedness_proxy', '')}",
                f"- Candidate papers: {row.get('candidate_paper_count', '')}",
                "",
            ]
        )
    lines.extend(["## Candidate Papers", ""])
    for paper in papers:
        lines.extend(
            [
                f"- {paper.get('title', '')}",
                f"  - Journal: {paper.get('journal', '')}",
                f"  - DOI: {paper.get('doi_url', '')}",
                f"  - Article type: {paper.get('article_type', '')}",
                f"  - OA/PDF: {paper.get('pdf_url', '') or 'No OA PDF found'}",
            ]
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def evidence_lookup(rows: list[dict[str, str]]) -> dict[str, dict[str, str]]:
    lookup: dict[str, dict[str, str]] = {}
    for row in rows:
        for key in (clean_text(row.get("source_id")), clean_text(row.get("journal")).lower()):
            if key:
                lookup[key] = row
    return lookup


def parse_float(value: Any) -> float | None:
    if value is None:
        return None
    text = str(value).strip()
    match = re.search(r"\d+(?:\.\d+)?", text)
    if not match:
        return None
    try:
        return float(match.group(0))
    except ValueError:
        return None


def safe_pdf_name(paper: dict[str, Any]) -> str:
    year = clean_text(paper.get("publication_year")) or "year"
    title = slugify(clean_text(paper.get("title")), "paper")[:90]
    doi = clean_text(paper.get("doi"))
    digest = hashlib.sha1((doi or clean_text(paper.get("openalex_id")) or title).encode("utf-8")).hexdigest()[:8]
    return f"{year}-{title}-{digest}.pdf"


def download_pdf(url: str, output_path: Path) -> bool:
    try:
        raw = http_get(url, accept="application/pdf,*/*", retries=2)
    except Exception:
        return False
    if not raw.startswith(b"%PDF") and b"%PDF" not in raw[:1024]:
        return False
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(raw)
    return True


def finalize(args: argparse.Namespace) -> None:
    payload = read_json(Path(args.candidates), {})
    papers = payload.get("papers", [])
    if not isinstance(papers, list):
        raise SystemExit("Candidate file does not contain a papers list.")
    evidence_rows = read_csv(Path(args.if_evidence))
    lookup = evidence_lookup(evidence_rows)
    min_if = float(args.min_if)
    limit = int(args.limit) if args.limit else 0
    output_dir = Path(args.output_dir)
    pdf_dir = output_dir / "pdfs"
    included: list[dict[str, Any]] = []
    verification_needed: list[dict[str, Any]] = []
    manual_download: list[dict[str, Any]] = []
    for paper in papers:
        if not isinstance(paper, dict):
            continue
        evidence = lookup.get(clean_text(paper.get("source_id"))) or lookup.get(clean_text(paper.get("journal")).lower()) or {}
        official_if = parse_float(evidence.get("official_impact_factor"))
        evidence_url = clean_text(evidence.get("evidence_url"))
        if official_if is None or official_if <= min_if or not evidence_url:
            paper["if_status"] = "official IF > 5 not verified"
            verification_needed.append(paper)
            continue
        paper["official_impact_factor"] = official_if
        paper["official_if_year"] = clean_text(evidence.get("official_if_year"))
        paper["if_evidence_url"] = evidence_url
        paper["if_evidence_note"] = clean_text(evidence.get("evidence_note"))
        paper["if_verified_date"] = clean_text(evidence.get("verified_date"))
        paper["if_status"] = "official IF > 5 verified"
        if limit and len(included) >= limit:
            continue
        if clean_text(paper.get("pdf_url")):
            paper["access_status"] = "pdf-url-available-publisher-page-review-required"
            if args.queue_all_manual:
                manual_download.append(paper)
        else:
            paper["access_status"] = "non-oa-or-no-pdf-url"
            manual_download.append(paper)
        included.append(paper)
    metadata_dir = output_dir / "metadata"
    write_json(metadata_dir / "papers.json", {"papers": included})
    write_csv(metadata_dir / "papers.csv", included, candidate_fieldnames())
    write_manual_download(output_dir / "manual-download.md", manual_download)
    write_if_needed(output_dir / "if-verification-needed.md", verification_needed, journal_evidence_rows(verification_needed), payload.get("config", {}))
    print(str((metadata_dir / "papers.json").resolve()))


def write_manual_download(path: Path, papers: list[dict[str, Any]]) -> None:
    lines = [
        "# Manual Download Queue",
        "",
        "These papers passed official IF filtering but do not have a downloaded local PDF. Ask the user to log in manually through their school/library/publisher page, then process only the explicit batch they confirm.",
        "",
    ]
    if not papers:
        lines.append("No manual downloads needed.")
    for paper in papers:
        lines.extend(
            [
                f"## {paper.get('title', '')}",
                "",
                f"- Journal: {paper.get('journal', '')}",
                f"- Year: {paper.get('publication_year', '')}",
                f"- DOI: {paper.get('doi_url', '')}",
                f"- Publisher/OpenAlex URL: {paper.get('landing_page_url', '') or paper.get('openalex_url', '')}",
                f"- Article type: {paper.get('article_type', '')}",
                f"- IF evidence: {paper.get('official_impact_factor', '')} ({paper.get('if_evidence_url', '')})",
                f"- Access status: {paper.get('access_status', '')}",
                f"- Reason: relevant cross-theme paper needing full-text review.",
                "",
            ]
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def default_zotero_dir() -> Path:
    candidates = [
        Path.home() / "Zotero",
        Path(os.environ.get("ZOTERO_DATA_DIR", "")),
    ]
    for candidate in candidates:
        if candidate and (candidate / "zotero.sqlite").exists():
            return candidate
    raise SystemExit(
        "Could not find Zotero data directory. Pass --zotero-dir with the folder containing zotero.sqlite."
    )


def zotero_snapshot(zotero_dir: Path, temp_dir: Path) -> Path:
    source = zotero_dir / "zotero.sqlite"
    if not source.exists():
        raise SystemExit(f"Missing Zotero database: {source}")
    snapshot = temp_dir / "zotero.sqlite"
    shutil.copy2(source, snapshot)
    return snapshot


def zotero_rows(con: sqlite3.Connection, query: str, params: tuple[Any, ...] = ()) -> list[sqlite3.Row]:
    con.row_factory = sqlite3.Row
    return list(con.execute(query, params))


def zotero_item_fields(con: sqlite3.Connection) -> dict[int, dict[str, str]]:
    fields: dict[int, dict[str, str]] = {}
    query = """
        select d.itemID, f.fieldName, v.value
        from itemData d
        join fields f on f.fieldID = d.fieldID
        join itemDataValues v on v.valueID = d.valueID
    """
    for row in zotero_rows(con, query):
        fields.setdefault(int(row["itemID"]), {})[str(row["fieldName"])] = clean_text(row["value"])
    return fields


def zotero_creators(con: sqlite3.Connection) -> dict[int, str]:
    creators: dict[int, list[tuple[int, str]]] = {}
    query = """
        select ic.itemID, ic.orderIndex, c.firstName, c.lastName
        from itemCreators ic
        join creators c on c.creatorID = ic.creatorID
        order by ic.itemID, ic.orderIndex
    """
    for row in zotero_rows(con, query):
        first = clean_text(row["firstName"])
        last = clean_text(row["lastName"])
        name = " ".join(part for part in [first, last] if part) or last or first
        if name:
            creators.setdefault(int(row["itemID"]), []).append((int(row["orderIndex"]), name))
    return {
        item_id: "; ".join(name for _, name in sorted(names))
        for item_id, names in creators.items()
    }


def zotero_tags(con: sqlite3.Connection) -> dict[int, str]:
    tags: dict[int, list[str]] = {}
    query = """
        select it.itemID, t.name
        from itemTags it
        join tags t on t.tagID = it.tagID
        order by t.name
    """
    for row in zotero_rows(con, query):
        tags.setdefault(int(row["itemID"]), []).append(clean_text(row["name"]))
    return {item_id: "; ".join(unique_strings(values)) for item_id, values in tags.items()}


def zotero_collections(con: sqlite3.Connection) -> dict[int, str]:
    collections: dict[int, list[str]] = {}
    query = """
        select ci.itemID, c.collectionName
        from collectionItems ci
        join collections c on c.collectionID = ci.collectionID
        order by c.collectionName
    """
    for row in zotero_rows(con, query):
        collections.setdefault(int(row["itemID"]), []).append(clean_text(row["collectionName"]))
    return {item_id: "; ".join(unique_strings(values)) for item_id, values in collections.items()}


def resolve_zotero_pdf_path(zotero_dir: Path, attachment_key: str, raw_path: str) -> Path | None:
    raw_path = clean_text(raw_path)
    if not raw_path:
        return None
    storage_dir = zotero_dir / "storage" / attachment_key
    if raw_path.startswith("storage:"):
        filename = raw_path.split(":", 1)[1]
        path = storage_dir / filename
        if path.exists():
            return path
        pdfs = sorted(storage_dir.glob("*.pdf")) if storage_dir.exists() else []
        return pdfs[0] if pdfs else None
    if raw_path.startswith("attachments:"):
        filename = raw_path.split(":", 1)[1]
        path = storage_dir / filename
        if path.exists():
            return path
        pdfs = sorted(storage_dir.glob("*.pdf")) if storage_dir.exists() else []
        return pdfs[0] if pdfs else None
    path = Path(raw_path)
    if path.exists():
        return path
    return None


def year_from_date(value: str) -> str:
    match = re.search(r"(19|20)\d{2}", clean_text(value))
    return match.group(0) if match else ""


def zotero_article_type(type_name: str, title: str) -> str:
    text = f"{type_name} {title}".lower()
    if "review" in text or "bibliometric" in text:
        return "review article"
    if type_name == "conferencePaper":
        return "conference paper"
    if type_name in {"book", "bookSection"}:
        return type_name
    return "research article"


def extract_pdf_text(path: Path, output_path: Path, max_chars: int) -> tuple[int, int]:
    try:
        from pypdf import PdfReader  # type: ignore
    except Exception:
        return 0, 0
    try:
        reader = PdfReader(str(path))
    except Exception:
        return 0, 0
    chunks: list[str] = []
    total_chars = 0
    for page in reader.pages:
        if total_chars >= max_chars:
            break
        try:
            text = page.extract_text() or ""
        except Exception:
            text = ""
        text = clean_text(text)
        if not text:
            continue
        remaining = max_chars - total_chars
        chunks.append(text[:remaining])
        total_chars += min(len(text), remaining)
    if chunks:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text("\n\n".join(chunks) + "\n", encoding="utf-8")
    return len(reader.pages), total_chars


def zotero_pdf_rows(con: sqlite3.Connection) -> list[sqlite3.Row]:
    query = """
        select
            ia.itemID as attachmentItemID,
            ia.parentItemID,
            ia.path,
            ia.contentType,
            attachment.key as attachmentKey,
            parent.key as parentKey,
            coalesce(parent.itemID, attachment.itemID) as bibItemID,
            coalesce(parentType.typeName, attachmentType.typeName) as bibTypeName
        from itemAttachments ia
        join items attachment on attachment.itemID = ia.itemID
        left join itemTypes attachmentType on attachmentType.itemTypeID = attachment.itemTypeID
        left join items parent on parent.itemID = ia.parentItemID
        left join itemTypes parentType on parentType.itemTypeID = parent.itemTypeID
        where ia.contentType = 'application/pdf'
        order by coalesce(parent.itemID, attachment.itemID), ia.itemID
    """
    return zotero_rows(con, query)


ZOTERO_THEME_RULES: list[tuple[str, list[str]]] = [
    (
        "Energy, Carbon, and Sustainability / 能源碳排与可持续",
        [
            r"\benergy\b",
            r"\bcarbon\b",
            r"\bemission(s)?\b",
            r"\bdecarboni[sz]ation\b",
            r"\bsustainab(le|ility)\b",
            r"\brenewable\b",
            r"\blife cycle\b",
            r"\blca\b",
            "能耗",
            "能源",
            "碳",
            "低碳",
            "可持续",
        ],
    ),
    (
        "Design, Simulation, and Optimization / 设计仿真与优化",
        [
            r"\bdesign\b",
            r"\bsimulation\b",
            r"\bmodel(l)?ing\b",
            r"\boptimization\b",
            r"\bperformance\b",
            r"\bparametric\b",
            r"\bdigital twin\b",
            "设计",
            "仿真",
            "模拟",
            "优化",
        ],
    ),
    (
        "AI, Data, and Digital Methods / AI数据与数字方法",
        [
            r"\bartificial intelligence\b",
            r"\bmachine learning\b",
            r"\bdeep learning\b",
            r"\bdata[- ]driven\b",
            r"\bneural network\b",
            r"\bcomputer vision\b",
            r"\bllm\b",
            r"\bknowledge graph\b",
            r"\bbim\b",
            "人工智能",
            "机器学习",
            "深度学习",
            "数据",
            "数字",
        ],
    ),
    (
        "Materials, Construction, and Infrastructure / 材料建造与基础设施",
        [
            r"\bmaterial(s)?\b",
            r"\bconstruction\b",
            r"\binfrastructure\b",
            r"\bconcrete\b",
            r"\bsteel\b",
            r"\btimber\b",
            r"\bbuilding envelope\b",
            r"\bmodular\b",
            r"\bprefabricat",
            "材料",
            "建造",
            "施工",
            "基础设施",
            "装配式",
            "模块化",
        ],
    ),
    (
        "Policy, Practice, and Review / 政策实践与综述",
        [
            r"\bpolicy\b",
            r"\bpractice\b",
            r"\bbarrier(s)?\b",
            r"\badoption\b",
            r"\bstakeholder\b",
            r"\breview\b",
            r"\bbibliometric\b",
            r"\bframework\b",
            "政策",
            "实践",
            "综述",
            "障碍",
            "框架",
        ],
    ),
    (
        "General / Cross-Cutting / 综合交叉",
        [
            r"\bassessment\b",
            r"\banalysis\b",
            r"\bcase stud(y|ies)\b",
            r"\bsurvey\b",
            "评估",
            "分析",
            "案例",
            "调查",
        ],
    ),
]

ZOTERO_METHOD_RULES: list[tuple[str, list[str]]] = [
    (
        "Deep Learning / 深度学习",
        [
            r"\bdeep learning\b",
            r"\bcnn\b",
            r"\blstm\b",
            r"\btransformer\b",
            r"\bneural network\b",
            r"\bgan\b",
            r"\bdiffusion\b",
            "深度学习",
            "神经网络",
        ],
    ),
    (
        "Machine Learning / 机器学习",
        [
            r"\bmachine learning\b",
            r"\brandom forest\b",
            r"\bxgboost\b",
            r"\bsvm\b",
            r"\bsupport vector\b",
            r"\bgradient boosting\b",
            r"\bregression\b",
            "机器学习",
            "随机森林",
        ],
    ),
    (
        "Optimization / 优化算法",
        [
            r"\boptimization\b",
            r"\bmulti[- ]objective\b",
            r"\bpareto\b",
            r"\bgenetic algorithm\b",
            r"\bnsga\b",
            r"\bbayesian optimization\b",
            "优化",
            "多目标",
        ],
    ),
    (
        "Simulation and Modeling / 仿真建模",
        [
            r"\bsimulation\b",
            r"\bmodel(l)?ing\b",
            r"\benergyplus\b",
            r"\bphysics[- ]based\b",
            r"\bcfd\b",
            "仿真",
            "模拟",
            "建模",
        ],
    ),
    (
        "Life Cycle Assessment / 生命周期评价",
        [
            r"\blife cycle assessment\b",
            r"\blife-cycle assessment\b",
            r"\blca\b",
            r"\blci\b",
            r"\blife cycle carbon\b",
            "生命周期",
        ],
    ),
    (
        "Computer Vision / 计算机视觉",
        [
            r"\bcomputer vision\b",
            r"\bobject detection\b",
            r"\bsegmentation\b",
            r"\byolo\b",
            r"\bimage\b",
            "计算机视觉",
            "图像",
            "检测",
        ],
    ),
    (
        "NLP, LLM, and Knowledge Graph / NLP、LLM与知识图谱",
        [
            r"\bnlp\b",
            r"\bnatural language\b",
            r"\bllm\b",
            r"\blarge language model\b",
            r"\bknowledge graph\b",
            r"\brag\b",
            "大语言模型",
            "知识图谱",
            "自然语言",
        ],
    ),
    (
        "Review or Conceptual Framework / 综述或概念框架",
        [
            r"\breview\b",
            r"\bsystematic review\b",
            r"\bbibliometric\b",
            r"\bframework\b",
            r"\btaxonomy\b",
            "综述",
            "文献计量",
            "框架",
        ],
    ),
    (
        "Statistical and Empirical Analysis / 统计与实证分析",
        [
            r"\bstatistical\b",
            r"\beconometric\b",
            r"\bcorrelation\b",
            r"\bsensitivity analysis\b",
            r"\bsurvey\b",
            "统计",
            "实证",
            "敏感性",
        ],
    ),
]


ZOTERO_SUBTHEME_RULES: list[tuple[str, list[str]]] = [
    (
        "Energy and HVAC / 能耗与HVAC",
        [
            r"\bhvac\b",
            r"\bthermal comfort\b",
            r"\benergy consumption\b",
            r"\bbuilding energy\b",
            r"\bcooling\b",
            r"\bheating\b",
            r"\bdemand response\b",
            "能耗",
            "暖通",
            "热舒适",
        ],
    ),
    (
        "Carbon and LCA / 碳排与LCA",
        [
            r"\bcarbon\b",
            r"\bemission(s)?\b",
            r"\blife cycle\b",
            r"\blife-cycle\b",
            r"\blca\b",
            r"\bembodied\b",
            r"\bdecarboni[sz]ation\b",
            "碳",
            "生命周期",
            "低碳",
        ],
    ),
    (
        "Design Optimization / 设计优化",
        [
            r"\bdesign\b",
            r"\boptimization\b",
            r"\bmulti[- ]objective\b",
            r"\bpareto\b",
            r"\bparametric\b",
            r"\bperformance\b",
            "设计",
            "优化",
            "多目标",
        ],
    ),
    (
        "Simulation and Digital Twin / 仿真与数字孪生",
        [
            r"\bsimulation\b",
            r"\bdigital twin\b",
            r"\bbim\b",
            r"\bbuilding information modeling\b",
            r"\benergyplus\b",
            r"\bmodel(l)?ing\b",
            "仿真",
            "模拟",
            "数字孪生",
            "建模",
        ],
    ),
    (
        "AI Prediction / AI预测",
        [
            r"\bmachine learning\b",
            r"\bdeep learning\b",
            r"\bneural network\b",
            r"\bprediction\b",
            r"\bforecast\b",
            r"\bdata[- ]driven\b",
            "机器学习",
            "深度学习",
            "预测",
            "数据驱动",
        ],
    ),
    (
        "Computer Vision and Sensing / 视觉与感知",
        [
            r"\bcomputer vision\b",
            r"\bimage\b",
            r"\bobject detection\b",
            r"\bsegmentation\b",
            r"\bsensor\b",
            r"\bpoint cloud\b",
            r"\bremote sensing\b",
            "计算机视觉",
            "图像",
            "检测",
            "传感",
        ],
    ),
    (
        "Materials and Structure / 材料与结构",
        [
            r"\bmaterial(s)?\b",
            r"\bconcrete\b",
            r"\bcement\b",
            r"\bsteel\b",
            r"\btimber\b",
            r"\bstructure\b",
            r"\bfacade\b",
            r"\benvelope\b",
            "材料",
            "混凝土",
            "结构",
            "围护",
        ],
    ),
    (
        "Construction Automation / 建造自动化",
        [
            r"\bconstruction\b",
            r"\brobot\b",
            r"\bautomation\b",
            r"\bprefabricat",
            r"\bmodular\b",
            r"\bprecast\b",
            r"\brebar\b",
            r"\bsite\b",
            "施工",
            "建造",
            "机器人",
            "装配式",
            "模块化",
        ],
    ),
    (
        "Policy, Review, and Adoption / 政策综述与应用",
        [
            r"\bpolicy\b",
            r"\breview\b",
            r"\bframework\b",
            r"\bbarrier\b",
            r"\badoption\b",
            r"\bstakeholder\b",
            r"\bbibliometric\b",
            r"\broadmap\b",
            "政策",
            "综述",
            "框架",
            "应用",
        ],
    ),
    (
        "Urban and Human Context / 城市与人本环境",
        [
            r"\burban\b",
            r"\bcity\b",
            r"\bcampus\b",
            r"\boccupant\b",
            r"\bhuman\b",
            r"\bheritage\b",
            r"\bcomfort\b",
            r"\bbehavior\b",
            "城市",
            "人本",
            "遗产",
            "舒适",
        ],
    ),
]


def score_rules(blob: str, rules: list[tuple[str, list[str]]]) -> list[tuple[str, int]]:
    text = blob.lower()
    scored: list[tuple[str, int]] = []
    for label, patterns in rules:
        score = 0
        for pattern in patterns:
            try:
                if re.search(pattern, text):
                    score += 1
            except re.error:
                if pattern.lower() in text:
                    score += 1
        if score:
            scored.append((label, score))
    return sorted(scored, key=lambda item: (-item[1], item[0].lower()))


def zotero_text_snippet(path: Path, limit: int = 60000) -> str:
    if not path.exists():
        return ""
    try:
        return clean_text(path.read_text(encoding="utf-8", errors="ignore")[:limit])
    except Exception:
        return ""


def compact_excerpt(text: str, limit: int = 520) -> str:
    text = clean_text(text)
    if not text:
        return ""
    pieces = re.split(r"(?<=[.!?。！？])\s+", text)
    excerpt = clean_text(" ".join(piece for piece in pieces[:3] if piece))
    if not excerpt:
        excerpt = text
    return excerpt[:limit] + ("..." if len(excerpt) > limit else "")


def classify_zotero_paper(paper: dict[str, Any], full_text: str) -> None:
    blob = " ".join(
        clean_text(paper.get(key))
        for key in (
            "title",
            "abstract",
            "article_type",
            "zotero_tags",
            "zotero_collections",
            "journal",
        )
    )
    blob = f"{blob} {full_text[:60000]}"
    theme_scores = score_rules(blob, ZOTERO_THEME_RULES)
    method_scores = score_rules(blob, ZOTERO_METHOD_RULES)
    subtheme_scores = score_rules(blob, ZOTERO_SUBTHEME_RULES)
    paper["theme"] = theme_scores[0][0] if theme_scores else "General / Cross-Cutting / 综合交叉"
    paper["subtheme"] = subtheme_scores[0][0] if subtheme_scores else default_zotero_subtheme(paper["theme"])
    if method_scores:
        paper["primary_method"] = method_scores[0][0]
        paper["methods"] = "; ".join(label for label, _ in method_scores[:4])
    elif "review" in clean_text(paper.get("article_type")).lower():
        paper["primary_method"] = "Review or Conceptual Framework / 综述或概念框架"
        paper["methods"] = paper["primary_method"]
    else:
        paper["primary_method"] = "Statistical and Empirical Analysis / 统计与实证分析"
        paper["methods"] = paper["primary_method"]
    source_text = clean_text(paper.get("abstract")) or full_text
    paper["summary_excerpt"] = compact_excerpt(source_text)
    paper["journal_group"] = journal_group_for_paper(paper)
    paper["metadata_quality"] = metadata_quality_for_paper(paper)


def default_zotero_subtheme(theme: str) -> str:
    if "Energy" in theme:
        return "Energy and HVAC / 能耗与HVAC"
    if "Materials" in theme:
        return "Materials and Structure / 材料与结构"
    if "AI" in theme:
        return "AI Prediction / AI预测"
    if "Policy" in theme:
        return "Policy, Review, and Adoption / 政策综述与应用"
    if "Design" in theme:
        return "Design Optimization / 设计优化"
    return "General / 综合交叉"


def journal_group_for_paper(paper: dict[str, Any]) -> str:
    journal = clean_text(paper.get("journal"))
    return journal if journal else "Metadata missing / 元数据缺失"


def metadata_quality_for_paper(paper: dict[str, Any]) -> str:
    missing: list[str] = []
    if not clean_text(paper.get("journal")):
        missing.append("journal")
    if not clean_text(paper.get("publication_year") or paper.get("publication_date")):
        missing.append("year/date")
    if not clean_text(paper.get("doi") or paper.get("doi_url")):
        missing.append("DOI")
    if missing:
        return "Missing / 缺失: " + ", ".join(missing)
    return "Complete / 完整"


def compact_theme_name(theme: str) -> str:
    text = clean_text(theme).split("/", 1)[0].strip()
    return text or "Theme"


def balance_zotero_subthemes(papers: list[dict[str, Any]], max_per_theme: int = 8) -> None:
    by_theme: dict[str, Counter[str]] = {}
    for paper in papers:
        theme = clean_text(paper.get("theme")) or "General / Cross-Cutting / 综合交叉"
        subtheme = clean_text(paper.get("subtheme")) or "General / 综合交叉"
        by_theme.setdefault(theme, Counter())[subtheme] += 1
    for theme, counts in by_theme.items():
        if len(counts) <= max_per_theme:
            continue
        keep = {name for name, _ in counts.most_common(max_per_theme - 1)}
        other = f"Other in {compact_theme_name(theme)} / 该主题其他"
        for paper in papers:
            if clean_text(paper.get("theme")) == theme and clean_text(paper.get("subtheme")) not in keep:
                paper["subtheme"] = other


def zotero_detail_for_paper(paper: dict[str, Any]) -> dict[str, dict[str, str]]:
    title = clean_text(paper.get("title"))
    theme = clean_text(paper.get("theme"))
    subtheme = clean_text(paper.get("subtheme"))
    method = clean_text(paper.get("primary_method"))
    methods = clean_text(paper.get("methods"))
    excerpt = clean_text(paper.get("summary_excerpt")) or "No abstract/text excerpt was available from Zotero metadata."
    pdf_status = clean_text(paper.get("full_text_status") or paper.get("access_status"))
    data_hint = "Use the PDF text and metadata to confirm the exact dataset, case, region, or experiment design."
    return {
        "topic": {
            "zh": f"该文献被自动归入“{theme}”下的“{subtheme}”。根据 Zotero 摘要或 PDF 文本片段，核心关注点与题名《{title}》一致：{excerpt}",
            "en": f"Auto-classified under '{theme}' > '{subtheme}'. Based on the Zotero abstract or extracted PDF text, the paper's focus is: {excerpt}",
        },
        "method": {
            "zh": f"主要方法识别为“{method}”；附加方法标签包括：{methods or method}。该标签来自题名、摘要、Zotero 标签和 PDF 文本关键词。",
            "en": f"Primary method: {method}. Additional method labels: {methods or method}. Labels are inferred from the title, abstract, Zotero tags, and extracted PDF text.",
        },
        "data": {
            "zh": "数据或案例信息已从 PDF 文本中纳入索引；建议在正式综述写作前按需要打开本地 PDF 复核具体样本、地区、软件或实验设置。",
            "en": data_hint,
        },
        "findings": {
            "zh": f"自动证据片段：{excerpt}",
            "en": f"Evidence excerpt: {excerpt}",
        },
        "limits": {
            "zh": "这是 Zotero 直读模式的自动摘要，适合快速分类和导航；正式引用前仍应人工核对全文中的结果、限制和研究设计。",
            "en": "This is an automatic Zotero-import note for navigation and triage. Verify findings, limitations, and study design in the full PDF before formal citation.",
        },
        "relevance": {
            "zh": f"与文献库主题的关系主要体现在“{theme} / {subtheme}”和“{method}”的交叉，可在关系图中查看它与其他文献的连接。",
            "en": f"Its role in the library is the intersection of '{theme} / {subtheme}' and '{method}', which is visualized in the theme-method relationship map.",
        },
    }


def write_zotero_reports(output_dir: Path, config: dict[str, Any], papers: list[dict[str, Any]]) -> None:
    themes = Counter(clean_text(paper.get("theme")) or "General / Cross-Cutting / 综合交叉" for paper in papers)
    subthemes = Counter(clean_text(paper.get("subtheme")) or "General / 综合交叉" for paper in papers)
    methods = Counter(clean_text(paper.get("primary_method")) or "Other" for paper in papers)

    review_lines = [
        "# Zotero Literature Review / Zotero 文献库综述",
        "",
        f"- Topic / 主题: {config.get('topic', '')}",
        f"- Included PDF-backed items / 纳入带 PDF 条目: {len(papers)}",
        "- Scope / 范围: local Zotero items with resolvable PDF attachments only",
        "- Note / 说明: Zotero 模式默认不重新检索文献，也不强制影响因子筛选；无 PDF 条目不会进入全文 dashboard。",
        "",
        "## Theme Overview / 主题概览",
        "",
    ]
    for label, count in themes.most_common():
        review_lines.append(f"- {label}: {count}")
    review_lines.extend(["", "## Subtheme Overview / 子主题概览", ""])
    for label, count in subthemes.most_common():
        review_lines.append(f"- {label}: {count}")
    review_lines.extend(["", "## Method Overview / 方法概览", ""])
    for label, count in methods.most_common():
        review_lines.append(f"- {label}: {count}")
    review_lines.extend(["", "## Paper Notes / 单篇笔记", ""])
    for paper in papers:
        review_lines.extend(
            [
                f"### #{paper.get('rank')} {paper.get('title')}",
                "",
                f"- Theme / 主题: {paper.get('theme', '')}",
                f"- Subtheme / 子主题: {paper.get('subtheme', '')}",
                f"- Method / 方法: {paper.get('primary_method', '')}",
                f"- Journal / 期刊: {paper.get('journal', '') or 'Metadata missing / 元数据缺失'}",
                f"- Year / 年份: {paper.get('publication_year', '')}",
                f"- Metadata / 元数据: {paper.get('metadata_quality', '')}",
                f"- Status / 状态: {paper.get('full_text_status', '')}",
                f"- DOI: {paper.get('doi_url') or paper.get('doi') or ''}",
                f"- Local PDF / 本地 PDF: {paper.get('local_pdf_path', '')}",
                f"- 中文简述: 该文献被归入“{paper.get('theme', '')} / {paper.get('subtheme', '')}”，主要方法为“{paper.get('primary_method', '')}”。自动证据片段如下，正式写作前建议打开 PDF 复核。",
                f"- Evidence excerpt: {paper.get('summary_excerpt', '')}",
                "",
            ]
        )
    (output_dir / "review-bilingual.md").write_text("\n".join(review_lines) + "\n", encoding="utf-8")

    rel_counter = Counter(
        (
            clean_text(paper.get("theme")) or "General / Cross-Cutting / 综合交叉",
            clean_text(paper.get("subtheme")) or "General / 综合交叉",
            clean_text(paper.get("primary_method")) or "Other",
        )
        for paper in papers
    )
    relation_lines = [
        "# Relationship Map / 关系图说明",
        "",
        "This file mirrors the dashboard relationship graph. Each row links a broad theme with a primary method and the papers that sit at that intersection.",
        "",
        "本文件对应 dashboard 中的“主题-方法关系图”。每一行表示一个主题与一个主要方法的交叉，以及落在这个交叉点的文献。",
        "",
        "| Theme / 主题 | Subtheme / 子主题 | Method / 方法 | Papers / 文献 | Count |",
        "|---|---|---|---|---:|",
    ]
    for (theme, subtheme, method), count in sorted(rel_counter.items(), key=lambda item: (-item[1], item[0][0], item[0][1], item[0][2])):
        ranks = [
            f"#{paper.get('rank')} {paper.get('title')}"
            for paper in papers
            if (clean_text(paper.get("theme")) or "General / Cross-Cutting / 综合交叉") == theme
            and (clean_text(paper.get("subtheme")) or "General / 综合交叉") == subtheme
            and (clean_text(paper.get("primary_method")) or "Other") == method
        ]
        relation_lines.append(f"| {theme} | {subtheme} | {method} | {'<br>'.join(ranks)} | {count} |")
    (output_dir / "relationship-map.md").write_text("\n".join(relation_lines) + "\n", encoding="utf-8")


def write_metadata_repair(path: Path, papers: list[dict[str, Any]]) -> None:
    rows = [
        paper
        for paper in papers
        if "Missing" in clean_text(paper.get("metadata_quality"))
    ]
    lines = [
        "# Zotero Metadata Repair / Zotero 元数据修复清单",
        "",
        "These records have local PDFs but incomplete Zotero metadata. They are included in the dashboard, but repairing Zotero metadata will improve journal/year/DOI browsing.",
        "",
        "这些条目有本地 PDF，所以已进入 dashboard；但 Zotero 元数据不完整。建议在 Zotero 中补齐期刊、年份或 DOI，以改善期刊和年份浏览。",
        "",
    ]
    if not rows:
        lines.append("No metadata repair needed.")
    for paper in rows:
        lines.extend(
            [
                f"## #{paper.get('rank')} {paper.get('title', '')}",
                "",
                f"- Missing / 缺失: {paper.get('metadata_quality', '')}",
                f"- Zotero item: {paper.get('zotero_item_id', '')}",
                f"- Journal / 期刊: {paper.get('journal', '') or 'Metadata missing'}",
                f"- Year / 年份: {paper.get('publication_year', '') or 'Metadata missing'}",
                f"- DOI: {paper.get('doi') or 'Metadata missing'}",
                f"- Local PDF / 本地 PDF: {paper.get('local_pdf_path', '')}",
                "",
            ]
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_zotero_dashboard_details(spec_path: Path, papers: list[dict[str, Any]]) -> None:
    spec = json.loads(spec_path.read_text(encoding="utf-8-sig"))
    if not isinstance(spec, dict):
        return
    spec["details"] = {str(paper.get("rank")): zotero_detail_for_paper(paper) for paper in papers}
    write_json(spec_path, spec)


def zotero_import(args: argparse.Namespace) -> None:
    zotero_dir = Path(args.zotero_dir).expanduser().resolve() if args.zotero_dir else default_zotero_dir()
    output_dir = Path(args.output_dir).resolve()
    metadata_dir = output_dir / "metadata"
    text_dir = output_dir / "texts"
    metadata_dir.mkdir(parents=True, exist_ok=True)
    skipped_missing_pdf: list[dict[str, Any]] = []
    with TemporaryDirectory(prefix="zotero-import-") as tmp:
        snapshot = zotero_snapshot(zotero_dir, Path(tmp))
        con = sqlite3.connect(snapshot)
        con.row_factory = sqlite3.Row
        fields_by_item = zotero_item_fields(con)
        creators_by_item = zotero_creators(con)
        tags_by_item = zotero_tags(con)
        collections_by_item = zotero_collections(con)
        seen_bib_items: set[int] = set()
        papers: list[dict[str, Any]] = []
        for row in zotero_pdf_rows(con):
            bib_item_id = int(row["bibItemID"])
            if bib_item_id in seen_bib_items:
                continue
            seen_bib_items.add(bib_item_id)
            attachment_key = clean_text(row["attachmentKey"])
            pdf_path = resolve_zotero_pdf_path(zotero_dir, attachment_key, clean_text(row["path"]))
            if not pdf_path or not pdf_path.exists():
                skipped_missing_pdf.append(
                    {
                        "zotero_item_id": bib_item_id,
                        "attachment_key": attachment_key,
                        "path": clean_text(row["path"]),
                        "reason": "PDF attachment path could not be resolved or file is missing.",
                    }
                )
                continue
            item_fields = fields_by_item.get(bib_item_id, {})
            attachment_fields = fields_by_item.get(int(row["attachmentItemID"]), {})
            title = clean_text(item_fields.get("title") or attachment_fields.get("title") or pdf_path.stem)
            doi = normalize_doi(item_fields.get("DOI", ""))
            date_value = clean_text(item_fields.get("date", ""))
            year = year_from_date(date_value)
            rank = len(papers) + 1
            full_text_path = text_dir / f"zotero-{rank:04d}-{slugify(title, 'paper')[:70]}.txt"
            pages = 0
            chars = 0
            if not args.no_extract_text:
                pages, chars = extract_pdf_text(pdf_path, full_text_path, max(1000, int(args.max_text_chars)))
            full_text = zotero_text_snippet(full_text_path) if chars else ""
            paper = {
                "rank": rank,
                "zotero_item_id": bib_item_id,
                "zotero_attachment_item_id": int(row["attachmentItemID"]),
                "zotero_key": clean_text(row["parentKey"] or row["attachmentKey"]),
                "zotero_attachment_key": attachment_key,
                "title": title,
                "authors": creators_by_item.get(bib_item_id, ""),
                "journal": clean_text(item_fields.get("publicationTitle") or item_fields.get("proceedingsTitle") or item_fields.get("bookTitle")),
                "publication_year": year,
                "publication_date": date_value or year,
                "doi": doi,
                "doi_url": doi_url(doi),
                "url": clean_text(item_fields.get("url", "")),
                "abstract": clean_text(item_fields.get("abstractNote", "")),
                "article_type": zotero_article_type(clean_text(row["bibTypeName"]), title),
                "zotero_item_type": clean_text(row["bibTypeName"]),
                "zotero_tags": tags_by_item.get(bib_item_id, ""),
                "zotero_collections": collections_by_item.get(bib_item_id, ""),
                "local_pdf": str(pdf_path.resolve()),
                "local_pdf_path": str(pdf_path.resolve()),
                "full_text_path": str(full_text_path.resolve()) if chars else "",
                "full_text_chars": chars,
                "pdf_pages": pages,
                "access_status": "PDF available in Zotero; text extracted" if chars else "PDF available in Zotero; text extraction pending",
                "full_text_status": "full-text extracted from Zotero" if chars else "PDF available; text extraction pending",
                "source": "Zotero local library",
                "theme": "",
                "subtheme": "",
                "primary_method": "",
                "methods": "",
                "journal_group": "",
                "metadata_quality": "",
                "summary_excerpt": "",
            }
            classify_zotero_paper(paper, full_text)
            papers.append(paper)
            if args.limit and len(papers) >= args.limit:
                break
        con.close()
    balance_zotero_subthemes(papers)
    config = {
        "topic": args.topic,
        "source": "Zotero local library",
        "zotero_dir": str(zotero_dir),
        "selection": "all Zotero items with local PDF attachments",
        "created": dt.datetime.now(dt.timezone.utc).isoformat(),
        "if_filtering": "not applied by default in Zotero import mode",
    }
    payload = {"config": config, "papers": papers}
    write_json(metadata_dir / "papers.json", payload)
    write_json(metadata_dir / "zotero-import-summary.json", {"config": config, "paper_count": len(papers), "skipped_missing_pdf": skipped_missing_pdf})
    write_csv(metadata_dir / "papers.csv", papers, zotero_fieldnames())
    write_zotero_skipped(output_dir / "zotero-skipped.md", skipped_missing_pdf)
    write_zotero_readme(output_dir / "manual-download.md")
    write_zotero_reports(output_dir, config, papers)
    write_metadata_repair(output_dir / "metadata-repair.md", papers)
    if not args.skip_dashboard:
        build_dashboard_script = Path(__file__).with_name("build_literature_dashboard.py")
        spec_path = output_dir / "dashboard-spec.json"
        dashboard_name = args.dashboard_name
        subprocess.run(
            [
                sys.executable,
                str(build_dashboard_script),
                "init-spec",
                "--papers",
                str(metadata_dir / "papers.json"),
                "--output",
                str(spec_path),
                "--title",
                args.dashboard_title,
                "--subtitle",
                args.dashboard_subtitle,
            ],
            check=True,
        )
        write_zotero_dashboard_details(spec_path, papers)
        subprocess.run(
            [
                sys.executable,
                str(build_dashboard_script),
                "build",
                "--papers",
                str(metadata_dir / "papers.json"),
                "--spec",
                str(spec_path),
                "--output-dir",
                str(output_dir),
                "--dashboard-name",
                dashboard_name,
            ],
            check=True,
        )
    print(str((metadata_dir / "papers.json").resolve()))


def zotero_fieldnames() -> list[str]:
    return [
        "rank",
        "zotero_item_id",
        "zotero_attachment_item_id",
        "zotero_key",
        "zotero_attachment_key",
        "title",
        "authors",
        "journal",
        "publication_year",
        "publication_date",
        "doi",
        "doi_url",
        "url",
        "abstract",
        "article_type",
        "zotero_item_type",
        "zotero_tags",
        "zotero_collections",
        "local_pdf",
        "local_pdf_path",
        "full_text_path",
        "full_text_chars",
        "pdf_pages",
        "access_status",
        "full_text_status",
        "source",
        "theme",
        "subtheme",
        "primary_method",
        "methods",
        "journal_group",
        "metadata_quality",
        "summary_excerpt",
    ]


def write_zotero_skipped(path: Path, skipped: list[dict[str, Any]]) -> None:
    lines = ["# Zotero Skipped Items", ""]
    if not skipped:
        lines.append("No Zotero PDF attachments were skipped because of missing files.")
    for item in skipped:
        lines.extend(
            [
                f"## Zotero item {item.get('zotero_item_id', '')}",
                "",
                f"- Attachment key: {item.get('attachment_key', '')}",
                f"- Path: {item.get('path', '')}",
                f"- Reason: {item.get('reason', '')}",
                "",
            ]
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_zotero_readme(path: Path) -> None:
    path.write_text(
        "# Manual Download Queue\n\n"
        "Zotero import mode reads only local PDF attachments already present in Zotero. "
        "Items without local PDFs are skipped and are not included in the full-text dashboard.\n",
        encoding="utf-8",
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Systematic literature review helper.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    init = subparsers.add_parser("init-config", help="Write a default review config.")
    init.add_argument("--topic", default="prefabricated modular construction LCA multi-objective optimization")
    init.add_argument("--output", required=True)
    init.add_argument("--mailto", default="")
    init.add_argument("--years", type=int, default=DEFAULT_YEARS)
    init.add_argument("--min-if", type=float, default=DEFAULT_MIN_IF)
    init.add_argument(
        "--keyword-group",
        action="append",
        default=[],
        help="Keyword group as name=term1|term2. Repeat for cross-theme searches.",
    )
    init.add_argument(
        "--query",
        action="append",
        default=[],
        help="Explicit search query. Repeat to override automatic group combinations.",
    )
    init.set_defaults(func=init_config)

    collect_parser = subparsers.add_parser("collect", help="Collect candidate papers and journal IF checklist.")
    collect_parser.add_argument("--config", required=True)
    collect_parser.add_argument("--output-dir", required=True)
    collect_parser.add_argument("--max-results", type=int, default=100)
    collect_parser.add_argument("--rows-per-query", type=int, default=25)
    collect_parser.add_argument("--max-pages-per-query", type=int, default=1)
    collect_parser.add_argument("--sleep", type=float, default=0.25)
    collect_parser.set_defaults(func=collect)

    finalize_parser = subparsers.add_parser("finalize", help="Filter by official IF evidence and create PDF access queues.")
    finalize_parser.add_argument("--candidates", required=True)
    finalize_parser.add_argument("--if-evidence", required=True)
    finalize_parser.add_argument("--output-dir", required=True)
    finalize_parser.add_argument("--min-if", type=float, default=DEFAULT_MIN_IF)
    finalize_parser.add_argument("--limit", type=int, default=0, help="Keep only the top N verified papers in papers.json.")
    finalize_parser.add_argument(
        "--download-oa",
        action="store_true",
        help="Deprecated no-op: PDFs should be saved only after opening the publisher article page and clicking the visible PDF control.",
    )
    finalize_parser.add_argument("--queue-all-manual", action="store_true", help="Add even OA-available-but-not-downloaded papers to manual-download.md.")
    finalize_parser.set_defaults(func=finalize)

    zotero_parser = subparsers.add_parser(
        "zotero-import",
        help="Read the local Zotero database and import items that already have PDF attachments.",
    )
    zotero_parser.add_argument(
        "--zotero-dir",
        default="",
        help="Zotero data directory containing zotero.sqlite; defaults to ZOTERO_DATA_DIR or ~/Zotero.",
    )
    zotero_parser.add_argument("--output-dir", required=True)
    zotero_parser.add_argument("--topic", default="Zotero Literature Library")
    zotero_parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="Maximum PDF-backed Zotero items to import; 0 means all.",
    )
    zotero_parser.add_argument(
        "--max-text-chars",
        type=int,
        default=200000,
        help="Maximum extracted text characters to keep per PDF.",
    )
    zotero_parser.add_argument(
        "--no-extract-text",
        action="store_true",
        help="Skip PDF text extraction and generate metadata/dashboard links only.",
    )
    zotero_parser.add_argument("--skip-dashboard", action="store_true")
    zotero_parser.add_argument("--dashboard-name", default="zotero-literature-dashboard")
    zotero_parser.add_argument("--dashboard-title", default="Zotero Literature Dashboard")
    zotero_parser.add_argument(
        "--dashboard-subtitle",
        default="Direct Zotero PDF import, bilingual classification, and local PDF links.",
    )
    zotero_parser.set_defaults(func=zotero_import)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    args.func(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
