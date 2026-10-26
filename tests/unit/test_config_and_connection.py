"""Tests for config.py and how api.Database opens its connections (pymysql is mocked)."""
import importlib

import pytest

import api
import config


class RecordingConnection:
    created = []

    def __init__(self, **kwargs):
        self.kwargs = kwargs
        self.connected = False
        self.closed = False
        RecordingConnection.created.append(self)

    def connect(self):
        self.connected = True

    def close(self):
        self.closed = True


@pytest.fixture
def recording_pymysql(monkeypatch):
    RecordingConnection.created = []
    monkeypatch.setattr(api.pymysql.connections, 'Connection', RecordingConnection)
    return RecordingConnection


@pytest.fixture
def cnf_file(tmp_path, monkeypatch):
    path = tmp_path / 'replica.my.cnf'
    path.write_text("[client]\nuser = 'u1234'\npassword = \"secret\"\nhost = replica.example\n")
    monkeypatch.setattr(config, 'db_conf_file', str(path))
    return path


def test_database_uses_credentials_from_cnf_file(recording_pymysql, cnf_file, monkeypatch):
    monkeypatch.setattr(config, 'db_host', 'toolsdb.example')
    monkeypatch.setattr(config, 'db_port', 3307)
    monkeypatch.setattr(config, 'db_name', 'pb_db')
    monkeypatch.setattr(config, 'replica_db_name', 'wiki_db')

    db = api.Database()

    pb, replica = recording_pymysql.created
    assert pb.kwargs['host'] == 'toolsdb.example'
    assert pb.kwargs['database'] == 'pb_db'
    assert pb.kwargs['charset'] == 'utf8mb4'
    assert replica.kwargs['host'] == 'replica.example'
    assert replica.kwargs['database'] == 'wiki_db'
    for conn in (pb, replica):
        assert conn.kwargs['user'] == 'u1234'       # quotes are stripped
        assert conn.kwargs['password'] == 'secret'
        assert conn.kwargs['port'] == 3307
        assert conn.connected

    db.close_connections()
    assert pb.closed and replica.closed


def test_database_wraps_connection_errors(cnf_file, monkeypatch):
    class Failing(RecordingConnection):
        def connect(self):
            raise api.pymysql.OperationalError(2003, "Can't connect")
    monkeypatch.setattr(api.pymysql.connections, 'Connection', Failing)
    with pytest.raises(api.WPPBException, match='wrong database connection'):
        api.Database()


def test_get_mw_user_id_without_replica_raises(recording_pymysql, cnf_file):
    db = api.Database(use_replica=False)
    assert len(recording_pymysql.created) == 1
    with pytest.raises(api.WPPBException, match='replica'):
        db.get_mw_user_id('Alice')


def test_missing_cnf_file_raises_wppb_exception(recording_pymysql, tmp_path, monkeypatch):
    monkeypatch.setattr(config, 'db_conf_file', str(tmp_path / 'missing.cnf'))
    with pytest.raises(api.WPPBException):
        api.Database()


def test_config_defaults_are_the_toolforge_values(monkeypatch):
    for name in ('PB_SQL_DUMP_FOLDER', 'PB_DB_CONF_FILE', 'PB_DB_HOST', 'PB_DB_PORT',
                 'PB_DB_NAME', 'PB_REPLICA_DB_NAME'):
        monkeypatch.delenv(name, raising=False)
    try:
        importlib.reload(config)
        assert config.db_host == 'tools.db.svc.wikimedia.cloud'
        assert config.db_port == 3306
        assert config.db_name == 's51344__pb'
        assert config.replica_db_name == 'dewiki_p'
        assert config.db_conf_file.endswith('/replica.pb-db.cnf')
        assert config.sql_dump_folder == '/data/project/pb/www/python/src/sql-dumps'
    finally:
        monkeypatch.undo()
        importlib.reload(config)


def test_config_can_be_overridden_by_environment(monkeypatch, tmp_path):
    monkeypatch.setenv('PB_SQL_DUMP_FOLDER', str(tmp_path))
    monkeypatch.setenv('PB_DB_CONF_FILE', '/tmp/test.cnf')
    monkeypatch.setenv('PB_DB_HOST', '127.0.0.1')
    monkeypatch.setenv('PB_DB_PORT', '33061')
    monkeypatch.setenv('PB_DB_NAME', 'pb_test')
    monkeypatch.setenv('PB_REPLICA_DB_NAME', 'dewiki_test')
    try:
        importlib.reload(config)
        assert config.sql_dump_folder == str(tmp_path)
        assert config.db_conf_file == '/tmp/test.cnf'
        assert config.db_host == '127.0.0.1'
        assert config.db_port == 33061
        assert config.db_name == 'pb_test'
        assert config.replica_db_name == 'dewiki_test'
    finally:
        monkeypatch.undo()
        importlib.reload(config)
