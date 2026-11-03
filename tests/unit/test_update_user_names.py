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
        if 'INSERT INTO `audit_trail`' in sql:
            self.conn.audit.append(args)
            self.lastrowid = len(self.conn.audit)
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
        self.audit = []

    def cursor(self):
        return FakeCursor(self)

    def commit(self):
        self.commits += 1

    def rollback(self):
        pass


def make_db(pb_names, mw_names, rename_log=None):
    """*rename_log* `{old_name: [new_name, ...]}`; by default every name change is in the log."""
    if rename_log is None:
        rename_log = {pb_names[i]: [mw_names[i]] for i in pb_names if i in mw_names and mw_names[i] != pb_names[i]}
    db = api.Database.__new__(api.Database)
    db.conn = FakeConnection(pb_names)
    db.wp_conn = object()
    db._get_mw_user_names = lambda ids: {i: mw_names[i] for i in ids if i in mw_names}
    db.log_queries = []

    def get_mw_renames(names):
        db.log_queries.append(set(names))
        return {name: rename_log[name] for name in names if name in rename_log}
    db._get_mw_renames = get_mw_renames
    return db

DONE, DRY_RUN, TAKEN, NOT_LOGGED = api.RENAME_DONE, api.RENAME_DRY_RUN, api.RENAME_NAME_TAKEN, api.RENAME_NOT_LOGGED


def test_renames_are_taken_over():
    db = make_db({1: 'Alice', 2: 'Bob', 3: 'Carol'}, {1: 'Alice', 2: 'Robert', 3: 'Carol'})
    assert db.update_user_names() == [(2, 'Bob', 'Robert', DONE)]
    assert db.conn.names == {1: 'Alice', 2: 'Robert', 3: 'Carol'}


def test_users_missing_on_the_replica_are_left_alone():
    db = make_db({1: 'Alice', 2: 'Gone'}, {1: 'Alice'})
    assert db.update_user_names() == []
    assert db.conn.names[2] == 'Gone'


def test_dry_run_changes_nothing():
    db = make_db({1: 'Alice', 2: 'Bob'}, {1: 'Alicia', 2: 'Bob'})
    assert db.update_user_names(dry_run=True) == [(1, 'Alice', 'Alicia', DRY_RUN)]
    assert db.conn.names == {1: 'Alice', 2: 'Bob'}
    assert db.conn.commits == 0


def test_case_only_rename():
    db = make_db({1: 'Dvschuetz'}, {1: 'DvSchuetz'})
    assert db.update_user_names() == [(1, 'Dvschuetz', 'DvSchuetz', DONE)]


def test_a_name_passed_on_is_set_in_the_right_order():
    # 1 takes the old name of 2, who was renamed to Carl
    db = make_db({1: 'Anna', 2: 'Bert'}, {1: 'Bert', 2: 'Carl'})
    assert sorted(db.update_user_names()) == [(1, 'Anna', 'Bert', DONE), (2, 'Bert', 'Carl', DONE)]
    assert db.conn.names == {1: 'Bert', 2: 'Carl'}


def test_swapped_names_are_reported():
    db = make_db({1: 'Anna', 2: 'Bert'}, {1: 'Bert', 2: 'Anna'})
    assert sorted(db.update_user_names()) == [(1, 'Anna', 'Bert', TAKEN), (2, 'Bert', 'Anna', TAKEN)]
    assert db.conn.names == {1: 'Anna', 2: 'Bert'}


def test_name_of_a_user_missing_on_the_replica_is_reported():
    # 2 is gone on dewiki and keeps its old name, which 1 now has
    db = make_db({1: 'Anna', 2: 'Bert'}, {1: 'Bert'})
    assert db.update_user_names() == [(1, 'Anna', 'Bert', TAKEN)]


def test_rename_without_log_entry_is_not_taken_over():
    # pb has the wrong user id 38 for Bubo bubo; on dewiki 38 is another, unrelated account
    db = make_db({38: 'Bubo bubo', 2: 'Bob'}, {38: 'Gruener-recke', 2: 'Robert'}, {'Bob': ['Robert']})
    assert db.update_user_names() == [(2, 'Bob', 'Robert', DONE), (38, 'Bubo bubo', 'Gruener-recke', NOT_LOGGED)]
    assert db.conn.names == {2: 'Robert', 38: 'Bubo bubo'}
    assert [entry[6] for entry in db.conn.audit] == ['Robert']


def test_dry_run_reports_renames_without_log_entry():
    db = make_db({38: 'Bubo bubo'}, {38: 'Gruener-recke'}, {})
    assert db.update_user_names(dry_run=True) == [(38, 'Bubo bubo', 'Gruener-recke', NOT_LOGGED)]


def test_chain_of_renames_in_the_log():
    db = make_db({1: 'Hilarmont'}, {1: 'Renamed user 09876576'},
                 {'Hilarmont': ['Pan Tau'], 'Pan Tau': ['Renamed user 09876576']})
    assert db.update_user_names() == [(1, 'Hilarmont', 'Renamed user 09876576', DONE)]


def test_log_entry_of_a_later_account_with_the_old_name_does_not_count():
    # A.Savin was renamed to Savin 2005, a new A.Savin was renamed to something else later
    db = make_db({1: 'A.Savin'}, {1: 'Savin 2005'}, {'A.Savin': ['A.Savin-SUL', 'Savin 2005']})
    assert db.update_user_names() == [(1, 'A.Savin', 'Savin 2005', DONE)]
    db = make_db({1: 'X'}, {1: 'Z'}, {'X': ['Y']})
    assert db.update_user_names() == [(1, 'X', 'Z', NOT_LOGGED)]


def test_rename_log_cycles_end():
    db = make_db({1: 'A'}, {1: 'Z'}, {'A': ['B'], 'B': ['A']})
    assert db.update_user_names() == [(1, 'A', 'Z', NOT_LOGGED)]
    assert len(db.log_queries) == 2


def test_rename_chain_is_limited():
    log = {'N%d' % i: ['N%d' % (i + 1)] for i in range(50)}
    db = make_db({1: 'N0'}, {1: 'N50'}, log)
    assert db.update_user_names() == [(1, 'N0', 'N50', NOT_LOGGED)]
    assert len(db.log_queries) == api.RENAME_CHAIN_MAX


@pytest.mark.parametrize('params, new_name', [
    (b'a:3:{s:10:"4::olduser";s:7:"A.Savin";s:10:"5::newuser";s:10:"Savin 2005";s:8:"6::edits";i:82957;}', 'Savin 2005'),
    ('a:3:{s:10:"4::olduser";s:7:"Incarus";s:10:"5::newuser";s:24:"GelöschterBenutzer77977";s:8:"6::edits";s:4:"2353";}'.encode(),
     'GelöschterBenutzer77977'),
    (b'a:4:{s:10:"4::olduser";s:3:"A;B";s:10:"5::newuser";s:6:"C";"D\'";s:8:"6::edits";i:5;s:7:"derived";b:0;}', 'C";"D\''),
    (b'ChrisHamburg-SUL', 'ChrisHamburg-SUL'),           # entries before about 2014
    (b'a:1:{s:10:"4::olduser";s:1:"A";}', None),
    (b'', None),
])
def test_rename_target(params, new_name):
    assert api._rename_target(params) == new_name


def test_user_id_corrections_can_be_recorded():
    db = make_db({}, {})
    db.add_audit_entry('user_change', 'Admin', user_id=40182, field='user_id', old_value=38, new_value=40182,
                       reason='wrong user id')
    assert db.conn.audit[0][4:7] == ('user_id', '38', '40182')


def test_needs_the_replica():
    db = make_db({}, {})
    db.wp_conn = None
    with pytest.raises(api.WPPBException):
        db.update_user_names()


def test_renames_are_recorded_in_the_audit_trail():
    db = make_db({1: 'Alice', 2: 'Bob'}, {1: 'Alicia', 2: 'Vanished user 1a2b3c'})
    db.update_user_names()
    #             timestamp, action, user, confirmed, field, old, new, reason, performer
    assert db.conn.audit == [
        (None, 'rename', 1, None, 'user_name', 'Alice', 'Alicia', None, 'update-user-names (Job)'),
        (None, 'rename', 2, None, 'user_name', 'Bob', 'Vanished user 1a2b3c', None, 'update-user-names (Job)'),
    ]


def test_failed_and_dry_run_renames_are_not_recorded():
    db = make_db({1: 'Anna', 2: 'Bert'}, {1: 'Bert', 2: 'Anna'})
    db.update_user_names()
    db.update_user_names(dry_run=True)
    assert db.conn.audit == []


def test_add_audit_entry():
    db = make_db({}, {})
    entry_id = db.add_audit_entry('user_change', 'Admin', user_id=5, field='user_is_hidden',
                                  old_value=0, new_value=1, reason='left')
    assert entry_id == 1
    assert db.conn.audit == [(None, 'user_change', 5, None, 'user_is_hidden', '0', '1', 'left', 'Admin')]
    assert db.conn.commits == 1


@pytest.mark.parametrize('kwargs', [
    {'action': 'drop_everything', 'performer': 'Admin'},
    {'action': 'user_change', 'performer': 'Admin', 'field': 'user_name'},
    {'action': 'user_delete', 'performer': 'Admin', 'field': 'user_comment'},
    {'action': 'user_change', 'performer': '', 'field': 'user_comment'},
])
def test_add_audit_entry_rejects_invalid_entries(kwargs):
    db = make_db({}, {})
    with pytest.raises(api.WPPBException):
        db.add_audit_entry(**kwargs)
    assert db.conn.audit == []
