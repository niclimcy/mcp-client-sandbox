from typing import Optional
from contextlib import AsyncExitStack
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from dotenv import load_dotenv
from anthropic import Anthropic
import json

load_dotenv()  # load environment variables from .env


class MCPClient:
    def __init__(self):
        # Initialize session and client objects
        self.sessions: dict[str, ClientSession] = {}
        self.exit_stack = AsyncExitStack()
        self.anthropic = Anthropic()

    async def register_all_servers(self, config_path: str = "servers.json"):
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

                session = await self.register_stdio_server(command, args)
                self.sessions[name] = session
            elif server_type == "http":
                url = config.get("url")
                if not isinstance(url, str):
                    raise ValueError(f"Server '{name}' is missing a valid 'url'")

                await self.register_http_server(url)
            else:
                raise ValueError(
                    f"Unsupported server type '{server_type}' for '{name}'"
                )
        print("\nTools Found:")
        for server, session in self.sessions.items():
            response = await session.list_tools()
            for tool in response.tools:
                print(f"- {tool.name} ({server})")

    async def register_stdio_server(
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

    async def register_http_server(self, url: str) -> None:
        """Register an HTTP server

        Args:
            url: URL of the HTTP server
        Returns:
            ClientSession connected to the server
        """

        # TODO: Implement HTTP server registration
        pass

    async def get_all_registered_tools(self):
        """Get a list of all registered tools across all sessions"""
        all_tools = []
        for session in self.sessions.values():
            response = await session.list_tools()
            all_tools.extend(response.tools)
        return all_tools

    async def find_registered_tool_server(
        self, tool_name: str
    ) -> Optional[ClientSession]:
        """Find the server session that has the specified tool registered"""
        for session in self.sessions.values():
            response = await session.list_tools()
            if any(tool.name == tool_name for tool in response.tools):
                return session
        return None

    async def process_query(self, query: str) -> str:
        """Process a query using all available tools"""
        messages = [{"role": "user", "content": query}]

        tools = await self.get_all_registered_tools()

        # Initial Claude API call
        response = self.anthropic.messages.create(
            model="claude-3-5-sonnet-20241022",
            max_tokens=1000,
            messages=messages,
            tools=tools,
        )

        # Process response and handle tool calls
        final_text = []

        assistant_message_content = []
        for content in response.content:
            if content.type == "text":
                final_text.append(content.text)
                assistant_message_content.append(content)
            elif content.type == "tool_use":
                tool_name = content.name
                tool_args = content.input

                session = await self.find_registered_tool_server(tool_name)
                if session is None:
                    raise ValueError(
                        f"Tool '{tool_name}' not found in any registered server"
                    )

                # Execute tool call
                result = await session.call_tool(tool_name, tool_args)
                final_text.append(f"[Calling tool {tool_name} with args {tool_args}]")

                assistant_message_content.append(content)
                messages.append(
                    {"role": "assistant", "content": assistant_message_content}
                )
                messages.append(
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "tool_result",
                                "tool_use_id": content.id,
                                "content": result.content,
                            }
                        ],
                    }
                )

                # Get next response from Claude
                response = self.anthropic.messages.create(
                    model="claude-3-5-sonnet-20241022",
                    max_tokens=1000,
                    messages=messages,
                    tools=tools,
                )

                final_text.append(response.content[0].text)

        return "\n".join(final_text)

    async def run(self):
        """Run an interactive chat loop"""
        print("\nMCP Client Started!")
        print("Type your queries or 'quit' to exit.")

        while True:
            try:
                query = input("\nQuery: ").strip()

                if query.lower() == "quit":
                    break

                response = await self.process_query(query)
                print("\n" + response)

            except Exception as e:
                print(f"\nError: {str(e)}")

    async def cleanup(self):
        """Clean up resources"""
        await self.exit_stack.aclose()
