# pb – Wikipedia:Persönliche Bekanntschaften

[![Tests](https://github.com/tool-labs/pb/actions/workflows/tests.yml/badge.svg)](https://github.com/tool-labs/pb/actions/workflows/tests.yml)

Web interface and database for the German Wikipedia project
[Wikipedia:Persönliche Bekanntschaften](https://de.wikipedia.org/wiki/Wikipedia:Pers%C3%B6nliche_Bekanntschaften)
(WP:PB, "personal acquaintances"). Wikipedians confirm that they have met each other
in real life. A participant with three confirmations is *verified* and may then confirm
others. The tool runs on [Wikimedia Toolforge](https://wikitech.wikimedia.org/wiki/Help:Toolforge)
at **<https://pb.toolforge.org/>**.

Same projects in other languages:
[Czech](https://cs.wikipedia.org/wiki/Wikipedie:Osobn%C3%AD_zn%C3%A1mosti),
[Dutch](https://nl.wikipedia.org/wiki/Wikipedia:Ontmoete_Wikimedianen),
[French](https://fr.wikipedia.org/wiki/Wikip%C3%A9dia:Connaissances_personnelles).

## How it works

```
 de.wikipedia.org                      Toolforge
 ┌──────────────────────────────┐      ┌──────────────────────────────────────────────┐
 │ WP:PB/neue Einträge          │ read │ SpBot (tool "spbot", scheduled jobs)         │
 │ ({{…/neuer Benutzer}},       ├─────►│  pers-bek-to-db-bot.py  every 10 min         │
 │  {{…/neue Bestätigung}})     │      │  pers-bek-info-bot.py   daily                │
 │                              │◄─────┤      │ uses web/bot_api.py                   │
 │ participant lists,           │ edit │      ▼                                       │
 │ talk page notifications      │      │ ToolsDB  s51344__pb ◄─── web app (this repo) │
 └──────────────────────────────┘      │ wiki replica dewiki_p ◄┘  pb.toolforge.org   │
                                       └──────────────────────────────────────────────┘
```

1. Users add requests (new participant, new confirmation) to
   *Wikipedia:Persönliche Bekanntschaften/neue Einträge*.
2. The bot [SpBot](https://de.wikipedia.org/wiki/Benutzer:SpBot) transfers them into the
   database, removes them from the page and updates the participant lists on the wiki.
   Its scripts live in the [spbot repository](https://github.com/euku/spbot/tree/spbot/scripts/userscripts)
   (`pers-bek-*.py`), but the database code they use is `web/bot_api.py` in this repository.
3. This web app shows participants, confirmations and statistics. It only reads data;
   hiding or banning participants is done manually in the database.

## Repository layout

| Path | Content |
|------|---------|
| `web/app.py` | Flask app: routes and Jinja filters |
| `web/api.py` | `Database`: read access to ToolsDB and the dewiki replica, statistics |
| `web/bot_api.py` | `BotDatabase`: write access, used by SpBot |
| `web/config.py` | Configuration (Toolforge defaults, overridable by environment variables) |
| `web/templates/`, `web/static/` | HTML templates (German UI), CSS, jQuery + tablesorter |
| `web/sql-dumps/` | Daily database dumps offered for download (not in git) |
| `jobs/` | Toolforge jobs: `toolforge-jobs.yaml`, statistics update, dump creation and cleanup |
| `sql/schema.md` | Database schema: tables, meaning of the columns, DDL (matches production) |
| `tests/` | Unit and system tests, see below |
| `bot/README.txt` | Notes about the bot |

## Database

ToolsDB database `s51344__pb` (MariaDB 10.6):

* `user`: participants. `user_id` is the MediaWiki user id. `user_participates_since`,
  `user_verified_since` (set by the bot with the third confirmation), `user_is_hidden`
  (participant left the project, the name is no longer shown), `user_was_banned`
  (excluded, e.g. sockpuppets), `user_comment` (admin note).
* `confirmation`: `cf_user_id` confirmed `cf_confirmed_user_id` at `cf_timestamp`.
  `cf_was_deleted` marks revoked confirmations.
* `stats_confirmations_by_month`: precomputed statistics for the main page, refreshed hourly
  by `jobs/update_stats.py`.

The web app also reads `user` and `block_target` from the dewiki replica (`dewiki_p`).
Credentials come from `~/replica.pb-db.cnf` (a symlink to Toolforge's `replica.my.cnf`).

## Configuration

`web/config.py` has the Toolforge values as defaults. For tests and local development
they can be overridden by environment variables:

| Variable | Default |
|----------|---------|
| `PB_DB_CONF_FILE` | `~/replica.pb-db.cnf` (`[client]` `user`, `password`, `host` of the replica) |
| `PB_DB_HOST` | `tools.db.svc.wikimedia.cloud` |
| `PB_DB_PORT` | `3306` (used for both connections) |
| `PB_DB_NAME` | `s51344__pb` |
| `PB_REPLICA_DB_NAME` | `dewiki_p` |
| `PB_SQL_DUMP_FOLDER` | `/data/project/pb/www/python/src/sql-dumps` |

## Deployment on Toolforge

```bash
ssh login.toolforge.org
become pb
cd ~/pb && git pull                      # ~/www/python/src is a symlink to ~/pb/web
toolforge webservice python3.11 restart  # uwsgi, log: ~/uwsgi.log
toolforge jobs load ~/toolforge-jobs.yaml  # symlink to ~/pb/jobs/toolforge-jobs.yaml
```

* The webservice uses the venv `~/www/python/venv`, the jobs use `~/pyvenv`.
* Jobs (`jobs/toolforge-jobs.yaml`): `update-stats` (hourly), `create-database-dump`,
  `delete-old-database-dump` and `remove-old-logs` (daily). File logs go to `~/logs/`.
* Before `toolforge jobs load`, compare with `toolforge jobs dump`: `load` replaces all jobs of the tool.

## Tests

```bash
pip install -r web/requirements.txt -r tests/requirements.txt
python -m pytest tests/unit          # no database needed
```

* **Unit tests** (`tests/unit/`) test the filters, statistics helpers, configuration and all
  routes with an in-memory fake database (`tests/unit/fake_db.py`).
* **System tests** (`tests/system/`) need a MariaDB server. They create two scratch databases
  (`pb_systemtest`, `dewiki_systemtest`), load the DDL from `sql/schema.md` and a minimal replica schema,
  write test data through `BotDatabase` the same way SpBot does, start the web app as a
  separate HTTP server process and test it via HTTP. They also run `jobs/update_stats.py`.
  Without `PB_TEST_DB_HOST` they are skipped.

  ```bash
  docker run -d --name pb-test-db -e MARIADB_ROOT_PASSWORD=root -p 3306:3306 mariadb:10.6
  PB_TEST_DB_HOST=127.0.0.1 PB_TEST_DB_PASSWORD=root python -m pytest tests/system
  ```

  Settings: `PB_TEST_DB_HOST`, `PB_TEST_DB_PORT` (3306), `PB_TEST_DB_USER` (root),
  `PB_TEST_DB_PASSWORD`, `PB_TEST_DB_NAME`, `PB_TEST_REPLICA_DB_NAME`.
  **The test databases are dropped and recreated**, so never point the tests at ToolsDB
  (Wikimedia hosts are refused).
* Known bugs are marked with `@pytest.mark.xfail(strict=True)` and a reason. Once a bug is
  fixed, the test passes, pytest reports it as `XPASS` and fails, and the marker has to be removed.
* GitHub Actions (`.github/workflows/tests.yml`) runs all tests on every push and pull request
  against MariaDB 10.6 with Python 3.11, once with the versions deployed on Toolforge
  (`tests/constraints-production.txt`) and once with the latest releases.

## History

The first version was written by Ulli Purwin (interface) and Euku (bot). In 2011 Ireas and
Wiegels took over the interface, which later moved from a private server to Toolforge.

## License

[GNU Lesser General Public License v3](LICENSE) or later.
Bug reports and feature requests: [GitHub issues](https://github.com/tool-labs/pb/issues)
or [Wikipedia Diskussion:Persönliche Bekanntschaften](https://de.wikipedia.org/wiki/Wikipedia_Diskussion:Pers%C3%B6nliche_Bekanntschaften).
