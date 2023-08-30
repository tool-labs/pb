import os.path, os
import sys, re
sys.path.append('/data/project/pb/pb/web/dynamic')
import pb_db_config
import wppb
import flask
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
    flask.g.db = wppb.Database(database=pb_db_config.db_name)

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
    data = flask.g.db.fetch_stats()

    return render_template('index.html',
                           confirmation_count=confirmation_count,
                           confirmations_per_day=confirmations_per_day,
                           user_count=user_count,
                           latest_confirmations=latest_confirmations,
                           data=data)