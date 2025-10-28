import asyncio
from contextlib import AsyncExitStack

from dotenv import load_dotenv

from logger.base import ToolUsageLogger
from logger.file_logger import FileSystemLogger
from providers.anthropic import ANTHROPIC_MODELS, AnthropicProvider
from providers.base import AIProvider
from providers.google_genai import GOOGLE_GENAI_MODELS, GoogleGenAIProvider
from providers.openai import OPENAI_MODELS, OpenAIProvider
from providers.openrouter import OPENROUTER_MODELS, OpenRouterProvider
from server_manager import MCPServerManager

load_dotenv()  # load environment variables from .env


class MCPClient:
    def __init__(
        self,
        provider: AIProvider | None = None,
        logger: ToolUsageLogger | None = None,
        # testing parameters. Leave empty to run as default mode
        is_test_mode: bool = False,
        test_data: dict | None = None,
    ):
        # Initialize session and client objects
        self.exit_stack = AsyncExitStack()
        self.server_manager = MCPServerManager(self.exit_stack)
        self.provider = provider or GoogleGenAIProvider()
        self.logger = logger or FileSystemLogger()
        self.current_session_id: str | None = None

        self.is_test_mode = is_test_mode
        self.test_data = test_data

        if self.is_test_mode and self.test_data:
            print("MCPClient initialized in TEST MODE with loaded data.")
        else:
            self.is_test_mode = False  # Set back to false if no data found.

    async def _process_query(self, query: str) -> str:
        """Process a query using all available tools"""
        tools = await self.server_manager.get_all_registered_tools()

        # Use the provider to process the query with tool execution
        return await self.provider.process_query(
            query=query,
            tools=tools,
            tool_executor=self.server_manager.execute_tool,
            logger=self.logger,
            server_manager=self.server_manager,
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

    async def _auto_switch_model(
        self, choice: int, model_string: str | None = None
    ) -> None:
        """
        Automatically switch model based on an integer choice and optional custom string.
        Used for test mode initialization.
        """
        models = self._get_available_models()

        if choice not in models:
            print(
                f"\n⚠️ WARNING: Invalid model choice '{choice}' found in test data. Using default model."
            )
            return

        provider_class, model_name = models[choice]

        if model_name is None:
            final_model_name = model_string.strip() if model_string else None

            if not final_model_name:
                print(
                    f"\n⚠️ WARNING: Model choice '{choice}' is custom, but 'model_string' is empty. Using default model."
                )
                return
        else:
            final_model_name = model_name

        self.provider = provider_class()
        self.provider.set_model(final_model_name)
        print(
            f"\nModel switched to {final_model_name} ({provider_class.__name__.removesuffix('Provider')}) via test data."
        )

    async def _switch_model(self) -> None:
        """Handle model switching based on user input (interactive mode)"""
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

            # End current logging session
            if self.current_session_id:
                await self.logger.end_session(self.current_session_id)
                print(
                    f"Previous session ended. Logs saved to: logs/session_{self.current_session_id}.json"
                )

            # Create new provider instance and set model
            self.provider = provider_class()
            self.provider.set_model(model_name)

            print(
                f"\nModel switched to {model_name} ({provider_class.__name__.removesuffix('Provider')})"
            )

            # Start new logging session with new provider
            await self._log_cleanup(True)

        except ValueError:
            print("Invalid input. Please enter a valid number.")
        except Exception as e:
            print(f"Error switching model: {str(e)}")

    async def _log_cleanup(self, start_new_session=False):
        """Ends the logging session and prints the log path."""
        if self.current_session_id:
            context_message = "Test run complete. " if self.is_test_mode else ""
            await self.logger.end_session(self.current_session_id)
            print(
                f"\n{context_message}Logs saved to: logs/session_{self.current_session_id}.json"
            )

            if start_new_session:
                provider_name = self.provider.__class__.__name__.removesuffix(
                    "Provider"
                )
                self.current_session_id = await self.logger.start_session(
                    provider_used=provider_name
                )
                print(f"New logging session started: {self.current_session_id}")

    async def _log_start(self):
        # Start logging session
        provider_name = self.provider.__class__.__name__.removesuffix("Provider")
        self.current_session_id = await self.logger.start_session(
            provider_used=provider_name
        )
        print(f"Logging session started: {self.current_session_id}")

    async def run(self):
        """Run an interactive chat loop"""
        print("\nMCP Client Started!")
        print(f"Current Model: {self.provider.current_model}")
        print("\nType '/q' or use Ctrl+D to quit")
        print("Type '/model' to switch models")

        if self.is_test_mode and self.test_data and "__filepath" in self.test_data:
            await self.server_manager.register_all_servers(
                config_path=self.test_data["__filepath"]
            )
        else:
            await self.server_manager.register_all_servers()

        # --- Test Mode ---
        if self.is_test_mode and self.test_data and "model_provider" in self.test_data:
            model_provider = self.test_data.get("model_provider")
            model_string = self.test_data.get("model_string", "")

            await self._auto_switch_model(model_provider, model_string)
            print(f"Current Model: {self.provider.current_model}")

            # Start logging session
            await self._log_start()

            try:
                print("\nExecuting test logic...")
                prompts = self.test_data.get("prompts", [])

                print(f"Total prompts to run: {len(prompts)}")

                if not prompts:
                    print("⚠️ WARNING: No prompts found in test data.")
                    # TODO: Consider throwing exception so that the finally block executes and can end logging session.
                    return  # Exit run if no prompts

                for i, query in enumerate(prompts):
                    print(f"\n[TEST PROMPT {i+1}/{len(prompts)}]: {query[:80]}...")

                    try:
                        response = await self._process_query(query)

                        print("\n[RESPONSE]:")
                        print(response)

                    except Exception as e:
                        print(
                            f"🔥 ERROR: Failed to process test prompt {i+1}. Error: {str(e)}"
                        )
                        # Continue to the next prompt, don't break the whole test run

            finally:
                await self._log_cleanup()

            return  # Exit the run method after the test is complete

        # --- Standard Interactive Mode ---
        else:
            print(f"Current Model: {self.provider.current_model}")
            print("\nType '/q' or use Ctrl+D to quit")
            print("Type '/model' to switch models")

            # Start logging session
            await self._log_start()

            try:
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
            finally:
                await self._log_cleanup()

    async def cleanup(self):
        """Clean up resources"""
        await self.exit_stack.aclose()
