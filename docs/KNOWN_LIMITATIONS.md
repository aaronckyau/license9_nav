# Known Limitations

1. 本 Windows 主機的 Docker Desktop/WSL engine 因外部 `Wsl/CallMsi/Install/REGDB_E_CLASSNOTREG` 無法使用；未執行本機 image build/container smoke。本工作沒有修改 Windows、WSL、Docker Desktop、registry、MSI、BIOS 或 virtualization。Compose config、Dockerfile/build-context、health、volume、Nginx、startup 已靜態審查；Ubuntu CI 承接真實 build/runtime。
2. 本機沒有 LibreOffice，因此 pytest 的真實 `soffice` integration test skip。Production image 與 CI 明確安裝 `libreoffice-writer`，production PDF 仍只依賴 LibreOffice。
3. 本機 `Word.Application` COM 匯出的 PDF metadata Creator 顯示 `WPS Docs`，反映主機 Office 相容層；只作唯讀視覺 QA，不是 production dependency。
4. FRED provider 需要有效 `FRED_API_KEY`；無 key 可使用官方 U.S. Treasury provider。外部服務 outage 時必須採有理由 manual override，不會自動猜值。
5. MVP 是單一 share class 一份 report；不含 multi-class consolidated report、approval chain、object storage、SSO 或 queue worker。
6. PDF/A、digital signature、screen-reader tagged PDF 不在 MVP 定義；DOCX/PDF 已做 package、layout、hash 與可開啟性驗證。
7. 目前目錄不是 Git working tree，因此無 commit history、branch、diff baseline 或 CI run URL；`.github/workflows/ci.yml` 已就緒，需先由擁有者放入正式 repository。
