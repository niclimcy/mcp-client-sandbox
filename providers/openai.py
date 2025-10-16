import json
from typing import Awaitable, Callable, Iterable

from mcp import Tool
from mcp.types import CallToolResult
from openai import OpenAI
from openai.types.chat.chat_completion_tool_union_param import (
    ChatCompletionToolUnionParam,
)

from providers.base import AIProvider
from logger.models import ToolCallRecord
from logger.base import ToolUsageLogger
from server_manager import MCPServerManager


OPENAI_MODELS = [
    "gpt-4.1",
    "gpt-5-nano",
    "gpt-5-mini",
    "gpt-5",
]


class OpenAIProvider(AIProvider):
    """OpenAI provider implementation."""

    def __init__(self, **kwargs) -> None:
        """Initialize OpenAI provider."""
        self.client = OpenAI(**kwargs)
        self.default_model = OPENAI_MODELS[0]  # gpt-4.1

    def get_supported_models(self) -> list[str]:
        """Get list of supported OpenAI models."""
        return OPENAI_MODELS

    def _convert_mcp_tools_to_openai_tools(
        self, mcp_tools: list[Tool]
    ) -> list[dict[str, Iterable[ChatCompletionToolUnionParam]]]:
        """
        Convert MCP tools to OpenAI tool format.

        Args:
            mcp_tools: List of MCP Tool objects

        Returns:
            List of OpenAI tool dictionaries
        """
        openai_tools = []

        for mcp_tool in mcp_tools:
            # Convert MCP tool schema to OpenAI function format
            tool = {
                "type": "function",
                "function": {
                    "name": mcp_tool.name,
                    "description": mcp_tool.description or "",
                    "parameters": {
                        "type": "object",
                        "properties": mcp_tool.inputSchema.get("properties", {}),
                        "required": mcp_tool.inputSchema.get("required", []),
                    },
                },
            }
            openai_tools.append(tool)

        return openai_tools

    async def process_query(
        self,
        query: str,
        tools: list[Tool],
        tool_executor: Callable[[str, dict], Awaitable[CallToolResult]],
        logger: ToolUsageLogger,
        server_manager: MCPServerManager,
        model: str | None = None,
    ) -> str:
        """
        Process a query using OpenAI with tool support.

        Args:
            query: User query to process
            tools: List of available MCP tools
            tool_executor: Callable that executes tool calls (tool_name, tool_args) -> result
            logger: Logger for tracking tool usage
            server_manager: Server manager for getting metadata
            model: Optional model name (uses default if not specified)

        Returns:
            Final response text after processing tool calls
        """
        model = model or self.default_model

        # Convert MCP tools to OpenAI format
        openai_tools = self._convert_mcp_tools_to_openai_tools(tools)

        # Initialize message history
        messages = [{"role": "user", "content": query}]

        # Initial OpenAI API call
        response = self.client.chat.completions.create(
            model=model,
            messages=messages,
            tools=openai_tools,
        )

        # Process response and handle tool calls
        final_text = []

        # Loop to handle multiple rounds of function calling
        max_iterations = 10
        iteration = 0

        while iteration < max_iterations:
            iteration += 1

            message = response.choices[0].message

            # Add assistant's response to message history
            messages.append(message.model_dump(exclude_unset=True))

            # Check if the assistant wants to call tools
            if message.tool_calls:
                # Execute each tool call
                for tool_call in message.tool_calls:
                    tool_name = tool_call.function.name
                    tool_args = json.loads(tool_call.function.arguments)

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

                    # Execute the tool
                    try:
                        result = await tool_executor(tool_name, tool_args)

                        final_text.append(
                            f"[Calling tool {tool_name} with args {tool_args}]"
                        )

                        # Format result for OpenAI
                        try:
                            # MCP result.content is a list of content items
                            # Extract just the text from TextContent items
                            result_text = ""
                            for content_item in result.content:
                                if hasattr(content_item, "text"):
                                    result_text += content_item.text

                            tool_response = result_text

                            # Log successful tool call
                            record.complete(
                                output={"result": tool_response},
                                status="success",
                            )
                            await logger.log_tool_call(record)
                        except Exception as e:
                            tool_response = str(e)

                            # Log error in result processing
                            record.complete(
                                output=None,
                                status="error",
                                error_message=f"Result processing error: {str(e)}",
                            )
                            await logger.log_tool_call(record)

                        # Add tool response to messages
                        messages.append(
                            {
                                "role": "tool",
                                "tool_call_id": tool_call.id,
                                "content": tool_response,
                            }
                        )
                    except Exception as e:
                        # Log tool execution error
                        record.complete(
                            output=None,
                            status="error",
                            error_message=str(e),
                        )
                        await logger.log_tool_call(record)
                        raise

                # Get next response from OpenAI with tool results
                response = self.client.chat.completions.create(
                    model=model,
                    messages=messages,
                    tools=openai_tools,
                )
            else:
                # No more tool calls, extract final text response
                if message.content:
                    final_text.append(message.content)
                break

        return "\n".join(final_text)
