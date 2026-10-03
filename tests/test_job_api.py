from concurrent.futures import ThreadPoolExecutor, TimeoutError
from threading import Event
from unittest.mock import AsyncMock, Mock

import main
import pytest
from fastapi.testclient import TestClient
from nodes.transaction_sync_job import JobAlreadyRunningError


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("JOB_SECRET", "test-only-token")
    monkeypatch.setattr(main.app, "dependency_overrides", {})
    main._create_transaction_sync_job.cache_clear()
    with TestClient(main.app) as test_client:
        yield test_client
    main._create_transaction_sync_job.cache_clear()


def test_health_does_not_initialize_job(client, monkeypatch):
    factory = Mock(side_effect=AssertionError("Job must remain lazy"))
    monkeypatch.setattr(main, "_create_transaction_sync_job", factory)
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    factory.assert_not_called()


@pytest.mark.parametrize("headers", [{}, {"Authorization": "Bearer incorrect"}])
def test_auth_rejected_before_initializing_job(client, monkeypatch, headers):
    factory = Mock(side_effect=AssertionError("Unauthorized job creation"))
    monkeypatch.setattr(main, "_create_transaction_sync_job", factory)
    response = client.post("/internal/jobs/transaction-sync", headers=headers)
    assert response.status_code == 401
    factory.assert_not_called()


def test_missing_job_secret_returns_503(client, monkeypatch):
    monkeypatch.delenv("JOB_SECRET")
    response = client.post("/internal/jobs/transaction-sync")
    assert response.status_code == 503


def test_authorized_endpoint_returns_job_summary(client):
    summary = {"emails_found": 3, "analysis_failed": 0, "saved": 2, "duplicates_skipped": 1}
    job = Mock(run=AsyncMock(return_value=summary))
    main.app.dependency_overrides[main.get_transaction_sync_job] = lambda: job
    response = client.post(
        "/internal/jobs/transaction-sync", headers={"Authorization": "Bearer test-only-token"}
    )
    assert response.status_code == 200
    assert response.json() == summary
    job.run.assert_awaited_once_with()


def test_endpoint_reports_already_running(client):
    job = Mock(run=AsyncMock(side_effect=JobAlreadyRunningError("Already running")))
    main.app.dependency_overrides[main.get_transaction_sync_job] = lambda: job
    response = client.post(
        "/internal/jobs/transaction-sync", headers={"Authorization": "Bearer test-only-token"}
    )
    assert response.status_code == 409


def test_concurrent_first_requests_share_one_job(client, monkeypatch):
    entered = Event()
    release = Event()

    def build_agent():
        entered.set()
        if not release.wait(timeout=5):
            raise AssertionError("Test did not release the factory")
        return object()

    agent_factory = Mock(side_effect=build_agent)
    repository_factory = Mock(return_value=object())
    monkeypatch.setattr(main, "TransactionAgent", agent_factory)
    monkeypatch.setattr(main, "TransactionRepository", repository_factory)

    with ThreadPoolExecutor(max_workers=2) as executor:
        first = executor.submit(main.get_transaction_sync_job)
        try:
            assert entered.wait(timeout=5)
            second = executor.submit(main.get_transaction_sync_job)
            with pytest.raises(TimeoutError):
                second.result(timeout=0.05)
        finally:
            release.set()
        assert first.result(timeout=5) is second.result(timeout=5)

    agent_factory.assert_called_once_with()
    repository_factory.assert_called_once_with()
