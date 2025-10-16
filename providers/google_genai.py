from typing import Any

from google import genai
from google.genai import types
from mcp import Tool

from providers.base import AIProvider


GOOGLE_GENAI_MODELS = [
    "gemini-flash-lite-latest",
    "gemini-2.5-flash-lite",
    "gemini-2.5-flash",
    "gemini-2.5-pro",
]


class GoogleGenAIProvider(AIProvider):
    """Google Generative AI provider implementation."""

    def __init__(self, **kwargs: Any) -> None:
        """Initialize Google GenAI provider."""
        self.client = genai.Client(**kwargs)
        self.default_model = GOOGLE_GENAI_MODELS[0]  # gemini-2.5-flash-lite

    def get_supported_models(self) -> list[str]:
        """Get list of supported Google GenAI models."""
        return GOOGLE_GENAI_MODELS

    def _convert_mcp_tools_to_genai_tools(
        self, mcp_tools: list[Tool]
    ) -> list[types.Tool]:
        """
        Convert MCP tools to Google GenAI tool format.

        Args:
            mcp_tools: List of MCP Tool objects

        Returns:
            List of Google GenAI Tool objects
        """
        genai_tools = []

        for mcp_tool in mcp_tools:
            # Convert MCP tool schema to GenAI FunctionDeclaration
            function_declaration = types.FunctionDeclaration(
                name=mcp_tool.name,
                description=mcp_tool.description or "",
                parameters=types.Schema(
                    type="OBJECT",
                    properties={
                        prop_name: types.Schema(
                            type=prop_schema.get("type", "STRING").upper(),
                            description=prop_schema.get("description", ""),
                        )
                        for prop_name, prop_schema in mcp_tool.inputSchema.get(
                            "properties", {}
                        ).items()
                    },
                    required=mcp_tool.inputSchema.get("required", []),
                ),
            )

            tool = types.Tool(function_declarations=[function_declaration])
            genai_tools.append(tool)

        return genai_tools

    async def process_query(
        self,
        query: str,
        tools: list[Tool],
        model: str | None = None,
        tool_executor: Any = None,
    ) -> str:
        """
        Process a query using Google GenAI with tool support.

        Args:
            query: User query to process
            tools: List of available MCP tools
            model: Optional model name (uses default if not specified)
            tool_executor: Callable that executes tool calls (tool_name, tool_args) -> result

        Returns:
            Final response text after processing tool calls
        """
        model = model or self.default_model

        # Convert MCP tools to GenAI format
        genai_tools = self._convert_mcp_tools_to_genai_tools(tools)

        # Initial GenAI call with manual function calling
        response = self.client.models.generate_content(
            model=model,
            contents=query,
            config=types.GenerateContentConfig(
                tools=genai_tools,
                automatic_function_calling=types.AutomaticFunctionCallingConfig(
                    disable=True
                ),
            ),
        )

        # Process response and handle tool calls
        final_text = []
        contents_history = [
            types.Content(
                role="user",
                parts=[types.Part.from_text(text=query)],
            )
        ]

        # Loop to handle multiple rounds of function calling
        max_iterations = 10
        iteration = 0

        while response.function_calls and iteration < max_iterations:
            iteration += 1

            # Add model's response to history
            contents_history.append(response.candidates[0].content)

            # Execute each function call
            function_response_parts = []
            for function_call in response.function_calls:
                tool_name = function_call.name
                tool_args = dict(function_call.args)

                if tool_executor:
                    # Execute the tool
                    result = await tool_executor(tool_name, tool_args)

                    final_text.append(
                        f"[Calling tool {tool_name} with args {tool_args}]"
                    )

                    # Format result for GenAI
                    try:
                        # MCP result.content is a list of content items
                        # Extract just the text from TextContent items
                        result_text = ""
                        for content_item in result.content:
                            if hasattr(content_item, "text"):
                                result_text += content_item.text

                        function_response = {"result": result_text}
                    except Exception as e:
                        function_response = {"error": str(e)}

                    # Create function response part
                    function_response_part = types.Part.from_function_response(
                        name=tool_name,
                        response=function_response,
                    )

                    function_response_parts.append(function_response_part)

            # Add all function responses to history in a single content
            if function_response_parts:
                contents_history.append(
                    types.Content(role="tool", parts=function_response_parts)
                )

                # Get response from model with function results
                response = self.client.models.generate_content(
                    model=model,
                    contents=contents_history,
                    config=types.GenerateContentConfig(tools=genai_tools),
                )

        # Extract final text response
        if response.text:
            final_text.append(response.text)

        return "\n".join(final_text)
