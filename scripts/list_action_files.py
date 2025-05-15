#!/usr/bin/env python3
import sys
from action_reader import get_actions_list

def main():
    """List all available actions for use in Espanso forms."""
    try:
        actions = get_actions_list()
        for action in actions:
            print(action)
    except Exception as e:
        # Print a fallback action to prevent Espanso form issues
        print("ErrorListingActions")
        print(f"Error listing actions: {e}", file=sys.stderr)

if __name__ == "__main__":
    main() 