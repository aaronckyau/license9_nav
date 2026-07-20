# Custom DOCX Template Guide

上傳格式必須是有效 `.docx`（Open XML ZIP package），小於設定的 `MAX_UPLOAD_BYTES`，MIME 類型需符合 DOCX。模板不得包含指向 Excel/OLE 的 `TargetMode="External"` relationship。

## Required placeholders

- `{{ fund_name }}`
- `{{ report_quarter }}`
- `{{ report_date }}`
- `{% for row in quarterly_rows %} ... {% endfor %}`（package 內必須含 `quarterly_rows`）
- `{{ nav_chart }}`
- `{{ manager_commentary }}`
- `{{ disclaimer }}`

Optional context: `share_class`, `investment_objective`, `strategy_highlights`, `fund_statistics`, `general_information`, `contacts`。

`quarterly_rows` 每列含 `year`, `q1`, `q2`, `q3`, `q4`, `ytd`。`fund_statistics` 是 metric-key 到顯示值的 mapping。`nav_chart` 是 `docxtpl.InlineImage`，應獨立放在 paragraph/cell。

## Authoring rules

- 使用 Docker 已安裝的 Carlito、Liberation Sans 或 DejaVu 字型。
- A4、適當 margins、表格 repeated header；不要指定固定 row height。
- Jinja tag 必須保持在同一個 Word run，避免 Word 拆開 placeholder。
- 不要 paste/link Excel chart；只使用 `nav_chart`。
- 先以測試 fund 上傳、產生並開啟 DOCX/PDF，再套到正式 fund。

上傳時會先檢查 package、必要 placeholder、MIME 與外部 Excel link；產生後再次掃描 relationship，錯誤會明確記錄為 generation failed，不會產生可 finalization 的檔案。
