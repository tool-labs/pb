#!/bin/bash
# Deletes SQL dumps older than 31 days and old webserver logs.
set -euo pipefail

OUTPUT_DIR="/data/project/pb/www/python/src/sql-dumps"
KEEP_DAYS=31

# Safety net: only delete old dumps if a recent one exists, so a broken
# dump job does not slowly remove all backups.
if [ -z "$(find "$OUTPUT_DIR"/ -maxdepth 1 -type f -name 'wppb-*.sql.bz2*' -mtime -3 -size +100k)" ]; then
    echo "No dump younger than 3 days found in $OUTPUT_DIR, not deleting anything." >&2
    exit 1
fi

find "$OUTPUT_DIR"/ -maxdepth 1 -type f -name 'wppb-*.sql.bz2*' -mtime +$KEEP_DAYS -print -delete

# Also delete the old webserver logs
find /data/project/pb/ -maxdepth 1 -type f -name "uwsgi.log.*" -mtime +14 -print -delete
