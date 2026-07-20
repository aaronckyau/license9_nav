# Known Limitations

1. 本 Windows 主機的 Docker Desktop/WSL engine 因外部 `Wsl/CallMsi/Install/REGDB_E_CLASSNOTREG` 無法使用；這是外部 host validation limitation，不是應用缺陷。本工作沒有修改 Windows、WSL、Docker Desktop、registry、MSI、BIOS 或 virtualization。Compose config 已在本機通過，且相同 Docker image/build/runtime 已在 Contabo Ubuntu VPS 實際通過。
2. 本機沒有 LibreOffice，因此 pytest 的真實 `soffice` integration test skip。Production VPS image 已使用 `libreoffice-writer` 成功產生四頁 XSQ PDF；production PDF 不依賴 Microsoft Word。
3. 本機 `Word.Application` COM 匯出的 PDF metadata Creator 顯示 `WPS Docs`，反映主機 Office 相容層；只作唯讀視覺 QA，不是 production dependency。
4. FRED provider 需要有效 `FRED_API_KEY`；一般三步流程在無 key 時自動使用官方 U.S. Treasury provider。兩個官方來源均 outage 時必須採有理由 manual override，不會自動猜值。
5. MVP 是單一 share class 一份 report；不含 multi-class consolidated report、approval chain、object storage、SSO 或 queue worker。
6. PDF/A、digital signature、screen-reader tagged PDF 不在 MVP 定義；DOCX/PDF 已做 package、layout、hash 與可開啟性驗證。
7. GitHub Actions workflow 已提交；是否執行仍取決於 GitHub Actions 帳戶／repository 設定，VPS 部署不依賴本機 Docker Desktop。
8. Production HSTS 為一年但未加 `includeSubDomains`／`preload`，以免未經全域 TLS inventory 影響同 hostname hierarchy 的其他應用；`manage.py check --deploy` 因此保留 W005/W021 兩個有意識的 warning，exit code 仍為 0。
