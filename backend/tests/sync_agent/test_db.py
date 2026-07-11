from __future__ import annotations

import pytest

from sync_agent.infrastructure.db import (
    _SQLCIPHER_AVAILABLE,
    LocalDatabase,
)


def test_schema_creation_is_idempotent(tmp_path):
    db_path = str(tmp_path / "agent.db")
    db1 = LocalDatabase(db_path=db_path, encryption_key="", allow_unencrypted=True)
    db1.close()
    # Reopening and re-running create_schema against the same file must
    # not raise (CREATE TABLE IF NOT EXISTS), even with existing data.
    db2 = LocalDatabase(db_path=db_path, encryption_key="", allow_unencrypted=True)
    db2.cursor().execute("INSERT INTO products (id, sku, name, mrp, sale_price, purchase_price, "
                         "tracks_batches, tracks_serials, tracks_expiry, reorder_level, is_combo, is_active) "
                         "VALUES ('p1','SKU1','Test',10,9,7,0,0,0,0,0,1)")
    db2.commit()
    db2.close()
    db3 = LocalDatabase(db_path=db_path, encryption_key="", allow_unencrypted=True)
    row = db3.cursor().execute("SELECT * FROM products WHERE id='p1'").fetchone()
    assert row["sku"] == "SKU1"
    db3.close()


def test_requires_encryption_key_unless_explicitly_opted_out(tmp_path):
    db_path = str(tmp_path / "agent.db")
    with pytest.raises(ValueError, match="db_encryption_key"):
        LocalDatabase(db_path=db_path, encryption_key="")


@pytest.mark.skipif(not _SQLCIPHER_AVAILABLE, reason="sqlcipher3-binary not installed")
def test_sqlcipher_roundtrip_with_correct_key(tmp_path):
    db_path = str(tmp_path / "encrypted.db")
    db = LocalDatabase(db_path=db_path, encryption_key="correct-horse-battery-staple")
    db.cursor().execute(
        "INSERT INTO products (id, sku, name, mrp, sale_price, purchase_price, tracks_batches, "
        "tracks_serials, tracks_expiry, reorder_level, is_combo, is_active) "
        "VALUES ('p1','SKU1','Test',10,9,7,0,0,0,0,0,1)"
    )
    db.commit()
    db.close()

    reopened = LocalDatabase(db_path=db_path, encryption_key="correct-horse-battery-staple")
    row = reopened.cursor().execute("SELECT * FROM products WHERE id='p1'").fetchone()
    assert row["sku"] == "SKU1"
    reopened.close()


@pytest.mark.skipif(not _SQLCIPHER_AVAILABLE, reason="sqlcipher3-binary not installed")
def test_sqlcipher_rejects_wrong_key(tmp_path):
    db_path = str(tmp_path / "encrypted2.db")
    db = LocalDatabase(db_path=db_path, encryption_key="the-real-key")
    db.cursor().execute(
        "INSERT INTO products (id, sku, name, mrp, sale_price, purchase_price, tracks_batches, "
        "tracks_serials, tracks_expiry, reorder_level, is_combo, is_active) "
        "VALUES ('p1','SKU1','Test',10,9,7,0,0,0,0,0,1)"
    )
    db.commit()
    db.close()

    with pytest.raises(ValueError, match="[Ee]ncrypt"):
        LocalDatabase(db_path=db_path, encryption_key="totally-wrong-key")


@pytest.mark.skipif(not _SQLCIPHER_AVAILABLE, reason="sqlcipher3-binary not installed")
def test_a_key_with_a_single_quote_is_handled_safely(tmp_path):
    """The PRAGMA key statement can't use bound parameters, so a
    passphrase containing a single quote is a real risk of either a SQL
    syntax error or, worse, injecting extra SQL -- verify it round-trips
    correctly instead."""
    db_path = str(tmp_path / "quote.db")
    key = "o'brien's-passphrase"
    db = LocalDatabase(db_path=db_path, encryption_key=key)
    db.cursor().execute("SELECT 1")
    db.close()

    reopened = LocalDatabase(db_path=db_path, encryption_key=key)
    reopened.cursor().execute("SELECT 1")
    reopened.close()


def test_plaintext_factory_used_when_allow_unencrypted(tmp_path):
    db_path = str(tmp_path / "plain.db")
    db = LocalDatabase(db_path=db_path, encryption_key="", allow_unencrypted=True)
    assert isinstance(db, LocalDatabase)
    db.close()

    # A plain sqlite3 connection (no sqlcipher) can open it directly,
    # proving it was never actually encrypted.
    import sqlite3

    conn = sqlite3.connect(db_path)
    conn.execute("SELECT 1 FROM products")
    conn.close()
