import asyncio
import argparse
from client import MCPClient

def get_cli_args():
    """Parses command-line arguments."""
    parser = argparse.ArgumentParser(description="Run the MCPClient with optional test flags.")

    # check test flag
    parser.add_argument(
        '--test',
        nargs='+', # Indicates one or more arguments are required after --test
        default=None,
        help='Run in test mode with specified test names (e.g., first_test second_test).'
    )

    args = parser.parse_args()

    test_files = None
    if args.test is not None:
        test_files = [f"{test_name}.json" for test_name in args.test]

    return args.test is not None, test_files

async def main(is_test_mode: bool, test_files: list[str] | None):
    """
    Main asynchronous function to run the client.
    
    Args:
        is_test_mode: True if the --test flag was provided.
        test_files: A list of test filenames (with .json extension) or None.
    """
    
    print(f"Test mode requested: {is_test_mode}")
    if is_test_mode:
        print(f"Test files to load: {test_files}")
    else:
        print("Running in standard mode.")

    client = MCPClient()
    # client = MCPClient(is_test_mode=is_test_mode, test_files=test_files)
    try:
        await client.run()
    finally:
        await client.cleanup()


if __name__ == "__main__":
    is_test_mode, files = get_cli_args()
    asyncio.run(main(is_test_mode, files))