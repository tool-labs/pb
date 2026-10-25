#!/bin/bash
# The job starts this script with `sh` (dash); re-run it with bash.
[ -z "$BASH_VERSION" ] && exec /bin/bash "$0" "$@"
set -euo pipefail

# Full dump of the pb database, bzip2-compressed and encrypted with the key
# in KEY_FILE (known to the maintainers). Published under /sql-dumps as an
# external backup. Decrypt with:
#   openssl enc -d -aes-256-cbc -pbkdf2 -iter 200000 -pass file:KEY_FILE \
#     -in wppb-YYYY-MM-DD.sql.bz2.enc | bunzip2 > wppb.sql
OUTPUT_DIR="/data/project/pb/www/python/src/sql-dumps"
KEY_FILE="/data/project/pb/.sql-dump-key"
MIN_SIZE=100000
TODAY=$(date +%F)
OUTPUT_FILE="wppb-$TODAY.sql.bz2.enc"
TMP_FILE="$OUTPUT_DIR/.$OUTPUT_FILE.tmp"
TIMESTAMP=$(date +"%F_%H-%M")
echo "== [$TIMESTAMP] =="

trap 'rm -f "$TMP_FILE"' EXIT
mariadb-dump --defaults-file=~/replica.my.cnf --host=tools.db.svc.wikimedia.cloud "s51344__pb" \
    | bzip2 \
    | openssl enc -aes-256-cbc -pbkdf2 -iter 200000 -salt -pass "file:$KEY_FILE" -out "$TMP_FILE"

SIZE=$(stat -c %s "$TMP_FILE")
if [ "$SIZE" -lt "$MIN_SIZE" ]; then
    echo "Dump too small ($SIZE bytes), not published" >&2
    exit 1
fi
chmod 644 "$TMP_FILE"
mv "$TMP_FILE" "$OUTPUT_DIR/$OUTPUT_FILE"
echo "$OUTPUT_FILE: $SIZE bytes"
