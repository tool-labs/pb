#!/bin/bash

LOG_DIR="/data/project/pb/log"

find -path "$LOG_DIR/*.log" -mtime +1 -exec rm {} \;

