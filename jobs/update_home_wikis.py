#! /usr/bin/python
# -*- coding: utf-8 -*-
import sys
sys.path.append('/data/project/pb/www/python/src')
from api import Database, setup_logger
import config
import logging

logger = logging.getLogger('pb')

if __name__ == "__main__":
    setup_logger()
    db = Database(use_replica=True, use_centralauth=True)
    try:
        # only users without an entry or with one older than home_wiki_max_age_days
        count = db.update_home_wikis(config.home_wiki_max_age_days)
    finally:
        db.close_connections()
    logger.info('Run completed, home wikis of %d users checked', count)
