import os
import secrets
from functools import lru_cache
from threading import Lock
from typing import Annotated

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, Header, HTTPException, status
from nodes.transaction_analysis_agent import TransactionAgent
from nodes.transaction_repository import TransactionRepository
from nodes.transaction_sync_job import JobAlreadyRunningError, TransactionSyncJob

load_dotenv()

app = FastAPI(title="Gastos Tracker")
_job_factory_lock = Lock()


@lru_cache(maxsize=1)
def _create_transaction_sync_job() -> TransactionSyncJob:
    return TransactionSyncJob(
        transaction_agent=TransactionAgent(),
        transaction_repository=TransactionRepository(),
    )


def get_transaction_sync_job() -> TransactionSyncJob:
    with _job_factory_lock:
        return _create_transaction_sync_job()


def verify_job_secret(
    authorization: Annotated[str | None, Header()] = None,
) -> None:
    expected_secret = os.getenv("JOB_SECRET")
    if not expected_secret:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="JOB_SECRET is not configured.",
        )

    expected_header = f"Bearer {expected_secret}"
    if authorization is None or not secrets.compare_digest(authorization, expected_header):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid job authorization.",
        )


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.post("/internal/jobs/transaction-sync")
async def run_transaction_sync(
    _: Annotated[None, Depends(verify_job_secret)],
    job: Annotated[TransactionSyncJob, Depends(get_transaction_sync_job)],
) -> dict:
    try:
        return await job.run()
    except JobAlreadyRunningError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(error),
        ) from error
