# -*- coding: utf-8 -*-
"""
Admin area under /admin: login with OAuth 2.0 on Meta (Wikimedia account), only for the
user names in `config.admins`. Everything an admin changes is recorded in `audit_trail`
(web/admin_api.py). The pages are in German only, like the project.

Setup (Toolforge envvars of the tool pb): PB_OAUTH_CLIENT_ID, PB_OAUTH_CLIENT_SECRET,
PB_SECRET_KEY (random, signs the session cookie). The OAuth consumer on Meta needs the
callback URL https://pb.toolforge.org/admin/oauth/callback and only "User identity
verification only".
"""
import datetime
import json
import os
import re
import secrets
import urllib.error
import urllib.parse
import urllib.request

import flask

import config
import i18n
from admin_api import AdminDatabase, AdminError, RELINK_MOVE, VANISHED_RE
from api import AUDIT_ACTIONS

bp = flask.Blueprint('admin', __name__, url_prefix='/admin')

USER_AGENT = 'pb.toolforge.org admin login (https://pb.toolforge.org/; https://github.com/tool-labs/pb)'
HTTP_TIMEOUT = 15
# pages that can be opened without being logged in
PUBLIC_ENDPOINTS = {'admin.login', 'admin.login_start', 'admin.oauth_callback', 'admin.logout'}
AUDIT_PAGE_SIZE = 100
LOG_TAIL_BYTES = 64 * 1024
LOG_TAIL_LINES = 15
PROBLEM_RE = re.compile(r'ERROR|CRITICAL|Traceback|Exception')

FEATURES = [
    ('Benutzer bearbeiten', 'Teilnehmer verstecken oder ausschließen, den (öffentlichen) Admin-Kommentar ändern, '
                            'Name und user_id mit dewiki abgleichen.'),
    ('Bestätigungen verwalten', 'Bestätigungen als gelöscht markieren, ihren Kommentar ändern oder sie ganz '
                                'löschen.'),
    ('Admin-Log', 'Alle Änderungen der Admins und der Jobs mit Begründung (nicht öffentlich).'),
    ('Verschwundene Konten', 'Konten, die auf eigenen Wunsch global umbenannt wurden, mit der Begründung aus dem '
                             'Umbenennungs-Logbuch auf Meta verstecken.'),
    ('Konsistenzprüfungen', 'Widersprüche in der Datenbank und Abweichungen von dewiki finden.'),
    ('Job-Status', 'Letzte Läufe und Fehler der Toolforge-Jobs.'),
]


# --- setup -------------------------------------------------------------------

def init_app(app):
    app.secret_key = config.secret_key
    app.config.update(
        SESSION_COOKIE_NAME='pb_admin',
        # the session is only needed in the admin area, the public pages never get the cookie
        SESSION_COOKIE_PATH='/admin',
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SECURE=config.session_cookie_secure,
        SESSION_COOKIE_SAMESITE='Lax',
        PERMANENT_SESSION_LIFETIME=datetime.timedelta(hours=config.admin_session_hours),
    )
    app.register_blueprint(bp)


def is_configured():
    return bool(config.secret_key and config.oauth_client_id and config.oauth_client_secret)


def render(template, **context):
    # not prettified like the public pages: that would remove blank lines from <textarea> and <pre>
    return flask.render_template(template, **context)


def get_db():
    if 'admin_db' not in flask.g:
        flask.g.admin_db = AdminDatabase()
    return flask.g.admin_db


@bp.teardown_request
def close_db(exception):
    db = flask.g.pop('admin_db', None)
    if db is not None:
        db.close_connections()


def current_admin():
    """The logged-in admin, `None` if nobody (or somebody who is no longer an admin) is logged in."""
    if not is_configured():
        return None
    name = flask.session.get('user')
    return name if name in config.admins else None


def csrf_token():
    return flask.session.get('csrf', '')


@bp.app_template_filter('format_datetime')
def format_datetime(value):
    return value.strftime('%Y-%m-%d %H:%M') if value else ''


@bp.context_processor
def inject_admin():
    return {'admin_user': current_admin(), 'csrf_token': csrf_token(), 'admins': config.admins,
            'features': FEATURES}


@bp.before_request
def require_admin():
    if flask.request.endpoint in PUBLIC_ENDPOINTS:
        return None
    if current_admin() is None:
        if flask.request.method == 'GET':
            return flask.redirect(flask.url_for('admin.login', next=flask.request.full_path.rstrip('?')))
        flask.abort(403)
    if flask.request.method == 'POST':
        check_csrf()
    return None


def check_csrf():
    token = flask.request.form.get('csrf_token', '')
    if not token or not secrets.compare_digest(token, csrf_token()):
        flask.abort(400, 'CSRF-Token fehlt oder ist ungültig, bitte die Seite neu laden.')


@bp.after_request
def no_caching(response):
    response.headers['Cache-Control'] = 'no-store, private'
    response.headers['X-Frame-Options'] = 'DENY'
    response.headers['Referrer-Policy'] = 'same-origin'
    return response


# --- login -------------------------------------------------------------------

@bp.route('/login')
def login():
    return render('admin/login.html', configured=is_configured(), next=flask.request.args.get('next', ''))


@bp.route('/login/start')
def login_start():
    if not is_configured():
        flask.abort(503)
    state = secrets.token_urlsafe(32)
    flask.session['oauth_state'] = state
    flask.session['next'] = i18n.local_url(flask.request.args.get('next'))
    query = urllib.parse.urlencode({'response_type': 'code', 'client_id': config.oauth_client_id, 'state': state})
    return flask.redirect(config.oauth_base_url + '/authorize?' + query)


def http_json(url, data=None, token=None):
    """GET (or POST with form *data*) *url* and return the JSON answer."""
    headers = {'User-Agent': USER_AGENT, 'Accept': 'application/json'}
    if token:
        headers['Authorization'] = 'Bearer ' + token
    body = urllib.parse.urlencode(data).encode() if data is not None else None
    request = urllib.request.Request(url, data=body, headers=headers)
    with urllib.request.urlopen(request, timeout=HTTP_TIMEOUT) as response:
        return json.loads(response.read().decode('utf-8'))


def fetch_profile(code):
    """Exchanges the authorization *code* for a token and returns the profile of the user."""
    token = http_json(config.oauth_base_url + '/access_token', data={
        'grant_type': 'authorization_code', 'code': code,
        'client_id': config.oauth_client_id, 'client_secret': config.oauth_client_secret})
    return http_json(config.oauth_base_url + '/resource/profile', token=token['access_token'])


@bp.route('/oauth/callback')
def oauth_callback():
    if not is_configured():
        flask.abort(503)
    expected_state = flask.session.pop('oauth_state', None)
    next_url = flask.session.pop('next', None) or flask.url_for('admin.index')
    args = flask.request.args
    if args.get('error'):
        return render('admin/login.html', configured=True, next=next_url,
                      error='Die Anmeldung wurde abgebrochen (%s).' % args.get('error')), 400
    if not expected_state or not secrets.compare_digest(args.get('state', ''), expected_state):
        return render('admin/login.html', configured=True, next=next_url,
                      error='Die Anmeldung ist abgelaufen oder ungültig, bitte noch einmal versuchen.'), 400
    try:
        profile = fetch_profile(args.get('code', ''))
    except (urllib.error.URLError, ValueError, KeyError, OSError) as e:
        flask.current_app.logger.warning('OAuth login failed: %s', e)
        return render('admin/login.html', configured=True, next=next_url,
                      error='Die Anmeldung bei Wikimedia ist fehlgeschlagen, bitte später noch einmal versuchen.'), 502
    name = profile.get('username')
    flask.session.clear()
    if name not in config.admins or profile.get('blocked'):
        return render('admin/denied.html', name=name), 403
    flask.session.permanent = True
    flask.session['user'] = name
    flask.session['csrf'] = secrets.token_urlsafe(32)
    flask.current_app.logger.info('admin login: %s', name)
    return flask.redirect(i18n.local_url(next_url))


@bp.route('/logout', methods=['POST'])
def logout():
    if not is_configured():
        return flask.redirect(flask.url_for('admin.login'))
    if current_admin() is not None:
        check_csrf()
    flask.session.clear()
    flask.flash('Du bist abgemeldet.', 'info')
    return flask.redirect(flask.url_for('admin.login'))


# --- pages -------------------------------------------------------------------

def back(default):
    """Redirect to the `next` form field (a local URL) or *default*."""
    target = flask.request.form.get('next')
    return flask.redirect(i18n.local_url(target) if target else default)


@bp.route('/')
def index():
    return render('admin/index.html', overview=get_db().get_overview())


@bp.route('/users')
def users():
    query = flask.request.args.get('q', '').strip()
    return render('admin/users.html', query=query, users=get_db().search_users(query))


@bp.route('/user/<int:user_id>')
def user(user_id, plan=None, relink_name=None, relink_reason=''):
    db = get_db()
    user = db.get_user_admin(user_id)
    if user is None:
        flask.abort(404)
    entries, _ = db.get_audit_entries(user_id=user_id, count=50)
    return render('admin/user.html', user=user, home_wiki=db.get_home_wiki(user_id),
                  given=db.get_confirmations_by_user(user_id, show_hidden_users=True),
                  received=db.get_confirmations_by_confirmed(user_id, show_hidden_users=True),
                  entries=entries, plan=plan, relink_name=relink_name or user['name'],
                  relink_reason=relink_reason, vanished=bool(VANISHED_RE.match(user['name'])))


@bp.route('/user/<int:user_id>/update', methods=['POST'])
def user_update(user_id):
    form = flask.request.form
    changes = {'user_is_hidden': 'hidden' in form, 'user_was_banned': 'banned' in form,
               'user_comment': form.get('comment', '')}
    try:
        changed = get_db().update_user(user_id, changes, form.get('reason'), current_admin())
    except AdminError as e:
        flask.flash(e.msg, 'error')
    else:
        flask.flash('Gespeichert: %s.' % ', '.join(changed) if changed else 'Keine Änderung.', 'info')
    return back(flask.url_for('admin.user', user_id=user_id))


@bp.route('/user/<int:user_id>/hide', methods=['POST'])
def user_hide(user_id):
    form = flask.request.form
    try:
        changed = get_db().update_user(user_id, {'user_is_hidden': True}, form.get('reason'), current_admin())
    except AdminError as e:
        flask.flash(e.msg, 'error')
    else:
        user = get_db().get_user_admin(user_id)
        flask.flash(('%s ist jetzt versteckt.' if changed else '%s war schon versteckt.') % user['name'], 'info')
    return back(flask.url_for('admin.vanished'))


@bp.route('/user/<int:user_id>/relink', methods=['POST'])
def user_relink(user_id):
    """Compares name and user_id with dewiki; first a preview, the change only with `confirm`."""
    form = flask.request.form
    name, reason = form.get('name', ''), form.get('reason', '')
    db = get_db()
    try:
        if not form.get('confirm'):
            plan = db.plan_relink(user_id, name)
            return user(user_id, plan=plan, relink_name=name, relink_reason=reason)
        plan = db.relink(user_id, name, reason, current_admin())
    except AdminError as e:
        flask.flash(e.msg, 'error')
        return flask.redirect(flask.url_for('admin.user', user_id=user_id))
    flask.flash(plan['message'] + ' Erledigt.', 'info')
    new_id = plan['mw_id'] if plan['action'] == RELINK_MOVE else user_id
    return flask.redirect(flask.url_for('admin.user', user_id=new_id))


def _confirmation_or_404(user_id, confirmed_user_id):
    db = get_db()
    confirmation = db.get_confirmation_admin(user_id, confirmed_user_id)
    if confirmation is None:
        flask.abort(404)
    return confirmation


@bp.route('/confirmation/<int:user_id>/<int:confirmed_user_id>')
def confirmation(user_id, confirmed_user_id):
    db = get_db()
    confirmation = _confirmation_or_404(user_id, confirmed_user_id)
    entries, _ = db.get_audit_entries(user_id=user_id, count=200)
    entries = [e for e in entries if e['confirmed_user_id'] == confirmed_user_id]
    return render('admin/confirmation.html', cf=confirmation, giver=db.get_user_admin(user_id),
                  taker=db.get_user_admin(confirmed_user_id),
                  reverse=db.get_confirmation_admin(confirmed_user_id, user_id), entries=entries)


@bp.route('/confirmation/<int:user_id>/<int:confirmed_user_id>/update', methods=['POST'])
def confirmation_update(user_id, confirmed_user_id):
    form = flask.request.form
    changes = {'cf_was_deleted': 'deleted' in form, 'cf_comment': form.get('comment', '')}
    try:
        changed = get_db().update_confirmation(user_id, confirmed_user_id, changes, form.get('reason'),
                                               current_admin())
    except AdminError as e:
        flask.flash(e.msg, 'error')
    else:
        flask.flash('Gespeichert: %s.' % ', '.join(changed) if changed else 'Keine Änderung.', 'info')
    return back(flask.url_for('admin.confirmation', user_id=user_id, confirmed_user_id=confirmed_user_id))


@bp.route('/confirmation/<int:user_id>/<int:confirmed_user_id>/delete', methods=['POST'])
def confirmation_delete(user_id, confirmed_user_id):
    form = flask.request.form
    if not form.get('really'):
        flask.flash('Zum Löschen bitte das Kästchen „wirklich löschen“ ankreuzen.', 'error')
        return flask.redirect(flask.url_for('admin.confirmation', user_id=user_id,
                                            confirmed_user_id=confirmed_user_id))
    try:
        get_db().delete_confirmation(user_id, confirmed_user_id, form.get('reason'), current_admin())
    except AdminError as e:
        flask.flash(e.msg, 'error')
        return flask.redirect(flask.url_for('admin.confirmation', user_id=user_id,
                                            confirmed_user_id=confirmed_user_id))
    flask.flash('Die Bestätigung %s → %s wurde gelöscht (im Admin-Log gesichert).' % (user_id, confirmed_user_id),
                'info')
    return flask.redirect(flask.url_for('admin.user', user_id=user_id))


@bp.route('/audit')
def audit():
    db = get_db()
    args = flask.request.args
    user_filter = args.get('user', '').strip()
    action = args.get('action', '')
    action = action if action in AUDIT_ACTIONS else ''
    performer = args.get('performer', '').strip()
    page = args.get('page', '1')
    page = int(page) if page.isdigit() and int(page) > 0 else 1
    user_id = None
    if user_filter:
        user_id = int(user_filter) if user_filter.isdigit() else db.get_user_id_by_name(user_filter)
        if user_id is None:
            user_id = -1  # unknown name: no entries
    entries, has_more = db.get_audit_entries(user_id=user_id, action=action, performer=performer, page=page,
                                             count=AUDIT_PAGE_SIZE)
    filters = {'user': user_filter, 'action': action, 'performer': performer}
    return render('admin/audit.html', entries=entries, has_more=has_more, page=page, filters=filters,
                  actions=AUDIT_ACTIONS, performers=db.get_audit_performers(),
                  page_url=lambda p: flask.url_for('admin.audit', page=p, **{k: v for k, v in filters.items() if v}))


@bp.route('/vanished')
def vanished():
    db = get_db()
    error = None
    try:
        candidates = db.get_vanished_candidates()
    except Exception as e:  # the Meta replica may be unreachable; show the list without log entries
        flask.current_app.logger.warning('global rename log not available: %s', e)
        error = 'Das Umbenennungs-Logbuch auf Meta ist gerade nicht erreichbar (%s).' % e
        candidates = []
    return render('admin/vanished.html', candidates=candidates, hidden_count=db.count_hidden_vanished(),
                  error=error)


@bp.route('/checks')
def checks():
    db = get_db()
    dewiki, dewiki_error = None, None
    try:
        dewiki = db.check_dewiki_accounts()
    except Exception as e:  # the replica may be unreachable; the other checks still work
        flask.current_app.logger.warning('dewiki replica not available: %s', e)
        dewiki_error = str(e)
    return render('admin/checks.html', self_confirmations=db.check_self_confirmations(),
                  verification=db.check_verification(), banned=db.check_banned_confirmations(),
                  dewiki=dewiki, dewiki_error=dewiki_error)


# --- jobs ----------------------------------------------------------------------

def read_jobs(path=None):
    """The jobs of toolforge-jobs.yaml: name, schedule and log files (a simple parser, no PyYAML)."""
    jobs = []
    with open(path or config.jobs_file, encoding='utf-8') as f:
        for line in f:
            match = re.match(r'^\s*(-\s+)?([\w-]+):\s*(.*?)\s*$', line)
            if not match or line.lstrip().startswith('#'):
                continue
            new_item, key, value = match.groups()
            if new_item:
                jobs.append({})
            if jobs:
                jobs[-1][key] = value.strip('"\'')
    return [job for job in jobs if 'name' in job]


def max_age(schedule):
    """How old the log of a job may be: a bit more than its interval (hourly or daily)."""
    fields = (schedule or '').split()
    if len(fields) == 5 and fields[1] == '*':
        return datetime.timedelta(hours=2)
    return datetime.timedelta(hours=26)


def log_info(relative_path, now):
    path = os.path.join(config.log_dir, os.path.basename(relative_path or ''))
    try:
        stat = os.stat(path)
        with open(path, 'rb') as f:
            f.seek(max(0, stat.st_size - LOG_TAIL_BYTES))
            lines = f.read().decode('utf-8', 'replace').splitlines()
    except OSError:
        return None
    if stat.st_size > LOG_TAIL_BYTES:
        lines = lines[1:]  # probably cut in the middle
    modified = datetime.datetime.fromtimestamp(stat.st_mtime)
    return {'path': path, 'size': stat.st_size, 'modified': modified, 'age': now - modified,
            'tail': lines[-LOG_TAIL_LINES:],
            'problems': [line for line in lines[-200:] if PROBLEM_RE.search(line)][-LOG_TAIL_LINES:],
            'last_completed': next((line for line in reversed(lines) if 'completed' in line), None)}


def job_status(now=None):
    now = now or datetime.datetime.now()
    jobs = []
    for job in read_jobs():
        logs = [log_info(job.get(key), now) for key in ('filelog-stdout', 'filelog-stderr')]
        newest = max((log['modified'] for log in logs if log), default=None)
        # a job without any output (e.g. remove-old-logs) leaves its empty log files untouched
        silent = any(logs) and all(log['size'] == 0 for log in logs if log)
        job.update(stdout=logs[0], stderr=logs[1], newest=newest, silent=silent,
                   stale=not silent and (newest is None or now - newest > max_age(job.get('schedule'))),
                   has_problems=any(log and log['problems'] for log in logs))
        jobs.append(job)
    return jobs


@bp.route('/jobs')
def jobs():
    try:
        status = job_status()
        error = None
    except OSError as e:
        status, error = [], str(e)
    return render('admin/jobs.html', jobs=status, error=error)
