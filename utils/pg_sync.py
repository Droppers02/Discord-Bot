from __future__ import annotations

from datetime import date, datetime, time
from typing import Any, Optional

import psycopg
from psycopg.rows import tuple_row

from utils.sql_compat import is_insert_query, normalize_params, translate_query


DatabaseError = psycopg.DatabaseError
Error = psycopg.Error
IntegrityError = psycopg.IntegrityError
OperationalError = psycopg.OperationalError
ProgrammingError = psycopg.ProgrammingError


def _normalize_value(value: Any) -> Any:
    if isinstance(value, (datetime, date, time)):
        return value.isoformat()
    return value


def _normalize_row(row):
    if row is None:
        return None
    return tuple(_normalize_value(value) for value in row)


class Cursor:
    def __init__(self, cursor: psycopg.Cursor[Any], lastrowid: Optional[int] = None):
        self._cursor = cursor
        self._lastrowid = lastrowid

    @property
    def rowcount(self) -> int:
        return self._cursor.rowcount

    @property
    def lastrowid(self) -> Optional[int]:
        return self._lastrowid

    def fetchone(self):
        row = self._cursor.fetchone()
        return _normalize_row(row)

    def fetchall(self):
        rows = self._cursor.fetchall()
        return [_normalize_row(row) for row in rows]

    def close(self):
        self._cursor.close()


class Connection:
    def __init__(self, dsn: str):
        self.dsn = dsn
        self._connection = psycopg.connect(dsn, row_factory=tuple_row)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        try:
            if exc_type is None:
                self._connection.commit()
            else:
                self._connection.rollback()
        finally:
            self._connection.close()

    def _fetch_lastrowid(self) -> Optional[int]:
        try:
            with self._connection.cursor() as cursor:
                cursor.execute("SELECT LASTVAL()")
                row = cursor.fetchone()
                return row[0] if row else None
        except psycopg.Error:
            return None

    def execute(self, query: str, params=()) -> Cursor:
        translated_query = translate_query(query)
        cursor = self._connection.cursor()
        cursor.execute(translated_query, normalize_params(params))

        lastrowid = None
        if is_insert_query(translated_query):
            lastrowid = self._fetch_lastrowid()

        return Cursor(cursor, lastrowid=lastrowid)

    def executemany(self, query: str, seq_of_params):
        translated_query = translate_query(query)
        with self._connection.cursor() as cursor:
            cursor.executemany(
                translated_query,
                [normalize_params(params) for params in seq_of_params],
            )

    def commit(self):
        self._connection.commit()

    def rollback(self):
        self._connection.rollback()

    def close(self):
        self._connection.close()


def connect(dsn: str) -> Connection:
    return Connection(dsn)