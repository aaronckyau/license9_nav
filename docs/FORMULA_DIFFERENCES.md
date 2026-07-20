# Formula Differences from the Legacy Workbook

本應用保留 `legacy_excel_v1` 的商業意義，但移除 spreadsheet cell/range 依賴。公式以日期與資料序列驅動，不複製固定 row/cell reference。

| 項目 | Legacy workbook | 應用實作 | 理由 |
|---|---|---|---|
| 月份 | 儲存格日期有月初/月中等標籤 | 正規化為 calendar month-end，保留 raw date/cell | 防止同月重複及跨月誤判 |
| 第一月報酬 | 依固定 inception cell | `first NAV / inception NAV - 1` | 適用任意 fund/share class |
| 季/YTD | 固定列範圍 | 以 quarter/year boundary 找 NAV | 新月份無需改公式 |
| 年化報酬 | `PRODUCT(1 + monthly returns)^(12/N)-1` | 相同的月度幾何年化，明確標成 legacy | 保持歷史報表相容性，day-based CAGR 只供 audit comparison |
| 波動 | Excel sample STDEV × sqrt(12) | Decimal 月報酬轉 sample stdev × sqrt(12) | 保持樣本定義 |
| 最大回撤 | workbook 使用固定 peak cell，約 `-41.47%` | 動態 running peak，約 `-57.44%` | 修正固定 cell 漏掉後續高點的錯誤 |
| RFR | 工作簿固定/外部資料 | 12 個連續月末官方 observation，截止 report end | 可稽核且防止 look-ahead |
| Sharpe | legacy annualized return 與 workbook RFR | 同分子/波動分母，但 RFR snapshot 可追溯 | 保持公式、改善資料治理 |
| 顯示精度 | 儲存格格式與浮點殘差 | Decimal raw；presentation `ROUND_HALF_UP` | 負百分比與小數一致 |

刻意差異只有 maximum drawdown 的錯誤修正及資料治理/驗證強化；公式 identifier 仍為 `legacy_excel_v1`，並在 snapshot 與報表 provenance 顯示。
