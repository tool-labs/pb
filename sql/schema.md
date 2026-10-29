# Database schema

The tool uses two databases:

* **`s51344__pb`** on ToolsDB (`tools.db.svc.wikimedia.cloud`, MariaDB 10.6): the data of
  the project. The web app reads it. SpBot (`web/bot_api.py`) and admins (manually, in SQL) write it.
* **`dewiki_p`**, the German Wikipedia replica (read only): used to look up MediaWiki user ids
  and blocks.

All times are the local wiki times (CET/CEST) from the templates on the wiki page, stored
unchanged. The system tests load the `sql` code blocks of this file
(see `tests/conftest.py`), so they must stay in sync with production.

## Tables

```
user 1 ──< confirmation >── 1 user
           (cf_user_id = who confirmed, cf_confirmed_user_id = who was confirmed)

stats_confirmations_by_month   (derived from confirmation + user, no foreign keys)
user_home_wiki                 (cache of the CentralAuth replica, 1 row per user, no foreign key)
audit_trail                    (log of admin actions, no foreign keys: entries outlive deleted rows)
```

### `user`: participants

| Column | Type | Meaning |
|--------|------|---------|
| `user_id` | `int unsigned`, unique | MediaWiki user id on dewiki. The bot looks it up in the replica when it adds the user, so only existing accounts can join. |
| `user_name` | `varchar(255)`, unique | User name as written in the request. Renames on the wiki are taken over hourly by `jobs/update_user_names.py` (by `user_id`). |
| `user_comment` | `text`, nullable | Admin note (e.g. "sockpuppet of …"). **Shown on the public user page.** |
| `user_participates_since` | `timestamp`, nullable | Time of the `{{…/neuer Benutzer}}` request. |
| `user_verified_since` | `timestamp`, nullable | Set once, by `BotDatabase.add_confirmation`, to the time of the confirmation that brought the user to 3 confirmations. `NULL` = not verified. Never cleared automatically. |
| `user_last_update` | `timestamp` | Set when the user is added and on every confirmation once the user has ≥ 3 (`touch_user`). |
| `user_is_hidden` | `0`/`1` | The participant has left the project. The name is no longer shown and their confirmations are not counted. Not meant for sockpuppets. |
| `user_was_banned` | `0`/`1` | Excluded from the project, e.g. sockpuppets. Not used for blocks on Wikipedia. |

There is no primary key, only the two unique keys (same as in production).

### `confirmation`: who has confirmed whom

| Column | Type | Meaning |
|--------|------|---------|
| `cf_user_id` | `int unsigned`, FK → `user.user_id` | The user who gives the confirmation. |
| `cf_confirmed_user_id` | `int unsigned`, FK → `user.user_id` | The user who is confirmed. |
| `cf_timestamp` | `timestamp` | Time of the `{{…/neue Bestätigung}}` request. |
| `cf_comment` | `mediumtext`, nullable | `Kommentar=` from the request (wikitext, may contain `[[links]]`). |
| `cf_was_deleted` | `0`/`1` | Revoked, e.g. after a sockpuppet was uncovered. Not for confirmations made by mistake. |

Primary key `(cf_user_id, cf_confirmed_user_id)`: one confirmation per direction. A mutual
acquaintance consists of two rows ("Rückbestätigung").
Index `cf_timestamp` for the "latest confirmations" lists on the start page and `/recent`.

### `stats_confirmations_by_month`: cache for the main page

| Column | Type | Meaning |
|--------|------|---------|
| `year_month` | `varchar(255)`, unique | `YYYY-MM` of `cf_timestamp`. |
| `group` | `int` | Always `0` (the web app supports two groups, only one is used). |
| `count` | `int unsigned` | Confirmations in that month, without deleted ones and without hidden users on either side. |

Rebuilt every hour by `jobs/update_stats.py` (`TRUNCATE` + `INSERT … SELECT`). The user statistics
on the main page are computed live from `user`.

### `user_home_wiki`: cached home wikis

| Column | Type | Meaning |
|--------|------|---------|
| `hw_user_id` | `int unsigned`, primary key | `user.user_id` (no foreign key, like the stats table). |
| `hw_has_sul` | `0`/`1` | The dewiki account is attached to a global (SUL) account. `0` also if the dewiki account no longer exists. |
| `hw_home_db` | `varchar(255)`, nullable | Home wiki of the global account (`gu_home_db`, e.g. `dewiki`). `NULL` without SUL account. |
| `hw_home_url` | `varchar(255)`, nullable | URL of the home wiki from `meta_p.wiki` (e.g. `https://de.wikipedia.org`). `NULL` for closed wikis that are not listed there. |
| `hw_checked` | `timestamp`, nullable | Time of the lookup (`NOW()` on ToolsDB, i.e. UTC, unlike the other timestamps). |

Filled by `jobs/update_home_wikis.py` (hourly): users without a row or with a row older than
`home_wiki_max_age_days` (`web/config.py`, 7 days) are looked up again. Users without a row are shown
without home wiki. The web app only reads this table, it has no replica connection.

### `audit_trail`: admin actions

| Column | Type | Meaning |
|--------|------|---------|
| `at_id` | `int unsigned`, auto increment | |
| `at_timestamp` | `timestamp` | When the action was done, **UTC** (unlike the wiki times in the other tables). |
| `at_action` | `varchar(32)` | See below. |
| `at_user_id` | `int unsigned`, nullable | The affected user; for confirmations `cf_user_id` (who confirmed). |
| `at_confirmed_user_id` | `int unsigned`, nullable | For confirmations: `cf_confirmed_user_id`. |
| `at_field` | `varchar(64)`, nullable | The changed column, `NULL` for deletions. |
| `at_old_value`, `at_new_value` | `mediumtext`, nullable | Values before/after (`0`/`1` for the flags). For deletions `at_old_value` is the deleted row as JSON. |
| `at_reason` | `text`, nullable | Reason entered by the admin (may contain wikitext links). |
| `at_performer` | `varchar(255)` | Wiki user name of the admin, or the job (`update-user-names (Job)`). |

`at_action` and the allowed `at_field` (checked by `Database.add_audit_entry`):

| `at_action` | `at_field` | Written by |
|-------------|------------|------------|
| `rename` | `user_name` | `jobs/update_user_names.py`, automatically with every rename |
| `user_change` | `user_was_banned`, `user_is_hidden`, `user_comment` | admins (manually in SQL until the web UI exists) |
| `confirmation_change` | `cf_comment`, `cf_was_deleted` | admins |
| `user_delete` | `NULL` | admins |
| `confirmation_delete` | `NULL` | admins |

Privacy: the table is **not public**. It contains old names, also of accounts that vanished on
request (`Vanished user …`, `Renamed user …`), and admin notes. The job log, which everyone on
Toolforge can read, gets only user ids and new names.

Until the web UI exists, a manual change is recorded in the same transaction, e.g.:

```
START TRANSACTION;
UPDATE user SET user_is_hidden = 1 WHERE user_id = 123;
INSERT INTO audit_trail (at_timestamp, at_action, at_user_id, at_field, at_old_value, at_new_value, at_reason, at_performer)
  VALUES (UTC_TIMESTAMP(), 'user_change', 123, 'user_is_hidden', '0', '1', 'left the project, see [[Diskussion:…]]', 'AdminName');
COMMIT;
```

## What is counted where

| Place | Hidden users | Banned users | Deleted confirmations |
|-------|--------------|--------------|-----------------------|
| Main page: participant count | excluded | excluded | – |
| Main page: confirmation count, latest confirmations, `/recent` | excluded | included | excluded |
| `/users`: list | excluded | excluded | – |
| `/users`: given/received counts | excluded | included | **included** |
| User page: lists | excluded | included (own page shows a warning) | included, marked |
| Wiki participant list (bot) | excluded | excluded | excluded, but confirmations *by* hidden users count |
| Verification (3 confirmations, bot) | included | included | included |
| Statistics table | excluded | included | excluded |
| `/users`: filter "confirmation in the last 6 months" | excluded | included | excluded |

## Replica tables used (`dewiki_p`)

* `user` (`user_id`, `user_name`): `Database.get_mw_user_id`, used by the bot before adding a user.
* `block_target` (`bt_user`): `Database.user_blocked`. The result is currently not displayed.
* `user` (`user_id`, `user_name`): also `Database.update_home_wikis` and `Database.update_user_names`
  (job `update-user-names`), to get the current names.

## CentralAuth replica tables used (`centralauth_p`, `meta_p`)

On `centralauth.analytics.db.svc.wikimedia.cloud`, read by `Database.update_home_wikis` only:

* `localuser` (`lu_wiki = 'dewiki'`, `lu_name`): the dewiki account is attached to a global account.
  Looked up by name, because `lu_local_id` has no index on the replica.
* `globaluser` (`gu_name`, `gu_home_db`): the home wiki.
* `meta_p.wiki` (`dbname`, `url`): the URL of the home wiki.

The system tests use a minimal stand-in, `tests/system/centralauth_schema.sql`.

The system tests use a minimal stand-in, `tests/system/replica_schema.sql`.

## DDL

The statements below match production. Export them with
`mariadb-dump --no-data s51344__pb`. To create an empty database from this file:

```bash
sed -n '/^```sql$/,/^```$/{/^```/d;p}' sql/schema.md | mariadb <database>
```

`NULL` is spelled out for the `timestamp` columns on purpose. ToolsDB runs with
`explicit_defaults_for_timestamp=OFF`, and without it MariaDB silently creates
`NOT NULL … ON UPDATE CURRENT_TIMESTAMP` columns.

```sql
DROP TABLE IF EXISTS `audit_trail`;
DROP TABLE IF EXISTS `user_home_wiki`;
DROP TABLE IF EXISTS `confirmation`;
DROP TABLE IF EXISTS `stats_confirmations_by_month`;
DROP TABLE IF EXISTS `user`;
```

```sql
CREATE TABLE `user` (
  `user_id` int(11) unsigned NOT NULL,
  `user_name` varchar(255) NOT NULL,
  `user_comment` mediumtext DEFAULT NULL,
  `user_participates_since` timestamp NULL DEFAULT NULL,
  `user_verified_since` timestamp NULL DEFAULT NULL,
  `user_last_update` timestamp NOT NULL DEFAULT current_timestamp(),
  `user_is_hidden` int(1) unsigned NOT NULL DEFAULT 0 COMMENT 'This filed toggles if the participant wants to leave PB or not. It is not the right place for uncovered sockpuppets.',
  `user_was_banned` int(1) unsigned NOT NULL DEFAULT 0 COMMENT 'This filed toggles if the participant was ''deleted''/banned from PB or not. It is the right place for uncovered sockpuppets, but not for users were banned on WP.',
  UNIQUE KEY `user_name` (`user_name`),
  UNIQUE KEY `user_id` (`user_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
```

```sql
CREATE TABLE `confirmation` (
  `cf_user_id` int(11) unsigned NOT NULL,
  `cf_confirmed_user_id` int(11) unsigned NOT NULL,
  `cf_timestamp` timestamp NOT NULL DEFAULT current_timestamp(),
  `cf_comment` mediumtext DEFAULT NULL,
  `cf_was_deleted` int(1) unsigned NOT NULL DEFAULT 0 COMMENT 'e.g. when a sockpuppet was uncovered, not when a confirmation was made by mistake',
  PRIMARY KEY (`cf_user_id`,`cf_confirmed_user_id`),
  KEY `cf_confirmed_user_id` (`cf_confirmed_user_id`),
  KEY `cf_user_id` (`cf_user_id`),
  KEY `cf_timestamp` (`cf_timestamp`),
  CONSTRAINT `confirmation_ibfk_1` FOREIGN KEY (`cf_user_id`) REFERENCES `user` (`user_id`),
  CONSTRAINT `confirmation_ibfk_2` FOREIGN KEY (`cf_confirmed_user_id`) REFERENCES `user` (`user_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
```

```sql
CREATE TABLE `stats_confirmations_by_month` (
  `year_month` varchar(255) NOT NULL,
  `group` int(2) NOT NULL,
  `count` int(6) unsigned NOT NULL,
  UNIQUE KEY `year_month` (`year_month`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
```

```sql
CREATE TABLE `user_home_wiki` (
  `hw_user_id` int(11) unsigned NOT NULL,
  `hw_has_sul` int(1) unsigned NOT NULL DEFAULT 0,
  `hw_home_db` varchar(255) DEFAULT NULL,
  `hw_home_url` varchar(255) DEFAULT NULL,
  `hw_checked` timestamp NULL DEFAULT NULL,
  PRIMARY KEY (`hw_user_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
```

```sql
CREATE TABLE `audit_trail` (
  `at_id` int(11) unsigned NOT NULL AUTO_INCREMENT,
  `at_timestamp` timestamp NULL DEFAULT NULL,
  `at_action` varchar(32) NOT NULL,
  `at_user_id` int(11) unsigned DEFAULT NULL,
  `at_confirmed_user_id` int(11) unsigned DEFAULT NULL,
  `at_field` varchar(64) DEFAULT NULL,
  `at_old_value` mediumtext DEFAULT NULL,
  `at_new_value` mediumtext DEFAULT NULL,
  `at_reason` text DEFAULT NULL,
  `at_performer` varchar(255) NOT NULL,
  PRIMARY KEY (`at_id`),
  KEY `at_user_id` (`at_user_id`),
  KEY `at_timestamp` (`at_timestamp`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
```

## Known issues

* `user` uses `utf8mb4_general_ci` (converted from `utf8mb3_general_ci` on 2026-10-26), the other tables
  `utf8mb4_unicode_ci`. `general_ci` keeps the sort order of the participant list the bot writes;
  `unicode_ci` would reorder it.
* `timestamp` columns end in January 2038 on MariaDB 10.6 (ToolsDB). MariaDB 11.5 and later extend
  `timestamp` to 2106, so this is left to the ToolsDB upgrade.
* `cf_timestamp` and the other timestamps hold the wiki's local time (CET/CEST) as written in the
  signatures, not UTC.
* Deleted confirmations (`cf_was_deleted = 1`) are counted inconsistently: the participant list on the
  wiki, the start page and the statistics leave them out, while the verification (`add_confirmation`),
  the minimum of 3 confirmations for a confirmer (`get_cf_count_by_confirmed`) and `/users` count them.
  This is known and accepted: there are only 10 deleted confirmations (the latest from 2012), and counting
  them or not changes no user's verification status.
* The daily dumps contain the whole database, including hidden users, banned users and admin comments.
  They are encrypted (`openssl enc -aes-256-cbc -pbkdf2 -iter 200000`); the key is known to the
  maintainers and stored in `~/.sql-dump-key` on Toolforge.
