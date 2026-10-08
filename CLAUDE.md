# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is an Espanso configuration that integrates LLM providers (OpenAI and Anthropic Claude) for text transformations and AI-powered task assistance. It provides two main triggers:

- `:rephrase:` - Text transformation with tone and action selection
- `:gpt:` - Multi-step AI task assistant with conversation history
- `:support:` - Customer support response generator

Plus a standalone push-to-talk dictation daemon (not an Espanso trigger, since Espanso has no hold/release hotkeys): hold F8 to record, release to transcribe and paste. F8 is swallowed system-wide while the daemon runs.

## Architecture

### Directory Structure

- `config/` - Espanso configuration (default.yml)
- `match/` - Espanso trigger definitions (YAML files)
- `scripts/` - Python scripts that power the AI features
- `gpt_tools/` - Configuration and data for GPT features:
  - `actions/` - JSON configs for text transformation actions (Rephrase, Expand, Translate, etc.)
  - `tasks/` - JSON configs for AI task personas (Speech-to-Text Editor, Customer Support, General Q&A)
  - `tone/` - Text files defining tone instructions (Friendly.txt, Formal.txt, etc.)
  - `faq/` - Markdown files with FAQ content for customer support
  - `context/` - Conversation history files (auto-generated)
  - `user_preferences.json` - Saved form defaults

### Key Python Scripts

- `text_processor.py` - Handles `:rephrase:` text transformations using action configs
- `multi_form.py` - Main entry point for `:gpt:` multi-step workflow
- `customer_support.py` - Handles `:support:` customer response generation
- `llm_client.py` - Unified API client abstraction for OpenAI and Anthropic
- `action_reader.py` - Loads and merges JSON configs with defaults for actions/tasks
- `state_io.py` - JSON state persistence between form steps
- `preferences_manager.py` - Saves/loads user form preferences
- `handle_form_step1.py` / `handle_form_step2.py` - Multi-step form handlers
- `list_*.py` - Scripts that output dropdown options for Espanso forms
- `push_to_talk.py` - Dictation daemon: global F8 hook (pynput `win32_event_filter` + `suppress_event`, so apps never receive F8), click-through overlay, pastes via clipboard + Ctrl+V. Launched at login by `Startup\espanso_push_to_talk.lnk` (`.venv\Scripts\pythonw.exe`); single instance via named mutex
- `next_hotkey_state.py` - Pure hold/tap/cancel state machine (tap < 0.4s or another key while held = discard)
- `record_audio.py` - Mic capture to 16 kHz mono WAV (sounddevice)
- `transcribe_audio.py` - xAI STT (`grok-voice-transcribe-2.0`) via shush `xai` provider; `STT_KEYTERMS` biases spelling
- `clean_transcript.py` - Cleanup pass using the `speech_to_text_editor` task, same language as the transcript

### Data Flow

1. User types trigger (e.g., `:gpt:`)
2. Espanso runs script variables to populate form dropdowns
3. User fills form, Espanso passes values to handler script
4. Handler saves state to `gpt_tools/gpt_form_state.json` and outputs next trigger
5. For multi-step forms, process repeats until final processing
6. Final script calls LLM API (OpenAI or Anthropic based on model config) and outputs result to Espanso

### JSON Configuration Pattern

Actions and tasks use JSON files with template fields:

- `prompt_template` / `system_message_template` - String templates with placeholders like `{tone_instruction}`, `{target_language}`, `{input_text}`
- `temperature`, `max_tokens`, `model` - OpenAI API parameters
- `requires_second_form` - Whether additional form input is needed

## Development Commands

```bash
# Install dependencies
pip install -r requirements.txt

# Test a script directly
python scripts/action_reader.py list_actions
python scripts/action_reader.py get_task "Speech-to-Text Editor"

# Unit tests (stdlib unittest; tests/__init__.py puts scripts/ on sys.path)
.venv/Scripts/python.exe -m unittest discover -s tests -t .

# Restart push-to-talk after editing its scripts
Get-CimInstance Win32_Process -Filter "Name='pythonw.exe'" | ? CommandLine -like '*push_to_talk*' | % { Stop-Process -Id $_.ProcessId }
Start-Process "$env:APPDATA\Microsoft\Windows\Start Menu\Programs\Startup\espanso_push_to_talk.lnk"

# Restart Espanso after changes
espanso restart
```

## Environment Setup

API keys are not stored here. `llm_client.py` routes every call through the shush proxy (`http://127.0.0.1:8765/openai_espanso`, `/anthropic`), which injects the key from the shush vault. Vault secrets:

- `oai_espanso` (OpenAI, mapped by the `openai_espanso` provider in shush `proxy.json`): `shush set oai_espanso`
- `anthropic_api_key` (built-in `anthropic` provider), only needed for `claude-*` models: `shush set anthropic_api_key`

Optional `scripts/.env`: `SHUSH_PROXY_URL` to override the proxy address.

The default model is `gpt-6-luna` (OpenAI, `reasoning_effort: low`, no `temperature` since OpenAI reasoning models reject it unless effort is `none`). To use Claude, set `"model": "claude-opus-5"` in the action/task JSON config.

## coding_guidelines

- ALWAYS use functional programming: pure functions, explicit inputs/outputs, no side effects
- KEEP functions small and single-purpose (under 50 lines)
- REQUIRE type annotations on all functions
- AVOID magic methods, heavy decorators, runtime DI—explicit over implicit
- USE composition over inheritance
- ENFORCE descriptive naming: `calculate_token_usage()` not `process()`
- NEVER use global state; pass dependencies as arguments
- PREFER return values over mutations
- HANDLE errors explicitly with Result types or early returns

# Naming Conventions

- ALWAYS use snake_case for: folders, files, functions, variables, modules
- NEVER use camelCase or kebab-case
- File names MUST match primary export: `calculate_tokens.py` exports `calculate_tokens()`

# Reuse & Architecture:

- BEFORE writing new code, ALWAYS explore existing modules first
- CHECK /src/lib, /src/services folders before creating anything
- NEVER duplicate existing logic—one source of truth
- PREFER importing and extending over reimplementing
- ONLY abstract when a pattern has repeated twice; no speculative abstraction

# Dependencies & Libraries:

- ALWAYS prefer established libraries over custom implementations
- BEFORE building functionality, SEARCH for well-maintained packages
- NEVER reinvent: dates, parsing, validation, HTTP, crypto, auth
- EVALUATE libraries by: active maintenance, docs quality, adoption
- PRIORITIZE packages already in the project's dependencies
- AVOID adding dependencies for trivial operations

# Logging:

- NEVER use raw print/console.log scattered in code
- ALL logging MUST go through a centralized logging module
- CHECK for existing logging module in project before creating log statements
- Logging module MUST support:
  - Severity levels: debug, info, warn, error
  - Multiple outputs: file, MQTT, serial, console
  - Independent toggle per output destination
  - Environment-driven configuration
- Log file structure:
  - Active: /logs/{script_name}.log
  - Archived: /logs/archives/{script_name}_{timestamp}.log
- On script start: IF current log is not empty, MOVE to /logs/archives with timestamp
- If no logging module exists, CREATE one in /src/lib before adding logs

# Security:

- NEVER hardcode secrets, API keys, or credentials
- ALWAYS use environment variables via .env (note: .env is hidden from LLM)
- CREATE .env.example with required variable names and placeholder values
- VALIDATE and sanitize all external inputs

# Workflow:

- FIRST list existing modules/utils relevant to the task
- SEARCH codebase for existing implementations before creating helpers
- PROPOSE file location and imports before writing any code

# Scope:

- ONLY change what's necessary to complete the task
- NEVER refactor unrelated code unless explicitly asked

# Uncertainty:

- If requirements are ambiguous, ASK before implementing
- If unsure about existing patterns in codebase, ASK or explore first
- NEVER invent business logic; ask for clarification

# Testing:

- REQUIRE unit tests for every public function
- LIMIT to one assertion per test with descriptive names
- ALWAYS test edge cases: empty inputs, nulls, boundaries
- INJECT external dependencies (DB, APIs) for testability

# Comments & Docs:

- MINIMIZE comments; code MUST be self-evident via naming and types
- ONLY comment "why", NEVER the "what"
- NO docstrings or generated docs unless explicitly requested
- If code needs explanation, REFACTOR first
  </coding_guidelines>

## Important Notes

- Set `auto_restart: false` in `config/default.yml` to prevent Espanso from restarting when context files are saved
- All scripts use UTF-8 encoding via `io.TextIOWrapper` for proper Unicode support on Windows
- Scripts output to stdout for Espanso replacement; stderr is used for debugging (but can cause Espanso errors if not silenced)
- Form preferences are persisted in `gpt_tools/user_preferences.json` and restored on next use

## Adding New Features

### New Text Action

Create `gpt_tools/actions/action_name.json` (use snake_case):

```json
{
    "name": "action_name",
    "display_name": "Action Name",
    "requires_second_form": false,
    "prompt_template": "{tone_instruction} [Your instruction] in {target_language}: \n\n\"{input_text}\"",
    "temperature": 0.6,
    "max_tokens": 2000,
    "model": "gpt-6-luna"
}
```

### New Task Persona

Create `gpt_tools/tasks/task_name.json` (use snake_case):

```json
{
    "name": "task_name",
    "display_name": "Task Name",
    "requires_second_form": false,
    "second_form_fields": [],
    "system_message_template": "You are... {language_instruction}",
    "temperature": 0.3,
    "max_tokens": 2000,
    "model": "gpt-6-luna"
}
```

### New Tone

Create `gpt_tools/tone/tone_name.txt` (use snake_case). Add a display name header as the first line:

```
# Tone Name
Instructions for the AI on how to adopt that tone.
```

### New FAQ

Create `gpt_tools/faq/filename.md` (use snake_case) with Q&A content in Markdown format.
