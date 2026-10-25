"""
System tests: real MariaDB server, real schema (sql/scheme.sql), data written
through the bot API (web/bot_api.py) and the web app running as its own
HTTP server process.

Configuration (all tests in this directory are skipped unless PB_TEST_DB_HOST is set):
    PB_TEST_DB_HOST, PB_TEST_DB_PORT (3306), PB_TEST_DB_USER (root), PB_TEST_DB_PASSWORD ('')
    PB_TEST_DB_NAME (pb_systemtest), PB_TEST_REPLICA_DB_NAME (dewiki_systemtest)

The test databases are dropped and recreated, so never point this at ToolsDB.
"""
import os
import re
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from html.parser import HTMLParser
from pathlib import Path

import pymysql
import pytest

from tests.conftest import REPO_DIR, WEB_DIR

DB_HOST = os.environ.get('PB_TEST_DB_HOST')
DB_PORT = int(os.environ.get('PB_TEST_DB_PORT', '3306'))
DB_USER = os.environ.get('PB_TEST_DB_USER', 'root')
DB_PASSWORD = os.environ.get('PB_TEST_DB_PASSWORD', '')
DB_NAME = os.environ.get('PB_TEST_DB_NAME', 'pb_systemtest')
REPLICA_DB_NAME = os.environ.get('PB_TEST_REPLICA_DB_NAME', 'dewiki_systemtest')

SCHEMA_FILE = REPO_DIR / 'sql' / 'scheme.sql'
REPLICA_SCHEMA_FILE = Path(__file__).with_name('replica_schema.sql')

# MediaWiki user ids of the test users (the pb database reuses them)
MW_USERS = {
    'Alice': 101, 'Bob': 102, 'Carol': 103, 'Dave': 104,
    'Eve': 105, 'Mallory': 106, 'Zoë Ünicode': 107,
}


def pytest_collection_modifyitems(config, items):
    here = Path(__file__).parent
    for item in items:
        if here in Path(item.fspath).parents:
            item.add_marker(pytest.mark.system)


def connect(database=None):
    return pymysql.connect(host=DB_HOST, port=DB_PORT, user=DB_USER, password=DB_PASSWORD,
                           database=database, charset='utf8mb4', autocommit=True)


def run_sql_file(conn, path):
    sql = '\n'.join(line for line in Path(path).read_text().splitlines()
                    if not line.lstrip().startswith('--'))
    with conn.cursor() as curs:
        for statement in re.split(r';\s*(?:\n|$)', sql):
            if statement.strip():
                curs.execute(statement)


@pytest.fixture(scope='session')
def databases():
    if not DB_HOST:
        pytest.skip('system tests need a MariaDB server, set PB_TEST_DB_HOST (see README.md)')
    if DB_HOST.endswith(('wikimedia.cloud', 'wmcloud.org', 'wmflabs.org')):
        pytest.exit('refusing to drop databases on a Wikimedia server: ' + DB_HOST, returncode=2)
    conn = connect()
    with conn.cursor() as curs:
        for name in (DB_NAME, REPLICA_DB_NAME):
            curs.execute(f'DROP DATABASE IF EXISTS `{name}`')
            curs.execute(f'CREATE DATABASE `{name}` CHARACTER SET utf8mb4')
    conn.close()
    yield
    conn = connect()
    with conn.cursor() as curs:
        for name in (DB_NAME, REPLICA_DB_NAME):
            curs.execute(f'DROP DATABASE IF EXISTS `{name}`')
    conn.close()


@pytest.fixture(scope='session')
def cnf_file(tmp_path_factory):
    """A replica.my.cnf like the one Toolforge provides."""
    path = tmp_path_factory.mktemp('cnf') / 'replica.my.cnf'
    path.write_text(f"[client]\nuser = '{DB_USER}'\npassword = '{DB_PASSWORD}'\nhost = {DB_HOST}\n")
    return path


@pytest.fixture(scope='session')
def dump_folder(tmp_path_factory):
    folder = tmp_path_factory.mktemp('sql-dumps')
    (folder / 'wppb-2026-01-01.sql.bz2').write_bytes(b'BZh91AY&SY first dump')
    (folder / 'wppb-2026-01-02.sql.bz2').write_bytes(b'BZh91AY&SY second dump')
    (folder / 'notes.txt').write_text('not a dump')
    return folder


@pytest.fixture(scope='session')
def app_env(databases, cnf_file, dump_folder):
    """Environment that points config.py at the test databases."""
    env = dict(os.environ)
    env.update({
        'PB_DB_CONF_FILE': str(cnf_file),
        'PB_DB_HOST': DB_HOST,
        'PB_DB_PORT': str(DB_PORT),
        'PB_DB_NAME': DB_NAME,
        'PB_REPLICA_DB_NAME': REPLICA_DB_NAME,
        'PB_SQL_DUMP_FOLDER': str(dump_folder),
        'PYTHONPATH': str(WEB_DIR),
    })
    return env


@pytest.fixture(scope='session', autouse=True)
def in_process_config(request):
    """Point config.py at the test databases for code running inside pytest (bot API)."""
    if not DB_HOST:
        yield
        return
    app_env = request.getfixturevalue('app_env')
    import config
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(config, 'db_conf_file', app_env['PB_DB_CONF_FILE'])
        mp.setattr(config, 'db_host', DB_HOST)
        mp.setattr(config, 'db_port', DB_PORT)
        mp.setattr(config, 'db_name', DB_NAME)
        mp.setattr(config, 'replica_db_name', REPLICA_DB_NAME)
        mp.setattr(config, 'sql_dump_folder', app_env['PB_SQL_DUMP_FOLDER'])
        yield


@pytest.fixture
def bot_db(seeded):
    from bot_api import BotDatabase
    db = BotDatabase()
    yield db
    db.close_connections()


@pytest.fixture
def pb_sql(seeded):
    """Direct connection to the pb test database for checks and admin changes."""
    conn = connect(DB_NAME)
    yield conn
    conn.close()


@pytest.fixture
def replica_sql(seeded):
    conn = connect(REPLICA_DB_NAME)
    yield conn
    conn.close()


def reset_databases():
    conn = connect(DB_NAME)
    run_sql_file(conn, SCHEMA_FILE)
    conn.close()
    conn = connect(REPLICA_DB_NAME)
    with conn.cursor() as curs:
        curs.execute('DROP TABLE IF EXISTS `user`, `block_target`')
    run_sql_file(conn, REPLICA_SCHEMA_FILE)
    with conn.cursor() as curs:
        curs.executemany('INSERT INTO `user` (user_id, user_name) VALUES (%s, %s)',
                         [(uid, name.encode('utf-8')) for name, uid in MW_USERS.items()])
    conn.close()


# (certifier, certified, timestamp, comment)
SEED_CONFIRMATIONS = [
    ('Alice', 'Bob', '2008-02-20 10:00:00', 'Stammtisch [[Berlin]]'),
    ('Bob', 'Alice', '2008-02-20 10:05:00', None),
    ('Carol', 'Alice', '2008-02-21 11:00:00', 'WikiCon'),
    ('Alice', 'Carol', '2008-02-21 11:05:00', None),
    ('Bob', 'Carol', '2008-02-22 12:00:00', None),
    ('Carol', 'Bob', '2008-02-22 12:05:00', None),
    ('Dave', 'Alice', '2015-06-02 10:00:00', None),       # Alice's 3rd -> verified
    ('Alice', 'Dave', '2015-06-02 10:10:00', None),
    ('Bob', 'Dave', '2015-06-03 10:00:00', None),
    ('Carol', 'Dave', '2015-06-04 12:00:00', None),       # Dave's 3rd -> verified
    ('Eve', 'Alice', '2016-01-02 18:00:00', 'by a user who left'),
    ('Alice', 'Eve', '2016-01-02 18:05:00', None),
    ('Mallory', 'Bob', '2017-01-02 09:00:00', None),      # Bob's 3rd -> verified
    ('Alice', 'Zoë Ünicode', '2024-05-02 20:00:00', 'Sommerfest 🎉'),
    ('Carol', 'Zoë Ünicode', '2024-05-03 20:00:00', 'deleted later'),
]

SEED_USERS = [
    ('Alice', '2008-02-10 12:00:00'),
    ('Bob', '2008-02-11 12:00:00'),
    ('Carol', '2008-02-12 12:00:00'),
    ('Dave', '2015-06-01 12:00:00'),
    ('Eve', '2016-01-01 12:00:00'),
    ('Mallory', '2017-01-01 12:00:00'),
    ('Zoë Ünicode', '2024-05-01 12:00:00'),
]


@pytest.fixture(scope='module')
def seeded(app_env):
    """
    Fresh databases per test module, filled the same way SpBot does it
    (pers-bek-to-db-bot.py -> BotDatabase), plus the manual admin changes
    (hiding, banning, comments, deleting) that are done directly in SQL.
    """
    from bot_api import BotDatabase
    reset_databases()
    db = BotDatabase()
    for name, since in SEED_USERS:
        assert db.add_user(name, since), name
    for certifier, certified, stamp, comment in SEED_CONFIRMATIONS:
        certifier_id = db.get_user_by_name(certifier)[1]
        certified_id = db.get_user_by_name(certified)[1]
        assert db.add_confirmation(certifier_id, certified_id, comment, stamp)
    db.close_connections()

    conn = connect(DB_NAME)
    with conn.cursor() as curs:
        curs.execute("UPDATE user SET user_is_hidden = 1 WHERE user_name = 'Eve'")
        curs.execute("UPDATE user SET user_was_banned = 1 WHERE user_name = 'Mallory'")
        curs.execute("UPDATE user SET user_comment = 'Admin note' WHERE user_name = 'Bob'")
        curs.execute("UPDATE confirmation SET cf_was_deleted = 1 WHERE cf_comment = 'deleted later'")
    conn.close()


def free_port():
    with socket.socket() as s:
        s.bind(('127.0.0.1', 0))
        return s.getsockname()[1]


@pytest.fixture(scope='session')
def live_server(app_env, tmp_path_factory):
    """Runs web/app.py in its own process with Werkzeug's HTTP server."""
    port = free_port()
    log_path = tmp_path_factory.mktemp('server') / 'server.log'
    log = open(log_path, 'w')
    proc = subprocess.Popen(
        [sys.executable, '-m', 'flask', '--app', 'app', 'run', '--host', '127.0.0.1', '--port', str(port)],
        cwd=WEB_DIR, env=app_env, stdout=log, stderr=subprocess.STDOUT)
    base_url = f'http://127.0.0.1:{port}'
    deadline = time.time() + 30
    while True:
        if proc.poll() is not None:
            pytest.fail('web app did not start:\n' + log_path.read_text())
        try:
            with socket.create_connection(('127.0.0.1', port), timeout=1):
                break
        except OSError:
            if time.time() > deadline:
                proc.kill()
                pytest.fail('web app did not open its port:\n' + log_path.read_text())
            time.sleep(0.2)
    yield base_url
    proc.terminate()
    try:
        proc.wait(timeout=10)
    except subprocess.TimeoutExpired:
        proc.kill()
    log.close()


class Response:
    def __init__(self, status, headers, body):
        self.status = status
        self.headers = headers
        self.body = body

    @property
    def text(self):
        return self.body.decode('utf-8')


@pytest.fixture
def http(live_server, seeded):
    def get(path):
        try:
            with urllib.request.urlopen(live_server + path, timeout=30) as resp:
                return Response(resp.status, resp.headers, resp.read())
        except urllib.error.HTTPError as e:
            return Response(e.code, e.headers, e.read())
    return get


class TableParser(HTMLParser):
    """Collects the text of all cells, row by row, of the tables with a given CSS class."""

    def __init__(self, css_class):
        super().__init__()
        self.css_class = css_class
        self.depth = 0
        self.rows = []
        self.cell = None

    def handle_starttag(self, tag, attrs):
        classes = (dict(attrs).get('class') or '').split()
        if tag == 'table' and (self.depth or self.css_class in classes):
            self.depth += 1
        elif self.depth and tag == 'tr':
            self.rows.append([])
        elif self.depth and tag in ('td', 'th'):
            self.cell = ''

    def handle_endtag(self, tag):
        if tag == 'table' and self.depth:
            self.depth -= 1
        elif self.depth and tag in ('td', 'th') and self.cell is not None:
            self.rows[-1].append(' '.join(self.cell.split()))
            self.cell = None

    def handle_data(self, data):
        if self.cell is not None:
            self.cell += data


def table_rows(html, css_class):
    parser = TableParser(css_class)
    parser.feed(html)
    return parser.rows
