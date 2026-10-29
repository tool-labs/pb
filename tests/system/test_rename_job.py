"""System test for the Toolforge job jobs/update_user_names.py (renames on dewiki)."""
import subprocess
import sys

from tests.conftest import REPO_DIR
from tests.system.conftest import table_rows


def run_update_user_names(app_env, *args):
    return subprocess.run([sys.executable, str(REPO_DIR / 'jobs' / 'update_user_names.py'), *args],
                          env=app_env, capture_output=True, text=True, timeout=60)


def pb_names(pb_sql):
    with pb_sql.cursor() as curs:
        curs.execute('SELECT user_id, user_name FROM user ORDER BY user_id')
        return dict(curs.fetchall())


def test_nothing_to_rename(app_env, pb_sql):
    result = run_update_user_names(app_env)
    assert result.returncode == 0, result.stderr
    assert 'Run completed, 0 renames' in result.stderr


def test_dry_run(app_env, pb_sql, replica_sql):
    with replica_sql.cursor() as curs:
        curs.execute("UPDATE user SET user_name = 'Roberta' WHERE user_id = 102")
        curs.execute("UPDATE user SET user_name = 'Zoe' WHERE user_id = 107")
    result = run_update_user_names(app_env, '--dry-run')
    assert result.returncode == 0, result.stderr
    assert 'user 102 would be renamed to Roberta' in result.stderr
    assert 'Run completed, 2 renames (dry run)' in result.stderr
    assert pb_names(pb_sql)[102] == 'Bob'


def test_renames_are_taken_over(app_env, pb_sql, http):
    result = run_update_user_names(app_env)
    assert result.returncode == 0, result.stderr
    assert 'user 102 renamed to Roberta' in result.stderr
    assert 'Bob' not in result.stderr                  # old names are not logged
    names = pb_names(pb_sql)
    assert names[102] == 'Roberta' and names[107] == 'Zoe'
    assert 'Run completed, 0 renames' in run_update_user_names(app_env).stderr
    users = [row[0] for row in table_rows(http('/users').text, 'users')[1:]]
    assert 'Roberta' in users and 'Bob' not in users
    assert http('/user/name/Roberta').status == 200


def test_renames_are_recorded_in_the_audit_trail(pb_sql):
    with pb_sql.cursor() as curs:
        curs.execute('SELECT at_action, at_user_id, at_field, at_old_value, at_new_value, at_performer,'
                     ' at_timestamp IS NOT NULL FROM audit_trail ORDER BY at_id')
        assert list(curs.fetchall()) == [
            ('rename', 102, 'user_name', 'Bob', 'Roberta', 'update-user-names (Job)', 1),
            ('rename', 107, 'user_name', 'Zoë Ünicode', 'Zoe', 'update-user-names (Job)', 1),
        ]


def test_admin_change_with_audit_entry(bot_db, pb_sql):
    bot_db.add_audit_entry('user_change', 'Admin', user_id=104, field='user_comment',
                           old_value=None, new_value='note', reason='Test [[link]]')
    with pb_sql.cursor() as curs:
        curs.execute("SELECT at_reason, at_performer FROM audit_trail WHERE at_action = 'user_change'")
        assert curs.fetchall() == (('Test [[link]]', 'Admin'),)


def test_name_used_by_another_participant_fails_the_job(app_env, pb_sql, replica_sql):
    # Alice is renamed to Carol, but the pb entry of Carol (gone on dewiki) still has that name
    with replica_sql.cursor() as curs:
        curs.execute("DELETE FROM user WHERE user_id = 103")
        curs.execute("UPDATE user SET user_name = 'Carol' WHERE user_id = 101")
    result = run_update_user_names(app_env)
    assert result.returncode == 1
    assert 'user 101 could not be renamed to Carol' in result.stderr
    assert pb_names(pb_sql)[101] == 'Alice'
