# -*- coding: utf-8 -*-
"""
    This file contains the web configuration.

    Every setting can be overridden by an environment variable (used by the
    tests and for local development). The defaults are the Toolforge values.
"""
import os
import os.path
# path to the local base directory
base_path = os.path.expanduser("~tools.pb/pb/web/")
sql_dump_folder = os.environ.get('PB_SQL_DUMP_FOLDER', '/data/project/pb/www/python/src/sql-dumps')
db_conf_file = os.environ.get('PB_DB_CONF_FILE', os.path.expanduser("~/replica.pb-db.cnf"))
db_host = os.environ.get('PB_DB_HOST', 'tools.db.svc.wikimedia.cloud')
db_port = int(os.environ.get('PB_DB_PORT', '3306'))
db_name = os.environ.get('PB_DB_NAME', "s51344__pb")
replica_db_name = os.environ.get('PB_REPLICA_DB_NAME', 'dewiki_p')
