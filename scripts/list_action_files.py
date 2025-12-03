#!/usr/bin/env python3
import sys
from action_reader import get_actions_with_display_names


def main():
    """List all available actions with display names for use in Espanso forms."""
    try:
        actions = get_actions_with_display_names()
        for filename, display_name in actions:
            # Output format: display_name (Espanso will show this in dropdown)
            # The filename is used internally when passed to scripts
            print(display_name)
    except Exception as e:
        # Print a fallback action to prevent Espanso form issues
        print("ErrorListingActions")
        print(f"Error listing actions: {e}", file=sys.stderr)


if __name__ == "__main__":
    main()
