# -*- coding: utf-8 -*-

"""
This file is a template for config.py, the file containing the web 
configuration.
"""

import os.path
# path to www index.py
index_path = "http://toolserver.org/~wppb/%(page)s/%(args)s"
# path to the www static directory
static_path = "http://toolserver.org/~wppb/static/"
# path to the local base directory
base_path = os.path.expanduser("~wppb/code/p_wppb/branches/production/web/")
# path to the logging directory
log_path = os.path.expanduser("~wppb/log")
# path to the database conf file
db_conf_file = os.path.expanduser("~/.my-pb-db-prod.cnf")
# database 
db_name = "p_wppb_trunk"
