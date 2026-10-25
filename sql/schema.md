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
```

### `user`: participants

| Column | Type | Meaning |
|--------|------|---------|
| `user_id` | `int unsigned`, unique | MediaWiki user id on dewiki. The bot looks it up in the replica when it adds the user, so only existing accounts can join. |
| `user_name` | `varchar(255)`, unique | User name as written in the request. Renames on the wiki are not followed automatically. |
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

## Replica tables used (`dewiki_p`)

* `user` (`user_id`, `user_name`): `Database.get_mw_user_id`, used by the bot before adding a user.
* `block_target` (`bt_user`): `Database.user_blocked`. The result is currently not displayed.

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
DROP TABLE IF EXISTS `confirmation`;
DROP TABLE IF EXISTS `stats_confirmations_by_month`;
DROP TABLE IF EXISTS `user`;
```

```sql
CREATE TABLE `user` (
  `user_id` int(11) unsigned NOT NULL,
  `user_name` varchar(255) NOT NULL,
  `user_comment` text DEFAULT NULL,
  `user_participates_since` timestamp NULL DEFAULT NULL,
  `user_verified_since` timestamp NULL DEFAULT NULL,
  `user_last_update` timestamp NOT NULL DEFAULT current_timestamp(),
  `user_is_hidden` int(1) unsigned NOT NULL DEFAULT 0 COMMENT 'This filed toggles if the participant wants to leave PB or not. It is not the right place for uncovered sockpuppets.',
  `user_was_banned` int(1) unsigned NOT NULL DEFAULT 0 COMMENT 'This filed toggles if the participant was ''deleted''/banned from PB or not. It is the right place for uncovered sockpuppets, but not for users were banned on WP.',
  UNIQUE KEY `user_name` (`user_name`),
  UNIQUE KEY `user_id` (`user_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb3 COLLATE=utf8mb3_general_ci;
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

## Known issues

* `user` still uses `utf8mb3`, while the connection and the other tables use `utf8mb4`. User names
  with 4-byte characters (e.g. emoji) cannot be stored.
* `timestamp` columns end in January 2038. `datetime` would avoid that.
* The daily dumps contain the whole database, including hidden users, banned users and admin comments.
  They are encrypted (`openssl enc -aes-256-cbc -pbkdf2 -iter 200000`); the key is known to the
  maintainers and stored in `~/.sql-dump-key` on Toolforge.
