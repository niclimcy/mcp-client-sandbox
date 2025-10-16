"""Data models for tool usage logging."""

import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal


@dataclass
class ServerMetadata:
    """Metadata about an MCP server.

    Attributes:
        name: Unique name/identifier for the server
        type: Type of server connection (stdio or http)
        connection_details: Dictionary containing connection information
            - For stdio: {"command": str, "args": list[str]}
            - For http: {"url": str}
        registered_at: Timestamp when the server was registered
    """

    name: str
    type: Literal["stdio", "http"]
    connection_details: dict[str, str | list[str]]
    registered_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> dict:
        """Convert to dictionary representation.

        Returns:
            Dictionary containing all metadata fields
        """
        return {
            "name": self.name,
            "type": self.type,
            "connection_details": self.connection_details,
            "registered_at": self.registered_at.isoformat(),
        }

    def to_json(self) -> str:
        """Convert to JSON string.

        Returns:
            JSON string representation
        """
        return json.dumps(self.to_dict(), indent=2)


@dataclass
class ToolCallRecord:
    """Record of a single tool call execution.

    Attributes:
        call_id: Unique identifier for this tool call
        tool_name: Namespaced tool name (server__tool_name)
        server_metadata: Metadata about the server that provided the tool
        input_args: Arguments passed to the tool
        output: Result returned by the tool
        status: Execution status (success, error, or timeout)
        error_message: Error message if status is error
        started_at: Timestamp when execution started
        completed_at: Timestamp when execution completed
        duration_ms: Execution duration in milliseconds
    """

    call_id: str
    tool_name: str
    server_metadata: ServerMetadata
    input_args: dict
    output: dict | str | None
    status: Literal["success", "error", "timeout"]
    error_message: str | None = None
    started_at: datetime = field(default_factory=datetime.now)
    completed_at: datetime | None = None
    duration_ms: float = 0.0

    @staticmethod
    def create(
        tool_name: str,
        server_metadata: ServerMetadata,
        input_args: dict,
    ) -> "ToolCallRecord":
        """Create a new tool call record with generated UUID.

        Args:
            tool_name: Namespaced tool name
            server_metadata: Server metadata
            input_args: Tool arguments

        Returns:
            New ToolCallRecord instance
        """
        return ToolCallRecord(
            call_id=str(uuid.uuid4()),
            tool_name=tool_name,
            server_metadata=server_metadata,
            input_args=input_args,
            output=None,
            status="success",  # Will be updated on completion
        )

    def complete(
        self,
        output: dict | str | None,
        status: Literal["success", "error", "timeout"],
        error_message: str | None = None,
    ) -> None:
        """Mark the tool call as completed and calculate duration.

        Args:
            output: Tool execution result
            status: Final execution status
            error_message: Error message if status is error
        """
        self.completed_at = datetime.now()
        self.output = output
        self.status = status
        self.error_message = error_message

        if self.completed_at:
            delta = self.completed_at - self.started_at
            self.duration_ms = delta.total_seconds() * 1000

    @property
    def duration_seconds(self) -> float:
        """Get execution duration in seconds.

        Returns:
            Duration in seconds
        """
        return self.duration_ms / 1000

    def to_dict(self) -> dict:
        """Convert to dictionary representation.

        Returns:
            Dictionary containing all record fields
        """
        return {
            "call_id": self.call_id,
            "tool_name": self.tool_name,
            "server_metadata": self.server_metadata.to_dict(),
            "input_args": self.input_args,
            "output": self.output,
            "status": self.status,
            "error_message": self.error_message,
            "started_at": self.started_at.isoformat(),
            "completed_at": (
                self.completed_at.isoformat() if self.completed_at else None
            ),
            "duration_ms": self.duration_ms,
        }

    def to_json(self) -> str:
        """Convert to JSON string.

        Returns:
            JSON string representation
        """
        return json.dumps(self.to_dict(), indent=2)


@dataclass
class ToolCallSession:
    """Container for multiple tool calls in a session.

    Attributes:
        session_id: Unique identifier for this session
        started_at: Timestamp when session started
        tool_calls: List of tool call records in this session
        provider_used: Name of the AI provider used
        ended_at: Timestamp when session ended (None if still active)
    """

    session_id: str
    started_at: datetime
    tool_calls: list[ToolCallRecord] = field(default_factory=list)
    provider_used: str = ""
    ended_at: datetime | None = None

    @staticmethod
    def create(provider_used: str = "") -> "ToolCallSession":
        """Create a new session with generated UUID.

        Args:
            provider_used: Name of the AI provider

        Returns:
            New ToolCallSession instance
        """
        return ToolCallSession(
            session_id=str(uuid.uuid4()),
            started_at=datetime.now(),
            provider_used=provider_used,
        )

    def add_tool_call(self, record: ToolCallRecord) -> None:
        """Add a tool call record to this session.

        Args:
            record: Tool call record to add
        """
        self.tool_calls.append(record)

    def end_session(self) -> None:
        """Mark the session as ended."""
        self.ended_at = datetime.now()

    @property
    def total_calls(self) -> int:
        """Get total number of tool calls in this session.

        Returns:
            Total number of calls
        """
        return len(self.tool_calls)

    @property
    def successful_calls(self) -> int:
        """Get number of successful tool calls.

        Returns:
            Number of successful calls
        """
        return sum(1 for call in self.tool_calls if call.status == "success")

    @property
    def failed_calls(self) -> int:
        """Get number of failed tool calls.

        Returns:
            Number of failed calls
        """
        return sum(1 for call in self.tool_calls if call.status == "error")

    def to_dict(self) -> dict:
        """Convert to dictionary representation.

        Returns:
            Dictionary containing all session fields
        """
        return {
            "session_id": self.session_id,
            "started_at": self.started_at.isoformat(),
            "ended_at": self.ended_at.isoformat() if self.ended_at else None,
            "provider_used": self.provider_used,
            "total_calls": self.total_calls,
            "successful_calls": self.successful_calls,
            "failed_calls": self.failed_calls,
            "tool_calls": [call.to_dict() for call in self.tool_calls],
        }

    def to_json(self) -> str:
        """Convert to JSON string.

        Returns:
            JSON string representation
        """
        return json.dumps(self.to_dict(), indent=2)
