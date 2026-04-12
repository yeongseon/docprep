---
title: API Reference
version: "2.1"
---

# API Reference

Complete reference for the Acme SDK public API.

## Client

### `Client(api_key, timeout=30, retries=3)`

Create a new API client with automatic retry support.

**Parameters:**
- `api_key` (str): Your API key
- `timeout` (int): Request timeout in seconds
- `retries` (int): Number of automatic retries on failure

**Example:**

```python
from acme import Client

client = Client(api_key="sk-...", timeout=60)
```

### `Client.query(prompt, model="default")`

Send a query and get a response.

**Parameters:**
- `prompt` (str): The input prompt
- `model` (str): Model identifier

**Returns:** `QueryResult` with `.text` and `.usage` attributes

**Example:**

```python
result = client.query("Summarize this document", model="precise")
print(result.text)
print(f"Tokens used: {result.usage.total_tokens}")
```

## Models

Available models:

| Model | Description | Latency | Quality |
|-------|-------------|---------|---------|
| `default` | General purpose | Medium | High |
| `fast` | Lower latency | Low | Medium |
| `precise` | Highest quality | High | Highest |
| `vision` | Multimodal | Medium | High |

## Error Codes

| Status | Code | Description |
|--------|------|-------------|
| 400 | INVALID_REQUEST | Malformed request body |
| 401 | UNAUTHORIZED | Missing or expired token |
| 429 | RATE_LIMITED | Too many requests |
| 500 | INTERNAL_ERROR | Server-side failure |

## Rate Limits

Default rate limits are 100 requests per minute per token.
Enterprise plans support custom limits up to 10,000 req/min.

### Rate Limit Headers

Every response includes rate limit information:

```
X-RateLimit-Limit: 100
X-RateLimit-Remaining: 87
X-RateLimit-Reset: 1699999999
```
