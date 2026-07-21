# Calculation Methodology

權威公式版本為 `legacy_excel_v1`。金融輸入與中間值使用 `decimal.Decimal`；NAV 在資料庫使用 `NUMERIC(38,18)`。只在 HTML/DOCX 顯示層以 `ROUND_HALF_UP` 和 organization precision 設定格式化。百分比內部以 decimal 表示，例如 5% 為 `0.05`。

## 月報酬與連續性

- 第一個月：`NAV_1 / inception_NAV - 1`。
- 之後月份：`NAV_t / NAV_(t-1) - 1`。
- 月份必須從 inception month 到 report end 連續；duplicate、缺月、非正 NAV、缺 quarter-end 都會阻止權威計算或 finalization。

## 報酬

- 月報所選期間回報：`report_month_NAV / previous_month_NAV - 1`；第一個月以 inception NAV 為基準。
- Quarter：`quarter_end_NAV / preceding_quarter_end_NAV - 1`；第一個 partial quarter 以 inception NAV 為基準。
- YTD：`latest_NAV / previous_December_NAV - 1`；第一年度以 inception NAV 為基準。
- ITD：`latest_NAV / inception_NAV - 1`。
- Legacy annualized return：`PRODUCT(1 + monthly returns)^(12 / N) - 1`，等價於 `(latest NAV / inception NAV)^(12 / N) - 1`。

## 風險與分布

- Annualized volatility：所有月報酬 sample standard deviation × `sqrt(12)`。
- Trailing 12-month volatility：最後 12 個月報酬 sample standard deviation × `sqrt(12)`；不足為 N/A。
- Positive/negative/zero months：各類月份數 ÷ 全部月報酬數。
- Maximum monthly gain/loss：月報酬序列 max/min。
- Maximum drawdown：每月 `NAV_t / max(inception_NAV, NAV_1..NAV_t) - 1` 的最小值。
- Sharpe：`(legacy annualized return - annual RFR decimal) / annualized volatility`；波動為零時為 N/A。

## XSQ 2026 Q1 regression

由 `reference/xsq_nav_history.xlsx` 45 筆資料計算：Q1/YTD `-16.24%`、ITD `-22.72%`、legacy geometric annualized return `-6.64%`、annualized volatility `53.92%`、trailing 12-month volatility `78.04%`、positive/negative months `38%/62%`、dynamic maximum drawdown `-57.44%`、以 4.1908583333% RFR 計算 Sharpe `-0.201`。精確 raw Decimal 由 tests 比對，以上為報表顯示精度。

每個 review metric 同時保存 raw value、display value、公式文字、formula version、data cutoff 與 warnings，final snapshot 可重現。月報與季報均使用 `legacy_excel_v1`；差異只在截止月份驗證、所選期間回報及報告回報表的呈現。
