#!/usr/bin/env python3
"""
Pretty print MCP client logs and tool call records.
"""

import json
import sys
from pathlib import Path
from datetime import datetime
from logger.models import ToolCallSession, ToolCallRecord, ServerMetadata

TIMESTAMP_FORMAT = "%Y-%m-%d %H:%M:%S"


def _format_timestamp(dt: datetime | None) -> str:
    """Format a datetime object to human-readable string.

    Args:
        dt: Datetime object to format

    Returns:
        Formatted timestamp string or 'N/A' if None
    """
    return dt.strftime(TIMESTAMP_FORMAT) if dt else "N/A"


def _deserialize_session(data: dict) -> ToolCallSession:
    """Deserialize a session dictionary into a ToolCallSession object.

    Args:
        data: Dictionary containing session data

    Returns:
        ToolCallSession object
    """
    session = ToolCallSession(
        session_id=data["session_id"],
        started_at=datetime.fromisoformat(data["started_at"]),
        provider_used=data.get("provider_used", ""),
        ended_at=(
            datetime.fromisoformat(data["ended_at"]) if data.get("ended_at") else None
        ),
    )

    # Deserialize tool calls
    for call_data in data.get("tool_calls", []):
        server_metadata = ServerMetadata(
            name=call_data["server_metadata"]["name"],
            type=call_data["server_metadata"]["type"],
            connection_details=call_data["server_metadata"].get(
                "connection_details", {}
            ),
            registered_at=datetime.fromisoformat(
                call_data["server_metadata"].get(
                    "registered_at", datetime.now().isoformat()
                )
            ),
        )

        call_record = ToolCallRecord(
            call_id=call_data["call_id"],
            tool_name=call_data["tool_name"],
            server_metadata=server_metadata,
            input_args=call_data.get("input_args", {}),
            output=call_data.get("output"),
            status=call_data["status"],
            error_message=call_data.get("error_message"),
            started_at=datetime.fromisoformat(call_data["started_at"]),
            completed_at=(
                datetime.fromisoformat(call_data["completed_at"])
                if call_data.get("completed_at")
                else None
            ),
            duration_ms=call_data.get("duration_ms", 0.0),
        )
        session.add_tool_call(call_record)

    return session


def _print_session_calls(session: ToolCallSession) -> None:
    """Print session summary and tool calls."""
    if not session.tool_calls:
        return

    print("  Tool Calls:")
    for j, call in enumerate(session.tool_calls, 1):
        print(f"    {j}. {call.tool_name}")
        print(
            f"       Server: {call.server_metadata.name} ({call.server_metadata.type})"
        )
        print(f"       Status: {call.status}")
        print(f"       Duration: {call.duration_ms:.2f}ms")
        if call.error_message:
            print(f"       Error: {call.error_message}")
    print()


def view_session_logs() -> None:
    """Display all logged sessions and their details."""
    logs_dir = Path("logs")

    if not logs_dir.exists():
        print("No logs directory found. Run the client first to generate logs.")
        return

    manifest_path = logs_dir / "manifest.json"
    if not manifest_path.exists():
        print("No manifest file found. No sessions have been logged yet.")
        return

    with open(manifest_path, "r", encoding="utf-8") as f:
        sessions: list[dict] = json.load(f).get("sessions", [])

    if not sessions:
        print("No sessions found in manifest.")
        return

    print(f"Found {len(sessions)} session(s)")

    for i, session_info in enumerate(sessions, 1):
        print(f"\nSession {i}:")
        print(f"  ID: {session_info['session_id']}")
        print(f"  Provider: {session_info['provider_used']}")
        print(
            f"  Started: {_format_timestamp(datetime.fromisoformat(session_info['started_at']))}"
        )
        ended = session_info.get("ended_at")
        print(
            f"  Ended: {_format_timestamp(datetime.fromisoformat(ended)) if ended else 'N/A'}"
        )
        print(f"  Total Calls: {session_info['total_calls']}")
        print()

        # Read and display full session details
        session_file = logs_dir / session_info["file"]
        if session_file.exists():
            with open(session_file, "r", encoding="utf-8") as f:
                _print_session_calls(_deserialize_session(json.load(f)))


def _print_session_details(session: ToolCallSession) -> None:
    """Print detailed information about a session and its tool calls."""
    print(f"Session ID: {session.session_id}")
    print(f"Provider: {session.provider_used}")
    print(f"Started: {_format_timestamp(session.started_at)}")
    print(f"Ended: {_format_timestamp(session.ended_at)}")
    print(f"Total Calls: {session.total_calls}")
    print(f"Successful: {session.successful_calls}")
    print(f"Failed: {session.failed_calls}")
    print()

    if not session.tool_calls:
        return

    print("Tool Calls:")
    for i, call in enumerate(session.tool_calls, 1):
        print(f"\n  {i}. {call.tool_name}")
        print(f"     Call ID: {call.call_id}")
        print(f"     Server: {call.server_metadata.name} ({call.server_metadata.type})")
        print(f"     Status: {call.status}")
        print(f"     Duration: {call.duration_ms:.2f}ms")
        print(f"     Started: {_format_timestamp(call.started_at)}")
        if call.completed_at:
            print(f"     Completed: {_format_timestamp(call.completed_at)}")
        if call.error_message:
            print(f"     Error: {call.error_message}")
        if call.input_args:
            print(f"     Input: {json.dumps(call.input_args, indent=8)}")
        if call.output:
            output = (
                call.output
                if isinstance(call.output, dict)
                else {"result": call.output}
            )
            print(f"     Output: {json.dumps(output, indent=8)}")


def view_specific_session(session_id: str) -> None:
    """Display detailed information for a specific session."""
    logs_dir = Path("logs")
    session_file = logs_dir / f"session_{session_id}.json"

    if not session_file.exists():
        print(f"Session file not found: {session_file}")
        return

    with open(session_file, "r", encoding="utf-8") as f:
        session = _deserialize_session(json.load(f))

    print(f"Session Details: {session_id}")

    _print_session_details(session)


def main() -> None:
    """Main entry point for viewing logs."""
    print("MCP Tool Usage Logs")

    if len(sys.argv) > 1:
        view_specific_session(sys.argv[1])
    else:
        view_session_logs()


if __name__ == "__main__":
    main()
