from collections.abc import Iterable

import psycopg
from body_hash import calculate_body_hash
from config import get_database_url
from dotenv import load_dotenv

load_dotenv()


class TransactionRepository:
    def __init__(self, database_url: str | None = None) -> None:
        self.database_url = database_url or get_database_url()
        if not self.database_url:
            raise RuntimeError("DATABASE_URL is required to save transactions.")

    def initialize_schema(self) -> None:
        with psycopg.connect(self.database_url) as conn, conn.cursor() as cur:
            cur.execute(
                """
                    CREATE TABLE IF NOT EXISTS gastostracker (
                        messageid TEXT,
                        messagebody TEXT NOT NULL,
                        messagedate DATE,
                        body_hash TEXT,
                        vendor TEXT,
                        amount DOUBLE PRECISION,
                        category TEXT,
                        valid BOOLEAN,
                        description TEXT,
                        analyzed_at TIMESTAMPTZ
                    )
                    """
            )
            cur.execute("ALTER TABLE gastostracker ADD COLUMN IF NOT EXISTS body_hash TEXT")
            cur.execute("ALTER TABLE gastostracker ADD COLUMN IF NOT EXISTS vendor TEXT")
            cur.execute(
                "ALTER TABLE gastostracker ADD COLUMN IF NOT EXISTS amount DOUBLE PRECISION"
            )
            cur.execute("ALTER TABLE gastostracker ADD COLUMN IF NOT EXISTS category TEXT")
            cur.execute("ALTER TABLE gastostracker ADD COLUMN IF NOT EXISTS valid BOOLEAN")
            cur.execute("ALTER TABLE gastostracker ADD COLUMN IF NOT EXISTS description TEXT")
            cur.execute(
                "ALTER TABLE gastostracker ADD COLUMN IF NOT EXISTS analyzed_at TIMESTAMPTZ"
            )
            self._backfill_body_hashes(cur)
            cur.execute(
                """
                    CREATE UNIQUE INDEX IF NOT EXISTS gastostracker_body_hash_unique
                    ON gastostracker (body_hash)
                    WHERE body_hash IS NOT NULL
                    """
            )

    def _backfill_body_hashes(self, cursor: psycopg.Cursor) -> None:
        cursor.execute("SELECT messageid, messagebody FROM gastostracker WHERE body_hash IS NULL")
        for message_id, message_body in cursor.fetchall():
            if not message_body:
                continue

            body_hash = calculate_body_hash(message_body)
            cursor.execute(
                "SELECT 1 FROM gastostracker WHERE body_hash = %s LIMIT 1",
                (body_hash,),
            )
            if cursor.fetchone() is not None:
                continue

            cursor.execute(
                """
                UPDATE gastostracker
                SET body_hash = %s
                WHERE messageid = %s AND body_hash IS NULL
                """,
                (body_hash, message_id),
            )

    def save_results(self, emails: Iterable[dict], analysis_results: Iterable[dict]) -> dict:
        emails_by_id = {email["id"]: email for email in emails}
        saved = 0
        skipped = 0
        failed = 0

        with psycopg.connect(self.database_url) as conn, conn.cursor() as cur:
            for result in analysis_results:
                if result["status"] != "success":
                    failed += 1
                    continue

                email = emails_by_id[result["email_id"]]
                transaction = result["transaction"]
                body_hash = calculate_body_hash(email["content"])
                output_values = (
                    transaction.vendor,
                    transaction.amount,
                    transaction.category,
                    transaction.valid,
                    transaction.description,
                )
                cur.execute(
                    """
                    UPDATE gastostracker
                    SET vendor = %s, amount = %s, category = %s, valid = %s,
                        description = %s, analyzed_at = NOW()
                    WHERE body_hash = %s AND analyzed_at IS NULL
                    """,
                    (*output_values, body_hash),
                )
                if cur.rowcount:
                    saved += 1
                    continue

                cur.execute(
                    """
                    SELECT EXISTS(
                        SELECT 1 FROM gastostracker
                        WHERE body_hash = %s AND analyzed_at IS NOT NULL
                    )
                    """,
                    (body_hash,),
                )
                if cur.fetchone()[0]:
                    skipped += 1
                    continue

                cur.execute(
                    """
                        INSERT INTO gastostracker (
                            messageid,
                            messagebody,
                            messagedate,
                            body_hash,
                            vendor,
                            amount,
                            category,
                            valid,
                            description,
                            analyzed_at
                        )
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
                        ON CONFLICT (body_hash) WHERE body_hash IS NOT NULL
                        DO UPDATE SET
                            vendor = EXCLUDED.vendor,
                            amount = EXCLUDED.amount,
                            category = EXCLUDED.category,
                            valid = EXCLUDED.valid,
                            description = EXCLUDED.description,
                            analyzed_at = EXCLUDED.analyzed_at
                        WHERE gastostracker.analyzed_at IS NULL
                        """,
                    (
                        email["id"],
                        email["content"],
                        email["date"],
                        body_hash,
                        transaction.vendor,
                        transaction.amount,
                        transaction.category,
                        transaction.valid,
                        transaction.description,
                    ),
                )
                if cur.rowcount == 1:
                    saved += 1
                else:
                    skipped += 1

        return {"saved": saved, "skipped": skipped, "failed": failed}
