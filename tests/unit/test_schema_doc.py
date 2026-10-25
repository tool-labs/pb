"""The system tests take their DDL from sql/schema.md; make sure it is complete."""
import re

from tests.conftest import schema_sql


def test_schema_doc_contains_the_ddl_of_all_tables():
    sql = schema_sql()
    assert re.findall(r'CREATE TABLE `(\w+)`', sql) == ['user', 'confirmation', 'stats_confirmations_by_month']
    assert sql.index('DROP TABLE IF EXISTS `confirmation`') < sql.index('DROP TABLE IF EXISTS `user`')


def test_schema_doc_spells_out_null_for_timestamps():
    # without NULL, ToolsDB (explicit_defaults_for_timestamp=OFF) creates NOT NULL columns
    sql = schema_sql()
    assert '`user_participates_since` timestamp NULL DEFAULT NULL' in sql
    assert '`user_verified_since` timestamp NULL DEFAULT NULL' in sql
