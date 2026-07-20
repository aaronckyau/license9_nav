# Test Report

日期：2026-07-18；環境：Windows、本機 Python 3.12/SQLite、Edge headless、Word COM 相容匯出；production target 為 Linux/PostgreSQL/LibreOffice。

## 自動化結果

```text
ruff check .                                      PASS
ruff format --check .                             PASS (38 files)
python manage.py check                            PASS (0 issues)
python manage.py makemigrations --check --dry-run PASS (No changes detected)
python manage.py migrate --check                  PASS
python manage.py check --deploy                   PASS (secure production env)
pytest -q                                         PASS: 32 passed, 1 skipped
docker compose --env-file .env.example config --quiet PASS
```

唯一 skip：`tests/test_reports.py::test_real_libreoffice_pdf_conversion`，原因是本 Windows 主機沒有 `soffice`。相同 test 會在 Ubuntu CI 安裝 LibreOffice 後執行。

## Workflow coverage

| 工作流 | 結果 | 主要證據 |
|---|---|---|
| login/logout/dashboard | PASS | Playwright 三視窗 + web tests |
| create/edit fund | PASS | web tests + fund setup screenshots |
| multiple share classes/series | PASS | model/web tests + dashboard isolation |
| monthly NAV create/edit | PASS | full workflow web test |
| duplicate NAV | PASS | DB constraint + duplicate POST form-error test |
| missing valuation months | PASS | calculation/import validation tests |
| abnormal NAV warning/acknowledgement | PASS | form/workflow tests |
| online RFR fetch/store | PASS | Treasury live command + mocked providers |
| justified manual RFR | PASS | validation/workflow tests |
| `legacy_excel_v1` metrics | PASS | XSQ Decimal regression tests |
| quarterly table/NAV chart | PASS | calculation, chart tests, browser/report render |
| commentary create/edit | PASS | full workflow + browser page |
| preview | PASS | HTML sections test + screenshots |
| DOCX | PASS | unit/integration package tests + real XSQ artifact |
| PDF | PASS/PARTIAL | Word COM visual PASS; local LibreOffice unavailable |
| prior versions/download | PASS | report history/download tests + screenshots |
| finalized immutability/staleness | PASS | model/service/web lifecycle tests |

## Browser visual QA

`scripts/visual_qa.cjs` 以 Edge 執行 1440×1000、1024×900、390×844。結果：36 screenshots、30 inspections、0 horizontal overflow、0 escaped controls、0 console error、0 page error。JSON：`artifacts/visual-qa/visual-qa-results.json`；三張 contact sheets 與全部頁面截圖同目錄。

## XSQ report QA

- `artifacts/sample-reports/XSQ_2026_Q1_Quarterly_Report.docx`：169030 bytes，SHA-256 記錄於 audit JSON。
- `artifacts/sample-reports/XSQ_2026_Q1_Quarterly_Report.pdf`：253634 bytes，4 頁 A4。
- DOCX audit：valid；2 embedded media；0 external/excel relationship；0 embedded spreadsheet；0 missing target；0 fixed row height。
- `artifacts/report-render/XSQ_2026_Q1_page-1.png` 至 `page-4.png`：逐頁檢查通過。
- 18 段 long-commentary fixture：6 頁 A4；評論自然跨頁，署名不孤立，information/disclaimer 新頁、footer 一致。

## 實際命令

```powershell
.\.venv\Scripts\ruff.exe check .
.\.venv\Scripts\ruff.exe format --check .
.\.venv\Scripts\python.exe manage.py check
.\.venv\Scripts\python.exe manage.py makemigrations --check --dry-run
.\.venv\Scripts\python.exe manage.py migrate --check
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe manage.py test_rfr_provider --provider TREASURY_CMT10 --report-end 2025-03-31
.\.venv\Scripts\python.exe manage.py fetch_rfr --report-id 3 --provider TREASURY_CMT10
.\.venv\Scripts\python.exe scripts\inspect_docx.py artifacts\sample-reports\XSQ_2026_Q1_Quarterly_Report.docx --output artifacts\sample-reports\XSQ_2026_Q1_DOCX_Audit.json
docker compose --env-file .env.example config --quiet
```

Playwright 使用 bundled Node、`NODE_PATH` 與 Edge executable，`QA_BASE_URL=http://127.0.0.1:8018`；密碼每次以 GUID 輪替，未保存或交付預設 credential。
