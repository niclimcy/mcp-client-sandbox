# MCP Client Monitoring

A monitoring tool for logging MCP server behavior and detecting malicious servers by intercepting all requests in the MCP client.

## Installation

This project uses [`uv`](https://docs.astral.sh/uv/) as the package manager.

```bash
uv sync
```

## Usage

### Interactive Mode

**1. Configure MCP Servers**

Create `servers.json` from `servers.example.json`. Environment variables in the format `${ENV_VAR}` will be replaced with values from your current environment.

**2. Set Environment Variables**

Create `.env` from `.env.example`. Define API keys for your AI providers and any environment variables referenced in `servers.json`.

**3. Start the Monitoring Service**

```bash
uv run main.py
```

### Test Mode

Run tests with the MCP client:

```bash
uv run main.py --test <file_name_1> <file_name_2>
```

Test files are located in the `/tests` directory.

### View Logs

Pretty print all logs collected during monitoring sessions:

```bash
uv run view_logs.py
```
