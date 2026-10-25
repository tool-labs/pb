"""In-memory replacement for api.Database used by the unit tests."""
import datetime as dt

import api


def ts(*args):
    return dt.datetime(*args)


# (user_name, user_id, user_comment, user_is_hidden, user_was_banned,
#  user_participates_since, user_verified_since)
USERS = [
    ('Alice', 1, None, 0, 0, ts(2008, 2, 10, 12, 0), ts(2008, 3, 1, 9, 30)),
    ('Bob', 2, 'Admin note', 0, 0, ts(2008, 2, 11, 12, 0), None),
    ('Eve', 3, None, 1, 0, ts(2016, 1, 1, 12, 0), None),
    ('Mallory', 4, None, 0, 1, ts(2017, 1, 1, 12, 0), None),
]

# (cf_user_id, cf_confirmed_user_id) -> (cf_timestamp, cf_comment)
CONFIRMATIONS = {
    (1, 2): (ts(2008, 2, 20, 10, 0), 'Met at the [[Stammtisch Berlin]]'),
    (2, 1): (ts(2008, 2, 20, 10, 5), None),
    (3, 1): (ts(2016, 1, 2, 18, 0), 'Hidden user comment'),
}


class FakeDatabase(api.Database):
    """Replaces api.Database in app.py; records how it was used."""

    instances = []

    def __init__(self, use_replica=True):
        self.use_replica = use_replica
        self.closed = False
        self.calls = []
        FakeDatabase.instances.append(self)

    def close_connections(self):
        self.closed = True

    def _user(self, pred):
        return next((u for u in USERS if pred(u)), None)

    def get_user_by_id(self, id):
        return self._user(lambda u: u[1] == id)

    def get_user_by_name(self, name):
        return self._user(lambda u: u[0] == name)

    def get_confirmation(self, user_id, confirmed_id):
        return CONFIRMATIONS.get((user_id, confirmed_id))

    def _confirmations(self, user_id, own_index, other_index, show_hidden_users):
        rows = []
        for key, (stamp, comment) in sorted(CONFIRMATIONS.items(), key=lambda kv: kv[1][0], reverse=True):
            if key[own_index] != user_id:
                continue
            other = self.get_user_by_id(key[other_index])
            if other[3] and not show_hidden_users:
                continue
            reverse_key = (key[1], key[0])
            rows.append((other[0], other[1], stamp, comment, 0, other[3], reverse_key in CONFIRMATIONS))
        return rows

    def get_confirmations_by_user(self, user_id, show_hidden_users=True):
        return self._confirmations(user_id, 0, 1, show_hidden_users)

    def get_confirmations_by_confirmed(self, user_id, show_hidden_users=True):
        return self._confirmations(user_id, 1, 0, show_hidden_users)

    def get_all_users(self, show_hidden_users=True, show_banned_users=False):
        rows = []
        for u in USERS:
            if (u[3] and not show_hidden_users) or (u[4] and not show_banned_users):
                continue
            given = len(self.get_confirmations_by_user(u[1], show_hidden_users)) or None
            taken = len(self.get_confirmations_by_confirmed(u[1], show_hidden_users)) or None
            rows.append(u + (given, taken))
        return rows

    def get_user_count(self, count_banned_users=False, count_hidden_users=True):
        return len([u for u in USERS if (count_hidden_users or not u[3]) and (count_banned_users or not u[4])])

    def get_confirmation_count(self, count_deleted_cf=False, count_hidden_users=True):
        return 2

    def get_latest_confirmations(self, page=1, count=50):
        self.calls.append(('get_latest_confirmations', page, count))
        if page > 1:
            return []
        return [('Bob', 'Alice', None, 0, ts(2008, 2, 20, 10, 5)),
                ('Alice', 'Bob', 'Met at the [[Stammtisch Berlin]]', 0, ts(2008, 2, 20, 10, 0))]

    def _get_stats_confirmations_by_month(self):
        return [('2008-02', 0, 2)]

    def _get_users_by_month(self):
        return [('2008-02', 0, 1), ('2008-02', 1, 1)]
