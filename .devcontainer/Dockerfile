FROM mcr.microsoft.com/devcontainers/python:1-3.12-bookworm

COPY --from=ghcr.io/astral-sh/uv:0.12.17 /uv /uvx /bin/

USER root

RUN mkdir -p /home/vscode/.deepagents/mentor/agents

COPY .devcontainer/dcode-agents/config.toml \
    /home/vscode/.deepagents/config.toml

COPY .devcontainer/dcode-agents/mentor/ \
    /home/vscode/.deepagents/mentor/

COPY .devcontainer/dcode-agents/mentor-researcher/ \
    /home/vscode/.deepagents/mentor/agents/mentor-researcher/

COPY .devcontainer/dcode-agents/mentor-reviewer/ \
    /home/vscode/.deepagents/mentor/agents/mentor-reviewer/

COPY .devcontainer/dcode-agents/mentor-debugger/ \
    /home/vscode/.deepagents/mentor/agents/mentor-debugger/

COPY .devcontainer/dcode-agents/mentor-curriculum/ \
    /home/vscode/.deepagents/mentor/agents/mentor-curriculum/

RUN chown -R vscode:vscode /home/vscode/.deepagents

USER vscode

RUN uv tool install "deepagents-code==0.1.71"

ENV PATH="/home/vscode/.local/bin:${PATH}"