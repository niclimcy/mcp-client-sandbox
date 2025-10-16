# AI Providers

This directory contains AI provider implementations for MCP (Model Context Protocol) tool integration.

## Architecture

- **`base.py`**: Abstract base class `AIProvider` that defines the interface for all AI providers
- **`anthropic.py`**: Anthropic Claude implementation
- **`google_genai.py`**: Google Generative AI (Gemini) implementation
- **`openai.py`**: OpenAI implementation
- **`openrouter.py`**: OpenRouter implementation (uses OpenAI SDK)

## Adding New Providers

To add a new AI provider:

1. Create a new file in this directory (e.g., `provider_name.py`)
2. Import and inherit from `AIProvider` base class
3. Implement the required abstract methods:
   - `__init__()`: Initialize the provider client
   - `get_supported_models()`: Return list of supported model names
   - `process_query()`: Handle query processing with MCP tool support
4. Add the provider to `client.py` imports
5. Update the model selection logic in `client.py`

## Supported Models

### Google GenAI

- gemini-flash-lite-latest (default)
- gemini-2.5-flash-lite
- gemini-2.5-flash
- gemini-2.5-pro

### Anthropic

- claude-haiku-4-5-20251001
- claude-sonnet-4-5-20250929

### OpenAI

- gpt-4.1
- gpt-5-nano
- gpt-5-mini
- gpt-5

### OpenRouter

- No predefined models (use custom model input)
- Access to 200+ models from various providers
- See https://openrouter.ai/models for available models
