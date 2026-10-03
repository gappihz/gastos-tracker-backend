# TODO:
# - [x] IMAP Lib login and sync
# - [x] Create functions to decipher email
# - [] Save Email - Make filter if email id exists
# - [] Save to NeonSQL

import imaplib
import email
import os
from dotenv import load_dotenv
import psycopg

load_dotenv()

appPass = os.getenv('APP_PASSWORD')
db_url = os.getenv('NEON_DB_URL')
print(db_url)


def fetch_emails(appPass):
    db_email = []
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
            # add if statement if statemtn - if ID in list of existing from DB Fetch append if not pass
            db_email.append(
                {
                    "id": m_id_m,
                    "date": m_date,
                    "content": body,
                }
            )
            print(db_email)

            break


if __name__ == "__main__":
    fetch_emails(appPass=appPass)
