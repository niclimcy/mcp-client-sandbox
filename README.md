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

First test: `chain_attack_test`

The repository includes an example test (`chain_attack_test`) that requires fetching git submodules and building 2 MCP servers (Node.js based). To run this first test locally, follow these steps:

1. Ensure you have Git and Node.js (npm) installed on your machine.

2. Initialize or update submodules (if you cloned without submodules):

```bash
# from the repo root
git submodule update --init --recursive
```

3. Build the malicious MCP server used by the test

```bash
cd examples/malicious_git_chain_attack
npm i
npm run build
cd -
```

4. Build the vulnerable MCP server used by the test

```bash
cd examples/vulnerable_git_mcp_server
npm i
npm run build
cd -
```

5. Set environment variables

```.env
GOOGLE_API_KEY=AIza****
SANDBOX_PATH=/path/to/mcp-client-monitoring/sandbox
```

6. Run the test with the MCP client (tests are referenced by name; the file `tests/chain_attack_test.json` is used when you pass `chain_attack_test`):

```bash
uv run main.py --test chain_attack_test
```

- This example requires Node. If you use nvm, ensure you have a compatible Node version active before running `npm i`.

### View Logs

Pretty print all logs collected during monitoring sessions:

```bash
uv run view_logs.py
```
