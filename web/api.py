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

class WPPBException(BaseException):
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

    def __init__(self):
        pb_database=config.db_name
        wp_replica_db='dewiki_p'
        # try to read the replica.pb-db.cnf
        p = config.db_conf_file
        if os.path.exists(p):
            parser = configparser.ConfigParser()
            parser.readfp(open(p))
            if parser.has_section('client'):
                if parser.has_option('client', 'user'):
                    user_name = parser.get('client', 'user').strip('"\'')
                if parser.has_option('client', 'password'):
                    password = parser.get('client', 'password').strip('"\'')
                if parser.has_option('client', 'host'):
                    wp_host = parser.get('client', 'host').strip('"\'')

        if user_name is None or password is None or wp_host is None:
            raise WPPBException('You did not specify enough information on' +
                                ' the database connection. The ~/replica.pb-db.cnf ' +
                                'file did not contain the required ' +
                                'information.')

        try:
            # Workaround for the outage of c2.labsdb:  the project database is
            # moved to tools-db.  ireas/2016-02-16
            self.conn = pymysql.connections.Connection(host='tools.db.svc.wikimedia.cloud', user=user_name, password=password, db=pb_database,
                           charset='utf8', use_unicode=True, defer_connect=True)
            self.wp_conn = pymysql.connections.Connection(host=wp_host, user=user_name, password=password, db=wp_replica_db,
                           charset='utf8', use_unicode=True, defer_connect=True)
            self.conn.ping()  # reconnecting mysql, https://stackoverflow.com/a/61152360
            self.wp_conn.ping()  # reconnecting mysql
        except pymysql.DatabaseError as e:
            raise WPPBException('You specified a wrong database connection ' +
                                'data. Error message: ' + str(e))


    def get_all_users(self, show_hidden_users=True, show_banned_users=False):
        """
        Returns a list of all users.
        """
        with self.conn.cursor() as curs:
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
                        WHERE (%s OR `user_is_hidden` = 0)
                        GROUP BY cf_user_id) as given
                    ON given.cf_user_id = user_id
                LEFT JOIN (
                    SELECT cf_confirmed_user_id, COUNT(1) as `count`
                        FROM confirmation
                        LEFT JOIN `user` AS giving ON giving.user_id = cf_user_id
                        WHERE (%s OR `user_is_hidden` = 0)
                        GROUP BY cf_confirmed_user_id) as taken
                    ON taken.cf_confirmed_user_id = user_id
                WHERE (%s OR `user_is_hidden` = 0) AND
                      (%s OR `user_was_banned` = 0)
                ORDER BY `user_name`
            ;''', (show_hidden_users, show_hidden_users, show_hidden_users, show_banned_users,))
            return curs.fetchall()

    def get_user_by_id(self, id):
        """
        Returns the user identified by *id*.
        """
        with self.conn.cursor() as curs:
            curs.execute('''
            SELECT `user_name`, `user_id`, `user_comment`, `user_is_hidden`, `user_was_banned`, `user_participates_since`, `user_verified_since`
                FROM `user`
                WHERE `user_id` = %s
            ;''', (id,))
            return curs.fetchone()

    def get_user_dict_by_name(self, name):
        user = self.get_user_by_name(name)
        if user is None: return None
        return {'name': user[0], 'id': user[1], 'comment': user[2], 'hidden': user[3], 'was_banned': user[4], 'participates_since': user[5], 'verified_since': user[6]}
    
    def get_user_by_name(self, name):
        """
        Returns the user by *name*.
        """
        with self.conn.cursor() as curs:
            curs.execute('''
            SELECT `user_name`, `user_id`, `user_comment`, `user_is_hidden`, `user_was_banned`, `user_participates_since`, `user_verified_since`
                FROM `user`
                WHERE `user_name` = %s
            ;''', (name,))
            return curs.fetchone()

    def get_user_count(self, count_banned_users=False, count_hidden_users=True):
        """
        Returns the count of all users.
        """
        with self.conn.cursor() as curs:
            curs.execute('''
            SELECT COUNT(`user_id`)
                FROM `user`
                WHERE (%s OR `user_is_hidden` = 0) AND
                      (%s OR `user_was_banned` = 0)
            ;''', (count_hidden_users, count_banned_users,))
            return curs.fetchone()[0]

    def get_confirmation_count(self, count_deleted_cf=False, count_hidden_users=True):
        """
        Returns the count of all confirmations.
        """
        with self.conn.cursor() as curs:
            curs.execute('''
            SELECT COUNT(1)
                FROM `confirmation`
                LEFT JOIN `user` AS giving ON giving.user_id = cf_user_id
                LEFT JOIN `user` AS taking ON taking.user_id = cf_confirmed_user_id
                WHERE (%s OR `cf_was_deleted` = 0) AND
                      (%s OR giving.`user_is_hidden` = 0) AND
                      (%s OR taking.`user_is_hidden` = 0)
            ;''', (count_deleted_cf, count_hidden_users, count_hidden_users,))
            return curs.fetchone()[0]

    # REMOVE?
    def get_cf_count_by_user(self, user_id, count_hidden_users=True):
        """
        Returns the count of confirmations by the user with the id *user_id*.
        """
        with self.conn.cursor() as curs:
            curs.execute('''
            SELECT COUNT(1)
                FROM `confirmation`
                LEFT JOIN `user` AS taking ON taking.user_id = cf_confirmed_user_id
                WHERE (`cf_user_id` = %s) AND
                      (%s OR taking.`user_is_hidden` = 0)
            ;''', (user_id, count_hidden_users))
            return curs.fetchone()[0]

    def get_confirmations_by_user(self, user_id, show_hidden_users=True):
        """
        Returns all confirmations done by *user_id*.
        """
        with self.conn.cursor() as curs:
            curs.execute('''
            SELECT user_name, user_id,
                   cf1.cf_timestamp, cf1.cf_comment, cf1.cf_was_deleted, user_is_hidden,
                   cf2.cf_confirmed_user_id IS NOT NULL
                FROM confirmation AS cf1
                LEFT JOIN user
                    ON user_id = cf1.cf_confirmed_user_id
                LEFT JOIN confirmation as cf2
                    ON cf2.cf_user_id = user_id AND cf2.cf_confirmed_user_id = %s
                WHERE (cf1.cf_user_id = %s) AND
                      (%s OR `user_is_hidden` = 0)
                ORDER BY cf1.cf_timestamp DESC
            ;''', (user_id, user_id, show_hidden_users))
            return curs.fetchall()

    def get_confirmations_by_confirmed(self, user_id, show_hidden_users=True):
        """
        Returns all confirmations for *user_id*.
        """
        with self.conn.cursor() as curs:
            curs.execute('''
            SELECT user_name, user_id,
                   cf1.cf_timestamp, cf1.cf_comment, cf1.cf_was_deleted, user_is_hidden,
                   cf2.cf_user_id IS NOT NULL
                FROM confirmation AS cf1
                LEFT JOIN user
                    ON user_id = cf1.cf_user_id
                LEFT JOIN confirmation as cf2
                    ON cf2.cf_confirmed_user_id = user_id AND cf2.cf_user_id = %s
                WHERE (cf1.cf_confirmed_user_id = %s) AND
                      (%s OR `user_is_hidden` = 0)
                ORDER BY cf1.cf_timestamp DESC
            ;''', (user_id, user_id, show_hidden_users))
            return curs.fetchall()

    def get_latest_user_list_with_confirmations(self):
        """
        Returns a list of all users joined this project in the last 3 months.
		Banned and hidden users are NOT shown.
        """
        with self.conn.cursor() as curs:
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

    def get_latest_confirmations(self, page=1, count=50):
        """
            Returns a paginated list of all confirmations with `count` entries.
        """
        with self.conn.cursor() as curs:
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
                WHERE cf_was_deleted = 0
                ORDER BY cf_timestamp DESC
                LIMIT %s OFFSET %s
            ''', (count, (page - 1)*count))
            return curs.fetchall()

    def get_confirmation(self, user_id, confirmed_id):
        """
        Returns the confirmation of *confirmed_id* by *user_id*.
        """
        with self.conn.cursor() as curs:
            curs.execute('''
            SELECT `cf_timestamp`, `cf_comment`
                FROM `confirmation`
                WHERE `cf_user_id` = %s
                    AND `cf_confirmed_user_id` = %s
            ;''', (user_id,confirmed_id))
            return curs.fetchone()

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

        with self.wp_conn.cursor() as curs:
            curs.execute('''
            SELECT `user_id` FROM `user`
                 WHERE `user_name` = %s
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
        with self.wp_conn.cursor() as curs:
            curs.execute('''
            SELECT `log_title` FROM `dewiki_p`.`logging`
            WHERE `log_namespace`=2 AND `log_timestamp` >= %s
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
        with self.conn.cursor() as curs:
            curs.execute('''
            UPDATE `user` SET
                `user_last_update` = %s
            WHERE `user`.`user_id` = %s LIMIT 1
            ;''', (timestamp, user_id,))
            self.conn.commit()
            return True

    def user_blocked(self, user_id):
        """
        Checks if a user is blocked and returns the reason and the duration.
        `None` as return value means that the user is not blocked.
        """
        with self.wp_conn.cursor() as curs:
            curs.execute('''SELECT 1 FROM block_target JOIN user ON user_id = bt_user
                WHERE user_name = %s LIMIT 1;''', (user_id,))
            row = curs.fetchone()
            return row

    def _generate_months_for_stats(self):
        """
            Returns number of months of each year and all months in iso format.
        """
        months = {}
        years_months = []
        year = 2008
        month = 2
        while date(year, month, 1) <= date.today():
            if not year in months:
                months[year] = 0
            months[year] += 1
            years_months.append(str(year) + '-' + str(month).zfill(2))
            month = month % 12 + 1
            if month == 1:
                year += 1
        return [months, years_months]

    def _get_stats_confirmations_by_month(self):
        """
        Returns the numbers of confirmations by month.
        Confirmations of banned or hidden users are NOT counted.
        """
        with self.conn.cursor() as curs:
            curs.execute('SELECT `year_month`, `group`, `count` FROM `stats_confirmations_by_month` ORDER BY 1;')
            return curs.fetchall()

    def _get_users_by_month(self):
        """
        Returns the numbers of new users by month.
        Banned and hidden users are NOT counted.
        """
        with self.conn.cursor() as curs:
            curs.execute('''
            SELECT SUBSTRING(`user_participates_since`, 1, 7), `user_verified_since` IS NOT NULL, COUNT(*)
                FROM `user`
                WHERE (user_is_hidden = 0) AND (user_was_banned = 0)
                GROUP BY 1, 2
                ORDER BY 1, 2
            ;''')
            return curs.fetchall()

    def _prepare_stats(self, year_months, data_rows):
        """
            Calculates counts, sums and totals from a database result set. Example:
            {   'months': {2016: 12, 2017: 12, ..., 2015: 12},
                'year_months': ['2008-02', '2008-03', ... '2023-08'],
                'users': {
                    'counts': {'2019-09': {0: 8}, '2014-09': {0: 3, 1: 11}, '2014-08': {0: 7, 1: 21}, ... },
                    'sums': {2016: [68, 111], 2017: [73, 84], ... },
                    'totals': [727, 1851]
                },
                'confirmations': { 'counts': /like above/ 'totals': [87905, 0]}
            }
        """
        counts = {}
        sums = {}
        totals = [0, 0]
        for year_month in year_months:
            counts[year_month] = {}
        for year_month, group, count in data_rows:
            counts[year_month][group] = count
            year = int(year_month[:4])
            if year not in sums:
                sums[year] = [0, 0]
            sums[year][group] += count
            totals[group] += count
        return counts, sums, totals

    def get_confirmations_per_day(self, confirmations):
        """
        Returns average number of confirmations per day.
        """
        return round(float(confirmations)/(date.today()-date(2008, 2, 8)).days, 3)

    def fetch_stats(self):
        """
            Fetches the full data set needed for the statistics on the main page.
        """
        months, year_months = self._generate_months_for_stats()
        counts_cf, sums_cf, totals_cf = self._prepare_stats(year_months, self._get_stats_confirmations_by_month())
        counts_u, sums_u, totals_u = self._prepare_stats(year_months, self._get_users_by_month())

        chart_data = { 'months': months, 'year_months': year_months,
            'confirmations': { 'counts': counts_cf, 'sums': sums_cf, 'totals': totals_cf },
            'users': { 'counts': counts_u, 'sums': sums_u, 'totals': totals_u }
        }
        return chart_data

    def update_stats_confirmations_by_month(self):
        """
            Runs database queries that fill the table 'stats_confirmations_by_month' with pregenerated data.
        """
        try:
            with self.conn.cursor() as curs:
                curs.execute('TRUNCATE `stats_confirmations_by_month`;')
                curs.execute('''
                INSERT INTO `stats_confirmations_by_month` (`year_month`, `group`, `count`)
                SELECT SUBSTRING(cf_timestamp, 1, 7), 0, COUNT(*)
                FROM confirmation
                JOIN user AS giving ON giving.user_id = cf_user_id
                JOIN user AS taking ON taking.user_id = cf_confirmed_user_id
                WHERE (cf_was_deleted = 0) AND
                        (giving.user_is_hidden = 0) AND
                        (taking.user_is_hidden = 0)
                GROUP BY 1
                ORDER BY 1;''')
        except:
            logger.error('Rolling back the queries!')
            self.conn.rollback()
            raise
        else:
            self.conn.commit()
        finally:
            curs.close()
            self.conn.close()

    def close_connections(self):
        """
            This method is used to explictly close a connection. Used by the bot!
        """
        self.conn.close()
        self.wp_conn.close()