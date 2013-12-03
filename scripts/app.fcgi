#! /usr/bin/python

activate_this = '/data/project/pb/pb-2.0-venv/bin/activate_this.py'
execfile(activate_this, dict(__file__=activate_this))

import flup.server.fcgi

import sys
sys.path.append('/data/project/pb/pb-2.0')

import pb.web

import time
import logging
logger = logging.FileHandler('/data/project/pb/pb-2.0-error.log')
pb.web.app.logger.setLevel(logging.DEBUG)
pb.web.app.logger.setHandler(logger)
pb.web.app.logger.debug("Flask server started at: " + time.asctime())

if __name__ == '__main__':
	flup.server.fcgi.WSGIServer(pb.web.app).run()

