#!/bin/bash

OUTPUT_DIR="/data/project/pb/public_html/sql-dumps"
TODAY=`date +%F`
OUTPUT_FILE=wppb-$TODAY.sql.bz2

mysqldump --defaults-file="/data/project/pb/replica.my.cnf" -h tools-db "s51344__pb" | bzip2 > "$OUTPUT_DIR/$OUTPUT_FILE"

