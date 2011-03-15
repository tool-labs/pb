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
                 database='p_wppb', wp_database=None):
        """
        Constructor.

        *wp_database* may be `None`. Otherwise it should be the wiki’s database
        name, e. g. 'dewiki_p'.
        """
        # try to read the .my.cnf
        import ConfigParser
        import os.path

        p = os.path.expanduser('~wppb/.my.cnf')
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
                                u' the database connection. The .my.cnf ' +
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


    def get_all_users(self):
        """
        Returns a list of all users.
        """
        with self.conn as curs:
            curs.execute('''
            SELECT `user_name`, `user_id`, `user_comment` 
                FROM `user` 
                ORDER BY `user_name`
            ;''')
            return curs.fetchall()

    def get_user_by_id(self, id):
        """
        Returns the user identified by *id*.
        """
        with self.conn as curs:
            curs.execute('''
            SELECT `user_name`, `user_id`, `user_comment` 
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
            SELECT `user_name`, `user_id`, `user_comment` 
                FROM `user` 
                WHERE `user_name` = ?
            ;''', (name,))
            return curs.fetchone()

    def get_user_count(self):
        """
        Returns the count of all users.
        """
        with self.conn as curs:
            curs.execute('''
            SELECT COUNT(`user_id`) 
                FROM `user`
            ;''')
            return curs.fetchone()[0]

    def get_confirmation_count(self):
        """
        Returns the count of all confirmations.
        """
        with self.conn as curs:
            curs.execute('''
            SELECT COUNT(1) 
                FROM `confirmation`
            ;''')
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
                   `cf_timestamp`, `cf_comment`
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
                   `cf_timestamp`, `cf_comment`
                FROM `confirmation`
                JOIN `user`
                    ON `user_id` = `cf_user_id`
                WHERE `cf_confirmed_user_id` = ?
                ORDER BY `cf_timestamp` ASC
            ;''', (user_id,))
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
        user_id = get_mw_user_id(user_name)
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
                return True

    def add_confirmation(self, user_id, confirmed_id, comment, timestamp):
        """
        Adds a new confirmation to the database: *user_id* confirmes
        *confirmed_id* with the comment *comment* at *timestamp*.
        Returns the success as a boolean value.

        *timestamp* has to be provided as 'YYYY-MM-DD hh:mm:ss'.
        """
        if (get_user_by_id(user_id) == None or 
            get_user_by_id(confirmed_id) == None):
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
