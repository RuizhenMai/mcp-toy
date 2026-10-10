import sqlite3

import pytest

import db


@pytest.fixture
def path(tmp_path):
    p = str(tmp_path / "t.db")
    db.init_db(p)
    return p


def test_init_is_idempotent(path):
    db.init_db(path)


def test_wal_enabled(path):
    with db.connect(path) as conn:
        assert conn.execute("PRAGMA journal_mode").fetchone()[0] == "wal"


def test_key_is_stored_hashed_and_looked_up(path):
    aid = db.create_account("cus_1", "a@b.co", "secret-key", path)
    row = db.get_account_by_key("secret-key", path)
    assert row["id"] == aid and row["status"] == "active"
    assert row["api_key_hash"] != "secret-key"
    assert db.get_account_by_key("wrong", path) is None


def test_duplicate_customer_rejected(path):
    db.create_account("cus_1", None, "k1", path)
    with pytest.raises(sqlite3.IntegrityError):
        db.create_account("cus_1", None, "k2", path)


def test_set_status(path):
    db.create_account("cus_1", None, "k1", path)
    db.set_status("cus_1", "canceled", path)
    assert db.get_account_by_key("k1", path)["status"] == "canceled"


def test_send_log_is_idempotent_and_counted(path):
    aid = db.create_account("cus_1", None, "k1", path)
    db.record_send(aid, "evt_1", path)
    with pytest.raises(sqlite3.IntegrityError):
        db.record_send(aid, "evt_1", path)  # retry can't double-count
    db.record_send(aid, "evt_2", path)
    assert db.count_sends_since(aid, "2000-01-01 00:00:00", path) == 2
    assert db.count_sends_since(aid, "2999-01-01 00:00:00", path) == 0
    db.mark_reported("evt_1", path)
    with db.connect(path) as conn:
        n = conn.execute(
            "SELECT COUNT(*) FROM email_log WHERE reported_to_stripe = 1"
        ).fetchone()[0]
    assert n == 1


def test_unknown_account_cannot_log_sends(path):
    with pytest.raises(sqlite3.IntegrityError):
        db.record_send(999, "evt_x", path)
