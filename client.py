from contextlib import AsyncExitStack
from dotenv import load_dotenv
import asyncio

from server_manager import MCPServerManager
from providers.anthropic import ANTHROPIC_MODELS, AnthropicProvider
from providers.base import AIProvider
from providers.google_genai import GOOGLE_GENAI_MODELS, GoogleGenAIProvider
from providers.openai import OPENAI_MODELS, OpenAIProvider
from providers.openrouter import OPENROUTER_MODELS, OpenRouterProvider

load_dotenv()  # load environment variables from .env


class MCPClient:
    def __init__(self, provider: AIProvider | None = None):
        # Initialize session and client objects
        self.exit_stack = AsyncExitStack()
        self.server_manager = MCPServerManager(self.exit_stack)
        self.provider = provider or GoogleGenAIProvider()

    async def _process_query(self, query: str) -> str:
        """Process a query using all available tools"""
        tools = await self.server_manager.get_all_registered_tools()

        # Use the provider to process the query with tool execution
        return await self.provider.process_query(
            query=query, tools=tools, tool_executor=self.server_manager.execute_tool
        )

    def _get_available_models(
        self,
    ) -> dict[int, tuple[type[AIProvider], str] | tuple[type[AIProvider], None]]:
        """
        Get all available models from all providers.

        Returns:
            Dict mapping option number to (provider_class, model_name) or (provider_class, None) for custom
        """
        models = {}
        option = 1

        # Google GenAI models
        for model in GOOGLE_GENAI_MODELS:
            models[option] = (GoogleGenAIProvider, model)
            option += 1
        models[option] = (GoogleGenAIProvider, None)  # Custom model option
        option += 1

        # Anthropic models
        for model in ANTHROPIC_MODELS:
            models[option] = (AnthropicProvider, model)
            option += 1
        models[option] = (AnthropicProvider, None)  # Custom model option
        option += 1

        # OpenAI models
        for model in OPENAI_MODELS:
            models[option] = (OpenAIProvider, model)
            option += 1
        models[option] = (OpenAIProvider, None)  # Custom model option
        option += 1

        # OpenRouter models (typically just custom)
        for model in OPENROUTER_MODELS:
            models[option] = (OpenRouterProvider, model)
            option += 1
        models[option] = (OpenRouterProvider, None)  # Custom model option
        option += 1

        return models

    def _display_available_models(self) -> None:
        """Display all available models grouped by provider"""
        print("\nAvailable models:")
        option = 1

        print("\nGoogle GenAI:")
        for model in GOOGLE_GENAI_MODELS:
            print(f"[{option}] {model}")
            option += 1
        print(f"[{option}] Custom model (enter model string)")
        option += 1

        print("\nAnthropic:")
        for model in ANTHROPIC_MODELS:
            print(f"[{option}] {model}")
            option += 1
        print(f"[{option}] Custom model (enter model string)")
        option += 1

        print("\nOpenAI:")
        for model in OPENAI_MODELS:
            print(f"[{option}] {model}")
            option += 1
        print(f"[{option}] Custom model (enter model string)")
        option += 1

        print("\nOpenRouter:")
        for model in OPENROUTER_MODELS:
            print(f"[{option}] {model}")
            option += 1
        print(f"[{option}] Custom model (enter model string)")
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

            # If model_name is None, it's a custom model option
            if model_name is None:
                # Prompt for custom model string
                provider_name = provider_class.__name__.replace("Provider", "")

                prompt = f"Enter custom {provider_name} model string: "

                model_name = await asyncio.to_thread(input, prompt)
                model_name = model_name.strip()

                if not model_name:
                    print("Model name cannot be empty.")
                    return

            # Create new provider instance and set model
            self.provider = provider_class()
            self.provider.default_model = model_name
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
        await self.server_manager.register_all_servers()

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
