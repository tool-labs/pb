#! /usr/bin/python
# -*- coding: utf-8 -*-
import sys
sys.path.append('/data/project/pb/www/python/src')
from api import Database, setup_logger
import logging

logger = logging.getLogger('pb')

def _run_update(db):
    """
        Triggers database queries that fill the table 'stats_confirmations_by_month' with pregenerated data.
    """
    db.update_stats_confirmations_by_month()

if __name__ == "__main__":
    setup_logger()
    _run_update(Database(use_replica=False))
    logger.info('Run completed')