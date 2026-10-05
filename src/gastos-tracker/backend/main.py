from functools import lru_cache
from threading import Lock
from typing import Annotated, Any

from dotenv import load_dotenv
from fastapi import Body, Depends, FastAPI, HTTPException, status
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


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.post("/internal/jobs/transaction-sync")
async def run_transaction_sync(
    job: Annotated[TransactionSyncJob, Depends(get_transaction_sync_job)],
    _payload: Annotated[Any, Body()] = None,
) -> dict:
    try:
        return await job.run()
    except JobAlreadyRunningError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(error),
        ) from error
