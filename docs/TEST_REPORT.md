# Test Report

日期：2026-07-20；環境：Windows Python 3.12/SQLite/Edge headless/Word COM 唯讀 QA，加上 Contabo Ubuntu/PostgreSQL 17/Docker/LibreOffice production smoke。

## 自動化結果

```text
ruff check .                                      PASS
ruff format --check .                             PASS (38 files)
python manage.py check                            PASS (0 issues)
python manage.py makemigrations --check --dry-run PASS (No changes detected)
python manage.py migrate --check                  PASS
python manage.py check --deploy                   PASS (exit 0; W005/W021 intentionally retained)
pytest -q                                         PASS: 44 passed, 1 skipped
docker compose --env-file .env.example config --quiet PASS
VPS docker compose build/up + all healthchecks    PASS
VPS /app/scripts/smoke_report.sh                  PASS (DOCX + LibreOffice PDF)
Public /nav authenticated three-step workflow    PASS
Public /nav login/logout/static/health/readiness PASS
```

唯一 skip：`tests/test_reports.py::test_real_libreoffice_pdf_conversion`，原因是本 Windows 主機沒有 `soffice`。VPS 的 production image 已另以相同 report pipeline 及真實 LibreOffice smoke 通過。

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
| PDF | PASS | Word COM local visual PASS；VPS LibreOffice production smoke PASS |
| prior versions/download | PASS | report history/download tests + screenshots |
| finalized immutability/staleness | PASS | model/service/web lifecycle tests |

## Browser visual QA

`scripts/visual_qa.cjs` 以 Edge 執行 1440×1000、1024×900、390×844。結果：36 screenshots、30 inspections、0 horizontal overflow、0 escaped controls、0 console error、0 page error。JSON：`artifacts/visual-qa/visual-qa-results.json`；三張 contact sheets 與全部頁面截圖同目錄。

最新三步流程以真實 Edge 重新檢查 11 個主要頁面 × 1440、1024、390 三個 viewport，加上登入／登出，共 39 張截圖及 33 次頁面 inspection；0 horizontal overflow、0 escaped control、0 console error、0 page error。結果：`artifacts/simple-workflow-qa/full-suite/visual-qa-results.json`。三個 `simple-entry-*.png` 已逐張檢查；首次檢查發現桌面送出列遮擋評論欄，修正後重跑全套通過。

2026-07-20 最新 UX 增量另以 in-app Edge 驗證按年份 NAV 頁及報告評論卡：1440×1000、1024×900、390×844 均無水平溢出。實際瀏覽器操作成功新增 2025 年 4 月 NAV `151.250000` 並開放 5 月，也成功在指定 report/version 儲存評論後進入產生流程。8 張有效截圖位於 `artifacts/visual-qa-zh/workflow-v2-*.png`。

功能 commit `0cde04b` 部署後，再由公開 HTTPS 入口以一次性 QA 帳號驗證登入、基金首頁、`/nav/classes/1/entry/` 與 `/nav/reports/`；頁面均顯示新版繁體中文工作流，一次性帳號隨即刪除，未寫入基金、NAV 或報告資料。

「NAV 已是最新」狀態另加入 regression test，確認年份／月份、六位小數 NAV 及每筆編輯 URL 仍顯示。以本機真實 XSQ 資料在 1440×1000 與 390×844 驗證 48 個編輯入口：兩個 viewport 均無水平溢出、console error 為 0；既有月份編輯頁可載入原值及稽核原因欄。

功能 commit `f35ae2b` 部署後，再由公開 HTTPS 入口確認最新 NAV 頁顯示 48 個編輯 URL，並成功只讀載入既有 NAV 的編輯表單、原值及稽核原因欄；production CSS、health/readiness 與三個容器 healthcheck 均通過，一次性 QA 帳號隨即刪除。

## XSQ report QA

- `artifacts/sample-reports/XSQ_2026_Q1_Quarterly_Report.docx`：169009 bytes，SHA-256 `a0197b2eec664ecfeaa15f8c2aa12f9019f219c22d9567307f6f3929d8c36941`。
- `artifacts/sample-reports/XSQ_2026_Q1_Quarterly_Report.pdf`：252225 bytes，4 頁 A4；本機以 Word/WPS 相容 COM 唯讀匯出供視覺 QA。
- DOCX audit：valid；2 embedded media；0 external/excel relationship；0 embedded spreadsheet；0 missing target；0 fixed row height。
- `artifacts/report-render/XSQ_2026_Q1_page-1.png` 至 `page-4.png`：依使用者提供的 2026 Q1 DOCX 章節結構逐頁檢查通過；負百分比、三位 Sharpe precision、表格、內嵌圖表、評論、免責聲明及頁尾均正常。
- 18 段 long-commentary fixture：6 頁 A4；評論自然跨頁，署名不孤立，information/disclaimer 新頁、footer 一致。
- VPS production artifact：`/app/media/reports/1/v1/quarterly-report.docx` 與 `.pdf`；DOCX ZIP 完整、2 embedded media、0 external relationship；LibreOffice PDF 為 4 頁 A4、PDF 1.6。
- 公開 smoke：`/nav`→`/nav/`、未登入 workflow→`/nav/accounts/login/`、login/logout、CSS、`healthz`、`readyz` 全部通過；一次性 QA 帳號驗證首頁三步、輸入頁 2026 年 6 月預設值及產生報告頁後已刪除；已停用四個舊入口回傳 404。

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

## 年度 NAV 儀表板驗證（2026-07-20）

- `tests/test_imports_models_web.py`：覆蓋上一年度 12 月基準、無基準 fallback、首筆「—」、缺月不誤標單月回報、待輸入月份排序、正負月回報／累積回報、FY／YTD、6 位 NAV、12 個月份、全部編輯 URL、目標頁及圖表登入保護、404、no-store 及原有編輯表單。
- 實際 XSQ 本機資料：5 個年度、48 個 NAV 編輯入口及 5 張年度圖表均成功載入；瀏覽器主控台 error 為 0。
- 1440×1000：摘要／圖表約 32%／68%，六欄表格完整，無水平溢位。
- 1024×900：摘要改為 2×2，圖表及表格垂直排列，無水平溢位。
- 390×844：摘要 2 欄，月份轉為卡片，編輯按鈕 96×44px，手機圖表完整載入，無水平溢位。
- 360×800：摘要 1 欄，月份卡片及 44px 編輯目標完整，無水平溢位。
- 另以超長基金／股份類別名稱做臨時本機資料 QA，360px 可自然換行且無水平溢位；驗證後依正確關聯順序刪除臨時資料，未修改正式 XSQ NAV。
- 視覺證據位於 `artifacts/visual-qa-zh/nav-dashboard-*.png`。
