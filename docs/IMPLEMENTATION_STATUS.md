# Implementation Status

最後更新：2026-07-18

## 狀態

MVP 實作與可在本機執行的驗證已完成，可交接至 Linux CI/VPS 做 container build/smoke。

## 已完成

- 自訂 authenticated 0–6 步驟工作流與 Django Admin 分離。
- 多 fund/share class、NAV entry/edit/import、duplicate constraint、missing month 與 abnormal movement warning。
- `legacy_excel_v1` 全套績效、quarterly return table、NAV chart、Decimal/display rounding。
- FRED/U.S. Treasury 線上 RFR、cache/snapshot/cutoff、理由必填 manual override。
- Commentary/preview/versioning、DOCX/PDF、hash、外部 relationship audit、final immutability/staleness/audit。
- XSQ 45 筆 legacy workbook 匯入及 2026 Q1 真實樣本報表。
- Dockerfile、Compose、Nginx、entrypoint、health checks、backup/restore、CI 與完整文件。
- 32 passed、1 個因本機無 LibreOffice 而 skip；三視窗 36 screenshots/30 inspections/0 failures。

## 外部驗證限制

- 本機 Docker engine 無法使用，未執行 image build/container smoke；`docker compose config --quiet` 已通過。
- 本機無 LibreOffice，真實 LibreOffice pytest integration skip；Ubuntu CI 與 production image 會安裝並執行。
- 本機 PDF 以可用 Word COM 唯讀匯出供視覺 QA，非 production dependency。
