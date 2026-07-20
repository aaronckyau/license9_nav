# Operations and Deployment

## Production checklist

1. 建立專用 Linux 使用者與部署目錄；只讓該使用者可讀 `.env`（`chmod 600 .env`）。
2. 產生長且隨機的 `DJANGO_SECRET_KEY`、PostgreSQL 密碼；設定正確 host/origin。
3. 保持 `BIND_ADDRESS=127.0.0.1`，由 Caddy/Nginx/負載平衡器終止 TLS；傳遞 `Host`、`X-Forwarded-Proto`。
4. TLS 完成後設定 secure cookies、SSL redirect 與適合的 HSTS，再逐步提高 `SECURE_HSTS_SECONDS`。
5. 防火牆只開 SSH/HTTP/HTTPS；Compose database 位於 internal network 且沒有 host port。
6. 啟動後執行 `/readyz`、登入、RFR provider test、DOCX/PDF smoke、受保護下載測試。

## Startup and diagnostics

```bash
docker compose up --build -d
docker compose ps
docker compose logs --tail=200 web
curl --fail http://127.0.0.1:8000/readyz
docker compose exec web python manage.py check --deploy
docker compose exec web /app/scripts/smoke_report.sh
```

`healthz` 只證明 process 回應；`readyz` 也執行 database `SELECT 1`。Gunicorn、Django 與 Nginx logs 都寫 stdout/stderr。

## Backup

每日備份 PostgreSQL 與 media，至少保留 7 日 daily、4 週 weekly、12 個月 monthly；把副本加密送到另一個故障域並定期做 restore drill。

```bash
scripts/backup.sh backups
sha256sum backups/*
```

資料庫 dump 與 media tar 必須視為同一個 restore point；檔名 UTC timestamp 應配對。備份 `.env` 的安全副本但不可與一般 artifact 公開存放。

## Restore

先停止寫入並做事故前備份。restore script 需明確 acknowledgement；對非空 DB 的完整災難復原，建議先建立乾淨資料庫/volume，再匯入 dump。

```bash
docker compose up -d db web
CONFIRM_RESTORE=YES scripts/restore.sh backups/db-20260717T000000Z.sql.gz
docker compose exec -T web tar -xzf - -C /app/media < backups/media-20260717T000000Z.tar.gz
docker compose restart web
curl --fail http://127.0.0.1:8000/readyz
docker compose exec web python manage.py check
```

驗證 fund/report counts、最近 finalized report 的 DOCX/PDF hash 與登入下載。

## Upgrade and rollback

升級前備份；`docker compose build --pull` 後 `docker compose up -d`。entrypoint 執行 migration/collectstatic。完成 ready/smoke/business checks 才關閉舊維護窗口。若 migration 向後不相容，不可只退 image；使用已測試的 reverse migration 或從升級前 DB+media backup 完整還原。

## Generated files and temporary cleanup

正式 DOCX/PDF 是報告版本的 immutable artifact，不做自動刪除。LibreOffice temporary user profile 與 HTML preview chart 使用 scoped temporary directory，自動清除。失敗生成可能留下未登記的 `nav-chart.png`/DOCX 在該 draft version directory；每月可在備份後比對 `GeneratedFile.storage_path` 清理 30 日以上且沒有 DB metadata 的 orphan，絕不可刪除 finalized/stale report directory。

## Incident notes

- FRED 故障：測試 Treasury fallback；必要時用有理由的 manual override，不得任意補值。
- PDF 失敗：檢查 `soffice --version`、container logs、media volume 空間與 permissions；狀態會保留為 `GENERATION_FAILED`。
- Stale report：不要覆寫舊 artifact；檢視 NAV audit，建立新 report version、重新生成與 finalization。
