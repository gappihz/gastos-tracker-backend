# Python Microservice Buildkit

A minimal Python 3.12 microservice starter with reproducible dependencies, testing, linting, a VS Code dev container, and optional AI development tooling.

## Included

- Python 3.12
- `uv` for dependency and virtual-environment management
- pytest for testing
- Ruff for linting and formatting
- VS Code dev container
- LangChain with OpenAI and OpenRouter integrations
- Deep Agents Code with mentor, debugger, reviewer, researcher, and curriculum agents
- prompt-kit MCP configuration and optional Context7 MCP configuration

## Deploy Gastos Tracker

See [the backend deployment instructions](src/gastos-tracker/backend/BACKEND_README.md#railway-deployment) for Docker, the Railway API service, hourly scheduling, and manual sync requests.

## Start a New Project

Requirements: Git, Docker, VS Code, and the VS Code Dev Containers extension.

Replace `<buildkit-url>` and `<project-name>`:

```bash
git clone <buildkit-url> <project-name>
cd <project-name>
cp .env.example .env
```

Detach the clone from the buildkit's Git history. Before deleting `.git`, verify that the current directory is the new clone and not the original buildkit:

```bash
pwd
git remote -v
rm -rf .git
git init
```

Open the project:

```bash
code .
```

In VS Code, run **Dev Containers: Reopen in Container**. The container build installs `uv` and Deep Agents Code; its post-create command synchronizes all dependency groups and configures the MCP servers.

## Rename the Project

Update these values before the first commit:

- `project.name` and `project.description` in `pyproject.toml`
- `name` in `.devcontainer/devcontainer.json`
- The title and description in this README

Then synchronize the lockfile:

```bash
uv sync --all-groups
```

Create the fresh repository's first commit:

```bash
git add README.md pyproject.toml uv.lock .devcontainer .env.example .gitignore .dockerignore
git commit -m "Initialize project"
```

Add the new repository remote when ready:

```bash
git remote add origin <new-repository-url>
git branch -M main
git push -u origin main
```

## Environment

The dev container reads `.env` when it starts, so create it before reopening the project in the container:

```bash
cp .env.example .env
```

Available variables:

```dotenv
CONTEXT7_API_KEY=
OPENROUTER_API_KEY=
```

- `CONTEXT7_API_KEY` enables Context7 MCP configuration. Context7 is skipped when this value is empty.
- `OPENROUTER_API_KEY` is available to code and tools that connect through OpenRouter.

Never commit `.env`.

## Common Commands

Run these inside the dev container:

```bash
# Synchronize runtime and development dependencies
uv sync --all-groups

# Run tests
uv run pytest

# Run lint checks
uv run ruff check .

# Check formatting
uv run ruff format --check .

# Apply formatting
uv run ruff format .

# Start Deep Agents Code
dcode
```

## Dependencies

```bash
# Add a runtime dependency
uv add <package>

# Add a development dependency
uv add --dev <package>
```

Commit both `pyproject.toml` and `uv.lock` after dependency changes.

## Initial Structure

```text
.
├── .devcontainer/
├── .dockerignore
├── .env.example
├── .gitignore
├── pyproject.toml
├── uv.lock
└── README.md
```

Add application and test directories when starting the service:

```text
src/
tests/
```
