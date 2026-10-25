#!/bin/bash
# Deletes job logs that have not been written to for more than 31 days.
set -euo pipefail

LOG_DIR="/data/project/pb/logs"

find "$LOG_DIR"/ -maxdepth 1 -type f -mtime +31 -print -delete
