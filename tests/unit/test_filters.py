"""Tests for the Jinja filters and helpers in app.py."""
import datetime as dt

import pytest

import app as webapp


def test_format_date():
    assert webapp.format_date(dt.datetime(2008, 2, 8, 13, 5)) == '2008-02-08'
    assert webapp.format_date(None) == ''


def test_format_time():
    assert webapp.format_time(dt.datetime(2008, 2, 8, 13, 5)) == '13:05'
    assert webapp.format_time(None) == ''


def test_format_boolean():
    with webapp.app.test_request_context(headers={'Accept-Language': 'de'}):
        assert webapp.format_boolean(True) == 'ja'
        assert webapp.format_boolean(1) == 'ja'
        assert webapp.format_boolean(False) == 'nein'
        assert webapp.format_boolean(None) == 'nein'


def test_format_boolean_outside_of_a_request_is_english():
    assert webapp.format_boolean(True) == 'yes'
    assert webapp.format_boolean(False) == 'no'


@pytest.mark.parametrize('comment', [None, ''])
def test_parse_comment_handles_empty_comments(comment):
    assert webapp.format_comment(comment) == ''


def test_parse_comment_keeps_plain_text():
    assert webapp.format_comment('Met at WikiCon') == 'Met at WikiCon'


def test_parse_comment_links_a_single_wikilink():
    assert (webapp.format_comment('Met at [[WikiCon]]')
            == 'Met at <a href="https://de.wikipedia.org/wiki/WikiCon">WikiCon</a>')


def test_parse_comment_links_multiple_wikilinks():
    html = webapp.format_comment('[[Berlin]] and [[Hamburg]]')
    assert html.count('<a ') == 2
    assert 'wiki/Berlin"' in html and 'wiki/Hamburg"' in html


def test_parse_comment_links_piped_wikilinks():
    assert (webapp.format_comment('[[Wikipedia:Stammtisch Berlin|Stammtisch]]')
            == '<a href="https://de.wikipedia.org/wiki/Wikipedia%3AStammtisch_Berlin">Stammtisch</a>')


def test_parse_comment_url_encodes_the_target():
    html = webapp.format_comment('[[A&B "x" ü]]')
    assert 'href="https://de.wikipedia.org/wiki/A%26B_%22x%22_%C3%BC"' in html
    assert '>A&amp;B &#34;x&#34; ü</a>' in html


def test_parse_comment_keeps_section_links():
    assert 'href="https://de.wikipedia.org/wiki/Foo/Bar#Abschnitt"' in webapp.format_comment('[[Foo/Bar#Abschnitt]]')


def test_parse_comment_escapes_html():
    html = webapp.format_comment('<script>alert(1)</script> [[<b>X</b>]]')
    assert '<script>' not in html and '<b>' not in html
    assert '&lt;script&gt;' in html
    assert isinstance(html, webapp.Markup)


def test_prettify_html_removes_blank_lines():
    html = '<p>\n\n   \n<b>x</b>\n\t\n</p>'
    assert webapp.prettify_html(html).splitlines() == ['<p>', '<b>x</b>', '</p>']


def test_scan_dir_lists_only_sql_dumps(tmp_path):
    (tmp_path / 'wppb-2026-01-02.sql.bz2').write_bytes(b'12345')
    (tmp_path / 'wppb-2026-01-01.sql.bz2').write_bytes(b'1')
    (tmp_path / 'old.sql').write_bytes(b'12')
    (tmp_path / 'notes.txt').write_bytes(b'ignored')
    assert webapp._scan_dir(str(tmp_path)) == [
        ['old.sql', 2],
        ['wppb-2026-01-01.sql.bz2', 1],
        ['wppb-2026-01-02.sql.bz2', 5],
    ]


def test_scan_dir_of_missing_folder_is_empty(tmp_path):
    assert webapp._scan_dir(str(tmp_path / 'missing')) == []
