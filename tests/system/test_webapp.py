"""System tests: HTTP requests against the running web app backed by a real MariaDB."""
import urllib.parse

import pytest

from tests.system.conftest import table_rows

# Expected values for the data from conftest.seeded:
#   visible users (neither hidden nor banned): Alice, Bob, Carol, Dave, Zoë Ünicode
#   visible confirmations: 15 seeded - 2 involving hidden Eve - 1 deleted = 12
VISIBLE_USERS = ['Alice', 'Bob', 'Carol', 'Dave', 'Zoë Ünicode']


def user_url(name):
    return '/user/name/' + urllib.parse.quote(name)


def test_index(http):
    response = http('/')
    assert response.status == 200
    html = response.text
    assert 'Momentan nehmen 5 Benutzer' in html
    assert 'insgesamt 12 Mal bestätigt' in html


def test_index_lists_the_latest_visible_confirmations(http):
    html = http('/').text
    section = html.split('Letzte Bestätigungen', 1)[1].split('</ul>', 1)[0]
    entries = section.count('<li>')
    assert entries == 10
    first = section.split('<li>')[1]
    assert first.startswith('2024-05-02, 20:00')
    assert 'Zoë Ünicode' in first
    assert 'deleted later' not in section
    assert 'Eve' not in section


def test_users_page(http):
    response = http('/users')
    assert response.status == 200
    assert 'Die folgenden 5 Benutzer' in response.text
    rows = table_rows(response.text, 'users')
    assert rows[0][0] == 'Name'
    #          name, taken, given, participates since, verified since
    assert rows[1:] == [
        ['Alice', '3', '4', '2008-02-10', '2015-06-02'],
        ['Bob', '3', '3', '2008-02-11', '2017-01-02'],
        ['Carol', '2', '4', '2008-02-12', ''],
        ['Dave', '3', '1', '2015-06-01', '2015-06-04'],
        ['Zoë Ünicode', '2', '0', '2024-05-01', ''],
    ]


def test_users_page_hides_hidden_and_banned_users(http):
    html = http('/users').text
    assert 'Eve' not in html
    assert 'Mallory' not in html


def test_user_page(http):
    response = http('/user/name/Alice')
    assert response.status == 200
    html = response.text
    assert 'Teilnehmerinformationen für Alice' in html
    assert table_rows(html, 'toc') == [
        ['Nimmt teil seit', '2008-02-10'],
        ['Ist bestätigt seit', '2015-06-02'],
        ['↓ Erhaltene Bestätigungen', '3'],
        ['↓ Vergebene Bestätigungen', '4'],
    ]

    received = table_rows(html, 'taken')
    given = table_rows(html, 'given')
    assert received[0] == ['', 'Von', 'Datum', 'Kommentar', 'Rückbestätigt?']
    assert given[0] == ['', 'An', 'Datum', 'Kommentar', 'Rückbestätigt?']
    assert [r[1:] for r in received[1:]] == [
        ['Dave', '2015-06-02', '', 'ja'],
        ['Carol', '2008-02-21', 'WikiCon', 'ja'],
        ['Bob', '2008-02-20', '', 'ja'],
    ]
    # the comment cell holds the text the browser shows
    assert [r[1:] for r in given[1:]] == [
        ['Zoë Ünicode', '2024-05-02', 'Sommerfest 🎉', 'nein'],
        ['Dave', '2015-06-02', '', 'ja'],
        ['Carol', '2008-02-21', '', 'ja'],
        ['Bob', '2008-02-20', 'Stammtisch Berlin', 'ja'],
    ]


def test_user_page_links_wikilinks_in_comments(http):
    assert 'Stammtisch <a href="https://de.wikipedia.org/wiki/Berlin">Berlin</a>' in http('/user/name/Alice').text


def test_user_page_with_unicode_name(http):
    response = http(user_url('Zoë Ünicode'))
    assert response.status == 200
    assert 'Teilnehmerinformationen für Zoë Ünicode' in response.text
    assert 'Sommerfest 🎉' in response.text


def test_user_page_marks_deleted_confirmations(http):
    html = http(user_url('Zoë Ünicode')).text
    assert 'cf_deleted' in html
    assert 'deleted later' in html


def test_user_page_of_banned_user(http):
    html = http('/user/name/Mallory').text
    assert 'Mallory wurde aus dem Projekt' in html


def test_user_page_shows_admin_comment(http):
    assert '<b>Kommentar:</b> Admin note' in http('/user/name/Bob').text


def test_user_page_does_not_name_hidden_confirmers(http):
    html = http('/user/name/Alice').text
    assert 'Eve' not in html
    assert 'by a user who left' not in html


def test_unknown_user(http):
    response = http('/user/name/Nobody')
    assert response.status == 200
    assert 'der angegebene Benutzer existiert nicht' in response.text


def test_confirmation_page(http):
    html = http('/confirmation/101/102').text
    assert 'Alice hat Bob am 2008-02-20 um 10:00 Uhr bestätigt' in html
    assert 'Stammtisch <a href="https://de.wikipedia.org/wiki/Berlin">Berlin</a>' in html
    assert 'Bob hat Alice am 2008-02-20 um 10:05 Uhr bestätigt' in html


def test_confirmation_page_one_sided(http):
    html = http('/confirmation/101/107').text
    assert 'Alice hat Zoë Ünicode am 2024-05-02 um 20:00 Uhr bestätigt' in html
    assert 'Zoë Ünicode hat Alice noch nicht bestätigt.' in html


def test_confirmation_page_with_unknown_user(http):
    assert 'Ein Fehler ist aufgetreten' in http('/confirmation/101/999').text


def test_recent_confirmations(http):
    response = http('/recent')
    assert response.status == 200
    rows = table_rows(response.text, 'recent')
    assert rows[0] == ['Datum, Uhrzeit', 'Von', 'An', 'Kommentar']
    assert len(rows) == 1 + 12
    assert rows[1] == ['2024-05-02, 20:00', 'Alice', 'Zoë Ünicode', 'Sommerfest 🎉']
    assert rows[-1] == ['2008-02-20, 10:00', 'Alice', 'Bob', 'Stammtisch Berlin']
    stamps = [r[0] for r in rows[1:]]
    assert stamps == sorted(stamps, reverse=True)


def test_recent_confirmations_second_page_is_empty(http):
    rows = table_rows(http('/recent/2').text, 'recent')
    assert rows == [['Datum, Uhrzeit', 'Von', 'An', 'Kommentar']]


def test_recent_confirmations_rejects_page_zero(http):
    assert http('/recent/0').status == 400


def test_about(http):
    assert http('/about').status == 200


def test_sql_dumps(http):
    html = http('/sql-dumps').text
    assert 'wppb-2026-01-01.sql.bz2' in html
    assert 'wppb-2026-01-02.sql.bz2' in html
    assert 'notes.txt' not in html


def test_sql_dump_download(http):
    response = http('/sql-dump-file/wppb-2026-01-02.sql.bz2')
    assert response.status == 200
    assert response.body == b'BZh91AY&SY second dump'
    assert 'attachment' in response.headers['Content-Disposition']


def test_sql_dump_download_rejects_other_files(http):
    assert http('/sql-dump-file/notes.txt').status == 400
    assert http('/sql-dump-file/..%2Fapp.py').status in (400, 404)


def test_static_files(http):
    assert http('/static/main.css').status == 200
