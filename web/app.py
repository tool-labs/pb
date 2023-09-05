import os.path, os
import re, locale
import config
from api import Database
import flask
from flask import send_file
import logging

logger = logging.getLogger('pb')

def render_template(template, **context):
    text = flask.render_template(template, **context)
    return prettify_html(text)

def prettify_html(html):
    prettified_html = ''
    for line in html.splitlines():
        if not re.match(r'^\s*$', line):
            prettified_html += line + os.linesep
    return prettified_html

app = flask.Flask(__name__)

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

@app.template_filter('format_number')
def format_number(number):
    return locale.format('%d', number, grouping=True)

@app.template_filter('format_datetime')
def format_datetime(dt):
    if dt is None:
        return ""
    dt_format = locale.nl_langinfo(locale.D_T_FMT)
    return dt.strftime(dt_format)

@app.template_filter('format_boolean')
def format_boolean(boolean):
    return "ja" if boolean else "nein"

@app.template_filter('parse_comment')
def format_comment(comment):
    p = re.compile('\[\[ ( [^}]* ) \]\]', re.VERBOSE)
    r = r'<a href="https://de.wikipedia.org/wiki/\1">[[\1]]</a>'
    return p.sub(r, comment)

@app.before_request
def before_request():
    flask.g.db = Database()

@app.after_request
def after_request(response):
    if flask.g.db is not None:
        flask.g.db.close_connections()
    return response

@app.route('/')
def index():
    confirmation_count = flask.g.db.get_confirmation_count(False, False)
    confirmations_per_day = flask.g.db.get_confirmations_per_day(confirmation_count)
    user_count = flask.g.db.get_user_count(False, False)
    latest_confirmations = flask.g.db.get_latest_confirmations(page=1, count=10)
    data = flask.g.db.fetch_stats()

    return render_template('index.html',
                           confirmation_count=confirmation_count,
                           confirmations_per_day=confirmations_per_day,
                           user_count=user_count,
                           latest_confirmations=latest_confirmations,
                           data=data)

@app.route('/about')
def about():
    return render_template('about.html')

@app.route('/confirmations')
def confirmations():
    return render_template('confirmations.html')

@app.route('/confirmation/<int:user_id_one>/<int:user_id_two>')
def confirmation_users(user_id_one, user_id_two):
    u1 = flask.g.db.get_user_by_id(user_id_one)
    user_one = {'user_name': u1[0], 'user_id': u1[1], 'user_commen': u1[2], 'user_is_hidden': u1[3],
                'user_was_banned': u1[4], 'user_participates_since': u1[5], 'user_verified_since': u1[6] } if u1 is not None else None
    u2 = flask.g.db.get_user_by_id(user_id_two)
    user_two = {'user_name': u2[0], 'user_id': u2[1], 'user_commen': u2[2], 'user_is_hidden': u2[3],
                'user_was_banned': u2[4], 'user_participates_since': u2[5], 'user_verified_since': u2[6] } if u2 is not None else None
    cf12 = flask.g.db.get_confirmation(user_id_one, user_id_two)
    cf_one_two = {'cf_timestamp': cf12[0], 'cf_comment': cf12[1]} if cf12 is not None else None
    cf21 = flask.g.db.get_confirmation(user_id_two, user_id_one)
    cf_two_one = {'cf_timestamp': cf21[0], 'cf_comment': cf21[1]} if cf21 is not None else None
    
    return render_template('confirmation.html', user_one=user_one, user_two=user_two,
                           cf_one_two=cf_one_two, cf_two_one=cf_two_one)

@app.route('/recent')
@app.route('/recent/<int:page>')
def recent_confirmations(page=1):
    if page < 1:
        flask.abort(400)

    confirmations = flask.g.db.get_latest_confirmations(page, count=50)
    return render_template('recent_changes.html', confirmations=confirmations, page=page)

@app.route('/user/name/<user_name>')
def user(user_name=None):
    user = flask.g.db.get_user_dict_by_name(user_name)
    if user is None:
        return render_template('user.html', user=None)

    user_blocked_in_dewikip = flask.g.db.user_blocked(user['name'])
    confirmations_given = flask.g.db.get_confirmations_by_user(user['id'], show_hidden_users=False)
    confirmations_received = flask.g.db.get_confirmations_by_confirmed(user['id'], show_hidden_users=False)
    previous_user_name = flask.g.db.get_mw_last_user_name_by_name(user['name'])

    return render_template('user.html',
                           user=user, user_blocked_in_dewikip=user_blocked_in_dewikip,
                           confirmations_given=confirmations_given,
                           confirmations_received=confirmations_received,
                           previous_user_name=previous_user_name)

@app.route('/users')
def users():
    users = flask.g.db.get_all_users(show_hidden_users=False)
    return render_template('users.html', users=users)

@app.route('/sql-dumps')
def sql_dumps():
    files_list = _scan_dir(config.sql_dump_folder)
    return render_template('sql-dumps.html', files_list=files_list)

@app.route('/sql-dump-file/<file_name>')
def sql_dump_file(file_name):
    if not re.fullmatch(re.compile(r"wppb\-20\d\d-\d\d-\d\d\.sql\.bz2"), file_name):
        return flask.abort(400)
    try:
        return send_file(f'{config.sql_dump_folder}/{file_name}', download_name=file_name, as_attachment=True)
    except Exception as e:
        logger.error(e)
        return str(e)

def _scan_dir(root_dir: str):
    result = []
    walk_result = os.walk(root_dir)
    walk_result = sorted(walk_result, reverse=True)
    for root, dirs, files in walk_result:
        sorted_files = sorted(files)
        for file in sorted_files:
            if file.endswith('.sql.bz2') or file.endswith('.sql'):
                file_path = os.path.join(root, file)
                file_size = os.path.getsize(file_path)
                result.append([file, file_size])
    return result

if __name__ == "__main__":
    app.run(debug = True, threaded = True, host='0.0.0.0', port=80, use_reloader=True)