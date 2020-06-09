# -*- coding: utf-8 -*-

"""
This file is a template for config.py, the file containing the web 
configuration.
"""

import os.path
# path to www index.py
index_path = "/index.py?p=%(page)s&%(args)s"
# path to the www static directory
static_path = "/static/"
# path to the local base directory
base_path = os.path.expanduser("~tools.pb/pb/web/")
# path to the logging directory
log_path = os.path.expanduser("~tools.pb/log/pb")
# path to the database conf file
db_conf_file = os.path.expanduser("~/replica.pb-db.cnf")
# database
# Due to the outage of c2.labsdb, I created a new database on tools-db with the
# backup as of 2016-02-14.
# db_name = "p50380g50752__pb"
db_name = "s51344__pb"
