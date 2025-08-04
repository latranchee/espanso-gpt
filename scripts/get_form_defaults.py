#!/usr/bin/env python3
"""
Script to get form defaults based on saved user preferences.
Usage: python get_form_defaults.py <form_name> <field_name>
Outputs the preferred default value for the specified form field.
"""

import sys
import os

# Add the scripts directory to the path so we can import preferences_manager
sys.path.insert(0, os.path.dirname(__file__))

from preferences_manager import get_form_preference, DEFAULT_PREFERENCES

def main():
    if len(sys.argv) != 3:
        print("Usage: python get_form_defaults.py <form_name> <field_name>", file=sys.stderr)
        sys.exit(1)
    
    form_name = sys.argv[1]
    field_name = sys.argv[2]
    
    # Get the preferred default value
    default_value = get_form_preference(form_name, field_name)
    
    if default_value is not None:
        print(default_value)
    else:
        # If no preference is saved, use the hardcoded default from DEFAULT_PREFERENCES
        if form_name in DEFAULT_PREFERENCES and field_name in DEFAULT_PREFERENCES[form_name]:
            print(DEFAULT_PREFERENCES[form_name][field_name])
        else:
            # If no default is defined, output empty string (Espanso will use its own default)
            print("")

if __name__ == "__main__":
    main() 