import json
import os
import sys

# Determine the Espanso config directory.
# ESPANSO_CONFIG_DIR is an environment variable set by Espanso when running scripts.
# Fallback to a common relative path if the env var isn't set (e.g., for direct testing, though less reliable).
CONFIG_DIR = os.environ.get("ESPANSO_CONFIG_DIR", os.path.join(os.path.dirname(__file__), ".."))
STATE_FILE_NAME = "gpt_tools/gpt_form_state.json"
STATE_FILE_PATH = os.path.join(CONFIG_DIR, STATE_FILE_NAME)

def save_state(data):
    """Saves the given data dictionary to the state JSON file."""
    try:
        with open(STATE_FILE_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4)
        # For debugging when running via Espanso, print to stderr
        # print(f"DEBUG state_io: Saved state to {STATE_FILE_PATH}: {data}", file=sys.stderr)
    except Exception as e:
        print(f"ERROR state_io: Failed to save state to {STATE_FILE_PATH}: {e}", file=sys.stderr)
        # Potentially re-raise or handle more gracefully depending on desired script behavior
        raise

def load_state():
    """Loads data from the state JSON file. Returns an empty dict if not found or error."""
    if not os.path.exists(STATE_FILE_PATH):
        # print(f"DEBUG state_io: State file not found at {STATE_FILE_PATH}. Returning empty dict.", file=sys.stderr)
        return {}
    try:
        with open(STATE_FILE_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
            # print(f"DEBUG state_io: Loaded state from {STATE_FILE_PATH}: {data}", file=sys.stderr)
            return data
    except Exception as e:
        print(f"ERROR state_io: Failed to load state from {STATE_FILE_PATH}: {e}. Returning empty dict.", file=sys.stderr)
        return {}

def delete_state():
    """Deletes the state JSON file if it exists."""
    try:
        if os.path.exists(STATE_FILE_PATH):
            os.remove(STATE_FILE_PATH)
            # print(f"DEBUG state_io: Deleted state file {STATE_FILE_PATH}", file=sys.stderr)
    except Exception as e:
        print(f"ERROR state_io: Failed to delete state file {STATE_FILE_PATH}: {e}", file=sys.stderr)
        # Potentially re-raise or handle
        raise

if __name__ == "__main__":
    # Example usage for direct testing
    print(f"Config directory determined as: {CONFIG_DIR}")
    print(f"State file path: {STATE_FILE_PATH}")

    test_data_step1 = {"task_objective": "Test Task", "language": "English", "prompt": "Hello"}
    print(f"Attempting to save step 1: {test_data_step1}")
    save_state(test_data_step1)

    loaded_data_step1 = load_state()
    print(f"Loaded step 1: {loaded_data_step1}")

    test_data_step2 = {"sentiment": "positive"}
    # Simulate appending step 2 data
    current_state = load_state()
    current_state.update(test_data_step2)
    print(f"Attempting to save combined state: {current_state}")
    save_state(current_state)
    
    loaded_data_combined = load_state()
    print(f"Loaded combined state: {loaded_data_combined}")

    print("Attempting to delete state file...")
    delete_state()
    
    remaining_state = load_state()
    print(f"State after deletion (should be empty): {remaining_state}")
    if not os.path.exists(STATE_FILE_PATH):
        print("State file successfully deleted.")
    else:
        print("ERROR: State file still exists after deletion attempt.") 