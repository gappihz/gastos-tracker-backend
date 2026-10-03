import psycopg
from body_hash import calculate_body_hash
from config import get_database_url
from dotenv import load_dotenv
from langchain.tools import tool

load_dotenv()

db_url = get_database_url()


@tool
def check_duplicate_transaction_email(message_body: str) -> dict:
    """Check whether this transaction email body has already been processed."""
    if not db_url:
        raise RuntimeError("DATABASE_URL is required to check duplicate emails.")

    body_hash = calculate_body_hash(message_body)

    with psycopg.connect(db_url) as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT EXISTS(
                SELECT 1 FROM gastostracker
                WHERE body_hash = %s AND analyzed_at IS NOT NULL
            )
            """,
            (body_hash,),
        )
        is_duplicate = cur.fetchone()[0]

    return {"is_duplicate": is_duplicate}


tools = [check_duplicate_transaction_email]
