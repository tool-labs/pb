#!/bin/bash
OUTPUT_DIR="/data/project/pb/www/python/src/sql-dumps"
TODAY=`date +%F`
OUTPUT_FILE=wppb-$TODAY.sql.bz2
TIMESTAMP=`date +"%F_%H-%M"`
echo "== [$TIMESTAMP] =="
mariadb-dump --defaults-file=~/replica.my.cnf --host=tools.db.svc.wikimedia.cloud "s51344__pb" | bzip2 > "$OUTPUT_DIR/$OUTPUT_FILE"