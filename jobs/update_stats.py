#! /usr/bin/python
# -*- coding: utf-8 -*-
import os.path, sys
sys.path.append('/data/project/pb/pb/web/dynamic/')
import pb_db_config
sys.path.append(os.path.abspath(pb_db_config.base_path + '../pyapi'))
import wppb
import logging

logger = logging.getLogger('pb')
db = wppb.Database(database=pb_db_config.db_name)

def setup_logger():
	logFormatter = logging.Formatter('%(asctime)s - [%(levelname)-5.5s] - %(message)s')	
	consoleHandler = logging.StreamHandler()
	consoleHandler.setFormatter(logFormatter)
	consoleHandler.setLevel(logging.DEBUG)
	logger.setLevel(logging.DEBUG)
	for h in logging.getLogger().handlers:
		logging.getLogger().removeHandler(h)
	logging.getLogger().addHandler(consoleHandler)
setup_logger()

def _run_update():
    """
        Triggers database queries that fill the table 'stats_confirmations_by_month' with pregenerated data.
    """
    db.update_stats_confirmations_by_month()

if __name__ == "__main__":
    _run_update()
    logger.info('Run completed')