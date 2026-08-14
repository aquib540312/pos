from __future__ import annotations

import sqlite3
import threading
from typing import Protocol

try:
    from sqlcipher3 import dbapi2 as sqlcipher

    _SQLCIPHER_AVAILABLE = True
    # sqlcipher3 defines its own exception hierarchy -- sqlcipher3.dbapi2
    # .DatabaseError is *not* a subclass of sqlite3.DatabaseError despite
    # the identical name (verified directly), so both have to be caught.
    # A wrong key surfaces inconsistently depending on which statement
    # first touches an undecryptable page: a plain SELECT raises
    # sqlcipher's DatabaseError, but CREATE TABLE IF NOT EXISTS (which
    # inspects sqlite_master first) can instead raise a raw MemoryError --
    # both mean the same thing here, so both are treated as "bad key."
    _DB_OPEN_ERRORS: tuple[type[Exception], ...] = (sqlite3.DatabaseError, sqlcipher.DatabaseError, MemoryError)
except ImportError:  # pragma: no cover - exercised in CI where the wheel is installed
    _SQLCIPHER_AVAILABLE = False
    _DB_OPEN_ERRORS = (sqlite3.DatabaseError, MemoryError)


class ConnectionFactory(Protocol):
    def connect(self, db_path: str, encryption_key: str) -> sqlite3.Connection: ...


def _escape_sql_string_literal(value: str) -> str:
    """PRAGMA statements don't accept `?` bound parameters in SQLite (it's
    a syntax error, verified against sqlcipher3 directly) -- the key has
    to be interpolated as a SQL string literal, so single quotes must be
    doubled the way any SQL string literal escapes them."""
    return value.replace("'", "''")


class SqlCipherConnectionFactory:
    """Real encryption at rest via SQLCipher (AES-256-CBC + HMAC), the
    de facto standard for encrypted SQLite -- not an application-level
    bolt-on. Handing it a plain passphrase (rather than a raw `x'..'` key)
    lets SQLCipher do its own salted PBKDF2-HMAC-SHA512 key derivation
    internally, with the salt stored in the first 16 bytes of the
    database file itself; that's its normal, fully-supported mode, so
    there's no key-management scheme of our own to get wrong.

    A wrong key isn't detected at `PRAGMA key` time (SQLCipher can't tell
    "wrong key" apart from "not yet decrypted") -- it surfaces as a
    `sqlite3.DatabaseError: file is not a database` on the first real
    statement, which `open_connection` below turns into a clear error.
    """

    def connect(self, db_path: str, encryption_key: str) -> sqlite3.Connection:
        if not _SQLCIPHER_AVAILABLE:
            raise RuntimeError(
                "sqlcipher3 is not installed, so the local database cannot be "
                "encrypted at rest. Run `pip install sqlcipher3`, or -- only if "
                "you understand and accept the tradeoff -- construct the agent with "
                "PlaintextConnectionFactory() and allow_unencrypted_storage=True."
            )
        conn = sqlcipher.connect(db_path, check_same_thread=False)
        conn.execute(f"PRAGMA key = '{_escape_sql_string_literal(encryption_key)}'")
        conn.execute("PRAGMA foreign_keys = ON")
        # sqlcipher3's Cursor/Row types are distinct classes from the
        # stdlib sqlite3 module's -- sqlite3.Row rejects a sqlcipher3
        # Cursor outright (TypeError), so it needs sqlcipher3's own Row.
        conn.row_factory = sqlcipher.Row
        return conn


class PlaintextConnectionFactory:
    """No encryption. Only for local development/tests, and only when the
    caller has explicitly opted in (see `open_connection`'s
    `allow_unencrypted` guard) -- never the implicit default."""

    def connect(self, db_path: str, encryption_key: str) -> sqlite3.Connection:
        conn = sqlite3.connect(db_path, check_same_thread=False)
        conn.execute("PRAGMA foreign_keys = ON")
        conn.row_factory = sqlite3.Row
        return conn


_SCHEMA_STATEMENTS = [
    """
    CREATE TABLE IF NOT EXISTS products (
        id TEXT PRIMARY KEY,
        sku TEXT NOT NULL,
        barcode TEXT,
        name TEXT NOT NULL,
        description TEXT,
        category_id TEXT,
        hsn_code_id TEXT,
        uom_id TEXT,
        mrp REAL NOT NULL,
        sale_price REAL NOT NULL,
        purchase_price REAL NOT NULL,
        tracks_batches INTEGER NOT NULL,
        tracks_serials INTEGER NOT NULL,
        tracks_expiry INTEGER NOT NULL,
        reorder_level REAL NOT NULL,
        is_combo INTEGER NOT NULL,
        is_active INTEGER NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS customers (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        phone TEXT,
        email TEXT,
        gstin TEXT,
        state_code TEXT,
        address TEXT,
        is_credit_customer INTEGER NOT NULL,
        credit_limit REAL NOT NULL,
        credit_balance REAL NOT NULL,
        loyalty_points_balance REAL NOT NULL,
        is_active INTEGER NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS stock_items (
        id TEXT PRIMARY KEY,
        warehouse_id TEXT NOT NULL,
        product_id TEXT NOT NULL,
        batch_id TEXT,
        quantity_on_hand REAL NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS offline_sales (
        client_operation_id TEXT PRIMARY KEY,
        occurred_at TEXT NOT NULL,
        branch_id TEXT NOT NULL,
        warehouse_id TEXT NOT NULL,
        customer_id TEXT,
        items_json TEXT NOT NULL,
        payments_json TEXT NOT NULL,
        is_credit_sale INTEGER NOT NULL,
        coupon_code TEXT,
        status TEXT NOT NULL,
        server_invoice_id TEXT,
        server_conflict_id TEXT,
        error_detail TEXT,
        created_at TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS conflicts (
        id TEXT PRIMARY KEY,
        client_operation_id TEXT NOT NULL,
        conflict_type TEXT NOT NULL,
        details_json TEXT NOT NULL,
        status TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS sync_cursors (
        entity_type TEXT PRIMARY KEY,
        cursor_value INTEGER NOT NULL DEFAULT 0
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS audit_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp TEXT NOT NULL,
        action TEXT NOT NULL,
        detail_json TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS sync_journal (
        id TEXT PRIMARY KEY,
        cycle_type TEXT NOT NULL,
        started_at TEXT NOT NULL,
        finished_at TEXT,
        success INTEGER
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS terminal_meta (
        key TEXT PRIMARY KEY,
        value TEXT NOT NULL
    )
    """,
]


def create_schema(conn: sqlite3.Connection) -> None:
    """Every statement is `CREATE TABLE IF NOT EXISTS` -- safe to call on
    every startup regardless of whether the file is brand new or has
    years of history, no separate "first run" branch needed."""
    for statement in _SCHEMA_STATEMENTS:
        conn.execute(statement)
    conn.commit()


class LocalDatabase:
    """Owns the one encrypted connection a terminal process uses.
    `check_same_thread=False` plus this lock is what lets the background
    worker thread and a foreground status/CLI call share one connection
    safely -- SQLite itself serializes writes at the file level regardless,
    this just prevents two Python threads from interleaving statements on
    the same cursor."""

    def __init__(
        self,
        db_path: str,
        encryption_key: str,
        connection_factory: ConnectionFactory | None = None,
        allow_unencrypted: bool = False,
    ):
        if connection_factory is None:
            if not encryption_key and not allow_unencrypted:
                raise ValueError(
                    "db_encryption_key is required (or pass allow_unencrypted_storage=True "
                    "explicitly, e.g. in tests, to opt out of encryption-at-rest)."
                )
            connection_factory = PlaintextConnectionFactory() if allow_unencrypted else SqlCipherConnectionFactory()
        self._lock = threading.RLock()
        try:
            self.conn = connection_factory.connect(db_path, encryption_key)
            create_schema(self.conn)
        except _DB_OPEN_ERRORS as exc:
            raise ValueError(
                "Could not open the local database -- this almost always means the "
                "encryption key is wrong (a corrupt file gives the same error, but is "
                "far less likely)."
            ) from exc

    def cursor(self) -> sqlite3.Cursor:
        return self.conn.cursor()

    def commit(self) -> None:
        self.conn.commit()

    def close(self) -> None:
        self.conn.close()

    @property
    def lock(self) -> threading.RLock:
        return self._lock
