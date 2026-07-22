# MVP Assumptions

## 2026-07-21 NAV 輸入流程簡化

- NAV 輸入頁以年度顯示固定 1 至 12 月。使用者可在任何尚未有紀錄且不早於基金成立月份的列輸入 NAV，包括尚未結束的月份及下一年度；年度選單預設提供至系統年份的下一年。歷史年度預設收起，選取「顯示或新增年度」後展開該年度。月度及累積回報由系統在儲存 NAV 後自動計算，不能手動輸入。
- NAV 刪除採軟刪除及稽核紀錄；資料不會被實體移除，受影響的報告仍依既有規則標示為需要重新產生。一般報告操作頁只顯示目前新建或選取的報告，完整歷史資料仍保留供受信任管理用途。

最後更新：2026-07-21

1. 一般使用者網站與工程／操作文件使用繁體中文；基金名稱、代碼、幣別、公式 ID、官方資料來源、稽核 JSON 欄位及使用者輸入的報告內容保留原文。對外 DOCX/PDF 的語言仍依基金報告內容及 `report_language` 設定，不由網站介面語言自動改寫。現階段為完整繁中單語介面；若日後重新啟用英文切換，須補齊 Django message catalog。
2. Organization defaults 存於 singleton；fund 可明確覆寫。報表生成時把 resolved 值寫入 immutable snapshot。
3. 本機/測試允許 SQLite；Linux container/VPS 使用 PostgreSQL 17。
4. Valuation month 是 calendar month-end；一般年度表輸入時 valuation date 亦由系統設為該月月末。只有受信任管理員／歷史匯入可保留另有來源依據的實際日期。
5. Legacy workbook 的月初日期視為月份標籤；匯入保留 raw date、sheet/cell 並正規化月末。
6. 2022-07-07 觀察視為 2022-07 月度值；inception NAV 100 分開保留。commit 前要求 first-period acknowledgement。
7. 每個 share class/month 只能有一筆 active NAV。一般年度表直接修改時由系統使用固定理由「由年度 NAV 表直接修改。」、遞增 revision 並建立 before/after audit；使用者不需另填理由。受信任管理員的資料更正仍按內部 change-control 補充依據。
8. 異常月變動預設門檻為絕對值大於 25%；使用者可確認後保存，不會悄悄改值。
9. Custom DOCX template 是進階路徑；檢查 extension、MIME、package、大小及 required placeholders，內建 generator 永遠可用。
10. Manual RFR 輸入 published annual percentage（例如 `4.19`），計算前轉為 decimal `0.0419`。
11. 報表採 A4、Arial 相容字體、流動段落與無固定列高；長評論及 disclaimer 由 Word/LibreOffice 自動分頁。
12. Finalization 必須已有 non-empty DOCX、PDF、snapshot，且計算/RFR/commentary validations 全部通過。
13. Repository 使用 GitHub `aaronckyau/license9_nav` 的 `main` branch；VPS 只接受 fast-forward pull，部署 commit 必須可追溯。
14. Production 使用既有 `www.4mstrategy.com` TLS virtual host 的 `/nav` prefix，Compose 只綁 `127.0.0.1:5430`；未另開 firewall port。
15. 本機可用的 `Word.Application` COM 匯出回報 Creator 為 WPS Docs，視為主機 Office 相容層；production 不依賴它。
16. Windows WSL/Docker Desktop `Wsl/CallMsi/Install/REGDB_E_CLASSNOTREG` 是外部 host-level 限制；本工作不修改任何全域 Windows/WSL/Docker/registry/BIOS 設定。
17. Production 啟用一年 HSTS，但暫不啟用 `includeSubDomains` 或 `preload`，因為兩者影響同網域其他服務，須先做全域 TLS inventory；因此 `check --deploy` 保留 W005/W021 兩項已知警告。
18. 三步流程以「系統日期所屬月份之前，最近已完整結束的月份」作為可輸入上限；若系統日期正好是月末，則包含該月。以本次系統日期 2026-07-20 計算，上限為 2026 年 6 月。
19. 一般 NAV 頁按年份顯示既有月份，既有月份直接在表內修改；新增時只開放自成立月份起最早缺少的一個月份。系統以該月月末作為正式 valuation month/date，避免跳月及重複。實際估值日不同、Indicative 狀態或歷史補匯只由受信任管理員或匯入工具處理，不在一般流程顯示獨立 NAV 表單。
20. 簡化 NAV 頁每次只儲存一筆正式 NAV；基金經理評論不再附著於 NAV，而是在報告頁按報告期間獨立輸入。報告月份資料未齊時，產生動作會列出缺月，且不使用假資料補足。
21. 使用者提供的 `X Squared Capital Management LPF Quarterly Newsletter 2026Q1_draft_pending commentary.docx` 與 repository 內參考 DOCX 雜湊相同，作為報告結構及視覺設計依據。內建產生器重建相同章節層次並嵌入原生圖表圖片，不複製來源檔的外部 Excel 關聯。
22. 三步流程的官方 RFR 是自動模式：organization 選 FRED 但未設定 optional `FRED_API_KEY` 時，系統改用不需 key 的 U.S. Treasury 10-year 官方資料。操作者明確指定 FRED 時不 fallback，仍要求 key。
23. yfinance 的 `^TNX` 可作參考性 10 年期利率資料，但 yfinance 明示其未獲 Yahoo 認可且資料介面只供個人／研究用途，因此不作權威報告來源。Production 繼續使用 U.S. Treasury 官方 `BC_10YEAR`，FRED `DGS10` 為可選官方來源。
24. 一般使用者每個股份類別、報告類型及截止月份只看到一份現行報告。`DRAFT`、`READY` 或 `GENERATION_FAILED` 報告再次儲存／產生時沿用同一筆紀錄並更新輸出，不建立使用者可見版本；`FINAL`／`STALE` 維持不可修改。資料庫的 `version` 欄只保留供既有資料、稽核及定稿重現，不在一般流程顯示。
25. 年度 NAV 儀表板的首月回報優先使用上一年度 12 月 NAV 作基準。若無該筆資料，改以當年度首筆 NAV 作期間基準，頁面明確提示此 fallback，且首筆月回報及累積回報顯示「—」，不製造 0% 回報。這項規則只用於 NAV 輸入頁的展示分析，不改變 `legacy_excel_v1` 報告計算。
26. 年度 NAV 圖表只在視覺繪製時把 `Decimal` 轉為浮點座標；所有表格數值、月回報、期間回報、最高及最低 NAV 均由後端以 `Decimal` 計算，並只在展示時四捨五入至兩位小數。既有匯入資料的底層精度不因單純查看而被改寫。
27. 若進階匯入或資料修正造成兩筆 NAV 之間缺月，年度儀表板不把跨月變動標示為單月回報，而顯示「—」；累積回報仍可相對已揭露的年度基準顯示。最早缺少月份會依月份順序插入待輸入列。
28. 月報可選任何已完成月份，截止日為該月月末，期間回報為該月 NAV 除以上月 NAV 減一；季報只可選 3、6、9、12 月，既有季度表及 `legacy_excel_v1` 邏輯不變。月報與季報的基金表現區塊均顯示同一個年度／Q1–Q4／YTD 績效矩陣；矩陣仍只使用報告截止日或以前的 NAV，未完成季度不會以虛構回報補值。
29. 自訂 DOCX 範本的 `quarterly_rows` 是所有報表共用的基金表現資料契約；月報與季報均可套用同一範本，以保持版面、圖表、統計、評論及基金表現一致。首頁同截止日有多份報告時，以最近更新者作為繼續操作入口。
30. 兩位小數輸入限制適用於一般使用者的新增／修改表單。受信任的 legacy Excel／CSV 匯入仍保留來源檔原始精度，避免破壞歷史計算重現；匯入預覽及所有一般頁面只顯示四捨五入後兩位小數，底層權威計算仍使用完整 `Decimal`。
31. 一般「基金設定」頁只呈現使用者指定的基本資料、單一 Portfolio Manager 聯絡人、投資目標、策略重點及免責聲明。Currency 與 Return Basis 以基金條款保存，避免在多股份類別情況下悄悄覆寫任何 Share Class 的權威幣別或回報基準；其他進階資料仍可由受信任管理員透過 Django Admin 維護。
32. 報告建立時可選繁體中文或簡體中文，並將選擇寫入報告本身及 immutable snapshot。只本地化系統固定文字；基金名稱、機構資料、基金經理評論、免責聲明及使用者自訂 DOCX 範本內容維持原文，不作自動翻譯。
33. 2026-07-22 匯入 Boya Quant LPF 時，來源活頁簿「2026 June (monthly)」實際最新 NAV 為 2026-05，且來源日期以月初作月份標籤；系統以日曆月末建立估值月份，並在 `raw_source_date`、工作表及儲存格欄位保留來源依據。成立 NAV 100.00（2025-11-24）會建立為 2025-11 的首筆 NAV，確保 `legacy_excel_v1` 的成立以來回報可重現。
34. Boya Quant LPF 的來源月報「一般資料」列示普通合夥人為 Harmony Creek (HK) Limited，但同一份原始免責聲明提及 ARC Partners Limited。系統採用一般資料欄位作基金設定，並逐字保留來源免責聲明，不對法律文字作推斷性修訂；報告維持可供定稿，待業務確認後才可定稿。
35. Boya 2026-05 月報的基金經理評論包含簡體中文原文，因此該份報告選用 `zh-Hans` 與 Noto Sans CJK SC；此設定只決定系統固定文字及字型，不會翻譯英文、簡體中文評論或基金／法律原文。
36. 報告建立頁必須由目前報告的 `report` query parameter，或 NAV 頁帶入的 `share_class` query parameter 取得基金範圍。股份類別選單只列出該基金的 active 類別；不再提供報告文字選項。新增報告使用基金的有效 `report_language`，若舊基金保存的值不在現行選項內則安全回退為繁體中文。
