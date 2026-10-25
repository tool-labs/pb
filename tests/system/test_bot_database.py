"""
System tests for web/bot_api.py, the database API that SpBot's
pers-bek-to-db-bot.py and pers-bek-info-bot.py use, against a real MariaDB.

Read-only tests come first, the tests that add data follow (same module data).
"""
import datetime as dt

import pymysql
import pytest

from tests.system.conftest import MW_USERS


def user_row(pb_sql, name):
    with pb_sql.cursor(pymysql.cursors.DictCursor) as curs:
        curs.execute('SELECT * FROM user WHERE user_name = %s', (name,))
        return curs.fetchone()


def db_time(conn, expression):
    with conn.cursor() as curs:
        curs.execute(f"SELECT DATE_FORMAT({expression}, '%Y-%m-%d %H:%i:%s')")
        return curs.fetchone()[0]


def test_users_were_added_with_mediawiki_ids(pb_sql):
    with pb_sql.cursor() as curs:
        curs.execute('SELECT user_name, user_id FROM user')
        assert dict(curs.fetchall()) == MW_USERS


def test_third_confirmation_verifies_the_user(pb_sql):
    alice = user_row(pb_sql, 'Alice')
    assert alice['user_participates_since'] == dt.datetime(2008, 2, 10, 12, 0)
    assert alice['user_verified_since'] == dt.datetime(2015, 6, 2, 10, 0)
    assert user_row(pb_sql, 'Dave')['user_verified_since'] == dt.datetime(2015, 6, 4, 12, 0)
    assert user_row(pb_sql, 'Bob')['user_verified_since'] == dt.datetime(2017, 1, 2, 9, 0)
    assert user_row(pb_sql, 'Carol')['user_verified_since'] is None
    assert user_row(pb_sql, 'Zoë Ünicode')['user_verified_since'] is None


def test_verification_touches_last_update(pb_sql):
    assert user_row(pb_sql, 'Dave')['user_last_update'] == dt.datetime(2015, 6, 4, 12, 0)


def test_unicode_is_stored_unchanged(bot_db):
    assert bot_db.get_user_by_name('Zoë Ünicode')[1] == 107
    assert bot_db.get_confirmation(101, 107)[1] == 'Sommerfest 🎉'


def test_get_mw_user_id(bot_db):
    assert bot_db.get_mw_user_id('Alice') == 101
    assert bot_db.get_mw_user_id('Zoë Ünicode') == 107
    assert bot_db.get_mw_user_id('Nobody') is None


def test_has_confirmed(bot_db):
    assert bot_db.has_confirmed(101, 102)
    assert not bot_db.has_confirmed(101, 106)


def test_get_cf_count_by_confirmed(bot_db):
    assert bot_db.get_cf_count_by_confirmed(101) == 4                          # incl. hidden Eve
    assert bot_db.get_cf_count_by_confirmed(101, count_hidden_users=False) == 3


def test_user_list_for_the_wiki(bot_db):
    # used for "Teilnehmerliste" and "JS-alle Benutzer"; hidden and banned users are left out
    rows = {name: count for name, count, since in bot_db.get_user_list_with_confirmations()}
    assert rows == {'Alice': 4, 'Bob': 3, 'Carol': 2, 'Dave': 3, 'Zoë Ünicode': 1}


def test_get_all_users(bot_db):
    names = [row[0] for row in bot_db.get_all_users(show_hidden_users=True, show_banned_users=True)]
    assert names == ['Alice', 'Bob', 'Carol', 'Dave', 'Eve', 'Mallory', 'Zoë Ünicode']
    names = [row[0] for row in bot_db.get_all_users(show_hidden_users=False, show_banned_users=False)]
    assert names == ['Alice', 'Bob', 'Carol', 'Dave', 'Zoë Ünicode']


def test_counts(bot_db):
    assert bot_db.get_user_count(count_banned_users=False, count_hidden_users=False) == 5
    assert bot_db.get_user_count(count_banned_users=True, count_hidden_users=True) == 7
    assert bot_db.get_confirmation_count(count_deleted_cf=False, count_hidden_users=False) == 12
    assert bot_db.get_confirmation_count(count_deleted_cf=True, count_hidden_users=True) == 15


def test_user_blocked(replica_sql, seeded):
    # insert before the first query: the connection keeps a REPEATABLE READ snapshot
    with replica_sql.cursor() as curs:
        curs.execute('INSERT INTO block_target (bt_user) VALUES (%s)', (MW_USERS['Bob'],))
    from bot_api import BotDatabase
    bot_db = BotDatabase()
    assert bot_db.user_blocked('Bob')
    assert bot_db.user_blocked('Alice') is None
    bot_db.close_connections()


def test_add_user_rejects_unknown_mediawiki_user(bot_db, pb_sql):
    assert bot_db.add_user('Nobody', '2026-01-01 12:00:00') is False
    assert user_row(pb_sql, 'Nobody') is None


@pytest.mark.parametrize('stamp', ['2026-01-01', '01.01.2026 12:00', ''])
def test_add_user_rejects_bad_timestamps(bot_db, replica_sql, pb_sql, stamp):
    with replica_sql.cursor() as curs:
        curs.execute("INSERT IGNORE INTO user (user_id, user_name) VALUES (201, 'Frank')")
    assert bot_db.add_user('Frank', stamp) is False
    assert user_row(pb_sql, 'Frank') is None


def test_add_user_twice_raises_integrity_error(bot_db, replica_sql):
    with replica_sql.cursor() as curs:
        curs.execute("INSERT INTO user (user_id, user_name) VALUES (202, 'Grace')")
    assert bot_db.add_user('Grace', '2026-01-01 12:00:00') is True
    with pytest.raises(pymysql.IntegrityError):
        bot_db.add_user('Grace', '2026-01-02 12:00:00')


def test_add_confirmation_rejects_unknown_users(bot_db):
    assert bot_db.add_confirmation(101, 999, None, '2026-01-01 12:00:00') is False
    assert bot_db.add_confirmation(999, 101, None, '2026-01-01 12:00:00') is False


def test_add_confirmation_rejects_bad_timestamps(bot_db):
    assert bot_db.add_confirmation(102, 107, None, '2026-01-01') is False
    assert not bot_db.has_confirmed(102, 107)


def test_add_confirmation_twice_raises_integrity_error(bot_db):
    with pytest.raises(pymysql.IntegrityError):
        bot_db.add_confirmation(101, 102, 'again', '2026-01-01 12:00:00')


def test_further_confirmations_keep_the_verification_date(bot_db, pb_sql):
    assert bot_db.add_confirmation(107, 101, None, '2026-01-03 12:00:00')
    assert user_row(pb_sql, 'Alice')['user_verified_since'] == dt.datetime(2015, 6, 2, 10, 0)


def test_new_users_list(bot_db, replica_sql, pb_sql):
    # "Neu dazugekommen": users who joined in the last 3 months
    with replica_sql.cursor() as curs:
        curs.execute("INSERT INTO user (user_id, user_name) VALUES (203, 'Heidi')")
    assert bot_db.add_user('Heidi', db_time(pb_sql, 'NOW() - INTERVAL 10 DAY'))
    names = [name for name, count, since in bot_db.get_latest_user_list_with_confirmations()]
    assert 'Heidi' in names
    assert 'Alice' not in names


def test_yesterdays_confirmations(bot_db, pb_sql):
    # pers-bek-info-bot.py notifies users about the confirmations of the previous day
    assert bot_db.add_confirmation(104, 103, None, db_time(pb_sql, 'CURDATE() - INTERVAL 1 DAY + INTERVAL 12 HOUR'))
    assert bot_db.add_confirmation(104, 107, None, db_time(pb_sql, 'CURDATE() + INTERVAL 1 HOUR'))
    rows = bot_db.get_yesterdays_confirmations_sorted_by_confirmed(day=1, delta=1)
    assert [(confirmed, confirmer) for confirmed, confirmer, stamp in rows] == [('Carol', 'Dave')]
