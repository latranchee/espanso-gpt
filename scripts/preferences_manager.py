import json
import os
import sys
from typing import Dict, Any, Optional

# Determine the Espanso config directory
CONFIG_DIR = os.environ.get("ESPANSO_CONFIG_DIR", os.path.join(os.path.dirname(__file__), ".."))
PREFERENCES_FILE = os.path.join(CONFIG_DIR, "gpt_tools", "user_preferences.json")

# Default preferences structure
DEFAULT_PREFERENCES = {
    "gpt_multi_form": {
        "conversation_mode_choice": "Start New",
        "task_objective_choice": "Speech-to-Text Editor", 
        "output_language_choice": "French",
        "include_screenshot_choice": "false"
    },
    "gpt_step2_form": {
        "sentiment_choice": "neutre",
        "relation_choice": "client",
        "faq_selection": "None"
    },
    "customer_support": {
        "sentiment": "neutre",
        "relation": "client", 
        "selected_faq": "None",
        "language_choice": "French",
        "include_screenshot": "true"
    }
}

def ensure_preferences_dir():
    """Ensure the gpt_tools directory exists for storing preferences."""
    gpt_tools_dir = os.path.join(CONFIG_DIR, "gpt_tools")
    if not os.path.exists(gpt_tools_dir):
        os.makedirs(gpt_tools_dir)

def load_preferences() -> Dict[str, Any]:
    """Load user preferences from file, return defaults if file doesn't exist."""
    ensure_preferences_dir()
    
    if not os.path.exists(PREFERENCES_FILE):
        return DEFAULT_PREFERENCES.copy()
    
    try:
        with open(PREFERENCES_FILE, "r", encoding="utf-8") as f:
            prefs = json.load(f)
            # Merge with defaults to ensure all keys exist
            merged_prefs = DEFAULT_PREFERENCES.copy()
            for form_name, form_prefs in prefs.items():
                if form_name in merged_prefs:
                    merged_prefs[form_name].update(form_prefs)
                else:
                    merged_prefs[form_name] = form_prefs
            return merged_prefs
    except Exception as e:
        print(f"ERROR preferences_manager: Failed to load preferences: {e}", file=sys.stderr)
        return DEFAULT_PREFERENCES.copy()

def save_preferences(preferences: Dict[str, Any]):
    """Save user preferences to file."""
    ensure_preferences_dir()
    
    try:
        with open(PREFERENCES_FILE, "w", encoding="utf-8") as f:
            json.dump(preferences, f, indent=4, ensure_ascii=False)
    except Exception as e:
        print(f"ERROR preferences_manager: Failed to save preferences: {e}", file=sys.stderr)
        raise

def update_form_preferences(form_name: str, field_values: Dict[str, str]):
    """Update preferences for a specific form with new field values."""
    prefs = load_preferences()
    
    if form_name not in prefs:
        prefs[form_name] = {}
    
    prefs[form_name].update(field_values)
    save_preferences(prefs)

def get_form_preference(form_name: str, field_name: str, default_value: Optional[str] = None) -> Optional[str]:
    """Get a specific preference value for a form field."""
    prefs = load_preferences()
    
    if form_name in prefs and field_name in prefs[form_name]:
        return prefs[form_name][field_name]
    
    return default_value

def get_form_preferences(form_name: str) -> Dict[str, str]:
    """Get all preferences for a specific form."""
    prefs = load_preferences()
    return prefs.get(form_name, {})

if __name__ == "__main__":
    # Test the preferences system
    print(f"Config directory: {CONFIG_DIR}")
    print(f"Preferences file: {PREFERENCES_FILE}")
    
    # Load current preferences
    current_prefs = load_preferences()
    print(f"Current preferences: {json.dumps(current_prefs, indent=2)}")
    
    # Test updating preferences
    test_updates = {
        "conversation_mode_choice": "Continue Last",
        "output_language_choice": "English"
    }
    
    print(f"Testing preference update: {test_updates}")
    update_form_preferences("gpt_multi_form", test_updates)
    
    # Verify the update
    updated_prefs = load_preferences()
    print(f"Updated preferences: {json.dumps(updated_prefs, indent=2)}") 