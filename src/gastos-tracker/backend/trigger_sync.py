import json
import math
import os
from http.client import HTTPException
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

SUMMARY_FIELDS = ("emails_found", "analysis_failed", "saved", "duplicates_skipped")


class NoRedirectHandler(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def trigger_sync(job_url: str, timeout_seconds: float = 1800) -> dict:
    try:
        url = urlsplit(job_url)
    except ValueError:
        raise ValueError("JOB_URL must be a valid HTTP or HTTPS endpoint URL.") from None

    if (
        url.scheme not in {"http", "https"}
        or not url.hostname
        or url.username is not None
        or url.password is not None
        or url.fragment
    ):
        raise ValueError("JOB_URL must be an HTTP or HTTPS endpoint URL without credentials.")
    if not math.isfinite(timeout_seconds) or timeout_seconds <= 0:
        raise ValueError("JOB_TIMEOUT_SECONDS must be a positive finite number.")

    try:
        request = Request(
            job_url,
            data=b"{}",
            headers={"Accept": "application/json", "Content-Type": "application/json"},
            method="POST",
        )
        with build_opener(NoRedirectHandler()).open(request, timeout=timeout_seconds) as response:
            result = json.load(response)
    except HTTPError as error:
        error.close()
        if error.code == 409:
            return {"status": "skipped", "reason": "job_already_running"}
        raise RuntimeError(
            f"Sync endpoint returned HTTP {error.code}; no retry attempted."
        ) from None
    except (URLError, OSError, HTTPException):
        raise RuntimeError(
            "Sync request failed or timed out. The server may still be processing; "
            "no retry attempted."
        ) from None
    except ValueError:
        raise RuntimeError("Invalid request configuration or non-JSON sync response.") from None

    if not isinstance(result, dict) or any(
        type(result.get(field)) is not int or result[field] < 0 for field in SUMMARY_FIELDS
    ):
        raise RuntimeError("Sync endpoint returned an unexpected summary.")

    return {field: result[field] for field in SUMMARY_FIELDS}


def main() -> int:
    try:
        timeout_seconds = float(os.getenv("JOB_TIMEOUT_SECONDS", "1800"))
    except ValueError:
        print(json.dumps({"status": "failed", "error": "JOB_TIMEOUT_SECONDS must be a number."}))
        return 1

    try:
        result = trigger_sync(os.getenv("JOB_URL", ""), timeout_seconds)
    except (ValueError, RuntimeError) as error:
        print(json.dumps({"status": "failed", "error": str(error)}))
        return 1

    print(json.dumps(result))
    return int(result.get("analysis_failed", 0) > 0)


if __name__ == "__main__":
    raise SystemExit(main())
