import os
import subprocess
import sys
from state_io import load_state, save_state, STATE_FILE_PATH
from preferences_manager import update_form_preferences

ESPANSO_CMD_PATH = os.path.join(os.environ.get("LOCALAPPDATA", ""), "Programs", "Espanso", "espanso.cmd")

def main():
    debug_file_target = os.path.join(os.path.expanduser("~"), "espanso_debug_paths.txt")

    current_state = load_state()
    if not current_state:
        with open(debug_file_target, "a", encoding="utf-8") as f_debug:
            f_debug.write("ERROR handle_form_step2: Failed to load state from Step 1 or state is empty.\n")
        sys.exit(1)
    else:
        with open(debug_file_target, "a", encoding="utf-8") as f_debug:
            f_debug.write(f"handle_form_step2.py: Loaded current_state: {current_state}\n")

    sentiment = os.getenv("ESPANSO_GPT_STEP2_FORM_DATA_SENTIMENT_CHOICE")
    relation = os.getenv("ESPANSO_GPT_STEP2_FORM_DATA_RELATION_CHOICE")
    faq_selection = os.getenv("ESPANSO_GPT_STEP2_FORM_DATA_FAQ_SELECTION")
    desired_sketch = os.getenv("ESPANSO_GPT_STEP2_FORM_DATA_DESIRED_ANSWER_SKETCH")

    with open(debug_file_target, "a", encoding="utf-8") as f_debug:
        f_debug.write(f"handle_form_step2.py: Retrieved from Env - Sentiment: {sentiment}\n")
        f_debug.write(f"handle_form_step2.py: Retrieved from Env - Relation: {relation}\n")
        f_debug.write(f"handle_form_step2.py: Retrieved from Env - FAQ Selection: {faq_selection}\n")
        f_debug.write(f"handle_form_step2.py: Retrieved from Env - Desired Sketch: {desired_sketch}\n")

    # Save user preferences for next time
    try:
        preferences_to_save = {
            "sentiment_choice": sentiment,
            "relation_choice": relation,
            "faq_selection": faq_selection
        }
        update_form_preferences("gpt_step2_form", preferences_to_save)
        with open(debug_file_target, "a", encoding="utf-8") as f_debug:
            f_debug.write(f"handle_form_step2.py: Saved preferences: {preferences_to_save}\n")
    except Exception as e_prefs:
        with open(debug_file_target, "a", encoding="utf-8") as f_debug:
            f_debug.write(f"WARNING handle_form_step2: Could not save preferences: {e_prefs}\n")
        # Don't exit on preference save failure, it's not critical

    updated_state = {
        **current_state,
        "sentiment": sentiment,
        "relation": relation,
        "selected_faq": faq_selection,
        "desired_answer_sketch": desired_sketch,
    }

    try:
        save_state(updated_state)
        with open(debug_file_target, "a", encoding="utf-8") as f_debug:
            f_debug.write(f"handle_form_step2.py: Saved updated_state: {updated_state}\n")
    except Exception as e:
        with open(debug_file_target, "a", encoding="utf-8") as f_debug:
            f_debug.write(f"ERROR handle_form_step2: Could not save updated state: {e}\n")
        sys.exit(1)

    next_trigger = ":gpt_final_processing"
    try:
        with open(debug_file_target, "a", encoding="utf-8") as f_debug:
            f_debug.write(f"handle_form_step2.py: Triggering next step: {next_trigger}\n")
        subprocess.run([ESPANSO_CMD_PATH, "match", "exec", "-t", next_trigger], check=True)
    except Exception as e_subproc:
        with open(debug_file_target, "a", encoding="utf-8") as f_debug:
            f_debug.write(f"ERROR handle_form_step2: Failed to trigger '{next_trigger}'. Error: {e_subproc}\n")
        sys.exit(1)

    sys.exit(0)

if __name__ == "__main__":
    # 0. Call this script with the arguments for this form step.
    #    Example: python scripts/handle_form_step2.py "positive" "formal" "Here is an idea for the answer..."
    #
    # 1. Ensure handle_form_step1.py has run and created a gpt_tools/gpt_form_state.json with appropriate test data.
    #    (Or, manually create gpt_tools/gpt_form_state.json in the expected CONFIG_DIR for testing state_io.py)
    #    Example content for gpt_tools/gpt_form_state.json for this test:
    #    {
    #        "task_objective": "Generate a summary",
    #        "input_text": "This is the long text to summarize.",
    #    }
    # 2. Set mock env vars for Step 2 fields:
    #    os.environ["ESPANSO_GPT_STEP2_FORM_DATA_SENTIMENT_CHOICE"] = "Test Sentiment"
    #    os.environ["ESPANSO_GPT_STEP2_FORM_DATA_RELATION_CHOICE"] = "Test Relation"
    #    os.environ["ESPANSO_GPT_STEP2_FORM_DATA_FAQ_SELECTION"] = "test_faq.md"
    #    if "ESPANSO_CONFIG_DIR" not in os.environ: # For state_io.py pathing
    #        os.environ["ESPANSO_CONFIG_DIR"] = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    # 3. Then call main().
    main() 