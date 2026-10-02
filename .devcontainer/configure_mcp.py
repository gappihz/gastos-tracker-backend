import json
import os
from pathlib import Path

mcp_servers = {
    "prompt-kit": {
        "command": "npx",
        "args": ["-y", "shadcn@canary", "mcp"],
        "env": {
            "REGISTRY_URL": "https://www.prompt-kit.com/c/registry.json"
        },
    }
}

context7_api_key = os.environ.get("CONTEXT7_API_KEY")

if context7_api_key:
    mcp_servers["context7"] = {
        "url": "https://mcp.context7.com/mcp",
        "transport": "http",
        "headers": {
            "CONTEXT7_API_KEY": context7_api_key
        },
    }
else:
    print("CONTEXT7_API_KEY is not set; Context7 MCP server was not configured.")

target = Path.home() / ".deepagents" / ".mcp.json"
target.parent.mkdir(parents=True, exist_ok=True)
target.write_text(json.dumps({"mcpServers": mcp_servers}, indent=2) + "\n")
target.chmod(0o600)