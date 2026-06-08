# Bilingual Reporting Template

Use this structure for `review-bilingual.md`, `relationship-map.md`, and the
semantic content that feeds `dashboard-spec.json`.

## review-bilingual.md

Recommended sections:

1. `# Systematic Literature Review / 系统文献综述`
2. `## Search Scope / 检索范围`
   - Keywords, date window, IF rule, OA/non-OA handling, and number of included papers.
   - State that publisher-hosted PDFs were saved only after opening the official article/full-text page and clicking the visible publisher PDF control.
3. `## Evidence Labels / 证据标签`
   - Define `full-text read`, `abstract-only`, `metadata-only`, `research article`, and `review article`.
4. `## Theme Taxonomy / 主题分类`
   - Bilingual category names.
   - Explain how keyword groups, abstracts, and full-text findings were combined.
5. `## Method Taxonomy / 方法分类`
   - Bilingual method-family names.
   - Note the primary method assigned to each paper and secondary methods when important.
6. `## Paper Notes / 单篇文献笔记`
   - For each paper: title, authors, year, journal, DOI, IF evidence, article type, and access label.
   - Chinese note: objective, method, data/case, findings, limitations, relevance.
   - English note: objective, method, data/case, findings, limitations, relevance.
7. `## Category Synthesis / 分类综合`
   - Chinese and English synthesis for each theme and method family.
8. `## Gaps And Next Searches / 研究空白与后续检索`
   - Bilingual research gaps and suggested query refinements.

## relationship-map.md

Recommended sections:

1. `# Relationship Map / 关系图谱`
2. `## Theme-Method Matrix / 主题-方法矩阵`
   - Explain which paper connects which primary theme and primary method.
3. `## Conceptual Links / 概念关系`
   - Connect the user's domain concepts, assessment dimensions, models, datasets, and decisions.
4. `## Method Links / 方法关系`
   - Connect input data, model families, objective functions, constraints, validation, and outputs.
5. `## Paper-To-Paper Links / 文献之间的关系`
   - Identify review papers that frame the area.
   - Identify empirical/modeling papers that operationalize those frameworks.
   - Identify papers that share methods, datasets, objective functions, or application scenarios.
6. `## Suggested Mermaid Map / 建议图谱`
   - Include a Mermaid diagram when useful.

## dashboard-spec.json

After writing the synthesis, create or refine `dashboard-spec.json` using
`references/dashboard-spec.md`. The dashboard spec should reuse the same theme
and method names as the Markdown reports.

For each paper, write bilingual detail notes with:

- `topic`: what the paper studies and why it belongs to the assigned theme;
- `method`: model, algorithm, framework, or analytical approach;
- `data`: dataset, case, simulation setting, experiment, or evidence source;
- `findings`: main results and quantitative outcomes when available;
- `limits`: stated or inferred limitations, grounded in the available text;
- `relevance`: why the paper matters for the user's research question.

## Writing Rules

- Keep claims grounded in the evidence label.
- Do not infer methods or findings from title-only records.
- Use Chinese first, then English, unless the user asks otherwise.
- Preserve original paper titles, DOI links, journal names, and official source URLs exactly.
- Mention non-OA gaps when important papers could not be accessed.
- Do not mark a paper as `full-text read` or `PDF downloaded` unless the article
  page or repository landing page was visibly accessed before the PDF was saved.
- Do not imply direct hidden-URL or temporary signed-URL downloading for
  publisher-hosted papers.
- Keep category names stable across `review-bilingual.md`, `relationship-map.md`, and `dashboard-spec.json`.
