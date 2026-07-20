# Backup and Restore

資料庫 dump 與 media tar 是同一個 restore point；檔名共享 UTC timestamp。每日執行，至少保留 7 日 daily、4 週 weekly、12 個月 monthly，並將加密副本送到不同故障域。`.env` 要有獨立安全備份，不可放進一般 artifact。

## 備份

```bash
cd /opt/monthly_nav
scripts/backup.sh backups
sha256sum backups/db-*.sql.gz backups/media-*.tar.gz > backups/SHA256SUMS
```

腳本先確認 `pg_dump` 成功再 gzip，並由 web container 封裝 `/app/media`。建議排程後監控 exit code、檔案非零大小與可用空間。

## 還原演練

先在隔離 staging/全新 volumes 演練。正式事故處理先停止使用者寫入並做事故前備份。

```bash
cd /opt/monthly_nav
docker compose up -d db web
CONFIRM_RESTORE=YES scripts/restore.sh \
  backups/db-20260718T000000Z.sql.gz \
  backups/media-20260718T000000Z.tar.gz
docker compose restart web
curl --fail http://127.0.0.1:8000/readyz
docker compose exec web python manage.py check
```

`CONFIRM_RESTORE=YES` 是明確 destructive acknowledgement。只提供第一個參數時只還原 DB，不還原 media。

## 還原後驗證

```bash
docker compose exec web python manage.py shell -c \
  "from navapp.models import Fund,QuarterlyReport,GeneratedFile; print(Fund.objects.count(), QuarterlyReport.objects.count(), GeneratedFile.objects.count())"
docker compose exec web /app/scripts/smoke_report.sh
```

另登入 UI，核對最近 FINAL report、下載 DOCX/PDF，並比對 `GeneratedFile.sha256` 與實體檔案。DB/media 任何一方時間點不一致都視為還原失敗。
