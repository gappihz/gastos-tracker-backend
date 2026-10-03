import asyncio

from nodes.email_node import fetch_emails
from nodes.transaction_analysis_agent import TransactionAgent
from nodes.transaction_repository import TransactionRepository


class JobAlreadyRunningError(Exception):
    pass


class TransactionSyncJob:
    def __init__(
        self,
        transaction_agent: TransactionAgent,
        transaction_repository: TransactionRepository,
    ) -> None:
        self.transaction_agent = transaction_agent
        self.transaction_repository = transaction_repository
        self._lock = asyncio.Lock()

    async def run(self, max_concurrency: int = 5) -> dict:
        if self._lock.locked():
            raise JobAlreadyRunningError("A transaction sync job is already running.")

        async with self._lock:
            await asyncio.to_thread(self.transaction_repository.initialize_schema)
            emails = await asyncio.to_thread(fetch_emails)
            analysis_results = await self.transaction_agent.run(emails, max_concurrency)
            persistence = await asyncio.to_thread(
                self.transaction_repository.save_results,
                emails,
                analysis_results,
            )

        return {
            "emails_found": len(emails),
            "analysis_failed": persistence["failed"],
            "saved": persistence["saved"],
            "duplicates_skipped": persistence["skipped"],
        }
