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
# CentralAuth replica for the home wikis of the participants (jobs/update_home_wikis.py)
centralauth_host = os.environ.get('PB_CENTRALAUTH_HOST', 'centralauth.analytics.db.svc.wikimedia.cloud')
centralauth_db_name = os.environ.get('PB_CENTRALAUTH_DB_NAME', 'centralauth_p')
# meta_p.wiki (dbname -> url), on the same server as centralauth_p
meta_db_name = os.environ.get('PB_META_DB_NAME', 'meta_p')
# the cached home wiki of a user is looked up again after this many days
home_wiki_max_age_days = int(os.environ.get('PB_HOME_WIKI_MAX_AGE_DAYS', '7'))
