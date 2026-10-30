"""
Translations of the web interface.

The language of a page is, in this order of precedence:
  1. the URL parameter ``forcedlang=<code>`` (only for this request, nothing is stored),
  2. the cookie ``pb_lang``, set by a manual choice in the language menu,
  3. the browser's ``Accept-Language`` header,
  4. English.

The messages live in ``translations/<code>.json`` (key -> text). The texts are
trusted HTML with ``{name}`` placeholders; the values filled in are escaped
unless they are already ``Markup``. A key missing in a language falls back to
English.
"""
import json
import os.path

import flask
from markupsafe import Markup

# the most widely spoken languages (total speakers) and those of the sister projects (ca, cs, nl, pl):
# code -> (flag, name in the language itself); Catalan gets the flag of Andorra, where it is the official language
LANGUAGES = {
    'ar': ('🇸🇦', 'العربية'),
    'bn': ('🇧🇩', 'বাংলা'),
    'ca': ('🇦🇩', 'Català'),
    'cs': ('🇨🇿', 'Čeština'),
    'de': ('🇩🇪', 'Deutsch'),
    'en': ('🇬🇧', 'English'),
    'es': ('🇪🇸', 'Español'),
    'fr': ('🇫🇷', 'Français'),
    'hi': ('🇮🇳', 'हिन्दी'),
    'id': ('🇮🇩', 'Bahasa Indonesia'),
    'it': ('🇮🇹', 'Italiano'),
    'ja': ('🇯🇵', '日本語'),
    'ko': ('🇰🇷', '한국어'),
    'mr': ('🇮🇳', 'मराठी'),
    'nl': ('🇳🇱', 'Nederlands'),
    'pl': ('🇵🇱', 'Polski'),
    'pt': ('🇧🇷', 'Português'),
    'ru': ('🇷🇺', 'Русский'),
    'ta': ('🇮🇳', 'தமிழ்'),
    'te': ('🇮🇳', 'తెలుగు'),
    'tr': ('🇹🇷', 'Türkçe'),
    'ur': ('🇵🇰', 'اردو'),
    'vi': ('🇻🇳', 'Tiếng Việt'),
    'zh': ('🇨🇳', '中文'),
}
RTL_LANGUAGES = {'ar', 'ur'}
DEFAULT_LANGUAGE = 'en'
COOKIE_NAME = 'pb_lang'
COOKIE_MAX_AGE = 365 * 24 * 3600
FORCE_PARAM = 'forcedlang'

TRANSLATIONS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'translations')


def _load_catalogs():
    catalogs = {}
    for code in LANGUAGES:
        with open(os.path.join(TRANSLATIONS_DIR, code + '.json'), encoding='utf-8') as f:
            catalogs[code] = json.load(f)
    return catalogs


CATALOGS = _load_catalogs()


def browser_language(request):
    """The supported language the browser prefers most (``de-AT`` counts as ``de``), else English."""
    best = None
    best_quality = 0
    for value, quality in request.accept_languages:
        code = value.split('-')[0].split('_')[0].lower()
        if code in LANGUAGES and quality > best_quality:
            best, best_quality = code, quality
    return best or DEFAULT_LANGUAGE


def chosen_language(request):
    """The language of this request: URL parameter, then cookie, then browser."""
    for value in (request.args.get(FORCE_PARAM), request.cookies.get(COOKIE_NAME)):
        if value in LANGUAGES:
            return value
    return browser_language(request)


def current_language():
    """The language of the current request (English outside of a request)."""
    if not flask.has_request_context():
        return DEFAULT_LANGUAGE
    if 'lang' not in flask.g:
        flask.g.lang = chosen_language(flask.request)
    return flask.g.lang


def gettext(key, **values):
    """The text for *key* in the current language, with the placeholders filled in."""
    lang = current_language()
    text = CATALOGS[lang].get(key)
    if text is None:
        text = CATALOGS[DEFAULT_LANGUAGE].get(key, key)
    return Markup(text).format(**values) if values else Markup(text)


def text_direction(lang):
    return 'rtl' if lang in RTL_LANGUAGES else 'ltr'


def local_url(url):
    """*url* if it is a path on this site, otherwise ``/`` (no open redirects)."""
    if not url or not url.startswith('/') or url.startswith('//') or url.startswith('/\\'):
        return '/'
    return url
