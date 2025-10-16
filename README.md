# MCP Client Monitoring

This project was created to log MCP server behaviour, to detect malicious MCP servers by intercepting all requests in the MCP client.

## Installation

This project uses [`uv`](https://docs.astral.sh/uv/) as the package manager. To install dependencies, run:

```bash
uv sync
```

## Usage

### Run the MCP Client

To start the MCP client monitoring service:

```bash
uv run main.py
```

### View Logs

To pretty print all logs collected during monitoring sessions:

```bash
uv run view_logs.py
```
