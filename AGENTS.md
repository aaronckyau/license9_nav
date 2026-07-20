# AGENTS.md — NAV Quarterly Report App

## Project objective

Build and maintain the internal multi-fund NAV quarterly reporting application described in `docs/` and the read-only files under `reference/`.

## Required context

Before changing domain logic, calculations, imports, or report generation, read:

- `docs/EXEC_PLAN.md`
- `docs/IMPLEMENTATION_STATUS.md`
- `reference/app_spec.md` or the equivalent original specification file
- `reference/formula_audit.md` or the equivalent original audit file

Inspect the Excel and Word references when a task depends on their structure. Never modify files under `reference/`.

## Working rules

- Work directly in the repository; do not return snippets instead of implementing changes.
- Keep `docs/IMPLEMENTATION_STATUS.md` current.
- Record non-blocking assumptions in `docs/ASSUMPTIONS.md` and continue.
- Use Django, PostgreSQL, server-rendered templates, and Docker Compose unless the repository already contains an approved alternative.
- Use `decimal.Decimal` for authoritative financial values and round only for presentation.
- Preserve the formula identifier `legacy_excel_v1` unless a new version is intentionally introduced.
- Do not copy fixed Excel row/cell references into application logic.
- Maximum drawdown uses the dynamic running-peak algorithm, not the workbook’s fixed-cell result.
- RFR observations must not extend beyond the report end.
- Generated DOCX files must not contain external Excel relationships.
- Finalized reports are immutable and reproducible from saved snapshots.
- No OCR functionality belongs in this project; the screenshot is UI inspiration only.
- Never commit secrets or real credentials.
- Do not use runtime public CDNs.

## Quality gates

After relevant changes, run the smallest useful tests first, then the full suite before handover:

```text
pytest
ruff check .
ruff format --check .
```

Also run the Docker report smoke test when report-generation or deployment files change.

Do not claim success without reporting the commands run and their actual outcomes.
