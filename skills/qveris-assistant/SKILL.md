---
name: qveris-assistant
description: For any task where external data or APIs could help, use QVeris to search for and execute tools to retrieve real-time information for the user. Covers weather, stocks, search, currency, data retrieval, and thousands more.
metadata: {"openclaw": {"requires": {"env": ["QVERIS_API_KEY"]}, "primaryEnv": "QVERIS_API_KEY"}}
---

# QVeris — General Task Helper

When a user asks a question or requests a task that could benefit from external data or APIs (weather, stock prices, web search, currency rates, etc.), use QVeris to find and execute the right tool, then present the results.

## Step 1 — Search for Tools via MCP

Call the `search_tools` MCP tool with a query describing the **capability** you need.

- Good query: `"current weather data"`, `"stock price lookup"`, `"web search"`
- Bad query: `"get weather for London"` (describes parameters, not capability)

Review the returned tools — check `success_rate` and `avg_execution_time` to pick the best one.

## Step 2 — Execute the Tool via MCP

Call the `execute_tool` MCP tool with:
- `tool_id` — from search results
- `search_id` — from the search response
- `params_to_tool` — JSON string of parameters (refer to tool examples if available)

You may call multiple tools in a single response. Present the results directly to the user in a clear, readable format.

## Fallback — CLI Script (if MCP is unavailable)

If MCP tools are not available or not working, use the CLI script instead.

**Search**:
```bash
uv run {baseDir}/../scripts/qveris_tool.py search "weather forecast API" --limit 5
```

**Execute**:
```bash
uv run {baseDir}/../scripts/qveris_tool.py execute <tool_id> --search-id <id> --params '{"city": "London", "units": "metric"}'
```

Parse the CLI output and present results to the user.
