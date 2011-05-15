# -*- coding: utf-8 -*-

"""
This class provides all necessary functionality for accessing WP:PB’s database.
"""

import oursql
import string

class WPPBException:
    """
    Exception thrown by WP:PB.
    """

    def __init__(self, msg):
        """
        Constructor.
        """
        self.msg = msg

    def __str__(self):
        """
        Returns a string representation of this exception.
        """
        return repr(self.msg)

class Database:
    """
    This class provides access to the database.
    """

    def __init__(self, user_name=None, password=None, host=None,
                 database='p_wppb', wp_database='dewiki_p'):
        """
        Constructor.

        *wp_database* may be `None`. Otherwise it should be the wiki’s database
        name, e. g. 'dewiki_p'.
        """
        # try to read the .my.cnf
        import ConfigParser
        import os.path
        import pb_db_config

        p = pb_db_config.db_conf_file
        if os.path.exists(p):
            parser = ConfigParser.ConfigParser()
            parser.read(p)
            if parser.has_section('client'):
                if parser.has_option('client', 'user') and user_name is None:
                    user_name = parser.get('client', 'user')
                if (parser.has_option('client', 'password')
                    and password is None):
                    password = string.strip(parser.get('client', 'password'),
                                            '"')
                if parser.has_option('client', 'host') and host is None:
                    host = string.strip(parser.get('client', 'host'), '"')


        if user_name is None or password is None or host is None:
            raise WPPBException(u'You did not specify enough information on' +
                                u' the database connection. The .my-pb-db-****.cnf ' +
                                u'file did not contain the required ' +
                                u'information.')

        try:
            self.conn = oursql.connect(host=host, user=user_name,
                                       passwd=password, db=database)
            self.wp_conn = None
            if wp_database != None:
                self.wp_conn = oursql.connect(host=host,user=user_name,
                                              passwd=password,db=wp_database)
        except oursql.DatabaseError, e:
            raise WPPBException(u'You specified wrong database connection ' +
                                u'data. Error message: ' + unicode(e))


    def get_all_users(self, show_hidden_users=True, show_banned_users=False):
        """
        Returns a list of all users.
        """
        with self.conn as curs:
            curs.execute('''
            SELECT `user_name`, `user_id`, `user_comment`,
                    `user_is_hidden`, `user_was_banned`,
                    `user_participates_since`, `user_verified_since`,
                    given.count as given_count, taken.count as taken_count
                FROM `user`, (
                    SELECT cf_user_id, COUNT(1) as `count`
                        FROM confirmation
                        GROUP BY cf_user_id) as given, (
                    SELECT cf_confirmed_user_id, COUNT(1) as `count`
                        FROM confirmation
                        GROUP BY cf_confirmed_user_id) as taken
                WHERE (? OR `user_is_hidden` = 0) AND
                      (? OR `user_was_banned` = 0) AND
                      given.cf_user_id = user_id AND
                      taken.cf_confirmed_user_id = user_id
                ORDER BY `user_name`
            ;''', (show_hidden_users, show_banned_users,))
            return curs.fetchall()

    def get_user_by_id(self, id):
        """
        Returns the user identified by *id*.
        """
        with self.conn as curs:
            curs.execute('''
            SELECT `user_name`, `user_id`, `user_comment`, `user_is_hidden`, `user_was_banned`, `user_participates_since`, `user_verified_since`
                FROM `user`
                WHERE `user_id` = ?
            ;''', (id,))
            return curs.fetchone()

    def get_user_by_name(self, name):
        """
        Returns the user *name*.
        """
        with self.conn as curs:
            curs.execute('''
            SELECT `user_name`, `user_id`, `user_comment`, `user_is_hidden`, `user_was_banned`, `user_participates_since`, `user_verified_since`
                FROM `user`
                WHERE `user_name` = ?
            ;''', (name,))
            return curs.fetchone()

    def get_user_count(self, count_banned_users=False):
        """
        Returns the count of all users.
        """
        with self.conn as curs:
            curs.execute('''
            SELECT COUNT(`user_id`)
                FROM `user`
                WHERE ? OR `user_was_banned` = 0
            ;''', (count_banned_users,))
            return curs.fetchone()[0]

    def get_confirmation_count(self, count_deleted_cf=False):
        """
        Returns the count of all confirmations.
        """
        with self.conn as curs:
            curs.execute('''
            SELECT COUNT(1)
                FROM `confirmation`
                WHERE ? OR `cf_was_deleted` = 0
            ;''', (count_deleted_cf,))
            return curs.fetchone()[0]

    def get_cf_count_by_user(self, user_id):
        """
        Returns the count of confirmations by the user with the id *user_id*.
        """
        with self.conn as curs:
            curs.execute('''
            SELECT COUNT(1)
                FROM `confirmation`
                WHERE `cf_user_id` = ?
            ;''', (user_id,))
            return curs.fetchone()[0]

    def get_cf_count_by_confirmed(self, user_id):
        """
        Returns the count of confirmations of *user_id*.
        """
        with self.conn as curs:
            curs.execute('''
            SELECT COUNT(1)
                FROM `confirmation`
                WHERE `cf_confirmed_user_id` = ?
            ;''', (user_id,))
            return curs.fetchone()[0]

    def get_confirmations_by_user(self, user_id):
        """
        Returns all confirmations done by *user_id*.
        """
        with self.conn as curs:
            curs.execute('''
            SELECT `user_name`, `cf_confirmed_user_id`,
                   `cf_timestamp`, `cf_comment`, `cf_was_deleted`, `user_is_hidden`
                FROM `confirmation`
                JOIN `user`
                    ON `user_id` = `cf_confirmed_user_id`
                WHERE `cf_user_id` = ?
                ORDER BY `cf_timestamp` ASC
            ;''', (user_id,))
            return curs.fetchall()

    def get_confirmations_by_confirmed(self, user_id):
        """
        Returns all confirmations for *user_id*.
        """
        with self.conn as curs:
            curs.execute('''
            SELECT `user_name`, `cf_user_id`,
                   `cf_timestamp`, `cf_comment`, `cf_was_deleted`, `user_is_hidden`
                FROM `confirmation`
                JOIN `user`
                    ON `user_id` = `cf_user_id`
                WHERE `cf_confirmed_user_id` = ?
                ORDER BY `cf_timestamp` ASC
            ;''', (user_id,))
            return curs.fetchall()

    def get_latest_user_list_with_confirmations(self):
        """
        Returns a list of all users joined this project in the last 3 months
		banned and hidden users are NOT shown
        """
        with self.conn as curs:
            curs.execute('''
            SELECT `user_name`, COUNT(`cf_user_id`), `user_participates_since`
                FROM `user`
                LEFT JOIN `confirmation`
                    ON `cf_was_deleted` = 0 AND `user_id` = `cf_confirmed_user_id`
               WHERE `user_is_hidden` = 0 AND `user_was_banned` = 0 AND `user_participates_since` > DATE_ADD(NOW(), INTERVAL -3 MONTH)
                GROUP BY `user_name`
                ORDER BY `user_participates_since` ASC
            ;''')
            return curs.fetchall()

    def get_yesterdays_confirmations_sorted_by_confirmed(self, day=1, delta=1):
        """
        Returns a list of all confirmations were made yesterday. This is
             used by the bot for informing the user about the confirmations he got.
             banned and hidden users are NOT shown
        """
        with self.conn as curs:
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
               WHERE `cf_timestamp` > DATE_ADD(CURDATE(), INTERVAL -? DAY) AND `cf_timestamp` < DATE_ADD(CURDATE(), INTERVAL -? DAY) AND `cf_was_deleted`=0
               ORDER BY was_confirmed_name
               ;''', (day,day-delta))
            return curs.fetchall()

    def get_latest_confirmations(self, limit=8, days=30):
        """
        Returns a list of all confirmations were made in the last ? months
		banned and hidden users are shown
        """
        with self.conn as curs:
            curs.execute('''
            SELECT
                  has_confirmed_t.`user_name` AS has_confirmed_name,
                  was_confirmed_t.`user_name` AS was_confirmed_name,
                  `cf_comment`,`cf_was_deleted`,`cf_timestamp`
               FROM `confirmation`
               JOIN `user` AS was_confirmed_t
                 ON `cf_confirmed_user_id` = was_confirmed_t.`user_id` AND was_confirmed_t.`user_is_hidden`=0
               JOIN `user` AS has_confirmed_t
                 ON `cf_user_id` = has_confirmed_t.`user_id` AND has_confirmed_t.`user_is_hidden`=0
               WHERE `cf_timestamp` > DATE_ADD(NOW(), INTERVAL -? DAY)
               ORDER BY `cf_timestamp` DESC LIMIT ?
            ;''', (days,limit))
            return curs.fetchall()


    def get_user_list_with_confirmations(self):
        """
        Returns an overview over all users, i.e. user list + number of confirmations this user got
		banned and hidden users are NOT shown, but we do not count the deleted confirmations here
        """
        with self.conn as curs:
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

    def has_confirmed(self, user_id, confirmed_id):
        """
        Returns true if *user_id* confirmed *confirmed_id*.
        """
        with self.conn as curs:
            curs.execute('''
            SELECT COUNT(1)
                FROM `confirmation`
                WHERE `cf_user_id` = ?
                    AND `cf_confirmed_user_id` = ?
            ;''', (user_id,confirmed_id))
            return bool(curs.fetchone()[0])

    def get_confirmation(self, user_id, confirmed_id):
        """
        Returns the confirmation of *confirmed_id* by *user_id*.
        """
        with self.conn as curs:
            curs.execute('''
            SELECT `cf_timestamp`, `cf_comment`
                FROM `confirmation`
                WHERE `cf_user_id` = ?
                    AND `cf_confirmed_user_id` = ?
            ;''', (user_id,confirmed_id))
            return curs.fetchone()

    def add_user(self, user_name):
        """
        Adds a user to the database. Returns the success as a boolean value.
        """
        # check if the user exists (MW database)
        user_id = self.get_mw_user_id(user_name)
        if len(user_name) == 0 or user_id == None:
            # user does not exist
            return False
        else:
            # user does exist
            with self.conn as curs:
                curs.execute('''
                INSERT INTO `user` (`user_id`, `user_name`)
                    VALUES (?,?)
                ;''', (user_id,user_name))
                # self.touch_user(user_id, timestamp) not neccessary
                return True

    def add_user(self, user_name, part_tstamp, comment=None):
        """
        Adds a user to the database with given timestamp of participation. Returns the success as a boolean value.
         comment is not used here, but is useful for admin comments like "X is a sock"
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
            with self.conn as curs:
                curs.execute('''
                INSERT INTO `user` (`user_id`, `user_name`, `user_participates_since`, `user_last_update`)
                    VALUES (?,?,?,?)
                ;''', (user_id,user_name,part_tstamp,part_tstamp))
                # self.touch_user(user_id, timestamp) not neccessary
                return True

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
        import re
        if re.match("\d\d\d\d-\d\d-\d\d \d\d:\d\d:\d\d", timestamp) == None:
            return False
        with self.conn as curs:
            curs.execute('''
            INSERT INTO `confirmation` (
                `cf_user_id`,
                `cf_confirmed_user_id`,
                `cf_timestamp`,
                `cf_comment`
            )
                VALUES (?,?,?,?)
            ;''', (user_id,confirmed_id,timestamp,comment))
            if (len(self.get_confirmations_by_confirmed(confirmed_id))==3):
                curs.execute('''
                UPDATE `user` SET
                     `user_verified_since` = ?
                WHERE `user`.`user_id` = ? LIMIT 1
                ;''', (timestamp, confirmed_id,))
                self.touch_user(confirmed_id, timestamp)
                return True

    def get_mw_user_id(self, user_name):
        """
        Returns the MediaWiki user id for the user *user_name* or `None` if
        the user does not exist.
        """
        if self.wp_conn == None:
            return False

        with self.wp_conn as curs:
            curs.execute('''
            SELECT `user_id` FROM `user`
                WHERE `user_name` = ?
            ;''', (user_name,))
            row = curs.fetchone()
            if row != None:
                return int(row[0])
            else:
                return None

    def touch_user(self, user_id, timestamp):
        """
        Updates `user`.`user_last_update` for *user_id*. This is used
        after adding the user, makeing changes to the user manually or
        when the user gets 'verified'.
        """
        with self.wp_conn as curs:
            curs.execute('''
            UPDATE `user` SET
                `user_last_update` = ?
            WHERE `user`.`user_id` = ? LIMIT 1
            ;''', (timestamp, user_id,))
            return True

    def user_blocked(self, user_id):
        """
        Checks if a user is blocked and returns the reason and the duration. 
        `None` as return value means that the user is not blocked.
        """
        
        with self.wp_conn as curs:
            curs.execute('''
            SELECT `ipb_reason`, `ipb_expiry`
                FROM `ipblocks`
                WHERE `ipb_user` = ?
                LIMIT 1
            ;''', (user_id,))
            row = curs.fetchone()
            return row

