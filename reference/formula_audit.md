# XSQ Excel 績效公式審核（v1）

- 審核檔案：`XSQ Data till 202603.xlsx`
- 主要審核工作表：`2026 Mar (monthly)`
- 對照報告：`X Squared Capital Management LPF Quarterly Newsletter 2026Q1`
- 目的：Web App 第一版先重現現有 Excel 的報告結果，同時清楚標示可能錯誤、非標準或不適合自動化的公式。
- 審核日期：2026-07-17

> **實作原則**：報告顯示數字先以現有 Excel 邏輯為基準；但不照搬固定儲存格位置或手動貼值。App 應從 NAV 時序資料動態計算，並保存公式版本、原始輸入及計算結果，供日後追溯。

---

## 1. 2026 Q1 現有 Excel 基準結果

以下數字可作為第一輪系統驗收基準：

| 指標 | 現有 Excel 結果 |
|---|---:|
| 2026 Q1 Return | -16.236898% |
| 2026 YTD Return | -16.236898% |
| ITD Return | -22.720995% |
| Annualized Return | -6.642387% |
| Positive Months | 37.777778% |
| Negative Months | 62.222222% |
| Annualized Volatility | 53.920428% |
| Trailing 12-Month Volatility | 78.039608% |
| Risk-Free Rate（Excel 12 個月平均） | 4.190858% |
| Sharpe Ratio | -0.200912 |
| Excel 顯示的 Max Drawdown | -41.472744% |

Word 顯示格式應為：回報及波幅 2 個小數位、正負月份 0 個小數位、Sharpe 3 個小數位。

---

## 2. 現有 Excel 公式及 App 的 Legacy 實作定義

### 2.1 Monthly Return

Excel 邏輯：

```text
Monthly Return[t] = NAV[t] / NAV[t-1] - 1
```

首個觀察期：

```text
First Return = First NAV / Inception NAV - 1
```

App v1：照此公式計算。

必要條件：

- NAV 必須大於 0。
- 同一 Share Class 每個月份只可有一筆有效 NAV。
- 月份不可中斷；如缺月，系統不得把兩個月的回報當成一個月回報。
- 若基金有 distribution、split、series conversion 或其他會令 NAV 不代表 total return 的事件，需加入 adjustment factor；目前 Excel 未處理此類調整。

### 2.2 Quarterly Return

Excel 的一般邏輯：

```text
Quarterly Return = Quarter-End NAV / Previous Quarter-End NAV - 1
```

基金或 Share Class 在季度中途成立時：

```text
First Partial-Quarter Return = First Quarter-End NAV / Inception NAV - 1
```

App v1：按 valuation month 動態尋找季末 NAV，不使用固定行號。

### 2.3 YTD Return

Excel 邏輯：

```text
YTD = Latest NAV / Previous Year-End NAV - 1
```

首個年度沒有上一年年末 NAV 時：

```text
YTD = Latest NAV / Inception NAV - 1
```

App v1：照此邏輯。

### 2.4 ITD Return

Excel 2026 Q1 公式：

```excel
=(E47-100)/100
```

一般化後：

```text
ITD = Latest NAV / Inception NAV - 1
```

App v1 必須使用每個 Share Class 的 `inception_nav`，不可把 100 寫死。

### 2.5 Annualized Return

Excel 公式：

```excel
=(PRODUCT(1 + Monthly Returns))^(12 / Number of Monthly Returns) - 1
```

等價表示：

```text
Annualized Return = (Latest NAV / Inception NAV)^(12 / N) - 1
```

其中 `N` 是 Excel 計入的月度回報數目。

App v1：為重現 Excel，採用相同月度幾何年化公式。

### 2.6 Monthly Standard Deviation since Inception

Excel：

```excel
=STDEVA(Monthly Return Range)
```

App v1：在所有輸入均為數值的前提下，使用 sample standard deviation（`n-1`），結果與目前 Excel 相同。

### 2.7 Trailing 12-Month Standard Deviation

Excel：

```excel
=STDEVA(Latest 12 Monthly Returns)
```

App v1：只在已有最少 12 個連續月度回報時顯示；否則顯示 `N/A`，不可把不足 12 個月的資料包裝為 12-month 指標。

### 2.8 Annualized Volatility

Excel：

```text
Annualized Volatility = Monthly SD since Inception × SQRT(12)
```

App v1：照此公式。報告標籤建議寫成 `Annualized Volatility (Since Inception)`，以免被誤解為 trailing volatility。

### 2.9 Positive / Negative Months

Excel：

```text
Positive Months % = Count(Return > 0) / Count(Numeric Returns)
Negative Months % = Count(Return < 0) / Count(Numeric Returns)
```

App v1：為重現 Excel，照此公式。

### 2.10 Maximum Monthly Gain / Loss

Excel：

```text
Maximum Monthly Gain = MAX(Monthly Returns)
Maximum Monthly Loss = MIN(Monthly Returns)
```

App v1：照此公式。

### 2.11 Risk-Free Rate

Excel 2026 Q1：

```text
RFR = Average of 12 monthly USGG10YR Index PX_LAST_ASK observations / 100
```

App v1 建議：

1. 主來源：FRED `DGS10`（10-Year U.S. Treasury Constant Maturity，daily，percent）。
2. 將 daily observations 聚合成 monthly end-of-period。
3. 取截至報告月份的最近 12 個月末觀察值。
4. 以算術平均計算 annual RFR，再除以 100。
5. 保存每一個原始觀察日期、數值、資料來源及抓取時間。
6. 允許報告層級 manual override，並要求輸入 override reason。
7. Bloomberg 數據可日後作為可選 provider；如需要與舊 Excel 的 Sharpe 完全一致，應使用同一 Bloomberg field 或匯入舊值。

官方資料來源：

- FRED DGS10：https://fred.stlouisfed.org/series/DGS10
- FRED API observations：https://fred.stlouisfed.org/docs/api/fred/series_observations.html
- U.S. Treasury Interest Rate Statistics：https://home.treasury.gov/policy-issues/financing-the-government/interest-rate-statistics

### 2.12 Sharpe Ratio

Excel：

```text
Sharpe = (Annualized Return - Annual RFR) / Annualized Volatility since Inception
```

App v1：報告數字先照此公式，並把計算方法標記為 `legacy_excel_v1`。

### 2.13 Maximum Drawdown

現有 Excel 2026 Q1：

```excel
=E36/E32-1
```

這只是指定一個固定 peak 及固定 trough，而不是在完整歷史中搜尋最大回撤。

標準動態算法：

```text
Running Peak[t] = max(NAV[0..t])
Drawdown[t] = NAV[t] / Running Peak[t] - 1
Maximum Drawdown = min(Drawdown[t])
```

App 應使用標準動態算法；如必須保留 Excel 數字，則另外保存 `legacy_manual_drawdown`，不可把固定行號公式套用到其他基金。

---

## 3. 已識別問題及風險

### A. 很可能是錯誤，需優先處理

#### A1. Max Drawdown 不是全歷史最大回撤

- Excel 固定公式：`=E36/E32-1`
- Excel 結果：`-41.472744%`
- 按完整 NAV 歷史的 running peak-to-trough 計算：`-57.435305%`
- 對應 peak：105.242736（2022-08 標籤）
- 對應 trough：44.7962496（2025-04 標籤）

結論：如果欄位名稱是 `Max Drawdown`，現有公式很可能錯誤。App 不應複製固定儲存格公式。

#### A2. Inception Date 與首個 NAV 的日期重疊

- Inception Date：7 July 2022，Inception NAV：100。
- 首個 NAV 觀察值同樣標示 7 July 2022，但 NAV 已是 103.011676。
- Excel 把兩者之間的 +3.011676% 當成一個月度回報。

可能原因：日期只是用作月份標籤，而不是真實 valuation date。匯入 App 前應確認首個觀察值實際代表哪個月末。

#### A3. NAV 日期與報告日期不一致

- 多數 Excel NAV 日期是每月 1 日，例如最新 NAV row 是 1 March 2026。
- Word 報告寫的是 `All data as on 31 March 2026`。

目前回報因按行序計算而未必受影響，但日期追溯、季度選擇、外部數據對齊及審計會受影響。App 應保存真實 valuation date；舊資料匯入時可按月份正規化為該月最後一個曆日，但需先取得業務確認。

#### A4. `2026 Jun (monthly)` 可產生時點不一致的數據

該 worksheet 已建立 Apr–Jun 空白 NAV rows，但績效公式仍引用 March 2026 NAV；同時 RFR 區域已包含後續月份數值。若人工誤用，可能生成「NAV 截至 3 月、RFR 截至 6 月」的混合報告。

App 必須：

- 自動以最新有效 NAV 決定 report period；
- 完整季度未輸入前禁止 finalize；
- RFR 的截止月份必須等於 report end month；
- 預覽頁顯示 NAV cutoff 及 RFR cutoff。

#### A5. Word 圖表仍連接舊本機 Excel

Word chart relationship 指向：

```text
file:///C:\Users\lydia\Documents\yomiclient\cache\e3\XSQ Data till 2025 Dec(1).xlsx
```

這個外部連結在 VPS、其他電腦及日後檔案搬移後可能失效或顯示舊資料。App 必須直接產生圖像並嵌入 Word，不保留 external workbook link。

### B. 公式可運作，但方法非標準或需明確披露

#### B1. Sharpe Ratio 方法可能與讀者預期不同

現有方法使用：

- 幾何 Annualized Return；
- 10-year Treasury yield 的 12-month average；
- since-inception annualized volatility。

常見 ex-post Sharpe 會以每月 excess return 的平均值除以其標準差再年化。兩種方法可能有顯著差異，甚至符號不同。這不一定是 Excel 算術錯誤，但必須在公式版本及內部文件中明確定義。

#### B2. 10-year Treasury 並非短期 cash proxy

Excel 使用 `USGG10YR Index`。這是既有業務選擇，但有 duration mismatch。第一版應照舊；日後可把 RFR series 設為 fund-level setting，例如 3-month、1-year 或 10-year。

#### B3. Annualized Return 未使用實際日數

Excel 已計算 `Days = End Date - Inception Date`，但 Annualized Return 不使用 Days，而是用月數 `12/N` 年化。

以目前 2026 Q1 資料計算：

- Excel 月度幾何年化：約 `-6.6424%`
- 以 31 March 2026 及實際 1,363 日計算的 day-based CAGR：約 `-6.6739%`

目前差異較小，但中途成立、非月末或缺月時可擴大。第一版照 Excel；系統可同時在 audit 頁顯示 day-based CAGR 作參考，但不放進報告，除非日後批准改公式。

#### B4. Zero-return 月份的分類

零回報會被計入分母，但不屬於 positive 或 negative，因此兩者相加可能少於 100%。第一版照 Excel；建議內部畫面另顯示 `% Zero Months`。

#### B5. `STDEVA` 對非純數值內容較敏感

目前回報範圍是數值，因此結果正常。App 應在資料層禁止文字、布林值或空字串進入回報序列，並以 sample standard deviation 計算。

### C. 自動化及維護風險

#### C1. 大量歷史 NAV、Monthly Return 及 Growth Factor 是手動值

在 `2026 Mar (monthly)` 中，許多 cells 是已貼入的數值而不是連續公式。這會令人工新增月份時容易漏填、錯貼或保留舊數字。

App 應只保存 NAV input；所有 return、quarter、YTD、statistics 皆由 calculation service 重算。

#### C2. 2022 Q3 及 Q4 的季度 cells 在最新 monthly sheet 為空白

Word 表仍顯示：

- 2022 Q3：-0.18%
- 2022 Q4：-4.28%

即季度報告表不是單純引用完整的 H column。App 必須按日期動態建立整張年度／季度矩陣。

#### C3. 固定範圍會隨新增月份失效

例如：

```excel
STDEVA(F3:F47)
PRODUCT(G3:G47)
COUNT(F3:F47)
```

每季複製 worksheet 再手動修改範圍，容易遺漏。App 應查詢該 Share Class 截至 report end 的所有有效 records，不使用 row ranges。

#### C4. 缺月可能被靜默忽略

Excel `PRODUCT`、`COUNT` 及標準差範圍在有 blanks 時可能仍返回數字。若中間缺一個月份，下一個 NAV 的跨期變動可被誤當單月回報。

App 應在計算前檢查月份連續性；缺月時阻止 final report，除非使用者明確標記該基金本來不是 monthly valuation。

#### C5. 歷史 RFR 有無效日期文字

RFR 歷史區域出現 `2021/9/31`，而 9 月沒有 31 日。該值目前不在 2026 Q1 的 12-month average 範圍內，但顯示手動資料可有日期錯誤。App 必須使用 date type 及來源驗證。

#### C6. 欄位標題與資料內容不一致

Excel column C 的標題是 `Indicative/ Official`，但內容是金額並用於 `NAV/SHARE = C/B`，看似實際為 total NAV。新 App 已決定只輸入 NAV per Share，因此不應沿用這個欄位結構。

---

## 4. App v1 應採用的公式版本策略

每次計算及產生報告時保存：

```text
calculation_method = legacy_excel_v1
rfr_provider = FRED_DGS10 | TREASURY_CMT10 | BLOOMBERG_USGG10YR | MANUAL
rfr_method = average_of_12_month_end_observations
formula_version = 1
calculated_at = timestamp
source_nav_version = immutable identifier
```

### 報告數字照 Excel的項目

- Monthly Return
- Quarterly Return
- YTD
- ITD（改用動態 inception NAV）
- Annualized Return（月度幾何年化）
- Positive / Negative Months
- Annualized Volatility since inception
- Max Monthly Gain / Loss
- Sharpe Ratio 的整體公式

### 不應照搬固定儲存格的項目

- Max Drawdown：使用動態 running peak 算法。
- 季度／YTD row selection：按日期計算。
- RFR row range：按 report end 及 observation dates 計算。
- Word chart：由 App 直接嵌入。

### 必須保留 audit trail

- 每筆 NAV 的建立及修改時間。
- 修改前／修改後數值。
- 報告使用哪一版 NAV。
- RFR 原始 observations。
- 公式版本。
- Word/PDF 檔案 hash。
- Manual override 的原因。

---

## 5. 驗收測試案例

### Test 1 — 2026 Q1 基準回報

```text
Previous year-end NAV = 92.25900603925423
Jan-2026 NAV = 90.61700453137055
Feb-2026 NAV = 90.70900308009685
Mar-2026 NAV = 77.27900516437292
```

預期：

```text
Q1 Return = 77.27900516437292 / 92.25900603925423 - 1
          = -16.2368981826%
YTD Return = -16.2368981826%
```

### Test 2 — 報告顯示

```text
Q1 = -16.24%
YTD = -16.24%
ITD = -22.72%
Annualized Return = -6.64%
Positive Months = 38%
Negative Months = 62%
Annualized Volatility = 53.92%
Sharpe = -0.201   # 僅在使用 Excel 的 4.190858% RFR 時
```

### Test 3 — Missing Month

若 Jan NAV 後直接輸入 Mar NAV而沒有 Feb NAV：

- 系統顯示 validation error；
- 不計算 Mar monthly return；
- 不允許 finalize Q1 report。

### Test 4 — RFR cutoff

2026 Q1 報告只可使用截至 March 2026 的最近 12 個月末 RFR，不可包含 April–June 2026 observations。

### Test 5 — Dynamic Drawdown

使用完整現有 NAV 歷史，標準 Maximum Drawdown 應約為：

```text
-57.435305%
```

而非 Excel 固定公式的 `-41.472744%`。

### Test 6 — Word external links

產生的 `.docx` package 中不得存在：

```text
TargetMode="External"
```

指向 Excel 的 chart relationship。

---

## 6. 需要管理層／業務最終確認的三個決定

1. **Max Drawdown**：採用標準動態結果（建議），還是保留舊 Excel 的人工 peak/trough 數字。
2. **Sharpe disclosure**：是否繼續使用現有幾何 annualized return 方法，或日後轉為 monthly excess return Sharpe。
3. **舊 NAV 日期正規化**：是否把以每月 1 日或其他月份標籤儲存的日期，轉為該月最後一個曆日。

在未另行批准前，建議系統預設：

```text
Max Drawdown = standard running peak-to-trough
Sharpe = legacy_excel_v1
Legacy valuation dates = import as valuation month + preserve original raw date
```
