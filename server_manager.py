import json
from contextlib import AsyncExitStack
from typing import Optional
import os
from dotenv import load_dotenv
import re

from mcp import ClientSession, StdioServerParameters, Tool
from mcp.client.stdio import stdio_client
from mcp.client.streamable_http import streamablehttp_client
from mcp.types import CallToolResult

from logger.models import ServerMetadata


class MCPServerManager:
    """Manages MCP server connections and tool execution"""

    def __init__(self, exit_stack: AsyncExitStack):
        """Initialize the server manager

        Args:
            exit_stack: AsyncExitStack for managing async context managers
        """
        self.sessions: dict[str, ClientSession] = {}
        self.server_metadata: dict[str, ServerMetadata] = {}
        self.exit_stack = exit_stack

    async def register_all_servers(self, config_path: str = "servers.json"):
        """Register all servers defined in the given config file

        Args:
            config_path: Path to the servers configuration JSON file
        """
        load_dotenv()
        with open(config_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        # Replace ${VAR_NAME} in all string fields recursively
        def substitute_env_vars(obj):
            if isinstance(obj, dict):
                return {k: substitute_env_vars(v) for k, v in obj.items()}
            elif isinstance(obj, list):
                return [substitute_env_vars(i) for i in obj]
            elif isinstance(obj, str):
                # repeatedly expand until no ${VAR} left (handles nested)
                pattern = re.compile(r"\$\{([^}]+)\}")
                expanded = obj
                prev = None
                while prev != expanded:
                    prev = expanded
                    expanded = pattern.sub(lambda m: os.getenv(m.group(1), ""), expanded)
                return expanded
            else:
                return obj

        data = substitute_env_vars(data)

        servers = data.get("servers")
        if not isinstance(servers, dict):
            raise ValueError("Expected 'servers' to be a mapping of server definitions")

        for name, config in servers.items():
            if not isinstance(config, dict):
                raise ValueError(f"Server entry '{name}' must be an object")

            server_type = config.get("type")
            if server_type == "stdio":
                command = config.get("command")
                args = config.get("args", [])
                image = config.get("image")

                if not isinstance(command, str):
                    raise ValueError(f"Server '{name}' is missing a valid 'command'")
                if not isinstance(args, list):
                    raise ValueError(f"Server '{name}' must provide 'args' as a list")

                if image:
                    command, args = await self._with_docker(command, args, image)

                session = await self._register_stdio_server(command, args)
                self.sessions[name] = session

                # Store server metadata
                self.server_metadata[name] = ServerMetadata(
                    name=name,
                    type="stdio",
                    connection_details={"command": command, "args": args},
                )
            elif server_type == "http":
                url = config.get("url")
                if not isinstance(url, str):
                    raise ValueError(f"Server '{name}' is missing a valid 'url'")

                session = await self._register_http_server(name, url)
                self.sessions[name] = session

                # Store server metadata
                self.server_metadata[name] = ServerMetadata(
                    name=name, type="http", connection_details={"url": url}
                )
            else:
                raise ValueError(
                    f"Unsupported server type '{server_type}' for '{name}'"
                )

        print("\nTools Found:")
        for server, session in self.sessions.items():
            response = await session.list_tools()
            for tool in response.tools:
                namespaced_name = f"{server}__{tool.name}"
                print(f"- {namespaced_name}")

    async def _with_docker(self, command, args: list[str], image: str):
        print(f"Spawning stdio server in Docker image '{image}'")
        docker_cmd = ["docker", "run", "--rm", "-i", image, command, *args]

        return docker_cmd[0], docker_cmd[1:]

    async def _register_stdio_server(
        self, command: str, args: list[str]
    ) -> ClientSession:
        """Register a stdio server

        Args:
            command: Command to start the server (e.g., "python" or "node")
            args: Arguments for the command (e.g., path to the server script)
        Returns:
            ClientSession connected to the server
        """
        server_params = StdioServerParameters(command=command, args=args, env=None)
        stdio_transport = await self.exit_stack.enter_async_context(
            stdio_client(server_params)
        )
        stdio, write = stdio_transport
        session = await self.exit_stack.enter_async_context(ClientSession(stdio, write))
        await session.initialize()
        return session

    async def _register_http_server(self, name: str, url: str) -> ClientSession:
        """Register an HTTP server using streamable HTTP transport

        Args:
            name: Name identifier for the server
            url: URL of the HTTP server (e.g., "http://localhost:8000/mcp")
        Returns:
            ClientSession connected to the server
        """
        # Connect to a streamable HTTP server
        http_transport = await self.exit_stack.enter_async_context(
            streamablehttp_client(url)
        )
        read_stream, write_stream, _ = http_transport

        # Create a session using the client streams
        session = await self.exit_stack.enter_async_context(
            ClientSession(read_stream, write_stream)
        )

        # Initialize the connection
        await session.initialize()

        return session

    async def get_all_registered_tools(self) -> list[Tool]:
        """Get a list of all registered tools across all sessions with namespaced names

        Tools are renamed to include the server name to avoid conflicts:
        Format: {server_name}__{original_tool_name}
        Example: weather__get_forecast, database__query
        """
        all_tools: list[Tool] = []
        for server_name, session in self.sessions.items():
            response = await session.list_tools()
            for tool in response.tools:
                # Create a new tool with namespaced name
                # Store original name in description for reference
                namespaced_tool = Tool(
                    name=f"{server_name}__{tool.name}",
                    description=f"[{server_name}] {tool.description or ''}".strip(),
                    inputSchema=tool.inputSchema,
                )
                all_tools.append(namespaced_tool)
        return all_tools

    def _parse_namespaced_tool_name(self, namespaced_name: str) -> tuple[str, str]:
        """Parse a namespaced tool name into server name and original tool name

        Args:
            namespaced_name: Tool name in format {server_name}__{tool_name}

        Returns:
            Tuple of (server_name, original_tool_name)

        Raises:
            ValueError: If the tool name is not properly namespaced
        """
        if "__" not in namespaced_name:
            raise ValueError(
                f"Tool name '{namespaced_name}' is not properly namespaced. "
                f"Expected format: {{server_name}}__{{tool_name}}"
            )

        parts = namespaced_name.split("__", 1)
        if len(parts) != 2:
            raise ValueError(f"Invalid namespaced tool name: {namespaced_name}")

        return parts[0], parts[1]

    async def _find_registered_server_by_tool(
        self, namespaced_tool_name: str
    ) -> Optional[ClientSession]:
        """Find a registered server by namespaced tool name

        Args:
            namespaced_tool_name: Tool name in format {server_name}__{tool_name}

        Returns:
            ClientSession for the server, or None if not found
        """
        try:
            server_name, _ = self._parse_namespaced_tool_name(namespaced_tool_name)
            return self.sessions.get(server_name)
        except ValueError:
            # Try to find by original name (backward compatibility)
            for session in self.sessions.values():
                response = await session.list_tools()
                for tool in response.tools:
                    if tool.name == namespaced_tool_name:
                        return session
            return None

    async def execute_tool(
        self, namespaced_tool_name: str, tool_args: dict
    ) -> CallToolResult | None:
        """Execute a tool by finding its session and calling it with the original tool name

        Args:
            namespaced_tool_name: Tool name in format {server_name}__{tool_name}
            tool_args: Arguments to pass to the tool

        Returns:
            Result from the tool execution

        Raises:
            ValueError: If the tool or server is not found
        """
        session = await self._find_registered_server_by_tool(namespaced_tool_name)
        if not session:
            raise ValueError(
                f"Tool '{namespaced_tool_name}' not found in any registered session"
            )

        # Extract the original tool name to call on the server
        try:
            _, original_tool_name = self._parse_namespaced_tool_name(
                namespaced_tool_name
            )
        except ValueError:
            # Fallback for non-namespaced names (backward compatibility)
            original_tool_name = namespaced_tool_name

        return await session.call_tool(original_tool_name, tool_args)

    def get_server_metadata(self, server_name: str) -> ServerMetadata | None:
        """Get metadata for a specific server.

        Args:
            server_name: Name of the server

        Returns:
            ServerMetadata object or None if server not found
        """
        return self.server_metadata.get(server_name)

    def get_server_metadata_by_tool_name(
        self, namespaced_tool_name: str
    ) -> ServerMetadata | None:
        """Get metadata for the server that provides a tool.

        Args:
            namespaced_tool_name: Tool name in format {server_name}__{tool_name}

        Returns:
            ServerMetadata object or None if server not found
        """
        try:
            server_name, _ = self._parse_namespaced_tool_name(namespaced_tool_name)
            return self.server_metadata.get(server_name)
        except ValueError:
            return None
