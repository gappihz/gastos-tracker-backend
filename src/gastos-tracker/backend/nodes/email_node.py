# TODO:
# - [x] IMAP Lib login and sync
# - [x] Create functions to decipher email
# - [x] Save Email - Make filter if email id exists
# - [x] Save to NeonSQL

import imaplib
import email
from email.utils import parsedate_to_datetime
import os
from dotenv import load_dotenv
import psycopg

load_dotenv()

appPass = os.getenv('APP_PASSWORD')
db_url = os.getenv('DATABASE_URL')


def fetch_existing_messages(db_url):
    with psycopg.connect(db_url) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT messageid FROM gastostracker"
            )
            existing_emails = [row[0] for row in cur.fetchall()]
    return existing_emails


def insert_emails(db_url, emails: list):
    rows = [
        (
            item['id'],
            item['content'],
            parsedate_to_datetime(item['date']).date()
        )
        for item in emails
    ]
    with psycopg.connect(db_url) as conn:
        with conn.cursor() as cur:
            cur.executemany(
                """
                INSERT INTO gastostracker (messageid, messagebody, messagedate)
                VALUES (%s, %s, %s)          
                """,
                rows,
            )


def fetch_emails(appPass, existing_ids: list):
    db_email = []
    try:
        with imaplib.IMAP4_SSL("imap.gmail.com", 993) as mail:
            mail.login(
                "gappihertzd@gmail.com",
                appPass
            )
            mail.select("INBOX")

            status, data = mail.search(None, "SUBJECT", "gastos")
            message_ids = data[0].split()

            for m_id in message_ids:
                status, msg_data = mail.fetch(m_id, "(RFC822)")
                raw_email = msg_data[0][1]
                message = email.message_from_bytes(raw_email)
                body = message.get_payload(decode=True).decode(
                    message.get_content_charset() or "utf-8",
                    errors="replace",
                )

                m_id_m, m_date = message['Message-Id'], message['Date']
                if m_id_m in existing_ids:
                    continue
                else:
                    db_email.append(
                        {
                            "id": m_id_m,
                            "date": m_date,
                            "content": body,
                        }
                    )

        return db_email
    except Exception as e:
        raise f'Error: {e}'


def main(db_url, appPass):
    existing_emails = fetch_existing_messages(db_url=db_url)
    emails = fetch_emails(appPass=appPass, existing_ids=existing_emails)
    insert_emails(db_url=db_url, emails=emails)


if __name__ == "__main__":
    main(db_url=db_url, appPass=appPass)
