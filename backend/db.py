import asyncio
import logging
import os
import re
from collections.abc import AsyncIterator, Sequence
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Protocol, runtime_checkable

import aiosqlite
import asyncpg  # type: ignore[import-untyped]

logger = logging.getLogger(__name__)

# Local single-user mode: SQLite + in-process queue. The default for a personal,
# self-hosted install. Set LOCAL_MODE=false (cloud/multi-user) to use Postgres.
# This is the single source of truth for the flag; other modules import it here.
LOCAL_MODE = (os.getenv("LOCAL_MODE") or "true").strip().lower() in ("1", "true", "yes")

# Postgres is only required when NOT in local mode.
DATABASE_URL: str | None = os.getenv("DATABASE_URL") or None

# Shared SQLite file. The renderer (better-sqlite3) opens the SAME file, so the
# path must resolve identically across processes. start.sh exports VIBECUT_DB_PATH.
_DEFAULT_DB_PATH = Path(__file__).resolve().parents[1] / "backend" / "data" / "local.db"
DB_PATH = Path(os.getenv("VIBECUT_DB_PATH") or _DEFAULT_DB_PATH)

_SCHEMA_PATH = Path(__file__).resolve().parents[1] / "migrations" / "sqlite" / "schema.sql"


@runtime_checkable
class Row(Protocol):
    """Minimal mapping row interface: supports ``row["column"]`` access."""

    def __getitem__(self, key: str) -> Any: ...


class DbConn(Protocol):
    """The async DB surface used by the route handlers.

    asyncpg's connection already satisfies this; ``SqliteConn`` is a thin
    adapter that maps the same calls onto an ``aiosqlite.Connection``.
    """

    async def fetch(self, sql: str, *args: Any) -> list[Any]: ...

    async def fetchrow(self, sql: str, *args: Any) -> Any | None: ...

    async def fetchval(self, sql: str, *args: Any) -> Any: ...

    async def execute(self, sql: str, *args: Any) -> str: ...

    def transaction(self) -> Any: ...


_PLACEHOLDER_RE = re.compile(r"\$(\d+)")
# PG-only type casts that SQLite does not understand. Stripped before execution.
_CAST_RE = re.compile(r"::(?:jsonb|json|uuid|int|integer|bigint|text|float|bool|boolean)\b")


def _translate_sql(sql: str, args: Sequence[Any]) -> tuple[str, list[Any]]:
    """Translate asyncpg ``$N`` placeholders to SQLite ``?`` and remap args.

    asyncpg positional params can repeat or reorder (e.g. ``$1 ... $1``), so we
    rebuild the argument list in the order the placeholders appear rather than
    blindly substituting. PG-only type casts are also stripped.
    """
    new_args: list[Any] = []

    def _sub(match: re.Match[str]) -> str:
        index = int(match.group(1)) - 1
        if index < 0 or index >= len(args):
            raise IndexError(
                f"placeholder ${index + 1} has no matching argument "
                f"(got {len(args)} args)"
            )
        new_args.append(args[index])
        return "?"

    translated = _PLACEHOLDER_RE.sub(_sub, sql)
    translated = _CAST_RE.sub("", translated)
    return translated, new_args


def _status_from_sql(sql: str, rowcount: int) -> str:
    """Build a Postgres-style command status tag so callers comparing against
    ``"DELETE 0"`` keep working under SQLite."""
    verb = sql.lstrip().split(None, 1)[0].upper() if sql.strip() else ""
    if verb == "DELETE":
        return f"DELETE {rowcount}"
    if verb == "UPDATE":
        return f"UPDATE {rowcount}"
    if verb == "INSERT":
        return f"INSERT 0 {rowcount}"
    return verb


class SqliteConn:
    """Adapter exposing the :class:`DbConn` surface over an aiosqlite connection.

    A single connection is shared for the whole process and access is serialized
    by an :class:`asyncio.Lock` held for the duration of each ``acquire()`` block,
    so transactions never interleave.
    """

    def __init__(self, conn: aiosqlite.Connection) -> None:
        self._conn = conn

    async def fetch(self, sql: str, *args: Any) -> list[aiosqlite.Row]:
        translated, params = _translate_sql(sql, args)
        async with self._conn.execute(translated, params) as cursor:
            return list(await cursor.fetchall())

    async def fetchrow(self, sql: str, *args: Any) -> aiosqlite.Row | None:
        translated, params = _translate_sql(sql, args)
        async with self._conn.execute(translated, params) as cursor:
            return await cursor.fetchone()

    async def fetchval(self, sql: str, *args: Any) -> Any:
        translated, params = _translate_sql(sql, args)
        async with self._conn.execute(translated, params) as cursor:
            row = await cursor.fetchone()
        if row is None:
            return None
        return row[0]

    async def execute(self, sql: str, *args: Any) -> str:
        translated, params = _translate_sql(sql, args)
        async with self._conn.execute(translated, params) as cursor:
            rowcount = cursor.rowcount
        await self._conn.commit()
        return _status_from_sql(sql, rowcount if rowcount >= 0 else 0)

    @asynccontextmanager
    async def transaction(self) -> AsyncIterator[None]:
        await self._conn.execute("BEGIN")
        try:
            yield
        except BaseException:
            await self._conn.rollback()
            raise
        else:
            await self._conn.commit()

    async def executescript(self, script: str) -> None:
        await self._conn.executescript(script)
        await self._conn.commit()


class SqlitePool:
    """Minimal pool-shaped facade over a single shared aiosqlite connection."""

    def __init__(self) -> None:
        self._conn: aiosqlite.Connection | None = None
        self._lock = asyncio.Lock()
        self._open_lock = asyncio.Lock()

    async def _get_conn(self) -> aiosqlite.Connection:
        if self._conn is None:
            async with self._open_lock:
                if self._conn is None:
                    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
                    conn = await aiosqlite.connect(DB_PATH)
                    conn.row_factory = aiosqlite.Row
                    await conn.execute("PRAGMA journal_mode=WAL")
                    await conn.execute("PRAGMA foreign_keys=ON")
                    await conn.execute("PRAGMA busy_timeout=5000")
                    await conn.commit()
                    self._conn = conn
                    logger.info("SQLite connection opened at %s", DB_PATH)
        return self._conn

    @asynccontextmanager
    async def acquire(self) -> AsyncIterator[SqliteConn]:
        conn = await self._get_conn()
        async with self._lock:
            yield SqliteConn(conn)

    async def close(self) -> None:
        if self._conn is not None:
            await self._conn.close()
            self._conn = None
            logger.info("SQLite connection closed")


_pg_pool: asyncpg.Pool | None = None
_sqlite_pool: SqlitePool | None = None


async def get_db_pool() -> Any:
    """Return the shared connection pool for the active backend.

    The returned object exposes ``.acquire()`` as an async context manager
    yielding a :class:`DbConn`. In LOCAL_MODE this is SQLite; otherwise asyncpg.
    """
    if LOCAL_MODE:
        global _sqlite_pool
        if _sqlite_pool is None:
            _sqlite_pool = SqlitePool()
        return _sqlite_pool

    global _pg_pool
    if _pg_pool is None:
        if DATABASE_URL is None:
            raise ValueError("DATABASE_URL is not set (required when LOCAL_MODE=false)")
        ssl = "require" if os.getenv("DATABASE_SSL") == "true" else None
        try:
            _pg_pool = await asyncpg.create_pool(
                DATABASE_URL,
                ssl=ssl,
                min_size=2,
                max_size=20,
                command_timeout=30,
            )
            logger.info("Database pool created")
        except Exception:
            logger.exception("Failed to create database pool")
            raise
    return _pg_pool


async def init_local_schema() -> None:
    """Create the SQLite schema on first boot. No-op when not in LOCAL_MODE."""
    if not LOCAL_MODE:
        return
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    schema_sql = _SCHEMA_PATH.read_text(encoding="utf-8")
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        await conn.executescript(schema_sql)
    logger.info("SQLite schema initialized at %s", DB_PATH)


async def close_db_pool() -> None:
    """Gracefully close whichever backend pool is active on shutdown."""
    global _pg_pool, _sqlite_pool
    if _pg_pool is not None:
        await _pg_pool.close()
        _pg_pool = None
        logger.info("Database pool closed")
    if _sqlite_pool is not None:
        await _sqlite_pool.close()
        _sqlite_pool = None
