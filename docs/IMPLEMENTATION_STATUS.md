# Implementation Status

最後更新：2026-07-20

## 狀態

MVP 已完成並部署至 Contabo Linux VPS 的 `https://www.4mstrategy.com/nav/`。Production PostgreSQL、Gunicorn、Nginx、LibreOffice、登入及報表 smoke 均已實際驗證。

2026-07-20 的三步月結版本已推送 GitHub 並部署至 production，使用者提供的 XSQ 2026 Q1 DOCX 作為新版報告設計依據。部署後已通過 Docker build、migration、LibreOffice DOCX/PDF smoke、公開 health/readiness 及 authenticated HTTPS 三步流程檢查。

## 已完成

- 自訂 authenticated 三步月結工作流與 Django Admin 分離；原有專業控制保留在進階入口。
- 多 fund/share class、NAV entry/edit/import、duplicate constraint、missing month 與 abnormal movement warning。
- `legacy_excel_v1` 全套績效、quarterly return table、NAV chart、Decimal/display rounding。
- FRED/U.S. Treasury 線上 RFR、cache/snapshot/cutoff、理由必填 manual override。
- Commentary/preview/versioning、DOCX/PDF、hash、外部 relationship audit、final immutability/staleness/audit。
- XSQ 45 筆 legacy workbook 匯入及 2026 Q1 真實樣本報表。
- Dockerfile、Compose、Nginx、entrypoint、health checks、backup/restore、CI 與完整文件。
- 41 passed、1 個因本機無 LibreOffice 而 skip；最新 NAV／報告評論介面另完成 1440、1024、390 三視窗與實際提交驗證，無水平溢出。
- GitHub `main`、VPS `/root/apps/license9_nav`、subpath `/nav` 與 loopback port `5430` 已部署。
- VPS Docker image build、三個 healthy containers、migration、`check --deploy`、LibreOffice DOCX/PDF smoke 與 public login/logout 已通過。
- 一般使用者網站已完整繁體中文化，包括登入、導覽、三步工作流程、表單、狀態、驗證訊息、績效檢視、RFR、評論、預覽、報告歷史及稽核頁；專有名詞及基金資料保留原文。
- NAV 頁按年份列出既有月份，只開放最早缺少的月份輸入，儲存後立即前進下一個月份；阻止跳月／重複 NAV，並保留異常變動的第二次確認。
- 基金經理評論已移到「評論及產生報告」頁，每個 report/version 使用自己的評論欄，一次提交便儲存評論並產生報告。
- 產生報告時自動更新官方 RFR；已有具理由的人工 RFR 時不覆寫。產生完成後返回報告紀錄並直接提供下載。
- 中文版 1440×1000、1024×900、390×844 共 30 頁面／viewport inspections，無水平溢出、殘留的核心英文操作標籤或舊術語「管理員評論」。

本次按年份 NAV／報告頁評論 UX 已以 commit `0cde04b` 推送至 GitHub `main` 並部署至 production。部署後重新通過 migration check、三個容器 healthcheck、公開 health/readiness，以及一次性 QA 帳號的登入、基金首頁、NAV 輸入頁與報告評論頁檢查；QA 帳號已於檢查後刪除。

2026-07-20 後續修正讓 NAV 已追到最近完成月份時仍保留完整年份／月份清單，每個既有月份均顯示 NAV 及「編輯」入口；功能 commit `f35ae2b` 已推送並部署。本機 1440×1000、390×844 瀏覽器檢查及完整測試通過，production 亦以一次性 QA 帳號確認 48 個編輯入口及既有 NAV 編輯表單；帳號已刪除且未修改 NAV 資料。

## 外部驗證限制

- 本機 Docker engine 仍因外部 Windows/WSL 問題無法使用；未修改主機設定。相同 image/build/runtime 已在 Contabo Ubuntu VPS 實際通過，因此不再阻礙 repository completion。
- 本機無 LibreOffice，真實 LibreOffice pytest integration skip；VPS production image 的 LibreOffice DOCX→PDF smoke 已通過。
- 本機 PDF 以可用 Word COM 唯讀匯出供視覺 QA，非 production dependency。
