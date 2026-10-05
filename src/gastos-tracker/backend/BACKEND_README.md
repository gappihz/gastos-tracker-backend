## Purpose of this BackEnd
- [x] SQL DataBase - Neon
    - [x] Node - Deterministic - always fetch and check in an hourly basis
    - [x] Node - Retrieves Emails with subject name gastos:
        - [x] Get Email Body save to NeonSQL
            - [x] email ID
            - [x] body
            - [x] Date? (opt)
- [ ] Create Classifier Agent
    - [ ] Create tool strategy output structured output
    - [ ] Let message body be the invokation
    - [ ] Use SQL Insert 
- [ ] Second Instance or Service - ReAct Agent Financial Advisor
    - [ ] SQL Tools
    - [ ] Email Tools and access

## Railway deployment

Use two Railway services in the same project and environment, both built from the repository-root `Dockerfile`:

```text
Hourly Railway cron -> POST -> API -> Gmail -> agent -> Neon
Manual POST ---------------> API
```

The API owns the job. The cron service only calls it and exits. Creating these files does not install a schedule; complete the Railway settings below.

### 1. Push the deployment files

Commit and push the root `Dockerfile`, `.dockerignore`, `.gitignore`, `.env.example`, `pyproject.toml`, `uv.lock`, backend source, tests, and documentation to your repository. Review your other local changes before committing. `uv.lock` is no longer ignored and must be committed for the Docker build. Do not commit `.env` or credentials.

The image uses Python 3.12, installs locked production dependencies, runs as a non-root user, and starts one Uvicorn worker. The existing `.devcontainer/Dockerfile` remains development-only.

### 2. Create the API service

In Railway, create a service from the GitHub repository and name it `web`. Keep the source/root directory at the repository root so Railway detects `Dockerfile`.

Configure these Variables using raw values, without enclosing quotes:

| Variable | Value |
| --- | --- |
| `DATABASE_URL` | Neon PostgreSQL connection URL, including its SSL settings |
| `APP_PASSWORD` | Working Gmail app password for the mailbox currently used in `email_node.py` |
| `OPENROUTER_API_KEY` | OpenRouter API key |
| `PORT` | `8000` |

The current mailbox is hardcoded in `email_node.py`; `GMAIL_ADDRESS` does not change it. This deployment does not alter the email login or transaction persistence logic. Do not upload `.env`; Railway supplies variables at runtime.

Under service settings:

- Leave Start Command unset; the image's default starts the API and reads `PORT`.
- Set Healthcheck Path to `/health`.
- Use one replica. Do not enable an hourly schedule on this service.
- Use the normal web-service restart policy, such as On Failure.
- Generate a public domain, targeting port `8000`, for manual HTTPS requests.
- Keep the API continuously running rather than configuring it as a cron process.

Verify `GET https://YOUR_API_DOMAIN/health` returns `{"status":"ok"}`. This is a startup/liveness check only; it does not contact Gmail, OpenRouter, or Neon.

### 3. Test a manual sync

Call the endpoint with any JSON body:

```bash
curl --fail-with-body --show-error --silent \
  --request POST \
  --header "Content-Type: application/json" \
  --data '{}' \
  https://YOUR_API_DOMAIN/internal/jobs/transaction-sync
```

This is a live operation: it fetches Gmail, runs the agent, and persists results in Neon. The request waits for completion and returns counts for `emails_found`, `analysis_failed`, `saved`, and `duplicates_skipped`. Check `analysis_failed` even when HTTP status is 200. Saved counts include updates to previously unprocessed rows, not just new inserts.

- `409`: a job is already running in that API process; do not start another.
- `500`: check the API logs; do not assume any transaction outputs were committed.

Use HTTPS directly for public requests. Railway's public proxy currently closes requests after five minutes without transferred data; this endpoint sends its response only at completion. A timeout does not prove the server stopped. Use the private cron trigger for longer runs and inspect logs before retrying.

### 4. Create the hourly trigger service

Create another service from the same repository in the same Railway project and environment; name it `hourly-sync`. Use the repository root and the same Dockerfile.

Set its Start Command to:

```text
python /app/src/gastos-tracker/backend/trigger_sync.py
```

Set its Variables to:

```text
JOB_URL=http://${{web.RAILWAY_PRIVATE_DOMAIN}}:${{web.PORT}}/internal/jobs/transaction-sync
JOB_TIMEOUT_SECONDS=1800
```

These `${{...}}` references are Railway variable syntax. Replace `web` if you chose another API service name. The explicit web `PORT=8000` makes the private port reference available. Only this trigger needs `JOB_URL` and `JOB_TIMEOUT_SECONDS`; it does not need database, Gmail, or OpenRouter credentials.

Configure:

- Cron Schedule: `0 * * * *` (hourly, in UTC).
- Restart Policy: Never. Otherwise a failed or completed trigger could be restarted unexpectedly.
- Healthcheck Path: unset. This is a finite process, not an HTTP server.
- No public domain is required for the trigger.

Deploy and manually run the cron service once. Its logs should contain the same counts as the manual API request. It exits nonzero on HTTP/network errors or `analysis_failed > 0`, and logs an overlapping run as skipped. It never automatically retries and never follows redirects.

Railway skips a scheduled invocation if its previous cron process is still running. Private HTTP avoids the public proxy inactivity limit; the trigger also has a configurable request timeout. Private networking must be in the same project/environment. The image listens on IPv4; legacy IPv6-only Railway environments need an IPv4-capable environment or a different network/bind configuration.

### 5. Local Docker check

On a machine with Docker, run from the repository root:

```bash
docker build --tag gastos-tracker .
docker run --detach --name gastos-tracker --restart unless-stopped \
  --env-file .env --publish 127.0.0.1:8000:8000 gastos-tracker
curl --fail http://127.0.0.1:8000/health
docker logs gastos-tracker
```

For Docker's `--env-file`, values must not have surrounding quotes; Docker preserves them, unlike Python dotenv parsing. The real `.env` and its variants are excluded from the build context. No credentials are built into the image.

### Execution limits

The job's overlap lock is process-local. Keep one web replica and one worker; it does not prevent overlap across separate services, replicas, or old/new deployments. Avoid deploying during an active sync. Before scaling or requiring durable background execution, add a database-backed job lock/queue. Neither the health endpoint nor a successful image build verifies live transaction persistence.

Official references: [Dockerfiles](https://docs.railway.com/builds/dockerfiles), [cron jobs](https://docs.railway.com/cron-jobs), [private networking](https://docs.railway.com/networking/private-networking/how-it-works), [reference variables](https://docs.railway.com/variables/reference), [HTTP limits](https://docs.railway.com/networking/public-networking/specs-and-limits).
