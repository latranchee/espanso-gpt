import os
import subprocess
import sys
import pyperclip
import time # For generating unique IDs
# import uuid # Alternative for unique IDs: uuid.uuid4()
from state_io import save_state, delete_state, STATE_FILE_PATH, load_state, CONFIG_DIR # Import CONFIG_DIR

DEBUG_MODE = True

# Assuming state_io.py is in the same directory or Python's path is configured for it.
# For Espanso, scripts are typically in %CONFIG%/scripts/, so direct import should work.
ESPANSO_CMD_PATH = r"C:\Users\Olivier Lambert\AppData\Local\Programs\Espanso\espanso.cmd"
LAST_CONV_ID_FILENAME = "last_conversation_id.txt"
LAST_CONV_ID_FILEPATH = os.path.join(CONFIG_DIR, LAST_CONV_ID_FILENAME)

def main():
    debug_file_target = os.path.join(os.path.expanduser("~"), "espanso_debug_paths.txt")
    
    # Log all environment variables at the start of main when run by Espanso
    try:
        with open(debug_file_target, "w", encoding="utf-8") as f_debug: # 'w' to overwrite for this new run
            f_debug.write("--- handle_form_step1.py: ALL ENVIRONMENT VARIABLES ---\n")
            for key, value in os.environ.items():
                f_debug.write(f"{key}=>{value}\n")
            f_debug.write("--- END ENVIRONMENT VARIABLES ---\n\n")
    except Exception as e_env_log:
        # Fallback if we can't even write the env log
        print(f"CRITICAL DEBUG ERROR: Could not write env_log to {debug_file_target}: {e_env_log}", file=sys.stderr)

    # Clear previous state and log it
    try:
        delete_state()
        with open(debug_file_target, "a", encoding="utf-8") as f_debug: # 'a' to append now
            f_debug.write(f"handle_form_step1.py: Called delete_state() for {STATE_FILE_PATH}. File exists after delete: {os.path.exists(STATE_FILE_PATH)}\n")
    except Exception as e:
        with open(debug_file_target, "a", encoding="utf-8") as f_debug:
            f_debug.write(f"handle_form_step1.py: Error deleting state: {e}\n")
        # print(f"Error deleting previous state in handle_form_step1: {e}", file=sys.stderr)

    # Espanso passes form field values as environment variables:
    # ESPANSO_<FORM_VAR_NAME>_<FIELD_NAME>
    # Example: gpt_step1_form_data.task_objective_choice becomes
    # ESPANSO_GPT_STEP1_FORM_DATA_TASK_OBJECTIVE_CHOICE

    conversation_mode = os.getenv("ESPANSO_GPT_STEP1_FORM_DATA_CONVERSATION_MODE_CHOICE", "Start New")
    task_objective = os.getenv("ESPANSO_GPT_STEP1_FORM_DATA_TASK_OBJECTIVE_CHOICE")
    output_language = os.getenv("ESPANSO_GPT_STEP1_FORM_DATA_OUTPUT_LANGUAGE_CHOICE")
    initial_prompt_from_form = os.getenv("ESPANSO_GPT_STEP1_FORM_DATA_INITIAL_USER_PROMPT", "") # Default to empty string
    desired_sketch = os.getenv("ESPANSO_GPT_STEP1_FORM_DATA_DESIRED_ANSWER_SKETCH")
    include_screenshot_str = os.getenv("ESPANSO_GPT_STEP1_FORM_DATA_INCLUDE_SCREENSHOT_CHOICE", "false") # New var

    # Log the values it *thinks* it got for the specific fields
    with open(debug_file_target, "a", encoding="utf-8") as f_debug:
        f_debug.write(f"handle_form_step1.py: Retrieved from Env - Conv Mode: {conversation_mode}\n")
        f_debug.write(f"handle_form_step1.py: Retrieved from Env - Task Objective: {task_objective}\n")
        f_debug.write(f"handle_form_step1.py: Retrieved from Env - Output Language: {output_language}\n")
        f_debug.write(f"handle_form_step1.py: Retrieved from Env - Initial Prompt Form: {initial_prompt_from_form}\n")
        f_debug.write(f"handle_form_step1.py: Retrieved from Env - Desired Sketch: {desired_sketch}\n")
        f_debug.write(f"handle_form_step1.py: Retrieved from Env - Include Screenshot: {include_screenshot_str}\n") # Log new var

    if task_objective is None:
        with open(debug_file_target, "a", encoding="utf-8") as f_debug:
            f_debug.write("ERROR handle_form_step1: Task Objective is None after os.getenv.\n")
        sys.exit(1) # Indicate an error

    active_conversation_id = ""
    if conversation_mode == "Continue Last":
        try:
            with open(LAST_CONV_ID_FILEPATH, "r", encoding="utf-8") as f_last_id:
                active_conversation_id = f_last_id.read().strip()
            if not active_conversation_id:
                conversation_mode = "Start New"
                if DEBUG_MODE:
                    with open(debug_file_target, "a", encoding="utf-8") as f_debug:
                        f_debug.write("DEBUG handle_form_step1: last_conversation_id.txt was empty. Switching to Start New.\n")
            else:
                if DEBUG_MODE:
                    with open(debug_file_target, "a", encoding="utf-8") as f_debug:
                        f_debug.write(f"DEBUG handle_form_step1: Loaded last_conversation_id: {active_conversation_id}\n")
        except FileNotFoundError:
            conversation_mode = "Start New"
            if DEBUG_MODE:
                with open(debug_file_target, "a", encoding="utf-8") as f_debug:
                    f_debug.write("DEBUG handle_form_step1: last_conversation_id.txt not found. Switching to Start New.\n")
    
    if conversation_mode == "Start New":
        active_conversation_id = str(time.time())
        if DEBUG_MODE:
            with open(debug_file_target, "a", encoding="utf-8") as f_debug:
                f_debug.write(f"DEBUG handle_form_step1: Generated new_conversation_id: {active_conversation_id}\n")

    # If initial_prompt_from_form is empty, try to use clipboard content
    final_initial_prompt = initial_prompt_from_form
    if not initial_prompt_from_form:
        try:
            final_initial_prompt = pyperclip.paste()
            if not final_initial_prompt: # If clipboard is also empty
                final_initial_prompt = "" # Ensure it's an empty string, not None
            with open(debug_file_target, "a", encoding="utf-8") as f_debug:
                 f_debug.write(f"DEBUG handle_form_step1: Pyperclip paste result for initial_prompt: '{final_initial_prompt}'\n")
        except Exception as e_clip:
            final_initial_prompt = ""
            with open(debug_file_target, "a", encoding="utf-8") as f_debug:
                 f_debug.write(f"DEBUG handle_form_step1: Pyperclip error: {e_clip}. Using empty prompt for initial_prompt.\n")

    step1_data = {
        "conversation_mode": conversation_mode,
        "active_conversation_id": active_conversation_id,
        "task_objective": task_objective,
        "output_language": output_language,
        "initial_prompt": final_initial_prompt, # Use potentially clipboard-filled prompt
        "desired_answer_sketch": desired_sketch,
        "include_screenshot": include_screenshot_str, # Save to state
        # Add any other fields from Step 1 form here
    }

    try:
        save_state(step1_data)
        with open(debug_file_target, "a", encoding="utf-8") as f_debug:
            f_debug.write(f"handle_form_step1.py: Saved step1_data to state file: {step1_data}\n")
    except Exception as e:
        with open(debug_file_target, "a", encoding="utf-8") as f_debug:
            f_debug.write(f"ERROR handle_form_step1: Could not save state: {e}\n")
        # print(f"ERROR handle_form_step1: Could not save state. {e}", file=sys.stderr)
        sys.exit(1)

    # Conditional triggering of next step
    next_trigger = ""
    if task_objective == "Customer Support Task":
        next_trigger = ":gpt_form_step2"
    else:
        next_trigger = ":gpt_final_processing"
    
    try:
        with open(debug_file_target, "a", encoding="utf-8") as f_debug:
            f_debug.write(f"handle_form_step1.py: Triggering next step: {next_trigger}\n")
        # Add a small delay if screenshot is true, to allow screen to settle after form submission
        if include_screenshot_str.lower() == "true":
            time.sleep(0.5) # 0.5 second delay, adjust if needed
        subprocess.run([ESPANSO_CMD_PATH, "match", "exec", "-t", next_trigger], check=True)
    except Exception as e_subproc:
        with open(debug_file_target, "a", encoding="utf-8") as f_debug:
            f_debug.write(f"ERROR handle_form_step1: Failed to trigger '{next_trigger}'. Error: {e_subproc}\n")
        # print(f"ERROR handle_form_step1: Failed to trigger next Espanso match '{next_trigger}'. Error: {e}", file=sys.stderr)
        sys.exit(1)

    sys.exit(0) # Success, prevent unwanted output

# Call main directly when the script is run by Espanso or for testing.
# The if __name__ == "__main__" block should ideally only be for code 
# that *sets up* a direct test environment, not for code that runs in production.
if __name__ == "__main__":
    # To test this script directly from the command line with mock inputs:
    # 1. Comment out the main() call below.
    # 2. Set mock env vars like this:
    #    os.environ["ESPANSO_GPT_STEP1_FORM_DATA_TASK_OBJECTIVE_CHOICE"] = "General Q&A" 
    #    os.environ["ESPANSO_GPT_STEP1_FORM_DATA_OUTPUT_LANGUAGE_CHOICE"] = "Test Language"
    #    os.environ["ESPANSO_GPT_STEP1_FORM_DATA_INITIAL_USER_PROMPT"] = "Direct test prompt"
    #    os.environ["ESPANSO_GPT_STEP1_FORM_DATA_DESIRED_ANSWER_SKETCH"] = "Direct test sketch"
    #    if "ESPANSO_CONFIG_DIR" not in os.environ: # For state_io.py pathing
    #        os.environ["ESPANSO_CONFIG_DIR"] = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    # 3. Then call main().
    # For Espanso execution, main() must be called without these env var manipulations here.
    main()
    # print("handle_form_step1.py direct test finished.", file=sys.stderr) 