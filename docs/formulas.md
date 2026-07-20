# Formula and Numeric Policy

權威版本識別碼固定為 `legacy_excel_v1`。所有中間值使用 `decimal.Decimal`；資料庫 NAV 使用 PostgreSQL `NUMERIC(38,18)`，只在顯示層用 `ROUND_HALF_UP`。百分比資料以 decimal（例如 5% = `0.05`）計算。

## Returns

- 第一個月：`NAV_1 / Inception NAV - 1`。
- 其後月：`NAV_t / NAV_(t-1) - 1`。
- 季報酬：`quarter-end NAV / preceding quarter-end NAV - 1`；第一個 partial quarter 以 inception NAV 為基準。
- YTD：`latest NAV / prior-year December NAV - 1`；第一年度以 inception NAV 為基準。
- ITD：`latest NAV / inception NAV - 1`。
- 舊版年化報酬：`PRODUCT(1 + monthly returns)^(12/N)-1`（月度幾何年化）。
- 年化波動：所有月報酬 sample standard deviation × `sqrt(12)`。
- Trailing 12-month volatility：最後 12 個月報酬的 sample standard deviation × `sqrt(12)`；不足顯示 N/A。
- 正／負／零月份比例：對所有月報酬分類後除以總月份數。
- 最大月 gain/loss：月報酬序列的 max/min。

## Maximum drawdown

使用動態 running peak：每期 `drawdown_t = NAV_t / max(Inception NAV, NAV_1..NAV_t) - 1`，取最小值。這是刻意修正舊工作簿固定 cell reference 的錯誤；XSQ 參考資料的動態值約 `-57.4353%`，不使用工作簿約 `-41.47%` 的固定 cell 結果。

## RFR and Sharpe

線上 provider 的每日值按月份取「不晚於 report end 的最後非空觀察」，必須涵蓋 report end 向前連續 12 個月份。年 RFR decimal = 12 個 published percent 的算術平均 ÷ 100。

`Sharpe = (Legacy annualized return - Annual RFR decimal) / Annualized volatility since inception`

人工 RFR 由使用者輸入 published percentage（例如 `4.19`），系統轉為 `0.0419` 並要求理由、操作者與時間。

## Validation

重複月份、缺月、非正 NAV、缺 quarter-end NAV、RFR 少於 12 月或超過 report end 均阻止權威計算／finalization。每項 review metric 都保留 raw 值、公式文字、版本、資料 cutoff 與 warning。
