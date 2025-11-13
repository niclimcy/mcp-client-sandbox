import copy
import pathlib
import json

from client import MCPClient
from logger.taint_rule_engine import Confidence
from log_processor import process_logs


async def test(test_names: list[str] | None):
    """
    Runs the MCPClient in test mode using specified test JSON files.

    Args:
        test_names: List of test filenames (without .json extension) to run.
    """
    print("--- Running in Test Mode ---")

    # Step 1: Validate and load test files
    if not test_names or len(test_names) == 0:
        print("🚫 No test names provided. Exiting test run.")
        return

    TEST_DIR = pathlib.Path("tests")
    test_data_to_run = []
    for name in test_names:
        filename = f"{name}.json"
        filepath = TEST_DIR / filename

        print(f"Checking for test file: {filepath}...")

        if not filepath.exists():
            print(
                f"⚠️ ERROR: Test file not found at {filepath}. "
                f"Skipping test '{name}'."
            )
            continue

        # Step 2: Read and parse the JSON
        try:
            with open(filepath, "r") as f:
                test_data = json.load(f)
            test_data["__filepath"] = str(filepath.absolute())

            print(f"✅ Success: Loaded test data for '{name}'.")
            test_data_to_run.append(test_data)

        except json.JSONDecodeError:
            print(
                f"❌ ERROR: Failed to parse JSON in {filepath}. "
                f"Skipping test '{name}'."
            )
        except Exception as e:
            print(
                f"❌ ERROR: An unexpected error occurred reading {filepath}: "
                f"{e}. Skipping test '{name}'."
            )

    if not test_data_to_run:
        print("\n🚫 No valid test files loaded. Exiting test run.")
        return

    # Step 3: Iterate and run the client for each test
    for i, data in enumerate(test_data_to_run):
        test_name = test_names[i]  # Use the original name for logging/reference

        print(
            "\n--- Starting Client Run for Test: "
            f"{test_name} ({i+1}/{len(test_data_to_run)}) ---"
        )
        num_models = len(data.get("models", []))
        print(f"Test '{test_name}' contains {num_models} model(s).")

        for model_index in range(num_models):
            print(
                "\n--- Starting Client Run for Test: "
                f"{test_name} ({i+1}/{len(test_data_to_run)}) "
                f"Model ({model_index + 1}/{num_models}) ---"
            )
            data_copy = copy.deepcopy(data)
            data_copy["cur_model_index"] = model_index

            # Create a new client for each test run
            # Pass is_test_mode=True and the loaded JSON data
            client = MCPClient(is_test_mode=True, test_data=data_copy)

            try:
                # The client.run() should handle the test logic based on test_data
                await client.run()
            except Exception as e:
                print(f"🔥 FATAL ERROR during client run for test '{test_name}': {e}")
            finally:
                print(f"--- Finished Client Run for Test: {test_name} ---")

                session_id = await client.cleanup()
                log_path = pathlib.Path("logs") / f"session_{session_id}.json"
                process_logs(
                    log_path, min_confidence=Confidence.MEDIUM, min_risk_score=2
                )

    print("--- 🎉FINISHED ALL TESTS!!! ---")
