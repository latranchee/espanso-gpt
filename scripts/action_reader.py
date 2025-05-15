#!/usr/bin/env python3
import os
import json
import glob
import sys

# Base directories
CONFIG_DIR = os.environ.get("ESPANSO_CONFIG_DIR", os.path.join(os.path.dirname(__file__), ".."))
ACTIONS_DIR = os.path.join(CONFIG_DIR, "gpt_tools", "actions")
TASKS_DIR = os.path.join(CONFIG_DIR, "gpt_tools", "tasks")

# Default schemas
DEFAULT_ACTION_SCHEMA = {
    "name": "Unknown Action",
    "requires_second_form": False,
    "prompt_template": "Process the following text in {target_language}: \n\n\"{input_text}\"",
    "temperature": 0.6,
    "max_tokens": 2000
}

DEFAULT_TASK_SCHEMA = {
    "name": "Unknown Task",
    "requires_second_form": False,
    "second_form_fields": [],
    "system_message_template": "You are a helpful AI assistant.",
    "description": "No description provided.",
    "temperature": 0.3,
    "max_tokens": 2000
}

def ensure_directories():
    """Ensure the actions and tasks directories exist."""
    os.makedirs(ACTIONS_DIR, exist_ok=True)
    os.makedirs(TASKS_DIR, exist_ok=True)

def get_actions_list():
    """Get a list of available action names (without .json extension)."""
    ensure_directories()
    action_files = glob.glob(os.path.join(ACTIONS_DIR, "*.json"))
    if not action_files:
        return ["NoActionsFound"]
    
    action_names = []
    for path in sorted(action_files):
        base_name = os.path.basename(path)
        name, _ = os.path.splitext(base_name)
        action_names.append(name)
    
    return action_names

def get_tasks_list():
    """Get a list of available task names (without .json extension)."""
    ensure_directories()
    task_files = glob.glob(os.path.join(TASKS_DIR, "*.json"))
    if not task_files:
        return ["NoTasksFound"]
    
    task_names = []
    for path in sorted(task_files):
        base_name = os.path.basename(path)
        name, _ = os.path.splitext(base_name)
        task_names.append(name)
    
    return task_names

def get_action(action_name):
    """Get the configuration for a specific action."""
    if not action_name or action_name == "NoActionsFound":
        return DEFAULT_ACTION_SCHEMA
    
    action_path = os.path.join(ACTIONS_DIR, f"{action_name}.json")
    
    try:
        if os.path.exists(action_path):
            with open(action_path, 'r', encoding='utf-8') as f:
                action_data = json.load(f)
                # Merge with defaults for any missing fields
                return {**DEFAULT_ACTION_SCHEMA, **action_data}
        else:
            print(f"Warning: Action file not found: {action_path}", file=sys.stderr)
            return DEFAULT_ACTION_SCHEMA
    except Exception as e:
        print(f"Error loading action {action_name}: {e}", file=sys.stderr)
        return DEFAULT_ACTION_SCHEMA

def get_task(task_name):
    """Get the configuration for a specific task."""
    if not task_name or task_name == "NoTasksFound":
        return DEFAULT_TASK_SCHEMA
    
    task_path = os.path.join(TASKS_DIR, f"{task_name}.json")
    
    try:
        if os.path.exists(task_path):
            with open(task_path, 'r', encoding='utf-8') as f:
                task_data = json.load(f)
                # Merge with defaults for any missing fields
                return {**DEFAULT_TASK_SCHEMA, **task_data}
        else:
            print(f"Warning: Task file not found: {task_path}", file=sys.stderr)
            return DEFAULT_TASK_SCHEMA
    except Exception as e:
        print(f"Error loading task {task_name}: {e}", file=sys.stderr)
        return DEFAULT_TASK_SCHEMA

# Simple testing
if __name__ == "__main__":
    if len(sys.argv) > 1:
        command = sys.argv[1]
        
        if command == "list_actions":
            # Print all action names
            for action in get_actions_list():
                print(action)
                
        elif command == "list_tasks":
            # Print all task names
            for task in get_tasks_list():
                print(task)
                
        elif command == "get_action" and len(sys.argv) > 2:
            # Get and print a specific action
            action_name = sys.argv[2]
            action = get_action(action_name)
            print(json.dumps(action, indent=2))
            
        elif command == "get_task" and len(sys.argv) > 2:
            # Get and print a specific task
            task_name = sys.argv[2]
            task = get_task(task_name)
            print(json.dumps(task, indent=2))
            
        else:
            print("Usage:", file=sys.stderr)
            print("  action_reader.py list_actions", file=sys.stderr)
            print("  action_reader.py list_tasks", file=sys.stderr)
            print("  action_reader.py get_action <action_name>", file=sys.stderr)
            print("  action_reader.py get_task <task_name>", file=sys.stderr)
    else:
        print("No command specified. Use 'list_actions', 'list_tasks', 'get_action', or 'get_task'.", file=sys.stderr) 