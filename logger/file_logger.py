"""File system based logger implementation."""

import asyncio
import json
from pathlib import Path

from logger.base import ToolUsageLogger
from logger.models import ToolCallRecord, ToolCallSession


class FileSystemLogger(ToolUsageLogger):
    """Logger that writes tool usage logs to the file system.

    This logger creates one JSON file per session and maintains a manifest
    of all sessions.

    Attributes:
        logs_dir: Directory where log files are stored
        sessions: In-memory cache of active sessions
    """

    def __init__(self, logs_dir: str = "logs"):
        """Initialize the file system logger.

        Args:
            logs_dir: Directory path for storing log files
        """
        self.logs_dir = Path(logs_dir)
        self.sessions: dict[str, ToolCallSession] = {}
        self.current_session_id: str | None = None
        self._ensure_logs_directory()

    def _ensure_logs_directory(self) -> None:
        """Create the logs directory if it doesn't exist."""
        self.logs_dir.mkdir(parents=True, exist_ok=True)

    def _get_session_file_path(self, session_id: str) -> Path:
        """Get the file path for a session's log file.

        Args:
            session_id: ID of the session

        Returns:
            Path to the session log file
        """
        return self.logs_dir / f"session_{session_id}.json"

    def _get_manifest_path(self) -> Path:
        """Get the file path for the manifest file.

        Returns:
            Path to the manifest file
        """
        return self.logs_dir / "manifest.json"

    async def _read_manifest(self) -> dict:
        """Read the manifest file asynchronously.

        Returns:
            Manifest data as a dictionary
        """
        manifest_path = self._get_manifest_path()
        if not manifest_path.exists():
            return {"sessions": []}

        def _read():
            with open(manifest_path, "r", encoding="utf-8") as f:
                return json.load(f)

        return await asyncio.to_thread(_read)

    async def _write_manifest(self, manifest: dict) -> None:
        """Write the manifest file asynchronously.

        Args:
            manifest: Manifest data to write
        """
        manifest_path = self._get_manifest_path()

        def _write():
            with open(manifest_path, "w", encoding="utf-8") as f:
                json.dump(manifest, f, indent=2)

        await asyncio.to_thread(_write)

    async def _add_session_to_manifest(self, session: ToolCallSession) -> None:
        """Add a session to the manifest.

        Args:
            session: Session to add to manifest
        """
        manifest = await self._read_manifest()

        # Add session metadata to manifest
        session_info = {
            "session_id": session.session_id,
            "started_at": session.started_at.isoformat(),
            "ended_at": session.ended_at.isoformat() if session.ended_at else None,
            "provider_used": session.provider_used,
            "total_calls": session.total_calls,
            "file": f"session_{session.session_id}.json",
        }

        # Update existing or add new
        sessions = manifest.get("sessions", [])
        existing_index = next(
            (
                i
                for i, s in enumerate(sessions)
                if s["session_id"] == session.session_id
            ),
            None,
        )

        if existing_index is not None:
            sessions[existing_index] = session_info
        else:
            sessions.append(session_info)

        manifest["sessions"] = sessions
        await self._write_manifest(manifest)

    async def _write_session_file(self, session: ToolCallSession) -> None:
        """Write a session to its log file.

        Args:
            session: Session to write
        """
        session_path = self._get_session_file_path(session.session_id)

        def _write():
            with open(session_path, "w", encoding="utf-8") as f:
                json.dump(session.to_dict(), f, indent=2)

        await asyncio.to_thread(_write)

    async def _read_session_file(self, session_id: str) -> dict | None:
        """Read a session from its log file.

        Args:
            session_id: ID of the session to read

        Returns:
            Session data as dictionary or None if not found
        """
        session_path = self._get_session_file_path(session_id)
        if not session_path.exists():
            return None

        def _read():
            with open(session_path, "r", encoding="utf-8") as f:
                return json.load(f)

        return await asyncio.to_thread(_read)

    async def log_tool_call(self, record: ToolCallRecord) -> None:
        """Log a tool call record to the current session.

        Args:
            record: Tool call record to log
        """
        if not self.current_session_id:
            raise ValueError("No active session. Call start_session() first.")

        session = self.sessions.get(self.current_session_id)
        if not session:
            raise ValueError(f"Session {self.current_session_id} not found.")

        session.add_tool_call(record)

        # Persist the updated session
        await self._write_session_file(session)
        await self._add_session_to_manifest(session)

    async def start_session(self, provider_used: str = "") -> str:
        """Start a new logging session.

        Args:
            provider_used: Name of the AI provider being used

        Returns:
            Session ID for the new session
        """
        session = ToolCallSession.create(provider_used=provider_used)
        self.current_session_id = session.session_id
        self.sessions[session.session_id] = session

        # Write initial session file and update manifest
        await self._write_session_file(session)
        await self._add_session_to_manifest(session)

        return session.session_id

    async def end_session(self, session_id: str) -> None:
        """End a logging session.

        Args:
            session_id: ID of the session to end
        """
        session = self.sessions.get(session_id)
        if not session:
            # Try to load from file
            session_data = await self._read_session_file(session_id)
            if not session_data:
                return
            # Session exists in file but not in memory, skip ending
            return

        session.end_session()

        # Write final session file and update manifest
        await self._write_session_file(session)
        await self._add_session_to_manifest(session)

    async def get_session_history(self, session_id: str) -> ToolCallSession | None:
        """Get the history for a specific session.

        Args:
            session_id: ID of the session to retrieve

        Returns:
            ToolCallSession object or None if not found
        """
        # Check in-memory cache first
        if session_id in self.sessions:
            return self.sessions[session_id]

        # Try to load from file
        session_data = await self._read_session_file(session_id)
        if not session_data:
            return None

        # Note: Full reconstruction from file would require deserializing
        # all nested objects. For simplicity, return the in-memory version
        # or None if not available
        return None

    async def add_tool_call_to_session(
        self, session_id: str, record: ToolCallRecord
    ) -> None:
        """Add a tool call record to a session and persist it.

        Args:
            session_id: ID of the session
            record: Tool call record to add
        """
        session = self.sessions.get(session_id)
        if not session:
            return

        session.add_tool_call(record)

        # Persist the updated session
        await self._write_session_file(session)
        await self._add_session_to_manifest(session)

    async def export_logs(self, format: str = "json") -> str:
        """Export all logs in the specified format.

        Args:
            format: Output format (currently only "json" is supported)

        Returns:
            Exported logs as a string
        """
        if format != "json":
            raise ValueError(f"Unsupported format: {format}")

        manifest = await self._read_manifest()
        return json.dumps(manifest, indent=2)
