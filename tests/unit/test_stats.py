"""Tests for the statistics helpers of api.Database (no database connection needed)."""
import datetime as dt

import api


def make_db():
    # bypass __init__, which would connect to the database
    return api.Database.__new__(api.Database)


def test_generate_months_starts_with_project_start_and_ends_today():
    months, year_months = make_db()._generate_months_for_stats()
    today = dt.date.today()
    assert year_months[0] == '2008-02'
    assert year_months[-1] == today.strftime('%Y-%m')
    assert months[2008] == 11
    assert months[2009] == 12
    assert months[today.year] == today.month
    assert sum(months.values()) == len(year_months)
    assert len(set(year_months)) == len(year_months)


def test_prepare_stats_counts_sums_and_totals():
    year_months = ['2008-02', '2008-03', '2009-01']
    rows = [('2008-02', 0, 3), ('2008-02', 1, 2), ('2008-03', 1, 4), ('2009-01', 0, 1)]
    counts, sums, totals = make_db()._prepare_stats(year_months, rows)
    assert counts == {'2008-02': {0: 3, 1: 2}, '2008-03': {1: 4}, '2009-01': {0: 1}}
    assert sums == {2008: [3, 6], 2009: [1, 0]}
    assert totals == [4, 6]


def test_prepare_stats_keeps_months_without_data():
    counts, sums, totals = make_db()._prepare_stats(['2008-02', '2008-03'], [])
    assert counts == {'2008-02': {}, '2008-03': {}}
    assert sums == {}
    assert totals == [0, 0]


def test_confirmations_per_day():
    days = (dt.date.today() - dt.date(2008, 2, 8)).days
    assert make_db().get_confirmations_per_day(days * 2) == 2.0
    assert make_db().get_confirmations_per_day(0) == 0.0


def test_fetch_stats_combines_both_data_sets():
    db = make_db()
    db._get_stats_confirmations_by_month = lambda: [('2008-02', 0, 5)]
    db._get_users_by_month = lambda: [('2008-02', 0, 1), ('2008-02', 1, 2)]
    data = db.fetch_stats()
    assert data['year_months'][0] == '2008-02'
    assert data['confirmations']['totals'] == [5, 0]
    assert data['users']['counts']['2008-02'] == {0: 1, 1: 2}
    assert data['users']['sums'][2008] == [1, 2]
