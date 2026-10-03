import os


def get_database_url() -> str | None:
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        return None

    if (
        len(database_url) >= 2
        and database_url[0] in {"'", '"'}
        and database_url[-1] == database_url[0]
    ):
        return database_url[1:-1]

    return database_url
