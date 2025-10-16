"""Abstract base class for tool usage loggers."""

from abc import ABC, abstractmethod
from logger.models import ToolCallRecord, ToolCallSession


class ToolUsageLogger(ABC):
    """Abstract base class for logging tool usage.

    This class defines the interface that all logger implementations must follow.
    """

    current_session_id: str | None = None

    @abstractmethod
    async def log_tool_call(self, record: ToolCallRecord) -> None:
        """Log a tool call record to the current session.

        Args:
            record: Tool call record to log
        """
        pass

    @abstractmethod
    async def start_session(self, provider_used: str = "") -> str:
        """Start a new logging session.

        Args:
            provider_used: Name of the AI provider being used

        Returns:
            Session ID for the new session
        """
        pass

    @abstractmethod
    async def end_session(self, session_id: str) -> None:
        """End a logging session.

        Args:
            session_id: ID of the session to end
        """
        pass

    @abstractmethod
    async def get_session_history(self, session_id: str) -> ToolCallSession | None:
        """Get the history for a specific session.

        Args:
            session_id: ID of the session to retrieve

        Returns:
            ToolCallSession object or None if not found
        """
        pass

    @abstractmethod
    async def export_logs(self, format: str = "json") -> str:
        """Export all logs in the specified format.

        Args:
            format: Output format (currently only "json" is supported)

        Returns:
            Exported logs as a string
        """
        pass
