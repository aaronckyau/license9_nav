# NAV Quarterly Report App

內部多基金 NAV 季報系統。基金完成設定後，一般使用者只需依「選擇基金 → 輸入月份、NAV 與基金經理評論 → 產生報告」三步完成月結；系統自動取得 RFR、執行 `legacy_excel_v1` 計算並產生有版本的 DOCX/PDF。基金設定、績效檢查、手動 RFR、預覽及定稿仍保留在進階頁面；Django Admin 僅供受信任的系統管理與資料修正。

## 本機啟動（Windows PowerShell）

需求為 Python 3.12。本機可不安裝 Docker 或 LibreOffice；Microsoft Word/WPS 相容 COM 僅用於本次唯讀 PDF 視覺 QA，不是應用依賴。

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
.\.venv\Scripts\python.exe manage.py migrate
.\.venv\Scripts\python.exe manage.py createsuperuser
.\.venv\Scripts\python.exe manage.py seed_demo
.\.venv\Scripts\python.exe manage.py runserver
```

開啟 `http://127.0.0.1:8000/`。`/healthz` 檢查應用程序；`/readyz` 另檢查資料庫。

## 首位管理員

互動方式：

```bash
docker compose exec web python manage.py createsuperuser
```

自動化方式：在 `.env` 設定 `DJANGO_SUPERUSER_USERNAME`、`DJANGO_SUPERUSER_EMAIL`、`DJANGO_SUPERUSER_PASSWORD`，再執行：

```bash
docker compose exec web python manage.py bootstrap_admin
```

此命令冪等；既有帳號不會被改密碼。專案不附預設帳密。

## Docker Compose / VPS

目前 production 已部署於 `https://www.4mstrategy.com/nav/`，VPS checkout 為 `/root/apps/license9_nav`，Compose 對 host 只綁定 `127.0.0.1:5430`。以下仍保留可攜式首次部署流程；正式環境細節見 `docs/ENGINEERING_HANDOVER.md`。

```bash
cp .env.example .env
# 填入真實 secret、密碼、host、HTTPS origin 與安全設定
docker compose --env-file .env config --quiet
docker compose build --pull web
docker compose up -d db
docker compose run --rm web python manage.py migrate --noinput
docker compose up -d
docker compose ps
curl --fail -H 'X-Forwarded-Proto: https' http://127.0.0.1:8000/readyz
docker compose exec web python manage.py check --deploy
docker compose exec web /app/scripts/smoke_report.sh
```

Compose 預設只綁定 `127.0.0.1:8000`；由 VPS 上的 TLS reverse proxy 對外服務。PostgreSQL 不暴露 host port，正式 DOCX/PDF 只能經登入保護的 Django download view 取得。

## XSQ 匯入與樣本報表

```bash
python manage.py seed_demo --skip-nav
python manage.py import_legacy_xsq --file reference/xsq_nav_history.xlsx --dry-run
python manage.py import_legacy_xsq --file reference/xsq_nav_history.xlsx --commit --confirm-first-period
python manage.py generate_sample_report
python scripts/inspect_docx.py media/reports/1/v1/quarterly-report.docx
```

樣本成品位於 `artifacts/sample-reports/`；逐頁渲染及 UI 證據位於 `artifacts/report-render/`、`artifacts/visual-qa/` 與 `artifacts/simple-workflow-qa/`。

## 品質閘門

```bash
ruff check .
ruff format --check .
python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py migrate --check
pytest -q
```

CI 位於 `.github/workflows/ci.yml`，在 Ubuntu 安裝 LibreOffice 並額外執行真實 DOCX→PDF smoke 與 DOCX package audit。

## 文件

- [架構](docs/ARCHITECTURE.md)
- [計算方法](docs/CALCULATION_METHODOLOGY.md)
- [舊 Excel 公式差異](docs/FORMULA_DIFFERENCES.md)
- [RFR 方法](docs/RFR_METHODOLOGY.md)
- [報表生成](docs/REPORT_GENERATION.md)
- [VPS 部署](docs/DEPLOYMENT_VPS.md)
- [備份還原](docs/BACKUP_RESTORE.md)
- [使用指南](docs/USER_GUIDE.md)
- [測試報告](docs/TEST_REPORT.md)
- [已知限制](docs/KNOWN_LIMITATIONS.md)
- [工程交接](docs/ENGINEERING_HANDOVER.md)
