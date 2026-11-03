# -*- coding: utf-8 -*-
"""
Database access for the admin area (web/admin.py).

Every change is written together with its `audit_trail` entry in one transaction
(see sql/schema.md). The dewiki replica and the Meta replica are only connected
when a page needs them.
"""
import datetime
import json
import re

import pymysql

import config
from api import Database, WPPBException, read_db_credentials, _text

# columns an admin may change, in the order they are checked
USER_FIELDS = ('user_is_hidden', 'user_was_banned', 'user_comment')
CONFIRMATION_FIELDS = ('cf_was_deleted', 'cf_comment')
FLAG_FIELDS = ('user_is_hidden', 'user_was_banned', 'cf_was_deleted')

# names that global renames on request ("vanishing") give to an account
VANISHED_RE = re.compile(r'^(?:Vanished user |Renamed user |GelöschterBenutzer|Gelöschter Benutzer|User \d{8}-\d+$)')
VANISHED_REASON = 'Konto auf eigenen Wunsch verschwunden (Globale Umbenennung auf Meta am {day}: {comment})'
VANISHED_REASON_NO_LOG = ('Konto auf eigenen Wunsch verschwunden (kein Eintrag im Umbenennungs-Logbuch gefunden, '
                          'Name deutet auf Verschwinden hin)')

# results of AdminDatabase.plan_relink
RELINK_NONE, RELINK_RENAME, RELINK_MOVE, RELINK_UNKNOWN, RELINK_TAKEN = 'none', 'rename', 'move', 'unknown', 'taken'

# filter of the user search: value -> (label, SQL condition)
USER_STATUSES = {
    'hidden': ('versteckt', '`user_is_hidden` = 1'),
    'banned': ('ausgeschlossen', '`user_was_banned` = 1'),
    'hidden_or_banned': ('versteckt oder ausgeschlossen', '(`user_is_hidden` = 1 OR `user_was_banned` = 1)'),
    'visible': ('weder versteckt noch ausgeschlossen', '`user_is_hidden` = 0 AND `user_was_banned` = 0'),
}

USER_SELECT = '''SELECT `user_id`, `user_name`, `user_comment`, `user_participates_since`, `user_verified_since`,
                        `user_last_update`, `user_is_hidden`, `user_was_banned` FROM `user`'''


class AdminError(WPPBException):
    """A change was refused; the message is shown to the admin."""


def _user(row):
    if row is None:
        return None
    return {'id': row[0], 'name': row[1], 'comment': row[2], 'participates_since': row[3],
            'verified_since': row[4], 'last_update': row[5], 'hidden': row[6], 'was_banned': row[7]}


def normalize_user_name(name):
    """MediaWiki form of a user name: spaces instead of underscores, first letter upper case."""
    name = ' '.join((name or '').replace('_', ' ').split())
    return name[:1].upper() + name[1:]


def _normalize(field, value):
    if field in FLAG_FIELDS:
        return 1 if value else 0
    value = str(value or '').replace('\r\n', '\n').strip()
    return value or None


def _require_reason(reason):
    reason = (reason or '').strip()
    if not reason:
        raise AdminError('Bitte eine Begründung angeben.')
    return reason


def _mw_timestamp(value):
    value = _text(value)
    try:
        return datetime.datetime.strptime(value, '%Y%m%d%H%M%S')
    except (TypeError, ValueError):
        return None


class AdminDatabase(Database):
    """The pb database plus the admin functions."""

    def __init__(self):
        super().__init__(use_replica=False)
        self.meta_conn = None

    # --- connections -------------------------------------------------------

    def _credentials(self):
        user, password, wp_host = read_db_credentials()
        return user, password, wp_host

    def replica(self):
        """The dewiki replica connection, opened on first use."""
        if self.wp_conn is None:
            user, password, host = self._credentials()
            self.wp_conn = pymysql.connect(host=host, port=config.db_port, user=user, password=password,
                                           database=config.replica_db_name, charset='utf8')
        return self.wp_conn

    def meta(self):
        """The Meta replica connection (global rename log), opened on first use."""
        if self.meta_conn is None:
            user, password, _ = self._credentials()
            self.meta_conn = pymysql.connect(host=config.meta_replica_host, port=config.db_port, user=user,
                                             password=password, database=config.meta_replica_db_name, charset='utf8')
        return self.meta_conn

    def close_connections(self):
        super().close_connections()
        if self.meta_conn is not None:
            self.meta_conn.close()

    def _write(self, change):
        """Runs *change(cursor)* in a transaction and returns its result."""
        try:
            with self.conn.cursor() as curs:
                result = change(curs)
            self.conn.commit()
            return result
        except BaseException:
            self.conn.rollback()
            raise

    # --- reading -----------------------------------------------------------

    def get_overview(self):
        with self.conn.cursor() as curs:
            curs.execute('SELECT COUNT(*), SUM(`user_is_hidden`), SUM(`user_was_banned`) FROM `user`;')
            users, hidden, banned = curs.fetchone()
            curs.execute('SELECT COUNT(*), SUM(`cf_was_deleted`) FROM `confirmation`;')
            confirmations, deleted = curs.fetchone()
            curs.execute('SELECT COUNT(*), MAX(`at_timestamp`) FROM `audit_trail`;')
            audit_entries, last_audit = curs.fetchone()
        return {'users': users, 'hidden': int(hidden or 0), 'banned': int(banned or 0),
                'confirmations': confirmations, 'deleted': int(deleted or 0),
                'audit_entries': audit_entries, 'last_audit': last_audit}

    def search_users(self, query, status='', limit=200):
        """
        Users (also hidden and banned ones) whose name contains *query*, or with the id *query*,
        restricted by *status* (one of `USER_STATUSES`). Without query and status: nothing.
        """
        query = (query or '').strip()
        status = status if status in USER_STATUSES else ''
        if not query and not status:
            return []
        where, args = [], []
        if query:
            pattern = '%' + query.replace('\\', '\\\\').replace('%', '\\%').replace('_', '\\_') + '%'
            where.append('(`user_name` LIKE %s OR `user_id` = %s)')
            args += [pattern, int(query) if query.isdigit() else -1]
        if status:
            where.append(USER_STATUSES[status][1])
        with self.conn.cursor() as curs:
            curs.execute(USER_SELECT + ' WHERE ' + ' AND '.join(where) + ' ORDER BY `user_name` LIMIT %s;',
                         args + [limit])
            return [_user(row) for row in curs.fetchall()]

    def get_user_admin(self, user_id):
        with self.conn.cursor() as curs:
            curs.execute(USER_SELECT + ' WHERE `user_id` = %s;', (user_id,))
            return _user(curs.fetchone())

    def get_user_id_by_name(self, name):
        with self.conn.cursor() as curs:
            curs.execute('SELECT `user_id` FROM `user` WHERE `user_name` = %s;', (name,))
            row = curs.fetchone()
            return row[0] if row else None

    def get_confirmation_admin(self, user_id, confirmed_user_id):
        with self.conn.cursor() as curs:
            curs.execute('''
            SELECT `cf_user_id`, `cf_confirmed_user_id`, `cf_timestamp`, `cf_comment`, `cf_was_deleted`
                FROM `confirmation` WHERE `cf_user_id` = %s AND `cf_confirmed_user_id` = %s
            ;''', (user_id, confirmed_user_id))
            row = curs.fetchone()
        if row is None:
            return None
        return {'user_id': row[0], 'confirmed_user_id': row[1], 'timestamp': row[2], 'comment': row[3],
                'was_deleted': row[4]}

    def get_audit_entries(self, user_id=None, action=None, performer=None, page=1, count=100):
        """
        Entries of `audit_trail`, newest first, with the current names of the users.
        *user_id* matches both user columns. Returns `(entries, has_more)`.
        """
        where, args = [], []
        if user_id is not None:
            where.append('(`at_user_id` = %s OR `at_confirmed_user_id` = %s)')
            args += [user_id, user_id]
        if action:
            where.append('`at_action` = %s')
            args.append(action)
        if performer:
            where.append('`at_performer` = %s')
            args.append(performer)
        with self.conn.cursor() as curs:
            curs.execute('''
            SELECT `at_id`, `at_timestamp`, `at_action`, `at_user_id`, `at_confirmed_user_id`, `at_field`,
                    `at_old_value`, `at_new_value`, `at_reason`, `at_performer`, u1.`user_name`, u2.`user_name`
                FROM `audit_trail`
                LEFT JOIN `user` AS u1 ON u1.`user_id` = `at_user_id`
                LEFT JOIN `user` AS u2 ON u2.`user_id` = `at_confirmed_user_id`
                %s
                ORDER BY `at_id` DESC
                LIMIT %%s OFFSET %%s
            ;''' % (('WHERE ' + ' AND '.join(where)) if where else ''), args + [count + 1, (page - 1) * count])
            rows = curs.fetchall()
        keys = ('id', 'timestamp', 'action', 'user_id', 'confirmed_user_id', 'field', 'old_value', 'new_value',
                'reason', 'performer', 'user_name', 'confirmed_user_name')
        return [dict(zip(keys, row)) for row in rows[:count]], len(rows) > count

    def get_audit_performers(self):
        with self.conn.cursor() as curs:
            curs.execute('SELECT DISTINCT `at_performer` FROM `audit_trail` ORDER BY 1;')
            return [row[0] for row in curs.fetchall()]

    # --- changes -----------------------------------------------------------

    def update_user(self, user_id, changes, reason, performer):
        """
        Sets the fields of *changes* (`USER_FIELDS` only) and records every changed field in
        `audit_trail`. Returns the names of the changed fields (empty if nothing changed).
        """
        reason = _require_reason(reason)

        def change(curs):
            curs.execute('SELECT ' + ', '.join('`%s`' % f for f in USER_FIELDS) +
                         ' FROM `user` WHERE `user_id` = %s FOR UPDATE;', (user_id,))
            row = curs.fetchone()
            if row is None:
                raise AdminError('Unbekannter Benutzer: %s' % user_id)
            changed = []
            for field, old in zip(USER_FIELDS, row):
                if field not in changes:
                    continue
                new = _normalize(field, changes[field])
                if new == _normalize(field, old):
                    continue
                curs.execute('UPDATE `user` SET `%s` = %%s WHERE `user_id` = %%s;' % field, (new, user_id))
                self.add_audit_entry('user_change', performer, user_id=user_id, field=field, old_value=old,
                                     new_value=new, reason=reason, commit=False)
                changed.append(field)
            return changed
        return self._write(change)

    def update_confirmation(self, user_id, confirmed_user_id, changes, reason, performer):
        """Like `update_user`, for the `CONFIRMATION_FIELDS` of one confirmation."""
        reason = _require_reason(reason)

        def change(curs):
            curs.execute('SELECT ' + ', '.join('`%s`' % f for f in CONFIRMATION_FIELDS) +
                         ' FROM `confirmation` WHERE `cf_user_id` = %s AND `cf_confirmed_user_id` = %s FOR UPDATE;',
                         (user_id, confirmed_user_id))
            row = curs.fetchone()
            if row is None:
                raise AdminError('Unbekannte Bestätigung: %s → %s' % (user_id, confirmed_user_id))
            changed = []
            for field, old in zip(CONFIRMATION_FIELDS, row):
                if field not in changes:
                    continue
                new = _normalize(field, changes[field])
                if new == _normalize(field, old):
                    continue
                curs.execute('UPDATE `confirmation` SET `%s` = %%s WHERE `cf_user_id` = %%s AND `cf_confirmed_user_id` = %%s;'
                             % field, (new, user_id, confirmed_user_id))
                self.add_audit_entry('confirmation_change', performer, user_id=user_id,
                                     confirmed_user_id=confirmed_user_id, field=field, old_value=old,
                                     new_value=new, reason=reason, commit=False)
                changed.append(field)
            return changed
        return self._write(change)

    def delete_confirmation(self, user_id, confirmed_user_id, reason, performer):
        """Deletes one confirmation; the deleted row is kept as JSON in `audit_trail`."""
        reason = _require_reason(reason)

        def change(curs):
            curs.execute('''
            SELECT `cf_user_id`, `cf_confirmed_user_id`, `cf_timestamp`, `cf_comment`, `cf_was_deleted`
                FROM `confirmation` WHERE `cf_user_id` = %s AND `cf_confirmed_user_id` = %s FOR UPDATE
            ;''', (user_id, confirmed_user_id))
            row = curs.fetchone()
            if row is None:
                raise AdminError('Unbekannte Bestätigung: %s → %s' % (user_id, confirmed_user_id))
            old = dict(zip(('cf_user_id', 'cf_confirmed_user_id', 'cf_timestamp', 'cf_comment', 'cf_was_deleted'), row))
            curs.execute('DELETE FROM `confirmation` WHERE `cf_user_id` = %s AND `cf_confirmed_user_id` = %s;',
                         (user_id, confirmed_user_id))
            self.add_audit_entry('confirmation_delete', performer, user_id=user_id, confirmed_user_id=confirmed_user_id,
                                 old_value=json.dumps(old, default=str, ensure_ascii=False), reason=reason, commit=False)
        self._write(change)

    def _mw_user_by_name(self, name):
        """`(user_id, user_name)` of a dewiki account, `None` if it does not exist."""
        with self.replica().cursor() as curs:
            curs.execute('SELECT `user_id`, `user_name` FROM `user` WHERE `user_name` = %s;', (name,))
            row = curs.fetchone()
        return (int(row[0]), _text(row[1])) if row else None

    def plan_relink(self, user_id, dewiki_name):
        """
        What `relink` would do to bring *user_id* in line with the dewiki account *dewiki_name*:
        a dict with `action` (`RELINK_*`), `name`, `mw_id` and a `message` for the admin.
        """
        user = self.get_user_admin(user_id)
        if user is None:
            raise AdminError('Unbekannter Benutzer: %s' % user_id)
        name = normalize_user_name(dewiki_name)
        plan = {'action': RELINK_UNKNOWN, 'name': name, 'mw_id': None, 'old_name': user['name'], 'old_id': user_id}
        account = self._mw_user_by_name(name) if name else None
        if account is None:
            plan['message'] = 'Auf dewiki gibt es kein Benutzerkonto „%s“.' % name
            return plan
        plan['mw_id'], plan['name'] = account
        name_owner = self.get_user_id_by_name(plan['name'])
        if plan['mw_id'] == user_id:
            if plan['name'] == user['name']:
                plan.update(action=RELINK_NONE, message='Name und user_id stimmen bereits mit dewiki überein.')
            elif name_owner is not None:
                plan.update(action=RELINK_TAKEN, message='Der Name „%s“ gehört in pb schon dem Benutzer mit der user_id %s.'
                            % (plan['name'], name_owner))
            else:
                plan.update(action=RELINK_RENAME, message='Umbenennung: „%s“ → „%s“ (user_id %s bleibt).'
                            % (user['name'], plan['name'], user_id))
            return plan
        if self.get_user_admin(plan['mw_id']) is not None:
            plan.update(action=RELINK_TAKEN, message='Die user_id %s (dewiki: „%s“) gehört in pb schon einem anderen '
                        'Teilnehmer.' % (plan['mw_id'], plan['name']))
        elif name_owner is not None and name_owner != user_id:
            plan.update(action=RELINK_TAKEN, message='Der Name „%s“ gehört in pb schon dem Benutzer mit der user_id %s.'
                        % (plan['name'], name_owner))
        else:
            plan.update(action=RELINK_MOVE, message='user_id-Korrektur: %s → %s, Name „%s“ → „%s“. Bestätigungen, '
                        'die auf die alte user_id verweisen, werden mit verschoben.'
                        % (user_id, plan['mw_id'], user['name'], plan['name']))
        return plan

    def relink(self, user_id, dewiki_name, reason, performer):
        """
        Carries out `plan_relink`: renames the user or moves the row to the right user_id
        (with all confirmations, see sql/schema.md). Returns the plan.
        """
        reason = _require_reason(reason)
        plan = self.plan_relink(user_id, dewiki_name)
        if plan['action'] not in (RELINK_RENAME, RELINK_MOVE):
            raise AdminError(plan['message'])
        old_name, new_name, new_id = plan['old_name'], plan['name'], plan['mw_id']

        def rename(curs):
            curs.execute('UPDATE `user` SET `user_name` = %s WHERE `user_id` = %s;', (new_name, user_id))
            self.add_audit_entry('rename', performer, user_id=user_id, field='user_name', old_value=old_name,
                                 new_value=new_name, reason=reason, commit=False)

        def move(curs):
            curs.execute("UPDATE `user` SET `user_name` = CONCAT('tmp-fix-', `user_id`) WHERE `user_id` = %s;", (user_id,))
            curs.execute('''
            INSERT INTO `user` (`user_id`, `user_name`, `user_comment`, `user_participates_since`, `user_verified_since`,
                                `user_last_update`, `user_is_hidden`, `user_was_banned`)
                SELECT %s, %s, `user_comment`, `user_participates_since`, `user_verified_since`,
                       `user_last_update`, `user_is_hidden`, `user_was_banned`
                FROM `user` WHERE `user_id` = %s
            ;''', (new_id, new_name, user_id))
            curs.execute('UPDATE `confirmation` SET `cf_user_id` = %s WHERE `cf_user_id` = %s;', (new_id, user_id))
            curs.execute('UPDATE `confirmation` SET `cf_confirmed_user_id` = %s WHERE `cf_confirmed_user_id` = %s;',
                         (new_id, user_id))
            curs.execute('DELETE FROM `user` WHERE `user_id` = %s;', (user_id,))
            # cached home wiki of the old account; the job looks up the new one
            curs.execute('DELETE FROM `user_home_wiki` WHERE `hw_user_id` = %s;', (user_id,))
            self.add_audit_entry('user_change', performer, user_id=new_id, field='user_id', old_value=user_id,
                                 new_value=new_id, reason=reason, commit=False)
            if new_name != old_name:
                self.add_audit_entry('rename', performer, user_id=new_id, field='user_name', old_value=old_name,
                                     new_value=new_name, reason=reason, commit=False)

        try:
            self._write(rename if plan['action'] == RELINK_RENAME else move)
        except pymysql.IntegrityError as e:
            raise AdminError('Die Datenbank hat die Änderung abgelehnt: %s' % (e,))
        return plan

    # --- vanished accounts -------------------------------------------------

    def get_vanished_candidates(self):
        """
        Visible participants whose name looks like a vanished account, each with the latest
        global rename to that name on Meta (`rename`: timestamp, performer, comment, or `None`)
        and the suggested `reason` for hiding.
        """
        with self.conn.cursor() as curs:
            curs.execute(USER_SELECT + ' WHERE `user_is_hidden` = 0 ORDER BY `user_name`;')
            users = [_user(row) for row in curs.fetchall() if VANISHED_RE.match(row[1])]
        renames = self.get_global_renames([user['name'] for user in users])
        for user in users:
            user['rename'] = renames.get(user['name'])
            user['reason'] = vanished_reason(user['rename'])
        return users

    def count_hidden_vanished(self):
        with self.conn.cursor() as curs:
            curs.execute('SELECT `user_name` FROM `user` WHERE `user_is_hidden` = 1;')
            return sum(1 for row in curs.fetchall() if VANISHED_RE.match(row[0]))

    def get_global_renames(self, new_names):
        """`{new_name: {'timestamp', 'performer', 'comment'}}`: the latest global rename to each name (Meta)."""
        if not new_names:
            return {}
        titles = ['CentralAuth/' + name.replace(' ', '_') for name in new_names]
        with self.meta().cursor() as curs:
            curs.execute('''
            SELECT `log_title`, `log_timestamp`, `actor_name`, `comment_text`
                FROM `logging_logindex`
                JOIN `actor_logging` ON `actor_id` = `log_actor`
                JOIN `comment_logging` ON `comment_id` = `log_comment_id`
                WHERE `log_type` = 'gblrename' AND `log_namespace` = -1 AND `log_title` IN (%s)
                ORDER BY `log_timestamp`
            ;''' % ', '.join(['%s'] * len(titles)), titles)
            renames = {}
            for title, timestamp, performer, comment in curs.fetchall():
                name = _text(title)[len('CentralAuth/'):].replace('_', ' ')
                renames[name] = {'timestamp': _mw_timestamp(timestamp), 'performer': _text(performer),
                                 'comment': _text(comment)}
            return renames

    # --- consistency checks ------------------------------------------------

    def check_self_confirmations(self):
        with self.conn.cursor() as curs:
            curs.execute('''
            SELECT `cf_user_id`, `user_name`, `cf_timestamp`, `cf_was_deleted`
                FROM `confirmation` JOIN `user` ON `user_id` = `cf_user_id`
                WHERE `cf_user_id` = `cf_confirmed_user_id` ORDER BY `cf_timestamp`
            ;''')
            return [dict(zip(('id', 'name', 'timestamp', 'was_deleted'), row)) for row in curs.fetchall()]

    def check_verification(self):
        """
        Visible users whose `user_verified_since` does not fit their confirmations: not verified with
        3 or more confirmations, or verified with fewer than 3 (the bot counts all, also deleted
        ones and those of hidden users, see sql/schema.md).
        """
        with self.conn.cursor() as curs:
            curs.execute('''
            SELECT `user_id`, `user_name`, `user_verified_since`, COUNT(`cf_user_id`),
                    COALESCE(SUM(`cf_was_deleted` = 0), 0)
                FROM `user` LEFT JOIN `confirmation` ON `cf_confirmed_user_id` = `user_id`
                WHERE `user_is_hidden` = 0
                GROUP BY `user_id`, `user_name`, `user_verified_since`
                HAVING (`user_verified_since` IS NULL AND COUNT(`cf_user_id`) >= 3)
                    OR (`user_verified_since` IS NOT NULL AND COUNT(`cf_user_id`) < 3)
                ORDER BY `user_name`
            ;''')
            return [dict(zip(('id', 'name', 'verified_since', 'count', 'valid_count'), row))
                    for row in curs.fetchall()]

    def check_banned_confirmations(self):
        """Confirmations from or to excluded users that are not marked as deleted."""
        with self.conn.cursor() as curs:
            curs.execute('''
            SELECT `cf_user_id`, giving.`user_name`, giving.`user_was_banned`,
                    `cf_confirmed_user_id`, taking.`user_name`, taking.`user_was_banned`, `cf_timestamp`
                FROM `confirmation`
                JOIN `user` AS giving ON giving.`user_id` = `cf_user_id`
                JOIN `user` AS taking ON taking.`user_id` = `cf_confirmed_user_id`
                WHERE `cf_was_deleted` = 0 AND (giving.`user_was_banned` = 1 OR taking.`user_was_banned` = 1)
                ORDER BY `cf_timestamp`
            ;''')
            keys = ('user_id', 'user_name', 'user_banned', 'confirmed_user_id', 'confirmed_user_name',
                    'confirmed_banned', 'timestamp')
            return [dict(zip(keys, row)) for row in curs.fetchall()]

    def check_dewiki_accounts(self, batch_size=500):
        """
        Compares the participants with dewiki (by user_id): `missing` (no account with that id)
        and `renamed` (the name differs; `update-user-names` takes over the renames that are in
        the rename log every hour, the rest needs a look, probably a wrong user_id).
        """
        with self.conn.cursor() as curs:
            curs.execute('SELECT `user_id`, `user_name`, `user_is_hidden` FROM `user` ORDER BY `user_name`;')
            users = curs.fetchall()
        self.replica()
        mw_names = {}
        ids = [row[0] for row in users]
        for start in range(0, len(ids), batch_size):
            mw_names.update(self._get_mw_user_names(ids[start:start + batch_size]))
        missing, renamed = [], []
        for user_id, name, hidden in users:
            if user_id not in mw_names:
                missing.append({'id': user_id, 'name': name, 'hidden': hidden})
            elif mw_names[user_id] != name:
                renamed.append({'id': user_id, 'name': name, 'hidden': hidden, 'dewiki_name': mw_names[user_id]})
        return {'missing': missing, 'renamed': renamed}


def vanished_reason(rename):
    """The reason for hiding a vanished account, in the form used so far (audit_trail 86-92)."""
    if not rename:
        return VANISHED_REASON_NO_LOG
    day = rename['timestamp'].strftime('%Y-%m-%d') if rename['timestamp'] else '?'
    return VANISHED_REASON.format(day=day, comment=rename['comment'] or '')
