import asyncio
import argparse
import sys

from client import MCPClient
from test import test


def get_cli_args():
    """
    Parses command-line arguments.

    Returns:
        is_test_mode: True if the --test flag was provided.
        test_files: A list of json test filenames with no extension or None.
    """

    parser = argparse.ArgumentParser(
        description="Run the MCPClient with optional test flags."
    )
    parser.add_argument(
        "--test",
        nargs="+",  # Indicates one or more arguments are required after --test
        default=None,
        help=(
            "Run in test mode with specified test names (e.g., first_test second_test)."
        ),
    )
    args = parser.parse_args()

    test_names = args.test if args.test is not None else []
    return args.test is not None, test_names


async def main():
    """
    Main asynchronous function to run the client.
    """
    # Standard Mode (Original Logic)
    print("--- Running in Standard Mode ---")
    client = MCPClient()

    try:
        await client.run()

    except Exception as e:
        print(f"❌ ERROR: Unexpected error occurred during client run: {e}")

    finally:
        await client.cleanup()


if __name__ == "__main__":
    is_test_mode, files = get_cli_args()

    if is_test_mode:
        asyncio.run(test(files))
        sys.exit(0)  # Exit after test mode

    asyncio.run(main())
