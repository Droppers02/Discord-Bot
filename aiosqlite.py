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
    def __init__(self, connection: "Connection", cursor: psycopg.AsyncCursor[Any], lastrowid: Optional[int] = None):
        self._connection = connection
        self._cursor = cursor
        self._lastrowid = lastrowid

    @property
    def rowcount(self) -> int:
        return self._cursor.rowcount

    @property
    def lastrowid(self) -> Optional[int]:
        return self._lastrowid

    async def fetchone(self):
        row = await self._cursor.fetchone()
        return _normalize_row(row)

    async def fetchall(self):
        rows = await self._cursor.fetchall()
        return [_normalize_row(row) for row in rows]

    async def close(self):
        await self._cursor.close()

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        await self.close()


class _ExecuteOperation:
    def __init__(self, connection: "Connection", query: str, params: tuple[Any, ...]):
        self._connection = connection
        self._query = query
        self._params = params
        self._cursor: Optional[Cursor] = None

    async def _execute(self) -> Cursor:
        self._cursor = await self._connection._execute(self._query, self._params)
        return self._cursor

    def __await__(self):
        return self._execute().__await__()

    async def __aenter__(self) -> Cursor:
        if self._cursor is None:
            await self._execute()
        return self._cursor

    async def __aexit__(self, exc_type, exc, tb):
        if self._cursor is not None:
            await self._cursor.close()
            self._cursor = None


class Connection:
    def __init__(self, dsn: str):
        self.dsn = dsn
        self._connection: Optional[psycopg.AsyncConnection[Any]] = None

    async def _ensure_connection(self) -> psycopg.AsyncConnection[Any]:
        if self._connection is None:
            self._connection = await psycopg.AsyncConnection.connect(self.dsn, row_factory=tuple_row)
        return self._connection

    def __await__(self):
        return self._ensure_connection().__await__()

    async def __aenter__(self):
        await self._ensure_connection()
        return self

    async def __aexit__(self, exc_type, exc, tb):
        if self._connection is None:
            return
        try:
            if exc_type is None:
                await self._connection.commit()
            else:
                await self._connection.rollback()
        finally:
            await self._connection.close()
            self._connection = None

    async def _fetch_lastrowid(self, connection: psycopg.AsyncConnection[Any]) -> Optional[int]:
        try:
            async with connection.cursor() as cursor:
                await cursor.execute("SELECT LASTVAL()")
                row = await cursor.fetchone()
                return row[0] if row else None
        except psycopg.Error:
            return None

    async def _execute(self, query: str, params: tuple[Any, ...] = ()) -> Cursor:
        connection = await self._ensure_connection()
        translated_query = translate_query(query)
        cursor = connection.cursor()
        await cursor.execute(translated_query, params)

        lastrowid = None
        if is_insert_query(translated_query):
            lastrowid = await self._fetch_lastrowid(connection)

        return Cursor(self, cursor, lastrowid=lastrowid)

    def execute(self, query: str, params: tuple[Any, ...] = ()) -> _ExecuteOperation:
        return _ExecuteOperation(self, query, normalize_params(params))

    async def executemany(self, query: str, seq_of_params):
        connection = await self._ensure_connection()
        translated_query = translate_query(query)
        async with connection.cursor() as cursor:
            await cursor.executemany(
                translated_query,
                [normalize_params(params) for params in seq_of_params],
            )

    async def commit(self):
        connection = await self._ensure_connection()
        await connection.commit()

    async def rollback(self):
        connection = await self._ensure_connection()
        await connection.rollback()

    async def close(self):
        if self._connection is not None:
            await self._connection.close()
            self._connection = None


def connect(dsn: str) -> Connection:
    return Connection(dsn)