from typing import Awaitable, Callable

from anthropic import Anthropic
from mcp import Tool
from mcp.types import CallToolResult

from providers.base import AIProvider


ANTHROPIC_MODELS = ["claude-haiku-4-5-20251001", "claude-sonnet-4-5-20250929"]


class AnthropicProvider(AIProvider):
    """Anthropic Claude AI provider implementation."""

    def __init__(self, **kwargs) -> None:
        """Initialize Anthropic provider."""
        self.client = Anthropic(**kwargs)
        self.default_model = ANTHROPIC_MODELS[0]

    def get_supported_models(self) -> list[str]:
        """Get list of supported Anthropic models."""
        return ANTHROPIC_MODELS

    async def process_query(
        self,
        query: str,
        tools: list[Tool],
        model: str | None = None,
        tool_executor: Callable[[str, dict], Awaitable[CallToolResult]] | None = None,
    ) -> str:
        """
        Process a query using Anthropic Claude with tool support.

        Args:
            query: User query to process
            tools: List of available MCP tools
            model: Optional model name (uses default if not specified)
            tool_executor: Callable that executes tool calls (tool_name, tool_args) -> result

        Returns:
            Final response text after processing tool calls
        """
        model = model or self.default_model
        messages = [{"role": "user", "content": query}]

        # Initial Claude API call
        response = self.client.messages.create(
            model=model,
            max_tokens=1000,
            messages=messages,
            tools=tools,
        )

        # Process response and handle tool calls
        final_text = []
        assistant_message_content = []

        for content in response.content:
            if content.type == "text":
                final_text.append(content.text)
                assistant_message_content.append(content)
            elif content.type == "tool_use":
                tool_name = content.name
                tool_args = content.input

                # Execute tool call via provided executor
                if tool_executor:
                    result = await tool_executor(tool_name, tool_args)
                    final_text.append(
                        f"[Calling tool {tool_name} with args {tool_args}]"
                    )

                    assistant_message_content.append(content)
                    messages.append(
                        {"role": "assistant", "content": assistant_message_content}
                    )
                    messages.append(
                        {
                            "role": "user",
                            "content": [
                                {
                                    "type": "tool_result",
                                    "tool_use_id": content.id,
                                    "content": result.content,
                                }
                            ],
                        }
                    )

                    # Get next response from Claude
                    response = self.client.messages.create(
                        model=model,
                        max_tokens=1000,
                        messages=messages,
                        tools=tools,
                    )

                    final_text.append(response.content[0].text)

        return "\n".join(final_text)
