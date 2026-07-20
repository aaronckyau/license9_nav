#!/bin/sh
set -eu

backup_dir="${1:-backups}"
timestamp="$(date -u +%Y%m%dT%H%M%SZ)"
mkdir -p "$backup_dir"
db_file="$backup_dir/db-$timestamp.sql"
docker compose exec -T db pg_dump -U "${POSTGRES_USER:-nav_app}" "${POSTGRES_DB:-nav_reports}" > "$db_file"
gzip "$db_file"
docker compose exec -T web tar -czf - -C /app/media . > "$backup_dir/media-$timestamp.tar.gz"
printf 'Database and media backups created under %s\n' "$backup_dir"
