"""In-memory replacement for admin_api.AdminDatabase used by the unit tests of the admin area."""
from admin_api import AdminError, vanished_reason
from tests.unit.fake_db import CONFIRMATIONS, USERS, FakeDatabase, ts


def _user(u):
    return {'id': u[1], 'name': u[0], 'comment': u[2], 'hidden': u[3], 'was_banned': u[4],
            'participates_since': u[5], 'verified_since': u[6], 'last_update': u[5]}


class FakeAdminDatabase(FakeDatabase):
    """Records the changes in `log` instead of writing them."""

    log = []

    def get_overview(self):
        return {'users': 4, 'hidden': 1, 'banned': 1, 'confirmations': 4, 'deleted': 0,
                'audit_entries': 1, 'last_audit': ts(2026, 10, 29, 23, 5)}

    def search_users(self, query, status='', limit=200):
        FakeAdminDatabase.log.append(('search_users', query, status))
        matches = {'': lambda u: True, 'hidden': lambda u: u[3], 'banned': lambda u: u[4],
                   'hidden_or_banned': lambda u: u[3] or u[4], 'visible': lambda u: not u[3] and not u[4]}
        if not query and not status:
            return []
        return [_user(u) for u in USERS if matches[status](u)
                and (not query or query.lower() in u[0].lower() or query == str(u[1]))]

    def get_user_admin(self, user_id):
        user = self.get_user_by_id(user_id)
        return _user(user) if user else None

    def get_user_id_by_name(self, name):
        user = self.get_user_by_name(name)
        return user[1] if user else None

    def get_confirmation_admin(self, user_id, confirmed_user_id):
        cf = CONFIRMATIONS.get((user_id, confirmed_user_id))
        if cf is None:
            return None
        return {'user_id': user_id, 'confirmed_user_id': confirmed_user_id, 'timestamp': cf[0], 'comment': cf[1],
                'was_deleted': 0}

    def get_audit_entries(self, user_id=None, action=None, performer=None, page=1, count=100):
        FakeAdminDatabase.log.append(('get_audit_entries', user_id, action, performer, page))
        entry = {'id': 1, 'timestamp': ts(2026, 10, 29, 23, 5), 'action': 'user_change', 'user_id': 3,
                 'confirmed_user_id': None, 'field': 'user_is_hidden', 'old_value': '0', 'new_value': '1',
                 'reason': 'left, see [[WP:PB]]', 'performer': 'Euku', 'user_name': 'Eve', 'confirmed_user_name': None}
        return [entry], page == 1

    def get_audit_performers(self):
        return ['Euku', 'update-user-names (Job)']

    @staticmethod
    def _reason(reason):
        if not (reason or '').strip():
            raise AdminError('Bitte eine Begründung angeben.')

    def update_user(self, user_id, changes, reason, performer):
        self._reason(reason)
        FakeAdminDatabase.log.append(('update_user', user_id, changes, reason, performer))
        return [field for field in changes if field != 'user_comment']

    def update_confirmation(self, user_id, confirmed_user_id, changes, reason, performer):
        self._reason(reason)
        FakeAdminDatabase.log.append(('update_confirmation', user_id, confirmed_user_id, changes, reason, performer))
        return list(changes)

    def delete_confirmation(self, user_id, confirmed_user_id, reason, performer):
        self._reason(reason)
        FakeAdminDatabase.log.append(('delete_confirmation', user_id, confirmed_user_id, reason, performer))

    def plan_relink(self, user_id, dewiki_name):
        FakeAdminDatabase.log.append(('plan_relink', user_id, dewiki_name))
        if dewiki_name == 'Nobody':
            return {'action': 'unknown', 'name': dewiki_name, 'mw_id': None,
                    'message': 'Auf dewiki gibt es kein Benutzerkonto „Nobody“.'}
        return {'action': 'move', 'name': dewiki_name, 'mw_id': 99, 'old_id': user_id,
                'message': 'user_id-Korrektur: %s → 99' % user_id}

    def relink(self, user_id, dewiki_name, reason, performer):
        self._reason(reason)
        FakeAdminDatabase.log.append(('relink', user_id, dewiki_name, reason, performer))
        return self.plan_relink(user_id, dewiki_name)

    def get_vanished_candidates(self):
        rename = {'timestamp': ts(2024, 9, 29, 10, 57), 'performer': 'Cabayi',
                  'comment': 'per [[m:Special:GlobalRenameQueue/request/129480|request]]'}
        return [{'id': 2, 'name': 'Bob', 'participates_since': ts(2008, 2, 11), 'rename': rename,
                 'reason': vanished_reason(rename)}]

    def count_hidden_vanished(self):
        return 7

    def check_self_confirmations(self):
        return [{'id': 1, 'name': 'Alice', 'timestamp': ts(2009, 1, 1), 'was_deleted': 0}]

    def check_verification(self):
        return [{'id': 2, 'name': 'Bob', 'verified_since': None, 'count': 3, 'valid_count': 3}]

    def check_banned_confirmations(self):
        return [{'user_id': 4, 'user_name': 'Mallory', 'user_banned': 1, 'confirmed_user_id': 1,
                 'confirmed_user_name': 'Alice', 'confirmed_banned': 0, 'timestamp': ts(2017, 1, 2, 9, 0)}]

    def check_dewiki_accounts(self, batch_size=500):
        return {'missing': [], 'renamed': [{'id': 1, 'name': 'Alice', 'hidden': 0, 'dewiki_name': 'Alice2'}]}
