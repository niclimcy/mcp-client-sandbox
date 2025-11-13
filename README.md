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

Run tests with the MCP client using the `--test` flag. You can pass one or more test names (space-separated). Test files live in the `tests/` directory and are referenced by name (the loader appends `.json`).

Quick usage:

```bash
uv run src/main.py --test <test_name_1> [<test_name_2> ...]
```

Example: the repository includes an example test called `chain_attack_test`. It requires fetching git submodules and building two Node.js-based example MCP servers. Follow the steps below to run it locally.

1. Fetch and initialize submodules:

```bash
# from the repo root
git submodule update --init --recursive
```

2. Build the malicious MCP server used by the test:

```bash
cd examples/malicious_git_chain_attack
npm ci
npm run build
cd -
```

3. Build the vulnerable MCP server used by the test:

```bash
cd examples/vulnerable_git_mcp_server
npm ci
npm run build
cd -
```

4. Create a `.env` in the repo root (you can copy from `.env.example`) and set required environment variables. Example `.env` entries:

```env
# API key for provider
GOOGLE_API_KEY=AIza****

# Absolute path to andbox environment used by this test
SANDBOX_PATH=/absolute/path/to/mcp-client-monitoring/sandbox
```

5. Run the example test `chain_attack_test`:

```bash
uv run src/main.py --test chain_attack_test
```

Running multiple tests:

```bash
uv run src/main.py --test chain_attack_test another_test_name
```

Troubleshooting & tips

- If a Node build fails, run `npm ci` then `npm run build` inside the failing example folder and inspect the build output.
- If you get errors about missing submodules or missing example server files, re-run:

```bash
git submodule update --init --recursive
```

### View Logs

Pretty print all logs collected during monitoring sessions:

```bash
uv run src/view_logs.py
```
