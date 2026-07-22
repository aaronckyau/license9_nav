# Implementation Status

## 2026-07-22 Boya 原稿樣式與內嵌 NAV 圖（已完成）

- 依使用者提供的 2026-05 原始月報建立 Boya 專用報告樣式：Times New Roman／宋體、A4 0.5-inch margins、月度回報表、基金統計、評論、一般資料與免責聲明。
- 原稿的 Word 原生圖表具有外部 Excel/OLE 關聯；系統已改以動態產生的內嵌 NAV PNG 取代，並重新產生 Boya 的 2026-05 月報、2026 Q2 季報及 2026-06 月報。三份 DOCX package audit 均通過（兩張內嵌媒體、零外部 Excel 關聯），production LibreOffice PDF 已逐頁檢查。
- NAV 圖的 X 軸刻度依資料筆數自動調整：18 筆或以下逐月顯示、19–36 筆每兩月、37–72 筆每三月、超過 72 筆每六月，讓短期月報可看見較完整的日期序列而不使長期圖表標籤重疊。

## 2026-07-22 報告頁基金範圍化（本機驗證完成）

- 報告期間選擇器改以目前報告或 NAV 頁帶入的股份類別鎖定基金範圍；不再讓使用者從清單選到其他基金的股份類別，亦移除「報告文字」欄位。
- 新增回歸測試涵蓋同一基金範圍、跨基金 POST 拒絕、無既有報告的基金範圍及基金預設報告語言。完整測試、Ruff、Django system check 與 migration check 已於本機通過，並已於 production 發布；公開 `/nav/healthz`、`/nav/readyz` 與受保護的報告頁入口均已驗證。

## 2026-07-22 Boya Quant LPF 資料匯入（已完成）

- 已完成使用者提供的 `Boya Data till 202605.xlsx` 與 `Boya Quant LPF Monthly Newsletter 202605.docx` 的只讀結構核對。將只匯入本基金的 2025-11 成立 NAV 及 2025-12 至 2026-05 NAV；活頁簿中 2022–2024 的舊資料與本基金成立日不符，不會混入。
- Production 已備份並建立 Boya Quant LPF／Initial Series，匯入 7 筆官方 NAV，建立 2026 年 5 月月報；Treasury `BC_10YEAR` 的 12 筆觀察值、DOCX、PDF、immutable snapshot 及 DOCX 無外部 Excel 關聯檢查均已通過。
- 視覺檢查發現簡體中文的使用者評論在 LibreOffice PDF 顯示問號；另發現同名 PDF 已存在時 LibreOffice 不會覆寫。已把使用者輸入的評論、基金內容、表格與免責聲明 run 直接指定為所選 Noto CJK 字型（避免 LibreOffice 回退到 Arial），並在每次轉檔前只移除該報告輸出目錄的同名 PDF；兩項均有回歸測試。修正已發佈，並以實際 production LibreOffice 重新產生 Boya 報告：5 頁 A4 PDF、簡體評論完整顯示、DOCX package audit 有效、無外部 Excel relationship、2 個嵌入媒體且無嵌入 spreadsheet。報告維持 `READY`／可供定稿，未自動定稿。

## 2026-07-22 中文報告文字（已發佈）

- 報告建立頁加入繁體中文／簡體中文選擇；內建 DOCX 與 NAV 圖表使用相應 CJK 字型及系統固定文字，使用者原文內容不會被自動翻譯。
- 已通過繁體／簡體內建 DOCX 回歸測試、完整 pytest、Ruff、Django system check 及 migration check；本機沒有 Noto CJK／LibreOffice，圖表文字在本機安全退回英文軸標籤，production Docker image 會安裝 Noto CJK。
- 功能 commit `9fdbe0a` 已推送至 GitHub `main` 並部署至 Contabo production；資料庫及媒體已於部署前備份，migration、CJK 字型、LibreOffice DOCX/PDF smoke、繁體 DOCX 固定文字及 public `healthz`／`readyz`／登入頁均通過。

## 2026-07-22 基金設定簡化（本機驗證完成，待發佈）

- 一般基金設定頁已縮減為指定的基本資料表格、Portfolio Manager 的 Name／Contact、Investment Objective、Strategy Highlights and Characteristics 及 Disclaimer。
- 相關機構、條款、聯絡人與策略資料仍使用既有資料模型保存，確保現有報表、稽核、資料匯入及 Django Admin 不受影響；一般頁不再顯示品牌、DOCX 範本、報告繼承規則或可任意增列的 formset。
- 本機已通過 `pytest`（`53 passed, 1 skipped`）、Ruff format/check、Django system check 與 migration check。

## 2026-07-21 月報與季報版面一致化（本機驗證完成，待發佈）

- 月報 DOCX 與 HTML 預覽的「基金表現」已改為與季報相同的年度／Q1–Q4／YTD 績效矩陣；報告標題和截止日期仍保留月報語意，資料只計至所選月報截止日。
- 基金已設定自訂 DOCX 範本時，月報亦套用同一範本，讓標誌、表格、NAV 圖、統計、評論、頁首頁尾及 disclaimer 結構與季報一致。
- 已用使用者提供的 `MANU-2026 年第 2 季季報 (3).docx` 結構核對：其基金表現表為六欄 `Year / Q1 / Q2 / Q3 / Q4 / YTD`；本次月報沿用該表格結構。
- 已通過 `pytest`（`53 passed, 1 skipped`）、Ruff format/check、Django system check 與 migration check；唯一 skip 是本機未安裝 LibreOffice，故 PDF/PNG 渲染保留為部署容器驗證項目。

## 2026-07-21 NAV 刪除與報告頁簡化（已發佈）

- 每月 NAV 表格新增可稽核的刪除按鈕；刪除後會使受影響報告進入需要重新產生的狀態。
- 報告期間表單選擇季報時，截止欄位會顯示為「截止季度」並限制為四個季度結束月份。
- 一般報告操作頁只顯示目前新建或選取的報告，避免歷史報告卡片堆疊。
- commit `50408a5` 已推送 GitHub `main` 並部署至 Contabo production。本機完整 suite 為 `52 passed, 1 skipped`（本機缺少 LibreOffice），Ruff、Django system check、migration check 均通過；VPS 容器健康、DOCX/PDF smoke 與公開 health/readiness 均通過。

## 2026-07-21 NAV 年度輸入流程修正（已發佈）

- 基金卡片改為單一入口：點選後直接進入「輸入每股 NAV」，不再顯示個別報告連結。
- NAV 頁只保留月份、每股 NAV、月度回報、累積回報與操作表格；年度摘要與趨勢圖不再顯示。
- 年度表格固定顯示 1 至 12 月；目前選取年度預設展開，過去年度預設收起。年度選單提供至系統年份的下一年。
- 使用者只輸入每股 NAV；月度及累積回報由系統於儲存後自動計算。所有未填寫月份（包括尚未結束月份與下一年度）都可直接輸入並儲存。
- commit `5762226` 已推送 GitHub `main` 並部署至 Contabo production。本機品質檢查為 `52 passed, 1 skipped`（本機缺少 LibreOffice），Ruff、Django system check、migration check 均通過；VPS 容器健康、DOCX/PDF smoke 與公開 health/readiness 均通過。

## 2026-07-21 報告品牌與頁尾更新

- XSQ 內建 DOCX 報告改用使用者提供的 Aureum Infinity 標誌；其他基金仍保留既有的基金／機構標誌設定。
- 移除報告中的 Calculation and provenance 文字，以及舊有的詳細費用結構附註。
- 頁尾統一只顯示動態頁碼（Page 1、Page 2 等）。
- 使用 Microsoft Word 唯讀 COM 匯出 PDF，完成四頁 XSQ 2026 Q2 報告的視覺驗證；此工具僅作本機 QA，正式環境仍使用容器內 LibreOffice。

最後更新：2026-07-21

## 狀態

MVP 已完成並部署至 Contabo Linux VPS 的 `https://www.4mstrategy.com/nav/`。Production PostgreSQL、Gunicorn、Nginx、LibreOffice、登入及報表 smoke 均已實際驗證。

2026-07-20 的三步月結版本已推送 GitHub 並部署至 production，使用者提供的 XSQ 2026 Q1 DOCX 作為新版報告設計依據。部署後已通過 Docker build、migration、LibreOffice DOCX/PDF smoke、公開 health/readiness 及 authenticated HTTPS 三步流程檢查。

2026-07-21 更新把「評論及產生報告」改為月報／季報期間選擇器；一般使用者每個期間只操作一份現行報告，不再看到版本或 NAV／報告進階連結。Production 官方 Treasury `BC_10YEAR` 連線及 2026-06-30 的 12 筆觀察值已重新實測成功。

2026-07-21 後續把年度 NAV 表改為直接輸入及修改：每筆 NAV 只顯示／接受小數點後兩位，使用者毋須另開編輯頁或填寫修改原因、估值月份、估值日期及狀態。系統保留原月份／日期／狀態，自動遞增修訂版次、建立 before/after audit，並把受影響的定稿報告標示為需重新產生。

## 已完成

- 自訂 authenticated 三步月結工作流與 Django Admin 分離；原有專業控制保留在進階入口。
- 多 fund/share class、NAV entry/edit/import、duplicate constraint、missing month 與 abnormal movement warning。
- `legacy_excel_v1` 全套績效、quarterly return table、NAV chart、Decimal/display rounding。
- FRED/U.S. Treasury 線上 RFR、cache/snapshot/cutoff、理由必填 manual override。
- Commentary/preview/versioning、DOCX/PDF、hash、外部 relationship audit、final immutability/staleness/audit。
- XSQ 45 筆 legacy workbook 匯入及 2026 Q1 真實樣本報表。
- Dockerfile、Compose、Nginx、entrypoint、health checks、backup/restore、CI 與完整文件。
- 51 passed、1 個因本機無 LibreOffice 而 skip；最新 NAV 年度儀表板另完成 1440、1024、390、360 四視窗實際驗證，無水平溢出。
- GitHub `main`、VPS `/root/apps/license9_nav`、subpath `/nav` 與 loopback port `5430` 已部署。
- VPS Docker image build、三個 healthy containers、migration、`check --deploy`、LibreOffice DOCX/PDF smoke 與 public login/logout 已通過。
- 一般使用者網站已完整繁體中文化，包括登入、導覽、三步工作流程、表單、狀態、驗證訊息、績效檢視、RFR、評論、預覽、報告歷史及稽核頁；專有名詞及基金資料保留原文。
- NAV 頁按年份列出既有月份，每月均可在同一表格輸入或修改兩位小數 NAV；只開放最早缺少月份作新增，阻止跳月／重複 NAV，並保留異常變動的第二次確認。
- 基金經理評論已移到「評論及產生報告」頁，每個報告期間使用自己的評論欄，一次提交便儲存評論並產生報告。
- 產生報告時自動更新官方 RFR；已有具理由的人工 RFR 時不覆寫。產生完成後返回報告紀錄並直接提供下載。
- 中文版 1440×1000、1024×900、390×844 共 30 頁面／viewport inspections，無水平溢出、殘留的核心英文操作標籤或舊術語「管理員評論」。

本次按年份 NAV／報告頁評論 UX 已以 commit `0cde04b` 推送至 GitHub `main` 並部署至 production。部署後重新通過 migration check、三個容器 healthcheck、公開 health/readiness，以及一次性 QA 帳號的登入、基金首頁、NAV 輸入頁與報告評論頁檢查；QA 帳號已於檢查後刪除。

2026-07-20 後續修正讓 NAV 已追到最近完成月份時仍保留完整年份／月份清單；當時使用獨立編輯入口。該入口已於 2026-07-21 被同表格直接修改流程取代。

## 外部驗證限制

- 本機 Docker engine 仍因外部 Windows/WSL 問題無法使用；未修改主機設定。相同 image/build/runtime 已在 Contabo Ubuntu VPS 實際通過，因此不再阻礙 repository completion。
- 本機無 LibreOffice，真實 LibreOffice pytest integration skip；VPS production image 的 LibreOffice DOCX→PDF smoke 已通過。
- 本機 PDF 以可用 Word COM 唯讀匯出供視覺 QA，非 production dependency。

## 年度 NAV 儀表板（2026-07-20）

- 已把登入後的 NAV 輸入／歷史頁重整為按年份排列的專業基金管理儀表板；保留既有新增月份、編輯 NAV、異常變動確認、報告入口及稽核流程。
- 每個年度顯示最新 NAV、FY／YTD／期間回報、年度最高及最低 NAV、月回報、累積回報，以及由伺服器產生的內嵌折線圖。
- 權威顯示計算使用 `Decimal`；NAV 顯示及一般輸入統一為 2 位小數，百分比顯示正負號及 2 位小數。上一年度 12 月基準缺少時會使用當年首筆 NAV 並明確提示，首筆回報維持「—」。
- 圖表由 authenticated、`private, no-store` 的 PNG endpoint 即時提供；桌面及手機分別使用橫向／直向版面，不依賴前端 JavaScript 或公共 CDN。
- 響應式版面已於 1440×1000、1024×900、390×844、360×800 實際檢查：無水平溢位，390px 顯示 2 欄摘要，360px 顯示 1 欄摘要，月資料轉為可讀卡片，編輯目標至少 44px。
- 年度 NAV 儀表板功能 commits `75d32fb`、`ef04eef` 已推送至 GitHub `main` 並部署至 production。VPS image build、migration、三個容器 healthcheck、Django deployment check、LibreOffice DOCX/PDF smoke、公開 health/readiness、未登入保護及一次性帳號 authenticated smoke 均通過；一次性帳號已刪除，未修改 NAV 資料。
