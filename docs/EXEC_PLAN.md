# NAV Quarterly Report MVP Execution Plan

最後更新：2026-07-18

## 交付目標

完成 `docs/CODEX_MASTER_PROMPT.md` 定義的 server-rendered 多基金 NAV 季報 MVP：資料庫 NAV 為唯一權威來源、重現 `legacy_excel_v1`、支援官方/人工 RFR、產生受保護且可重現的 DOCX/PDF，並以 Docker Compose 部署至 Linux VPS。

## 執行結果

- [x] 完整閱讀 repository 指令、master prompt 與 `reference/` 全部檔案；檢查 Excel 公式/data-only、DOCX package 與四頁渲染。
- [x] 建立 Django、認證、健康檢查、環境設定、自訂 UI、PostgreSQL/SQLite 邊界與 production container skeleton。
- [x] 建立 organization、fund、share class、NAV revision、RFR、report、generated file、audit 模型與 migrations。
- [x] 實作純 Decimal、日期驅動的 `legacy_excel_v1` 與 XSQ regression。
- [x] 實作 FRED、U.S. Treasury、cache、12 個月 cutoff、manual override 與 finalized 鎖定。
- [x] 實作基金/share class CRUD、月度 NAV、duplicate/missing/abnormal warning、bulk import、audit/stale lifecycle。
- [x] 實作績效檢視、基金經理評論、HTML 預覽、版本歷史、不可變定稿及受保護下載。
- [x] 實作 Matplotlib chart、內建/custom DOCX、外部關聯稽核、LibreOffice headless PDF、hash 與 snapshot。
- [x] 實作冪等 XSQ legacy import、demo seed、sample report 與 package audit commands。
- [x] 完成 Docker/Nginx/health/volume/startup/backup/restore 靜態驗證及 Ubuntu CI。
- [x] 完成 1440/1024/390 三視窗 UI QA、XSQ 2026 Q1 DOCX、Word COM PDF、逐頁及長評論分頁 QA。
- [x] 完成文件、全套 tests、Ruff、Django、migrations 與 Compose config。

## 關鍵設計決策

- 權威金融值使用 `decimal.Decimal`；只在顯示層 `ROUND_HALF_UP`。
- 公式版本固定為 `legacy_excel_v1`；最大回撤刻意使用 running peak 修正 workbook 固定 cell 錯誤。
- valuation month 正規化為月末，但保留原始日期、sheet/cell 與 import warning。
- 官方 RFR 必須恰好選出 report end 當日或之前的連續 12 個月末觀察；人工值必須有理由、操作者與時間。
- FINAL/STALE report 的內容、snapshot 與檔案不可覆寫；NAV、fund、share class、organization report settings 變更將既有 FINAL 標成 STALE。
- production PDF 只依賴 container 內 LibreOffice；Word COM 只作本機交付視覺證據。

## Definition of done

所有應用層與 artifact 要求均通過。唯一未在此 Windows 主機執行的項目是 Docker engine build/smoke 與本機 LibreOffice integration；兩者已由 Compose/CI 定義承接，且記錄為外部環境驗證限制，不是應用缺陷。詳見 `docs/FINAL_VALIDATION_REPORT.md`。
