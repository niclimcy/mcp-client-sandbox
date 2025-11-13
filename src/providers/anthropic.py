from typing import Awaitable, Callable

from anthropic import Anthropic
from mcp import Tool
from mcp.types import CallToolResult

from logger.base import ToolUsageLogger
from logger.models import ToolCallRecord
from providers.base import AIProvider
from server_manager import MCPServerManager

ANTHROPIC_MODELS = ["claude-haiku-4-5-20251001", "claude-sonnet-4-5-20250929"]


class AnthropicProvider(AIProvider):
    """Anthropic Claude AI provider implementation."""

    _default_model = ANTHROPIC_MODELS[0]  # claude-haiku-4-5-20251001

    def __init__(self, **kwargs) -> None:
        """Initialize Anthropic provider."""
        self.client = Anthropic(**kwargs)
        self.set_model(self._default_model)
        self.conversation_history = []

    def get_supported_models(self) -> list[str]:
        """Get list of supported Anthropic models."""
        return ANTHROPIC_MODELS

    async def process_query(
        self,
        query: str,
        tools: list[Tool],
        tool_executor: Callable[[str, dict], Awaitable[CallToolResult]],
        logger: ToolUsageLogger,
        server_manager: MCPServerManager,
    ) -> str:
        """
        Process a query using Anthropic Claude with tool support.

        Args:
            query: User query to process
            tools: List of available MCP tools
            tool_executor: Callable that executes tool calls (tool_name, tool_args) -> result
            logger: Logger for tracking tool usage
            server_manager: Server manager for getting metadata

        Returns:
            Final response text after processing tool calls
        """
        model = self.current_model or self._default_model

        # Start with conversation history and add new user query
        messages = self.conversation_history.copy()
        messages.append({"role": "user", "content": query})

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

                # Create tool call record for logging
                server_metadata = server_manager.get_server_metadata_by_tool_name(
                    tool_name
                )
                if not server_metadata:
                    raise ValueError(
                        f"Could not find server metadata for tool: {tool_name}"
                    )

                record = ToolCallRecord.create(
                    tool_name=tool_name,
                    server_metadata=server_metadata,
                    input_args=tool_args,
                )

                # Execute tool call
                try:
                    result = await tool_executor(tool_name, tool_args)
                    final_text.append(
                        f"[Calling tool {tool_name} with args {tool_args}]"
                    )

                    # Format result for Claude
                    try:
                        # MCP result.content is a list of content items
                        # Extract just the text from TextContent items
                        result_text = ""
                        for content_item in result.content:
                            if hasattr(content_item, "text"):
                                result_text += content_item.text

                        # Log successful tool call
                        record.complete(
                            output={"result": result_text},
                            status="success",
                        )
                        await logger.log_tool_call(record)
                    except Exception as e:
                        # Log error in result processing
                        record.complete(
                            output=None,
                            status="error",
                            error_message=f"Result processing error: {str(e)}",
                        )
                        await logger.log_tool_call(record)

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
                except Exception as e:
                    # Log tool execution error
                    record.complete(
                        output=None,
                        status="error",
                        error_message=str(e),
                    )
                    await logger.log_tool_call(record)
                    raise

        # Update conversation history with the complete exchange
        self.conversation_history = messages

        return "\n".join(final_text)
