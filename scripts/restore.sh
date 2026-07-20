#!/bin/sh
set -eu

if [ "${CONFIRM_RESTORE:-}" != "YES" ]; then
    printf 'Set CONFIRM_RESTORE=YES to acknowledge that restore replaces current database content.\n' >&2
    exit 2
fi
if [ "$#" -lt 1 ] || [ "$#" -gt 2 ]; then
    printf 'Usage: CONFIRM_RESTORE=YES scripts/restore.sh backup.sql.gz [media.tar.gz]\n' >&2
    exit 2
fi
gzip -dc "$1" | docker compose exec -T db psql -v ON_ERROR_STOP=1 -U "${POSTGRES_USER:-nav_app}" "${POSTGRES_DB:-nav_reports}"
if [ "$#" -eq 2 ]; then
    docker compose exec -T web tar -xzf - -C /app/media < "$2"
    printf 'Database and media restore completed.\n'
else
    printf 'Database restore completed; no media archive was supplied.\n'
fi
