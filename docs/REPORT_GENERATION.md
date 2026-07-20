# Report Generation

## 流程

1. 從 fund/share class/NAV/RFR/commentary/resolved organization settings 建立 JSON snapshot。
2. 重新計算 `legacy_excel_v1`，拒絕 duplicate、missing month、quarter gap、invalid RFR 等問題。
3. 用 Matplotlib 產生內嵌 PNG NAV chart。
4. 使用內建 python-docx generator，或已驗證 required placeholders 的 custom DOCX template。
5. 稽核 ZIP/package integrity、relationships、embedded media、table geometry、footer、metadata；拒絕 external Excel relationship。
6. 先登記 DOCX 與 SHA-256，再以隔離 LibreOffice profile headless 轉 PDF，登記 PDF/hash。
7. 只有 DOCX、PDF、snapshot 與所有 finalization checks 通過時才可 FINAL。

PDF 失敗時保留可下載/診斷 DOCX，report 狀態為 `GENERATION_FAILED`，不會假裝完整成功。

## 版面規則

- A4、Arial（Linux 映射 Liberation Sans）、固定 page margins、流動 paragraphs。
- Chart 為 embedded PNG；不得有 external Excel/chart workbook link。
- 表格寬度明確、header repeat、無 fixed row height，避免文字/負百分比截斷。
- 基金經理評論自動跨頁，作者與最後一段保持同頁。
- General Information 與 Disclaimer 各自 new page；Disclaimer 使用專業 10pt/1.15 legal layout。
- default/even/first footer 一致顯示 fund code、report ID、period/version、generation time、page field。
- core metadata 包含 title、subject、author、formula/report/version/snapshot provenance。

## 驗證命令

```bash
python manage.py generate_sample_report
python scripts/inspect_docx.py artifacts/sample-reports/XSQ_2026_Q1_Quarterly_Report.docx \
  --output artifacts/sample-reports/XSQ_2026_Q1_DOCX_Audit.json
```

結構 audit 結果：valid、2 個 embedded media/drawings、0 external relationship、0 embedded spreadsheet、0 missing target、0 fixed row height，四張表寬度皆 9864 dxa。Word COM PDF 為 4 頁 A4；18 段長評論 QA 為 6 頁 A4，逐頁 PNG 位於 `artifacts/report-render/`。

Production 唯一 PDF runtime 是 Linux image 內 `soffice`。Word/WPS COM 僅為此 Windows 主機的唯讀視覺驗證，沒有出現在 production code 或 dependencies。
