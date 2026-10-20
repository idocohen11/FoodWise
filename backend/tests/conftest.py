from unittest.mock import MagicMock

import pytest

from backend.app import create_app


@pytest.fixture
def connector(monkeypatch):
    connect = MagicMock()
    connection = connect.return_value
    connection.in_transaction = True
    connection.cursor.return_value.fetchone.return_value = {"user_id": 7}
    connection.cursor.return_value.fetchall.return_value = []
    connection.cursor.return_value.rowcount = 1
    monkeypatch.setattr("backend.db.mysql.connector.connect", connect)
    return connect


@pytest.fixture
def app(connector):
    return create_app({"TESTING": True, "DB_PASSWORD": "test-only-secret"})


@pytest.fixture
def client(app):
    return app.test_client()
