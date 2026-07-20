# NAV Quarterly Report Web App — 功能及技術規格（v1）

- 使用場景：公司內部 VPS
- 使用者：第一版只有 1 個 full-access user
- 報告輸出：Word 及 PDF
- 報告語言：預設英文；管理介面可使用英文／中文
- 核心原則：基金靜態資料設定一次；日常只需輸入每月 NAV per Share，季度再填 Manager Commentary。

---

## 1. 已確認需求

1. 使用者直接輸入 **NAV per Share**。
2. NAV 頻率為 **Monthly**。
3. 支援多個 Fund，以及每個 Fund 多個 **Share Class / Series**。
4. 績效報告第一版依照現有 Excel 邏輯計算；可能有問題的公式另載於 `XSQ_Excel_Formula_Audit_v1.md`。
5. Risk-Free Rate 由網上官方來源自動取得。
6. 輸出 `.docx` 及 `.pdf`。
7. 可改善現有 Word 排版，支援 Manager Commentary 自動分頁。
8. Logo、Disclaimer、General Information 等有 organization default，但可由個別 Fund 覆寫。
9. 第一版只有一種使用者權限：full access。
10. 系統安裝於內部 VPS。

---

## 2. 建議使用者流程

### Step 0 — Fund Dashboard

顯示：

- Fund name
- Share Class / Series
- 最新 NAV month
- 最新 NAV per Share
- 最新已完成 report period
- 狀態：`NAV Up to Date`、`Missing NAV`、`Commentary Required`、`Draft`、`Final`

動作：

- Create Fund
- Edit Fund
- Add Share Class
- Enter NAV
- Create Quarterly Report
- View Previous Reports

### Step 1 — Enter Monthly NAV

欄位：

| 欄位 | 必填 | 說明 |
|---|---|---|
| Fund | 是 | 已選基金 |
| Share Class / Series | 是 | 績效計算單位 |
| Valuation Month | 是 | 例如 2026-03 |
| Valuation Date | 是 | 預設該月最後一日，可修改 |
| NAV per Share | 是 | Decimal，建議儲存最少 8 位小數 |
| Status | 是 | Official / Indicative |
| Note | 否 | 特殊估值、distribution 等說明 |

Validation：

- NAV 必須大於 0。
- 同一 Share Class 同一 valuation month 不可重複。
- 不可跳月。
- 日期不可早於 inception date。
- 新輸入 NAV 相對上月變動超過設定門檻時顯示警告，例如 ±25%，但可確認後保存。
- 修改已用於 finalized report 的 NAV 時，要求原因並把相關 report 標示為 `Stale / Regeneration Required`。

### Step 2 — Performance Review

顯示：

- Monthly returns
- Quarterly return
- YTD return
- ITD return
- Annualized return
- Positive / Negative / Zero months
- Annualized volatility since inception
- Trailing 12-month volatility
- Maximum monthly gain / loss
- Maximum drawdown
- RFR source及12個 observations
- Sharpe ratio
- NAV chart

每個指標顯示：

- 未四捨五入原值
- 報告顯示值
- 公式名稱／版本
- 是否通過 validation

### Step 3 — Manager Commentary

欄位：

- Commentary Title（可選）
- Manager Commentary（必填）
- Author（預設 portfolio manager，可修改）
- Commentary Date（預設 report date）

支援：

- 多段落
- Bold / Italic
- Bulleted list
- Numbered list
- 自動字數及估計頁數提示

第一版不必支援複雜 HTML；只保留可安全映射到 Word 的基本 rich text。

### Step 4 — Report Preview

預覽：

- Cover/header
- Investment Objective
- Strategy Highlights
- Quarterly performance table
- NAV graph
- Fund Statistics
- Manager Commentary
- General Information
- Contacts
- Disclaimer

顯示 data cutoffs：

```text
NAV data through: 31 March 2026
RFR data through: 31 March 2026
Formula version: legacy_excel_v1
```

### Step 5 — Generate

按鈕：

- Save Draft
- Generate Word
- Generate PDF
- Finalize
- Download Word
- Download PDF
- Regenerate

Finalized report：

- 不可直接覆蓋；修改後建立新 version。
- 保存檔案 hash、產生時間、公式版本、NAV data version 及 RFR observations。

---

## 3. Create New Fund 欄位字典

### 3.1 Fund Identity

| 欄位 | 必填 | 備註 |
|---|---|---|
| Fund Legal Name | 是 | 法律名稱 |
| Fund Display Name | 是 | 報告顯示名稱 |
| Fund Short Code | 是 | 唯一代碼，例如 XSQ |
| Fund Structure | 是 | 例如 Hong Kong Limited Partnership Fund |
| Domicile | 是 | 例如 Hong Kong |
| Financial Year End | 是 | 例如 31 December |
| Report Language | 是 | 預設 English |
| Active / Archived | 是 | 狀態 |

### 3.2 Investment Content

| 欄位 | 必填 | 備註 |
|---|---|---|
| Investment Objective | 是 | 長文字 |
| Strategy Highlights | 是 | 可增加、刪除、排序多個 bullets |
| Performance Note | 否 | 例如 fee structure note |
| Professional Investor Statement | 否 | 可繼承 default |

### 3.3 Parties and Service Providers

| 欄位 | 必填 |
|---|---|
| Portfolio Manager | 是 |
| General Partner | 視基金結構 |
| Investment Manager | 是 |
| Fund Administrator | 是 |
| Auditor | 否 |
| Legal Adviser | 否 |
| Custodian / Prime Broker | 否 |

### 3.4 Fund Terms

| 欄位 | 必填 | 備註 |
|---|---|---|
| Minimum Contribution | 否 | Text，保留幣別及格式 |
| Valuation Frequency | 是 | MVP 固定 Monthly |
| Base Currency | 是 | ISO currency，例如 USD |
| Bloomberg Code | 否 | Text |
| Management Fee | 否 | Text |
| Carried Interest / Performance Fee | 否 | Text |
| Lock-up Period | 否 | Text |
| Redemption Terms | 否 | Text |
| Subscription Terms | 否 | Text |

### 3.5 Contacts

每個 Fund 可有多個 contact：

- Role
- Name
- Email
- Phone
- Address
- Display in Report：Yes / No
- Sort Order

### 3.6 Branding and Template

| 欄位 | 必填 | 備註 |
|---|---|---|
| Logo | 否 | 預設 organization logo |
| Primary Brand Colour | 否 | 預設 organization setting |
| Word Template | 是 | 預設共用 template，可覆寫 |
| Disclaimer | 是 | 可繼承／覆寫 |
| Header Text | 否 | 例如 For Professional Investors only |
| Date Statement Template | 是 | 例如 All data as on {report_date} unless stated otherwise |
| Percentage Decimal Places | 是 | 預設 2 |
| Sharpe Decimal Places | 是 | 預設 3 |

---

## 4. Share Class / Series 欄位

績效必須在 Share Class 層級計算，因不同 class 可有不同 fee、currency、inception 及 NAV。

| 欄位 | 必填 |
|---|---|
| Fund | 是 |
| Class / Series Name | 是 |
| Class Code | 是 |
| Inception Date | 是 |
| Inception NAV | 是 |
| Currency | 是 |
| Return Basis | 是：Net / Gross |
| Management Fee | 否；可覆寫 Fund |
| Performance Fee | 否；可覆寫 Fund |
| Bloomberg Code | 否 |
| Active | 是 |
| Display in Quarterly Report | 是 |

第一版報告建議一次只輸出一個 Share Class；日後可加入同一份報告顯示多個 classes。

---

## 5. 績效計算規格

計算單位：每個 Share Class。

### Monthly Return

```text
R[t] = NAV[t] / NAV[t-1] - 1
```

### Quarterly Return

```text
RQ = Quarter-End NAV / Previous Quarter-End NAV - 1
```

首個季度使用 inception NAV 作為基準。

### YTD

```text
YTD = Latest NAV / Previous Year-End NAV - 1
```

首個年度使用 inception NAV。

### ITD

```text
ITD = Latest NAV / Inception NAV - 1
```

### Annualized Return — Legacy Excel v1

```text
Annualized Return = PRODUCT(1 + Monthly Returns)^(12 / N) - 1
```

### Annualized Volatility — Legacy Excel v1

```text
Annualized Volatility = STDEV.S(All Monthly Returns) × SQRT(12)
```

### Trailing 12-Month Volatility

```text
T12M Volatility = STDEV.S(Latest 12 Monthly Returns) × SQRT(12)
```

### Positive / Negative Months

```text
Positive % = Count(R > 0) / Count(All Numeric R)
Negative % = Count(R < 0) / Count(All Numeric R)
Zero % = Count(R = 0) / Count(All Numeric R)  # UI only
```

### Maximum Drawdown

```text
Running Peak[t] = MAX(NAV[0..t])
Drawdown[t] = NAV[t] / Running Peak[t] - 1
Max Drawdown = MIN(Drawdown[t])
```

### Risk-Free Rate — Legacy Excel v1

```text
RFR = Average(last 12 monthly end-of-period 10Y Treasury observations) / 100
```

### Sharpe — Legacy Excel v1

```text
Sharpe = (Annualized Return - RFR) / Annualized Volatility
```

詳細風險及差異見 `XSQ_Excel_Formula_Audit_v1.md`。

---

## 6. RFR Online Integration

### 6.1 Primary Provider

FRED series：`DGS10`

API 建議參數：

```text
series_id=DGS10
file_type=json
frequency=m
aggregation_method=eop
observation_start=<report end minus sufficient buffer>
observation_end=<report end>
```

FRED API 需要 API key，於 VPS `.env` 保存：

```text
FRED_API_KEY=...
```

### 6.2 Fallback Provider

U.S. Treasury Daily Treasury Par Yield Curve Rates XML feed，讀取 10-year field，App 自行取每月最後可用 business-day observation。

### 6.3 Processing Rules

1. 不使用 report end 之後的 observation。
2. 每個月份取 end-of-period value。
3. 必須取得 12 個月份；不足時阻止 finalization，或由使用者 manual override。
4. 保存 raw response checksum 及 parsed observations。
5. Provider failure 時先使用同一 report period 的已快取資料。
6. Manual override 必須保存原因。
7. 畫面顯示 public source 與 Bloomberg legacy source 未必完全相同，因此 Sharpe 可能有輕微差異。

---

## 7. Word 及 PDF 產生方式

### 7.1 Word Template

建議使用 `.docx` template + placeholders，例如：

```text
{{ fund_name }}
{{ report_quarter }}
{{ report_date }}
{{ investment_objective }}
{{ strategy_highlights }}
{{ performance_table }}
{{ nav_chart }}
{{ fund_statistics }}
{{ manager_commentary }}
{{ general_information }}
{{ contacts }}
{{ disclaimer }}
```

實作可使用 Python `docxtpl` / `python-docx`。

### 7.2 Chart

- 從 database NAV records 直接建立 PNG/SVG-compatible raster image。
- 圖像嵌入 Word。
- 不建立 external Excel relationship。
- X-axis 使用實際 valuation month。
- 以 inception NAV 及歷史 NAV per Share 顯示。

### 7.3 Automatic Pagination

- Commentary 可跨頁。
- 表格 header 在跨頁時重複。
- 避免表格 row 被不合理切開。
- Disclaimer 自動延續，不強迫固定四頁。
- 首頁重要區塊盡可能保持完整。

### 7.4 PDF

先產生 Word，再在 VPS 使用 LibreOffice headless 轉換成 PDF，使 Word/PDF 版面盡量一致：

```text
DOCX → LibreOffice headless → PDF
```

每次產生後檢查：

- Word 檔案可開啟；
- PDF 頁數大於 0；
- 兩個檔案均保存 hash；
- 無外部 Excel link。

---

## 8. 建議資料庫結構

### `funds`

- id
- legal_name
- display_name
- short_code
- structure
- domicile
- year_end_month/day
- investment_objective
- performance_note
- language
- active
- created_at / updated_at

### `fund_strategy_highlights`

- id
- fund_id
- text
- sort_order

### `share_classes`

- id
- fund_id
- name
- code
- inception_date
- inception_nav
- currency
- return_basis
- fee overrides
- active

### `nav_records`

- id
- share_class_id
- valuation_month
- valuation_date
- nav_per_share
- status
- note
- version
- created_at / updated_at

Unique constraint：

```text
(share_class_id, valuation_month, active_version)
```

### `fund_parties`

- fund_id
- party_type
- name
- display_order

### `fund_terms`

- fund_id
- term_key
- display_label
- value_text
- display_order

### `contacts`

- fund_id
- role
- name
- email
- phone
- address
- display_order

### `disclaimer_versions`

- id
- scope：organization / fund
- fund_id nullable
- version
- effective_from
- body

### `rfr_observations`

- provider
- series
- observation_date
- value_percent
- fetched_at
- raw_checksum

### `reports`

- id
- fund_id
- share_class_id
- year
- quarter
- report_date
- status
- commentary
- commentary_author
- formula_version
- rfr_provider
- rfr_value
- nav_data_version
- disclaimer_version
- created_at / finalized_at

Unique constraint：

```text
(share_class_id, year, quarter, version)
```

### `generated_files`

- report_id
- file_type：DOCX / PDF
- storage_path
- sha256
- generated_at

### `audit_logs`

- entity_type
- entity_id
- action
- before_json
- after_json
- reason
- created_at

---

## 9. 建議技術架構

### Application

- Python Django
- PostgreSQL
- Django templates + HTMX（MVP 足夠，不必先建大型 SPA）
- `decimal.Decimal` 處理 NAV 及中間計算
- `docxtpl` / `python-docx` 產生 Word
- Matplotlib 產生 chart
- LibreOffice headless 轉 PDF

選擇 Django 的原因：

- 內建 authentication、forms、ORM、migration、admin。
- 適合內部 CRUD、版本及報告工作流。
- 單一 Docker deployment 相對簡單。

### VPS Deployment

Docker Compose services：

```text
nginx
web (Django + Gunicorn)
postgres
```

可選：

```text
worker (如日後加入 Celery)
redis
```

安全：

- HTTPS。
- 強密碼及 session timeout。
- 只允許公司 IP / VPN（如可行）。
- PostgreSQL 不公開到 Internet。
- 文件及 DB 每日備份。
- `.env` 不加入 source control。

---

## 10. MVP 範圍

### Included

- 單一 full-access login
- 多 Fund
- 多 Share Class
- Create/Edit Fund master data
- Monthly NAV input
- Excel history import
- Performance calculations
- Online RFR
- Commentary editor
- Preview
- Word/PDF generation
- Report version history
- Audit log
- Backup-ready Docker deployment

### Not Included in v1

- 多角色 approval workflow
- 外部 client login
- Bloomberg API direct integration
- Benchmark attribution
- Daily NAV
- Automated email delivery
- E-signature
- Multi-language report in the same document

---

## 11. 2026 Q1 驗收標準

以現有 XSQ NAV history 為測試資料：

| 指標 | 預期 |
|---|---:|
| Q1 Return | -16.236898% |
| YTD | -16.236898% |
| ITD | -22.720995% |
| Annualized Return | -6.642387% |
| Positive Months | 37.777778% |
| Negative Months | 62.222222% |
| Annualized Volatility | 53.920428% |
| Sharpe | 使用 legacy RFR 4.190858% 時為 -0.200912 |

Word：

- 季度表數字與現有報告一致。
- NAV graph 使用最新 March 2026 NAV。
- Manager Commentary 取代 placeholder。
- Commentary 增長時自動分頁。
- `.docx` 無 external Excel link。

PDF：

- 內容與 Word 一致。
- 無截字、表格重疊或空白尾頁異常。

---

## 12. 建議開發順序

1. Database schema及Fund/Share Class CRUD。
2. Excel NAV import及日期正規化預覽。
3. NAV entry及validation。
4. Calculation engine + 2026 Q1 automated tests。
5. RFR provider adapter及cache。
6. Word template generation。
7. PDF conversion及render QA。
8. Report versioning及audit logs。
9. Docker Compose、Nginx、HTTPS及backup。
10. User acceptance testing。

---

## 13. 預設決策

為避免開發停滯，v1 採用以下預設：

```text
Report calculation method: legacy_excel_v1
Max drawdown: standard dynamic running-peak method
RFR primary source: FRED DGS10
RFR calculation: average of 12 monthly end-of-period observations
RFR fallback: U.S. Treasury XML or manual override
Historical date import: preserve raw date + map to valuation month
Report template: organization default with fund-level overrides
Report output: one Share Class per report
```
