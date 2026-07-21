# User Guide

## 登入與主要流程

使用管理員提供的個人帳號登入。一般工作都在自訂頁面完成，不使用 Django Admin。

1. **選擇基金**：在首頁選擇基金及股份類別，按「輸入每股 NAV」。
2. **輸入每股 NAV**：頁面按年份顯示年度摘要、NAV 折線圖及完整月份紀錄。每個既有月份都有兩位小數輸入欄，直接修改後按同列「儲存」即可；毋須輸入修改原因、估值月份、估值日期或狀態。即使 NAV 已追到最新，清單仍會保留。年度回報優先以上一年 12 月 NAV 為基準；若缺少該筆資料，頁面會提示以當年首筆 NAV 作基準，首筆回報顯示「—」。最早缺少的月份會顯示輸入欄。輸入最多兩位小數並按「新增月份」後，系統顯示已保存數值並自動開放下一個月份。最近已完成月份是可輸入上限，例如系統日期 2026-07-21 時上限為 2026 年 6 月。
3. **評論及產生報告**：選擇股份類別、月報或季報、年度及截止月份。月報可選任何已完成月份；季報只可選 3、6、9、12 月。輸入該期間的基金經理評論並按「儲存評論並產生報告」。系統先保存評論、驗證缺月，再自動取得官方 RFR、計算績效並產生 Word 及 PDF；完成後可在同一張報告卡下載。

基金建立後不需要在正常流程重複設定基金或輸入報告日期。評論屬於所選報告期間，不屬於某一筆 NAV。報告所需月份尚未齊全時會列出缺月並停止產生，不會補入假資料。

期間已完成時可先按「僅儲存評論」，稍後再產生。若報告已是 `READY`，再次保存或產生會更新同一份現行報告及其下載檔，不會要求使用者管理版本。已定稿報告不可修改。

## NAV 驗證

- Valuation month/date 由一般流程設為該月月末；NAV 必須大於零且小數點後最多兩位。
- 同 share class/month 重複時表單顯示錯誤，不產生 500。
- 缺月會在產生或進階績效檢查時列出，並阻止權威生成／定稿。
- 絕對月變動超過 organization threshold（預設 25%）顯示 abnormal warning；需勾選 acknowledgement 才可保存。
- 修改既有 NAV 不要求使用者另填理由；系統自動保留固定理由、before/after/revision。受影響 FINAL 轉為 STALE，但原 snapshot/file 不變。

## RFR

優先按 **Fetch online RFR** 取得 FRED/U.S. Treasury 12 個月末值。Provider 暫時不可用且有正式依據時，才使用 **Manual override**，輸入 published percentage 及具體理由。FINAL/STALE report 的 RFR 不能修改。

## 報告不可變性

一般報告頁每個股份類別、類型及截止月份只顯示一份現行報告及其 DOCX/PDF 下載。FINAL/STALE 不允許修改評論、重新生成、覆寫 RFR 或改 snapshot；內部稽核欄位仍保留重現既有定稿資料所需資訊。

## 管理員

`/admin/` 只供 trusted system administration/data correction。任何 admin correction 仍需依內部 change-control，並在應用中確認 affected report staleness；正常月結流程不可依賴 Admin。
