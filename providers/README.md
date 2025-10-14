# AI Providers

This directory contains AI provider implementations for MCP (Model Context Protocol) tool integration.

## Architecture

- **`base.py`**: Abstract base class `AIProvider` that defines the interface for all AI providers
- **`anthropic.py`**: Anthropic Claude implementation
- **`google_genai.py`**: Google Generative AI (Gemini) implementation

## Default Provider

The default provider is **Google GenAI** using the **gemini-2.5-flash-lite** model.

## Adding New Providers

To add a new AI provider:

1. Create a new file in this directory (e.g., `openai.py`)
2. Import and inherit from `AIProvider` base class
3. Implement the required abstract methods:
   - `__init__()`: Initialize the provider client
   - `get_supported_models()`: Return list of supported model names
   - `process_query()`: Handle query processing with MCP tool support
4. Add the provider to `__init__.py`
5. Optionally update `client.py` to change the default provider

## Supported Models

### Anthropic
- claude-sonnet-4-5-20250929

### Google GenAI
- gemini-2.5-flash-lite (default)
- gemini-2.5-flash
- gemini-2.5-pro

### OpenAI (Not Yet Implemented)
- gpt-5
- gpt-5-mini
- gpt-5-nano
- gpt-4.1
