---
title: Getting Started with Acme SDK
author: engineering-team
version: "2.1"
---

# Getting Started

Welcome to the Acme SDK! This guide walks you through installation and basic usage.

## Installation

Install the SDK via pip:

```bash
pip install acme-sdk
```

Or with optional dependencies:

```bash
pip install acme-sdk[async,cache]
```

## Quick Start

Create a client and make your first API call:

```python
from acme import Client

client = Client(api_key="sk-...")
result = client.query("Hello, world!")
print(result.text)
```

## Configuration

Set environment variables for default configuration:

```bash
export ACME_API_KEY=sk-...
export ACME_TIMEOUT=30
```

Or configure programmatically:

```python
from acme import Client, Config

config = Config(timeout=60, retries=3)
client = Client(api_key="sk-...", config=config)
```

## Next Steps

- Read the [API Reference](api-reference.md) for detailed endpoint documentation
- Check out [Examples](examples.md) for common use cases
- Join our [Discord](https://discord.gg/acme) for community support
