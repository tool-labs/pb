"""Tests for the translations (i18n.py) and the language choice of the web app."""
import re

import pytest

import i18n
from tests.conftest import WEB_DIR

PLACEHOLDER_RE = re.compile(r'\{(\w+)\}')
TAG_RE = re.compile(r'<(/?(?:a|span|code|br)\b[^>]*)>')  # links etc. must survive the translation


def test_every_language_has_a_catalog():
    assert len(i18n.LANGUAGES) == 24
    assert set(i18n.CATALOGS) == set(i18n.LANGUAGES)
    assert {'de', 'en', 'ca', 'cs', 'nl', 'pl'} <= set(i18n.LANGUAGES)


@pytest.mark.parametrize('code', sorted(i18n.LANGUAGES))
def test_catalog_is_complete_and_consistent(code):
    reference = i18n.CATALOGS['en']
    catalog = i18n.CATALOGS[code]
    assert set(catalog) == set(reference)
    for key, text in catalog.items():
        assert set(PLACEHOLDER_RE.findall(text)) == set(PLACEHOLDER_RE.findall(reference[key])), key
        assert sorted(TAG_RE.findall(text)) == sorted(TAG_RE.findall(reference[key])), key


def test_every_key_used_in_the_templates_exists():
    sources = [*(WEB_DIR / 'templates').glob('*.html'), WEB_DIR / 'app.py']
    used = {key for path in sources for key in re.findall(r"_\('([\w.]+)'", path.read_text())}
    assert used and used <= set(i18n.CATALOGS['en'])


def html(response):
    return response.get_data(as_text=True)


def test_english_without_browser_language(plain_client):
    page = html(plain_client.get('/'))
    assert '<html lang="en" dir="ltr">' in page
    assert 'Participants in the <em>Personal acquaintances</em> project: 2.' in page


@pytest.mark.parametrize('header, expected', [
    ('de', 'de'),
    ('de-AT,de;q=0.9,en;q=0.8', 'de'),
    ('fr-CH, fr;q=0.9, en;q=0.8, de;q=0.7', 'fr'),
    ('sv, de;q=0.5', 'de'),             # first supported language
    ('sv, fi;q=0.5', 'en'),             # no supported language
    ('en;q=0.5, ja', 'ja'),             # the quality counts, not the order
    ('zh-TW', 'zh'),
    ('*', 'en'),
])
def test_browser_language(plain_client, header, expected):
    page = html(plain_client.get('/about', headers={'Accept-Language': header}))
    assert f'<html lang="{expected}"' in page


def test_right_to_left_languages(plain_client):
    assert '<html lang="ar" dir="rtl">' in html(plain_client.get('/', headers={'Accept-Language': 'ar'}))


def test_cookie_overrides_browser_language(plain_client):
    plain_client.set_cookie(i18n.COOKIE_NAME, 'es')
    assert '<html lang="es"' in html(plain_client.get('/', headers={'Accept-Language': 'de'}))


def test_unknown_cookie_value_is_ignored(plain_client):
    plain_client.set_cookie(i18n.COOKIE_NAME, 'xx')
    assert '<html lang="de"' in html(plain_client.get('/', headers={'Accept-Language': 'de'}))


def test_forcedlang_overrides_cookie_and_browser(plain_client):
    plain_client.set_cookie(i18n.COOKIE_NAME, 'de')
    response = plain_client.get('/users?forcedlang=en', headers={'Accept-Language': 'de'})
    assert '<html lang="en"' in html(response)
    assert 'Set-Cookie' not in response.headers     # only for this request


def test_unknown_forcedlang_is_ignored(plain_client):
    assert '<html lang="de"' in html(plain_client.get('/?forcedlang=xx', headers={'Accept-Language': 'de'}))


def test_no_cookie_without_a_manual_choice(plain_client):
    response = plain_client.get('/', headers={'Accept-Language': 'fr'})
    assert 'Set-Cookie' not in response.headers


def test_pages_vary_by_language(client):
    vary = client.get('/').headers['Vary']
    assert 'Accept-Language' in vary and 'Cookie' in vary


def test_language_menu_links_back_to_the_current_page(client):
    page = html(client.get('/users?verified=yes&forcedlang=de'))
    assert '<summary><span class="flag">🇩🇪</span> Deutsch</summary>' in page
    # forcedlang is left out, otherwise it would override the choice
    assert 'href="/lang/ja?next=/users?verified%3Dyes"' in page
    assert page.count('<li><a href="/lang/') == len(i18n.LANGUAGES)


def test_choosing_a_language_sets_the_cookie_and_goes_back(plain_client):
    response = plain_client.get('/lang/ja?next=/users?verified%3Dyes', headers={'Accept-Language': 'de'})
    assert response.status_code == 302
    assert response.headers['Location'] == '/users?verified=yes'
    cookie = response.headers['Set-Cookie']
    assert cookie.startswith(f'{i18n.COOKIE_NAME}=ja;')
    assert 'Max-Age=' in cookie and 'HttpOnly' in cookie and 'SameSite=Lax' in cookie
    assert '<html lang="ja"' in html(plain_client.get('/users', headers={'Accept-Language': 'de'}))


def test_choosing_the_browser_language_needs_no_cookie(plain_client):
    response = plain_client.get('/lang/de?next=/', headers={'Accept-Language': 'de'})
    assert response.status_code == 302
    assert 'Set-Cookie' not in response.headers


def test_choosing_the_browser_language_removes_an_old_cookie(plain_client):
    plain_client.set_cookie(i18n.COOKIE_NAME, 'ja')
    response = plain_client.get('/lang/de?next=/', headers={'Accept-Language': 'de'})
    assert response.headers['Set-Cookie'].startswith(f'{i18n.COOKIE_NAME}=;')
    assert '<html lang="de"' in html(plain_client.get('/', headers={'Accept-Language': 'de'}))


@pytest.mark.parametrize('next_url', ['https://evil.example/', '//evil.example/', '/\\evil.example', 'users', ''])
def test_choosing_a_language_only_redirects_within_the_site(plain_client, next_url):
    response = plain_client.get('/lang/en', query_string={'next': next_url})
    assert response.headers['Location'] == '/'


def test_unknown_language_choice(plain_client):
    assert plain_client.get('/lang/xx').status_code == 404


@pytest.mark.parametrize('path', ['/', '/about', '/users', '/recent', '/user/name/Alice', '/user/name/Nobody',
                                  '/confirmation/1/2', '/confirmation/1/99', '/sql-dumps'])
@pytest.mark.parametrize('code', sorted(i18n.LANGUAGES))
def test_all_pages_render_in_all_languages(plain_client, path, code):
    response = plain_client.get(path, query_string={'forcedlang': code})
    assert response.status_code == 200
    page = html(response)
    assert f'<html lang="{code}"' in page
    assert '{' not in page.split('<script', 1)[0]          # no unfilled placeholders in the head
    assert not re.search(r'>[^<]*\{\w+\}', page.split('</head>', 1)[1].split('<script', 1)[0])


def test_translated_values_are_escaped(plain_client, fake_db_class):
    assert i18n.gettext('user.title', name='<b>x</b>') == 'Participant information for &lt;b&gt;x&lt;/b&gt;'


@pytest.mark.parametrize('code, title', [
    ('de', 'Wikipedia:Persönliche Bekanntschaften'),
    ('en', 'Wikipedia:Personal acquaintances'),
    ('ca', 'Viquipèdia:Usuaris coneguts'),
    ('cs', 'Wikipedie:Osobní známosti'),
    ('es', 'Wikipedia:Conocidos personales'),
    ('fr', 'Wikipédia:Connaissances personnelles'),
    ('it', 'Wikipedia:Conoscenze personali'),
    ('nl', 'Wikipedia:Ontmoete Wikimedianen'),
])
def test_project_names_of_the_sister_projects(plain_client, code, title):
    """The names of the project pages that already exist in these Wikipedias."""
    assert f'| {title} |' in html(plain_client.get('/sql-dumps', query_string={'forcedlang': code}))
