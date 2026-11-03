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
# Global rename log on Meta, for the admin page "vanished accounts" (web/admin_api.py)
meta_replica_host = os.environ.get('PB_META_REPLICA_HOST', 'metawiki.web.db.svc.wikimedia.cloud')
meta_replica_db_name = os.environ.get('PB_META_REPLICA_DB_NAME', 'metawiki_p')

# Admin area (web/admin.py): login with OAuth 2.0 on Meta. The secrets are Toolforge envvars,
# without them the admin area is disabled.
secret_key = os.environ.get('PB_SECRET_KEY')
oauth_client_id = os.environ.get('PB_OAUTH_CLIENT_ID')
oauth_client_secret = os.environ.get('PB_OAUTH_CLIENT_SECRET')
oauth_base_url = os.environ.get('PB_OAUTH_BASE_URL', 'https://meta.wikimedia.org/w/rest.php/oauth2')
# global user names (SUL) of the admins, separated by commas
admins = [name.strip() for name in os.environ.get('PB_ADMINS', 'Euku,Wiegels').split(',') if name.strip()]
# the session cookie is only sent over HTTPS (switched off for local tests over plain HTTP)
session_cookie_secure = os.environ.get('PB_SESSION_COOKIE_SECURE', '1') == '1'
admin_session_hours = int(os.environ.get('PB_ADMIN_SESSION_HOURS', '12'))
# job definitions and log files for the admin page "jobs"
jobs_file = os.environ.get('PB_JOBS_FILE', os.path.join(os.path.dirname(os.path.dirname(os.path.realpath(__file__))),
                                                        'jobs', 'toolforge-jobs.yaml'))
log_dir = os.environ.get('PB_LOG_DIR', '/data/project/pb/logs')
