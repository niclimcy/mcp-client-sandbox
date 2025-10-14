from abc import ABC, abstractmethod
from typing import Any


class AIProvider(ABC):
    """Base class for AI providers supporting MCP tool integration."""

    @abstractmethod
    def __init__(self, **kwargs: Any) -> None:
        """Initialize the AI provider with necessary credentials and configuration."""
        pass

    @abstractmethod
    def get_supported_models(self) -> list[str]:
        """Get list of supported model names for this provider."""
        pass

    @abstractmethod
    async def process_query(
        self, query: str, tools: list[Any], model: str | None = None
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
