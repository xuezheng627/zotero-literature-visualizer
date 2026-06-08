#!/usr/bin/env python3
"""Validate the zotero-literature-visualizer skill for sharing.

This is an offline smoke test. It checks that the skill folder is portable,
the bundled Python scripts compile, default config uses the intended one-year
window, and the dashboard generator can render a small bilingual sample.
"""

from __future__ import annotations

import datetime as dt
import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any


def fail(message: str) -> None:
    raise SystemExit(f"FAIL: {message}")


def ok(message: str) -> None:
    print(f"OK: {message}")


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig")


def check_frontmatter(skill_dir: Path) -> None:
    skill_md = skill_dir / "SKILL.md"
    if not skill_md.exists():
        fail("SKILL.md is missing")
    text = read_text(skill_md)
    if not text.startswith("---\n"):
        fail("SKILL.md must start with YAML frontmatter")
    _, frontmatter, body = text.split("---", 2)
    fields: dict[str, str] = {}
    for line in frontmatter.splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        fields[key.strip()] = value.strip()
    if fields.get("name") != skill_dir.name:
        fail(f"frontmatter name must equal folder name {skill_dir.name!r}")
    if not fields.get("description"):
        fail("frontmatter description is missing")
    if len(body.strip()) < 100:
        fail("SKILL.md body is unexpectedly short")
    ok("frontmatter and SKILL.md body")


def check_no_generated_or_local_artifacts(skill_dir: Path) -> None:
    pycache = list(skill_dir.rglob("__pycache__"))
    if pycache:
        fail("__pycache__ folders should not be shipped with the skill")
    home = str(Path.home())
    local_workspace_drive = "E:"
    local_workspace_name = "project" + "2"
    forbidden = [
        home,
        home.replace("\\", "/"),
        "\\".join([local_workspace_drive, local_workspace_name]),
        "/".join([local_workspace_drive, local_workspace_name]),
        "building-energy-carbon-ai-feasibility",
        "polar-architecture-buildings",
        "prefabricated-modular-lca-moo-trial",
        "127.0.0.1:8770",
    ]
    offenders: list[str] = []
    for path in skill_dir.rglob("*"):
        if not path.is_file() or path.suffix.lower() in {".pyc", ".pdf", ".png", ".jpg", ".jpeg"}:
            continue
        if path.name == "quick_validate.py":
            continue
        text = read_text(path)
        for token in forbidden:
            if token in text:
                offenders.append(f"{path.relative_to(skill_dir)} contains {token}")
    if offenders:
        fail("; ".join(offenders[:6]))
    ok("no generated cache folders or local run paths")


def run(command: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(command, cwd=str(cwd), text=True, capture_output=True, encoding="utf-8")
    if result.returncode != 0:
        print(result.stdout)
        print(result.stderr, file=sys.stderr)
        fail("command failed: " + " ".join(command))
    return result


def check_scripts_compile(skill_dir: Path) -> None:
    scripts = sorted((skill_dir / "scripts").glob("*.py"))
    if not scripts:
        fail("scripts/*.py is missing")
    for script in scripts:
        try:
            compile(read_text(script), str(script), "exec")
        except SyntaxError as exc:
            fail(f"syntax error in {script.relative_to(skill_dir)}: {exc}")
    ok(f"compiled {len(scripts)} Python scripts")


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def check_default_config(skill_dir: Path, work_dir: Path) -> None:
    script = skill_dir / "scripts" / "systematic_literature_review.py"
    output = work_dir / "review-config.json"
    run(
        [
            sys.executable,
            str(script),
            "init-config",
            "--topic",
            "AI in building energy and carbon",
            "--output",
            str(output),
        ],
        skill_dir,
    )
    config = load_json(output)
    start = dt.date.fromisoformat(config["from_date"])
    end = dt.date.fromisoformat(config["to_date"])
    days = (end - start).days
    if not (360 <= days <= 370):
        fail(f"default date window should be about one year, got {days} days")
    ok("default init-config date window is one year")


def sample_papers() -> dict[str, Any]:
    return {
        "config": {"topic": "Portable dashboard smoke test"},
        "papers": [
            {
                "rank": 1,
                "title": "Physics-informed learning for building energy prediction",
                "authors": "A. Author; B. Author",
                "journal": "Energy and Buildings",
                "publication_date": "2026-01-15",
                "article_type": "research article",
                "doi": "10.1016/j.enbuild.2026.000001",
                "homepage_url": "https://www.sciencedirect.com/journal/energy-and-buildings",
                "official_impact_factor": "7.1",
                "theme": "Building Energy Prediction",
                "primary_method": "Physics-Informed AI",
                "abstract": "This paper studies building energy prediction with physics-informed neural networks.",
            },
            {
                "rank": 2,
                "title": "Machine learning for operational carbon reduction in buildings",
                "authors": "C. Author",
                "journal": "Applied Energy",
                "publication_date": "2025-11-08",
                "article_type": "research article",
                "doi": "10.1016/j.apenergy.2025.000002",
                "homepage_url": "https://www.sciencedirect.com/journal/applied-energy",
                "official_impact_factor": "10.1",
                "theme": "Operational Carbon Reduction",
                "primary_method": "ML/DL Prediction and Optimization",
                "abstract": "The study links machine learning, demand response, and operational carbon.",
            },
            {
                "rank": 3,
                "title": "Review of AI-assisted decarbonization pathways for the built environment",
                "authors": "D. Author",
                "journal": "Nature Communications",
                "publication_date": "2025-09-20",
                "article_type": "review article",
                "doi": "10.1038/s41467-025-00003",
                "homepage_url": "https://www.nature.com/ncomms/",
                "official_impact_factor": "14.7",
                "theme": "Decarbonization Pathways",
                "primary_method": "Review / Framework",
                "abstract": "This review maps AI methods for built-environment decarbonization.",
            },
        ],
    }


def check_dashboard_build(skill_dir: Path, work_dir: Path) -> None:
    papers_path = work_dir / "metadata" / "papers.json"
    papers_path.parent.mkdir(parents=True, exist_ok=True)
    papers_path.write_text(json.dumps(sample_papers(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    dashboard_script = skill_dir / "scripts" / "build_literature_dashboard.py"
    spec_path = work_dir / "dashboard-spec.json"
    run(
        [
            sys.executable,
            str(dashboard_script),
            "init-spec",
            "--papers",
            str(papers_path),
            "--output",
            str(spec_path),
            "--title",
            "建筑 AI 文献测试 / Building AI Literature Test",
        ],
        skill_dir,
    )
    run(
        [
            sys.executable,
            str(dashboard_script),
            "build",
            "--papers",
            str(papers_path),
            "--spec",
            str(spec_path),
            "--output-dir",
            str(work_dir),
            "--dashboard-name",
            "literature-dashboard",
        ],
        skill_dir,
    )
    html = read_text(work_dir / "literature-dashboard.html")
    data_js = read_text(work_dir / "literature-dashboard-data.js")
    for token in ("主题分类", "方法热度", "文章卡片", "期刊官网"):
        if token not in html:
            fail(f"dashboard HTML missing Chinese label {token!r}")
    if "Physics-informed learning" not in data_js:
        fail("dashboard data JS missing sample paper")
    mojibake_markers = [chr(code) for code in (0xFFFD, 0x6D93, 0x93C2, 0x934F, 0x942E, 0x93B5, 0x6FE1)]
    if any(marker in html + data_js for marker in mojibake_markers):
        fail("dashboard output appears to contain mojibake")
    ok("dashboard init-spec and build smoke test")


def main(argv: list[str] | None = None) -> int:
    args = argv or sys.argv[1:]
    skill_dir = Path(args[0]).resolve() if args else Path(__file__).resolve().parents[1]
    if not skill_dir.exists():
        fail(f"skill folder does not exist: {skill_dir}")
    check_frontmatter(skill_dir)
    check_no_generated_or_local_artifacts(skill_dir)
    check_scripts_compile(skill_dir)
    temp_root = Path(tempfile.mkdtemp(prefix="slr-skill-validate-"))
    try:
        check_default_config(skill_dir, temp_root / "config")
        check_dashboard_build(skill_dir, temp_root / "dashboard")
    finally:
        shutil.rmtree(temp_root, ignore_errors=True)
    print("PASS: zotero-literature-visualizer skill is share-ready for offline validation.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
