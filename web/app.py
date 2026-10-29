import calendar
import datetime
import gzip
import os.path, os
import re
from urllib.parse import quote
import config
from api import Database
import flask
from markupsafe import Markup, escape
import logging

logger = logging.getLogger('pb')

def render_template(template, **context):
    text = flask.render_template(template, **context)
    return prettify_html(text)

def prettify_html(html):
    return ''.join(line + os.linesep for line in html.splitlines() if line.strip())

app = flask.Flask(__name__)
# let browsers cache the static files for a day instead of revalidating them on every page view
app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 86400

@app.after_request
def compress_response(response):
    """
    Gzips text responses; the pages compress about 10-14 times smaller.
    """
    if (response.status_code != 200 or 'Content-Encoding' in response.headers
            or 'gzip' not in flask.request.headers.get('Accept-Encoding', '')
            or response.mimetype not in ('text/html', 'text/css', 'text/javascript', 'application/javascript')):
        return response
    response.direct_passthrough = False
    data = response.get_data()
    if len(data) < 1000:
        return response
    response.set_data(gzip.compress(data, compresslevel=6))
    response.headers['Content-Encoding'] = 'gzip'
    response.vary.add('Accept-Encoding')
    return response

@app.template_filter('format_date')
def format_date(date):
    if date is None:
        return ""
    return date.strftime("%Y-%m-%d")

@app.template_filter('format_time')
def format_time(time):
    if time is None:
        return ""
    return time.strftime("%H:%M")

@app.template_filter('format_boolean')
def format_boolean(boolean):
    return "ja" if boolean else "nein"

LINK_RE = re.compile(r'\[\[([^\[\]|]+)(?:\|([^\[\]]*))?\]\]')

@app.template_filter('parse_comment')
def format_comment(comment):
    """
    Turns [[target]] and [[target|label]] into links to de.wikipedia.org.
    The comment is escaped first, so the result is safe to mark as HTML.
    The link target is unescaped again before it is URL-encoded.
    """
    def repl(m):
        target, label = m.group(1), m.group(2) or m.group(1)
        target = Markup(target).unescape().strip().replace(' ', '_')
        return '<a href="https://de.wikipedia.org/wiki/%s">%s</a>' % (quote(target, safe='/#'), label)
    return Markup(LINK_RE.sub(repl, str(escape(comment or ''))))

def get_db():
    """
    Opens the database connection on first use within a request.
    """
    if 'db' not in flask.g:
        flask.g.db = Database(use_replica=False)
    return flask.g.db

@app.teardown_request
def teardown_request(exception):
    db = flask.g.pop('db', None)
    if db is not None:
        db.close_connections()

@app.route('/')
def index():
    data = get_db().fetch_stats()
    # same count as get_confirmation_count(False, False), but taken from the hourly stats instead of a slow live query
    confirmation_count = data['confirmations']['totals'][0]
    confirmations_per_day = get_db().get_confirmations_per_day(confirmation_count)
    user_count = get_db().get_user_count(False, False)
    latest_confirmations = get_db().get_latest_confirmations(page=1, count=10)

    return render_template('index.html',
                           confirmation_count=confirmation_count,
                           confirmations_per_day=confirmations_per_day,
                           user_count=user_count,
                           latest_confirmations=latest_confirmations,
                           data=data)

@app.route('/about')
def about():
    return render_template('about.html')

@app.route('/confirmation/<int:user_id_one>/<int:user_id_two>')
def confirmation_users(user_id_one, user_id_two):
    u1 = get_db().get_user_by_id(user_id_one)
    u2 = get_db().get_user_by_id(user_id_two)
    # hidden users (who left the project) must not be shown
    if (u1 is not None and u1[3]) or (u2 is not None and u2[3]):
        flask.abort(404)
    user_one = {'user_name': u1[0], 'user_id': u1[1], 'user_comment': u1[2], 'user_is_hidden': u1[3],
                'user_was_banned': u1[4], 'user_participates_since': u1[5], 'user_verified_since': u1[6] } if u1 is not None else None
    user_two = {'user_name': u2[0], 'user_id': u2[1], 'user_comment': u2[2], 'user_is_hidden': u2[3],
                'user_was_banned': u2[4], 'user_participates_since': u2[5], 'user_verified_since': u2[6] } if u2 is not None else None
    cf12 = get_db().get_confirmation(user_id_one, user_id_two)
    cf_one_two = {'cf_timestamp': cf12[0], 'cf_comment': cf12[1]} if cf12 is not None else None
    cf21 = get_db().get_confirmation(user_id_two, user_id_one)
    cf_two_one = {'cf_timestamp': cf21[0], 'cf_comment': cf21[1]} if cf21 is not None else None

    return render_template('confirmation.html', user_one=user_one, user_two=user_two,
                           cf_one_two=cf_one_two, cf_two_one=cf_two_one)

@app.route('/recent')
@app.route('/recent/<int:page>')
def recent_confirmations(page=1):
    if page < 1:
        flask.abort(400)

    confirmations = get_db().get_latest_confirmations(page, count=50)
    return render_template('recent_changes.html', confirmations=confirmations, page=page)

@app.route('/user/name/<path:user_name>')
def user(user_name=None):
    user = get_db().get_user_dict_by_name(user_name)
    if user is None:
        return render_template('user.html', user=None)
    # hidden users (who left the project) must not be shown
    if user['hidden']:
        flask.abort(404)

    confirmations_given = get_db().get_confirmations_by_user(user['id'], show_hidden_users=False)
    confirmations_received = get_db().get_confirmations_by_confirmed(user['id'], show_hidden_users=False)

    return render_template('user.html',
                           user=user,
                           home_wiki=get_db().get_home_wiki(user['id']),
                           confirmations_given=confirmations_given,
                           confirmations_received=confirmations_received)

RECENT_MONTHS = 6
# allowed values of the filters on /users ('' = all)
USER_FILTERS = {'verified': ('yes', 'no'), 'recent': ('received', 'given', 'any')}
NO_SUL = 'none'

def today():
    return datetime.date.today()

def months_before(day, months):
    """*day* minus *months* calendar months, as datetime at midnight (Aug 31 - 6 = Feb 28)."""
    month = day.month - months
    year = day.year + (month - 1) // 12
    month = (month - 1) % 12 + 1
    return datetime.datetime(year, month, min(day.day, calendar.monthrange(year, month)[1]))

def _user_filters(args):
    """The filters of /users from the query string; unknown values are ignored."""
    filters = {'homewiki': args.get('homewiki', '').strip()}
    for name, values in USER_FILTERS.items():
        value = args.get(name, '')
        filters[name] = value if value in values else ''
    return filters

def _user_matches(user, filters, since):
    home_wiki = user['home_wiki']
    if filters['homewiki'] == NO_SUL:
        if home_wiki is None or home_wiki['sul']:
            return False
    elif filters['homewiki'] and (home_wiki is None or home_wiki['db'] != filters['homewiki']):
        return False
    if filters['verified'] and (user['verified_since'] is not None) != (filters['verified'] == 'yes'):
        return False
    received = user['last_taken'] is not None and user['last_taken'] >= since
    given = user['last_given'] is not None and user['last_given'] >= since
    if filters['recent'] == 'received' and not received:
        return False
    if filters['recent'] == 'given' and not given:
        return False
    if filters['recent'] == 'any' and not (received or given):
        return False
    return True

def _home_wiki_options(users, selected):
    """`(value, label, count)` for the home wiki filter, the most frequent first."""
    counts = {}
    for user in users:
        home_wiki = user['home_wiki']
        if home_wiki is not None:
            key = home_wiki['db'] if home_wiki['sul'] else NO_SUL
            if key:
                counts[key] = counts.get(key, 0) + 1
    if selected and selected not in counts:
        counts[selected] = 0
    labels = {NO_SUL: 'kein SUL-Konto auf dewiki'}
    return [(key, labels.get(key, key), count)
            for key, count in sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))]

@app.route('/users')
def users():
    all_users = get_db().get_user_list()
    filters = _user_filters(flask.request.args)
    since = months_before(today(), RECENT_MONTHS)
    users = [user for user in all_users if _user_matches(user, filters, since)]
    return render_template('users.html', users=users, total=len(all_users), filters=filters,
                           filtered=any(filters.values()), since=since, recent_months=RECENT_MONTHS,
                           home_wikis=_home_wiki_options(all_users, filters['homewiki']))

@app.route('/sql-dumps')
def sql_dumps():
    files_list = _scan_dir(config.sql_dump_folder)
    return render_template('sql-dumps.html', files_list=files_list)

@app.route('/sql-dump-file/<file_name>')
def sql_dump_file(file_name):
    if not re.fullmatch(re.compile(r"wppb\-20\d\d-\d\d-\d\d\.sql\.bz2(\.enc)?"), file_name):
        return flask.abort(400)
    try:
        return flask.send_from_directory(config.sql_dump_folder, file_name, as_attachment=True)
    except FileNotFoundError:
        flask.abort(404)

def _scan_dir(root_dir: str):
    result = []
    walk_result = os.walk(root_dir)
    walk_result = sorted(walk_result, reverse=True)
    for root, dirs, files in walk_result:
        sorted_files = sorted(files)
        for file in sorted_files:
            if file.endswith(('.sql.bz2', '.sql.bz2.enc', '.sql')):
                file_path = os.path.join(root, file)
                file_size = os.path.getsize(file_path)
                result.append([file, file_size])
    return result

if __name__ == "__main__":
    # only for local tests, the webservice runs the app via uwsgi
    app.run(debug = True, threaded = True, host='0.0.0.0', port=80, use_reloader=True)
