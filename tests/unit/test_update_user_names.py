"""Tests for Database.update_user_names with a fake pb connection (unique, case-insensitive user names)."""
import pymysql
import pytest

import api


class FakeCursor:
    def __init__(self, conn):
        self.conn = conn

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

    def execute(self, sql, args=None):
        if sql.startswith('SELECT'):
            self.rows = sorted(self.conn.names.items())
            return
        new_name, user_id = args
        if any(n.casefold() == new_name.casefold() for i, n in self.conn.names.items() if i != user_id):
            raise pymysql.IntegrityError(1062, 'Duplicate entry')
        self.conn.names[user_id] = new_name

    def fetchall(self):
        return self.rows


class FakeConnection:
    def __init__(self, names):
        self.names = dict(names)
        self.commits = 0

    def cursor(self):
        return FakeCursor(self)

    def commit(self):
        self.commits += 1

    def rollback(self):
        pass


def make_db(pb_names, mw_names):
    db = api.Database.__new__(api.Database)
    db.conn = FakeConnection(pb_names)
    db.wp_conn = object()
    db._get_mw_user_names = lambda ids: {i: mw_names[i] for i in ids if i in mw_names}
    return db


def test_renames_are_taken_over():
    db = make_db({1: 'Alice', 2: 'Bob', 3: 'Carol'}, {1: 'Alice', 2: 'Robert', 3: 'Carol'})
    assert db.update_user_names() == [(2, 'Bob', 'Robert', True)]
    assert db.conn.names == {1: 'Alice', 2: 'Robert', 3: 'Carol'}


def test_users_missing_on_the_replica_are_left_alone():
    db = make_db({1: 'Alice', 2: 'Gone'}, {1: 'Alice'})
    assert db.update_user_names() == []
    assert db.conn.names[2] == 'Gone'


def test_dry_run_changes_nothing():
    db = make_db({1: 'Alice', 2: 'Bob'}, {1: 'Alicia', 2: 'Bob'})
    assert db.update_user_names(dry_run=True) == [(1, 'Alice', 'Alicia', False)]
    assert db.conn.names == {1: 'Alice', 2: 'Bob'}
    assert db.conn.commits == 0


def test_case_only_rename():
    db = make_db({1: 'Dvschuetz'}, {1: 'DvSchuetz'})
    assert db.update_user_names() == [(1, 'Dvschuetz', 'DvSchuetz', True)]


def test_a_name_passed_on_is_set_in_the_right_order():
    # 1 takes the old name of 2, who was renamed to Carl
    db = make_db({1: 'Anna', 2: 'Bert'}, {1: 'Bert', 2: 'Carl'})
    assert sorted(db.update_user_names()) == [(1, 'Anna', 'Bert', True), (2, 'Bert', 'Carl', True)]
    assert db.conn.names == {1: 'Bert', 2: 'Carl'}


def test_swapped_names_are_reported():
    db = make_db({1: 'Anna', 2: 'Bert'}, {1: 'Bert', 2: 'Anna'})
    assert sorted(db.update_user_names()) == [(1, 'Anna', 'Bert', False), (2, 'Bert', 'Anna', False)]
    assert db.conn.names == {1: 'Anna', 2: 'Bert'}


def test_name_of_a_user_missing_on_the_replica_is_reported():
    # 2 is gone on dewiki and keeps its old name, which 1 now has
    db = make_db({1: 'Anna', 2: 'Bert'}, {1: 'Bert'})
    assert db.update_user_names() == [(1, 'Anna', 'Bert', False)]


def test_needs_the_replica():
    db = make_db({}, {})
    db.wp_conn = None
    with pytest.raises(api.WPPBException):
        db.update_user_names()
