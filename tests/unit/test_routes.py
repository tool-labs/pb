"""Tests for the Flask routes in app.py, using the fake database from conftest.py."""
import pytest

import app as webapp
import config
from tests.unit import fake_db


def test_index_shows_numbers_latest_confirmations_and_stats(client):
    response = client.get('/')
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert 'Momentan nehmen 2 Benutzer' in html
    assert 'insgesamt 2 Mal bestätigt' in html
    assert '<a href="/user/name/Alice">Alice</a>' in html
    assert '2008-02-20, 10:05' in html
    assert 'insgesamt <span class="total">2 Bestätigungen</span>' in html
    assert 'insgesamt <span class="total">2 Teilnehmer</span>' in html


def test_responses_contain_no_blank_lines(client):
    html = client.get('/').get_data(as_text=True)
    assert all(line.strip() for line in html.splitlines())


def test_about(client):
    response = client.get('/about')
    assert response.status_code == 200
    assert 'Über das Projekt' in response.get_data(as_text=True)


def test_users_lists_visible_users_only(client):
    html = client.get('/users').get_data(as_text=True)
    assert 'Die folgenden 2 Benutzer' in html
    assert '/user/name/Alice' in html and '/user/name/Bob' in html
    assert 'Eve' not in html          # hidden
    assert 'Mallory' not in html      # banned


def test_user_page(client):
    response = client.get('/user/name/Alice')
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert 'Teilnehmerinformationen für Alice' in html
    assert 'https://de.wikipedia.org/wiki/Benutzer:Alice' in html
    assert '2008-02-10' in html       # participates since
    assert '2008-03-01' in html       # verified since
    assert '<a href="/user/name/Bob">Bob</a>' in html
    assert 'Ex-Teilnehmer' in html or 'Eve' not in html


def test_user_page_shows_comment(client):
    assert '<b>Kommentar:</b> Admin note' in client.get('/user/name/Bob').get_data(as_text=True)


def test_user_page_of_banned_user_shows_warning(client):
    html = client.get('/user/name/Mallory').get_data(as_text=True)
    assert 'wurde aus dem Projekt' in html


def test_unknown_user(client):
    response = client.get('/user/name/Nobody')
    assert response.status_code == 200
    assert 'der angegebene Benutzer existiert nicht' in response.get_data(as_text=True)


def test_user_page_escapes_html_in_comments(client, monkeypatch):
    monkeypatch.setitem(fake_db.CONFIRMATIONS, (1, 2), (fake_db.ts(2008, 2, 20, 10, 0), '<script>alert(1)</script>'))
    html = client.get('/user/name/Alice').get_data(as_text=True)
    assert '<script>alert(1)</script>' not in html
    assert '&lt;script&gt;' in html


def test_user_page_renders_wikilinks_in_comments(client):
    html = client.get('/user/name/Alice').get_data(as_text=True)
    assert '<a href="https://de.wikipedia.org/wiki/Stammtisch_Berlin">Stammtisch Berlin</a>' in html


def test_recent_confirmations_render_wikilinks_in_comments(client):
    html = client.get('/recent').get_data(as_text=True)
    assert '<a href="https://de.wikipedia.org/wiki/Stammtisch_Berlin">Stammtisch Berlin</a>' in html


def test_hidden_user_page_is_not_shown(client):
    response = client.get('/user/name/Eve')
    assert response.status_code == 404
    assert 'Eve' not in response.get_data(as_text=True)


def test_recent_confirmations(client, fake_db_class):
    response = client.get('/recent')
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert 'Neueste Bestätigungen' in html
    assert '<a href="/recent/2">Älter →</a>' in html
    assert fake_db_class.instances[-1].calls == [('get_latest_confirmations', 1, 50)]


def test_recent_confirmations_page_two(client, fake_db_class):
    assert client.get('/recent/2').status_code == 200
    assert fake_db_class.instances[-1].calls == [('get_latest_confirmations', 2, 50)]


def test_recent_confirmations_rejects_page_zero(client):
    assert client.get('/recent/0').status_code == 400


def test_confirmation_details(client):
    html = client.get('/confirmation/1/2').get_data(as_text=True)
    assert 'Alice hat Bob am 2008-02-20 um 10:00 Uhr bestätigt' in html
    assert 'Bob hat Alice am 2008-02-20 um 10:05 Uhr bestätigt' in html


def test_confirmation_details_one_sided(client):
    html = client.get('/confirmation/1/4').get_data(as_text=True)
    assert 'Alice hat Mallory noch nicht bestätigt.' in html


def test_confirmation_details_of_unknown_user(client):
    html = client.get('/confirmation/1/999').get_data(as_text=True)
    assert 'Ein Fehler ist aufgetreten' in html


@pytest.mark.parametrize('url', ['/confirmation/3/1', '/confirmation/1/3'])
def test_confirmation_details_hide_hidden_users(client, url):
    response = client.get(url)
    assert response.status_code == 404
    assert 'Eve' not in response.get_data(as_text=True)


def test_confirmations_route_is_gone(production_client):
    assert production_client.get('/confirmations').status_code == 404


def test_unknown_route_is_404(client):
    assert client.get('/does-not-exist').status_code == 404


def test_static_pages_do_not_open_a_database_connection(client, fake_db_class):
    assert client.get('/about').status_code == 200
    assert fake_db_class.instances == []


def test_database_connection_is_opened_once_and_closed_after_request(client, fake_db_class):
    client.get('/')
    assert len(fake_db_class.instances) == 1
    assert fake_db_class.instances[0].closed


def test_web_app_does_not_use_the_replica(client, fake_db_class):
    client.get('/users')
    assert fake_db_class.instances[0].use_replica is False


def test_database_connection_is_closed_after_failing_request(production_client, fake_db_class, monkeypatch):
    def broken(*args, **kwargs):
        raise RuntimeError('database went away')
    monkeypatch.setattr(fake_db_class, 'get_all_users', broken)
    assert production_client.get('/users').status_code == 500
    assert fake_db_class.instances[0].closed


@pytest.fixture
def dump_folder(tmp_path, monkeypatch):
    monkeypatch.setattr(config, 'sql_dump_folder', str(tmp_path))
    (tmp_path / 'wppb-2026-01-01.sql.bz2').write_bytes(b'BZh91AY&SY dump one')
    (tmp_path / 'wppb-2026-01-02.sql.bz2').write_bytes(b'BZh91AY&SY dump two')
    (tmp_path / 'secret.txt').write_bytes(b'not listed')
    return tmp_path


def test_sql_dump_list(client, dump_folder):
    html = client.get('/sql-dumps').get_data(as_text=True)
    assert '<a href="/sql-dump-file/wppb-2026-01-01.sql.bz2">wppb-2026-01-01.sql.bz2</a>' in html
    assert 'wppb-2026-01-02.sql.bz2' in html
    assert '19 Byte' in html
    assert 'secret.txt' not in html


def test_sql_dump_download(client, dump_folder):
    response = client.get('/sql-dump-file/wppb-2026-01-02.sql.bz2')
    assert response.status_code == 200
    assert response.data == b'BZh91AY&SY dump two'
    assert 'attachment' in response.headers['Content-Disposition']
    assert 'wppb-2026-01-02.sql.bz2' in response.headers['Content-Disposition']


@pytest.mark.parametrize('file_name', [
    'secret.txt',
    'wppb-2026-01-01.sql',
    'wppb-2026-1-01.sql.bz2',
    'xwppb-2026-01-01.sql.bz2',
    '..%2Fconfig.py',
    '%2E%2E%2Fsecret.txt',
])
def test_sql_dump_download_rejects_other_files(client, dump_folder, file_name):
    assert client.get('/sql-dump-file/' + file_name).status_code in (400, 404)


def test_sql_dump_download_of_missing_file_is_404(client, dump_folder):
    response = client.get('/sql-dump-file/wppb-2020-01-01.sql.bz2')
    assert response.status_code == 404
    assert str(dump_folder) not in response.get_data(as_text=True)


def test_sql_dump_download_of_encrypted_dump(client, dump_folder):
    (dump_folder / 'wppb-2026-01-03.sql.bz2.enc').write_bytes(b'Salted__encrypted')
    assert 'wppb-2026-01-03.sql.bz2.enc' in client.get('/sql-dumps').get_data(as_text=True)
    response = client.get('/sql-dump-file/wppb-2026-01-03.sql.bz2.enc')
    assert response.status_code == 200
    assert response.data == b'Salted__encrypted'


def test_static_files(client):
    assert client.get('/static/main.css').status_code == 200
    assert client.get('/static/jquery-3.7.1.min.js').status_code == 200
