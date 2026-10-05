import io
import json
from unittest.mock import Mock
from urllib.error import HTTPError, URLError

import pytest
import trigger_sync

SUMMARY = {"emails_found": 3, "analysis_failed": 0, "saved": 2, "duplicates_skipped": 1}
JOB_URL = "http://web.railway.internal:8000/internal/jobs/transaction-sync"


@pytest.fixture
def opener(monkeypatch):
    client = Mock()
    client.open.return_value = io.BytesIO(json.dumps(SUMMARY).encode())
    factory = Mock(return_value=client)
    monkeypatch.setattr(trigger_sync, "build_opener", factory)
    monkeypatch.setenv("JOB_URL", JOB_URL)
    monkeypatch.delenv("JOB_TIMEOUT_SECONDS", raising=False)
    return client


def test_trigger_posts_json_with_timeout(opener):
    assert trigger_sync.trigger_sync(JOB_URL, 600) == SUMMARY
    request = opener.open.call_args.args[0]
    assert request.full_url == JOB_URL
    assert request.get_method() == "POST"
    assert request.data == b"{}"
    assert request.get_header("Content-type") == "application/json"
    assert request.get_header("Authorization") is None
    assert opener.open.call_args.kwargs == {"timeout": 600}
    assert isinstance(trigger_sync.build_opener.call_args.args[0], trigger_sync.NoRedirectHandler)
    assert opener.open.return_value.closed


def test_redirect_handler_refuses_to_forward_credentials():
    handler = trigger_sync.NoRedirectHandler()
    assert handler.redirect_request(None, None, 302, "", {}, "https://other.invalid") is None


def test_successful_cron_logs_only_counts_and_exits_zero(opener, capsys):
    opener.open.return_value = io.BytesIO(json.dumps({**SUMMARY, "secret": "omit-me"}).encode())
    assert trigger_sync.main() == 0
    assert json.loads(capsys.readouterr().out) == SUMMARY


def test_partial_analysis_failure_exits_nonzero(opener, capsys):
    summary = {**SUMMARY, "analysis_failed": 1}
    opener.open.return_value = io.BytesIO(json.dumps(summary).encode())
    assert trigger_sync.main() == 1
    assert json.loads(capsys.readouterr().out) == summary


def test_already_running_is_skipped_without_retry(opener, capsys):
    opener.open.side_effect = HTTPError(JOB_URL, 409, "Conflict", {}, io.BytesIO())
    assert trigger_sync.main() == 0
    assert json.loads(capsys.readouterr().out) == {
        "status": "skipped",
        "reason": "job_already_running",
    }
    assert opener.open.call_count == 1


@pytest.mark.parametrize("status", [301, 302, 307, 401, 503, 500])
def test_http_error_fails_without_retry_or_response_leak(opener, capsys, status):
    opener.open.side_effect = HTTPError(
        JOB_URL, status, "sensitive-error", {}, io.BytesIO(b"private-response")
    )
    assert trigger_sync.main() == 1
    output = capsys.readouterr().out
    assert f"HTTP {status}" in output
    assert "private-response" not in output
    assert "sensitive-error" not in output
    assert "test-only-token" not in output
    assert opener.open.call_count == 1


@pytest.mark.parametrize("error", [TimeoutError(), URLError("sensitive-url")])
def test_network_failure_warns_server_may_still_be_running(opener, capsys, error):
    opener.open.side_effect = error
    assert trigger_sync.main() == 1
    output = capsys.readouterr().out
    assert "server may still be processing" in output
    assert "sensitive-url" not in output
    assert opener.open.call_count == 1


@pytest.mark.parametrize("response", [b"not-json", b"[]", b"{}", b'{"saved": true}'])
def test_unexpected_response_is_a_failed_run(opener, capsys, response):
    opener.open.return_value = io.BytesIO(response)
    assert trigger_sync.main() == 1
    assert json.loads(capsys.readouterr().out)["status"] == "failed"


@pytest.mark.parametrize("timeout", ["0", "-1", "NaN", "inf", "not-a-number"])
def test_invalid_timeout_is_rejected_before_network(opener, monkeypatch, capsys, timeout):
    monkeypatch.setenv("JOB_TIMEOUT_SECONDS", timeout)
    assert trigger_sync.main() == 1
    opener.open.assert_not_called()
    assert "JOB_TIMEOUT_SECONDS" in capsys.readouterr().out


def test_missing_job_url_is_rejected_before_network(opener, monkeypatch):
    monkeypatch.delenv("JOB_URL")
    assert trigger_sync.main() == 1
    opener.open.assert_not_called()


def test_credentials_in_url_are_rejected_without_logging_them(opener, monkeypatch, capsys):
    monkeypatch.setenv("JOB_URL", "https://user:private-password@example.invalid/sync")
    assert trigger_sync.main() == 1
    opener.open.assert_not_called()
    assert "private-password" not in capsys.readouterr().out
