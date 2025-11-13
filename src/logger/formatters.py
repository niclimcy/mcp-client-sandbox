"""Utility functions for formatting log output."""

import json

from logger.models import ToolCallRecord, ToolCallSession


def format_record_as_json(record: ToolCallRecord) -> str:
    """Format a tool call record as JSON.

    Args:
        record: Tool call record to format

    Returns:
        Pretty-printed JSON string
    """
    return record.to_json()


def format_session_as_json(session: ToolCallSession) -> str:
    """Format a tool call session as JSON.

    Args:
        session: Tool call session to format

    Returns:
        Pretty-printed JSON string
    """
    return session.to_json()


def format_record_as_table(record: ToolCallRecord) -> str:
    """Format a tool call record as a readable table.

    Args:
        record: Tool call record to format

    Returns:
        Formatted table string
    """
    lines = [
        "=" * 80,
        f"Tool Call: {record.tool_name}",
        f"Call ID: {record.call_id}",
        f"Status: {record.status}",
        "-" * 80,
        f"Server: {record.server_metadata.name} ({record.server_metadata.type})",
        f"Connection: {record.server_metadata.connection_details}",
        "-" * 80,
        f"Input Arguments:",
        json.dumps(record.input_args, indent=2),
        "-" * 80,
        f"Output:",
        json.dumps(record.output, indent=2) if record.output else "None",
        "-" * 80,
        f"Started: {record.started_at.isoformat()}",
        f"Completed: {record.completed_at.isoformat() if record.completed_at else 'N/A'}",
        f"Duration: {record.duration_ms:.2f}ms ({record.duration_seconds:.3f}s)",
    ]

    if record.error_message:
        lines.extend(
            [
                "-" * 80,
                f"Error: {record.error_message}",
            ]
        )

    lines.append("=" * 80)
    return "\n".join(lines)


def sanitize_secrets(data: dict) -> dict:
    """Remove or mask sensitive information from a dictionary.

    Args:
        data: Dictionary that may contain sensitive data

    Returns:
        Dictionary with sensitive values masked
    """
    sensitive_keys = {
        "password",
        "passwd",
        "pwd",
        "secret",
        "api_key",
        "apikey",
        "api-key",
        "token",
        "access_token",
        "refresh_token",
        "auth",
        "authorization",
        "key",
        "private_key",
        "public_key",
        "credential",
        "credentials",
    }

    def mask_value(value: str) -> str:
        """Mask a sensitive value."""
        if len(value) <= 4:
            return "***"
        return f"{value[:2]}...{value[-2:]}"

    def sanitize_recursive(obj):
        """Recursively sanitize nested structures."""
        if isinstance(obj, dict):
            return {
                k: (
                    mask_value(v)
                    if isinstance(v, str) and k.lower() in sensitive_keys
                    else sanitize_recursive(v)
                )
                for k, v in obj.items()
            }
        elif isinstance(obj, list):
            return [sanitize_recursive(item) for item in obj]
        else:
            return obj

    return sanitize_recursive(data)
