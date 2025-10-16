from abc import ABC, abstractmethod
from typing import Awaitable, Callable

from mcp import Tool
from mcp.types import CallToolResult


class AIProvider(ABC):
    """Base class for AI providers supporting MCP tool integration."""

    default_model: str

    @abstractmethod
    def __init__(self, **kwargs) -> None:
        """Initialize the AI provider with necessary credentials and configuration."""
        pass

    @abstractmethod
    def get_supported_models(self) -> list[str]:
        """Get list of supported model names for this provider."""
        pass

    @abstractmethod
    async def process_query(
        self,
        query: str,
        tools: list[Tool],
        model: str | None = None,
        tool_executor: Callable[[str, dict], Awaitable[CallToolResult]] | None = None,
    ) -> str:
        """
        Process a query using available tools.

        Args:
            query: User query to process
            tools: List of available MCP tools
            model: Optional model name (uses default if not specified)

        Returns:
            Final response text after processing tool calls
        """
        pass
