#! /usr/bin/python
# -*- coding: utf-8 -*-
"""
Takes over renames on dewiki into the pb database (user.user_name, matched by user_id).
--dry-run only reports them. Exits with 1 if a name could not be set.
"""
import argparse
import sys
sys.path.append('/data/project/pb/www/python/src')
from api import Database, setup_logger
import logging

logger = logging.getLogger('pb')

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dry-run', action='store_true', help='only report the renames')
    args = parser.parse_args()
    setup_logger()
    db = Database(use_replica=True)
    try:
        results = db.update_user_names(dry_run=args.dry_run)
    finally:
        db.close_connections()
    failed = 0
    # only the user id and the new name: the logs can be read by everyone on Toolforge,
    # and some renames are vanishing requests
    for user_id, old_name, new_name, done in results:
        if done:
            logger.info('user %d renamed to %s', user_id, new_name)
        elif args.dry_run:
            logger.info('user %d would be renamed to %s', user_id, new_name)
        else:
            failed += 1
            logger.error('user %d could not be renamed to %s: name used by another participant', user_id, new_name)
    logger.info('Run completed, %d renames%s', len(results), ' (dry run)' if args.dry_run else '')
    sys.exit(1 if failed else 0)
