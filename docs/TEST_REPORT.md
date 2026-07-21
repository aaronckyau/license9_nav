# Test Report

日期：2026-07-21；環境：Windows Python 3.12/SQLite/in-app browser/Word DOCX 結構 QA，加上既有 Contabo Ubuntu/PostgreSQL 17/Docker/LibreOffice production smoke。

## 自動化結果

```text
ruff check .                                      PASS
ruff format --check .                             PASS (38 files)
python manage.py check                            PASS (0 issues)
python manage.py makemigrations --check --dry-run PASS (No changes detected)
python manage.py migrate --check                  PASS
python manage.py check --deploy                   PASS (exit 0; W005/W021 intentionally retained)
pytest -q                                         PASS: 51 passed, 1 skipped
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

2026-07-21 月報／季報選擇器增量以真實瀏覽器操作驗證：成功建立 XSQ 2026 年 6 月月報、儲存評論並執行官方 RFR／計算／DOCX 路徑；`TREASURY_CMT10 / BC_10YEAR` 保存 12 筆截至 2026-06-30 的觀察值。1440×1000、1024×900、390×844 均無水平溢出或 console error，截圖為 `artifacts/visual-qa/report-history-{desktop-1440,tablet-1024,mobile-390}.png`。頁面不再顯示版本、「輸入下一個 NAV 月份」、「進階」、「修正現有 NAV」或「報告檢查」。本機 PDF 因沒有 LibreOffice 按預期失敗，但已產生的 Word 仍可下載；DOCX audit 位於 `artifacts/visual-qa/monthly-report-docx-audit.json`，結果 valid、2 embedded media、0 external relationship、0 embedded spreadsheet、0 fixed row height。

`scripts/visual_qa.cjs` 以 Edge 執行 1440×1000、1024×900、390×844。結果：36 screenshots、30 inspections、0 horizontal overflow、0 escaped controls、0 console error、0 page error。JSON：`artifacts/visual-qa/visual-qa-results.json`；三張 contact sheets 與全部頁面截圖同目錄。

最新三步流程以真實 Edge 重新檢查 11 個主要頁面 × 1440、1024、390 三個 viewport，加上登入／登出，共 39 張截圖及 33 次頁面 inspection；0 horizontal overflow、0 escaped control、0 console error、0 page error。結果：`artifacts/simple-workflow-qa/full-suite/visual-qa-results.json`。三個 `simple-entry-*.png` 已逐張檢查；首次檢查發現桌面送出列遮擋評論欄，修正後重跑全套通過。

2026-07-20 最新 UX 增量另以 in-app Edge 驗證按年份 NAV 頁及報告評論卡：1440×1000、1024×900、390×844 均無水平溢出。實際瀏覽器操作成功新增 2025 年 4 月 NAV `151.250000` 並開放 5 月，也成功在指定 report/version 儲存評論後進入產生流程。8 張有效截圖位於 `artifacts/visual-qa-zh/workflow-v2-*.png`。

功能 commit `0cde04b` 部署後，再由公開 HTTPS 入口以一次性 QA 帳號驗證登入、基金首頁、`/nav/classes/1/entry/` 與 `/nav/reports/`；頁面均顯示新版繁體中文工作流，一次性帳號隨即刪除，未寫入基金、NAV 或報告資料。

「NAV 已是最新」狀態最初曾驗證六位小數及獨立編輯入口；該歷史行為已由 2026-07-21 的兩位小數表內修改流程取代，最新證據見下方「年度 NAV 表內修改及兩位小數」。

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

- `tests/test_imports_models_web.py`：覆蓋上一年度 12 月基準、無基準 fallback、首筆「—」、缺月不誤標單月回報、待輸入月份排序、正負月回報／累積回報、FY／YTD、2 位 NAV、12 個月份、表內儲存、no-op、舊路徑 405／redirect、圖表登入保護、404 及 no-store。
- 實際 XSQ 本機資料：5 個年度、48 個 NAV 編輯入口及 5 張年度圖表均成功載入；瀏覽器主控台 error 為 0。
- 1440×1000：摘要／圖表約 32%／68%，六欄表格完整，無水平溢位。
- 1024×900：摘要改為 2×2，圖表及表格垂直排列，無水平溢位。
- 390×844：摘要 2 欄，月份轉為卡片，編輯按鈕 96×44px，手機圖表完整載入，無水平溢位。
- 360×800：摘要 1 欄，月份卡片及 44px 編輯目標完整，無水平溢位。
- 另以超長基金／股份類別名稱做臨時本機資料 QA，360px 可自然換行且無水平溢位；驗證後依正確關聯順序刪除臨時資料，未修改正式 XSQ NAV。
- 視覺證據位於 `artifacts/visual-qa-zh/nav-dashboard-*.png`。

## 年度 NAV 表內修改及兩位小數（2026-07-21）

- 新增及修改表單均只接受正數及小數點後最多兩位；三位小數 POST 回傳表單錯誤且資料庫不變。
- 既有月份在年度表內直接修改，頁面不再輸出 `nav-edit` URL、修改原因、估值日期、狀態或「修正 NAV 歷史紀錄」。
- 表內修改保留原 valuation month/date/status，自動遞增 revision、建立 `AuditLog UPDATE` 及固定系統理由；受影響 FINAL 報告仍轉為 `STALE`，原 snapshot/file 保持不變。
- 權威計算仍使用底層 `Decimal` 精度；年度表、首頁、月報 HTML 預覽、檢查頁及內建月報 DOCX 的 NAV 顯示統一為兩位小數。
- 舊 `/nav/new/` 及 `/nav/<id>/edit/` 路徑保留相容 redirect，只導回年度 NAV 表，不再提供獨立表單。
- 舊路徑只接受 GET redirect；舊表單 POST 明確回覆 HTTP 405，避免看似成功但未儲存。相同數值的表內 POST 顯示「沒有變更」，不增 revision、不建 audit、亦不把報告標示過期。
- NAV 真正變更時，受影響 FINAL 報告維持不可變並轉為 STALE；受影響的未定稿報告會回到 DRAFT、清除舊 snapshot/error/GeneratedFile 及檔案，避免下載過時成果。
- 本機真實 XSQ 資料的 in-app browser QA：1440×1000、1024×900、390×844 三個 viewport 的 `documentElement.scrollWidth` 均小於 viewport；0 console warning/error。頁面有 48 個兩位小數輸入欄及 48 個同列儲存按鈕、0 個 edit link，且不含「修改原因／估值日期／狀態／修正 NAV 歷史紀錄」。390px 手機版輸入寬 165.75px，儲存按鈕 303×44px。
- 實際互動使用本機 Browser QA 基金把 2025 年 4 月 NAV `151.25 → 151.26`，收到「NAV 已更新。」後再還原為 `151.25`；XSQ NAV 未被修改。暫時 QA 帳戶已刪除。
- 視覺證據：`artifacts/visual-qa/nav-inline-desktop-1440.png`、`nav-inline-tablet-1024.png`、`nav-inline-mobile-390.png`、`nav-inline-mobile-390-table.png`、`nav-inline-mobile-390-action.png`。

## 年度 NAV 儀表板 production 部署驗證（2026-07-20）

- GitHub `main` 及 VPS runtime source 均部署功能 SHA `ef04eef`；部署前 DB/media backup timestamp 為 `20260720T081838Z`。
- `docker compose --env-file .env config --quiet`、web image build、entrypoint migration／collectstatic、三個容器 healthcheck 及 `manage.py migrate --check` 通過。
- `manage.py check --deploy` exit 0；只保留文件已記錄的 HSTS `includeSubDomains`／`preload` W005、W021 警告。
- Production LibreOffice smoke 通過，產生 XSQ 2026 Q1 DOCX/PDF；legacy import 為 `created=0 skipped=45`，沒有重複 NAV。
- 公開 `https://www.4mstrategy.com/nav/healthz`、`readyz` 回傳 200；登入頁回傳 200；未登入年度頁及圖表均正確 302 至 `/nav/accounts/login/`。
- 一次性帳號經公開 HTTPS 登入後，年度頁回傳 200，顯示 5 個年度卡、5 個月度表、5 張圖表與 48 個編輯入口；2025 圖表回傳 200 `image/png`。QA 帳號查詢結果為 0。
- 啟動後日誌無 traceback 或持續 5xx；容器切換瞬間曾有一次內部 Nginx health probe 502，下一次 probe 即恢復 200，公開驗證全程正常。
