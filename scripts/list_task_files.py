#!/usr/bin/env python3
import sys
from action_reader import get_tasks_with_display_names


def main():
    """List all available tasks with display names for use in Espanso forms."""
    try:
        tasks = get_tasks_with_display_names()
        for filename, display_name in tasks:
            # Output display_name for the dropdown
            print(display_name)
    except Exception as e:
        # Print a fallback task to prevent Espanso form issues
        print("ErrorListingTasks")
        print(f"Error listing tasks: {e}", file=sys.stderr)


if __name__ == "__main__":
    main()
