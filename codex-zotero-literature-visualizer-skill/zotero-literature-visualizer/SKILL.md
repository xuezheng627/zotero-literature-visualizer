---
name: zotero-literature-visualizer
description: Collect, verify, download, classify, visualize, and synthesize recent high-impact academic literature from user keywords or direct Zotero PDF libraries, with a quality-first default of the best 30 papers from the last year regardless of OA status. Use when the user asks for a systematic or semi-systematic literature review, recent top papers, Zotero direct import, journal Impact Factor filtering, official journal source verification, school/library-login PDF access for non-OA papers, bilingual Chinese-English summaries, paper classification, relationship analysis, or an interactive dashboard with paper cards, category charts, method hotspots, and local PDF links.
---

# Zotero Literature Visualizer / Zotero 文献整理可视化

## Overview

Use this skill to build a local literature-review library from any user-provided
keywords. The default goal is quality-first: identify the best 30 papers from
the last year in high-impact journals, regardless of OA status. OA availability
must never be used as a selection or ranking criterion. The workflow verifies
journal Impact Factor from official journal or publisher pages, prepares
manual school/library-login access for closed papers, reads available full
texts, writes bilingual Chinese-English synthesis, and renders an interactive
dashboard.

The bundled scripts handle deterministic metadata collection, OA PDF discovery,
manual PDF queues, metadata export, starter dashboard specs, and dashboard
rendering.
Codex still performs the scholarly judgment: official IF verification,
full-text reading, taxonomy design, bilingual paper notes, and relationship
analysis.

## Zotero Direct Import Mode

Use Zotero mode when the user already has papers and PDFs in Zotero and wants a
visual review of their own library. Do not ask the user to export BibTeX, RIS,
CSV, or Zotero RDF unless direct reading fails.

Default behavior:

- Auto-discover `~/Zotero` or use `ZOTERO_DATA_DIR` / `--zotero-dir`.
- Copy `zotero.sqlite` to a temporary snapshot before reading it, so Zotero can
  stay open and the original database is never modified.
- Read titles, authors, year, journal, DOI, abstract, Zotero tags,
  collections, item type, and PDF attachment paths.
- Include only Zotero items whose PDF attachment resolves to an existing local
  file.
- Skip items without local PDFs; never label them as full-text items.
- Point `local_pdf_path` to the original Zotero PDF. Do not copy or move PDFs by
  default.
- Do not run OpenAlex/Crossref/Unpaywall and do not apply IF>5 filtering unless
  the user explicitly asks for extra official IF verification.
- For user-facing Zotero runs, omit `--limit` so each user's full local
  PDF-backed Zotero library is imported. Use `--limit` only for smoke tests,
  debugging, or when the user explicitly asks for a smaller subset.
- When a Zotero run has more than 100 papers, automatically use the
  `large-library` dashboard layout: two-level theme/subtheme taxonomy, search,
  a compact theme tree that reveals subthemes only for the selected primary
  theme, collapsible subtheme and year paper groups, aggregated theme-method
  maps, and a journal browser with missing metadata separated from real journal
  sources.

Typical user request:

```text
Use zotero-literature-visualizer Zotero mode to read all Zotero items with local PDFs, classify them, summarize them bilingually, and generate the visualization dashboard.
```

Command pattern:

```powershell
& '<python>' '<skill-dir>\scripts\systematic_literature_review.py' zotero-import `
  --output-dir literature-reviews\zotero-library `
  --topic "My Zotero Library" `
  --dashboard-name zotero-literature-dashboard
```

Optional controls:

- `--zotero-dir <path>` when Zotero is not under the default user folder.
- `--limit 100` for a smoke test or a smaller dashboard only; do not use it in
  the final Zotero dashboard unless the user asks.
- `--max-text-chars 80000` to keep large libraries faster.
- `--no-extract-text` only when the user wants metadata and PDF links without
  text extraction.

Expected Zotero-mode outputs:

- `metadata/papers.json`
- `metadata/papers.csv`
- `metadata/zotero-import-summary.json`
- `texts/`
- `zotero-skipped.md`
- `manual-download.md` explaining that no new downloads are needed in this mode
- `review-bilingual.md`
- `relationship-map.md`
- `metadata-repair.md`
- `dashboard-spec.json`
- `<dashboard-name>.html`

After generation, inspect a few records: confirm `local_pdf_path` opens, the
paper count matches the intended PDF-backed set or limit, theme/method labels
are populated, and the dashboard has no mojibake. If the user wants a polished
final literature review, read representative extracted text files and refine
`dashboard-spec.json`, `review-bilingual.md`, and `relationship-map.md` with
real scholarly judgment.

## Zotero API Import Mode

Use Zotero API import mode when the user wants newly downloaded papers to be
added back into Zotero automatically. Prefer this over editing `zotero.sqlite`
directly. Never print or commit the user's API key.

Key handling:

- Read the key from `ZOTERO_API_KEY` or a user-provided `--api-key-file`.
- Keep API keys outside the skill folder and outside share zips.
- Verify permissions before writing. The key needs personal library write
  access; PDF upload also needs file access. Group access is not needed unless
  the user explicitly wants group-library imports.

Verify a key:

```powershell
& '<python>' '<skill-dir>\scripts\zotero_api_import.py' --api-key-file '<key-file-or-folder>' verify-key
```

Import a downloaded-paper manifest:

```powershell
& '<python>' '<skill-dir>\scripts\zotero_api_import.py' --api-key-file '<key-file-or-folder>' import-manifest `
  --manifest '<run-dir>\metadata\papers-to-zotero.json' `
  --collection 'Codex Imported Papers' `
  --tag 'Codex-imported' `
  --upload-files `
  --output '<run-dir>\metadata\zotero-api-import-log.json'
```

For local linked PDFs that should appear in Zotero without using Zotero cloud
file storage, replace `--upload-files` with `--link-files`:

```powershell
& '<python>' '<skill-dir>\scripts\zotero_api_import.py' --api-key-file '<key-file-or-folder>' import-manifest `
  --manifest '<run-dir>\metadata\papers-to-zotero.json' `
  --collection 'Codex Imported Papers' `
  --tag 'Codex-imported' `
  --link-files `
  --output '<run-dir>\metadata\zotero-api-import-log.json'
```

Manifest rows may include `title`, `authors`, `doi`, `journal`,
`publication_date` or `publication_year`, `abstract`, `url`, and
`local_pdf_path`. The importer creates `journalArticle` items, creates or reuses
the collection, adds the tag, skips existing DOI matches by default, and uploads
local PDF files as child attachments when `--upload-files` is set, or creates
local linked-file child attachments when `--link-files` is set. If Zotero
returns a storage-quota error for a PDF, keep the article item, log the failed
attachment, and explain that Zotero cloud file storage may need more space or a
local/manual import workflow.

For local-only PDF workflows, use `--link-files`, not `--upload-files`. The
Zotero Web API still writes Zotero library metadata online, but linked-file PDF
attachments point to the user's local disk and do not upload the PDF bytes to
Zotero File Storage. If `--link-files` is unavailable or a local Zotero setup
does not sync linked-file attachment metadata as expected, use one of these
fallback local-first approaches:

- Keep the Zotero article item created by the API and store `local_pdf_path` in
  the dashboard overlay.
- Generate a Zotero Desktop JavaScript runner that uses the local Zotero
  JavaScript API to add linked-file PDF attachments from the user's disk.
- On Windows, optionally generate a small PowerShell helper for the run folder
  that copies the Zotero Desktop JavaScript runner to the clipboard and starts
  Zotero. Do not use fragile SendKeys-style UI automation by default; let the
  user click Zotero's Run button unless they explicitly accept that risk.
- Generate a RIS/BibTeX import package for the user to import in Zotero
  Desktop. Avoid direct writes to `zotero.sqlite`.

## Portability And Validation

Use portable placeholders in instructions and commands. Resolve `<skill-dir>` to
the installed skill folder and `<python>` to a real Python 3 executable. On
Windows, the bare `python` command may point to the Microsoft Store placeholder;
use the Codex bundled Python or another installed Python if that happens.

Before sharing or after installing the skill on a new machine, run:

```powershell
& '<python>' '<skill-dir>\scripts\quick_validate.py' '<skill-dir>'
```

The validator checks frontmatter, required files, accidental local paths,
Python syntax, the default one-year config window, and a small bilingual
dashboard build. Do not distribute `__pycache__`, run folders, browser profiles,
PDFs, or downloaded publisher/session artifacts as part of the skill itself.

## Keyword And Scope Defaults

When the user provides keywords, translate them into keyword groups. Treat the
first group as the required domain and later groups as analytical/method groups
unless the user specifies another logic.

Example for building AI:

```powershell
& '<python>' '<skill-dir>\scripts\systematic_literature_review.py' init-config `
  --topic "AI methods in architecture, buildings, and construction" `
  --years 1 `
  --min-if 5 `
  --keyword-group "domain=architecture|building|construction|built environment" `
  --keyword-group "ai=artificial intelligence|machine learning|deep learning|LLM|foundation model" `
  --keyword-group "methods=reinforcement learning|computer vision|graph neural network|transformer|physics-informed neural network" `
  --output literature-reviews\<topic-slug>\review-config.json
```

When the user does not provide a topic, use the original default:

- `construction`: prefabricated/modular/off-site construction
- `lca`: life cycle assessment, embodied carbon, carbon footprint
- `optimization`: multi-objective optimization, Pareto, NSGA-II

Default inclusion logic: first keyword group AND at least one later keyword
group. Use explicit `--query` values or edit `review-config.json` when a field
needs a custom search equation.

## Quality-First Selection Rule

- Default to `--years 1`, `--min-if 5`, and a final target of `--limit 30`
  unless the user asks for a different window or count.
- Rank by relevance to the user keywords, cross-theme match strength, journal
  quality evidence, citation/recency signals available in metadata, and article
  importance. Do not rank by OA status.
- Include OA and non-OA papers equally if they are among the best 30.
- Treat OA PDF availability as metadata only. It is not a search filter and
  should not trigger direct background downloading before the publisher article
  page has been opened and checked.
- If the user wants the school-login workflow, omit `--download-oa` and use
  `--queue-all-manual` so every selected paper without a local PDF appears in
  `manual-download.md`.

## Core Workflow

1. Create a run folder under `literature-reviews/<topic-slug>/`.
2. Create and edit the config:
   ```powershell
   & '<python>' '<skill-dir>\scripts\systematic_literature_review.py' init-config --topic "<topic>" --years 1 --min-if 5 --output literature-reviews\<topic-slug>\review-config.json
   ```
   Add repeated `--keyword-group "name=term1|term2"` arguments for arbitrary
   domains. Use repeated `--query "<exact search query>"` to override automatic
   group combinations.
3. Collect a candidate pool larger than the final target from OpenAlex,
   Crossref-style OpenAlex metadata, source metrics, and Unpaywall metadata:
   ```powershell
   & '<python>' '<skill-dir>\scripts\systematic_literature_review.py' collect --config literature-reviews\<topic-slug>\review-config.json --output-dir literature-reviews\<topic-slug> --max-results 120
   ```
   This writes `metadata/all-candidates.*`,
   `metadata/journal-if-evidence.csv`, and `if-verification-needed.md`.
4. Verify journal Impact Factor from official journal or publisher pages. Read
   `references/if-verification.md`, then update
   `metadata/journal-if-evidence.csv`.
5. Finalize the verified set as the top 30. For a school-login workflow, queue
   selected papers for manual browser access:
   ```powershell
   & '<python>' '<skill-dir>\scripts\systematic_literature_review.py' finalize --candidates literature-reviews\<topic-slug>\metadata\all-candidates.json --if-evidence literature-reviews\<topic-slug>\metadata\journal-if-evidence.csv --output-dir literature-reviews\<topic-slug> --min-if 5 --limit 30 --queue-all-manual
   ```
   Do not add `--download-oa` for normal work. PDF access should proceed
   through the publisher-visible workflow below.
6. For non-OA papers in `manual-download.md`, ask the user to log in manually
   through their school/library/publisher page in the active browser session.
   Do not ask for passwords, store credentials, or bypass paywalls. Process
   only the explicit batch the user confirms or supplies.
7. Open each publisher article page, confirm that the article/full-text page is
   visible under authorized access, then click the official page-level
   `View PDF`, `Download PDF`, or equivalent PDF button. Save only the PDF that
   comes from that visible publisher flow.
8. Read downloaded PDFs with `pypdf` or an available PDF extractor. Label every
   paper as `full-text read`, `abstract-only`, `metadata-only`,
   `not accessible`, or `needs manual PDF`.
9. Write bilingual outputs using `references/reporting-template.md`:
   - `review-bilingual.md`
   - `relationship-map.md`
   - `dashboard-spec.json`
10. Render the dashboard:
   ```powershell
   & '<python>' '<skill-dir>\scripts\build_literature_dashboard.py' init-spec --papers literature-reviews\<topic-slug>\metadata\papers.json --output literature-reviews\<topic-slug>\dashboard-spec.json
   ```
   Refine `dashboard-spec.json` after reading the papers, then:
   ```powershell
   & '<python>' '<skill-dir>\scripts\build_literature_dashboard.py' build --papers literature-reviews\<topic-slug>\metadata\papers.json --spec literature-reviews\<topic-slug>\dashboard-spec.json --output-dir literature-reviews\<topic-slug> --dashboard-name literature-dashboard
   ```
   Read `references/dashboard-spec.md` before refining the spec.

## Preferred Browser Download Workflow

When the user wants automatic PDF retrieval after a one-time school/library
login, use the dedicated browser downloader instead of direct HTTP requests:

```powershell
& '<python>' '<skill-dir>\scripts\browser_pdf_downloader.py' `
  --run-dir literature-reviews\<topic-slug> `
  --browser chrome `
  --start-rank 1 `
  --limit 30
```

This script launches a separate Chrome profile, sets PDFs to download instead
of using hidden requests, fixes the download directory to the run folder's
`pdfs/`, opens each official article page, waits while the user completes any
school/library login in Chrome, clicks the visible publisher PDF control, opens
the PDF page/viewer, then clicks the visible PDF-viewer download/save control.
It validates, renames, and records the downloaded PDF in `metadata/papers.json`.
By default it watches only the run folder's `pdfs/` directory for stability;
use `--watch-user-downloads` only when the user has explicitly saved PDFs into
the normal Downloads folder and wants Codex to import them.

Use this as the default for non-OA or mixed-access review batches. It preserves
the user's browser login session in the dedicated profile for later batches, but
Codex must not read, export, or store credentials/cookies. If Chrome is blocked
by a publisher page, fall back to visible manual saving and then import the
file, rather than using hidden network URLs. Use `--direct-pdf-download` only
as a fallback when a publisher's PDF viewer cannot expose a usable visible
download control.

## Optional ChemDeep Integration

If the `literature-survey` or `deep-research` ChemDeep skills are installed and
the `mcp__chemdeep__...` tools are actually available in the active Codex
session, they may be used as an optional helper layer, not as a replacement for
this skill's quality gate and reporting workflow.

Use ChemDeep only for tasks it can improve:

- `literature-survey`: lightweight search, scoring, full-text detail fetching,
  browser-session preparation, or single-paper PDF download.
- `deep-research`: high-cost multi-iteration research only after explicit user
  confirmation.

When combining with ChemDeep:

1. Keep this skill responsible for official IF verification, final inclusion,
   metadata normalization, bilingual synthesis, relationship maps, and dashboard
   rendering.
2. Use ChemDeep's live-browser/PDF tools only after the user explicitly asks for
   full text or PDF downloading and has a lawful school/library/publisher
   session.
3. Preserve the same access boundary: official article page first, visible
   `Open/View PDF` control second, visible PDF-viewer download/save control
   third.
4. If ChemDeep tools are not visible in the active session, do not pretend they
   are available. Continue with the bundled OpenAlex/Unpaywall/browser workflow
   and tell the user that Codex must be restarted or the ChemDeep MCP server must
   be configured before those tools can be called.
5. Never let ChemDeep or any auxiliary downloader weaken the rules against
   paywall bypass, hidden signed URLs, credential handling, CAPTCHA automation,
   or false full-text-read claims.

## Optional ScienceDirect Live Session Fetcher

If `sciencedirect-live-session-fetcher` is installed, use it as a
publisher-specific helper for ScienceDirect/Elsevier-heavy batches only. It is
usually more useful than ChemDeep for this narrow problem because it provides a
dedicated Edge DevTools session, one-shot browser profiles, serial retries,
sleep intervals, and per-row success/missing CSVs.

Recommended routing:

- Use this `zotero-literature-visualizer` skill for discovery, IF verification,
  selection, metadata normalization, summaries, classification, and dashboards.
- For ScienceDirect/Elsevier rows, default to `sciencedirect-live-session-fetcher`
  after the user has explicitly confirmed an authorized browser session. Prefer a
  clean one-shot Edge session with extensions disabled and serial 5-8 second
  pauses. Use a small failed-row CSV when retrying.
- Use the bundled `browser_pdf_downloader.py` for non-Elsevier publishers or
  when the user specifically asks for the strict visible workflow: official
  article page -> visible `Open/View PDF` -> visible PDF-viewer download/save.
- After any ScienceDirect helper run, import only files that pass `%PDF-`
  validation and title/DOI matching, then update `papers.json`, `papers.csv`,
  and the dashboard. Do not mark a paper `full-text read` until the actual PDF
  text or full article page has been accessed.

Bridge helper:

```powershell
& '<python>' '<skill-dir>\scripts\sciencedirect_fetcher_bridge.py' prepare-csv `
  --run-dir literature-reviews\<topic-slug> `
  --source literature-reviews\<topic-slug>\metadata\verified-high-if-papers.json `
  --output literature-reviews\<topic-slug>\sciencedirect-fetch-input.csv `
  --missing-only

powershell -ExecutionPolicy Bypass -File '<sciencedirect-skill>\scripts\run_devtools_sciencedirect_fetch.ps1' `
  -InputCsv literature-reviews\<topic-slug>\sciencedirect-fetch-input.csv `
  -OutDir literature-reviews\<topic-slug>\sciencedirect-fetch-output `
  -PythonExe '<python>' `
  -DebugPort 9222 `
  -PageWaitSeconds 8 `
  -InterItemSleepSeconds 7

& '<python>' '<skill-dir>\scripts\sciencedirect_fetcher_bridge.py' import-results `
  --run-dir literature-reviews\<topic-slug> `
  --target literature-reviews\<topic-slug>\metadata\verified-high-if-papers.json `
  --results literature-reviews\<topic-slug>\sciencedirect-fetch-output\devtools_results.csv
```

Boundary:

- The ScienceDirect helper may extract short-lived ScienceDirect PDF metadata
  inside the authorized browser session. Treat that as a fallback for reliability,
  not as the default user-facing workflow when the user has asked for visible
  PDF clicking first.
- Do not use it for non-Elsevier publishers unless its Firefox mixed-publisher
  route exposes normal page metadata or visible PDF links.
- Do not reuse old browser-profile runtime folders as an access source. Launch a
  fresh dedicated session and let the user complete any login or verification.
- Never use it to bypass access controls, automate CAPTCHA/Cloudflare, copy
  credentials, or make hidden signed URLs look like durable PDF links.

## Impact Factor Rules

- Official Impact Factor evidence is mandatory for main inclusion when the user
  requests IF filtering.
- Use only the journal official page, a publisher-hosted journal page, or a
  metrics page linked from that journal/publisher page.
- Do not use OpenAlex, SJR, CiteScore, ResearchGate, LetPub, Resurchify,
  third-party journal lists, or search snippets as final IF evidence.
- If the official page does not clearly show the required IF value, keep the
  journal in `if-verification-needed.md` and exclude its papers until verified.
- Record `official_impact_factor`, `official_if_year`, `evidence_url`,
  `evidence_note`, `verified_date`, and `verified_by`.
- Match journals by title and ISSN/eISSN when similarly named titles exist.

## Non-OA And Manual Access

- Do not download a paper solely from a constructed PDF URL, temporary signed
  asset URL, OpenAlex PDF URL, Unpaywall URL, or hidden network request.
- For every publisher-hosted paper, first open the official article/full-text
  page in a visible, authorized browser session. Only after the article page is
  accessible should Codex click the page's visible `View PDF`, `Download PDF`,
  or equivalent publisher PDF control. Prefer opening the PDF page/viewer first,
  then clicking the visible PDF-viewer download/save control to save the file.
- For repositories such as arXiv, PMC, institutional repositories, or
  user-supplied files, the repository landing page should still be opened or
  recorded before saving the PDF.
- For closed or login-required papers, create or update `manual-download.md`
  with DOI, publisher URL, journal, IF evidence status, priority, and reason.
- Ask the user to manually log in to their school/library/publisher portal when
  those papers matter for the review.
- It is acceptable to open the publisher/library page in the browser and pause
  while the user logs in. The user must type credentials themselves.
- Use only the active browser session or PDFs the user places in the run folder.
- Never bypass paywalls, scrape credentials, store cookies, or automate hidden
  login steps.
- Never treat a temporary `pdf.sciencedirectassets.com`, S3, CDN, or signed PDF
  URL as the starting point for access. Those URLs may be used only as the
  browser's result after Codex has visibly opened the article page and clicked
  the official PDF button.
- Do not save `Supplementary Information`, `Supporting Information`, or
  additional-file PDFs as the article PDF unless the user explicitly asks for
  supplementary materials.
- If the browser or PDF viewer blocks automated file saving, pause and ask the
  user to click the visible publisher/PDF-viewer save button manually. Codex may
  then import, rename, validate, and summarize the PDF file that appears in the
  downloads folder.
- Never claim full-text reading unless a PDF or full-text page was actually
  accessed.

## Dashboard Rules

- Use 4-8 primary themes and 4-8 primary method families for a 30-paper review
  unless the literature clearly demands otherwise. Prefer 6 or fewer primary
  themes for the visible paper-card taxonomy.
- For Zotero or other large-library dashboards over 100 papers, keep the 5-6
  primary themes but add a second-level `subtheme` taxonomy. Keep each primary
  theme to at most 8 visible subthemes by merging small long-tail clusters into
  an "Other in <theme>" group.
- Assign each paper exactly one primary theme and one primary method in
  `dashboard-spec.json`; mention secondary relationships in the bilingual notes.
  For large-library layouts, also assign exactly one `subtheme`.
- Keep category names stable across `review-bilingual.md`,
  `relationship-map.md`, and `dashboard-spec.json`.
- The dashboard should include paper cards, bilingual detail notes, theme donut,
  method donut, theme-method flow map, official journal homepage links, DOI
  links, and local PDF launcher links when files exist.
- Large-library dashboards should use four main views: `Overview`, `Explore`,
  `Map`, and `Journals`. Use an aggregated theme-method map rather than one
  curve per paper, and default article lists to compact rows grouped by
  collapsible subtheme and year. In the Explore sidebar, show only the primary
  themes at first, then reveal the selected primary theme's subthemes.
- Keep `Unknown` or missing journal metadata out of normal journal rankings.
  Show it as `Metadata missing / 元数据缺失` and write `metadata-repair.md`.
- Paper-card filter controls should default to `All` plus theme categories only.
  Keep method families visible in the method donut and theme-method flow map,
  not as extra paper-card filters.
- Remove or avoid low-value status panels once PDFs and evidence are already
  integrated into the cards and detail layer.

## Bundled Resources

- `scripts/systematic_literature_review.py`: config creation, generic
  keyword-group search, OpenAlex discovery, Unpaywall enrichment, journal IF
  checklist generation, official-IF finalization, PDF access queue creation, and
  metadata export.
- `scripts/browser_pdf_downloader.py`: dedicated Chrome/Edge authorized-browser
  downloader for school/library-login batches. It opens official article pages,
  clicks visible PDF controls, uses browser-native downloads, and updates local
  PDF metadata.
- `scripts/build_literature_dashboard.py`: starter dashboard-spec creation and
  reusable interactive dashboard rendering.
- `scripts/large_library_dashboard.py`: offline large-library dashboard layout
  for 100+ paper Zotero/full-text libraries.
- `scripts/quick_validate.py`: offline portability and smoke-test validator for
  sharing or installing the skill on another machine.
- `references/if-verification.md`: official Impact Factor verification rules.
- `references/reporting-template.md`: bilingual review, relationship-map, and
  per-paper note structure.
- `references/dashboard-spec.md`: schema and rules for the dashboard semantic
  layer.
