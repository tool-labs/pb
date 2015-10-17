# -*- coding: utf-8 -*-

"""
This file is a template for config.py, the file containing the web 
configuration.
"""

import os.path
# path to www index.py
index_path = "https://tools.wmflabs.org/pb/index.py?p=%(page)s&%(args)s"
# path to the www static directory
static_path = "https://tools.wmflabs.org/pb/static/"
# path to the local base directory
base_path = os.path.expanduser("~tools.pb/pb/web/")
# path to the logging directory
log_path = os.path.expanduser("~tools.pb/log/pb")
# path to the database conf file
db_conf_file = os.path.expanduser("~/replica.pb-db.cnf")
# database
db_name = "p50380g50752__pb"
