# Engineering Handover

## 交付摘要

MVP 已完成並通過本機可執行的 application、calculation、import、RFR、report、security、browser 與 artifact checks。主流程是自訂頁面 `Select Fund → Fund Setup → Enter NAV → Review Performance → Manager Commentary → Preview → Generate Report`；Admin 只作 trusted correction。

## Runtime 與入口

- Django 5.2 / Python 3.12，production PostgreSQL 17、Gunicorn、Nginx、LibreOffice。
- 本機：`.\.venv\Scripts\python.exe manage.py runserver`。
- Health：`/healthz`；readiness（含 DB）：`/readyz`。
- 登入：`/accounts/login/`；Admin：`/admin/`。
- Normal workflow routes 由 `navapp/urls.py` 定義。

## 首次資料與登入

專案沒有預設密碼。互動 bootstrap：`python manage.py createsuperuser`。自動 bootstrap：設定 `DJANGO_SUPERUSER_USERNAME`、`DJANGO_SUPERUSER_EMAIL`、`DJANGO_SUPERUSER_PASSWORD` 後執行 `python manage.py bootstrap_admin`；既有帳號不改密碼。

XSQ demo：

```bash
python manage.py seed_demo
python manage.py generate_sample_report
```

## VPS 精確命令

```bash
cd /opt/monthly_nav
cp .env.example .env
chmod 600 .env
docker compose --env-file .env config --quiet
docker compose build --pull web
docker compose up -d db
docker compose run --rm web python manage.py migrate --noinput
docker compose up -d
docker compose ps
curl --fail http://127.0.0.1:8000/readyz
docker compose exec web python manage.py check --deploy
docker compose exec web python manage.py bootstrap_admin
docker compose exec web /app/scripts/smoke_report.sh
```

必要 `.env`：`DJANGO_SECRET_KEY`、`ALLOWED_HOSTS`、`CSRF_TRUSTED_ORIGINS`、`POSTGRES_DB`、`POSTGRES_USER`、`POSTGRES_PASSWORD`；HTTPS production 另必須正確設定 secure cookies、SSL redirect、HSTS。完整表見 `DEPLOYMENT_VPS.md`。

## Backup/restore

```bash
scripts/backup.sh backups
CONFIRM_RESTORE=YES scripts/restore.sh \
  backups/db-YYYYMMDDTHHMMSSZ.sql.gz \
  backups/media-YYYYMMDDTHHMMSSZ.tar.gz
docker compose restart web
curl --fail http://127.0.0.1:8000/readyz
```

DB/media 必須同一 timestamp 並做 off-site encrypted copy；還原後核對 counts、登入下載與 `GeneratedFile.sha256`。

## 重要不變條件

- 不要把金融計算改成 float；不要只為顯示精度修改 raw values。
- 不要改名或覆寫 `legacy_excel_v1`，除非刻意新增新 formula version。
- 不要把 Excel cell references 寫入 service；maximum drawdown 必須 running peak。
- 不要讓 RFR observation 超過 report end。
- 不要公開 `/media/`，也不要把 external Excel relationships 放入 DOCX。
- FINAL/STALE report 不可改；來源更正後建立新 version。

## 驗證與 artifacts

全套結果：32 passed、1 local-LibreOffice skip；Ruff/Django/migrations/deploy check/Compose config PASS。XSQ DOCX/PDF 在 `artifacts/sample-reports/`；四頁與長評論六頁 render 在 `artifacts/report-render/`；36 張 UI screenshots/contact sheets/JSON 在 `artifacts/visual-qa/`。

## 下一個環境步驟

把目錄納入正式 Git repository，讓 `.github/workflows/ci.yml` 在 Ubuntu 跑完 LibreOffice report smoke；之後在 staging VPS 執行上述 Compose 命令、TLS/proxy、restore drill 與登入下載驗證。這是環境交付，不需再改 MVP 架構。
