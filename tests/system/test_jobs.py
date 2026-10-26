"""System tests for the Toolforge job jobs/update_stats.py and the statistics on the main page."""
import subprocess
import sys

from tests.conftest import REPO_DIR

EXPECTED_STATS = [('2008-02', 0, 6), ('2015-06', 0, 4), ('2017-01', 0, 1), ('2024-05', 0, 1)]


def run_update_stats(app_env):
    return subprocess.run([sys.executable, str(REPO_DIR / 'jobs' / 'update_stats.py')],
                          env=app_env, capture_output=True, text=True, timeout=60)


def stats_rows(pb_sql):
    with pb_sql.cursor() as curs:
        curs.execute('SELECT `year_month`, `group`, `count` FROM stats_confirmations_by_month ORDER BY 1')
        return list(curs.fetchall())


def test_main_page_without_stats(http, pb_sql):
    assert stats_rows(pb_sql) == []
    html = http('/').text
    assert 'insgesamt <span class="total">0 Bestätigungen</span>' in html
    assert 'insgesamt 0 Mal bestätigt' in html


def test_update_stats_job(app_env, pb_sql):
    result = run_update_stats(app_env)
    assert result.returncode == 0, result.stderr
    assert 'Run completed' in result.stderr
    # hidden users and deleted confirmations are not counted
    assert stats_rows(pb_sql) == EXPECTED_STATS


def test_update_stats_job_is_repeatable(app_env, pb_sql):
    assert run_update_stats(app_env).returncode == 0
    assert stats_rows(pb_sql) == EXPECTED_STATS


def test_main_page_shows_stats(http):
    html = http('/').text
    assert 'insgesamt <span class="total">12 Bestätigungen</span>' in html
    assert 'insgesamt 12 Mal bestätigt' in html
    assert 'insgesamt <span class="total">5 Teilnehmer</span>' in html
    assert '<span class="total_0">2 unbestätigte</span>' in html
    assert '<span class="total_1">3 bestätigte</span>' in html
    assert 'title="2008-02: 6"' in html
    assert 'title="2015-06: 4"' in html
