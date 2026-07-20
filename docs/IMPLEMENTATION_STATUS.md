# Implementation Status

最後更新：2026-07-20

## 狀態

MVP 已完成並部署至 Contabo Linux VPS 的 `https://www.4mstrategy.com/nav/`。Production PostgreSQL、Gunicorn、Nginx、LibreOffice、登入及報表 smoke 均已實際驗證。

## 已完成

- 自訂 authenticated 0–6 步驟工作流與 Django Admin 分離。
- 多 fund/share class、NAV entry/edit/import、duplicate constraint、missing month 與 abnormal movement warning。
- `legacy_excel_v1` 全套績效、quarterly return table、NAV chart、Decimal/display rounding。
- FRED/U.S. Treasury 線上 RFR、cache/snapshot/cutoff、理由必填 manual override。
- Commentary/preview/versioning、DOCX/PDF、hash、外部 relationship audit、final immutability/staleness/audit。
- XSQ 45 筆 legacy workbook 匯入及 2026 Q1 真實樣本報表。
- Dockerfile、Compose、Nginx、entrypoint、health checks、backup/restore、CI 與完整文件。
- 35 passed、1 個因本機無 LibreOffice 而 skip；繁中介面三視窗 32 張 screenshots／30 次 inspections／0 failures。
- GitHub `main`、VPS `/root/apps/license9_nav`、subpath `/nav` 與 loopback port `5430` 已部署。
- VPS Docker image build、三個 healthy containers、migration、`check --deploy`、LibreOffice DOCX/PDF smoke 與 public login/logout 已通過。
- 一般使用者網站已完整繁體中文化，包括登入、導覽、七步工作流程、表單、狀態、驗證訊息、績效檢視、RFR、評論、預覽、報告歷史及稽核頁；專有名詞及基金資料保留原文。
- 中文版 1440×1000、1024×900、390×844 共 30 頁面／viewport inspections，無水平溢出、殘留的核心英文操作標籤或舊術語「管理員評論」。

## 外部驗證限制

- 本機 Docker engine 仍因外部 Windows/WSL 問題無法使用；未修改主機設定。相同 image/build/runtime 已在 Contabo Ubuntu VPS 實際通過，因此不再阻礙 repository completion。
- 本機無 LibreOffice，真實 LibreOffice pytest integration skip；VPS production image 的 LibreOffice DOCX→PDF smoke 已通過。
- 本機 PDF 以可用 Word COM 唯讀匯出供視覺 QA，非 production dependency。
