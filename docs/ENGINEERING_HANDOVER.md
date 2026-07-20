# Engineering Handover

## 交付摘要

MVP 基線已推送 GitHub 並部署至 `https://www.4mstrategy.com/nav/`，通過本機應用程式、計算、匯入、RFR、瀏覽器及產物檢查，以及 VPS production Docker／LibreOffice／公開端點 smoke test。最新本地版本把正常月結收斂為「選擇基金 → 輸入月份、NAV 及基金經理評論 → 產生報告」三步；設定、績效、人工 RFR、預覽及定稿保留為進階控制。Django Admin 只供受信任的資料修正人員使用。此最新變更須在取得明確授權後再 push／deploy。

## Runtime 與入口

- Django 5.2 / Python 3.12，production PostgreSQL 17、Gunicorn、Nginx、LibreOffice。
- 本機：`.\.venv\Scripts\python.exe manage.py runserver`。
- Health：`/healthz`；readiness（含 DB）：`/readyz`。
- 登入：`/accounts/login/`；Admin：`/admin/`。
- Production 公開 prefix：`/nav`；VPS loopback：`127.0.0.1:5430`。
- Normal workflow routes 由 `navapp/urls.py` 定義。

## 首次資料與登入

通用部署沒有硬編碼預設密碼。互動 bootstrap：`python manage.py createsuperuser`。自動 bootstrap：設定 `DJANGO_SUPERUSER_USERNAME`、`DJANGO_SUPERUSER_EMAIL`、`DJANGO_SUPERUSER_PASSWORD` 後執行 `python manage.py bootstrap_admin`；既有帳號不改密碼。現有 VPS username 是 `admin`，初始密碼只存於 root-only `/root/.license9_nav_admin_password`，首次登入後必須更改。

XSQ demo：

```bash
python manage.py seed_demo
python manage.py generate_sample_report
```

## VPS 精確命令

```bash
cd /root/apps/license9_nav
git pull --ff-only origin main
docker compose --env-file .env config --quiet
docker compose --env-file .env build --pull web
docker compose --env-file .env up -d
docker compose --env-file .env ps
curl --fail -H 'Host: www.4mstrategy.com' -H 'X-Forwarded-Proto: https' http://127.0.0.1:5430/readyz
docker compose --env-file .env exec -T web python manage.py check --deploy
docker compose --env-file .env exec -T web python manage.py seed_demo
docker compose --env-file .env exec -T web /app/scripts/smoke_report.sh
curl --fail https://www.4mstrategy.com/nav/healthz
curl --fail https://www.4mstrategy.com/nav/readyz
```

必要 `.env`：`DJANGO_SECRET_KEY`、`ALLOWED_HOSTS`、`CSRF_TRUSTED_ORIGINS`、`FORCE_SCRIPT_NAME=/nav`、`SESSION_COOKIE_NAME=nav_sessionid`、`CSRF_COOKIE_NAME=nav_csrftoken`、PostgreSQL 三項、`BIND_ADDRESS=127.0.0.1`、`HTTP_PORT=5430`；HTTPS production 另必須設定 secure cookies、SSL redirect、HSTS。完整表見 `DEPLOYMENT_VPS.md`。

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

全套結果：33 passed、1 local-LibreOffice skip；Ruff/Django/migrations/deploy check/Compose config PASS；VPS image build、三個 healthy containers、LibreOffice report smoke、公開 login/logout PASS。XSQ DOCX/PDF 在 `artifacts/sample-reports/`；VPS copies 在 Docker media volume 的 `/app/media/reports/1/v1/`；四頁與長評論六頁 render 在 `artifacts/report-render/`；36 張 UI screenshots/contact sheets/JSON 在 `artifacts/visual-qa/`。

## Production 狀態

- GitHub：`https://github.com/aaronckyau/license9_nav`，branch `main`。
- VPS：`/root/apps/license9_nav`；public `https://www.4mstrategy.com/nav/`；部署 commit 以 `git rev-parse HEAD` 核對。
- Nginx 設定更新前備份：`/etc/nginx/sites-available/4mstrategy.com.bak.20260720T020446Z.nav-deploy`。
- 後續操作重點是首次登入更改管理員密碼、安排加密 off-site backup 及定期 restore drill；不需再改 MVP 架構。
