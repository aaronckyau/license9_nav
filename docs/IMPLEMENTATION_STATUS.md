# Implementation Status

## 2026-07-21 NAV 刪除與報告頁簡化（已發佈）

- 每月 NAV 表格新增可稽核的刪除按鈕；刪除後會使受影響報告進入需要重新產生的狀態。
- 報告期間表單選擇季報時，截止欄位會顯示為「截止季度」並限制為四個季度結束月份。
- 一般報告操作頁只顯示目前新建或選取的報告，避免歷史報告卡片堆疊。
- commit `50408a5` 已推送 GitHub `main` 並部署至 Contabo production。本機完整 suite 為 `52 passed, 1 skipped`（本機缺少 LibreOffice），Ruff、Django system check、migration check 均通過；VPS 容器健康、DOCX/PDF smoke 與公開 health/readiness 均通過。

## 2026-07-21 NAV 年度輸入流程修正（已發佈）

- 基金卡片改為單一入口：點選後直接進入「輸入每股 NAV」，不再顯示個別報告連結。
- NAV 頁只保留月份、每股 NAV、月度回報、累積回報與操作表格；年度摘要與趨勢圖不再顯示。
- 年度表格固定顯示 1 至 12 月；目前選取年度預設展開，過去年度預設收起。年度選單提供至系統年份的下一年。
- 使用者只輸入每股 NAV；月度及累積回報由系統於儲存後自動計算。所有未填寫月份（包括尚未結束月份與下一年度）都可直接輸入並儲存。
- commit `5762226` 已推送 GitHub `main` 並部署至 Contabo production。本機品質檢查為 `52 passed, 1 skipped`（本機缺少 LibreOffice），Ruff、Django system check、migration check 均通過；VPS 容器健康、DOCX/PDF smoke 與公開 health/readiness 均通過。

## 2026-07-21 報告品牌與頁尾更新

- XSQ 內建 DOCX 報告改用使用者提供的 Aureum Infinity 標誌；其他基金仍保留既有的基金／機構標誌設定。
- 移除報告中的 Calculation and provenance 文字，以及舊有的詳細費用結構附註。
- 頁尾統一只顯示動態頁碼（Page 1、Page 2 等）。
- 使用 Microsoft Word 唯讀 COM 匯出 PDF，完成四頁 XSQ 2026 Q2 報告的視覺驗證；此工具僅作本機 QA，正式環境仍使用容器內 LibreOffice。

最後更新：2026-07-21

## 狀態

MVP 已完成並部署至 Contabo Linux VPS 的 `https://www.4mstrategy.com/nav/`。Production PostgreSQL、Gunicorn、Nginx、LibreOffice、登入及報表 smoke 均已實際驗證。

2026-07-20 的三步月結版本已推送 GitHub 並部署至 production，使用者提供的 XSQ 2026 Q1 DOCX 作為新版報告設計依據。部署後已通過 Docker build、migration、LibreOffice DOCX/PDF smoke、公開 health/readiness 及 authenticated HTTPS 三步流程檢查。

2026-07-21 更新把「評論及產生報告」改為月報／季報期間選擇器；一般使用者每個期間只操作一份現行報告，不再看到版本或 NAV／報告進階連結。Production 官方 Treasury `BC_10YEAR` 連線及 2026-06-30 的 12 筆觀察值已重新實測成功。

2026-07-21 後續把年度 NAV 表改為直接輸入及修改：每筆 NAV 只顯示／接受小數點後兩位，使用者毋須另開編輯頁或填寫修改原因、估值月份、估值日期及狀態。系統保留原月份／日期／狀態，自動遞增修訂版次、建立 before/after audit，並把受影響的定稿報告標示為需重新產生。

## 已完成

- 自訂 authenticated 三步月結工作流與 Django Admin 分離；原有專業控制保留在進階入口。
- 多 fund/share class、NAV entry/edit/import、duplicate constraint、missing month 與 abnormal movement warning。
- `legacy_excel_v1` 全套績效、quarterly return table、NAV chart、Decimal/display rounding。
- FRED/U.S. Treasury 線上 RFR、cache/snapshot/cutoff、理由必填 manual override。
- Commentary/preview/versioning、DOCX/PDF、hash、外部 relationship audit、final immutability/staleness/audit。
- XSQ 45 筆 legacy workbook 匯入及 2026 Q1 真實樣本報表。
- Dockerfile、Compose、Nginx、entrypoint、health checks、backup/restore、CI 與完整文件。
- 51 passed、1 個因本機無 LibreOffice 而 skip；最新 NAV 年度儀表板另完成 1440、1024、390、360 四視窗實際驗證，無水平溢出。
- GitHub `main`、VPS `/root/apps/license9_nav`、subpath `/nav` 與 loopback port `5430` 已部署。
- VPS Docker image build、三個 healthy containers、migration、`check --deploy`、LibreOffice DOCX/PDF smoke 與 public login/logout 已通過。
- 一般使用者網站已完整繁體中文化，包括登入、導覽、三步工作流程、表單、狀態、驗證訊息、績效檢視、RFR、評論、預覽、報告歷史及稽核頁；專有名詞及基金資料保留原文。
- NAV 頁按年份列出既有月份，每月均可在同一表格輸入或修改兩位小數 NAV；只開放最早缺少月份作新增，阻止跳月／重複 NAV，並保留異常變動的第二次確認。
- 基金經理評論已移到「評論及產生報告」頁，每個報告期間使用自己的評論欄，一次提交便儲存評論並產生報告。
- 產生報告時自動更新官方 RFR；已有具理由的人工 RFR 時不覆寫。產生完成後返回報告紀錄並直接提供下載。
- 中文版 1440×1000、1024×900、390×844 共 30 頁面／viewport inspections，無水平溢出、殘留的核心英文操作標籤或舊術語「管理員評論」。

本次按年份 NAV／報告頁評論 UX 已以 commit `0cde04b` 推送至 GitHub `main` 並部署至 production。部署後重新通過 migration check、三個容器 healthcheck、公開 health/readiness，以及一次性 QA 帳號的登入、基金首頁、NAV 輸入頁與報告評論頁檢查；QA 帳號已於檢查後刪除。

2026-07-20 後續修正讓 NAV 已追到最近完成月份時仍保留完整年份／月份清單；當時使用獨立編輯入口。該入口已於 2026-07-21 被同表格直接修改流程取代。

## 外部驗證限制

- 本機 Docker engine 仍因外部 Windows/WSL 問題無法使用；未修改主機設定。相同 image/build/runtime 已在 Contabo Ubuntu VPS 實際通過，因此不再阻礙 repository completion。
- 本機無 LibreOffice，真實 LibreOffice pytest integration skip；VPS production image 的 LibreOffice DOCX→PDF smoke 已通過。
- 本機 PDF 以可用 Word COM 唯讀匯出供視覺 QA，非 production dependency。

## 年度 NAV 儀表板（2026-07-20）

- 已把登入後的 NAV 輸入／歷史頁重整為按年份排列的專業基金管理儀表板；保留既有新增月份、編輯 NAV、異常變動確認、報告入口及稽核流程。
- 每個年度顯示最新 NAV、FY／YTD／期間回報、年度最高及最低 NAV、月回報、累積回報，以及由伺服器產生的內嵌折線圖。
- 權威顯示計算使用 `Decimal`；NAV 顯示及一般輸入統一為 2 位小數，百分比顯示正負號及 2 位小數。上一年度 12 月基準缺少時會使用當年首筆 NAV 並明確提示，首筆回報維持「—」。
- 圖表由 authenticated、`private, no-store` 的 PNG endpoint 即時提供；桌面及手機分別使用橫向／直向版面，不依賴前端 JavaScript 或公共 CDN。
- 響應式版面已於 1440×1000、1024×900、390×844、360×800 實際檢查：無水平溢位，390px 顯示 2 欄摘要，360px 顯示 1 欄摘要，月資料轉為可讀卡片，編輯目標至少 44px。
- 年度 NAV 儀表板功能 commits `75d32fb`、`ef04eef` 已推送至 GitHub `main` 並部署至 production。VPS image build、migration、三個容器 healthcheck、Django deployment check、LibreOffice DOCX/PDF smoke、公開 health/readiness、未登入保護及一次性帳號 authenticated smoke 均通過；一次性帳號已刪除，未修改 NAV 資料。
