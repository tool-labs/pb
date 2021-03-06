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
        # try to read the replica.pb-db.cnf
        import ConfigParser
        import os.path
        import pb_db_config

        p = pb_db_config.db_conf_file
        if os.path.exists(p):
            parser = ConfigParser.ConfigParser()
            parser.readfp(open(p))
            if parser.has_section('client'):
                if parser.has_option('client', 'user') and user_name is None:
                    user_name = string.strip(parser.get('client', 'user'),
				             '"\'')
                if (parser.has_option('client', 'password')
                    and password is None):
                    password = string.strip(parser.get('client', 'password'),
                                            '"\'')
                if parser.has_option('client', 'host') and host is None:
                    host = string.strip(parser.get('client', 'host'), '"\'')


        if user_name is None or password is None or host is None:
            raise WPPBException(u'You did not specify enough information on' +
                                u' the database connection. The ~/replica.pb-db.cnf ' +
                                u'file did not contain the required ' +
                                u'information.')

        try:
            # Workaround for the outage of c2.labsdb:  the project database is
            # moved to tools-db.  ireas/2016-02-16
            self.conn = oursql.connect(host='tools-db', user=user_name,
                                       passwd=password, db=database)
            self.pb_database_name = database

            self.wp_conn = None
            if wp_database != None:
                self.wp_conn = oursql.connect(host=host,user=user_name,
                           passwd=password,db=wp_database, charset='utf8', use_unicode=True)
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
                FROM `user`
                LEFT JOIN (
                    SELECT cf_user_id, COUNT(1) as `count`
                        FROM confirmation
                        LEFT JOIN `user` AS taking ON taking.user_id = cf_confirmed_user_id
                        WHERE (? OR `user_is_hidden` = 0)
                        GROUP BY cf_user_id) as given
                    ON given.cf_user_id = user_id
                LEFT JOIN (
                    SELECT cf_confirmed_user_id, COUNT(1) as `count`
                        FROM confirmation
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

    def get_user_count(self, count_banned_users=False, count_hidden_users=True):
        """
        Returns the count of all users.
        """
        with self.conn as curs:
            curs.execute('''
            SELECT COUNT(`user_id`)
                FROM `user`
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
                FROM `confirmation`
                LEFT JOIN `user` AS giving ON giving.user_id = cf_user_id
                LEFT JOIN `user` AS taking ON taking.user_id = cf_confirmed_user_id
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
                FROM `confirmation`
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
                FROM `confirmation`
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
                FROM confirmation AS cf1
                LEFT JOIN user
                    ON user_id = cf1.cf_confirmed_user_id
                LEFT JOIN confirmation as cf2
                    ON cf2.cf_user_id = user_id AND cf2.cf_confirmed_user_id = ?
                WHERE (cf1.cf_user_id = ?) AND
                      (? OR `user_is_hidden` = 0)
                ORDER BY cf1.cf_timestamp DESC
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
                FROM confirmation AS cf1
                LEFT JOIN user
                    ON user_id = cf1.cf_user_id
                LEFT JOIN confirmation as cf2
                    ON cf2.cf_confirmed_user_id = user_id AND cf2.cf_user_id = ?
                WHERE (cf1.cf_confirmed_user_id = ?) AND
                      (? OR `user_is_hidden` = 0)
                ORDER BY cf1.cf_timestamp DESC
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
                FROM `user`
                LEFT JOIN `confirmation`
                    ON `cf_was_deleted` = 0 AND `user_id` = `cf_confirmed_user_id`
                WHERE `user_is_hidden` = 0 AND `user_was_banned` = 0 AND `user_participates_since` > DATE_ADD(NOW(), INTERVAL -3 MONTH)
                GROUP BY `user_name`
                ORDER BY `user_participates_since` ASC, `user_name`
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
        Returns a list of all confirmations were made in the last ? months.
		Banned and hidden users are shown.
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
        Returns an overview over all users, i.e. user list + number of confirmations this user got.
		Banned and hidden users are NOT shown, but we do not count the deleted confirmations here.
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
            if (len(self.get_confirmations_by_confirmed(confirmed_id))>=3):
                curs.execute('''
                UPDATE `user` SET
                     `user_verified_since` = ?
                WHERE `user`.`user_id` = ? AND `user_verified_since` IS NULL LIMIT 1
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
        # due to some trubble with UTF-8, just commented out
        #raw_user_name = user_name.encode('utf-8')
        #latin_user_name = raw_user_name.decode('latin-1')

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

    def get_mw_last_user_name_by_name(self, user_name):
        """
        Returs the old MediaWiki user name (after renaming) for the current *user_name*.
        The name is shown only if he/she was renamed after the first participation in PB.
        This should avoid revealing possible old real names.
        """
        # FIXME(incident-c2)
        # euku[2017-09-09]: too slow => disabled
        return None

        user_participates_since = self.get_user_by_name(user_name)[5]
        user_participates_since = user_participates_since.strftime("%Y%m%d%H%M%S")
        if self.wp_conn == None:
            return False
        with self.wp_conn as curs:
            curs.execute('''
            SELECT `log_title` FROM `dewiki_p`.`logging`
            WHERE `log_namespace`=2 AND `log_timestamp` >= ?
            AND `log_type` = 'renameuser' AND `log_action` = 'renameuser'
            AND `log_params` LIKE '%::newuser";s:3:"''' + user_name + '''";%'
            ;''', (user_participates_since,))
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
                FROM confirmation
                LEFT JOIN user AS giving ON giving.user_id = cf_user_id
                LEFT JOIN user AS taking ON taking.user_id = cf_confirmed_user_id
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
                FROM user
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

    def unpickle_stats(self):
        import pickle
        return pickle.load(open('/data/project/pb/stats.pickle', 'r'))

