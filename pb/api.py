# -*- coding: utf-8 -*-

"""
This class provides all necessary functionality for accessing WP:PB’s database.
"""

import oursql
import string


class WPPBException(Exception):
    """
    Exception thrown by WP:PB.
    """


class Database(object):
    """
    This class provides access to the database.  It requires three databases on
    the same host:  the project database (*confirmation_db*) with the confirmation
    data, the MediaWiki database (*mediawiki_db*) containing the user data and
    the login database (*login_db*) containig the login data of the tool users.
    """

    def __init__(self, confirmation_db, mediawiki_db, login_db, default_file=None,
                 host=None, user=None, password=None):
        """
        Creates a new database instance using the given confirmation, mediawiki
        and login databases.  The given default file is used to read the connection
        credentials if the host, user and password are not passed to this
        constructor.
        """

        self.confirmation_db = confirmation_db
        self.mediawiki_db = mediawiki_db
        self.login_db = login_db

        try:
            self.conn = oursql.connect(db=confirmation_db, #read_default_file=default_file,
                                       host=host, user=user, passwd=password)
        except oursql.DatabaseError, e:
            raise Exception(u'You specified wrong database connection data: {}'\
                            .format(unicode(e)))

    def close(self):
        self.conn.close()

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
                FROM `''' + self.confirmation_db + '''`.`user`
                LEFT JOIN (
                    SELECT cf_user_id, COUNT(1) as `count`
                        FROM ''' + self.confirmation_db + '''.confirmation
                        LEFT JOIN `user` AS taking ON taking.user_id = cf_confirmed_user_id
                        WHERE (? OR `user_is_hidden` = 0)
                        GROUP BY cf_user_id) as given
                    ON given.cf_user_id = user_id
                LEFT JOIN (
                    SELECT cf_confirmed_user_id, COUNT(1) as `count`
                        FROM ''' + self.confirmation_db + '''.confirmation
                        LEFT JOIN `user` AS giving ON giving.user_id = cf_user_id
                        WHERE (? OR `user_is_hidden` = 0)
                        GROUP BY cf_confirmed_user_id) as taken
                    ON taken.cf_confirmed_user_id = user_id
                WHERE (? OR `user_is_hidden` = 0) AND
                      (? OR `user_was_banned` = 0)
                ORDER BY `user_name`
            ;''', (show_hidden_users, show_hidden_users, show_hidden_users, show_banned_users,))
            return curs.fetchall()

    def get_user_by_id(self, id):
        """
        Returns the user identified by *id*.
        """
        with self.conn as curs:
            curs.execute('''
            SELECT `user_name`, `user_id`, `user_comment`, `user_is_hidden`, `user_was_banned`, `user_participates_since`, `user_verified_since`
                FROM ''' + self.confirmation_db + '''.`user`
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
                FROM ''' + self.confirmation_db + '''.`user`
                WHERE `user_name` = ?
            ;''', (name,))
            return curs.fetchone()

    def get_user_dict_by_name(self, name):
        user = self.get_user_by_name(name)
        return {'name': user[0], 'id': user[1], 'comment': user[2], 'hidden': user[3], 'was_banned': user[4], 'participates_since': user[5], 'verified_since': user[6]}
    
    def get_user_count(self, count_banned_users=False, count_hidden_users=True):
        """
        Returns the count of all users.
        """
        with self.conn as curs:
            curs.execute('''
            SELECT COUNT(`user_id`)
                FROM ''' + self.confirmation_db + '''.`user`
                WHERE (? OR `user_is_hidden` = 0) AND
                      (? OR `user_was_banned` = 0)
            ;''', (count_hidden_users, count_banned_users,))
            return curs.fetchone()[0]

    def get_confirmation_count(self, count_deleted_cf=False, count_hidden_users=True):
        """
        Returns the count of all confirmations.
        """
        with self.conn as curs:
            curs.execute('''
            SELECT COUNT(1)
                FROM ''' + self.confirmation_db + '''.`confirmation`
                LEFT JOIN ''' + self.confirmation_db + '''.`user` AS giving ON giving.user_id = cf_user_id
                LEFT JOIN ''' + self.confirmation_db + '''.`user` AS taking ON taking.user_id = cf_confirmed_user_id
                WHERE (? OR `cf_was_deleted` = 0) AND
                      (? OR giving.`user_is_hidden` = 0) AND
                      (? OR taking.`user_is_hidden` = 0)
            ;''', (count_deleted_cf, count_hidden_users, count_hidden_users,))
            return curs.fetchone()[0]

    def get_cf_count_by_user(self, user_id, count_hidden_users=True):
        """
        Returns the count of confirmations by the user with the id *user_id*.
        """
        with self.conn as curs:
            curs.execute('''
            SELECT COUNT(1)
                FROM ''' + self.confirmation_db + '''.`confirmation`
                LEFT JOIN `user` AS taking ON taking.user_id = cf_confirmed_user_id
                WHERE (`cf_user_id` = ?) AND
                      (? OR taking.`user_is_hidden` = 0)
            ;''', (user_id, count_hidden_users))
            return curs.fetchone()[0]

    def get_cf_count_by_confirmed(self, user_id, count_hidden_users=True):
        """
        Returns the count of confirmations of *user_id*.
        """
        with self.conn as curs:
            curs.execute('''
            SELECT COUNT(1)
                FROM ''' + self.confirmation_db + '''.`confirmation`
                LEFT JOIN `user` AS giving ON giving.user_id = cf_user_id
                WHERE (`cf_confirmed_user_id` = ?) AND
                      (? OR giving.`user_is_hidden` = 0)
            ;''', (user_id, count_hidden_users))
            return curs.fetchone()[0]

    def get_confirmations_by_user(self, user_id, show_hidden_users=True):
        """
        Returns all confirmations done by *user_id*.
        """
        with self.conn as curs:
            curs.execute('''
            SELECT user_name, user_id,
                   cf1.cf_timestamp, cf1.cf_comment, cf1.cf_was_deleted, user_is_hidden,
                   cf2.cf_confirmed_user_id IS NOT NULL
                FROM ''' + self.confirmation_db + '''.confirmation AS cf1
                LEFT JOIN ''' + self.confirmation_db + '''.user
                    ON user_id = cf1.cf_confirmed_user_id
                LEFT JOIN ''' + self.confirmation_db + '''.confirmation as cf2
                    ON cf2.cf_user_id = user_id AND cf2.cf_confirmed_user_id = ?
                WHERE (cf1.cf_user_id = ?) AND
                      (? OR `user_is_hidden` = 0)
                ORDER BY cf1.cf_timestamp ASC
            ;''', (user_id, user_id, show_hidden_users))
            return curs.fetchall()

    def get_confirmations_by_confirmed(self, user_id, show_hidden_users=True):
        """
        Returns all confirmations for *user_id*.
        """
        with self.conn as curs:
            curs.execute('''
            SELECT user_name, user_id,
                   cf1.cf_timestamp, cf1.cf_comment, cf1.cf_was_deleted, user_is_hidden,
                   cf2.cf_user_id IS NOT NULL
                FROM ''' + self.confirmation_db + '''.confirmation AS cf1
                LEFT JOIN ''' + self.confirmation_db + '''.user
                    ON user_id = cf1.cf_user_id
                LEFT JOIN ''' + self.confirmation_db + '''.confirmation as cf2
                    ON cf2.cf_confirmed_user_id = user_id AND cf2.cf_user_id = ?
                WHERE (cf1.cf_confirmed_user_id = ?) AND
                      (? OR `user_is_hidden` = 0)
                ORDER BY cf1.cf_timestamp ASC
            ;''', (user_id, user_id, show_hidden_users))
            return curs.fetchall()

    def get_latest_user_list_with_confirmations(self):
        """
        Returns a list of all users joined this project in the last 3 months.
		Banned and hidden users are NOT shown.
        """
        with self.conn as curs:
            curs.execute('''
            SELECT `user_name`, COUNT(`cf_user_id`), `user_participates_since`
                FROM ''' + self.confirmation_db + '''.`user`
                LEFT JOIN ''' + self.confirmation_db + '''.`confirmation`
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
        Banned and hidden users are NOT shown.
        """
        with self.conn as curs:
            curs.execute('''
               SELECT
                  was_confirmed_t.`user_name` AS was_confirmed_name,
                  has_confirmed_t.`user_name` AS has_confirmed_name,
                  `cf_timestamp`
               FROM ''' + self.confirmation_db + '''.`confirmation`
               JOIN ''' + self.confirmation_db + '''.`user` AS was_confirmed_t
                 ON `cf_confirmed_user_id` = was_confirmed_t.`user_id` AND was_confirmed_t.`user_is_hidden`=0
               JOIN ''' + self.confirmation_db + '''.`user` AS has_confirmed_t
                 ON `cf_user_id` = has_confirmed_t.`user_id` AND has_confirmed_t.`user_is_hidden`=0
               WHERE `cf_timestamp` > DATE_ADD(CURDATE(), INTERVAL -? DAY) AND `cf_timestamp` < DATE_ADD(CURDATE(), INTERVAL -? DAY) AND `cf_was_deleted`=0
               ORDER BY was_confirmed_name
               ;''', (day,day-delta))
            return curs.fetchall()

    def get_latest_confirmations(self, limit=8, days=30):
        """
        Returns a list of all confirmations were made in the last ? months.
		Banned and hidden users are shown.
        """
        with self.conn as curs:
            curs.execute('''
            SELECT
                  has_confirmed_t.`user_name` AS has_confirmed_name,
                  was_confirmed_t.`user_name` AS was_confirmed_name,
                  `cf_comment`,`cf_was_deleted`,`cf_timestamp`
               FROM ''' + self.confirmation_db + '''.`confirmation`
               JOIN ''' + self.confirmation_db + '''.`user` AS was_confirmed_t
                 ON `cf_confirmed_user_id` = was_confirmed_t.`user_id` AND was_confirmed_t.`user_is_hidden`=0
               JOIN ''' + self.confirmation_db + '''.`user` AS has_confirmed_t
                 ON `cf_user_id` = has_confirmed_t.`user_id` AND has_confirmed_t.`user_is_hidden`=0
               WHERE `cf_timestamp` > DATE_ADD(NOW(), INTERVAL -? DAY)
               ORDER BY `cf_timestamp` DESC LIMIT ?
            ;''', (days,limit))
            return curs.fetchall()


    def get_user_list_with_confirmations(self):
        """
        Returns an overview over all users, i.e. user list + number of confirmations this user got.
		Banned and hidden users are NOT shown, but we do not count the deleted confirmations here.
        """
        with self.conn as curs:
            curs.execute('''
            SELECT `user_name`, COUNT(`cf_user_id`), `user_participates_since`
                FROM ''' + self.confirmation_db + '''.`user`
                LEFT JOIN ''' + self.confirmation_db + '''.`confirmation`
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
                FROM ''' + self.confirmation_db + '''.`confirmation`
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
                FROM ''' + self.confirmation_db + '''.`confirmation`
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
                INSERT INTO ''' + self.confirmation_db + '''.`user` (`user_id`, `user_name`)
                    VALUES (?,?)
                ;''', (user_id,user_name))
                # self.touch_user(user_id, timestamp) not neccessary
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
            with self.conn as curs:
                curs.execute('''
                INSERT INTO ''' + self.confirmation_db + '''.`user` (`user_id`, `user_name`, `user_participates_since`, `user_last_update`)
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
            INSERT INTO ''' + self.confirmation_db + '''.`confirmation` (
                `cf_user_id`,
                `cf_confirmed_user_id`,
                `cf_timestamp`,
                `cf_comment`
            )
                VALUES (?,?,?,?)
            ;''', (user_id,confirmed_id,timestamp,comment))
            if (len(self.get_confirmations_by_confirmed(confirmed_id))==3):
                curs.execute('''
                UPDATE ''' + self.confirmation_db + '''.`user` SET
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
        raw_user_name = user_name.encode('utf-8')
        latin_user_name = raw_user_name.decode('latin-1')

        with self.conn as curs:
            curs.execute('''
            SELECT ''' + self.mediawiki_db + '''.`user_id` FROM `user`
                 WHERE `user_name` = ?
            ;''', (latin_user_name,))
            row = curs.fetchone()
            if row != None:
                return int(row[0])
            else:
                return None

    def get_mw_last_user_name_by_name(self, user_name):
        """
        Returs the old MediaWiki user name (after renaming) for the current *user_name*.
        The name is shown only if he/she was renamed after the first participation in PB.
        This should avoid revealing possible old real names.
        """
        with self.conn as curs:
            curs.execute('''
            SELECT ''' + self.mediaiki_db + '''.`log_title` FROM `dewiki_p`.`logging`
            WHERE `log_namespace`=2 AND `log_timestamp` >= (
               SELECT YEAR(`user_participates_since`) * 100 * 100 * 100 * 100 * 100 +
               MONTH(`user_participates_since`) * 100 * 100 * 100 * 100 +
               DAYOFMONTH(`user_participates_since`) * 100 * 100 * 100 +
               HOUR(`user_participates_since`)  * 100 * 100 +
               MINUTE(`user_participates_since`) * 100
               FROM `''' + self.confirmation_db + '''`.`user` WHERE `user_name` = ? LIMIT 1
            ) AND `log_type` = 'renameuser' AND `log_action` = 'renameuser'
            AND SUBSTRING( `log_params` , 1, 260 ) = ?
            ;''', (user_name, user_name,))
            row = curs.fetchone()
            if row != None:
                return str(row[0])
            else:
                return None

    def touch_user(self, user_id, timestamp):
        """
        Updates `user`.`user_last_update` for *user_id*. This is used
        after adding the user, making changes to the user manually or
        when the user gets 'verified'.
        """
        with self.conn as curs:
            curs.execute('''
            UPDATE ''' + self.confirmation_db + '''.`user` SET
                `user_last_update` = ?
            WHERE `user`.`user_id` = ? LIMIT 1
            ;''', (timestamp, user_id,))
            return True

    def user_blocked(self, user_id):
        """
        Checks if a user is blocked and returns the reason and the duration. 
        `None` as return value means that the user is not blocked.
        """
        with self.conn as curs:
            curs.execute('''
            SELECT ''' + self.mediawiki_db + '''.`ipb_reason`, `ipb_expiry`
                FROM `ipblocks`
                WHERE `ipb_user` = ?
                LIMIT 1
            ;''', (user_id,))
            row = curs.fetchone()
            return row

    def get_months(self):
        """
        Returns numbers of months in each year and all months in iso format.
        """
        from datetime import date
        months = {}
        years_months = []
        year = 2008
        month = 2
        while date(year, month, 1) <= date.today():
            if not year in months:
                months[year] = 0
            months[year] += 1
            years_months.append(str(year)+'-'+str(month).zfill(2))
            month = month%12+1
            if month == 1:
                year += 1
        return [months, years_months]

    def get_confirmations_by_month(self):
        """
        Returns the numbers of confirmations by month.
        Confirmations of banned or hidden users are NOT count.
        """
        with self.conn as curs:
            curs.execute('''
            SELECT SUBSTRING(cf_timestamp, 1, 7), 0, COUNT(*)
                FROM ''' + self.confirmation_db + '''.confirmation
                LEFT JOIN ''' + self.confirmation_db + '''.user AS giving ON giving.user_id = cf_user_id
                LEFT JOIN ''' + self.confirmation_db + '''.user AS taking ON taking.user_id = cf_confirmed_user_id
                WHERE (cf_was_deleted = 0) AND
                      (giving.user_is_hidden = 0) AND
                      (taking.user_is_hidden = 0)
                GROUP BY 1
                ORDER BY 1
            ;''')
            return curs.fetchall()

    def get_users_by_month(self):
        """
        Returns the numbers of new users by month.
        Banned and hidden users are NOT count.
        """
        with self.conn as curs:
            curs.execute('''
            SELECT SUBSTRING(user_participates_since, 1, 7), user_verified_since IS NOT NULL, COUNT(*)
                FROM ''' + self.confirmation_db + '''.user
                WHERE (user_is_hidden = 0) AND (user_was_banned = 0)
                GROUP BY 1, 2
                ORDER BY 1, 2
            ;''')
            return curs.fetchall()

    def get_stats(self, year_months, result):
        """
        Calculates counts, sums and totals from a database result set
        """
        counts = {}
        sums = {}
        totals = [0, 0]
        for year_month in year_months:
            counts[year_month] = {}
        for (year_month, group, count) in result:
            counts[year_month][group] = count
            year = int(year_month[:4])
            if not year in sums:
                sums[year] = [0, 0]
            sums[year][group] += count
            totals[group] += count
        return (counts, sums, totals)

    def get_confirmations_per_day(self, confirmations):
        """
        Returns average number of confirmations per day.
        """
        from datetime import date
        return round(float(confirmations)/(date.today()-date(2008, 2, 8)).days, 3)

    def get_login_user(self, openid):
        with self.conn as curs:
            curs.execute('''SELECT user_id FROM ''' + self.login_db + '''.user WHERE user_openid = ?;''', (openid,))
            return curs.fetchone()

    def create_login_user(self, user_id, openid):
        with self.conn as curs:
            curs.execute('''INSERT INTO ''' + self.login_db + '''.user (user_id, user_openid) VALUES (?, ?);''', (user_id, openid))

