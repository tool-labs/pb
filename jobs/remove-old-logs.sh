#!/bin/bash

LOG_DIR="/data/project/pb/log/pb"

find -path "$LOG_DIR/*.txt" -mtime +1 -exec rm {} \;

