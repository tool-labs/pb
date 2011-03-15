# -*- coding: utf-8 -*-

"""
This file is a template for config.py, the file containing the web 
configuration.
"""

import os.path
# path to www index.py
index_path = "http://localhost/~wppb/cgi-bin/trunk/index.py?p=%(page)s&%(args)s"
# path to the www static directory
static_path = "http://localhost/~wppb/trunk/static/"
# path to the local base directory
base_path = os.path.expanduser("~wppb/code/p_wppb/trunk/web/")
# path to the logging directory
log_path = os.path.expanduser("~wppb/log")
# database
db_name = "p_wppb"
