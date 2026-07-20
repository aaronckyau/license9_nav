# Reference Analysis

Last updated: 2026-07-17

## File inventory and integrity

| Reference file | Inspection | Key evidence |
|---|---|---|
| `reference/app_spec.md` | Full UTF-8 read | Multi-fund/class workflow, monthly NAV per share, report sections, inheritance, RFR, audit/versioning requirements. |
| `reference/formula_audit.md` | Full UTF-8 read | `legacy_excel_v1`, exact 2026 Q1 values, date/field issues, dynamic drawdown correction, external chart warning. |
| `reference/ui_reference.png` | Original-resolution visual inspection | White header, numbered workflow tabs, blue primary action, pale teal selection, light grid background, centered work panel, status badge. No OCR feature is carried into this app. |
| `reference/xsq_nav_history.xlsx` | Formula and cached-value passes with `openpyxl` | 21 worksheets; principal sheet `2026 Mar (monthly)`; formulas, cached results, NAV/RFR series, fixed ranges, and invalid legacy date confirmed. |
| `reference/xsq_2026_q1_newsletter.docx` | OOXML/package audit, Word render to PDF, four-page PNG review | A4, 0.5-inch margins, one section, four tables, inline chart, anchored header logo, footer fields, external Excel chart relation, manual layout gaps. |

The root copies of the workbook and newsletter have the same SHA-256 values as their `reference/` counterparts:

- Workbook: `e212b94b1e8ad5610023e05f7899890dc2e77047b7541915ac28b6cf9049727a`
- Newsletter: `b6d7dc5708377ad86732f19ee39f73b0d630c4177ac0c8e23451988df86bd273`

## Excel findings

The workbook has 21 sheets, including 17 visible/hidden monthly copies and three hidden quarterly-era sheets. Each monthly sheet duplicates a growing range, one chart, and fixed formulas. The principal `2026 Mar (monthly)` sheet is `A1:AG128` with 517 non-empty cells and 203 formula cells.

### Authoritative legacy NAV series

- Inception NAV: `E2 = 100`.
- Source inputs: share count in column B and total value in column C.
- NAV per share: column E (`C / B`).
- Raw date/month label: column D.
- Monthly return: column F.
- Growth factor: column G.
- Quarterly/YTD helper values: columns H/I.
- Rows 3-47 contain 45 monthly observations from July 2022 through March 2026.

Important cached values:

| Cell/period | Value |
|---|---:|
| 2022-07 first NAV | 103.011676 |
| 2022-08 running peak | 105.24273600000001 |
| 2025-04 trough | 44.79624962677401 |
| 2025-12 NAV | 92.25900603925423 |
| 2026-01 NAV | 90.61700453137055 |
| 2026-02 NAV | 90.70900308009685 |
| 2026-03 NAV | 77.27900516437292 |

### Formula/output evidence

- Q1/YTD: `E47/E44-1 = -0.1623689818260956`.
- ITD: `(E47-100)/100 = -0.2272099483562708`.
- Annualized return: `PRODUCT(G3:G47)^(12/COUNT(G3:G47))-1 = -0.06642386917348142`.
- Monthly sample SD: `STDEVA(F3:F47) = 0.15565486859606537`.
- Annualized volatility: `F56*SQRT(12) = 0.539204281707685`.
- Trailing 12-month volatility: `STDEVA(F36:F47)*SQRT(12) = 0.7803960768881653`.
- Positive/negative: `17/45 = 0.377777...` and `28/45 = 0.622222...`.
- RFR: average of `K59:K70 = 4.190858333333334%`; decimal `0.04190858333333334`.
- Sharpe: `(annualized return - RFR)/annualized volatility = -0.20091170671664707`.
- Workbook drawdown: fixed `E36/E32-1 = -0.414727436776988`; the application must use the dynamic result around `-0.57435305`.

### Data-quality and automation issues

- The first NAV and inception date both show 7 July 2022, yet the first return is +3.011676% from inception NAV.
- Most monthly labels use the first day rather than actual month-end dates.
- The RFR history contains the invalid string date `2021/9/31`.
- Workbook column labels are semantically inconsistent: `Indicative/ Official` holds amounts used to derive NAV per share.
- Fixed ranges and copied quarterly sheets can silently exclude newly added rows or allow mixed NAV/RFR cutoffs.
- Historical quarterly output is not consistently present on the latest monthly sheet, so the application must rebuild the matrix from dates.

## Word findings

The document is one A4 portrait section with 0.5-inch margins, four pages, Times New Roman-heavy direct formatting, no real heading styles, one anchored header logo, one inline chart, four tables, and PAGE/NUMPAGES footer fields. The content includes all required sections.

The chart package contains this external relationship:

```text
file:///C:\Users\lydia\Documents\yomiclient\cache\e3\XSQ Data till 2025 Dec(1).xlsx
```

The rendered document reveals a large unused lower half on page 2, a dense disclaimer page 3, and an almost empty page 4 containing only the final disclaimer line. The new generator will preserve the restrained navy/grey financial tone and report content, but use an embedded chart image, semantic styles, automatic flow, explicit table geometry, and no fixed four-page layout.

## Implementation mapping

| Reference concept | Application mapping |
|---|---|
| Organization/fund static content | `OrganizationSettings`, `Fund`, `FundStrategyHighlight`, `FundParty`, `FundTerm`, and `Contact`. |
| Inception NAV and monthly NAV rows | `ShareClass` and month-normalized `NAVRecord`; no total NAV/share-count runtime dependency. |
| Workbook formulas | Pure `Decimal` calculation service using dates and sequences, never cell coordinates. |
| Formula/cutoff evidence | Calculation detail metadata and immutable report snapshot JSON. |
| RFR table | Provider observations, cached records, ordered report snapshot observations, and manual override metadata. |
| Newsletter body | HTML preview plus clean built-in DOCX generator with embedded chart and flowing content. |
| Workbook/Word audit weaknesses | Validation gates, source-cell/raw-date retention, authenticated versioned files, SHA-256 hashes, and audit log. |
