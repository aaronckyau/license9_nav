# User Guide

## 登入與主要流程

使用管理員提供的個人帳號登入。一般工作都在自訂頁面完成，不使用 Django Admin。

1. **Select Fund**：Dashboard 選 fund/share class，或建立新 fund。
2. **Fund Setup**：填 legal/display name、domicile、objective；建立一或多個 share classes/series；設定 strategy、parties、terms、contacts。
3. **Enter NAV**：逐月輸入 valuation month/date 與 NAV per share，或 dry-run/confirm CSV/XLSX import。
4. **Review Performance**：選 year/quarter/version，檢查 continuity warnings、quarterly table、NAV chart、metrics 與 RFR。
5. **Manager Commentary**：輸入 title、Markdown commentary、author、date；可重複編輯 draft。
6. **Preview**：檢查所有報表 section、負百分比、小數精度、disclaimer 與 provenance。
7. **Generate Report**：產生 DOCX/PDF；下載、核對後 finalization。資料需更正時建立新 version，不覆寫 FINAL。

## NAV 驗證

- Valuation month 會正規化為月末；NAV 必須大於零。
- 同 share class/month 重複時表單顯示錯誤，不產生 500。
- 缺月會在 Review Performance 列出並阻止權威生成/finalization。
- 絕對月變動超過 organization threshold（預設 25%）顯示 abnormal warning；需勾選 acknowledgement 才可保存。
- 修改既有 NAV 必須填理由；audit 保留 before/after/revision。受影響 FINAL 轉為 STALE，但原 snapshot/file 不變。

## RFR

優先按 **Fetch online RFR** 取得 FRED/U.S. Treasury 12 個月末值。Provider 暫時不可用且有正式依據時，才使用 **Manual override**，輸入 published percentage 及具體理由。FINAL/STALE report 的 RFR 不能修改。

## 版本與不可變性

Report History 顯示每個 version 的 status、creation/finalization、DOCX/PDF 下載與 review。FINAL/STALE 不允許修改 commentary、重新生成、覆寫 RFR 或改 snapshot；來源修正後建立下一 version。

## 管理員

`/admin/` 只供 trusted system administration/data correction。任何 admin correction 仍需依內部 change-control，並在應用中確認 affected report staleness；正常月結流程不可依賴 Admin。
