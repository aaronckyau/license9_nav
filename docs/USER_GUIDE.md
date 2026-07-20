# User Guide

## 登入與主要流程

使用管理員提供的個人帳號登入。一般工作都在自訂頁面完成，不使用 Django Admin。

1. **選擇基金**：在首頁選擇基金及股份類別，按「選擇並開始輸入」。
2. **輸入 NAV 及基金經理評論**：選年份與 1–12 月，輸入該月每股 NAV 及評論。系統日期顯示於頁面；預設月份為最近已完成月份，例如 2026-07-20 預設 2026 年 6 月。非季末月份儲存後返回首頁，季末月份前往產生報告。
3. **產生報告**：在 3、6、9、12 月 NAV 齊全後按「產生報告」。系統會先驗證缺月，再自動取得官方 RFR、計算績效，並產生 Word 及 PDF；完成後可在同頁下載。

基金建立後不需要在正常月結流程重複設定基金、選季度、輸入報告日期或另外開啟評論頁。系統會依月份自動判斷季度。報告所需季度月份尚未齊全時，系統會列出缺月並停止產生，不會補入假資料。

## 進階功能

頁首「進階」及每份報告的「進階檢查」保留基金／股份類別設定、NAV 歷史與批次匯入、績效檢視、人工 RFR、HTML 預覽、版本與定稿控制。只有首次建立基金、資料修正或專業覆核時才需要使用。

## NAV 驗證

- Valuation month 會正規化為月末；NAV 必須大於零。
- 同 share class/month 重複時表單顯示錯誤，不產生 500。
- 缺月會在產生或進階績效檢查時列出，並阻止權威生成／定稿。
- 絕對月變動超過 organization threshold（預設 25%）顯示 abnormal warning；需勾選 acknowledgement 才可保存。
- 修改既有 NAV 必須填理由；audit 保留 before/after/revision。受影響 FINAL 轉為 STALE，但原 snapshot/file 不變。

## RFR

優先按 **Fetch online RFR** 取得 FRED/U.S. Treasury 12 個月末值。Provider 暫時不可用且有正式依據時，才使用 **Manual override**，輸入 published percentage 及具體理由。FINAL/STALE report 的 RFR 不能修改。

## 版本與不可變性

Report History 顯示每個 version 的 status、creation/finalization、DOCX/PDF 下載與 review。FINAL/STALE 不允許修改 commentary、重新生成、覆寫 RFR 或改 snapshot；來源修正後建立下一 version。

## 管理員

`/admin/` 只供 trusted system administration/data correction。任何 admin correction 仍需依內部 change-control，並在應用中確認 affected report staleness；正常月結流程不可依賴 Admin。
