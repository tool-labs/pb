"""Tests for the admin area (web/admin.py): login, access control, CSRF and the pages."""
import datetime as dt
import urllib.parse

import pytest

import admin
import admin_api
import app as webapp
import config
from tests.unit.fake_admin_db import FakeAdminDatabase

CSRF = 'test-csrf-token'


@pytest.fixture
def configured(monkeypatch, fake_db_class):
    monkeypatch.setattr(config, 'secret_key', 'test-secret')
    monkeypatch.setattr(config, 'oauth_client_id', 'client-id')
    monkeypatch.setattr(config, 'oauth_client_secret', 'client-secret')
    monkeypatch.setattr(config, 'admins', ['Euku', 'Wiegels'])
    monkeypatch.setattr(webapp.app, 'secret_key', 'test-secret')
    monkeypatch.setitem(webapp.app.config, 'SESSION_COOKIE_SECURE', False)
    monkeypatch.setattr(admin, 'AdminDatabase', FakeAdminDatabase)
    FakeAdminDatabase.log = []
    return FakeAdminDatabase


@pytest.fixture
def anon(configured):
    webapp.app.config['TESTING'] = True
    with webapp.app.test_client() as test_client:
        yield test_client


@pytest.fixture
def logged_in(anon):
    with anon.session_transaction('/admin/') as session:
        session['user'] = 'Euku'
        session['csrf'] = CSRF
    return anon


def html(response):
    return response.get_data(as_text=True)


def post(client, url, **data):
    data.setdefault('csrf_token', CSRF)
    return client.post(url, data=data)


# --- login page and access control ----------------------------------------------------------

def test_login_page_explains_the_area_and_names_the_admins(anon):
    response = anon.get('/admin/login')
    assert response.status_code == 200
    page = html(response)
    for text in ('Benutzer bearbeiten', 'Bestätigungen verwalten', 'Admin-Log', 'Verschwundene Konten',
                 'Konsistenzprüfungen', 'Job-Status'):
        assert text in page
    assert '<a href="https://de.wikipedia.org/wiki/Benutzer:Euku">Euku</a>' in page
    assert '<a href="https://de.wikipedia.org/wiki/Benutzer:Wiegels">Wiegels</a>' in page
    assert 'href="/admin/login/start"' in page
    assert 'admin-navi' not in page
    assert response.headers['Cache-Control'] == 'no-store, private'


def test_login_page_without_oauth_configuration(fake_db_class, monkeypatch):
    monkeypatch.setattr(config, 'oauth_client_secret', None)
    with webapp.app.test_client() as client:
        assert 'noch nicht eingerichtet' in html(client.get('/admin/login'))
        assert client.get('/admin/login/start').status_code == 503
        assert client.get('/admin/oauth/callback?code=x&state=y').status_code == 503
        assert client.get('/admin/').status_code == 302


@pytest.mark.parametrize('path', ['/admin/', '/admin/users?q=Al', '/admin/user/1', '/admin/confirmation/1/2',
                                  '/admin/audit', '/admin/vanished', '/admin/checks', '/admin/jobs'])
def test_pages_need_a_login(anon, path):
    response = anon.get(path)
    assert response.status_code == 302
    location = urllib.parse.urlsplit(response.headers['Location'])
    assert location.path == '/admin/login'
    assert urllib.parse.parse_qs(location.query)['next'] == [path]


@pytest.mark.parametrize('path', ['/admin/user/1/update', '/admin/user/1/hide', '/admin/user/1/relink',
                                  '/admin/confirmation/1/2/update', '/admin/confirmation/1/2/delete'])
def test_changes_need_a_login(anon, path):
    assert anon.post(path, data={'reason': 'x', 'hidden': '1'}).status_code == 403
    assert FakeAdminDatabase.log == []


def test_login_start_redirects_to_meta(anon):
    response = anon.get('/admin/login/start?next=/admin/audit')
    assert response.status_code == 302
    url = urllib.parse.urlsplit(response.headers['Location'])
    assert url.scheme + '://' + url.netloc + url.path == 'https://meta.wikimedia.org/w/rest.php/oauth2/authorize'
    query = urllib.parse.parse_qs(url.query)
    assert query['client_id'] == ['client-id']
    assert query['response_type'] == ['code']
    with anon.session_transaction('/admin/') as session:
        assert session['oauth_state'] == query['state'][0]
        assert session['next'] == '/admin/audit'


def start_login(client, monkeypatch, profile, next_url='/admin/audit'):
    """Runs the OAuth round trip with a faked Meta; returns the callback response."""
    codes = []

    def fake_fetch_profile(code):
        codes.append(code)
        return profile
    monkeypatch.setattr(admin, 'fetch_profile', fake_fetch_profile)
    location = client.get('/admin/login/start?next=' + next_url).headers['Location']
    state = urllib.parse.parse_qs(urllib.parse.urlsplit(location).query)['state'][0]
    response = client.get('/admin/oauth/callback?code=the-code&state=' + state)
    return response, codes


def test_login_of_an_admin(anon, monkeypatch):
    response, codes = start_login(anon, monkeypatch, {'username': 'Wiegels', 'blocked': False})
    assert codes == ['the-code']
    assert response.status_code == 302
    assert response.headers['Location'] == '/admin/audit'
    cookie = response.headers['Set-Cookie']
    assert 'pb_admin=' in cookie and 'Path=/admin' in cookie and 'HttpOnly' in cookie and 'SameSite=Lax' in cookie
    page = html(anon.get('/admin/'))
    assert 'angemeldet als <b>Wiegels</b>' in page
    with anon.session_transaction('/admin/') as session:
        assert session['user'] == 'Wiegels'
        assert len(session['csrf']) > 20
        assert 'oauth_state' not in session


def test_login_of_a_normal_user_is_refused(anon, monkeypatch):
    response, _ = start_login(anon, monkeypatch, {'username': 'Alice', 'blocked': False})
    assert response.status_code == 403
    page = html(response)
    assert 'Das Konto „Alice“ ist kein Admin dieses Tools.' in page
    assert 'Euku, Wiegels' in page
    assert anon.get('/admin/').status_code == 302
    with anon.session_transaction('/admin/') as session:
        assert 'user' not in session


def test_login_of_a_blocked_admin_is_refused(anon, monkeypatch):
    response, _ = start_login(anon, monkeypatch, {'username': 'Euku', 'blocked': True})
    assert response.status_code == 403
    assert anon.get('/admin/').status_code == 302


def test_callback_with_a_wrong_state(anon, monkeypatch):
    called = []
    monkeypatch.setattr(admin, 'fetch_profile', lambda code: called.append(code))
    anon.get('/admin/login/start')
    response = anon.get('/admin/oauth/callback?code=the-code&state=forged')
    assert response.status_code == 400
    assert 'abgelaufen oder ungültig' in html(response)
    assert called == []


def test_callback_without_login_start(anon, monkeypatch):
    monkeypatch.setattr(admin, 'fetch_profile', lambda code: pytest.fail('must not be called'))
    assert anon.get('/admin/oauth/callback?code=x&state=').status_code == 400


def test_callback_when_the_user_cancels(anon):
    anon.get('/admin/login/start')
    response = anon.get('/admin/oauth/callback?error=access_denied&state=x')
    assert response.status_code == 400
    assert 'abgebrochen' in html(response)


def test_callback_when_meta_fails(anon, monkeypatch):
    def failing(code):
        raise OSError('timeout')
    monkeypatch.setattr(admin, 'fetch_profile', failing)
    location = anon.get('/admin/login/start').headers['Location']
    state = urllib.parse.parse_qs(urllib.parse.urlsplit(location).query)['state'][0]
    response = anon.get('/admin/oauth/callback?code=x&state=' + state)
    assert response.status_code == 502
    assert anon.get('/admin/').status_code == 302


@pytest.mark.parametrize('next_url', ['//evil.example/', 'https://evil.example/'])
def test_login_does_not_redirect_to_other_sites(anon, monkeypatch, next_url):
    response, _ = start_login(anon, monkeypatch, {'username': 'Euku'}, next_url=urllib.parse.quote(next_url))
    assert response.headers['Location'] == '/'


def test_fetch_profile_exchanges_the_code(monkeypatch):
    monkeypatch.setattr(config, 'oauth_client_id', 'client-id')
    monkeypatch.setattr(config, 'oauth_client_secret', 'client-secret')
    calls = []

    def fake_http_json(url, data=None, token=None):
        calls.append((url, data, token))
        return {'access_token': 'tok'} if url.endswith('/access_token') else {'username': 'Euku'}
    monkeypatch.setattr(admin, 'http_json', fake_http_json)
    assert admin.fetch_profile('the-code') == {'username': 'Euku'}
    base = 'https://meta.wikimedia.org/w/rest.php/oauth2'
    assert calls == [
        (base + '/access_token', {'grant_type': 'authorization_code', 'code': 'the-code',
                                  'client_id': 'client-id', 'client_secret': 'client-secret'}, None),
        (base + '/resource/profile', None, 'tok'),
    ]


def test_an_admin_removed_from_the_list_loses_access(logged_in, monkeypatch):
    assert logged_in.get('/admin/').status_code == 200
    monkeypatch.setattr(config, 'admins', ['Wiegels'])
    assert logged_in.get('/admin/').status_code == 302


def test_logout(logged_in):
    response = post(logged_in, '/admin/logout')
    assert response.status_code == 302
    assert 'abgemeldet' in html(logged_in.get('/admin/login'))
    assert logged_in.get('/admin/').status_code == 302


def test_public_pages_set_no_cookie(anon):
    assert 'Set-Cookie' not in anon.get('/').headers
    assert 'Set-Cookie' not in anon.get('/admin/login').headers


@pytest.mark.parametrize('token', [None, '', 'wrong'])
def test_changes_need_the_csrf_token(logged_in, token):
    data = {'reason': 'x', 'hidden': '1'}
    if token is not None:
        data['csrf_token'] = token
    assert logged_in.post('/admin/user/1/update', data=data).status_code == 400
    assert FakeAdminDatabase.log == []


# --- pages -----------------------------------------------------------------------------------------

def test_overview(logged_in):
    page = html(logged_in.get('/admin/'))
    assert 'Admin: Übersicht' in page
    assert '<tr><th>Teilnehmer</th><td>4</td></tr>' in page
    assert 'href="/admin/vanished"' in page


def test_user_search_shows_hidden_and_banned_users(logged_in):
    assert ('<a href="/admin/user/3">Eve</a> <span class="badge badge-hidden">versteckt</span>'
            in html(logged_in.get('/admin/users?q=eve')))
    page = html(logged_in.get('/admin/users?q=a'))
    assert '<a href="/admin/user/4">Mallory</a> <span class="badge badge-banned">ausgeschlossen</span>' in page
    assert '<a href="/admin/user/1">Alice</a>' in page


def test_user_page(logged_in):
    page = html(logged_in.get('/admin/user/2'))
    assert 'Admin: Bob' in page
    assert '<textarea name="comment" rows="2">Admin note</textarea>' in page
    assert 'Vergebene Bestätigungen (1)' in page
    assert 'Erhaltene Bestätigungen (1)' in page
    assert 'href="/admin/confirmation/2/1"' in page and 'href="/admin/confirmation/1/2"' in page
    assert 'left, see <a href="https://de.wikipedia.org/wiki/WP%3APB">WP:PB</a>' in page
    assert f'name="csrf_token" value="{CSRF}"' in page


def test_user_page_of_unknown_user(logged_in):
    assert logged_in.get('/admin/user/12345').status_code == 404


def test_update_user(logged_in):
    response = post(logged_in, '/admin/user/2/update', hidden='1', comment='Sockenpuppe', reason='siehe [[VM]]')
    assert response.status_code == 302
    assert response.headers['Location'] == '/admin/user/2'
    assert FakeAdminDatabase.log == [('update_user', 2, {'user_is_hidden': True, 'user_was_banned': False,
                                                         'user_comment': 'Sockenpuppe'}, 'siehe [[VM]]', 'Euku')]
    assert 'Gespeichert: user_is_hidden, user_was_banned.' in html(logged_in.get('/admin/user/2'))


def test_update_user_without_reason(logged_in):
    post(logged_in, '/admin/user/2/update', hidden='1', comment='', reason=' ')
    assert FakeAdminDatabase.log == []
    assert 'Bitte eine Begründung angeben.' in html(logged_in.get('/admin/user/2'))


def test_relink_shows_a_preview_first(logged_in):
    response = post(logged_in, '/admin/user/2/relink', name='Bobby', reason='falsche user_id')
    assert response.status_code == 200
    page = html(response)
    assert 'user_id-Korrektur: 2 → 99' in page
    assert '<input type="hidden" name="confirm" value="1"/>' in page
    assert [call for call in FakeAdminDatabase.log if call[0] != 'get_audit_entries'] == [('plan_relink', 2, 'Bobby')]


def test_relink_without_an_account(logged_in):
    page = html(post(logged_in, '/admin/user/2/relink', name='Nobody', reason=''))
    assert 'kein Benutzerkonto „Nobody“' in page
    assert 'name="confirm"' not in page


def test_relink_confirmed(logged_in):
    response = post(logged_in, '/admin/user/2/relink', name='Bobby', reason='falsche user_id', confirm='1')
    assert response.headers['Location'] == '/admin/user/99'
    assert ('relink', 2, 'Bobby', 'falsche user_id', 'Euku') in FakeAdminDatabase.log


def test_confirmation_page(logged_in):
    page = html(logged_in.get('/admin/confirmation/1/2'))
    assert 'Admin: Bestätigung Alice → Bob' in page
    assert 'Stammtisch Berlin' in page
    assert 'href="/admin/confirmation/2/1">vorhanden' in page
    assert logged_in.get('/admin/confirmation/2/4').status_code == 404


def test_update_confirmation(logged_in):
    post(logged_in, '/admin/confirmation/1/2/update', deleted='1', comment='x', reason='Sockenpuppe')
    assert FakeAdminDatabase.log == [('update_confirmation', 1, 2, {'cf_was_deleted': True, 'cf_comment': 'x'},
                                      'Sockenpuppe', 'Euku')]


def test_delete_confirmation_needs_the_checkbox(logged_in):
    post(logged_in, '/admin/confirmation/1/2/delete', reason='versehentlich')
    assert FakeAdminDatabase.log == []
    response = post(logged_in, '/admin/confirmation/1/2/delete', reason='versehentlich', really='1')
    assert response.headers['Location'] == '/admin/user/1'
    assert FakeAdminDatabase.log == [('delete_confirmation', 1, 2, 'versehentlich', 'Euku')]


@pytest.mark.parametrize('query, expected', [
    ('', (None, '', '', 1)),
    ('?user=Bob&action=rename&performer=Euku&page=2', (2, 'rename', 'Euku', 2)),
    ('?user=3', (3, '', '', 1)),
    ('?user=Nobody', (-1, '', '', 1)),
    ('?action=drop+table&page=0', (None, '', '', 1)),
])
def test_audit_filters(logged_in, query, expected):
    assert logged_in.get('/admin/audit' + query).status_code == 200
    assert FakeAdminDatabase.log == [('get_audit_entries',) + expected]


def test_audit_page(logged_in):
    page = html(logged_in.get('/admin/audit?action=user_change'))
    assert '<option value="user_change" selected>user_change</option>' in page
    assert '<option value="update-user-names (Job)">' in page
    assert 'href="/admin/audit?page=2&amp;action=user_change">Ältere' in page


def test_vanished_page_suggests_the_reason(logged_in):
    page = html(logged_in.get('/admin/vanished'))
    assert 'Bereits versteckt: 7.' in page
    assert ('value="Konto auf eigenen Wunsch verschwunden (Globale Umbenennung auf Meta am 2024-09-29: '
            'per [[m:Special:GlobalRenameQueue/request/129480|request]])"') in page
    assert 'action="/admin/user/2/hide"' in page


def test_vanished_page_when_meta_is_unreachable(logged_in, monkeypatch):
    def failing(self):
        raise OSError('no route')
    monkeypatch.setattr(FakeAdminDatabase, 'get_vanished_candidates', failing)
    page = html(logged_in.get('/admin/vanished'))
    assert 'nicht erreichbar (no route)' in page


def test_hide_user(logged_in):
    response = post(logged_in, '/admin/user/2/hide', reason='verschwunden', next='/admin/vanished')
    assert response.headers['Location'] == '/admin/vanished'
    assert FakeAdminDatabase.log == [('update_user', 2, {'user_is_hidden': True}, 'verschwunden', 'Euku')]
    assert 'Bob ist jetzt versteckt.' in html(logged_in.get('/admin/vanished'))


def test_checks_page(logged_in):
    page = html(logged_in.get('/admin/checks'))
    assert 'Selbstbestätigungen (1)' in page
    assert 'Verifizierung passt nicht zu den Bestätigungen (1)' in page
    assert 'nicht als gelöscht markiert (1)' in page
    assert '<td>Alice2</td>' in page


def test_checks_page_when_the_replica_is_unreachable(logged_in, monkeypatch):
    def failing(self):
        raise OSError('no route')
    monkeypatch.setattr(FakeAdminDatabase, 'check_dewiki_accounts', failing)
    page = html(logged_in.get('/admin/checks'))
    assert 'dewiki-Replikat ist gerade nicht erreichbar' in page
    assert 'Selbstbestätigungen (1)' in page


# --- jobs ------------------------------------------------------------------------------------------

def test_read_jobs_parses_the_real_job_file():
    jobs = {job['name']: job for job in admin.read_jobs()}
    assert {'update-stats', 'update-home-wikis', 'update-user-names', 'create-database-dump'} <= set(jobs)
    assert jobs['update-stats']['schedule'] == '0    *   *   *   *'
    assert jobs['update-stats']['filelog-stderr'] == 'logs/update_stats.err'


def test_job_status(tmp_path, monkeypatch):
    jobs_file = tmp_path / 'jobs.yaml'
    jobs_file.write_text('# comment\n---\n- name: hourly\n  command: x\n  schedule: "0 * * * *"\n'
                         '  filelog-stdout: logs/hourly.out\n  filelog-stderr: logs/hourly.err\n'
                         '- name: daily\n  schedule: "0 0 * * *"\n  filelog-stderr: logs/daily.err\n'
                         '- name: missing\n  schedule: "0 0 * * *"\n  filelog-stderr: logs/missing.err\n')
    monkeypatch.setattr(config, 'jobs_file', str(jobs_file))
    monkeypatch.setattr(config, 'log_dir', str(tmp_path))
    (tmp_path / 'hourly.err').write_text('a - [INFO ] - Run completed\nb - [ERROR] - boom\n')
    (tmp_path / 'daily.err').write_text('c - [INFO ] - Run completed\n')
    (tmp_path / 'quiet.err').write_text('')
    with open(jobs_file, 'a') as f:
        f.write('- name: quiet\n  schedule: "0 0 * * *"\n  filelog-stderr: logs/quiet.err\n')
    now = dt.datetime.now()
    status = {job['name']: job for job in admin.job_status(now + dt.timedelta(hours=3))}
    assert status['hourly']['stale'] and not status['daily']['stale'] and status['missing']['stale']
    assert status['hourly']['has_problems'] and not status['daily']['has_problems']
    assert status['hourly']['stderr']['problems'] == ['b - [ERROR] - boom']
    assert status['hourly']['stderr']['last_completed'] == 'a - [INFO ] - Run completed'
    assert status['hourly']['stdout'] is None
    assert status['missing']['stderr'] is None
    assert status['quiet']['silent'] and not status['quiet']['stale']


def test_jobs_page(logged_in, tmp_path, monkeypatch):
    monkeypatch.setattr(config, 'log_dir', str(tmp_path))
    (tmp_path / 'update_stats.err').write_text('x - [INFO ] - Run completed\n')
    page = html(logged_in.get('/admin/jobs'))
    assert '<a href="#job-update-stats">update-stats</a>' in page
    assert 'x - [INFO ] - Run completed' in page
    assert 'Logdatei nicht gefunden' in page


# --- helpers of admin_api --------------------------------------------------------------------------

@pytest.mark.parametrize('name, expected', [
    ('alice_b', 'Alice b'), ('  Bob   Smith ', 'Bob Smith'), ('élan', 'Élan'), ('', ''),
])
def test_normalize_user_name(name, expected):
    assert admin_api.normalize_user_name(name) == expected


@pytest.mark.parametrize('name, vanished', [
    ('Vanished user e175adb86e72bb96a1706f7ab31b9df8', True),
    ('Renamed user 09876576', True),
    ('GelöschterBenutzer77977', True),
    ('User 20260213-1', True),
    ('User 20260213-1x', False),
    ('Vanished', False),
    ('Alice', False),
])
def test_vanished_names(name, vanished):
    assert bool(admin_api.VANISHED_RE.match(name)) == vanished


def test_vanished_reason():
    rename = {'timestamp': dt.datetime(2020, 7, 28, 12, 0), 'comment': 'courtesy vanishing'}
    assert admin_api.vanished_reason(rename) == ('Konto auf eigenen Wunsch verschwunden '
                                                 '(Globale Umbenennung auf Meta am 2020-07-28: courtesy vanishing)')
    assert 'kein Eintrag im Umbenennungs-Logbuch' in admin_api.vanished_reason(None)


@pytest.mark.parametrize('field, value, expected', [
    ('user_is_hidden', True, 1), ('user_is_hidden', '', 0), ('cf_was_deleted', 1, 1),
    ('user_comment', '  note\r\nline 2 ', 'note\nline 2'), ('user_comment', '   ', None), ('cf_comment', None, None),
])
def test_normalize(field, value, expected):
    assert admin_api._normalize(field, value) == expected
