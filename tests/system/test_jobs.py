"""System tests for the Toolforge jobs (statistics, home wikis) and the pages that show their results."""
import subprocess
import sys

from tests.conftest import REPO_DIR
from tests.system.conftest import table_rows

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


def run_update_home_wikis(app_env):
    return subprocess.run([sys.executable, str(REPO_DIR / 'jobs' / 'update_home_wikis.py')],
                          env=app_env, capture_output=True, text=True, timeout=60)


def home_wiki_rows(pb_sql):
    with pb_sql.cursor() as curs:
        curs.execute('SELECT u.user_name, hw_has_sul, hw_home_db, hw_home_url FROM user_home_wiki'
                     ' JOIN user AS u ON u.user_id = hw_user_id ORDER BY 1')
        return list(curs.fetchall())


def test_update_home_wikis_job(app_env, pb_sql):
    assert home_wiki_rows(pb_sql) == []
    result = run_update_home_wikis(app_env)
    assert result.returncode == 0, result.stderr
    assert 'home wikis of 7 users checked' in result.stderr
    assert home_wiki_rows(pb_sql) == [
        ('Alice', 1, 'dewiki', 'https://de.wikipedia.org'),
        ('Bob', 1, 'enwiki', 'https://en.wikipedia.org'),
        ('Carol', 1, 'closedwiki', None),
        ('Dave', 0, None, None),
        ('Eve', 1, 'dewiki', 'https://de.wikipedia.org'),
        ('Mallory', 1, 'dewiki', 'https://de.wikipedia.org'),
        ('Zoë Ünicode', 1, 'dewiki', 'https://de.wikipedia.org'),
    ]


def test_update_home_wikis_job_only_checks_old_entries(app_env, pb_sql):
    assert 'home wikis of 0 users checked' in run_update_home_wikis(app_env).stderr
    with pb_sql.cursor() as curs:
        curs.execute("UPDATE user_home_wiki SET hw_checked = NOW() - INTERVAL 8 DAY, hw_home_db = 'old'"
                     " WHERE hw_user_id = 101")
    assert 'home wikis of 1 users checked' in run_update_home_wikis(app_env).stderr
    assert home_wiki_rows(pb_sql)[0] == ('Alice', 1, 'dewiki', 'https://de.wikipedia.org')


def test_users_page_shows_home_wikis(http):
    rows = table_rows(http('/users').text, 'users')
    assert [(r[0], r[5]) for r in rows[1:]] == [
        ('Alice', 'dewiki'), ('Bob', 'enwiki'), ('Carol', 'closedwiki'),
        ('Dave', 'kein SUL-Konto'), ('Zoë Ünicode', 'dewiki'),
    ]


def user_names(http, query):
    return [r[0] for r in table_rows(http('/users' + query).text, 'users')[1:]]


def test_users_page_filters(http):
    assert user_names(http, '?homewiki=dewiki') == ['Alice', 'Zoë Ünicode']
    assert user_names(http, '?homewiki=none') == ['Dave']
    assert user_names(http, '?verified=no') == ['Carol', 'Zoë Ünicode']
    assert user_names(http, '?homewiki=dewiki&verified=yes') == ['Alice']
    # all seeded confirmations are older than 6 months
    assert user_names(http, '?recent=any') == []
    html = http('/users?homewiki=dewiki').text
    assert '<option value="dewiki" selected>dewiki (2)</option>' in html
    assert '<option value="none">kein SUL-Konto auf dewiki (1)</option>' in html


def test_user_page_shows_home_wiki(http):
    assert '<a href="https://en.wikipedia.org">en.wikipedia.org</a> (enwiki)' in http('/user/name/Bob').text
    assert 'kein SUL-Konto auf dewiki' in http('/user/name/Dave').text
