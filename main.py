import asyncio
import argparse
import json
from pathlib import Path
from client import MCPClient

def get_cli_args():
    """Parses command-line arguments."""
    parser = argparse.ArgumentParser(description="Run the MCPClient with optional test flags.")
    parser.add_argument(
        '--test',
        nargs='+', # Indicates one or more arguments are required after --test
        default=None,
        help='Run in test mode with specified test names (e.g., first_test second_test).'
    )
    args = parser.parse_args()

    test_names = args.test if args.test is not None else []
    return args.test is not None, test_names

async def main(is_test_mode: bool, test_names: list[str] | None):
    """
    Main asynchronous function to run the client.
    
    Args:
        is_test_mode: True if the --test flag was provided.
        test_files: A list of test filenames (without .json extension) or None.
    """
    
    if is_test_mode:
        print("--- Running in Test Mode ---")
        
        TEST_DIR = Path("tests")
        test_data_to_run = []
        for name in test_names:
            filename = f"{name}.json"
            filepath = TEST_DIR / filename
            
            print(f"Checking for test file: {filepath}...")

            if not filepath.exists():
                print(f"⚠️ ERROR: Test file not found at {filepath}. Skipping test '{name}'.")
                continue
            
            # Step 2: Read and parse the JSON
            try:
                with open(filepath, 'r') as f:
                    test_data = json.load(f)
                
                print(f"✅ Success: Loaded test data for '{name}'.")
                test_data_to_run.append(test_data)
                
            except json.JSONDecodeError:
                print(f"❌ ERROR: Failed to parse JSON in {filepath}. Skipping test '{name}'.")
            except Exception as e:
                print(f"❌ ERROR: An unexpected error occurred reading {filepath}: {e}. Skipping test '{name}'.")

        if not test_data_to_run:
            print("\n🚫 No valid test files were loaded. Exiting test run.")
            return

        # Step 3: Iterate and run the client for each test
        for i, data in enumerate(test_data_to_run):
            test_name = test_names[i] # Use the original name for logging/reference

            print(f"\n--- Starting Client Run for Test: {test_name} ({i+1}/{len(test_data_to_run)}) ---")
            
            # Create a new client for each test run
            # Pass is_test_mode=True and the loaded JSON data
            client = MCPClient(is_test_mode=True, test_data=data)
            
            try:
                # The client.run() should handle the test logic based on test_data
                await client.run() 
            except Exception as e:
                print(f"🔥 FATAL ERROR during client run for test '{test_name}': {e}")
            finally:
                await client.cleanup()
                print(f"--- Finished Client Run for Test: {test_name} ---")

    else:
        # Standard Mode (Original Logic)
        print("--- Running in Standard Mode ---")
        client = MCPClient()
        try:
            await client.run()
        finally:
            await client.cleanup()


if __name__ == "__main__":
    is_test_mode, files = get_cli_args()
    asyncio.run(main(is_test_mode, files))