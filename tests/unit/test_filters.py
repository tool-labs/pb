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
    assert webapp.format_boolean(True) == 'ja'
    assert webapp.format_boolean(1) == 'ja'
    assert webapp.format_boolean(False) == 'nein'
    assert webapp.format_boolean(None) == 'nein'


@pytest.mark.parametrize('comment', [None, ''])
def test_parse_comment_handles_empty_comments(comment):
    assert webapp.format_comment(comment) == ''


def test_parse_comment_keeps_plain_text():
    assert webapp.format_comment('Met at WikiCon') == 'Met at WikiCon'


def test_parse_comment_links_a_single_wikilink():
    assert (webapp.format_comment('Met at [[WikiCon]]')
            == 'Met at <a href="https://de.wikipedia.org/wiki/WikiCon">[[WikiCon]]</a>')


@pytest.mark.xfail(reason='known bug: the regex [^}]* is greedy and swallows everything between the first [[ and the last ]]')
def test_parse_comment_links_multiple_wikilinks():
    html = webapp.format_comment('[[Berlin]] and [[Hamburg]]')
    assert html.count('<a ') == 2
    assert 'wiki/Berlin"' in html and 'wiki/Hamburg"' in html


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
