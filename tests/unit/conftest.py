"""
Fixtures for the unit tests: the Flask app runs against an in-memory fake
database, so no MariaDB server is needed.
"""
import pytest

import app as webapp
from tests.unit.fake_db import FakeDatabase


@pytest.fixture
def fake_db_class(monkeypatch):
    FakeDatabase.instances = []
    monkeypatch.setattr(webapp, 'Database', FakeDatabase)
    return FakeDatabase


@pytest.fixture
def client(fake_db_class):
    webapp.app.config['TESTING'] = True
    with webapp.app.test_client() as test_client:
        yield test_client


@pytest.fixture
def production_client(fake_db_class):
    """A client that turns unhandled exceptions into HTTP 500 like in production."""
    webapp.app.config['TESTING'] = False
    try:
        with webapp.app.test_client() as test_client:
            yield test_client
    finally:
        webapp.app.config['TESTING'] = True
