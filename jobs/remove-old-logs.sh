#!/bin/bash

LOG_DIR="/data/project/pb/logs"

find -path "$LOG_DIR/*" -mtime +31 -exec rm {} \;

