from abc import ABC, abstractmethod
from typing import Any, Awaitable, Callable

from mcp import Tool
from mcp.types import CallToolResult

from logger.base import ToolUsageLogger
from server_manager import MCPServerManager


class AIProvider(ABC):
    """Base class for AI providers supporting MCP tool integration."""

    _default_model: str
    current_model: str
    conversation_history: list[Any]

    @abstractmethod
    def __init__(self, **kwargs) -> None:
        """Initialize the AI provider with necessary credentials and configuration."""
        pass

    @abstractmethod
    def get_supported_models(self) -> list[str]:
        """Get list of supported model names for this provider."""
        pass

    def set_model(self, model_string):
        self.current_model = model_string

    def reset_conversation_history(self) -> None:
        """Reset the conversation history. Should be called when starting a new session."""
        self.conversation_history = []

    @abstractmethod
    async def process_query(
        self,
        query: str,
        tools: list[Tool],
        tool_executor: Callable[[str, dict], Awaitable[CallToolResult]],
        logger: "ToolUsageLogger",
        server_manager: "MCPServerManager",
    ) -> str:
        """
        Process a query using available tools.

        Args:
            query: User query to process
            tools: List of available MCP tools
            tool_executor: Callable that executes tool calls
            logger: Logger for tracking tool usage (tracks session internally)
            server_manager: Server manager for getting metadata

        Returns:
            Final response text after processing tool calls
        """
        pass
