# User Guide

## 登入與主要流程

使用管理員提供的個人帳號登入。一般工作都在自訂頁面完成，不使用 Django Admin。

1. **選擇基金**：在首頁選擇基金及股份類別，按「輸入每股 NAV」。
2. **輸入每股 NAV**：頁面按年份列出既有月份與數值，每個既有月份均可按「編輯」修改；即使 NAV 已追到最新，清單仍會保留。最早缺少的月份會顯示輸入欄。輸入數值並按「新增月份」後，系統顯示已保存數值並自動開放下一個月份。最近已完成月份是可輸入上限，例如系統日期 2026-07-20 時上限為 2026 年 6 月。
3. **評論及產生報告**：每份季度報告均有自己的基金經理評論欄。在 3、6、9、12 月 NAV 齊全後，輸入該季度評論並按「儲存評論並產生報告」。系統先保存評論、驗證缺月，再自動取得官方 RFR、計算績效並產生 Word 及 PDF；完成後可在同一張報告卡下載。

基金建立後不需要在正常月結流程重複設定基金、選季度或輸入報告日期。評論屬於 report/version，不屬於某一筆 NAV。系統會依月份自動判斷季度；報告所需季度月份尚未齊全時會列出缺月並停止產生，不會補入假資料。

季度已完成時可先按「僅儲存評論」，稍後再產生。若報告已是 `READY`，再次保存或產生會自動建立下一個版本，舊版本的評論、快照及下載檔不會被覆寫。

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
