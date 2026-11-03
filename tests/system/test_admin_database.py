"""
System tests for web/admin_api.py (the admin area) against a real MariaDB: every change
and its audit_trail entry, the user_id correction and the checks.

The tests of this module share the seeded data and run in order.
"""
import json

import pymysql
import pytest

import config
from tests.system.conftest import DB_NAME, connect

META_DB_NAME = 'metawiki_systemtest'

META_SCHEMA = '''
CREATE TABLE `logging_logindex` (`log_id` int unsigned NOT NULL AUTO_INCREMENT PRIMARY KEY,
  `log_type` varbinary(32) NOT NULL, `log_timestamp` binary(14) NOT NULL, `log_namespace` int NOT NULL,
  `log_title` varbinary(255) NOT NULL, `log_actor` bigint unsigned NOT NULL, `log_comment_id` bigint unsigned NOT NULL);
CREATE TABLE `actor_logging` (`actor_id` bigint unsigned NOT NULL PRIMARY KEY, `actor_name` varbinary(255) NOT NULL);
CREATE TABLE `comment_logging` (`comment_id` bigint unsigned NOT NULL PRIMARY KEY, `comment_text` blob NOT NULL)
'''


@pytest.fixture(scope='module')
def meta_db(seeded):
    conn = connect()
    with conn.cursor() as curs:
        curs.execute(f'DROP DATABASE IF EXISTS `{META_DB_NAME}`')
        curs.execute(f'CREATE DATABASE `{META_DB_NAME}` CHARACTER SET utf8mb4')
        curs.execute(f'USE `{META_DB_NAME}`')
        for statement in META_SCHEMA.split(';'):
            curs.execute(statement)
        curs.execute("INSERT INTO actor_logging VALUES (1, 'Cabayi')")
        curs.execute("INSERT INTO comment_logging VALUES (1, 'per [[m:Special:GlobalRenameQueue/request/1|request]]')")
        curs.execute("INSERT INTO logging_logindex (log_type, log_timestamp, log_namespace, log_title, log_actor, "
                     "log_comment_id) VALUES ('gblrename', '20240929105726', -1, "
                     "'CentralAuth/Vanished_user_abc', 1, 1)")
    conn.close()
    yield
    conn = connect()
    with conn.cursor() as curs:
        curs.execute(f'DROP DATABASE IF EXISTS `{META_DB_NAME}`')
    conn.close()


@pytest.fixture
def db(seeded, meta_db, monkeypatch):
    from tests.system.conftest import DB_HOST
    monkeypatch.setattr(config, 'meta_replica_host', DB_HOST)
    monkeypatch.setattr(config, 'meta_replica_db_name', META_DB_NAME)
    from admin_api import AdminDatabase
    database = AdminDatabase()
    yield database
    database.close_connections()


def query(sql, args=()):
    conn = connect(DB_NAME)
    with conn.cursor(pymysql.cursors.DictCursor) as curs:
        curs.execute(sql, args)
        rows = list(curs.fetchall())     # PyMySQL returns an empty tuple when nothing matches
    conn.close()
    return rows


def audit(after_id=0):
    return query('SELECT * FROM audit_trail WHERE at_id > %s ORDER BY at_id', (after_id,))


def last_audit_id():
    rows = query('SELECT COALESCE(MAX(at_id), 0) AS id FROM audit_trail')
    return rows[0]['id']


def replica_execute(sql, args=()):
    from tests.system.conftest import REPLICA_DB_NAME
    conn = connect(REPLICA_DB_NAME)
    with conn.cursor() as curs:
        curs.execute(sql, args)
    conn.close()


def test_overview_and_search(db):
    overview = db.get_overview()
    assert (overview['users'], overview['hidden'], overview['banned']) == (7, 1, 1)
    assert overview['deleted'] == 1
    assert [u['name'] for u in db.search_users('o')] == ['Bob', 'Carol', 'Mallory', 'Zoë Ünicode']
    assert [u['name'] for u in db.search_users('105')] == ['Eve']
    assert db.search_users('%') == []           # LIKE wildcards are taken literally
    assert [u['name'] for u in db.search_users('', 'hidden')] == ['Eve']
    assert [u['name'] for u in db.search_users('', 'banned')] == ['Mallory']
    assert [u['name'] for u in db.search_users('', 'hidden_or_banned')] == ['Eve', 'Mallory']
    assert [u['name'] for u in db.search_users('o', 'visible')] == ['Bob', 'Carol', 'Zoë Ünicode']
    assert db.search_users('', '') == db.search_users('', 'unknown') == []
    assert db.get_user_admin(105)['hidden'] == 1


def test_update_user_writes_changes_and_audit_entries(db):
    start = last_audit_id()
    changed = db.update_user(103, {'user_is_hidden': True, 'user_was_banned': False, 'user_comment': ' Note\r\n2 '},
                             'reason [[X]]', 'Euku')
    assert changed == ['user_is_hidden', 'user_comment']
    row = query('SELECT * FROM user WHERE user_id = 103')[0]
    assert (row['user_is_hidden'], row['user_was_banned'], row['user_comment']) == (1, 0, 'Note\n2')
    entries = audit(start)
    assert [(e['at_action'], e['at_user_id'], e['at_field'], e['at_old_value'], e['at_new_value'], e['at_reason'],
             e['at_performer']) for e in entries] == [
        ('user_change', 103, 'user_is_hidden', '0', '1', 'reason [[X]]', 'Euku'),
        ('user_change', 103, 'user_comment', None, 'Note\n2', 'reason [[X]]', 'Euku'),
    ]
    assert all(e['at_timestamp'] is not None for e in entries)
    # the same values again: nothing changes, nothing is logged
    assert db.update_user(103, {'user_is_hidden': 1, 'user_comment': 'Note\n2'}, 'again', 'Euku') == []
    assert audit(start + 2) == []
    db.update_user(103, {'user_is_hidden': False, 'user_comment': ''}, 'undo', 'Euku')
    row = query('SELECT * FROM user WHERE user_id = 103')[0]
    assert (row['user_is_hidden'], row['user_comment']) == (0, None)


def test_update_user_needs_a_reason_and_a_known_user(db):
    from admin_api import AdminError
    start = last_audit_id()
    with pytest.raises(AdminError):
        db.update_user(101, {'user_is_hidden': True}, '  ', 'Euku')
    with pytest.raises(AdminError):
        db.update_user(999, {'user_is_hidden': True}, 'x', 'Euku')
    assert audit(start) == []
    assert query('SELECT user_is_hidden FROM user WHERE user_id = 101')[0]['user_is_hidden'] == 0


def test_a_failing_audit_entry_rolls_the_change_back(db):
    from api import WPPBException
    with pytest.raises(WPPBException):
        db.update_user(101, {'user_was_banned': True}, 'x', '')     # no performer
    assert query('SELECT user_was_banned FROM user WHERE user_id = 101')[0]['user_was_banned'] == 0


def test_update_and_delete_confirmation(db):
    start = last_audit_id()
    assert db.update_confirmation(106, 102, {'cf_was_deleted': True}, 'sock', 'Wiegels') == ['cf_was_deleted']
    assert query('SELECT cf_was_deleted FROM confirmation WHERE cf_user_id = 106 AND cf_confirmed_user_id = 102'
                 )[0]['cf_was_deleted'] == 1
    db.delete_confirmation(101, 107, 'by mistake', 'Wiegels')
    assert query('SELECT * FROM confirmation WHERE cf_user_id = 101 AND cf_confirmed_user_id = 107') == []
    entries = audit(start)
    assert [(e['at_action'], e['at_user_id'], e['at_confirmed_user_id'], e['at_field']) for e in entries] == [
        ('confirmation_change', 106, 102, 'cf_was_deleted'),
        ('confirmation_delete', 101, 107, None),
    ]
    assert json.loads(entries[1]['at_old_value']) == {
        'cf_user_id': 101, 'cf_confirmed_user_id': 107, 'cf_timestamp': '2024-05-02 20:00:00',
        'cf_comment': 'Sommerfest 🎉', 'cf_was_deleted': 0}


def test_audit_entries_with_filters(db):
    entries, has_more = db.get_audit_entries(user_id=107)
    assert [(e['action'], e['user_name'], e['confirmed_user_name']) for e in entries] == [
        ('confirmation_delete', 'Alice', 'Zoë Ünicode')]
    assert not has_more
    entries, has_more = db.get_audit_entries(performer='Euku', count=2)
    assert len(entries) == 2 and has_more
    entries, has_more = db.get_audit_entries(performer='Euku', count=2, page=2)
    assert [e['field'] for e in entries] == ['user_comment', 'user_is_hidden'] and not has_more
    assert db.get_audit_entries(action='rename')[0] == []
    assert db.get_audit_performers() == ['Euku', 'Wiegels']


def test_checks(db):
    conn = connect(DB_NAME)
    with conn.cursor() as curs:
        curs.execute("INSERT INTO confirmation (cf_user_id, cf_confirmed_user_id, cf_timestamp) "
                     "VALUES (103, 103, '2020-01-01 00:00:00')")
    conn.close()
    assert [(c['id'], c['name']) for c in db.check_self_confirmations()] == [(103, 'Carol')]
    # Carol now has 3 confirmations (Alice, Bob, herself) but is not verified
    assert [(v['name'], v['count']) for v in db.check_verification()] == [('Carol', 3)]
    # hidden users are left out
    conn = connect(DB_NAME)
    try:
        with conn.cursor() as curs:
            curs.execute('UPDATE user SET user_is_hidden = 1 WHERE user_id = 103')
        db.conn.rollback()      # end the snapshot of db's open transaction, so it sees the change
        assert db.check_verification() == []
    finally:
        with conn.cursor() as curs:
            curs.execute('UPDATE user SET user_is_hidden = 0 WHERE user_id = 103')
        conn.close()
    db.conn.rollback()
    # Mallory's confirmation of Bob was marked as deleted above, nothing left
    assert db.check_banned_confirmations() == []
    assert db.check_dewiki_accounts() == {'missing': [], 'renamed': []}


def test_relink_rename(db):
    from admin_api import RELINK_NONE, RELINK_RENAME, RELINK_TAKEN, RELINK_UNKNOWN
    replica_execute("UPDATE user SET user_name = 'Caroline' WHERE user_id = 103")
    assert db.check_dewiki_accounts()['renamed'] == [{'id': 103, 'name': 'Carol', 'hidden': 0,
                                                      'dewiki_name': 'Caroline'}]
    assert db.plan_relink(103, 'Carol')['action'] == RELINK_UNKNOWN
    assert db.plan_relink(103, 'Bob')['action'] == RELINK_TAKEN
    assert db.plan_relink(101, 'alice')['action'] == RELINK_NONE
    start = last_audit_id()
    plan = db.relink(103, 'caroline', 'renamed', 'Euku')
    assert (plan['action'], plan['name']) == (RELINK_RENAME, 'Caroline')
    assert db.get_user_admin(103)['name'] == 'Caroline'
    assert [(e['at_action'], e['at_old_value'], e['at_new_value']) for e in audit(start)] == [
        ('rename', 'Carol', 'Caroline')]


def test_relink_moves_a_wrong_user_id(db):
    from admin_api import AdminError, RELINK_MOVE
    replica_execute("INSERT INTO user (user_id, user_name) VALUES (201, 'David')")
    given = query('SELECT COUNT(*) AS n FROM confirmation WHERE cf_user_id = 104')[0]['n']
    received = query('SELECT COUNT(*) AS n FROM confirmation WHERE cf_confirmed_user_id = 104')[0]['n']
    before = query('SELECT * FROM user WHERE user_id = 104')[0]
    start = last_audit_id()
    plan = db.relink(104, 'David', 'wrong user id', 'Euku')
    assert (plan['action'], plan['mw_id']) == (RELINK_MOVE, 201)
    assert query('SELECT * FROM user WHERE user_id = 104') == []
    after = query('SELECT * FROM user WHERE user_id = 201')[0]
    assert after['user_name'] == 'David'
    for column in ('user_participates_since', 'user_verified_since', 'user_last_update', 'user_comment'):
        assert after[column] == before[column]
    assert query('SELECT COUNT(*) AS n FROM confirmation WHERE cf_user_id = 201')[0]['n'] == given
    assert query('SELECT COUNT(*) AS n FROM confirmation WHERE cf_confirmed_user_id = 201')[0]['n'] == received
    assert query('SELECT * FROM user_home_wiki WHERE hw_user_id = 104') == []
    assert [(e['at_action'], e['at_user_id'], e['at_field'], e['at_old_value'], e['at_new_value'])
            for e in audit(start)] == [('user_change', 201, 'user_id', '104', '201'),
                                       ('rename', 201, 'user_name', 'Dave', 'David')]
    with pytest.raises(AdminError):
        db.relink(201, 'Alice', 'taken', 'Euku')


def test_vanished_candidates(db):
    from admin_api import VANISHED_REASON_NO_LOG
    replica_execute("INSERT INTO user (user_id, user_name) VALUES (301, 'Vanished user abc'), (302, 'Renamed user def')")
    conn = connect(DB_NAME)
    with conn.cursor() as curs:
        curs.execute("INSERT INTO user (user_id, user_name, user_participates_since) VALUES "
                     "(301, 'Vanished user abc', '2010-01-01 00:00:00'), (302, 'Renamed user def', NULL)")
    conn.close()
    candidates = {u['name']: u for u in db.get_vanished_candidates()}
    assert set(candidates) == {'Vanished user abc', 'Renamed user def'}
    assert candidates['Vanished user abc']['rename']['performer'] == 'Cabayi'
    assert candidates['Vanished user abc']['reason'] == (
        'Konto auf eigenen Wunsch verschwunden (Globale Umbenennung auf Meta am 2024-09-29: '
        'per [[m:Special:GlobalRenameQueue/request/1|request]])')
    assert candidates['Renamed user def']['rename'] is None
    assert candidates['Renamed user def']['reason'] == VANISHED_REASON_NO_LOG
    assert db.count_hidden_vanished() == 0
    db.update_user(301, {'user_is_hidden': True}, candidates['Vanished user abc']['reason'], 'Euku')
    assert [u['name'] for u in db.get_vanished_candidates()] == ['Renamed user def']
    assert db.count_hidden_vanished() == 1
