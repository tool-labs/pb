# -*- coding: utf-8 -*-

import flask
import jinja2
import locale
import os
import pyintuition
import re

import api


locale.setlocale(locale.LC_ALL, '')

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
app.secret_key = 'secret'


@app.template_filter('format_date')
def format_date(date):
    date_format = locale.nl_langinfo(locale.D_FMT)
    return date.strftime(date_format)

@app.template_filter('format_time')
def format_time(time):
    time_format = locale.nl_langinfo(locale.T_FMT)
    return time.strftime(time_format)

@app.template_filter('format_number')
def format_number(number):
    return locale.format('%d', number, grouping=True)

@app.template_filter('format_datetime')
def format_datetime(dt):
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


@app.context_processor
def template_methods():
    def create_navbar_item(page, title, starts_with=False):
        active_class = u''
        target_url = flask.url_for(page)
        if flask.request.path == target_url or \
                (starts_with and flask.request_path.starts_with(target_url)):
            active_class = u' class="active"'
        return u'<li{}><a href="{}">{}</a></li>'.format(active_class, target_url, title)
    return dict(create_navbar_item=create_navbar_item,
		format_number=format_number,
		len=len,
		round=round,
		int=int)


@app.before_request
def before_request():
    flask.g.db = api.Database(confirmation_db='p50380g50752__pb', mediawiki_db=None, login_db=None,
                              host='dewiki.labsdb', user='p50380g50752', password='ueyoyiebeiviusoh')
    lang = flask.request.cookies.get('TsIntuition_userlang')
    if 'uselang' in flask.request.args:
        lang = flask.request.args['uselang']
    pyintuition.init('pb', app.jinja_env, language=lang)

@app.teardown_request
def teardown_request(request):
    db = getattr(flask.g, 'db', None)
    if db is not None:
        db.close()


@app.route('/')
def index():
    confirmation_count = flask.g.db.get_confirmation_count(False, False)
    confirmations_per_day = flask.g.db.get_confirmations_per_day(confirmation_count)
    user_count = flask.g.db.get_user_count(False, False)
    latest_confirmations = flask.g.db.get_latest_confirmations()

    return render_template('index.html',
                           confirmation_count=confirmation_count,
                           confirmations_per_day=confirmations_per_day,
                           user_count=user_count,
                           latest_confirmations=latest_confirmations)

@app.route('/about/')
def about():
    return render_template('about.html')

@app.route('/confirmations/')
def confirmations():
    return render_template('confirmations.html')

@app.route('/user/name/<user_name>/')
def user(user_name=None):
    user = flask.g.db.get_user_dict_by_name(user_name)

    if user is None:
        flask.abort(404)

    confirmations_given = flask.g.db.get_confirmations_by_user(user['id'])
    confirmations_received = flask.g.db.get_confirmations_by_confirmed(user['id'])

    return render_template('user.html',
                           user=user,
                           confirmations_given=confirmations_given,
                           confirmations_received=confirmations_received)

@app.route('/users/')
def users():
    users = flask.g.db.get_all_users(show_hidden_users=False)
    return render_template('users.html', users=users)

if __name__ == '__main__':
    app.run(debug=True)

