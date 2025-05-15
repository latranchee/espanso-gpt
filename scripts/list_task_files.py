#!/usr/bin/env python3
import sys
from action_reader import get_tasks_list

def main():
    """List all available tasks for use in Espanso forms."""
    try:
        tasks = get_tasks_list()
        for task in tasks:
            print(task)
    except Exception as e:
        # Print a fallback task to prevent Espanso form issues
        print("ErrorListingTasks")
        print(f"Error listing tasks: {e}", file=sys.stderr)

if __name__ == "__main__":
    main() 