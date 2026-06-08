#!/usr/bin/env python3
"""Build an interactive bilingual literature-review dashboard.

The script is deterministic: Codex writes or refines the semantic
dashboard-spec.json after reading metadata/full text, then this script renders
the reusable HTML/JS dashboard. It does not call an LLM and does not fetch
papers.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

from large_library_dashboard import write_large_library_dashboard


PALETTE = [
    "#6d7d8b",
    "#c28b2c",
    "#7b6fb2",
    "#4281a4",
    "#2e9c8f",
    "#c65f6f",
    "#5c9f57",
    "#8a6f55",
    "#9b6aa6",
    "#4c8fbd",
]

DETAIL_KEYS = ["topic", "method", "data", "findings", "limits", "relevance"]


def clean_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, list):
        value = "; ".join(str(item) for item in value if item)
    return re.sub(r"\s+", " ", str(value)).strip()


def read_payload(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8-sig")
    if path.suffix.lower() == ".js":
        _, _, text = text.partition("=")
        text = text.strip().rstrip(";")
    payload = json.loads(text)
    if isinstance(payload, dict):
        return payload
    raise SystemExit(f"Unsupported payload in {path}")


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_js(path: Path, var_name: str, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    body = json.dumps(payload, ensure_ascii=False, indent=2)
    path.write_text(f"window.{var_name} = {body};\n", encoding="utf-8")


def split_labels(value: Any) -> list[str]:
    text = clean_text(value)
    if not text:
        return []
    parts = re.split(r"\s*[;|,]\s*", text)
    return [part for part in (clean_text(item) for item in parts) if part]


def as_url(value: Any) -> str:
    text = clean_text(value)
    if not text:
        return ""
    if text.startswith("http://") or text.startswith("https://"):
        return text
    if re.match(r"^10\.\S+/\S+$", text):
        return f"https://doi.org/{text}"
    return text


def infer_method(paper: dict[str, Any]) -> str:
    blob = " ".join(
        clean_text(paper.get(key))
        for key in ("methods", "method", "title", "abstract", "topics", "concepts", "keyword_hits")
    ).lower()
    patterns = [
        ("Life Cycle Assessment", r"\b(life cycle assessment|life-cycle assessment|whole-building lca|\blca\b|life cycle carbon)\b"),
        ("Embodied Carbon Accounting", r"\b(embodied carbon|embodied energy|carbon accounting|carbon footprint|material carbon)\b"),
        ("Operational Energy and Retrofit", r"\b(retrofit|renovation|energy efficiency|operational carbon|operational energy|hvac|heat pump)\b"),
        ("Net-Zero / Decarbonization Scenario", r"\b(net zero|zero carbon|carbon neutrality|decarboni[sz]ation|decarboni[sz]e|pathway|scenario)\b"),
        ("Material Circularity and Reuse", r"\b(circular|reuse|recycling|recycled|bio-based|timber|cement|concrete|material)\b"),
        ("Optimization and Decision Support", r"\b(optimization|multi-objective|pareto|decision support|cost-optimal|scenario analysis)\b"),
        ("Policy / Review / Framework", r"\b(policy|barrier|driver|review|framework|roadmap|guideline|taxonomy)\b"),
        ("LLM / Knowledge Graph", r"\b(llm|large language model|gpt|rag|knowledge graph)\b"),
        ("Graph Neural Network", r"\b(graph neural network|gnn|graph learning)\b"),
        ("Reinforcement Learning", r"\b(reinforcement learning|deep reinforcement|rl|drl|marl)\b"),
        ("Physics-Informed AI", r"\b(physics-informed|pinn|neural operator|physical constraint)\b"),
        ("Transformer / Foundation Model", r"\b(transformer|foundation model|vision-language|diffusion)\b"),
        ("Computer Vision", r"\b(computer vision|object detection|segmentation|resnet|yolo|cnn|image)\b"),
        ("ML/DL Prediction and Optimization", r"\b(machine learning|deep learning|xgboost|random forest|neural network|optimization|surrogate)\b"),
    ]
    for label, pattern in patterns:
        if re.search(pattern, blob):
            return label
    labels = split_labels(paper.get("methods"))
    return labels[0] if labels else "Other / Cross-Cutting Method"


def infer_theme(paper: dict[str, Any]) -> str:
    for key in ("theme", "primary_theme", "category"):
        value = clean_text(paper.get(key))
        if value:
            return value
    blob = " ".join(clean_text(paper.get(key)) for key in ("title", "abstract", "topics", "concepts")).lower()
    patterns = [
        ("Whole-Building Carbon Assessment", r"\b(whole-building|life cycle|lca|carbon footprint|carbon accounting)\b"),
        ("Embodied Carbon and Materials", r"\b(embodied carbon|embodied energy|material|concrete|cement|timber|steel|reuse|recycling)\b"),
        ("Net-Zero and Decarbonization Pathways", r"\b(net zero|zero carbon|carbon neutrality|decarboni[sz]ation|pathway|scenario)\b"),
        ("Retrofit and Operational Energy", r"\b(retrofit|renovation|energy efficiency|operational carbon|operational energy|hvac|heat pump)\b"),
        ("Low-Carbon Design and Optimization", r"\b(design|optimization|multi-objective|pareto|cost-optimal|decision support)\b"),
        ("Policy, Adoption, and Barriers", r"\b(policy|barrier|driver|market|adoption|stakeholder|roadmap)\b"),
        ("Digital Tools and Data", r"\b(digital twin|simulation|bim|building information modeling|machine learning|artificial intelligence)\b"),
    ]
    for label, pattern in patterns:
        if re.search(pattern, blob):
            return label
    return "General / Cross-Cutting"


def infer_subtheme(paper: dict[str, Any], theme: str) -> str:
    for key in ("subtheme", "secondary_theme", "topic_cluster"):
        value = clean_text(paper.get(key))
        if value:
            return value
    blob = " ".join(
        clean_text(paper.get(key))
        for key in ("title", "abstract", "methods", "method", "topics", "concepts", "keyword_hits")
    ).lower()
    patterns = [
        ("Energy and HVAC / 能耗与HVAC", r"\b(hvac|thermal comfort|energy consumption|building energy|cooling|heating|demand response)\b"),
        ("Carbon and LCA / 碳排与LCA", r"\b(carbon|emission|life cycle|life-cycle|\blca\b|embodied|decarboni[sz]ation)\b"),
        ("Design Optimization / 设计优化", r"\b(design|optimization|multi-objective|pareto|parametric|performance)\b"),
        ("Simulation and Digital Twin / 仿真与数字孪生", r"\b(simulation|digital twin|bim|building information modeling|energyplus|model(l)?ing)\b"),
        ("AI Prediction / AI预测", r"\b(machine learning|deep learning|neural network|prediction|forecast|data-driven)\b"),
        ("Computer Vision and Sensing / 视觉与感知", r"\b(computer vision|image|object detection|segmentation|sensor|point cloud|remote sensing)\b"),
        ("Materials and Structure / 材料与结构", r"\b(material|concrete|cement|steel|timber|structure|facade|envelope)\b"),
        ("Construction Automation / 建造自动化", r"\b(construction|robot|automation|prefabricat|modular|precast|rebar|site)\b"),
        ("Policy, Review, and Adoption / 政策综述与应用", r"\b(policy|review|framework|barrier|adoption|stakeholder|bibliometric|roadmap)\b"),
        ("Urban and Human Context / 城市与人本环境", r"\b(urban|city|campus|occupant|human|heritage|comfort|behavior)\b"),
    ]
    for label, pattern in patterns:
        if re.search(pattern, blob):
            return label
    if "Review" in theme or "Policy" in theme:
        return "Policy, Review, and Adoption / 政策综述与应用"
    if "Energy" in theme:
        return "Energy and HVAC / 能耗与HVAC"
    if "Materials" in theme:
        return "Materials and Structure / 材料与结构"
    if "AI" in theme:
        return "AI Prediction / AI预测"
    if "Design" in theme:
        return "Design Optimization / 设计优化"
    return "General / 综合交叉"


def normalized_journal(raw: dict[str, Any]) -> str:
    journal = clean_text(raw.get("journal"))
    if journal:
        return journal
    source = clean_text(raw.get("source"))
    if source and source.lower() != "zotero local library":
        return source
    return ""


def metadata_quality(raw: dict[str, Any], journal: str, date_value: str, doi: str) -> str:
    missing: list[str] = []
    if not journal:
        missing.append("journal")
    if not date_value:
        missing.append("year/date")
    if not doi:
        missing.append("DOI")
    if missing:
        return "Missing / 缺失: " + ", ".join(missing)
    return "Complete / 完整"


def normalize_papers(raw_papers: list[dict[str, Any]], limit: int | None = None) -> list[dict[str, Any]]:
    papers: list[dict[str, Any]] = []
    for index, raw in enumerate(raw_papers[: limit or len(raw_papers)], start=1):
        if not isinstance(raw, dict):
            continue
        rank = clean_text(raw.get("rank")) or str(index)
        doi = as_url(raw.get("doi_url") or raw.get("doi"))
        journal = normalized_journal(raw)
        date_value = clean_text(raw.get("publication_date") or raw.get("publication_year"))
        theme = clean_text(raw.get("theme") or raw.get("primary_theme") or infer_theme(raw))
        subtheme = clean_text(raw.get("subtheme") or infer_subtheme(raw, theme))
        local_pdf = clean_text(
            raw.get("local_pdf_path")
            or raw.get("local_pdf")
            or raw.get("pdf_path")
            or raw.get("downloaded_pdf")
        )
        papers.append(
            {
                "rank": rank,
                "title": clean_text(raw.get("title")),
                "authors": clean_text(raw.get("authors")),
                "journal": journal,
                "publication_date": date_value,
                "article_type": clean_text(raw.get("article_type")) or "research article",
                "doi": doi,
                "homepage_url": as_url(raw.get("homepage_url")),
                "official_if_evidence_url": as_url(raw.get("official_if_evidence_url") or raw.get("if_evidence_url")),
                "official_impact_factor": clean_text(raw.get("official_impact_factor")),
                "methods": clean_text(raw.get("methods") or raw.get("method") or infer_method(raw)),
                "abstract": clean_text(raw.get("abstract")),
                "access_status": clean_text(raw.get("access_status") or raw.get("full_text_status")),
                "local_pdf_path": local_pdf,
                "theme": theme,
                "subtheme": subtheme,
                "primary_method": clean_text(raw.get("primary_method") or infer_method(raw)),
                "journal_group": clean_text(raw.get("journal_group")) or (journal if journal else "Metadata missing / 元数据缺失"),
                "metadata_quality": clean_text(raw.get("metadata_quality")) or metadata_quality(raw, journal, date_value, doi),
            }
        )
    return papers


def make_definitions(labels: list[str], descriptions: dict[str, str] | None = None) -> list[dict[str, str]]:
    descriptions = descriptions or {}
    seen: dict[str, int] = {}
    for label in labels:
        seen[label] = seen.get(label, 0) + 1
    ordered = sorted(seen, key=lambda item: (-seen[item], item.lower()))
    return [
        {
            "name": label,
            "description": descriptions.get(label, "Auto-classified; refine this description after full-text review."),
            "color": PALETTE[index % len(PALETTE)],
        }
        for index, label in enumerate(ordered)
    ]


def bilingual_placeholder(label: str, abstract: str = "") -> dict[str, str]:
    en = abstract[:360] + ("..." if len(abstract) > 360 else "") if abstract else "Add a concise evidence-grounded note after reading the abstract or full text."
    return {
        "zh": f"待补充：围绕“{label}”写出基于证据的中文总结。",
        "en": en,
    }


def init_spec(args: argparse.Namespace) -> None:
    payload = read_payload(Path(args.papers))
    papers = normalize_papers(payload.get("papers", []), args.limit)
    assignments = {
        str(paper["rank"]): {"theme": paper["theme"], "subtheme": paper["subtheme"], "method": paper["primary_method"]}
        for paper in papers
    }
    spec = {
        "title": args.title,
        "subtitle": args.subtitle,
        "layout": "large-library" if len(papers) > 100 else "review-dashboard",
        "theme_definitions": make_definitions([paper["theme"] for paper in papers]),
        "subtheme_definitions": make_definitions([paper["subtheme"] for paper in papers]),
        "method_definitions": make_definitions([paper["primary_method"] for paper in papers]),
        "paper_assignments": assignments,
        "details": {
            str(paper["rank"]): {
                "topic": bilingual_placeholder(assignments[str(paper["rank"])]["theme"], paper["abstract"]),
                "method": bilingual_placeholder(assignments[str(paper["rank"])]["method"]),
                "data": bilingual_placeholder("data/case"),
                "findings": bilingual_placeholder("findings"),
                "limits": bilingual_placeholder("limitations"),
                "relevance": bilingual_placeholder("relevance"),
            }
            for paper in papers
        },
    }
    write_json(Path(args.output), spec)
    print(str(Path(args.output).resolve()))


def load_spec(path: Path, papers: list[dict[str, Any]], title: str, subtitle: str) -> dict[str, Any]:
    if path.exists():
        spec = read_payload(path)
    else:
        spec = {}
    assignments = spec.get("paper_assignments") if isinstance(spec.get("paper_assignments"), dict) else {}
    for paper in papers:
        key = str(paper["rank"])
        row = assignments.get(key) if isinstance(assignments.get(key), dict) else {}
        assignments[key] = {
            "theme": clean_text(row.get("theme")) or paper["theme"],
            "subtheme": clean_text(row.get("subtheme")) or paper["subtheme"],
            "method": clean_text(row.get("method")) or paper["primary_method"],
        }
    theme_defs = spec.get("theme_definitions") if isinstance(spec.get("theme_definitions"), list) else []
    subtheme_defs = spec.get("subtheme_definitions") if isinstance(spec.get("subtheme_definitions"), list) else []
    method_defs = spec.get("method_definitions") if isinstance(spec.get("method_definitions"), list) else []
    if not theme_defs:
        theme_defs = make_definitions([assignments[str(p["rank"])]["theme"] for p in papers])
    if not subtheme_defs:
        subtheme_defs = make_definitions([assignments[str(p["rank"])]["subtheme"] for p in papers])
    if not method_defs:
        method_defs = make_definitions([assignments[str(p["rank"])]["method"] for p in papers])
    details: dict[str, Any] = {}
    if isinstance(spec.get("paper_details"), dict):
        details.update(spec["paper_details"])
    if isinstance(spec.get("details"), dict):
        details.update(spec["details"])
    return {
        "title": clean_text(spec.get("title")) or title,
        "subtitle": clean_text(spec.get("subtitle")) or subtitle,
        "layout": clean_text(spec.get("layout")) or ("large-library" if len(papers) > 100 else "review-dashboard"),
        "theme_definitions": theme_defs,
        "subtheme_definitions": subtheme_defs,
        "method_definitions": method_defs,
        "paper_assignments": assignments,
        "details": details,
    }


DASHBOARD_HTML = r"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Literature Review Dashboard</title>
  <style>
    :root {
      --ink:#182129; --muted:#64727e; --line:#dbe5ea; --paper:#f7fafb; --panel:#fff;
      --blue:#366f9f; --green:#3f8d72; --shadow:0 16px 42px rgba(25,39,52,.08);
    }
    * { box-sizing:border-box; }
    body { margin:0; color:var(--ink); background:var(--paper); font-family:Inter, "Segoe UI", Arial, sans-serif; }
    main { width:min(1180px, calc(100vw - 36px)); margin:0 auto; padding:26px 0 44px; }
    h1 { margin:0; font-size:32px; line-height:1.12; letter-spacing:0; }
    h2 { margin:0 0 6px; font-size:18px; line-height:1.25; }
    h3 { margin:0; }
    .hero { display:grid; grid-template-columns:1.25fr .75fr; gap:14px; align-items:stretch; margin-bottom:14px; }
    .panel, .kpi, .card, .detail-card { border:1px solid var(--line); border-radius:8px; background:var(--panel); box-shadow:var(--shadow); }
    .intro { padding:20px; }
    .intro p, .hint { color:var(--muted); font-size:13px; line-height:1.45; margin:8px 0 0; }
    .kpis { display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:10px; }
    .kpi { padding:15px; min-height:98px; }
    .kpi .label { color:var(--muted); font-size:12px; text-transform:uppercase; letter-spacing:.06em; }
    .kpi .value { margin-top:7px; font-size:31px; font-weight:780; line-height:1; }
    .kpi .note { margin-top:9px; color:var(--muted); font-size:12px; line-height:1.35; }
    .layout { display:grid; grid-template-columns:1fr 1fr; gap:14px; align-items:start; }
    .panel { padding:18px; overflow:hidden; }
    .viz { display:grid; grid-template-columns:210px minmax(0,1fr); gap:16px; align-items:center; min-height:390px; }
    .donut-wrap { position:relative; width:210px; height:210px; margin:0 auto; }
    .donut { width:210px; height:210px; display:block; }
    .segment { fill:none; stroke-width:24; cursor:pointer; transition:opacity .16s ease, stroke-width .16s ease; }
    .segment.dim { opacity:.32; }
    .segment.active { stroke-width:29; }
    .donut-center { position:absolute; inset:54px; display:grid; place-content:center; text-align:center; border:1px solid var(--line); border-radius:999px; background:#fff; }
    .donut-center strong { font-size:34px; line-height:1; }
    .donut-center span { color:var(--muted); font-size:12px; margin-top:5px; }
    .legend { display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:8px; margin-bottom:12px; }
    button { appearance:none; border:1px solid var(--line); border-radius:8px; background:#fff; color:var(--ink); min-height:36px; padding:8px 10px; font:inherit; cursor:pointer; }
    button[aria-pressed="true"] { background:var(--ink); color:#fff; border-color:var(--ink); }
    .chip { display:grid; grid-template-columns:11px 1fr auto; gap:8px; align-items:center; width:100%; text-align:left; min-height:42px; }
    .chip i { width:11px; height:11px; border-radius:999px; display:block; }
    .chip span { min-width:0; font-size:12px; line-height:1.25; color:var(--ink); }
    .chip strong { color:var(--muted); font-size:12px; }
    .chip[aria-pressed="true"] { background:#eef6f8; color:var(--ink); border-color:#9eb9c9; }
    .chip[aria-pressed="true"] span { color:var(--ink); }
    .chip[aria-pressed="true"] strong { color:#3d5568; }
    .papers { border:1px solid var(--line); border-radius:8px; background:#fbfdfd; padding:12px; min-height:176px; }
    .papers h3 { font-size:15px; margin:0 0 8px; }
    .paper-list { margin:0; padding:0; list-style:none; display:grid; gap:7px; }
    .paper-list button { min-height:0; width:100%; padding:0; border:0; background:transparent; color:#285d7d; text-align:left; font-size:12px; line-height:1.35; }
    .paper-list button:hover { text-decoration:underline; }
    .relation-wrap { min-height:405px; overflow:hidden; }
    .relation-svg { width:100%; min-height:370px; display:block; }
    .relation-link { fill:none; stroke-width:2.2; opacity:.48; cursor:pointer; transition:opacity .16s ease, stroke-width .16s ease; }
    .relation-link:hover { opacity:.95; stroke-width:4; }
    .relation-label { font-size:12px; font-weight:720; fill:var(--ink); }
    .relation-label-sub { font-size:11px; fill:var(--muted); }
    .relation-note { color:var(--muted); font-size:12px; margin-top:4px; min-height:18px; }
    .bars { display:grid; gap:12px; }
    .bar { display:grid; grid-template-columns:minmax(170px,245px) 1fr 48px; gap:12px; align-items:center; }
    .bar-name { min-width:0; font-size:14px; font-weight:680; }
    .bar-name span { display:block; color:var(--muted); font-size:12px; font-weight:500; margin-top:2px; }
    .track { height:16px; border:1px solid #dce6eb; background:#edf3f5; border-radius:999px; overflow:hidden; }
    .fill { height:100%; min-width:7px; border-radius:999px; }
    .count { color:var(--muted); text-align:right; font-size:13px; }
    .controls { display:flex; gap:8px; flex-wrap:wrap; margin:10px 0 16px; }
    .cards { display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:12px; }
    .card { padding:14px; box-shadow:none; cursor:pointer; transition:border-color .16s ease, transform .16s ease, box-shadow .16s ease; }
    .card:hover { border-color:#9eb9c9; transform:translateY(-1px); box-shadow:0 10px 24px rgba(30,46,60,.08); }
    .card h3 { font-size:15px; line-height:1.35; margin:0 0 8px; }
    .tags { display:flex; gap:6px; flex-wrap:wrap; }
    .tag { border-radius:999px; padding:4px 8px; font-size:12px; line-height:1; border:1px solid var(--line); color:var(--muted); background:#fff; }
    .tag.if { color:#835a10; background:#fff6db; border-color:#f0dca3; }
    .tag.theme { color:#1e638a; background:#eaf5fb; border-color:#cae2ef; }
    .tag.method { color:#316b57; background:#edf8f3; border-color:#cde8dd; }
    .detail-shell { position:fixed; inset:0; display:none; background:rgba(14,24,32,.42); z-index:50; padding:22px; overflow:auto; }
    .detail-shell.open { display:block; }
    .detail-card { width:min(900px, calc(100vw - 32px)); margin:0 auto; padding:20px; box-shadow:0 18px 52px rgba(10,18,24,.22); }
    .detail-top { display:flex; justify-content:space-between; gap:12px; align-items:start; margin-bottom:10px; }
    .eyebrow { color:var(--muted); font-size:12px; margin-bottom:6px; }
    .detail-card h2 { font-size:24px; line-height:1.25; }
    .detail-actions { display:flex; gap:7px; flex:0 0 auto; }
    .icon-button { width:36px; min-height:36px; padding:0; display:grid; place-items:center; font-size:18px; }
    .detail-grid { display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:9px; margin:13px 0; }
    .detail-fact { border:1px solid var(--line); border-radius:8px; padding:9px; background:#fbfdfd; }
    .detail-fact span { display:block; color:var(--muted); font-size:11px; margin-bottom:4px; }
    .detail-fact strong { font-size:13px; line-height:1.25; overflow-wrap:anywhere; }
    .detail-section { border-top:1px solid var(--line); padding-top:12px; margin-top:12px; }
    .detail-section h3 { font-size:15px; margin-bottom:7px; }
    .detail-section p { margin:6px 0; color:#273540; font-size:14px; line-height:1.55; }
    .lang-label { display:inline-block; min-width:28px; color:var(--muted); font-size:12px; font-weight:700; margin-right:4px; }
    .detail-links { display:flex; flex-wrap:wrap; gap:8px; margin-top:14px; }
    .detail-link { display:inline-flex; align-items:center; min-height:34px; border:1px solid var(--line); border-radius:8px; padding:7px 10px; background:#fff; color:#245f9e; text-decoration:none; }
    a { color:#245f9e; }
    @media (max-width:980px) {
      main { width:min(100vw - 24px,760px); padding-top:18px; }
      .hero, .layout, .cards { grid-template-columns:1fr; }
      .viz { grid-template-columns:1fr; min-height:0; }
      .legend { grid-template-columns:1fr; }
      .bar { grid-template-columns:1fr; }
      .count { text-align:left; }
      .detail-grid { grid-template-columns:1fr; }
    }
  </style>
</head>
<body>
<main>
  <section class="hero">
    <div class="intro panel">
      <h1 id="dashTitle"></h1>
      <p id="dashSubtitle"></p>
    </div>
    <div class="kpis">
      <div class="kpi"><div class="label">Papers</div><div class="value" id="paperCount">0</div><div class="note">included records</div></div>
      <div class="kpi"><div class="label">Themes</div><div class="value" id="themeKpi">0</div><div class="note">topic categories</div></div>
      <div class="kpi"><div class="label">Methods</div><div class="value" id="methodKpi">0</div><div class="note">method families</div></div>
      <div class="kpi"><div class="label">PDFs</div><div class="value" id="pdfKpi">0</div><div class="note">local files linked</div></div>
    </div>
  </section>
  <section class="layout">
    <article class="panel">
      <h2>主题分类 / Theme Taxonomy</h2>
      <p class="hint">点击饼图或图例查看对应文章。</p>
      <div class="viz"><div class="donut-wrap"><svg class="donut" id="themeDonut" viewBox="0 0 180 180"></svg><div class="donut-center"><strong id="themeCount">0</strong><span>papers</span></div></div><div><div class="legend" id="themeLegend"></div><div class="papers"><h3 id="themeTitle"></h3><ol class="paper-list" id="themePaperList"></ol></div></div></div>
    </article>
    <article class="panel">
      <h2>方法热度 / Method Hotspots</h2>
      <p class="hint">点击方法后显示该方法对应的文章。</p>
      <div class="viz"><div class="donut-wrap"><svg class="donut" id="methodDonut" viewBox="0 0 180 180"></svg><div class="donut-center"><strong id="methodCount">0</strong><span>papers</span></div></div><div><div class="legend" id="methodLegend"></div><div class="papers"><h3 id="methodTitle"></h3><ol class="paper-list" id="methodPaperList"></ol></div></div></div>
    </article>
  </section>
  <section class="panel" style="margin-top:14px;">
    <h2>主题 × 方法关系流图 / Theme-Method Link Map</h2>
    <p class="hint">每条曲线代表一篇文章：左侧是主题分类，右侧是主方法。点击曲线打开文章详情。</p>
    <div class="relation-wrap"><svg class="relation-svg" id="relationSvg" viewBox="0 0 980 390"></svg><div class="relation-note" id="relationNote">Tip: hover or click a curve to inspect a paper.</div></div>
  </section>
  <section class="panel" style="margin-top:14px;">
    <h2>期刊来源 / Journal Sources</h2>
    <p class="hint">点击期刊官网进入对应 journal homepage；如已完成官方 IF 验证，会同步显示 IF 数值。</p>
    <div class="bars" id="journalBars"></div>
  </section>
  <section class="panel" style="margin-top:14px;">
    <h2>文章卡片 / Paper Cards</h2>
    <p class="hint">点击卡片查看双语详情。</p>
    <div class="controls" id="filters"></div>
    <div class="cards" id="cards"></div>
  </section>
</main>
<aside class="detail-shell" id="detailShell" aria-hidden="true">
  <article class="detail-card">
    <div class="detail-top"><div><div class="eyebrow" id="detailEyebrow"></div><h2 id="detailTitle"></h2></div><div class="detail-actions"><button class="icon-button" type="button" id="detailPrev" title="上一篇">‹</button><button class="icon-button" type="button" id="detailNext" title="下一篇">›</button><button class="icon-button" type="button" id="detailClose" title="关闭">×</button></div></div>
    <div class="tags" id="detailTags"></div>
    <div class="detail-grid" id="detailFacts"></div>
    <div id="detailSections"></div>
    <div class="detail-links" id="detailLinks"></div>
  </article>
</aside>
<script src="__DATA_FILE__"></script>
<script src="__DETAILS_FILE__"></script>
<script>
  const data = window.__SLR_DASHBOARD_DATA__ || { papers: [], spec: {} };
  const papers = data.papers || [];
  const spec = data.spec || {};
  const details = window.__SLR_DASHBOARD_DETAILS__ || {};
  const themeDefs = spec.theme_definitions || [];
  const methodDefs = spec.method_definitions || [];
  const assignments = spec.paper_assignments || {};
  const radius = 67;
  const circumference = 2 * Math.PI * radius;
  let activeTheme = themeDefs[0]?.name || "";
  let activeMethod = methodDefs[0]?.name || "";
  let activeFilter = "all";
  let activeRank = null;

  function escapeHtml(value) {
    return String(value || "").replace(/[&<>"']/g, ch => ({ "&":"&amp;", "<":"&lt;", ">":"&gt;", "\"":"&quot;", "'":"&#39;" }[ch]));
  }
  function paperTheme(p) { return assignments[String(p.rank)]?.theme || p.theme || "Unclassified"; }
  function paperMethod(p) { return assignments[String(p.rank)]?.method || p.primary_method || p.methods || "Other"; }
  function byTheme(name) { return papers.filter(p => paperTheme(p) === name); }
  function byMethod(name) { return papers.filter(p => paperMethod(p) === name); }
  function colorFor(defs, name) { return defs.find(d => d.name === name)?.color || "#6d7d8b"; }
  function fileUrl(path) { return path ? encodeURI("file:///" + String(path).replace(/\\/g, "/")) : ""; }
  function localPageUrl(page) { return new URL(page, location.href.split("#")[0]).href; }
  function pdfLauncherUrl(paper) { return localPageUrl(`__PDF_OPEN_FILE__?rank=${encodeURIComponent(paper.rank)}`); }
  function detailText(value) {
    if (value && typeof value === "object") {
      return `<p><span class="lang-label">中</span>${escapeHtml(value.zh)}</p><p><span class="lang-label">EN</span>${escapeHtml(value.en)}</p>`;
    }
    return `<p>${escapeHtml(value || "No note yet.")}</p>`;
  }
  function detailSection(title, value) {
    return `<section class="detail-section"><h3>${title}</h3>${detailText(value)}</section>`;
  }
  function drawDonut(svgId, defs, activeName, getPapers, dataAttr) {
    let offset = 0;
    const total = Math.max(papers.length, 1);
    const segments = defs.map(def => {
      const n = getPapers(def.name).length;
      const length = n / total * circumference;
      const cls = def.name === activeName ? "segment active" : "segment dim";
      const node = `<circle class="${cls}" cx="90" cy="90" r="${radius}" stroke="${def.color}" stroke-dasharray="${length} ${circumference - length}" stroke-dashoffset="${-offset}" transform="rotate(-90 90 90)" data-${dataAttr}="${escapeHtml(def.name)}"><title>${escapeHtml(def.name)}: ${n}</title></circle>`;
      offset += length;
      return node;
    }).join("");
    document.getElementById(svgId).innerHTML = `<circle cx="90" cy="90" r="${radius}" fill="none" stroke="#edf3f5" stroke-width="24"></circle>${segments}`;
  }
  function renderCategory(kind) {
    const isTheme = kind === "theme";
    const defs = isTheme ? themeDefs : methodDefs;
    const active = isTheme ? activeTheme : activeMethod;
    const getPapers = isTheme ? byTheme : byMethod;
    const prefix = isTheme ? "theme" : "method";
    const activePapers = getPapers(active);
    drawDonut(`${prefix}Donut`, defs, active, getPapers, prefix);
    document.getElementById(`${prefix}Legend`).innerHTML = defs.map(def => {
      const n = getPapers(def.name).length;
      return `<button class="chip" type="button" data-${prefix}="${escapeHtml(def.name)}" aria-pressed="${def.name === active}"><i style="background:${def.color}"></i><span>${escapeHtml(def.name)}</span><strong>${n}</strong></button>`;
    }).join("");
    document.getElementById(`${prefix}Count`).textContent = activePapers.length;
    document.getElementById(`${prefix}Title`).textContent = `${active} · ${activePapers.length} 篇`;
    document.getElementById(`${prefix}PaperList`).innerHTML = activePapers.map(p => `<li><button type="button" data-rank="${p.rank}">#${p.rank} ${escapeHtml(p.title)}</button></li>`).join("");
    document.querySelectorAll(`#${prefix}Legend .chip, #${prefix}Donut .segment`).forEach(el => {
      el.addEventListener("click", () => {
        if (isTheme) activeTheme = el.dataset.theme; else activeMethod = el.dataset.method;
        renderCategory(kind);
      });
    });
    document.querySelectorAll(`#${prefix}PaperList button`).forEach(button => button.addEventListener("click", () => openDetail(button.dataset.rank)));
  }
  function renderRelationGraph() {
    const width = 980, leftX = 235, rightX = 745, top = 34, bottom = 342;
    const themeY = new Map(themeDefs.map((d, i) => [d.name, top + i * ((bottom - top) / Math.max(themeDefs.length - 1, 1))]));
    const methodY = new Map(methodDefs.map((d, i) => [d.name, top + i * ((bottom - top) / Math.max(methodDefs.length - 1, 1))]));
    const themeOffsets = new Map(), methodOffsets = new Map();
    const jitter = (map, key) => { const current = map.get(key) || 0; map.set(key, current + 1); return (current % 7 - 3) * 4; };
    const paths = papers.map(p => {
      const theme = paperTheme(p), method = paperMethod(p);
      const y1 = (themeY.get(theme) || top) + jitter(themeOffsets, theme);
      const y2 = (methodY.get(method) || top) + jitter(methodOffsets, method);
      const d = `M ${leftX} ${y1} C ${leftX + 180} ${y1}, ${rightX - 180} ${y2}, ${rightX} ${y2}`;
      return `<path class="relation-link" d="${d}" stroke="${colorFor(themeDefs, theme)}" data-rank="${p.rank}"><title>#${p.rank} ${escapeHtml(p.title)}</title></path>`;
    }).join("");
    const leftLabels = themeDefs.map(def => `<text class="relation-label" x="20" y="${themeY.get(def.name) + 4}" fill="${def.color}">${escapeHtml(def.name)}</text>`).join("");
    const rightLabels = methodDefs.map(def => `<text class="relation-label" x="${rightX + 18}" y="${methodY.get(def.name) + 4}" fill="${def.color}">${escapeHtml(def.name)}</text>`).join("");
    document.getElementById("relationSvg").innerHTML = `<text class="relation-label-sub" x="20" y="18">主题分类 / Theme</text><text class="relation-label-sub" x="${rightX + 18}" y="18">方法 / Method</text>${paths}${leftLabels}${rightLabels}`;
    document.querySelectorAll(".relation-link").forEach(path => {
      path.addEventListener("click", () => openDetail(path.dataset.rank));
      path.addEventListener("mouseenter", () => {
        const paper = papers.find(p => String(p.rank) === String(path.dataset.rank));
        if (paper) document.getElementById("relationNote").textContent = `#${paper.rank} ${paper.title}`;
      });
      path.addEventListener("mouseleave", () => document.getElementById("relationNote").textContent = "Tip: hover or click a curve to inspect a paper.");
    });
  }
  function paperTags(p) {
    return [
      ["theme", paperTheme(p)],
      ["method", paperMethod(p)],
      ["if", p.official_impact_factor ? `IF ${p.official_impact_factor}` : ""],
      ["", p.article_type || ""],
    ].filter(([, text]) => text);
  }
  function shownPapers(filter) {
    if (filter === "all") return papers;
    if (themeDefs.some(d => d.name === filter)) return papers.filter(p => paperTheme(p) === filter);
    return papers;
  }
  function renderFilters(active) {
    const rows = [["all", "全部 / All"], ...themeDefs.map(d => [d.name, d.name])];
    document.getElementById("filters").innerHTML = rows.map(([key, label]) => `<button type="button" data-key="${escapeHtml(key)}" aria-pressed="${key === active}">${escapeHtml(label)}</button>`).join("");
    document.querySelectorAll("#filters button").forEach(button => button.addEventListener("click", () => { activeFilter = button.dataset.key; renderFilters(activeFilter); renderCards(); }));
  }
  function renderCards() {
    const shown = shownPapers(activeFilter);
    document.getElementById("cards").innerHTML = shown.map(p => `<article class="card" role="button" tabindex="0" data-rank="${p.rank}"><h3>#${p.rank} ${escapeHtml(p.title)}</h3><div class="tags">${paperTags(p).map(([cls, text]) => `<span class="tag ${cls}">${escapeHtml(text)}</span>`).join("")}</div></article>`).join("");
    document.querySelectorAll(".card").forEach(card => {
      card.addEventListener("click", () => openDetail(card.dataset.rank));
      card.addEventListener("keydown", event => { if (event.key === "Enter" || event.key === " ") { event.preventDefault(); openDetail(card.dataset.rank); } });
    });
  }
  function renderJournals() {
    const byJournal = new Map();
    papers.forEach(p => {
      const key = p.journal || "Unknown";
      const row = byJournal.get(key) || { journal:key, n:0, ifValue:Number(p.official_impact_factor || 0), url:p.homepage_url || p.official_if_evidence_url };
      row.n += 1; row.ifValue = Math.max(row.ifValue, Number(p.official_impact_factor || 0)); if (!row.url) row.url = p.homepage_url || p.official_if_evidence_url;
      byJournal.set(key, row);
    });
    const journals = [...byJournal.values()].sort((a,b) => b.ifValue - a.ifValue || b.n - a.n);
    const jMax = Math.max(...journals.map(j => j.ifValue), 1);
    document.getElementById("journalBars").innerHTML = journals.map(j => {
      const link = j.url ? `<a href="${escapeHtml(j.url)}">期刊官网 / Journal homepage</a>` : "source missing";
      return `<div class="bar"><div class="bar-name">${escapeHtml(j.journal)}<span>${j.n} paper(s), ${link}</span></div><div class="track"><div class="fill" style="width:${Math.max(8, Math.round(j.ifValue / jMax * 100))}%;background:var(--green);"></div></div><div class="count">${j.ifValue ? j.ifValue.toFixed(1) : "-"}</div></div>`;
    }).join("");
  }
  function openDetail(rank) {
    const paper = papers.find(p => String(p.rank) === String(rank));
    if (!paper) return;
    activeRank = String(rank);
    const detail = details[activeRank] || {};
    document.getElementById("detailEyebrow").textContent = `Rank ${paper.rank} · ${paperTheme(paper)} · ${paper.article_type || "research article"}`;
    document.getElementById("detailTitle").textContent = paper.title;
    document.getElementById("detailTags").innerHTML = paperTags(paper).map(([cls, text]) => `<span class="tag ${cls}">${escapeHtml(text)}</span>`).join("");
    document.getElementById("detailFacts").innerHTML = [
      ["期刊 / Journal", paper.journal],
      ["发表日期 / Date", paper.publication_date],
      ["文章类型 / Type", paper.article_type],
      ["官方 IF / Official IF", paper.official_impact_factor || "verified"],
      ["主题分类 / Theme", paperTheme(paper)],
      ["方法 / Method", paperMethod(paper)]
    ].map(([label, value]) => `<div class="detail-fact"><span>${label}</span><strong>${escapeHtml(value)}</strong></div>`).join("");
    document.getElementById("detailSections").innerHTML = [
      detailSection("研究主题 / Research Theme", detail.topic),
      detailSection("方法 / Method", detail.method),
      detailSection("数据或案例 / Data or Case", detail.data),
      detailSection("主要结果 / Findings", detail.findings),
      detailSection("局限 / Limitations", detail.limits),
      detailSection("为什么重要 / Relevance", detail.relevance)
    ].join("");
    const pdfHref = fileUrl(paper.local_pdf_path);
    const launcherHref = pdfHref ? pdfLauncherUrl(paper) : "";
    document.getElementById("detailLinks").innerHTML = [
      paper.doi ? `<a class="detail-link" href="${escapeHtml(paper.doi)}">打开 DOI / Open DOI</a>` : "",
      launcherHref ? `<button class="detail-link" type="button" id="openPdfLauncher" data-href="${escapeHtml(launcherHref)}">打开本地 PDF / Open PDF</button>` : ""
    ].filter(Boolean).join("");
    const pdfButton = document.getElementById("openPdfLauncher");
    if (pdfButton) pdfButton.addEventListener("click", () => window.location.assign(pdfButton.dataset.href));
    const shown = shownPapers(activeFilter);
    const idx = shown.findIndex(p => String(p.rank) === activeRank);
    document.getElementById("detailPrev").disabled = idx <= 0;
    document.getElementById("detailNext").disabled = idx < 0 || idx >= shown.length - 1;
    document.getElementById("detailShell").classList.add("open");
    document.getElementById("detailShell").setAttribute("aria-hidden", "false");
    document.body.style.overflow = "hidden";
    history.replaceState(null, "", `#paper-${paper.rank}`);
  }
  function closeDetail(clearHash = true) {
    document.getElementById("detailShell").classList.remove("open");
    document.getElementById("detailShell").setAttribute("aria-hidden", "true");
    document.body.style.overflow = "";
    activeRank = null;
    if (clearHash && location.hash.startsWith("#paper-")) history.replaceState(null, "", location.href.split("#")[0]);
  }
  function moveDetail(delta) {
    const shown = shownPapers(activeFilter);
    const idx = shown.findIndex(p => String(p.rank) === String(activeRank));
    const next = shown[idx + delta];
    if (next) openDetail(next.rank);
  }
  document.getElementById("dashTitle").textContent = spec.title || "Literature Review Dashboard";
  document.getElementById("dashSubtitle").textContent = spec.subtitle || "";
  document.getElementById("paperCount").textContent = papers.length;
  document.getElementById("themeKpi").textContent = themeDefs.length;
  document.getElementById("methodKpi").textContent = methodDefs.length;
  document.getElementById("pdfKpi").textContent = papers.filter(p => p.local_pdf_path).length;
  renderCategory("theme");
  renderCategory("method");
  renderRelationGraph();
  renderJournals();
  renderFilters("all");
  renderCards();
  document.getElementById("detailClose").addEventListener("click", () => closeDetail());
  document.getElementById("detailPrev").addEventListener("click", () => moveDetail(-1));
  document.getElementById("detailNext").addEventListener("click", () => moveDetail(1));
  document.getElementById("detailShell").addEventListener("click", event => { if (event.target.id === "detailShell") closeDetail(); });
  document.addEventListener("keydown", event => { if (event.key === "Escape") closeDetail(); });
  function openHashDetail() {
    const initialMatch = location.hash.match(/^#paper-(.+)$/);
    if (initialMatch && String(activeRank) !== String(initialMatch[1])) openDetail(decodeURIComponent(initialMatch[1]));
  }
  window.addEventListener("hashchange", openHashDetail);
  setTimeout(openHashDetail, 0);
</script>
</body>
</html>
"""


PDF_OPEN_HTML = r"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Open Local PDF</title>
  <style>
    :root { --ink:#17202a; --muted:#607080; --line:#d8e2e8; --blue:#2f6f9f; }
    * { box-sizing:border-box; }
    body { margin:0; min-height:100vh; display:grid; place-items:center; background:#f6fafb; color:var(--ink); font-family:Inter, "Segoe UI", Arial, sans-serif; }
    main { width:min(760px, calc(100vw - 28px)); }
    article { border:1px solid var(--line); border-radius:8px; background:#fff; padding:22px; box-shadow:0 16px 42px rgba(25,39,52,.08); }
    h1 { margin:0; font-size:24px; line-height:1.28; }
    .meta, .note { color:var(--muted); font-size:13px; line-height:1.5; }
    .actions { display:flex; flex-wrap:wrap; gap:8px; margin:16px 0; }
    a, button { border:1px solid var(--line); border-radius:8px; min-height:36px; padding:8px 11px; background:#fff; color:var(--blue); font:inherit; text-decoration:none; cursor:pointer; }
    .primary { background:var(--blue); border-color:var(--blue); color:#fff; }
    code { display:block; white-space:pre-wrap; overflow-wrap:anywhere; border:1px solid var(--line); border-radius:8px; padding:10px; background:#fbfdfd; color:#31424f; }
  </style>
</head>
<body>
<main><article>
  <h1 id="title">Loading PDF...</h1>
  <p class="meta" id="meta"></p>
  <div class="actions" id="actions"></div>
  <p class="note">如果 in-app browser 的 PDF viewer 黑屏，请用“下载 PDF”或“复制文件路径”在 Edge/Chrome/Adobe Reader 打开。<br>If the in-app browser PDF viewer stays black, download the PDF or copy the path and open it in a desktop reader.</p>
  <code id="path"></code>
</article></main>
<script src="__DATA_FILE__"></script>
<script>
  const params = new URLSearchParams(location.search);
  const rank = params.get("rank");
  const papers = window.__SLR_DASHBOARD_DATA__?.papers || [];
  const paper = papers.find(item => String(item.rank) === String(rank));
  function escapeHtml(value) {
    return String(value || "").replace(/[&<>"']/g, ch => ({ "&":"&amp;", "<":"&lt;", ">":"&gt;", "\"":"&quot;", "'":"&#39;" }[ch]));
  }
  function fileUrl(path) { return path ? encodeURI("file:///" + String(path).replace(/\\/g, "/")) : ""; }
  if (!paper) {
    document.getElementById("title").textContent = "PDF not found";
    document.getElementById("meta").textContent = "No paper matches this rank.";
  } else {
    const pdfHref = fileUrl(paper.local_pdf_path);
    document.getElementById("title").textContent = `#${paper.rank} ${paper.title}`;
    document.getElementById("meta").textContent = `${paper.journal || ""} · ${paper.publication_date || ""}`;
    document.getElementById("path").textContent = paper.local_pdf_path || "";
    document.getElementById("actions").innerHTML = [
      pdfHref ? `<a class="primary" href="${pdfHref}">直接打开 PDF / Open PDF</a>` : "",
      pdfHref ? `<a href="${pdfHref}" download>下载 PDF / Download PDF</a>` : "",
      `<button type="button" id="copyPath">复制文件路径 / Copy path</button>`,
      `<a href="__DASHBOARD_FILE__#paper-${paper.rank}">返回 Dashboard / Back</a>`
    ].filter(Boolean).join("");
    document.getElementById("copyPath").addEventListener("click", async () => {
      await navigator.clipboard.writeText(paper.local_pdf_path || "");
      document.getElementById("copyPath").textContent = "已复制 / Copied";
    });
  }
</script>
</body>
</html>
"""


def build_dashboard(args: argparse.Namespace) -> None:
    payload = read_payload(Path(args.papers))
    papers = normalize_papers(payload.get("papers", []), args.limit)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    dashboard_file = args.dashboard_name if args.dashboard_name.endswith(".html") else f"{args.dashboard_name}.html"
    data_file = Path(dashboard_file).with_suffix("").name + "-data.js"
    details_file = Path(dashboard_file).with_suffix("").name + "-details.js"
    pdf_open_file = Path(dashboard_file).with_suffix("").name + "-pdf-open.html"
    title = args.title or clean_text(payload.get("config", {}).get("topic")) or "Systematic Literature Review"
    subtitle = args.subtitle or "Bilingual classification, article notes, journal evidence, and local PDF links."
    spec = load_spec(Path(args.spec), papers, title, subtitle)
    data_payload = {"config": payload.get("config", {}), "papers": papers, "spec": {key: spec[key] for key in ("title", "subtitle", "layout", "theme_definitions", "subtheme_definitions", "method_definitions", "paper_assignments")}}
    if spec.get("layout") == "large-library":
        write_large_library_dashboard(
            output_dir=output_dir,
            dashboard_file=dashboard_file,
            data_file=data_file,
            details_file=details_file,
            pdf_open_file=pdf_open_file,
            data_payload=data_payload,
            details=spec.get("details", {}),
        )
        print(str((output_dir / dashboard_file).resolve()))
        return
    write_js(output_dir / data_file, "__SLR_DASHBOARD_DATA__", data_payload)
    write_js(output_dir / details_file, "__SLR_DASHBOARD_DETAILS__", spec.get("details", {}))
    (output_dir / dashboard_file).write_text(
        DASHBOARD_HTML.replace("__DATA_FILE__", data_file)
        .replace("__DETAILS_FILE__", details_file)
        .replace("__PDF_OPEN_FILE__", pdf_open_file),
        encoding="utf-8",
    )
    (output_dir / pdf_open_file).write_text(
        PDF_OPEN_HTML.replace("__DATA_FILE__", data_file).replace("__DASHBOARD_FILE__", dashboard_file),
        encoding="utf-8",
    )
    print(str((output_dir / dashboard_file).resolve()))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build a literature review dashboard from papers.json and dashboard-spec.json.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    init = subparsers.add_parser("init-spec", help="Create a starter dashboard-spec.json for manual/Codex refinement.")
    init.add_argument("--papers", required=True, help="Path to metadata/papers.json, all-candidates.json, or dashboard data JS.")
    init.add_argument("--output", required=True)
    init.add_argument("--title", default="Systematic Literature Review Dashboard")
    init.add_argument("--subtitle", default="Bilingual classification, article notes, journal evidence, and local PDF links.")
    init.add_argument("--limit", type=int, default=None)
    init.set_defaults(func=init_spec)

    build = subparsers.add_parser("build", help="Render the dashboard HTML/JS files.")
    build.add_argument("--papers", required=True)
    build.add_argument("--spec", required=True)
    build.add_argument("--output-dir", required=True)
    build.add_argument("--dashboard-name", default="literature-dashboard")
    build.add_argument("--title", default="")
    build.add_argument("--subtitle", default="")
    build.add_argument("--limit", type=int, default=None)
    build.set_defaults(func=build_dashboard)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    args.func(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
