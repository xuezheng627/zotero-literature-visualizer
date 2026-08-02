# Official Impact Factor Verification

Use this reference when final inclusion depends on journal Impact Factor > 5.

## Acceptable Evidence

Accept evidence only from:

- The journal's official homepage.
- A publisher-hosted journal page for that exact journal.
- A page linked directly from the official journal/publisher page that lists journal metrics.

Do not use third-party metric mirrors as final evidence. OpenAlex, SJR, CiteScore, Google snippets, ResearchGate, LetPub, Resurchify, and library guides can help discovery but cannot be final evidence for "Impact Factor > 5".

## Procedure

1. Group candidate papers by journal/source.
2. For each journal, open the official journal or publisher page.
3. Match the journal by title and ISSN/eISSN when possible.
4. Find the latest stated `Journal Impact Factor`, `Impact Factor`, or `JIF`.
5. Record the value only when the official page clearly states it.
6. Include the journal only when the numeric value is greater than 5.
7. If official evidence cannot be found quickly, leave the evidence fields blank and keep papers in `if-verification-needed.md`.

## Evidence CSV Fields

Fill or update these fields in `metadata/journal-if-evidence.csv`:

- `official_impact_factor`: numeric value, for example `9.8`.
- `official_if_year`: year or edition shown by the official page, for example `2024`.
- `evidence_url`: official page URL.
- `evidence_note`: short note such as `Publisher journal metrics page states Journal Impact Factor 9.8`.
- `verified_date`: ISO date when checked.
- `verified_by`: usually `Codex`.

Keep the original `journal`, `source_id`, `issn_l`, `issn`, `publisher`, `homepage_url`, and OpenAlex proxy fields intact.

## Ambiguity Rules

- If the title is ambiguous, use ISSN/eISSN to confirm the journal.
- If the official page lists several metrics, use only `Journal Impact Factor` or clearly equivalent `Impact Factor`.
- If a page lists CiteScore but not Impact Factor, do not treat it as IF.
- If the page says the journal is not indexed or has no IF, exclude it.
- If the current IF is not visible but a paper is strategically important, flag it for user/manual verification instead of including it.
