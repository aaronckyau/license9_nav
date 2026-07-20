# Codex Master Build Prompt — Multi-Fund NAV Quarterly Report Web App

You are the lead software engineer responsible for building a complete, production-ready internal web application in the current repository. Work directly in the repository: inspect the reference files, create the application, run it, test it, fix failures, and leave deployment documentation. Do not stop after planning or scaffolding, and do not respond with code snippets only.

## 1. Mission

Build an internal VPS-hosted web application that lets one full-access user:

1. Create and maintain multiple funds.
2. Create multiple share classes or series under each fund.
3. Enter one NAV per Share for each share class every month.
4. Automatically calculate the performance matrix and fund statistics using the legacy Excel methodology described below.
5. Fetch the risk-free rate online from an official source and retain the source observations used for each report.
6. Enter Manager Commentary each quarter.
7. Preview a professionally formatted quarterly newsletter.
8. Generate and download both Word (`.docx`) and PDF (`.pdf`) versions.
9. Preserve report versions, calculation snapshots, source data, hashes, and an audit trail.

The normal recurring workflow must be very simple:

```text
Select Fund / Share Class
→ Enter Monthly NAV per Share
→ Review Calculations and Validation
→ Enter Manager Commentary
→ Preview
→ Generate Word and PDF
→ Finalize and Download
```

## 2. Reference files — inspect these before implementation

Search the repository recursively for the following files. They may be in `reference/`, the repository root, or have their original filenames:

```text
NAV_Quarterly_Report_App_Spec_v1.md
XSQ_Excel_Formula_Audit_v1.md
XSQ Data till 202603.xlsx
X Squared Capital Management LPF Quarterly Newsletter 2026Q1_draft_pending commentary.docx
cf48be25-e91d-4924-9b08-086f08d0b469.png
```

Preferred renamed locations are:

```text
reference/app_spec.md
reference/formula_audit.md
reference/xsq_nav_history.xlsx
reference/xsq_2026_q1_newsletter.docx
reference/ui_reference.png
```

Before writing core application code:

1. Read both Markdown specifications in full.
2. Inspect the Excel workbook with `openpyxl` twice where useful: once with formulas and once with `data_only=True`.
3. Identify the source NAV series, dates, formulas, hard-coded values, quarterly outputs, risk-free-rate observations, and data-quality issues.
4. Inspect the Word package and document structure, including tables, headings, chart relationships, headers, footers, images, page layout, and any external links.
5. Use the screenshot only as visual workflow inspiration. It is an OCR project screenshot, but this new application must contain no OCR functionality.
6. Create `docs/reference_analysis.md` summarizing what was found and how the implementation maps the reference files into the new system.
7. Treat the reference files as read-only. Never modify or overwrite them.

The existing Word newsletter is the content and layout reference. It contains, at minimum:

- Fund name, quarter, professional-investor statement, and report date statement.
- Investment Objective.
- Strategy Highlights and Characteristics.
- Net Quarterly Returns table by year, Q1–Q4, and YTD.
- NAV per Share performance chart.
- Fund Statistics.
- Manager Commentary.
- General Information.
- Contacts.
- Disclaimer.

Create a cleaner layout with automatic pagination rather than copying the existing four-page breaks exactly.

## 3. Work method

At the start of the task:

1. Inspect the repository and reference files.
2. Create `docs/EXEC_PLAN.md` with phases, deliverables, risks, and checkboxes.
3. Create or update `docs/IMPLEMENTATION_STATUS.md` after each major phase.
4. Record non-blocking assumptions in `docs/ASSUMPTIONS.md` and proceed. Do not pause for ordinary implementation decisions.
5. Ask a question only when work is genuinely blocked by missing information that cannot be represented by a setting, placeholder, or documented assumption.
6. Make logical Git commits after stable phases when Git is available.
7. Continue until the critical acceptance criteria in this prompt pass.

Do not claim completion unless the relevant tests and smoke checks have actually run successfully. If an external dependency such as LibreOffice is unavailable in the current environment, implement it, test everything else, add a clear integration check, and document the exact command to validate it in Docker.

## 4. Required technical architecture

Use a conservative, maintainable server-rendered stack suitable for one internal VPS:

- Python 3.12 or a newer compatible stable release.
- Django current supported LTS release.
- PostgreSQL.
- Django templates for pages and forms.
- HTMX only where it materially improves the workflow; do not build a large SPA.
- Custom local CSS inspired by the reference screenshot. Do not depend on a public CDN at runtime.
- `decimal.Decimal` for stored NAV values and financial calculations.
- `openpyxl` for Excel inspection and import.
- `docxtpl` and/or `python-docx` for Word generation.
- Matplotlib for chart generation.
- LibreOffice headless for DOCX-to-PDF conversion.
- Gunicorn behind Nginx.
- Docker Compose for the complete VPS deployment.
- Pytest and `pytest-django` for tests.
- Ruff for linting and formatting.

Do not introduce Node.js unless there is a compelling and documented reason. Prefer a single Django codebase.

Suggested Django apps or equivalent modules:

```text
accounts
organization
funds
navs
performance
rfr
reports
audit
```

The exact directory structure may be improved, but domain responsibilities must remain clear.

## 5. Authentication and access

MVP access requirements:

- One permission level: full access.
- Use standard Django authentication.
- Require login for every application page and file download.
- No public registration.
- Provide change-password and logout functions.
- Create the initial account using `createsuperuser` or a documented bootstrap environment variable/management command.
- Keep authorization code structured so roles can be added later.

## 6. Organization defaults and fund overrides

Create an `OrganizationSettings` singleton or equivalent with defaults for:

- Organization display name.
- Default logo.
- Default primary brand colour.
- Default professional-investor statement.
- Default report-date statement template.
- Default disclaimer and its version/effective date.
- Default contact/address information.
- Default percentage decimal places: 2.
- Default Sharpe decimal places: 3.
- Default report language: English.
- Default risk-free-rate provider and series.

Each fund may inherit or override relevant values, especially:

- Logo.
- Brand colour.
- Professional-investor statement.
- Date statement.
- Disclaimer.
- Contacts.
- General Information values.
- Optional report template.

Make inheritance explicit in the UI, for example `Use organization default` versus `Fund override`.

## 7. Fund creation and maintenance

Implement a fund create/edit wizard or well-organized form containing the following.

### 7.1 Fund identity

- Fund Legal Name — required.
- Fund Display Name — required.
- Fund Short Code — required and unique.
- Fund Structure — required.
- Domicile — required.
- Financial Year End — required.
- Report Language — required, default English.
- Active / Archived status.

### 7.2 Investment content

- Investment Objective — required, long text.
- Strategy Highlights — required, repeatable, sortable bullet items.
- Performance Note — optional.
- Professional Investor Statement — inherited or overridden.

### 7.3 Parties and service providers

Use repeatable rows with a type, display label, value, and sort order. Support at least:

- Portfolio Manager.
- General Partner.
- Investment Manager.
- Fund Administrator.
- Auditor.
- Legal Adviser.
- Custodian / Prime Broker.

### 7.4 Fund terms

Use repeatable display rows rather than rigid numeric fields, because terms differ among funds. Support at least:

- Minimum Contribution.
- Valuation Frequency; MVP default is Monthly.
- Base Currency.
- Bloomberg Code.
- Year End Date.
- Management Fee.
- Carried Interest / Performance Fee.
- Lock-up Period.
- Redemption Terms.
- Subscription Terms.

Each row needs a display label, text value, display flag, and sort order.

### 7.5 Contacts

A fund may have multiple contacts:

- Role.
- Name.
- Email.
- Phone.
- Address.
- Display in Report.
- Sort Order.

### 7.6 Branding and legal content

- Fund logo override.
- Brand colour override.
- Header text override.
- Date statement override.
- Disclaimer override with version and effective date.
- Optional custom DOCX template override; the built-in template remains the fallback.

For custom templates, document the supported placeholders and validate required placeholders before accepting the template. A bad custom template must produce a clear validation error rather than a corrupted report.

## 8. Share classes / series

Performance is calculated at share-class or series level. One fund can have many share classes.

Fields:

- Parent fund.
- Class / Series Name — required.
- Class Code — required and unique within the fund.
- Inception Date — required.
- Inception NAV — required and greater than zero.
- Currency — required.
- Return Basis — required: Net or Gross.
- Management Fee override — optional.
- Performance Fee override — optional.
- Bloomberg Code override — optional.
- Active.
- Display in Quarterly Report.

MVP reports cover one share class per report. Structure the domain so a future multi-class report is possible.

## 9. Monthly NAV entry

The recurring input is NAV per Share, not total NAV and not shares outstanding.

Fields:

- Fund.
- Share Class / Series.
- Valuation Month.
- Valuation Date.
- NAV per Share.
- Status: Official or Indicative.
- Note.
- Optional raw/source date for legacy imports.

Rules:

1. NAV must be greater than zero.
2. Store at least 12 decimal places and never round the stored input to the report display precision.
3. One active NAV record per share class per valuation month.
4. `valuation_month` must be represented consistently, preferably the last calendar day of the month.
5. `valuation_date` records the actual valuation date.
6. Dates cannot precede the share-class inception date.
7. Monthly sequences must be continuous for any period used in final calculations.
8. If a month is missing, do not treat a two-month change as one monthly return.
9. Warn when the change from the prior month exceeds a configurable threshold, default ±25%; allow saving after explicit acknowledgement.
10. Editing a NAV used by a finalized report requires a reason, creates an audit record, and marks affected reports `Stale / Regeneration Required` without silently overwriting final files.

Provide:

- A fast single-month entry form.
- A table of historical NAV records.
- Edit with audit reason.
- CSV/XLSX bulk import with dry-run preview, validation, and explicit confirmation.
- A one-off legacy XSQ import management command based on the supplied workbook.

The application database is the source of truth after import. Never use Excel formulas as the runtime calculation engine.

## 10. Financial calculation engine

Create a dedicated, pure, well-tested calculation service. Do not place formulas in templates or views.

### 10.1 Numeric policy

- Store NAV and calculated raw values as `Decimal` or serialized high-precision decimals.
- Use a high Decimal context precision.
- Round only for display and document output.
- Use `ROUND_HALF_UP` for presentation unless the reference workbook proves another method.
- Use floats only where a library requires them, such as plotting, and never treat plot values as authoritative calculations.
- Every result must include a formula version, source NAV version/snapshot, calculation timestamp, and unrounded value.

Use this formula identifier for the first version:

```text
legacy_excel_v1
```

### 10.2 Monthly return

```text
R[t] = NAV[t] / NAV[t-1] - 1
```

For the first observed period, follow the legacy workbook:

```text
First Return = First NAV / Inception NAV - 1
```

The supplied workbook has an inception-date/first-NAV ambiguity. Preserve the raw imported date, normalize by valuation month, document the assumption, and keep the import mapping configurable rather than hiding it.

### 10.3 Quarterly return

```text
Quarterly Return = Quarter-End NAV / Previous Quarter-End NAV - 1
```

For the first partial quarter:

```text
First Partial-Quarter Return = First Quarter-End NAV / Inception NAV - 1
```

Build the full matrix dynamically by year with columns Q1, Q2, Q3, Q4, and YTD. Never use fixed row numbers.

### 10.4 YTD return

```text
YTD = Latest NAV / Previous Year-End NAV - 1
```

For the first calendar year where no prior year-end NAV exists:

```text
YTD = Latest NAV / Inception NAV - 1
```

### 10.5 ITD return

```text
ITD = Latest NAV / Inception NAV - 1
```

Do not hard-code an inception NAV of 100.

### 10.6 Annualized return — legacy Excel v1

```text
Annualized Return = PRODUCT(1 + Monthly Returns)^(12 / N) - 1
```

`N` is the number of valid monthly returns from inception through the report end. The calculation must fail validation when a month inside the range is missing.

### 10.7 Annualized volatility since inception — legacy Excel v1

```text
Monthly SD = sample standard deviation of all monthly returns
Annualized Volatility = Monthly SD × SQRT(12)
```

Use sample standard deviation with denominator `n - 1`.

### 10.8 Trailing 12-month volatility

```text
T12M Volatility = sample standard deviation of latest 12 continuous monthly returns × SQRT(12)
```

Show `N/A` if fewer than 12 continuous monthly returns exist.

### 10.9 Positive, negative, and zero months

```text
Positive % = Count(R > 0) / Count(all numeric monthly returns)
Negative % = Count(R < 0) / Count(all numeric monthly returns)
Zero %     = Count(R = 0) / Count(all numeric monthly returns)
```

The report follows Excel and normally displays Positive and Negative percentages. The internal review screen must also display Zero Months because positive plus negative can be less than 100%.

### 10.10 Maximum monthly gain and loss

```text
Maximum Monthly Gain = MAX(monthly returns)
Maximum Monthly Loss = MIN(monthly returns)
```

### 10.11 Maximum drawdown — intentional correction

Do not copy the workbook’s fixed-cell drawdown formula. Use the standard dynamic algorithm:

```text
Running Peak[t] = MAX(NAV[0..t])
Drawdown[t] = NAV[t] / Running Peak[t] - 1
Maximum Drawdown = MIN(Drawdown[t])
```

Label this in documentation as an intentional correction from the legacy workbook. Preserve the legacy workbook value in the reference analysis only; do not use it as the system’s `Maximum Drawdown` result.

### 10.12 Risk-free rate — legacy Excel v1

```text
RFR = arithmetic average of the latest 12 monthly end-of-period
      10-year U.S. Treasury observations through report end / 100
```

Store the percentage observations as published and convert to decimal only in calculations.

### 10.13 Sharpe ratio — legacy Excel v1

```text
Sharpe = (Annualized Return - Annual RFR) / Annualized Volatility Since Inception
```

This is intentionally the workbook method, not the more common monthly excess-return Sharpe. Show a warning in the internal calculation details and document it in `docs/formulas.md`. Do not put the warning in the client-facing newsletter unless configured.

### 10.14 Additional internal metric

Calculate a day-based CAGR for audit comparison only:

```text
Day-based CAGR = (Latest NAV / Inception NAV)^(365.25 / actual_days) - 1
```

Do not display it in the standard report by default.

## 11. Calculation output and validation screen

The performance review screen must show:

- Monthly NAV and monthly return table.
- Quarterly return matrix.
- Latest quarter return.
- YTD.
- ITD.
- Annualized return.
- Annualized volatility since inception.
- Trailing 12-month volatility.
- Positive, negative, and zero months.
- Maximum monthly gain and loss.
- Maximum drawdown.
- RFR value, provider, series, cutoff, and the 12 observations.
- Sharpe ratio.
- Day-based CAGR as internal comparison.
- NAV per Share chart.

For each important metric, provide an expandable calculation detail containing:

- Formula name/version.
- Inputs.
- Unrounded result.
- Display result.
- Data cutoff.
- Validation status.

Block finalization when:

- Any required monthly NAV is missing.
- The quarter-end NAV is absent.
- RFR observations do not align with the report end and no approved manual override exists.
- Required fund or share-class data is missing.
- Required commentary is empty.
- Document generation failed.

## 12. Online risk-free-rate integration

Implement a provider interface such as:

```python
class RiskFreeRateProvider(Protocol):
    def fetch_observations(self, start_date, end_date) -> list[Observation]: ...
```

Required providers:

1. `FRED_DGS10` — primary.
2. `TREASURY_CMT10` — official U.S. Treasury fallback.
3. `MANUAL` — controlled override.

### 12.1 FRED primary provider

Use the official FRED `DGS10` series. Support an environment variable:

```text
FRED_API_KEY=
```

Fetch enough daily or monthly data to obtain exactly the latest 12 monthly end-of-period observations through the report-end month. When using daily data, group by calendar month and choose the final non-null observation on or before month end.

Requirements:

- HTTP timeout.
- Limited retries with backoff.
- A descriptive User-Agent.
- No future observations.
- Parse missing values safely.
- Persist every observation used.
- Persist fetched timestamp, provider, series, and raw response SHA-256 checksum.
- Reuse valid cached observations before making another request.

### 12.2 Treasury fallback

Use the official U.S. Treasury Daily Treasury Par Yield Curve XML feed and extract the 10-year field. Handle pagination or month-specific queries as documented by Treasury. Normalize the output to the same observation model as FRED.

### 12.3 Manual override

A user may enter an annual decimal or percentage RFR only when the online source is unavailable or when reconciliation with a legacy report is required.

Manual override requires:

- Value.
- Reason.
- User.
- Timestamp.
- Report scope.

Display overrides prominently in the internal preview and audit log.

### 12.4 RFR commands and UI

Provide:

- A `fetch_rfr` management command.
- A `test_rfr_provider` management command.
- A button on the performance review page to refresh the RFR.
- A clear source and cutoff display.
- A scheduled-command example for cron.

Tests must mock network responses. The normal test suite must not depend on live internet access.

## 13. Manager Commentary

The quarterly report form must include:

- Commentary Title — optional.
- Manager Commentary — required.
- Author — default to the fund’s portfolio manager, editable.
- Commentary Date — default to report date.

Use a safe Markdown subset or structured editor supporting:

- Paragraphs.
- Bold.
- Italic.
- Bulleted lists.
- Numbered lists.

Do not store arbitrary unsanitized HTML. Provide an HTML preview and map the supported structures reliably into Word paragraphs and list styles. Commentary may span multiple pages.

## 14. Report lifecycle and versioning

Report identity:

- Fund.
- Share class.
- Calendar year.
- Quarter.
- Version.

Statuses:

```text
DRAFT
READY
FINAL
STALE
GENERATION_FAILED
```

Rules:

1. A draft may be regenerated.
2. Finalization creates or freezes an immutable report snapshot.
3. A finalized version cannot be silently overwritten.
4. Changes after finalization create a new version or mark the old report stale.
5. The snapshot must include:
   - Fund and share-class display data.
   - All NAV inputs used.
   - All calculated raw and display values.
   - Formula version.
   - RFR observations and provider.
   - Manager Commentary.
   - Disclaimer version and text.
   - Branding values.
   - Generation timestamps.
6. Save SHA-256 hashes of generated DOCX and PDF files.
7. Keep prior generated files available for download.

Use local persistent file storage for the MVP, mounted as a Docker volume. Encapsulate storage access so object storage can be added later.

## 15. Word report generation

Create a new clean built-in DOCX template. Do not reuse the reference document’s external chart relationship.

The report must contain:

1. Header/cover area:
   - Fund display name.
   - Share class when applicable.
   - Quarter label, for example `2026 Q1`.
   - Professional-investor statement.
   - `All data as on {report_date} unless stated otherwise` or the configured equivalent.
2. Investment Objective.
3. Strategy Highlights and Characteristics.
4. Fund Performance — Net Quarterly Returns table.
5. Performance note.
6. NAV per Share chart.
7. Fund Statistics.
8. Manager Commentary.
9. General Information.
10. Contacts.
11. Disclaimer.
12. Optional internal document metadata in custom properties or footer, including report version and generation timestamp.

Formatting requirements:

- Professional, restrained financial-report styling.
- Fund brand colour applied consistently.
- Sensible typography using fonts installed in the Docker image.
- Automatic pagination.
- Repeat table header rows across pages where relevant.
- Avoid splitting a short table row across pages.
- Commentary and disclaimer may flow naturally across pages.
- Negative returns displayed with a minus sign.
- Empty future quarters displayed as blank or an em dash consistently.
- Percentages default to two decimals.
- Positive/negative months default to zero decimals.
- Sharpe default to three decimals.
- Inception date formatted naturally.
- No stale chart cache or external workbook dependency.

The DOCX package must not contain any Excel relationship with `TargetMode="External"`.

Support optional fund-specific DOCX templates using documented `docxtpl` placeholders. The default template must always work even when no custom template is supplied.

## 16. Chart generation

Generate a high-resolution chart directly from database NAV records and embed it in the Word document.

Requirements:

- NAV per Share on the y-axis.
- Actual valuation months on the x-axis.
- Include inception NAV at inception where appropriate.
- Use readable quarterly or semi-annual ticks for long histories.
- Use the fund’s brand colour when configured.
- No external Excel link.
- Save a generated chart asset under the report’s versioned working directory.
- Use deterministic dimensions so Word and PDF remain stable.
- Close Matplotlib figures to avoid memory leaks.

The HTML preview should show the same underlying chart data.

## 17. PDF generation

Flow:

```text
DOCX → LibreOffice headless → PDF
```

Requirements:

- Run LibreOffice with a timeout.
- Use an isolated temporary user profile/work directory to prevent lock conflicts.
- Capture stdout/stderr.
- Fail with a useful message.
- Confirm output exists and is non-empty.
- Save the PDF hash.
- Ensure generated files are never written under a public static directory.
- Provide a Docker health/smoke command that generates a sample DOCX and PDF.

## 18. HTML user interface

Use the screenshot as design inspiration, not as a pixel-perfect target.

Visual direction:

- Clean white header.
- Horizontal numbered steps: Select Fund, Enter NAV, Review, Commentary, Preview, Generate.
- Blue primary actions.
- Pale teal selected cards/status.
- Light grey-blue background with subtle grid texture.
- Large centered content panel.
- Clear status badge at the upper right.
- Responsive for desktop and tablet.
- Accessible labels, keyboard focus states, error summaries, and sufficient contrast.

Required pages:

1. Login.
2. Fund dashboard with cards and statuses.
3. Create/edit fund.
4. Create/edit share class.
5. Monthly NAV entry and history.
6. Bulk NAV import preview.
7. Performance review.
8. Manager Commentary.
9. HTML report preview.
10. Generate/finalize/download.
11. Report history and versions.
12. Organization settings.
13. Audit log view.

Dashboard status examples:

```text
NAV Up to Date
Missing NAV
Commentary Required
Draft
Ready
Final
Stale
```

Keep application strings ready for Django internationalization. English is the initial complete UI language.

## 19. Suggested data model

Implement normalized models with migrations. The exact names may change, but all concepts below must exist.

### OrganizationSettings

- identity and branding defaults.
- legal/default report content.
- RFR defaults.
- formatting defaults.

### Fund

- identity.
- structure/domicile/year end.
- investment objective.
- report settings.
- inheritance/override fields.
- active status.

### FundStrategyHighlight

- fund.
- text.
- sort order.

### FundParty

- fund.
- party type.
- display label.
- value.
- sort order.

### FundTerm

- fund.
- key.
- display label.
- value text.
- display flag.
- sort order.

### Contact

- fund.
- role/name/email/phone/address.
- display flag.
- sort order.

### ShareClass

- fund.
- name/code.
- inception date/NAV.
- currency.
- return basis.
- overrides.
- active flags.

### NAVRecord

- share class.
- valuation month.
- valuation date.
- raw source date.
- NAV per share.
- official/indicative status.
- note.
- data version or revision number.
- created/updated by and timestamps.

Use a database constraint preventing duplicate active NAV records for one share class and valuation month.

### RFRObservation

- provider.
- series.
- observation date.
- value percent.
- fetched timestamp.
- raw checksum.

### RFRSnapshot or ReportRFRObservation

- report/version link.
- exact ordered observations used.
- annual averaged value.
- override metadata where applicable.

### QuarterlyReport

- fund/share class.
- year/quarter/version.
- report date.
- status.
- commentary fields.
- formula version.
- snapshot JSON.
- created/finalized timestamps and users.

### GeneratedFile

- report.
- file type.
- storage path.
- SHA-256.
- generated timestamp.
- size.

### AuditLog

- actor.
- entity type/id.
- action.
- before JSON.
- after JSON.
- reason.
- timestamp.

Use indexes on share class/month, report identity, status, and observation date.

## 20. Legacy XSQ import and demo data

Implement a safe legacy import utility for the supplied Excel workbook.

Requirements:

1. `--dry-run` is the default or available.
2. Show the proposed fund, share class, valuation month, raw date, NAV per share, and any warning.
3. Do not import return formulas as source data.
4. Import only one authoritative NAV per month.
5. Preserve raw workbook date and source sheet/cell where possible.
6. Detect duplicate months and missing months.
7. Require confirmation for ambiguous first-period mapping.
8. Be idempotent.
9. Generate a machine-readable import report.
10. Include a management command such as:

```text
python manage.py import_legacy_xsq --file reference/xsq_nav_history.xlsx --dry-run
```

Also provide an optional demo/seed command that creates the X Squared fund using content extracted from the supplied Word document and NAV history from the workbook. Fund-specific content belongs in seed data, not in reusable templates or calculation code.

## 21. Exact reference acceptance values

Create automated tests from the supplied workbook and formula audit.

For the 2026 Q1 sample:

```text
Previous year-end NAV = 92.25900603925423
Jan-2026 NAV           = 90.61700453137055
Feb-2026 NAV           = 90.70900308009685
Mar-2026 NAV           = 77.27900516437292
Inception NAV          = 100
```

Expected raw results, within a documented tight tolerance:

```text
2026 Q1 Return                    = -16.2368981826%
2026 YTD Return                   = -16.2368981826%
ITD Return                        ≈ -22.720995%
Annualized Return                 ≈ -6.642387%
Positive Months                   ≈ 37.777778%
Negative Months                   ≈ 62.222222%
Annualized Volatility             ≈ 53.920428%
Trailing 12-Month Volatility      ≈ 78.039608%
Legacy fixture RFR                ≈ 4.190858%
Sharpe with that fixture RFR      ≈ -0.200912
Standard Dynamic Maximum Drawdown ≈ -57.435305%
```

Expected report display:

```text
Q1 Return              -16.24%
YTD Return             -16.24%
ITD Return             -22.72%
Annualized Return       -6.64%
Positive Months         38%
Negative Months         62%
Annualized Volatility   53.92%
Sharpe Ratio            -0.201
```

The live FRED result can differ from the workbook’s Bloomberg-derived RFR, so use a deterministic fixture for the Sharpe regression test and separate mocked tests for online data retrieval.

## 22. Required automated tests

At minimum, implement tests for:

### Calculation tests

- Monthly returns.
- First-period return from inception NAV.
- Quarterly matrix across multiple years.
- First partial quarter.
- YTD and first-year YTD.
- ITD with non-100 inception NAV.
- Legacy annualized return.
- Sample standard deviation and annualized volatility.
- Trailing 12-month volatility.
- Positive, negative, and zero month percentages.
- Maximum gain/loss.
- Dynamic maximum drawdown.
- Legacy Sharpe formula.
- Display rounding.

### Validation tests

- Missing month blocks finalization.
- Duplicate month rejected.
- Non-positive NAV rejected.
- Quarter-end NAV missing.
- RFR cutoff later than report end rejected.
- Fewer than 12 RFR observations handled.
- Manual RFR override requires reason.
- Required commentary missing.
- Required fund fields missing.

### RFR tests

- FRED JSON/XML parsing with mocked responses.
- Treasury XML parsing with mocked responses.
- End-of-period selection.
- Null/missing observations.
- Cache reuse.
- No future data.
- Timeout/error handling.

### Report tests

- DOCX opens as a valid ZIP/package.
- Required headings/content are present.
- Quarterly table values are correct.
- Chart image is embedded.
- No Excel relationship has `TargetMode="External"`.
- Long commentary spans naturally without corrupting the document.
- Fund override content appears instead of organization default.
- Final snapshot remains unchanged after later fund metadata edits.
- Generated file hash is stored.
- PDF conversion integration test runs in Docker when LibreOffice is available.

### Web tests

- Anonymous users are redirected to login.
- Full workflow can create fund, class, NAVs, draft report, commentary, and generated output.
- Multiple funds/share classes remain isolated.
- Editing NAV used by a final report creates audit history and stale status.
- Files cannot be downloaded without authentication.

## 23. Security and operational requirements

- CSRF protection enabled.
- Secure cookies and proxy SSL settings controlled through environment variables.
- Configurable `ALLOWED_HOSTS` and `CSRF_TRUSTED_ORIGINS`.
- Validate uploaded file type, extension, MIME, and maximum size.
- Sanitize commentary input.
- Do not log secrets, passwords, full session cookies, or FRED API keys.
- PostgreSQL must not be exposed publicly in Docker Compose.
- Generated documents must be served through authenticated Django views or protected internal Nginx routing.
- Add sensible security headers.
- Add a session timeout setting.
- Add `/healthz` and `/readyz` endpoints.
- Log application events to stdout in a production-friendly format.
- Include a database backup script and restore instructions.
- Include a media/document backup note.
- Include a cleanup policy for temporary report-generation directories.

## 24. Docker and VPS deployment deliverables

Create:

- Production `Dockerfile` installing LibreOffice and required system fonts.
- `docker-compose.yml` with at least `web`, `db`, and `nginx`.
- Persistent volumes for PostgreSQL and generated media.
- Nginx configuration.
- Entrypoint/start scripts.
- `.env.example` with no real secrets.
- Database health checks.
- Django health checks.
- Static/media configuration.
- `README.md` with exact local and VPS commands.
- Optional Certbot or upstream-TLS instructions, but do not hard-code a domain.
- Backup and restore commands.

The app must run without a runtime CDN and without any paid API dependency. FRED and Treasury are public official data sources; manual override covers outages.

## 25. Developer experience

Provide:

- `pyproject.toml` with pinned compatible dependencies.
- Ruff configuration.
- Pytest configuration.
- `.gitignore`.
- `.dockerignore`.
- `.env.example`.
- Makefile or equivalent commands for setup, test, lint, migration, seed, and smoke test.
- A concise architecture document.
- A formulas document.
- An operations/deployment document.
- A report-template placeholder guide.
- Sample data command.

Recommended commands should be simple, for example:

```text
make setup
make migrate
make superuser
make seed-demo
make test
make lint
make up
make smoke-report
```

## 26. Implementation phases

Execute all phases rather than merely listing them.

### Phase 0 — Discovery

- Inspect files and repository.
- Create reference analysis, assumptions, and execution plan.

### Phase 1 — Project foundation

- Django project, settings, Docker, PostgreSQL, login, base templates, CSS, health endpoints.

### Phase 2 — Domain and audit models

- Organization, funds, share classes, NAV, RFR, reports, generated files, audit logs, migrations, admin support where safe.

### Phase 3 — Calculation engine

- Pure calculation services, validation, formula metadata, unit tests, XSQ regression fixture.

### Phase 4 — RFR integration

- Provider abstraction, FRED, Treasury fallback, cache, manual override, management commands, mocked tests.

### Phase 5 — Fund and NAV workflow UI

- Dashboard, fund wizard, share classes, monthly NAV entry/history, bulk import preview, validations.

### Phase 6 — Report workflow UI

- Performance review, commentary editor, HTML preview, report versions/statuses.

### Phase 7 — DOCX/PDF generation

- Default template, chart, Word output, no external links, LibreOffice conversion, hashes, versioned storage.

### Phase 8 — Legacy import and demo

- Workbook import command, seed content from Word reference, dry-run and idempotency.

### Phase 9 — Hardening

- Security, tests, linting, backups, deployment documentation, smoke test, final review.

## 27. Definition of done

The MVP is done only when all of the following are true:

1. A clean Docker Compose deployment starts on a VPS-like environment.
2. A user can log in.
3. A user can create more than one fund and more than one share class.
4. A user can enter monthly NAV per Share.
5. Missing months and duplicate months are caught.
6. The XSQ 2026 Q1 regression calculations match the expected legacy results, except for the intentionally corrected dynamic maximum drawdown.
7. The app can fetch and display official online RFR observations or use a controlled manual override.
8. A user can enter Manager Commentary.
9. The HTML preview includes all required newsletter sections.
10. The generated Word document is valid, professionally laid out, and has no external Excel links.
11. The generated PDF is non-empty and corresponds to the Word report.
12. Finalized reports are immutable and versioned.
13. NAV edits affecting a final report are audited and mark the report stale.
14. Files and downloads require authentication.
15. Critical tests pass and the actual results are reported.
16. README contains exact installation, first-user, FRED key, backup, restore, and upgrade instructions.

## 28. Final response required from Codex

After implementation, provide a concise engineering handover containing:

1. What was built.
2. Architecture summary.
3. Important files and directories.
4. Exact local startup commands.
5. Exact Docker/VPS startup commands.
6. How to create the first account.
7. How to configure the FRED API key.
8. How to import the supplied XSQ workbook.
9. How to generate the sample 2026 Q1 Word and PDF.
10. Test, lint, and smoke-test commands plus actual results.
11. Any remaining limitations or assumptions.
12. Security/deployment actions the VPS administrator must complete.

Begin now by inspecting the repository and reference files, then create `docs/EXEC_PLAN.md` and proceed through implementation. Do not stop after the plan.
