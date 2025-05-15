import os
import subprocess
import sys
from state_io import load_state, save_state, STATE_FILE_PATH

ESPANSO_CMD_PATH = r"C:\Users\Olivier Lambert\AppData\Local\Programs\Espanso\espanso.cmd"

def main():
    debug_file_target = os.path.join(os.path.expanduser("~"), "espanso_debug_paths.txt")
    
    # Log all environment variables at the start of main when run by Espanso
    try:
        with open(debug_file_target, "a") as f_debug: # Append for step 2
            f_debug.write("\n--- handle_form_step2.py: ALL ENVIRONMENT VARIABLES ---\n")
            for key, value in os.environ.items():
                f_debug.write(f"{key}=>{value}\n")
            f_debug.write("--- END ENVIRONMENT VARIABLES ---\n\n")
    except Exception as e_env_log:
        print(f"CRITICAL DEBUG ERROR in handle_form_step2: Could not write env_log: {e_env_log}", file=sys.stderr)

    current_state = load_state()
    if not current_state:
        with open(debug_file_target, "a") as f_debug:
            f_debug.write("ERROR handle_form_step2: Failed to load state from Step 1 or state is empty.\n")
        sys.exit(1)
    else:
        with open(debug_file_target, "a") as f_debug:
            f_debug.write(f"handle_form_step2.py: Loaded current_state: {current_state}\n")

    sentiment = os.getenv("ESPANSO_GPT_STEP2_FORM_DATA_SENTIMENT_CHOICE")
    relation = os.getenv("ESPANSO_GPT_STEP2_FORM_DATA_RELATION_CHOICE")
    faq_selection = os.getenv("ESPANSO_GPT_STEP2_FORM_DATA_FAQ_SELECTION")

    with open(debug_file_target, "a") as f_debug:
        f_debug.write(f"handle_form_step2.py: Retrieved from Env - Sentiment: {sentiment}\n")
        f_debug.write(f"handle_form_step2.py: Retrieved from Env - Relation: {relation}\n")
        f_debug.write(f"handle_form_step2.py: Retrieved from Env - FAQ Selection: {faq_selection}\n")

    updated_state = {
        **current_state,
        "sentiment": sentiment,
        "relation": relation,
        "selected_faq": faq_selection,
    }

    try:
        save_state(updated_state)
        with open(debug_file_target, "a") as f_debug:
            f_debug.write(f"handle_form_step2.py: Saved updated_state: {updated_state}\n")
    except Exception as e:
        with open(debug_file_target, "a") as f_debug:
            f_debug.write(f"ERROR handle_form_step2: Could not save updated state: {e}\n")
        sys.exit(1)

    next_trigger = ":gpt_final_processing"
    try:
        with open(debug_file_target, "a") as f_debug:
            f_debug.write(f"handle_form_step2.py: Triggering next step: {next_trigger}\n")
        subprocess.run([ESPANSO_CMD_PATH, "match", "exec", "-t", next_trigger], check=True)
    except Exception as e_subproc:
        with open(debug_file_target, "a") as f_debug:
            f_debug.write(f"ERROR handle_form_step2: Failed to trigger '{next_trigger}'. Error: {e_subproc}\n")
        sys.exit(1)

    sys.exit(0)

if __name__ == "__main__":
    # To test this script directly:
    # 1. Ensure handle_form_step1.py has run and created a gpt_form_state.json with appropriate test data.
    #    (Or, manually create gpt_form_state.json in the expected CONFIG_DIR for testing state_io.py)
    #    Example content for gpt_form_state.json for this test:
    #    { "task_objective": "Customer Support Task", "output_language": "French", 
    #      "initial_prompt": "Test from step1", "desired_answer_sketch": "Sketch from step1" }
    # 2. Set mock env vars for Step 2 fields:
    #    os.environ["ESPANSO_GPT_STEP2_FORM_DATA_SENTIMENT_CHOICE"] = "Test Sentiment"
    #    os.environ["ESPANSO_GPT_STEP2_FORM_DATA_RELATION_CHOICE"] = "Test Relation"
    #    os.environ["ESPANSO_GPT_STEP2_FORM_DATA_FAQ_SELECTION"] = "test_faq.md"
    #    if "ESPANSO_CONFIG_DIR" not in os.environ: # For state_io.py pathing
    #        os.environ["ESPANSO_CONFIG_DIR"] = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    # 3. Then call main().
    main() 