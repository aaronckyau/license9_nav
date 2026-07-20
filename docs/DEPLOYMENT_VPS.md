# VPS Deployment

以下假設 Ubuntu VPS 已安裝 Docker Engine 與 Compose plugin、DNS/TLS reverse proxy 已規劃。Compose 內 Nginx 預設只綁 `127.0.0.1:8000`；不要直接公開 PostgreSQL 或 Django。

## 首次部署

```bash
sudo install -d -o "$USER" -g "$USER" /opt/monthly_nav
cd /opt/monthly_nav
git clone YOUR_REPOSITORY_URL .
cp .env.example .env
chmod 600 .env
# 編輯 .env；至少填入 secret、DB password、host、HTTPS origin、安全 cookies/HSTS
docker compose --env-file .env config --quiet
docker compose build --pull web
docker compose up -d db
docker compose run --rm web python manage.py migrate --noinput
docker compose up -d
docker compose ps
curl --fail -H 'X-Forwarded-Proto: https' http://127.0.0.1:8000/healthz
curl --fail -H 'X-Forwarded-Proto: https' http://127.0.0.1:8000/readyz
docker compose exec web python manage.py check --deploy
docker compose exec web python manage.py bootstrap_admin
docker compose exec web /app/scripts/smoke_report.sh
```

`entrypoint.sh` 在每次 web 啟動先執行 `migrate --noinput` 與 `collectstatic --noinput`。上面的顯式 migration 讓首次部署錯誤在正式 web 切換前可見。

## 必要環境變數

| 變數 | 說明 |
|---|---|
| `DJANGO_SECRET_KEY` | 長隨機 secret；不可用範例值 |
| `ALLOWED_HOSTS` | 逗號分隔正式 hostname |
| `CSRF_TRUSTED_ORIGINS` | 完整 HTTPS origins |
| `POSTGRES_DB`、`POSTGRES_USER`、`POSTGRES_PASSWORD` | DB credentials；密碼可含特殊字元，Compose 不再拼 URL |
| `TIME_ZONE` | 預設 `Asia/Hong_Kong` |
| `SESSION_COOKIE_SECURE`、`CSRF_COOKIE_SECURE` | HTTPS production 為 `true` |
| `SECURE_SSL_REDIRECT` | TLS proxy 正確後為 `true` |
| `SECURE_HSTS_SECONDS`、`SECURE_HSTS_INCLUDE_SUBDOMAINS`、`SECURE_HSTS_PRELOAD` | 先短期驗證再逐步提高 |
| `BIND_ADDRESS`、`HTTP_PORT` | 預設 `127.0.0.1:8000` |
| `FORCE_SCRIPT_NAME` | 部署於 path prefix 時設定，例如 `/nav` |
| `SESSION_COOKIE_NAME`、`CSRF_COOKIE_NAME` | 同 hostname 多應用時使用專屬 cookie 名稱 |

`DJANGO_DEBUG` 由 Compose 強制 `false`。可選變數：`FRED_API_KEY`、`RFR_HTTP_TIMEOUT`、`REPORT_CONVERSION_TIMEOUT`、`LIBREOFFICE_BINARY`、`MAX_UPLOAD_BYTES`、`LOG_LEVEL`、`SESSION_COOKIE_AGE`。`DATABASE_URL` 只供非 Compose 部署，credentials 必須 URL encode。

## Reverse proxy

外層 Caddy/Nginx 終止 TLS，再代理至 loopback port，必須傳遞 `Host`、`X-Forwarded-For`、`X-Forwarded-Proto=https`。Path-prefix 部署必須讓 trailing-slash `proxy_pass` 移除公開 prefix：

```nginx
location = /nav { return 301 /nav/; }
location ^~ /nav/ {
    proxy_pass http://127.0.0.1:5430/;
    proxy_set_header Host $host;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
    proxy_set_header X-Forwarded-Prefix /nav;
}
```

此模式同時要求 `.env` 設定 `FORCE_SCRIPT_NAME=/nav`、專屬 cookie names、`HTTP_PORT=5430`。公司內部系統建議另以 VPN、identity-aware proxy 或 IP allow-list 限制來源。

## 升級

```bash
cd /opt/monthly_nav
scripts/backup.sh backups
git pull --ff-only
docker compose build --pull web
docker compose up -d
docker compose ps
curl --fail -H 'X-Forwarded-Proto: https' http://127.0.0.1:8000/readyz
docker compose exec web python manage.py check --deploy
docker compose exec web /app/scripts/smoke_report.sh
```

若 migration 不向後相容，不可只退 image；使用測試過的 reverse migration，或依 `BACKUP_RESTORE.md` 還原同一時間點的 DB+media。

## 靜態驗證結果

`docker compose --env-file .env.example config --quiet` 通過。Dockerfile 使用 Python 3.12 slim、non-root UID 10001、LibreOffice/fonts/Poppler、writable named volumes；`.dockerignore` 採白名單防止 `.env`、SQLite、artifacts、backups、`.venv` 進 build context。DB 有 `pg_isready`、web `/readyz`、Nginx `/healthz` health checks（HTTPS-aware forwarding header），DB 位於 internal network，Nginx 等待 web ready。2026-07-20 已在 Contabo Ubuntu 實際完成 image build、三服務健康檢查、migration、LibreOffice DOCX/PDF smoke 與 `/nav` 公開驗證。
