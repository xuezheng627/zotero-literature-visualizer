# Dashboard Spec

Use this reference when creating `dashboard-spec.json` for
`scripts/build_literature_dashboard.py`.

## Purpose

The dashboard generator is deterministic. Codex supplies the semantic layer in
`dashboard-spec.json` after reading the metadata, abstracts, and available full
texts. The script then renders the same dashboard pattern for any topic:

- paper cards with a detail layer;
- bilingual per-paper notes;
- theme taxonomy donut chart;
- AI/method hotspot donut chart;
- theme-method relationship flow map;
- official journal homepage links;
- local PDF launcher page.

## Minimal Workflow

Create a starter spec:

```powershell
& '<python>' '<skill-dir>\scripts\build_literature_dashboard.py' init-spec `
  --papers literature-reviews\<topic>\metadata\papers.json `
  --output literature-reviews\<topic>\dashboard-spec.json `
  --title "<dashboard title>" `
  --subtitle "<scope note>"
```

Refine `dashboard-spec.json`, then build:

```powershell
& '<python>' '<skill-dir>\scripts\build_literature_dashboard.py' build `
  --papers literature-reviews\<topic>\metadata\papers.json `
  --spec literature-reviews\<topic>\dashboard-spec.json `
  --output-dir literature-reviews\<topic> `
  --dashboard-name literature-dashboard
```

The build command writes:

- `literature-dashboard.html`
- `literature-dashboard-data.js`
- `literature-dashboard-details.js`
- `literature-dashboard-pdf-open.html`

## Spec Schema

```json
{
  "title": "Dashboard title",
  "subtitle": "Scope, date range, IF threshold, paper count",
  "theme_definitions": [
    {
      "name": "Building Energy and Control",
      "description": "What belongs in this category",
      "color": "#6d7d8b"
    }
  ],
  "method_definitions": [
    {
      "name": "Reinforcement Learning",
      "description": "DRL, MARL, robust RL, control policies",
      "color": "#c28b2c"
    }
  ],
  "paper_assignments": {
    "1": {
      "theme": "Building Energy and Control",
      "method": "Reinforcement Learning"
    }
  },
  "details": {
    "1": {
      "topic": {
        "zh": "中文研究主题总结。",
        "en": "English research-theme summary."
      },
      "method": {
        "zh": "中文方法总结。",
        "en": "English method summary."
      },
      "data": {
        "zh": "中文数据或案例总结。",
        "en": "English data/case summary."
      },
      "findings": {
        "zh": "中文主要结果总结。",
        "en": "English findings summary."
      },
      "limits": {
        "zh": "中文局限总结。",
        "en": "English limitations summary."
      },
      "relevance": {
        "zh": "中文重要性总结。",
        "en": "English relevance summary."
      }
    }
  }
}
```

## Classification Rules

- Assign exactly one primary `theme` and one primary `method` to each paper for
  the relationship flow map. Mention secondary themes/methods in the bilingual
  detail notes when relevant.
- Use 4-8 themes for a 30-paper dashboard unless the literature clearly demands
  fewer or more. Prefer 6 or fewer visible paper-card themes. Too many
  categories makes the donut and flow map hard to read.
- Use method categories that are meaningful for the user's field. For AI in the
  built environment, examples include `ML/DL Prediction and Optimization`,
  `Reinforcement Learning`, `Physics-Informed AI`, `Graph Neural Network`,
  `LLM / Knowledge Graph`, `Transformer / Foundation Model`, and `Computer
  Vision`. For other fields, rename categories to match the domain.
- Keep `theme_definitions[*].name`, `method_definitions[*].name`, and every
  `paper_assignments` value exactly identical; the dashboard uses these strings
  as keys.
- Preserve original English paper titles, journal names, DOI URLs, and official
  journal URLs in the paper metadata.
- Keep paper-card filters theme-only: `All` plus primary themes. Method families
  belong in the method donut and theme-method relationship map.

## Evidence Rules

- Do not write `full-text read` style claims unless a PDF or full-text page was
  actually accessed.
- For publisher-hosted PDFs, count a local PDF as properly acquired only when
  the article/full-text page was opened first and the visible publisher PDF
  control was clicked. Do not treat temporary signed asset URLs as the access
  starting point.
- When only metadata or abstract was available, write cautious notes and state
  that the evidence is abstract-only in the report.
- Link local PDFs only when the file exists in the run folder or was supplied by
  the user.
- The journal source link should use `homepage_url` when available, falling back
  to `official_if_evidence_url`.
