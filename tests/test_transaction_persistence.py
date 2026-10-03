import sqlite3
from contextlib import contextmanager

import pytest
from body_hash import calculate_body_hash
from nodes.transaction_repository import TransactionRepository
from templates.template import TransactionAnalysis
from tools import tools as tool_module


class SQLiteCursorAdapter:
    def __init__(self, cursor):
        self.cursor = cursor

    def execute(self, query, params=()):
        self.cursor.execute(query.replace("%s", "?").replace("NOW()", "CURRENT_TIMESTAMP"), params)

    def fetchone(self):
        return self.cursor.fetchone()

    @property
    def rowcount(self):
        return self.cursor.rowcount


class SQLiteConnectionAdapter:
    def __init__(self, connection):
        self.connection = connection

    @contextmanager
    def cursor(self):
        cursor = self.connection.cursor()
        try:
            yield SQLiteCursorAdapter(cursor)
        finally:
            cursor.close()


@pytest.fixture
def database(monkeypatch):
    """Exercise persistence SQL offline; this does not validate PostgreSQL concurrency."""
    connection = sqlite3.connect(":memory:")
    connection.executescript(
        """
        CREATE TABLE gastostracker (
            messageid TEXT UNIQUE,
            messagebody TEXT,
            messagedate TEXT,
            body_hash TEXT,
            vendor TEXT,
            amount REAL,
            category TEXT,
            valid BOOLEAN,
            description TEXT,
            analyzed_at TEXT
        );
        CREATE UNIQUE INDEX gastostracker_body_hash_unique
        ON gastostracker(body_hash) WHERE body_hash IS NOT NULL;
        """
    )

    @contextmanager
    def connect(*args, **kwargs):
        with connection:
            yield SQLiteConnectionAdapter(connection)

    monkeypatch.setattr("psycopg.connect", connect)
    monkeypatch.setattr(tool_module, "db_url", "test")
    yield connection
    connection.close()


def email_record(message_id="one", body="Acme purchase 12.50"):
    return {"id": message_id, "content": body, "date": "2026-01-01"}


def result_for(record, valid=True):
    return {
        "email_id": record["id"],
        "status": "success",
        "transaction": TransactionAnalysis(
            vendor="Acme", amount=12.5, category="shopping", valid=valid, description="Purchase"
        ),
    }


def add_raw(database, record, hashed=True):
    database.execute(
        "INSERT INTO gastostracker(messageid,messagebody,messagedate,body_hash) VALUES (?,?,?,?)",
        (
            record["id"],
            record["content"],
            record["date"],
            calculate_body_hash(record["content"]) if hashed else None,
        ),
    )
    database.commit()


def test_raw_hashed_email_is_not_duplicate_and_receives_outputs(database):
    record = email_record()
    add_raw(database, record)
    assert not tool_module.check_duplicate_transaction_email.invoke(
        {"message_body": record["content"]}
    )["is_duplicate"]

    counts = TransactionRepository("test").save_results([record], [result_for(record)])

    assert counts == {"saved": 1, "skipped": 0, "failed": 0}
    assert database.execute(
        "SELECT messageid, vendor, amount, category, valid, description FROM gastostracker"
    ).fetchone() == ("one", "Acme", 12.5, "shopping", 1, "Purchase")
    assert database.execute("SELECT analyzed_at FROM gastostracker").fetchone()[0]
    assert tool_module.check_duplicate_transaction_email.invoke(
        {"message_body": record["content"]}
    )["is_duplicate"]


def test_completed_output_is_not_overwritten_by_duplicate_placeholder(database):
    record = email_record()
    repository = TransactionRepository("test")
    repository.save_results([record], [result_for(record)])
    duplicate = result_for(record)
    duplicate["transaction"] = TransactionAnalysis(
        vendor="",
        amount=0,
        category="other",
        valid=False,
        description="Duplicate transaction email body.",
    )

    assert repository.save_results([record], [duplicate]) == {
        "saved": 0,
        "skipped": 1,
        "failed": 0,
    }
    assert database.execute("SELECT vendor, amount FROM gastostracker").fetchone() == ("Acme", 12.5)


def test_legacy_duplicate_id_does_not_block_canonical_row_update(database):
    canonical = email_record()
    alias = email_record("two")
    add_raw(database, canonical)
    add_raw(database, alias, hashed=False)

    counts = TransactionRepository("test").save_results(
        [alias, canonical], [result_for(alias), result_for(canonical)]
    )

    assert counts == {"saved": 1, "skipped": 1, "failed": 0}
    assert database.execute("SELECT COUNT(*) FROM gastostracker").fetchone()[0] == 2
    assert (
        database.execute("SELECT vendor FROM gastostracker WHERE messageid = 'one'").fetchone()[0]
        == "Acme"
    )


def test_same_body_with_new_message_id_does_not_create_second_transaction(database):
    first = email_record()
    second = email_record("two", "  ACME purchase 12.50  ")
    counts = TransactionRepository("test").save_results(
        [first, second], [result_for(first), result_for(second)]
    )
    assert counts == {"saved": 1, "skipped": 1, "failed": 0}
    assert database.execute("SELECT COUNT(*) FROM gastostracker").fetchone()[0] == 1


def test_analysis_failure_leaves_raw_email_retryable(database):
    record = email_record()
    add_raw(database, record)
    counts = TransactionRepository("test").save_results(
        [record], [{"email_id": "one", "status": "failed", "error": "API unavailable"}]
    )
    assert counts == {"saved": 0, "skipped": 0, "failed": 1}
    assert database.execute("SELECT analyzed_at FROM gastostracker").fetchone()[0] is None


def test_invalid_but_completed_analysis_is_processed(database):
    record = email_record()
    TransactionRepository("test").save_results([record], [result_for(record, valid=False)])
    assert tool_module.check_duplicate_transaction_email.invoke(
        {"message_body": record["content"]}
    )["is_duplicate"]


def test_unrelated_constraint_failure_is_not_silently_counted_as_duplicate(database):
    original = email_record()
    repository = TransactionRepository("test")
    repository.save_results([original], [result_for(original)])
    changed = email_record(body="Different transaction")
    with pytest.raises(sqlite3.IntegrityError):
        repository.save_results([changed], [result_for(changed)])
