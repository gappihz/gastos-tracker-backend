import asyncio
import os

from dotenv import load_dotenv
from langchain.agents import create_agent
from langchain_openrouter import ChatOpenRouter
from templates.template import (
    TRANSACTION_AGENT_SYSTEM_PROMPT,
    transaction_response_format,
)
from tools.tools import tools

load_dotenv()


class TransactionAgent:
    def __init__(self) -> None:
        api_key = os.getenv("OPENROUTER_API_KEY")
        if not api_key:
            raise RuntimeError(
                "OPENROUTER_API_KEY is required to analyze transactions.")

        llm = ChatOpenRouter(
            model="deepseek/deepseek-v4-flash",
            api_key=api_key,
            max_tokens=800,
            temperature=0,
        )
        self.agent = create_agent(
            model=llm,
            system_prompt=TRANSACTION_AGENT_SYSTEM_PROMPT,
            response_format=transaction_response_format,
            tools=tools,
        )

    async def analyze_one(
        self,
        email_record: dict,
        semaphore: asyncio.Semaphore,
    ) -> dict:
        async with semaphore:
            result = await self.agent.ainvoke(
                {
                    "messages": [
                        {
                            "role": "user",
                            "content": email_record["content"],
                        }
                    ]
                }
            )
            return {
                "email_id": email_record["id"],
                "status": "success",
                "transaction": result["structured_response"],
            }

    async def run(self, email_records: list[dict], max_concurrency: int = 5) -> list[dict]:
        if max_concurrency < 1:
            raise ValueError("max_concurrency must be at least 1.")

        semaphore = asyncio.Semaphore(max_concurrency)
        outcomes = await asyncio.gather(
            *(self.analyze_one(email_record, semaphore)
              for email_record in email_records),
            return_exceptions=True,
        )

        results = []
        for email_record, outcome in zip(email_records, outcomes, strict=True):
            if isinstance(outcome, Exception):
                results.append(
                    {
                        "email_id": email_record["id"],
                        "status": "failed",
                        "error": str(outcome),
                    }
                )
            elif isinstance(outcome, BaseException):
                raise outcome
            else:
                results.append(outcome)

        return results
