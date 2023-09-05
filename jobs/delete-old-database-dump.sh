#!/bin/bash

OUTPUT_DIR="/data/project/pb/www/python/src/sql-dumps"
OLDATE=`date +%F -d "-31 days"`
OUTPUT_FILE="wppb-$OLDATE*"
rm -f $OUTPUT_DIR/$OUTPUT_FILE
