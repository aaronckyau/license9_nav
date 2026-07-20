# MVP Assumptions

最後更新：2026-07-18

1. MVP UI 與對外報表使用英文；工程/操作文件以繁體中文交接。
2. Organization defaults 存於 singleton；fund 可明確覆寫。報表生成時把 resolved 值寫入 immutable snapshot。
3. 本機/測試允許 SQLite；Linux container/VPS 使用 PostgreSQL 17。
4. Valuation month 是 calendar month-end；valuation date 是使用者提供的實際日期。
5. Legacy workbook 的月初日期視為月份標籤；匯入保留 raw date、sheet/cell 並正規化月末。
6. 2022-07-07 觀察視為 2022-07 月度值；inception NAV 100 分開保留。commit 前要求 first-period acknowledgement。
7. 每個 share class/month 只能有一筆 active NAV；修正要求理由、遞增 revision 並建立 audit。
8. 異常月變動預設門檻為絕對值大於 25%；使用者可確認後保存，不會悄悄改值。
9. Custom DOCX template 是進階路徑；檢查 extension、MIME、package、大小及 required placeholders，內建 generator 永遠可用。
10. Manual RFR 輸入 published annual percentage（例如 `4.19`），計算前轉為 decimal `0.0419`。
11. 報表採 A4、Arial 相容字體、流動段落與無固定列高；長評論及 disclaimer 由 Word/LibreOffice 自動分頁。
12. Finalization 必須已有 non-empty DOCX、PDF、snapshot，且計算/RFR/commentary validations 全部通過。
13. 目錄沒有 `.git` metadata，因此無可比較的 commit/diff baseline，也不建立或推送 repository。
14. HTTPS、IP allow-list/VPN、DNS、憑證與 off-site backup 是 VPS 管理責任；Django/Nginx 的安全設定與命令已文件化。
15. 本機可用的 `Word.Application` COM 匯出回報 Creator 為 WPS Docs，視為主機 Office 相容層；production 不依賴它。
16. Windows WSL/Docker Desktop `Wsl/CallMsi/Install/REGDB_E_CLASSNOTREG` 是外部 host-level 限制；本工作不修改任何全域 Windows/WSL/Docker/registry/BIOS 設定。
