---
name: qveris-coding
description: When coding a project that needs external APIs or tools, use QVeris to discover, verify, and generate production code that calls those APIs. Covers weather, stocks, search, currency, data retrieval, and thousands more.
metadata: {"openclaw": {"requires": {"env": ["QVERIS_API_KEY"]}, "primaryEnv": "QVERIS_API_KEY"}}
---

# QVeris — External API Code Generation

When a coding project needs to call external APIs or third-party tools (weather, stocks, search, currency, data retrieval, etc.), follow this workflow to discover a working API and generate production code.

## Step 1 — Search & Verify via MCP

Use the QVeris MCP server to find and test tools.

1. **Search**: Call the `search_tools` MCP tool with a query that describes the **capability** you need (not specific parameters).
   - Good query: `"current weather data"`, `"stock price API"`, `"currency exchange rates"`
   - Bad query: `"get weather for London"` (too specific)
2. **Test**: Call `execute_tool` with the `tool_id` from search results and pass parameters via `params_to_tool` (JSON string). Refer to examples returned by search if available.
3. You may call multiple MCP tools in a single response. Iterate between `search_tools` and `execute_tool` until you find a tool that works.

## Step 2 — Generate Production Code

Once you have confirmed a working `tool_id` from Step 1, generate code that calls the **QVeris REST API** directly. Do **not** use the MCP tool results as the final output — generate real, standalone code.

Rules for generated code:
- Use the verified `tool_id` directly (no search call needed in production code).
- Set HTTP request timeout to **5 seconds**.
- Handle error responses correctly (non-200 status, `success: false`).
- Place the `QVERIS_API_KEY` in the code (read from environment variable or config).

### QVeris REST API Reference

**Base URL**: `https://qveris.ai/api/v1`

**Authentication**: Bearer token in the `Authorization` header.

```
Authorization: Bearer YOUR_QVERIS_API_KEY
```

**Execute Tool Endpoint**:

```
POST /tools/execute?tool_id={tool_id}
```

Request body:

```json
{
  "search_id": "string",
  "session_id": "string",
  "parameters": {
    "city": "London",
    "units": "metric"
  },
  "max_response_size": 20480
}
```

Response (200 OK):

```json
{
  "execution_id": "string",
  "result": {
    "data": { ... }
  },
  "success": true,
  "error_message": null,
  "elapsed_time_ms": 847
}
```

## Fallback — CLI Script (if MCP is unavailable)

If MCP tools are not available or not working, use the CLI script instead.

**Search**:
```bash
uv run {baseDir}/../scripts/qveris_tool.py search "weather forecast API" --limit 5
```

**Execute** (to verify a tool works):
```bash
uv run {baseDir}/../scripts/qveris_tool.py execute <tool_id> --search-id <id> --params '{"city": "London", "units": "metric"}'
```

After verifying a working tool via CLI, proceed to **Step 2** above to generate production code using the REST API.
