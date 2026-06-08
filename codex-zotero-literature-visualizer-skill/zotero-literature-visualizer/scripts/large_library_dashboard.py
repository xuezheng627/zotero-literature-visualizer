#!/usr/bin/env python3
"""Render the large-library dashboard layout for 100+ paper collections."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def write_js(path: Path, var_name: str, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    body = json.dumps(payload, ensure_ascii=False, indent=2)
    path.write_text(f"window.{var_name} = {body};\n", encoding="utf-8")


LARGE_LIBRARY_HTML = r"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Zotero Large Library Dashboard</title>
  <style>
    :root {
      --ink:#17212b; --muted:#64727e; --soft:#f3f6f7; --line:#d7e1e7; --panel:#fff;
      --blue:#326f9e; --green:#348269; --gold:#b67b25; --red:#bd5c68;
      --shadow:0 1px 2px rgba(20,31,42,.05), 0 10px 24px rgba(20,31,42,.045);
    }
    * { box-sizing:border-box; }
    body { margin:0; background:linear-gradient(180deg,#f8fafb 0,#eef3f5 100%); color:var(--ink); font-family:Inter, "Segoe UI", Arial, sans-serif; }
    main { width:min(1380px, calc(100vw - 32px)); margin:0 auto; padding:22px 0 42px; }
    h1, h2, h3 { margin:0; letter-spacing:0; }
    h1 { font-size:30px; line-height:1.14; }
    h2 { font-size:18px; line-height:1.25; }
    h3 { font-size:15px; line-height:1.3; }
    p { margin:0; }
    button, input, select { font:inherit; }
    button { border:1px solid var(--line); background:#fff; color:var(--ink); border-radius:5px; min-height:34px; padding:7px 10px; cursor:pointer; }
    button[aria-pressed="true"], .tab.active { background:var(--ink); color:#fff; border-color:var(--ink); }
    input, select { min-height:38px; border:1px solid var(--line); border-radius:5px; background:#fff; color:var(--ink); padding:8px 10px; width:100%; }
    a { color:#245f96; }
    .panel, .kpi, .subtheme-card, .detail-card { background:rgba(255,255,255,.96); border:1px solid var(--line); border-radius:6px; box-shadow:var(--shadow); }
    .hero { display:grid; grid-template-columns:1.15fr .85fr; gap:12px; align-items:stretch; margin-bottom:12px; }
    .intro { padding:18px; }
    .intro p, .hint, .small { color:var(--muted); font-size:12px; line-height:1.45; }
    .intro p { margin-top:8px; }
    .kpis { display:grid; grid-template-columns:repeat(3,minmax(0,1fr)); gap:8px; }
    .kpi { padding:13px; min-height:88px; }
    .kpi .label { color:var(--muted); font-size:11px; text-transform:uppercase; letter-spacing:.05em; }
    .kpi .value { font-size:28px; line-height:1; font-weight:790; margin-top:7px; }
    .kpi .note { color:var(--muted); font-size:11px; margin-top:7px; line-height:1.35; }
    .tabs { display:flex; gap:6px; flex-wrap:wrap; margin:12px 0; }
    .tab { min-width:118px; box-shadow:none; }
    .tab.active { box-shadow:inset 0 -2px 0 var(--gold); }
    .view { display:none; }
    .view.active { display:block; }
    .grid-2 { display:grid; grid-template-columns:1.05fr .95fr; gap:12px; align-items:start; }
    .grid-3 { display:grid; grid-template-columns:repeat(3,minmax(0,1fr)); gap:12px; align-items:start; }
    .panel { padding:16px; overflow:hidden; }
    .panel-head { display:flex; align-items:flex-start; justify-content:space-between; gap:10px; margin-bottom:12px; }
    .theme-stack { display:grid; gap:10px; }
    .theme-block { border:1px solid var(--line); border-radius:5px; background:#fbfdfd; padding:12px; }
    .theme-top { display:grid; grid-template-columns:10px 1fr auto; gap:9px; align-items:center; margin-bottom:9px; }
    .dot { width:10px; height:10px; border-radius:999px; display:block; }
    .subchips { display:flex; gap:6px; flex-wrap:wrap; }
    .subchip { border:1px solid var(--line); border-radius:999px; padding:4px 8px; font-size:12px; color:#354756; background:#fff; }
    .bars { display:grid; gap:9px; }
    .bar { display:grid; grid-template-columns:minmax(170px,260px) 1fr 48px; gap:10px; align-items:center; }
    .bar-name { min-width:0; font-size:13px; font-weight:680; line-height:1.25; }
    .bar-name span { display:block; color:var(--muted); font-size:11px; font-weight:500; margin-top:2px; }
    .track { height:15px; border:1px solid #dce6eb; border-radius:999px; background:#eef4f6; overflow:hidden; }
    .fill { height:100%; min-width:7px; border-radius:999px; }
    .count { color:var(--muted); font-size:12px; text-align:right; }
    .explore { display:grid; grid-template-columns:minmax(360px,390px) minmax(0,1fr); gap:16px; align-items:start; }
    .explore > aside.panel { position:sticky; top:12px; }
    .filters { display:grid; gap:8px; margin-top:10px; }
    .tree { display:grid; gap:4px; max-height:68vh; overflow:auto; padding-right:4px; }
    .tree button { width:100%; text-align:left; display:grid; grid-template-columns:1fr auto; gap:8px; align-items:center; border-color:transparent; background:transparent; border-radius:5px; }
    .tree button:hover { background:#f5f8fa; border-color:#dfe8ed; }
    .tree button[aria-pressed="true"] { background:var(--ink); color:#fff; border-color:var(--ink); }
    .tree button[aria-pressed="true"]:hover { background:var(--ink); color:#fff; border-color:var(--ink); }
    .tree .theme-node { border-left:3px solid transparent; font-weight:650; }
    .tree .theme-node[aria-expanded="true"]:not([aria-pressed="true"]) { border-color:#dfe8ed; border-left-color:#88aebe; background:#f1f7f8; }
    .tree .sub { margin-left:14px; font-size:12px; min-height:30px; border-left:2px solid #dce7ec; }
    .tree-count { color:var(--muted); font-size:11px; }
    button[aria-pressed="true"] .tree-count { color:#dbe7ee; }
    .results-head { display:flex; align-items:center; justify-content:space-between; gap:10px; margin-bottom:10px; }
    .results-actions { display:flex; justify-content:flex-end; gap:8px; flex-wrap:wrap; }
    .subtheme-list { display:grid; gap:9px; }
    .subtheme-card { box-shadow:none; overflow:hidden; border-left:3px solid #83aebe; }
    .subtheme-title { width:100%; border:0; border-radius:0; background:#fbfdfd; min-height:42px; display:grid; grid-template-columns:1fr auto; gap:10px; align-items:center; text-align:left; padding:10px 13px; }
    .year-list { display:grid; gap:6px; border-top:1px solid var(--line); background:#f7fafb; padding:9px 11px; }
    .year-card { border:1px solid var(--line); border-radius:4px; overflow:hidden; background:#fff; }
    .year-title { width:100%; border:0; border-radius:0; background:#fff; min-height:36px; display:grid; grid-template-columns:1fr auto; gap:10px; align-items:center; text-align:left; padding:8px 10px; font-size:13px; }
    .year-title:hover { background:#f7fbfd; }
    .paper-rows { display:grid; gap:1px; background:var(--line); border-top:1px solid var(--line); }
    .paper-row { display:grid; grid-template-columns:1fr 100px 150px 138px; gap:10px; align-items:center; min-height:40px; background:#fff; border:0; border-radius:0; text-align:left; padding:8px 11px; }
    .paper-title { min-width:0; color:#1f567a; font-weight:650; font-size:13px; line-height:1.28; }
    .paper-meta { color:var(--muted); font-size:11px; line-height:1.25; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
    .journal-info { border-top:1px solid var(--line); background:#f7fafb; padding:11px; display:grid; gap:10px; }
    .journal-facts { display:grid; grid-template-columns:repeat(4,minmax(0,1fr)); gap:8px; }
    .journal-fact { border:1px solid var(--line); border-radius:4px; background:#fff; padding:9px; min-width:0; }
    .journal-fact span { display:block; color:var(--muted); font-size:11px; margin-bottom:3px; }
    .journal-fact strong, .journal-fact a { color:var(--ink); font-size:12px; line-height:1.25; overflow-wrap:anywhere; }
    .map-wrap { display:grid; grid-template-columns:minmax(0,1fr) 360px; gap:12px; align-items:start; }
    .relation-svg { width:100%; height:520px; display:block; border:1px solid var(--line); border-radius:5px; background:#fbfdfd; }
    .relation-link { fill:none; opacity:.42; cursor:pointer; transition:opacity .15s ease, stroke-width .15s ease; }
    .relation-link:hover, .relation-link.active { opacity:.92; }
    .relation-label { font-size:12px; font-weight:760; fill:var(--ink); }
    .relation-sub { font-size:11px; fill:var(--muted); }
    .side-list { max-height:520px; overflow:auto; display:grid; gap:7px; padding-right:4px; }
    .mini-paper { border:1px solid var(--line); border-radius:5px; background:#fff; padding:9px; cursor:pointer; }
    .mini-paper strong { display:block; font-size:12px; line-height:1.3; color:#1f567a; }
    .mini-paper span { display:block; color:var(--muted); font-size:11px; margin-top:4px; }
    .detail-shell { position:fixed; inset:0; display:none; background:rgba(13,24,32,.45); z-index:50; padding:22px; overflow:auto; }
    .detail-shell.open { display:block; }
    .detail-card { width:min(920px, calc(100vw - 32px)); margin:0 auto; padding:20px; box-shadow:0 18px 54px rgba(9,18,24,.24); }
    .detail-top { display:flex; justify-content:space-between; gap:12px; align-items:flex-start; }
    .eyebrow { color:var(--muted); font-size:12px; margin-bottom:6px; }
    .detail-card h2 { font-size:23px; line-height:1.25; }
    .detail-actions { display:flex; gap:7px; flex:0 0 auto; }
    .icon-button { width:36px; min-height:36px; padding:0; display:grid; place-items:center; font-size:18px; }
    .tags { display:flex; flex-wrap:wrap; gap:6px; margin-top:10px; }
    .tag { border:1px solid var(--line); border-radius:999px; background:#fff; color:var(--muted); font-size:12px; line-height:1; padding:4px 8px; }
    .tag.theme { color:#1e638a; background:#eaf5fb; border-color:#cae2ef; }
    .tag.subtheme { color:#725723; background:#fff7df; border-color:#eedaa7; }
    .tag.method { color:#316b57; background:#edf8f3; border-color:#cde8dd; }
    .detail-grid { display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:9px; margin:13px 0; }
    .detail-fact { border:1px solid var(--line); border-radius:5px; padding:9px; background:#fbfdfd; }
    .detail-fact span { display:block; color:var(--muted); font-size:11px; margin-bottom:4px; }
    .detail-fact strong { font-size:13px; line-height:1.25; overflow-wrap:anywhere; }
    .detail-section { border-top:1px solid var(--line); padding-top:12px; margin-top:12px; }
    .detail-section h3 { font-size:15px; margin-bottom:7px; }
    .detail-section p { margin:6px 0; color:#273540; font-size:14px; line-height:1.55; }
    .lang-label { display:inline-block; min-width:28px; color:var(--muted); font-size:12px; font-weight:700; margin-right:4px; }
    .detail-links { display:flex; flex-wrap:wrap; gap:8px; margin-top:14px; }
    .detail-link { display:inline-flex; align-items:center; min-height:34px; border:1px solid var(--line); border-radius:5px; padding:7px 10px; background:#fff; color:#245f96; text-decoration:none; }
    @media (max-width:1060px) {
      main { width:min(100vw - 24px,820px); padding-top:16px; }
      .hero, .grid-2, .grid-3, .explore, .map-wrap { grid-template-columns:1fr; }
      .kpis { grid-template-columns:repeat(2,minmax(0,1fr)); }
      .explore > aside.panel { position:static; }
      .tree { max-height:none; }
      .paper-row { grid-template-columns:1fr; }
      .journal-facts { grid-template-columns:1fr; }
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
      <div class="kpi"><div class="label">Papers</div><div class="value" id="paperCount">0</div><div class="note">PDF-backed records</div></div>
      <div class="kpi"><div class="label">Themes</div><div class="value" id="themeCount">0</div><div class="note">primary categories</div></div>
      <div class="kpi"><div class="label">Subthemes</div><div class="value" id="subthemeCount">0</div><div class="note">second-level clusters</div></div>
      <div class="kpi"><div class="label">Methods</div><div class="value" id="methodCount">0</div><div class="note">method families</div></div>
      <div class="kpi"><div class="label">Journals</div><div class="value" id="journalCount">0</div><div class="note">known sources</div></div>
      <div class="kpi"><div class="label">PDFs</div><div class="value" id="pdfCount">0</div><div class="note">local files linked</div></div>
    </div>
  </section>

  <nav class="tabs" aria-label="Dashboard views">
    <button class="tab active" type="button" data-tab="overview">Overview / 总览</button>
    <button class="tab" type="button" data-tab="explore">Explore / 浏览</button>
    <button class="tab" type="button" data-tab="map">Map / 关系图</button>
  </nav>

  <section class="view active" id="view-overview">
    <div class="grid-2">
      <article class="panel">
        <div class="panel-head"><div><h2>主题树 / Theme Tree</h2><p class="hint">一级主题下显示二级子主题，便于快速定位。</p></div></div>
        <div class="theme-stack" id="overviewThemes"></div>
      </article>
      <div class="grid-1">
        <article class="panel" style="margin-bottom:12px;">
          <div class="panel-head"><div><h2>方法热度 / Method Hotspots</h2><p class="hint">按主要方法聚合，不再把每篇文章铺满页面。</p></div></div>
          <div class="bars" id="methodBars"></div>
        </article>
        <article class="panel">
          <div class="panel-head"><div><h2>Top 期刊 / Top Journals</h2><p class="hint">元数据缺失单独统计，不挤占期刊排行。</p></div></div>
          <div class="bars" id="topJournalBars"></div>
        </article>
      </div>
    </div>
  </section>

  <section class="view" id="view-explore">
    <div class="explore">
      <aside class="panel">
        <h2>浏览维度 / Browse</h2>
        <div class="tree" id="themeTree" style="margin-top:12px;"></div>
      </aside>
      <section class="panel">
        <div class="results-head">
          <div><h2>文章列表 / Papers</h2><p class="hint" id="resultHint"></p></div>
          <div class="results-actions">
            <button type="button" id="expandAllGroups">全部展开 / Expand all</button>
            <button type="button" id="collapseAllGroups">全部收起 / Collapse all</button>
            <button type="button" id="resetFilters">重置 / Reset</button>
          </div>
        </div>
        <div class="subtheme-list" id="paperGroups"></div>
      </section>
    </div>
  </section>

  <section class="view" id="view-map">
    <div class="map-wrap">
      <article class="panel">
        <div class="panel-head"><div><h2>主题 × 方法聚合关系图 / Aggregated Theme-Method Map</h2><p class="hint">线条宽度代表该主题-方法组合下的文章数量。点击线条查看对应文献。</p></div></div>
        <svg class="relation-svg" id="relationSvg" viewBox="0 0 1000 520"></svg>
      </article>
      <aside class="panel">
        <h2 id="mapTitle">选择一条关系线 / Select a link</h2>
        <p class="hint" id="mapHint">点击左侧曲线后，这里会列出对应文章。</p>
        <div class="side-list" id="mapPapers" style="margin-top:10px;"></div>
      </aside>
    </div>
  </section>

</main>

<aside class="detail-shell" id="detailShell" aria-hidden="true">
  <article class="detail-card">
    <div class="detail-top">
      <div><div class="eyebrow" id="detailEyebrow"></div><h2 id="detailTitle"></h2></div>
      <div class="detail-actions"><button class="icon-button" type="button" id="detailClose" title="关闭">×</button></div>
    </div>
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
const palette = ["#326f9e","#348269","#b67b25","#7b6fb2","#bd5c68","#5d8b54","#8a6f55","#4c8fbd","#9b6aa6"];
let activeTab = "overview";
let browseMode = "theme";
let activeTheme = "all";
let activeSubtheme = "all";
let expandedTreeTheme = "";
let activeMethod = "all";
let activeJournal = "all";
const expandedGroups = new Set();
const expandedYears = new Set();

function escapeHtml(value) {
  return String(value || "").replace(/[&<>"']/g, ch => ({ "&":"&amp;", "<":"&lt;", ">":"&gt;", "\"":"&quot;", "'":"&#39;" }[ch]));
}
function fileUrl(path) { return path ? encodeURI("file:///" + String(path).replace(/\\/g, "/")) : ""; }
function pdfLauncherUrl(paper) { return "__PDF_OPEN_FILE__?rank=" + encodeURIComponent(paper.rank); }
function paperAssign(p) { return assignments[String(p.rank)] || {}; }
function paperTheme(p) { return paperAssign(p).theme || p.theme || "General / 综合交叉"; }
function paperSubtheme(p) { return paperAssign(p).subtheme || p.subtheme || "General / 综合交叉"; }
function paperMethod(p) { return paperAssign(p).method || p.primary_method || "Other / 其他"; }
function paperYear(p) {
  const values = [p.publication_year, p.year, p.published_year, p.publication_date, p.published_date, p.date];
  for (const value of values) {
    const match = String(value || "").match(/(?:19|20)\d{2}/);
    if (match) return match[0];
  }
  return "Unknown year / 年份未知";
}
function yearStateKey(group, year) { return `${encodeURIComponent(group)}::${encodeURIComponent(year)}`; }
function clearYearsForGroup(group) {
  const prefix = `${encodeURIComponent(group)}::`;
  [...expandedYears].forEach(key => { if (key.startsWith(prefix)) expandedYears.delete(key); });
}
function knownJournal(p) { return p.journal && p.journal !== "Zotero local library" ? p.journal : ""; }
function journalGroup(p) { return p.journal_group || knownJournal(p) || "Metadata missing / 元数据缺失"; }
function colorForTheme(theme) {
  const idx = themeDefs.findIndex(item => item.name === theme);
  return (themeDefs[idx] && themeDefs[idx].color) || palette[Math.max(idx, 0) % palette.length];
}
function countBy(rows, fn) {
  const map = new Map();
  rows.forEach(row => { const key = fn(row); map.set(key, (map.get(key) || 0) + 1); });
  return [...map.entries()].sort((a,b) => b[1] - a[1] || a[0].localeCompare(b[0]));
}
function rowsForTheme(theme) { return papers.filter(p => paperTheme(p) === theme); }
function rowsForSubtheme(theme, subtheme) { return papers.filter(p => paperTheme(p) === theme && paperSubtheme(p) === subtheme); }
function groupStateKey(mode, name) { return `${mode}::${name}`; }
function displayJournal(p) { return knownJournal(p) || "Metadata missing / 元数据缺失"; }
function isMissingJournalName(name) { return String(name || "").startsWith("Metadata missing"); }
function sortJournalEntries(a, b) {
  const am = isMissingJournalName(a[0]);
  const bm = isMissingJournalName(b[0]);
  if (am !== bm) return am ? 1 : -1;
  return b[1].length - a[1].length || a[0].localeCompare(b[0]);
}
function homepageForJournal(items) {
  const hit = items.find(p => p.homepage_url || p.official_if_evidence_url);
  return hit ? (hit.homepage_url || hit.official_if_evidence_url || "") : "";
}
function impactFactorForJournal(items) {
  const values = items.map(p => Number(p.official_impact_factor || 0)).filter(Boolean);
  if (values.length) return Math.max(...values).toFixed(1);
  const text = items.map(p => String(p.official_impact_factor || "").trim()).find(Boolean);
  return text || "";
}
function categoryForPaper(p) {
  if (browseMode === "method") return paperMethod(p);
  if (browseMode === "journal") return displayJournal(p);
  if (activeTheme !== "all") return paperSubtheme(p);
  return paperTheme(p);
}
function groupByCategory(rows) {
  const byCategory = new Map();
  rows.forEach(p => {
    const key = categoryForPaper(p);
    if (!byCategory.has(key)) byCategory.set(key, []);
    byCategory.get(key).push(p);
  });
  return byCategory;
}
function renderBars(targetId, rows, maxRows, color) {
  const max = Math.max(...rows.map(([, n]) => n), 1);
  document.getElementById(targetId).innerHTML = rows.slice(0, maxRows).map(([name, count]) => `
    <div class="bar">
      <div class="bar-name">${escapeHtml(name)}<span>${count} paper(s)</span></div>
      <div class="track"><div class="fill" style="width:${Math.max(5, Math.round(count / max * 100))}%;background:${color};"></div></div>
      <div class="count">${count}</div>
    </div>`).join("");
}
function renderOverview() {
  document.getElementById("overviewThemes").innerHTML = themeDefs.map((def, index) => {
    const theme = def.name;
    const rows = rowsForTheme(theme);
    const subs = countBy(rows, paperSubtheme).slice(0, 8);
    return `<section class="theme-block">
      <div class="theme-top"><i class="dot" style="background:${def.color || palette[index % palette.length]}"></i><h3>${escapeHtml(theme)}</h3><strong>${rows.length}</strong></div>
      <div class="subchips">${subs.map(([name, count]) => `<span class="subchip">${escapeHtml(name)} · ${count}</span>`).join("")}</div>
    </section>`;
  }).join("");
  renderBars("methodBars", countBy(papers, paperMethod), 10, "var(--green)");
  renderBars("topJournalBars", countBy(papers.filter(knownJournal), knownJournal), 10, "var(--blue)");
}
function populateFilters() {}
function filteredPapers() {
  return papers.filter(p => {
    if (activeTheme !== "all" && paperTheme(p) !== activeTheme) return false;
    if (activeSubtheme !== "all" && paperSubtheme(p) !== activeSubtheme) return false;
    if (activeMethod !== "all" && paperMethod(p) !== activeMethod) return false;
    if (activeJournal !== "all" && displayJournal(p) !== activeJournal) return false;
    return true;
  });
}
function renderThemeTree() {
  const root = (mode, label, count) => `<button class="theme-node" type="button" data-mode="${mode}" aria-pressed="${browseMode === mode}"><span>${label}</span><span class="tree-count">${count}</span></button>`;
  const rows = [
    root("theme", "全部主题 / All themes", papers.length),
    root("method", "全部方法 / All methods", papers.length),
    root("journal", "全部期刊 / All journals", papers.length)
  ];
  document.getElementById("themeTree").innerHTML = rows.join("");
  document.querySelectorAll("#themeTree button").forEach(button => button.addEventListener("click", () => {
    const mode = button.dataset.mode || "theme";
    browseMode = mode;
    activeTheme = "all"; activeSubtheme = "all"; activeMethod = "all"; activeJournal = "all";
    expandedTreeTheme = "";
    expandedGroups.clear();
    expandedYears.clear();
    renderExplore();
  }));
}
function renderExplore() {
  const rows = filteredPapers();
  renderThemeTree();
  const title = browseMode === "method" ? "方法分类 / Methods" : browseMode === "journal" ? "期刊列表 / Journals" : "主题分类 / Themes";
  document.querySelector("#view-explore .results-head h2").textContent = title;
  document.getElementById("resultHint").textContent = `${rows.length} 篇文章 / ${rows.length} papers`;
  if (browseMode === "journal") {
    renderJournalGroups(rows);
    return;
  }
  renderCategoryGroups(rows);
}
function renderCategoryGroups(rows) {
  const byCategory = groupByCategory(rows);
  const groups = [...byCategory.entries()].sort((a,b) => b[1].length - a[1].length || a[0].localeCompare(b[0]));
  document.getElementById("paperGroups").innerHTML = groups.map(([sub, items]) => {
    const key = groupStateKey(browseMode, sub);
    const expanded = expandedGroups.has(key);
    const rowsHtml = expanded ? yearGroupsHtml(key, items) : "";
    return `<section class="subtheme-card">
      <button class="subtheme-title" type="button" data-group-key="${escapeHtml(key)}" aria-expanded="${expanded}"><strong>${escapeHtml(sub)}</strong><span>${items.length} papers · ${expanded ? "收起 / Collapse" : "展开 / Expand"}</span></button>
      ${rowsHtml}
    </section>`;
  }).join("") || `<p class="hint">没有匹配的文章 / No matching papers.</p>`;
  bindPaperGroupEvents();
}
function renderJournalGroups(rows) {
  const byJournal = groupByCategory(rows);
  const groups = [...byJournal.entries()].sort(sortJournalEntries);
  document.getElementById("paperGroups").innerHTML = groups.map(([journal, items]) => {
    const key = groupStateKey("journal", journal);
    const expanded = expandedGroups.has(key);
    const ifValue = impactFactorForJournal(items);
    const suffix = /^\d+(\.\d+)?$/.test(String(ifValue)) ? `IF ${ifValue} · ` : "";
    return `<section class="subtheme-card">
      <button class="subtheme-title" type="button" data-group-key="${escapeHtml(key)}" aria-expanded="${expanded}"><strong>${escapeHtml(journal)}</strong><span>${suffix}${items.length} papers · ${expanded ? "收起 / Collapse" : "展开 / Expand"}</span></button>
      ${expanded ? `${journalInfoHtml(journal, items)}${yearGroupsHtml(key, items)}` : ""}
    </section>`;
  }).join("") || `<p class="hint">没有匹配的期刊 / No matching journals.</p>`;
  bindPaperGroupEvents();
}
function journalInfoHtml(journal, items) {
  const homepage = homepageForJournal(items);
  const missingJournal = isMissingJournalName(journal);
  const ifValue = missingJournal ? "N/A - metadata missing" : (impactFactorForJournal(items) || "Verification needed");
  const metadataIssue = missingJournal || String(ifValue).startsWith("N/A - metadata");
  const years = countBy(items, paperYear).map(([year]) => year).join(", ");
  const link = metadataIssue ? "<strong>Repair Zotero metadata first</strong>" : (homepage ? `<a href="${escapeHtml(homepage)}">期刊官网 / Journal homepage</a>` : "<strong>Verification needed</strong>");
  return `<div class="journal-info">
    <div class="journal-facts">
      <div class="journal-fact"><span>期刊 / Journal</span><strong>${escapeHtml(journal)}</strong></div>
      <div class="journal-fact"><span>文章数 / Papers</span><strong>${items.length}</strong></div>
      <div class="journal-fact"><span>官方 IF / Official IF</span><strong>${escapeHtml(ifValue)}</strong></div>
      <div class="journal-fact"><span>官网 / Source</span>${link}</div>
    </div>
    <div class="journal-fact"><span>年份 / Years</span><strong>${escapeHtml(years || "Unknown year / 年份未知")}</strong></div>
  </div>`;
}
function bindPaperGroupEvents() {
  document.querySelectorAll("[data-rank]").forEach(el => el.addEventListener("click", () => openDetail(el.dataset.rank)));
  document.querySelectorAll("[data-year-group]").forEach(el => el.addEventListener("click", event => {
    if (event.target.closest("[data-rank]")) return;
    const group = el.dataset.yearGroup;
    const year = el.dataset.year;
    if (!group || !year) return;
    const key = yearStateKey(group, year);
    expandedYears.has(key) ? expandedYears.delete(key) : expandedYears.add(key);
    renderExplore();
  }));
  document.querySelectorAll("[data-group-key]").forEach(el => el.addEventListener("click", event => {
    const group = el.dataset.groupKey;
    if (!group || event.target.closest("[data-rank]")) return;
    if (expandedGroups.has(group)) {
      expandedGroups.delete(group);
      clearYearsForGroup(group);
    } else {
      expandedGroups.add(group);
    }
    renderExplore();
  }));
}
function yearGroupsHtml(group, items) {
  const byYear = new Map();
  items.forEach(p => {
    const year = paperYear(p);
    if (!byYear.has(year)) byYear.set(year, []);
    byYear.get(year).push(p);
  });
  const yearGroups = [...byYear.entries()].sort((a,b) => {
    const ay = parseInt(a[0], 10);
    const by = parseInt(b[0], 10);
    const an = Number.isFinite(ay) ? ay : -Infinity;
    const bn = Number.isFinite(by) ? by : -Infinity;
    return bn - an || a[0].localeCompare(b[0]);
  });
  return `<div class="year-list">${yearGroups.map(([year, yearItems]) => {
    const key = yearStateKey(group, year);
    const expanded = expandedYears.has(key);
    return `<section class="year-card">
      <button class="year-title" type="button" data-year-group="${escapeHtml(group)}" data-year="${escapeHtml(year)}" aria-expanded="${expanded}"><strong>${escapeHtml(year)}</strong><span>${yearItems.length} papers · ${expanded ? "收起 / Collapse" : "展开 / Expand"}</span></button>
      ${expanded ? `<div class="paper-rows">${yearItems.map(paperRow).join("")}</div>` : ""}
    </section>`;
  }).join("")}</div>`;
}
function paperRow(p) {
  return `<button class="paper-row" type="button" data-rank="${p.rank}">
    <span class="paper-title">#${p.rank} ${escapeHtml(p.title)}</span>
    <span class="paper-meta">${escapeHtml(p.publication_date || "Unknown")}</span>
    <span class="paper-meta">${escapeHtml(knownJournal(p) || "Metadata missing")}</span>
    <span class="paper-meta">${escapeHtml(paperMethod(p))}</span>
  </button>`;
}
function relationPairs() {
  const map = new Map();
  papers.forEach(p => {
    const key = paperTheme(p) + "||| " + paperMethod(p);
    if (!map.has(key)) map.set(key, { theme: paperTheme(p), method: paperMethod(p), papers: [] });
    map.get(key).papers.push(p);
  });
  return [...map.values()].sort((a,b) => b.papers.length - a.papers.length);
}
function renderMap() {
  const pairs = relationPairs();
  const width = 1000, leftX = 250, rightX = 720, top = 38, bottom = 470;
  const themes = themeDefs.map(d => d.name);
  const methods = countBy(papers, paperMethod).map(([name]) => name);
  const themeY = new Map(themes.map((name, i) => [name, top + i * ((bottom - top) / Math.max(themes.length - 1, 1))]));
  const methodY = new Map(methods.map((name, i) => [name, top + i * ((bottom - top) / Math.max(methods.length - 1, 1))]));
  const max = Math.max(...pairs.map(p => p.papers.length), 1);
  const paths = pairs.map(pair => {
    const y1 = themeY.get(pair.theme) || top;
    const y2 = methodY.get(pair.method) || top;
    const d = `M ${leftX} ${y1} C ${leftX + 165} ${y1}, ${rightX - 165} ${y2}, ${rightX} ${y2}`;
    const width = Math.max(2.5, Math.round(pair.papers.length / max * 16));
    return `<path class="relation-link" d="${d}" stroke="${colorForTheme(pair.theme)}" stroke-width="${width}" data-theme="${escapeHtml(pair.theme)}" data-method="${escapeHtml(pair.method)}"><title>${escapeHtml(pair.theme)} → ${escapeHtml(pair.method)}: ${pair.papers.length}</title></path>`;
  }).join("");
  const leftLabels = themes.map(name => `<text class="relation-label" x="20" y="${(themeY.get(name) || top) + 4}" fill="${colorForTheme(name)}">${escapeHtml(name)}</text>`).join("");
  const rightLabels = methods.map(name => `<text class="relation-label" x="${rightX + 18}" y="${(methodY.get(name) || top) + 4}">${escapeHtml(name)}</text>`).join("");
  document.getElementById("relationSvg").innerHTML = `<text class="relation-sub" x="20" y="18">主题 / Theme</text><text class="relation-sub" x="${rightX + 18}" y="18">方法 / Method</text>${paths}${leftLabels}${rightLabels}`;
  document.querySelectorAll(".relation-link").forEach(path => path.addEventListener("click", () => showPair(path.dataset.theme, path.dataset.method)));
  const first = pairs[0];
  if (first) showPair(first.theme, first.method);
}
function showPair(theme, method) {
  document.querySelectorAll(".relation-link").forEach(path => path.classList.toggle("active", path.dataset.theme === theme && path.dataset.method === method));
  const rows = papers.filter(p => paperTheme(p) === theme && paperMethod(p) === method);
  document.getElementById("mapTitle").textContent = `${theme} × ${method}`;
  document.getElementById("mapHint").textContent = `${rows.length} 篇文章 / ${rows.length} papers`;
  document.getElementById("mapPapers").innerHTML = rows.map(p => `<article class="mini-paper" data-rank="${p.rank}"><strong>#${p.rank} ${escapeHtml(p.title)}</strong><span>${escapeHtml(paperSubtheme(p))} · ${escapeHtml(knownJournal(p) || "Metadata missing")}</span></article>`).join("");
  document.querySelectorAll("#mapPapers [data-rank]").forEach(el => el.addEventListener("click", () => openDetail(el.dataset.rank)));
}
function detailText(value) {
  if (value && typeof value === "object") {
    return `<p><span class="lang-label">ZH</span>${escapeHtml(value.zh || "")}</p><p><span class="lang-label">EN</span>${escapeHtml(value.en || "")}</p>`;
  }
  return `<p>${escapeHtml(value || "No note yet.")}</p>`;
}
function detailSection(title, value) {
  return `<section class="detail-section"><h3>${title}</h3>${detailText(value)}</section>`;
}
function openDetail(rank) {
  const paper = papers.find(p => String(p.rank) === String(rank));
  if (!paper) return;
  const detail = details[String(rank)] || {};
  document.getElementById("detailEyebrow").textContent = `Rank ${paper.rank} · ${paperTheme(paper)} · ${paper.article_type || "research article"}`;
  document.getElementById("detailTitle").textContent = paper.title;
  document.getElementById("detailTags").innerHTML = [
    ["theme", paperTheme(paper)],
    ["subtheme", paperSubtheme(paper)],
    ["method", paperMethod(paper)]
  ].map(([cls, text]) => `<span class="tag ${cls}">${escapeHtml(text)}</span>`).join("");
  document.getElementById("detailFacts").innerHTML = [
    ["期刊 / Journal", knownJournal(paper) || "Metadata missing / 元数据缺失"],
    ["日期 / Date", paper.publication_date || "Unknown"],
    ["类型 / Type", paper.article_type || ""],
    ["主题 / Theme", paperTheme(paper)],
    ["子主题 / Subtheme", paperSubtheme(paper)],
    ["方法 / Method", paperMethod(paper)],
    ["元数据质量 / Metadata", paper.metadata_quality || ""],
    ["PDF / Local PDF", paper.local_pdf_path ? "linked" : "missing"]
  ].map(([label, value]) => `<div class="detail-fact"><span>${label}</span><strong>${escapeHtml(value)}</strong></div>`).join("");
  document.getElementById("detailSections").innerHTML = [
    detailSection("研究主题 / Research Theme", detail.topic),
    detailSection("方法 / Method", detail.method),
    detailSection("数据或案例 / Data or Case", detail.data),
    detailSection("主要结果 / Findings", detail.findings),
    detailSection("局限 / Limitations", detail.limits),
    detailSection("为什么重要 / Relevance", detail.relevance)
  ].join("");
  const launcherHref = paper.local_pdf_path ? pdfLauncherUrl(paper) : "";
  document.getElementById("detailLinks").innerHTML = [
    paper.doi ? `<a class="detail-link" href="${escapeHtml(paper.doi)}">打开 DOI / Open DOI</a>` : "",
    launcherHref ? `<button class="detail-link" type="button" id="openPdfLauncher" data-href="${escapeHtml(launcherHref)}">打开本地 PDF / Open PDF</button>` : ""
  ].filter(Boolean).join("");
  const pdfButton = document.getElementById("openPdfLauncher");
  if (pdfButton) pdfButton.addEventListener("click", () => window.location.assign(pdfButton.dataset.href));
  document.getElementById("detailShell").classList.add("open");
  document.getElementById("detailShell").setAttribute("aria-hidden", "false");
  document.body.style.overflow = "hidden";
  history.replaceState(null, "", `#paper-${paper.rank}`);
}
function closeDetail(clearHash = true) {
  document.getElementById("detailShell").classList.remove("open");
  document.getElementById("detailShell").setAttribute("aria-hidden", "true");
  document.body.style.overflow = "";
  if (clearHash && location.hash.startsWith("#paper-")) history.replaceState(null, "", location.href.split("#")[0]);
}
function setTab(tab) {
  activeTab = tab;
  document.querySelectorAll(".tab").forEach(btn => btn.classList.toggle("active", btn.dataset.tab === tab));
  document.querySelectorAll(".view").forEach(view => view.classList.toggle("active", view.id === `view-${tab}`));
}
document.getElementById("dashTitle").textContent = spec.title || "Zotero Literature Library";
document.getElementById("dashSubtitle").textContent = spec.subtitle || "";
document.getElementById("paperCount").textContent = papers.length;
document.getElementById("themeCount").textContent = themeDefs.length;
document.getElementById("subthemeCount").textContent = countBy(papers, paperSubtheme).length;
document.getElementById("methodCount").textContent = countBy(papers, paperMethod).length;
document.getElementById("journalCount").textContent = countBy(papers.filter(knownJournal), knownJournal).length;
document.getElementById("pdfCount").textContent = papers.filter(p => p.local_pdf_path).length;
document.querySelectorAll(".tab").forEach(btn => btn.addEventListener("click", () => setTab(btn.dataset.tab)));
document.getElementById("resetFilters").addEventListener("click", () => {
  browseMode = "theme";
  activeTheme = "all"; activeSubtheme = "all"; activeMethod = "all"; activeJournal = "all";
  expandedTreeTheme = "";
  expandedGroups.clear();
  expandedYears.clear();
  renderExplore();
});
document.getElementById("expandAllGroups").addEventListener("click", () => {
  groupByCategory(filteredPapers()).forEach((items, group) => {
    const key = groupStateKey(browseMode, group);
    expandedGroups.add(key);
    countBy(items, paperYear).forEach(([year]) => expandedYears.add(yearStateKey(key, year)));
  });
  renderExplore();
});
document.getElementById("collapseAllGroups").addEventListener("click", () => {
  expandedGroups.clear();
  expandedYears.clear();
  renderExplore();
});
document.getElementById("detailClose").addEventListener("click", () => closeDetail());
document.getElementById("detailShell").addEventListener("click", event => { if (event.target.id === "detailShell") closeDetail(); });
document.addEventListener("keydown", event => { if (event.key === "Escape") closeDetail(); });
function openHashDetail() {
  const match = location.hash.match(/^#paper-(.+)$/);
  if (match) openDetail(decodeURIComponent(match[1]));
}
populateFilters();
renderOverview();
renderExplore();
renderMap();
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
    document.getElementById("meta").textContent = `${paper.journal || "Metadata missing"} · ${paper.publication_date || ""}`;
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


def write_large_library_dashboard(
    *,
    output_dir: Path,
    dashboard_file: str,
    data_file: str,
    details_file: str,
    pdf_open_file: str,
    data_payload: dict[str, Any],
    details: dict[str, Any],
) -> None:
    write_js(output_dir / data_file, "__SLR_DASHBOARD_DATA__", data_payload)
    write_js(output_dir / details_file, "__SLR_DASHBOARD_DETAILS__", details)
    (output_dir / dashboard_file).write_text(
        LARGE_LIBRARY_HTML.replace("__DATA_FILE__", data_file)
        .replace("__DETAILS_FILE__", details_file)
        .replace("__PDF_OPEN_FILE__", pdf_open_file),
        encoding="utf-8",
    )
    (output_dir / pdf_open_file).write_text(
        PDF_OPEN_HTML.replace("__DATA_FILE__", data_file).replace("__DASHBOARD_FILE__", dashboard_file),
        encoding="utf-8",
    )
