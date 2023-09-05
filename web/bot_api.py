# -*- coding: utf-8 -*-

"""
This class provides all necessary functionality for accessing WP:PB’s database.
"""

# https://pypi.org/project/PyMySQL/#installation
import pymysql.cursors
from datetime import date
import re, os.path
import config
import configparser
import logging, logging.config
from api import WPPBException, Database
logger = logging.getLogger('pb')

def setup_logger():
	logFormatter = logging.Formatter('%(asctime)s - [%(levelname)-5.5s] - %(message)s')	
	consoleHandler = logging.StreamHandler()
	consoleHandler.setFormatter(logFormatter)
	consoleHandler.setLevel(logging.DEBUG)
	logger.setLevel(logging.DEBUG)
	for h in logging.getLogger().handlers:
		logging.getLogger().removeHandler(h)
	logging.getLogger().addHandler(consoleHandler)
setup_logger()

class BotDatabase(Database):
    """
    This class provides access to the database.
    """

    def __init__(self):
        super().__init__()

    def get_user_list_with_confirmations(self):
        """
        Returns an overview over all users, i.e. user list + number of confirmations this user got.
		Banned and hidden users are NOT shown, but we do not count the deleted confirmations here.
        """
        with self.conn.cursor() as curs:
            curs.execute('''
            SELECT `user_name`, COUNT(`cf_user_id`), `user_participates_since`
                FROM `user`
                LEFT JOIN `confirmation`
                    ON `cf_was_deleted` = 0 AND `user_id` = `cf_confirmed_user_id`
                WHERE `user_is_hidden` = 0 AND `user_was_banned` = 0
                GROUP BY `user_name`
                ORDER BY `user_name` ASC
            ;''')
            return curs.fetchall()

    def add_confirmation(self, user_id, confirmed_id, comment, timestamp):
        """
        Adds a new confirmation to the database: *user_id* confirmes
        *confirmed_id* with the comment *comment* at *timestamp*.
        If *confirmed_id* gets his third confirmation, he/she
        is 'verified' and *user_verified_since* will be set to
        *timestamp*.
        Returns the success as a boolean value.

        *timestamp* has to be provided as 'YYYY-MM-DD hh:mm:ss'.
        """
        if (self.get_user_by_id(user_id) == None or
            self.get_user_by_id(confirmed_id) == None):
            return False
        if re.match("\d\d\d\d-\d\d-\d\d \d\d:\d\d:\d\d", timestamp) == None:
            return False
        with self.conn.cursor() as curs:
            curs.execute('''
            INSERT INTO `confirmation` (
                `cf_user_id`,
                `cf_confirmed_user_id`,
                `cf_timestamp`,
                `cf_comment`
            )
                VALUES (%s,%s,%s,%s)
            ;''', (user_id,confirmed_id,timestamp,comment))
            if (len(self.get_confirmations_by_confirmed(confirmed_id))>=3):
                curs.execute('''
                UPDATE `user` SET
                     `user_verified_since` = %s
                WHERE `user`.`user_id` = %s AND `user_verified_since` IS NULL LIMIT 1
                ;''', (timestamp, confirmed_id,))
                self.touch_user(confirmed_id, timestamp)
            self.conn.commit()
        return True
    
    def add_user(self, user_name, part_tstamp, comment=None):
        """
        Adds a user to the database with given timestamp of participation. Returns the success as a boolean value.
        comment is not used here, but is useful for admin comments like "X is a sock".
        """
        # check if the user exists (MW database)
        user_id = self.get_mw_user_id(user_name)
        import re
        if re.match("\d\d\d\d-\d\d-\d\d \d\d:\d\d:\d\d", part_tstamp) == None:
            return False
        if len(user_name) == 0 or user_id == None:
            # user does not exist
            return False
        else:
            # user does exist
            with self.conn.cursor() as curs:
                curs.execute('''
                INSERT INTO `user` (`user_id`, `user_name`, `user_participates_since`, `user_last_update`)
                    VALUES (%s,%s,%s,%s)
                ;''', (user_id,user_name,part_tstamp,part_tstamp))
                self.conn.commit()
                return True

    def get_cf_count_by_confirmed(self, user_id, count_hidden_users=True):
        """
        Returns the count of confirmations of *user_id*.
        """
        with self.conn.cursor() as curs:
            curs.execute('''
            SELECT COUNT(1)
                FROM `confirmation`
                LEFT JOIN `user` AS giving ON giving.user_id = cf_user_id
                WHERE (`cf_confirmed_user_id` = %s) AND
                      (%s OR giving.`user_is_hidden` = 0)
            ;''', (user_id, count_hidden_users))
            return curs.fetchone()[0]
    
    def has_confirmed(self, user_id, confirmed_id):
        """
        Returns true if *user_id* confirmed *confirmed_id*.
        """
        with self.conn.cursor() as curs:
            curs.execute('''
            SELECT COUNT(1)
                FROM `confirmation`
                WHERE `cf_user_id` = %s
                    AND `cf_confirmed_user_id` = %s
            ;''', (user_id,confirmed_id))
            return bool(curs.fetchone()[0])

    def get_yesterdays_confirmations_sorted_by_confirmed(self, day=1, delta=1):
        """
        Returns a list of all confirmations were made yesterday. This is
        used by the bot for informing the user about the confirmations he got.
        Banned and hidden users are NOT shown.
        """
        with self.conn.cursor() as curs:
            curs.execute('''
               SELECT
                  was_confirmed_t.`user_name` AS was_confirmed_name,
                  has_confirmed_t.`user_name` AS has_confirmed_name,
                  `cf_timestamp`
               FROM `confirmation`
               JOIN `user` AS was_confirmed_t
                 ON `cf_confirmed_user_id` = was_confirmed_t.`user_id` AND was_confirmed_t.`user_is_hidden`=0
               JOIN `user` AS has_confirmed_t
                 ON `cf_user_id` = has_confirmed_t.`user_id` AND has_confirmed_t.`user_is_hidden`=0
               WHERE `cf_timestamp` > DATE_ADD(CURDATE(), INTERVAL - %s DAY) AND `cf_timestamp` < DATE_ADD(CURDATE(), INTERVAL -%s DAY) AND `cf_was_deleted`=0
               ORDER BY was_confirmed_name
               ;''', (day,day-delta))
            return curs.fetchall()

    def get_user_list_with_confirmations(self):
        """
        Returns an overview over all users, i.e. user list + number of confirmations this user got.
		Banned and hidden users are NOT shown, but we do not count the deleted confirmations here.
        """
        with self.conn.cursor() as curs:
            curs.execute('''
            SELECT `user_name`, COUNT(`cf_user_id`), `user_participates_since`
                FROM `user`
                LEFT JOIN `confirmation`
                    ON `cf_was_deleted` = 0 AND `user_id` = `cf_confirmed_user_id`
                WHERE `user_is_hidden` = 0 AND `user_was_banned` = 0
                GROUP BY `user_name`
                ORDER BY `user_name` ASC
            ;''')
            return curs.fetchall()
