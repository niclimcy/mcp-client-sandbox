from typing import Optional
from contextlib import AsyncExitStack
from mcp import ClientSession, StdioServerParameters, Tool
from mcp.client.stdio import stdio_client
from mcp.client.streamable_http import streamablehttp_client
from dotenv import load_dotenv
import json
import asyncio

from providers.anthropic import ANTHROPIC_MODELS, AnthropicProvider
from providers.base import AIProvider
from providers.google_genai import GOOGLE_GENAI_MODELS, GoogleGenAIProvider

load_dotenv()  # load environment variables from .env


class MCPClient:
    def __init__(self, provider: AIProvider | None = None):
        # Initialize session and client objects
        self.sessions: dict[str, ClientSession] = {}
        self.exit_stack = AsyncExitStack()
        self.provider = provider or GoogleGenAIProvider()

    async def _register_all_servers(self, config_path: str = "servers.json"):
        """Register all servers defined in the given config file"""

        with open(config_path, "r", encoding="utf-8") as f:
            data = json.load(f)

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

                if not isinstance(command, str):
                    raise ValueError(f"Server '{name}' is missing a valid 'command'")
                if not isinstance(args, list):
                    raise ValueError(f"Server '{name}' must provide 'args' as a list")

                session = await self._register_stdio_server(command, args)
                self.sessions[name] = session
            elif server_type == "http":
                url = config.get("url")
                if not isinstance(url, str):
                    raise ValueError(f"Server '{name}' is missing a valid 'url'")

                session = await self._register_http_server(name, url)
                self.sessions[name] = session
            else:
                raise ValueError(
                    f"Unsupported server type '{server_type}' for '{name}'"
                )
        print("\nTools Found:")
        for server, session in self.sessions.items():
            response = await session.list_tools()
            for tool in response.tools:
                print(f"- {tool.name} ({server})")

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

    async def _get_all_registered_tools(self) -> list[Tool]:
        """Get a list of all registered tools across all sessions"""
        all_tools: list[Tool] = []
        for session in self.sessions.values():
            response = await session.list_tools()
            all_tools.extend(response.tools)
        return all_tools

    async def _find_registered_server_by_tool(
        self, tool_name: str
    ) -> Optional[ClientSession]:
        """Find a registered tool by name across all sessions"""
        for session in self.sessions.values():
            response = await session.list_tools()
            for tool in response.tools:
                if tool.name == tool_name:
                    return session
        return None

    async def _execute_tool(self, tool_name: str, tool_args: dict) -> any:
        """Execute a tool by finding its session and calling it."""
        session = await self._find_registered_server_by_tool(tool_name)
        if session:
            return await session.call_tool(tool_name, tool_args)
        raise ValueError(f"Tool {tool_name} not found in any registered session")

    async def _process_query(self, query: str) -> str:
        """Process a query using all available tools"""
        tools = await self._get_all_registered_tools()

        # Use the provider to process the query with tool execution
        return await self.provider.process_query(
            query=query, tools=tools, tool_executor=self._execute_tool
        )

    def _get_available_models(self) -> dict[str, tuple[AIProvider, str]]:
        """
        Get all available models from all providers.

        Returns:
            Dict mapping option number to (provider_class, model_name)
        """
        models = {}
        option = 1

        for model in GOOGLE_GENAI_MODELS:
            models[option] = (GoogleGenAIProvider, model)
            option += 1

        for model in ANTHROPIC_MODELS:
            models[option] = (AnthropicProvider, model)
            option += 1

        return models

    def _display_available_models(self) -> None:
        """Display all available models grouped by provider"""
        print("\nAvailable models:")
        print("\nGoogle GenAI:")
        option = 1
        for model in GOOGLE_GENAI_MODELS:
            print(f"[{option}] {model}")
            option += 1

        print("\nAnthropic:")
        for model in ANTHROPIC_MODELS:
            print(f"[{option}] {model}")
            option += 1

    async def _switch_model(self) -> None:
        """Handle model switching based on user input"""
        self._display_available_models()

        try:
            # Get user input in a thread
            choice_str = await asyncio.to_thread(input, "\nSelect model number: ")
            choice = int(choice_str.strip())

            models = self._get_available_models()
            if choice not in models:
                print(
                    f"Invalid choice. Please select a number between 1 and {len(models)}"
                )
                return

            provider_class, model_name = models[choice]

            # Create new provider instance
            self.provider = provider_class()
            print(
                f"\nModel switched to {model_name} ({provider_class.__name__.rstrip('Provider')})"
            )

        except ValueError:
            print("Invalid input. Please enter a valid number.")
        except Exception as e:
            print(f"Error switching model: {str(e)}")

    async def run(self):
        """Run an interactive chat loop"""
        print("\nMCP Client Started!")
        print(f"Current Model: {self.provider.default_model}")
        print("\nType '/q' or use Ctrl+D to quit")
        print("Type '/model' to switch models")
        await self._register_all_servers()

        while True:
            try:
                # Use asyncio.to_thread for proper cancellation support
                query = await asyncio.to_thread(input, "\n> ")

                if query.strip() == "/model":
                    await self._switch_model()
                    continue

                if query.strip() == "/q":
                    print("\nExiting...")
                    break

                response = await self._process_query(query)
                print("\n" + response)

            except EOFError:
                print("\nExiting...")
                break
            except Exception as e:
                print(f"\nError: {str(e)}")

    async def cleanup(self):
        """Clean up resources"""
        await self.exit_stack.aclose()
