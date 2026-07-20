# Risk-Free Rate Methodology

## 官方來源

- `FRED_DGS10`：Federal Reserve Economic Data 的 10-Year Treasury Constant Maturity Rate。
- `TREASURY_CMT10`：U.S. Treasury 官方 par yield curve `BC_10YEAR`，作為不需 FRED API key 的 fallback。

一般三步流程採自動 provider 選擇：organization 設為 FRED 但沒有 `FRED_API_KEY` 時，直接改用 `TREASURY_CMT10`，使用者不需要處理環境設定。進階功能若明確指定 FRED，仍要求有效 API key，避免無聲忽略操作者的明確選擇。

yfinance 可以下載 Yahoo Finance 的 `^TNX`（Cboe 10 年期利率指數）歷史值，但 yfinance 官方文件明示該工具未獲 Yahoo 認可，下載介面預期只供個人、研究及教育用途。此應用需要可稽核的正式報告來源，因此不把 yfinance／`^TNX` 納入 production provider；權威預設仍是 U.S. Treasury 官方 `BC_10YEAR`。

Provider 以 timeout/retry 取得每日 published percentage，保存 provider、series、observation date、value、fetch time 與 raw checksum。重複 provider/series/date 使用資料庫 unique constraint 去重。

## 報告 snapshot

對 report end 向前 12 個 calendar months，各月選擇「不晚於該月末且不晚於 report end 的最後一筆非空 observation」。必須得到恰好 12 個連續月份；任何缺月或 report-end 後資料均拒絕。年 RFR decimal 為 12 個 published percentages 的算術平均 ÷ 100。

每個 report 保存獨立 `RFRSnapshot` 與 12 筆 ordered observations，因此 provider cache 後續更新不會改變已生成 snapshot。

## 人工覆寫

使用者輸入 published annual percentage，例如 `4.19`。系統轉為 `0.0419`，要求非空 justification，並保存 actor/time。Review/preview/report 都明示 `MANUAL`。FINAL 或 STALE report 禁止官方 refresh、cache attach 或 manual overwrite。

## 驗證證據

2026-07-20 本機實際連線 Treasury，成功取得截至 2026-03-31 的 12 個 observation：provider `TREASURY_CMT10`、series `BC_10YEAR`、64 字元 checksum。Mock tests 另覆蓋無 FRED key 自動 fallback、明確 FRED 選擇、retry、cutoff、缺月、cache 及 finalized 鎖定。
