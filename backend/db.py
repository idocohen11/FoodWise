"""The only module that opens MySQL connections or executes SQL."""

from contextlib import contextmanager

import mysql.connector
from flask import current_app

from backend.errors import DatabaseError


def get_connection():
    config = current_app.config
    if config["DB_PASSWORD"] is None:
        raise DatabaseError("DB_PASSWORD is not configured.")
    return mysql.connector.connect(
        host=config["DB_HOST"],
        port=config["DB_PORT"],
        database=config["DB_NAME"],
        user=config["DB_USER"],
        password=config["DB_PASSWORD"],
        connection_timeout=config["DB_CONNECT_TIMEOUT"],
        charset="utf8mb4",
        autocommit=False,
    )


class Session:
    def __init__(self, connection):
        self.connection = connection

    @contextmanager
    def cursor(self, sql, params):
        cursor = self.connection.cursor(dictionary=True)
        try:
            cursor.execute(sql, params)
            yield cursor
        finally:
            cursor.close()

    def one(self, sql, params=()):
        with self.cursor(sql, params) as cursor:
            return cursor.fetchone()

    def all(self, sql, params=()):
        with self.cursor(sql, params) as cursor:
            return cursor.fetchall()

    def execute(self, sql, params=()):
        with self.cursor(sql, params) as cursor:
            return cursor.rowcount


@contextmanager
def session(write=False):
    connection = None
    try:
        connection = get_connection()
        yield Session(connection)
        if write:
            connection.commit()
        else:
            connection.rollback()  # End the read snapshot explicitly.
    except mysql.connector.Error as exc:
        # Do not log connector messages: they may contain credentials or SQL.
        current_app.logger.error("Database operation failed (errno=%s)", exc.errno)
        raise DatabaseError("Database operation failed.") from None
    finally:
        if connection is not None:
            try:
                # Also rolls back any partial write when the service raises.
                if connection.in_transaction:
                    connection.rollback()
            except mysql.connector.Error:
                current_app.logger.error("Database rollback failed.")
            finally:
                try:
                    connection.close()
                except mysql.connector.Error:
                    current_app.logger.error("Database connection cleanup failed.")
