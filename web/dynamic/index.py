#! /usr/bin/env python
# -*- coding: utf-8 -*-

def serve_page(page_name, arguments):
    # init Jinja2
    from jinja2 import Environment, FileSystemLoader, TemplateNotFound
    env = Environment(loader=FileSystemLoader(pb_db_config.base_path + 'templates',
                                              encoding='utf-8'))
    try:
        template = env.get_template(page_name)
        print template.render(**arguments).encode('utf-8')
    except TemplateNotFound, t:
        template = env.get_template('error.html')
        print template.render(**arguments).encode('utf-8')

def href(page, args):
    return pb_db_config.index_path % {'page': page, 'args': args}

def link(page, args, text):
    return '<a href="%(href)s">%(text)s</a>' % {'href':href(page, args),
                                                'text':text}
def empty(string):
    import re
    ep = re.compile("^\s*$")
    return ep.match(string) != None

def format_date(timestamp):
    return timestamp.strftime("%d.%m.%Y")

def format_time(timestamp):
    return timestamp.strftime("%H:%M")

def format_number(number):
    import locale
    locale.setlocale(locale.LC_ALL, 'de_DE.UTF-8')
    return locale.format("%.d", number, True)


import pb_db_config

import cgi,cgitb
cgitb.enable(display=0, format='plain', logdir=pb_db_config.log_path)

print("Content-type: text/html;charset=utf-8\n")

field = cgi.FieldStorage()

import os.path
import sys
sys.path.append(os.path.abspath(pb_db_config.base_path + '../pyapi'))
import wppb

db = wppb.Database(database=pb_db_config.db_name)

page = 'index'
if 'p' in field:
    page = field['p'].value

args = {'config':pb_db_config, 'link':link, 'db': db, 'href':href, 'str':str,
        'field':field, 'empty':empty, 'format_date':format_date,
        'format_time':format_time, 'format_number':format_number}
serve_page(page + ".html", dict(field, **args))
