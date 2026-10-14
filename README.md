# Espanso GPT

An Espanso configuration for Windows that brings AI text tools and push-to-talk dictation to any app.

## Features

- **Multi-step AI Task Form** (`:gpt:`): configure AI tasks with customizable parameters and conversation history
- **Text Transformation** (`:rephrase:`): rephrase, expand, fix grammar, or translate text in a chosen tone
- **Customer Support Replies** (`:support:`): draft answers that follow your own FAQ files
- **F8 Dictation**: tap F8 and speak. Your words show live in a bubble next to the mouse, an AI pass cleans them up, and one click pastes the result into any text field
- **Context-Aware AI**: the system asks for more information when it needs it
- **JSON Configuration**: add or modify AI actions and tasks without coding
- **No API keys on disk**: keys stay in the [shush](https://github.com/latranchee/shush) vault, and the scripts call a local proxy that adds them

## Screenshots

### Multi-step AI Task Form

![AI Task Form](https://github.com/latranchee/espanso-gpt/raw/master/screenshots/step_1.jpg)

![AI Task Form](https://github.com/latranchee/espanso-gpt/raw/master/screenshots/step_2.jpg)

### Text Transformation

![Text Transformation](https://github.com/latranchee/espanso-gpt/raw/master/screenshots/text_transform.png)

### Context Requests

![AI Task Form](https://github.com/latranchee/espanso-gpt/raw/master/screenshots/context.jpg)

## Requirements

- Windows 10 (version 1703 or later) or Windows 11
- [Espanso](https://espanso.org/install/), installed for your user (the default)
- Python 3.10 or newer from [python.org](https://www.python.org/downloads/) (tested on 3.12 and 3.14)
- [shush](https://github.com/latranchee/shush), which holds the API keys
- An OpenAI API key that can use `gpt-6-luna`
- For dictation only: an xAI API key (speech-to-text) and a microphone

## Setup

### 1. Install Espanso

Follow [espanso.org/install](https://espanso.org/install/). Keep the default per-user install location: the `:gpt:` form calls `%LOCALAPPDATA%\Programs\Espanso\espanso.cmd`.

### 2. Set Up shush and Your API Keys

API keys never live in this repo or in a `.env` file. Every AI call goes to the local shush proxy (`http://127.0.0.1:8765`), which adds the key from the shush vault.

1. Install shush by following its README: clone it and add its folder to your `PATH`.
2. Add these two providers under `"providers"` in shush's `proxy.json`, next to `secret_manager.ps1` (create the file if it doesn't exist):

   ```json
   {
     "providers": {
       "openai_espanso": { "secret": "oai_espanso", "auth": "bearer", "base_url": "https://api.openai.com", "max_body_bytes": 26214400 },
       "xai": { "secret": "xai", "auth": "bearer", "base_url": "https://api.x.ai" }
     }
   }
   ```

3. Store the keys. Each command prompts for the value:

   ```powershell
   shush set oai_espanso
   shush set xai          # dictation only
   ```

4. Start the proxy and leave it running:

   ```powershell
   shush proxy start
   ```

   To start it with Windows instead, see the service mode in shush's README (`install_proxy_service.ps1`).

### 3. Clone This Repository as Your Espanso Config Folder

This repo *is* the Espanso config folder (`config/`, `match/`). Stop Espanso, move the existing folder aside, and clone in its place:

```powershell
espanso stop
Rename-Item "$env:APPDATA\espanso" espanso.bak
git clone https://github.com/latranchee/espanso-gpt.git "$env:APPDATA\espanso"
```

Copy anything you want to keep from `espanso.bak\match` into the new `match` folder.

### 4. Run the Installer

```powershell
cd "$env:APPDATA\espanso"
powershell -ExecutionPolicy Bypass -File .\install.ps1
```

The installer:

- checks that the repo is in Espanso's config folder and that Espanso is installed
- creates the `.venv` folder the triggers run from and installs `requirements.txt`
- checks that the shush proxy is running and that each key works, and prints exactly what to fix if not
- checks for a microphone, adds a Startup shortcut for F8 dictation, and starts it
- restarts Espanso

Run it again after fixing anything it reports, and after each `git pull`. To skip dictation (no Startup shortcut, no xAI key needed), add `-SkipDictation`.

**About `auto_restart`:** many scripts (especially the `:gpt:` task assistant) save conversation history and state files under `gpt_tools/`. With Espanso's `auto_restart` on, each save would restart Espanso and interrupt you, so `config/default.yml` sets `auto_restart: false`. After you edit match files or scripts, run `espanso restart` yourself.

## Usage

### AI Task Assistant

Type `:gpt:` and a form will appear, letting you:

- Select conversation mode (new or continue last)
- Choose task objective (Q&A, Speech-to-Text, Customer Support)
- Set output language
- Provide initial prompt or use clipboard content
- Optionally include screenshots

This multi-step form adapts to your selected objective, asking additional questions when more context is needed to provide the most relevant assistance.

### Text Transformations

Type `:rephrase:` to open the text transformation menu where you can:

- Rephrase text in different tones (friendly, formal, etc.)
- Expand on ideas
- Fix grammar
- Translate between languages

### Customer Support Replies

Type `:support:` to draft a reply to a customer, using one of your FAQ files as the source of truth (see [FAQ System](#faq-system)).

### Dictation (F8)

The installer's Startup shortcut keeps this running in the background from login.

1. Tap **F8** and speak. Your words appear live in a bubble next to the mouse pointer; nothing is typed into the app yet.
2. Tap **F8** again to stop. A soft tick means `gpt-6-luna` is cleaning up the text: punctuation, grammar, filler words, in the language you spoke. A bell means it's ready, usually within 1 to 3 seconds.
3. Click inside any text field. The text is pasted where you clicked, and it also stays on the clipboard. If you click before the bell, it pastes as soon as the text is ready.

More:

- Hold F8 instead of tapping to talk only while the key is down.
- Tap F8 again before pasting to add more to the same bubble.
- **Esc** dismisses the bubble.
- Hands-free mode stops by itself after 60 seconds without speech.
- While dictation runs, F8 never reaches other apps.
- If a name keeps coming out misspelled, add it to `STT_KEYTERMS` in `scripts/stream_transcription.py`.

## Customization

You can customize triggers and add your own shortcuts by modifying the YAML files in the `match` directory.

## JSON Configuration System

One of the powerful features of this system is its JSON-based configuration system, allowing you to modify AI behaviors without changing code.

### Actions (Text Transformations)

The `gpt_tools/actions/` directory contains JSON files defining text transformations available in the `:rephrase:` form:

```json
{
    "name": "rephrase",
    "display_name": "Rephrase",
    "requires_second_form": false,
    "prompt_template": "Rephrase the following text in {target_language}, follow these guidelines {tone_instruction}: \n\n\"{input_text}\"",
    "temperature": 0.6,
    "max_tokens": 2000,
    "model": "gpt-6-luna"
}
```

#### Key Fields in Action JSON Files

- `name`: Internal name, the same as the file name without `.json`
- `display_name`: Name shown in the dropdown (falls back to the file name)
- `requires_second_form`: Whether this action needs additional input (usually false)
- `prompt_template`: Template for the AI prompt with variables:
  - `{tone_instruction}`: Loaded from tone files
  - `{target_language}`: Selected language
  - `{input_text}`: The text to transform
- `max_tokens`: Maximum response length
- `model`: `gpt-6-luna` by default. A `claude-*` model works too, once you add your Anthropic key with `shush set anthropic_api_key`
- `reasoning_effort` (optional): how much `gpt-6-luna` thinks before answering: `none`, `low` (the default), `medium`, `high`, or `xhigh`
- `temperature`: Controls randomness (0.0-1.0). Reasoning models like `gpt-6-luna` only use it when `reasoning_effort` is `none`

#### Adding a New Action

To add a new action, create a JSON file in `gpt_tools/actions/` with the appropriate fields, using a snake_case file name.

Example (`summarize.json`):

```json
{
    "name": "summarize",
    "display_name": "Summarize",
    "requires_second_form": false,
    "prompt_template": "{tone_instruction} Summarize the following text in {target_language}: \n\n\"{input_text}\"",
    "temperature": 0.4,
    "max_tokens": 1500,
    "model": "gpt-6-luna"
}
```

### Tasks (AI Assistants)

The `gpt_tools/tasks/` directory contains JSON files defining the AI personas available in the `:gpt:` form:

```json
{
    "name": "speech_to_text_editor",
    "display_name": "Speech-to-Text Editor",
    "requires_second_form": false,
    "second_form_fields": [],
    "system_message_template": "You are a meticulous Speech-to-Text Editor. Your primary function is to...[detailed instructions]... {language_instruction}",
    "temperature": 0.3,
    "max_tokens": 2000,
    "reasoning_effort": "none",
    "model": "gpt-6-luna"
}
```

#### Key Fields in Task JSON Files

- `name`, `display_name`: Same as Actions
- `requires_second_form`: Whether this task needs a second form (like Customer Support)
- `second_form_fields`: List of additional fields needed
- `system_message_template`: Base system prompt with variables:
  - `{language_instruction}`: Language preference
  - `{sentiment_instruction}`: Sentiment (for customer support)
  - `{relation_instruction}`: Relationship type (for customer support)
  - `{faq_content}`: FAQ content (if selected)
- `temperature`, `max_tokens`, `model`, `reasoning_effort`: Same as Actions

The Speech-to-Text Editor task is also the prompt F8 dictation uses to clean up what you said.

#### Adding a New Task

To add a new task, create a JSON file in `gpt_tools/tasks/` with the appropriate fields, using a snake_case file name.

Example (`code_reviewer.json`):

```json
{
    "name": "code_reviewer",
    "display_name": "Code Reviewer",
    "requires_second_form": false,
    "second_form_fields": [],
    "system_message_template": "You are an experienced code reviewer. Help identify issues, improve code quality, and suggest better practices. {language_instruction}",
    "temperature": 0.2,
    "max_tokens": 2500,
    "model": "gpt-6-luna"
}
```

### FAQ System

The FAQ system allows you to provide context-specific information to guide AI responses, particularly for customer support tasks.

#### How to Use FAQs

1. **Create FAQ Files**: Place Markdown (.md) files in the `gpt_tools/faq/` directory
2. **Structure**: Write Q&A style content with headers and lists as needed
3. **Select in Forms**: When using `:support:`, or `:gpt:` with "Customer Support Task", you can select an FAQ file
4. **Effect**: The AI will prioritize information from the FAQ when answering related questions

FAQ files often hold customer or business details, so git ignores every file in `gpt_tools/faq/` except `sample.md`. Copy yours to a new machine yourself.

#### Example FAQ File (`product_returns.md`)

```markdown
# Product Returns Policy

## Return Window
Products can be returned within 30 days of purchase with receipt.

## Conditions for Returns
- Product must be in original packaging
- Item must be unused and undamaged
- Receipt or proof of purchase is required

## Exceptions
Electronics and opened media (games, music, software) cannot be returned once opened.
```

## Tone Files

The `gpt_tools/tone/` directory contains text files that define different tones for text transformations, such as `friendly.txt` and `formal.txt`.

To add a tone, create a snake_case `.txt` file. Its first line is the name shown in the dropdown, as a header (`# Friendly`), and the rest tells the AI how to speak in that tone.

## Configuration

Optional settings go in `scripts/.env` (see `scripts/.env.example`). It never holds API keys.

- `SHUSH_PROXY_URL`: where the shush proxy listens, if not `http://127.0.0.1:8765`

## Troubleshooting

- **Something isn't working**: run `.\install.ps1` again. It checks each piece and says what to fix.
- **AI triggers fail**: the shush proxy must be running (`shush proxy start`). Script logs are in `logs/`.
- **Python Errors**: the triggers run the Python in this folder's `.venv`, which the installer creates. It needs Python 3.10 or newer.
- **Form Not Appearing**: Make sure Espanso is running (`espanso status`)
- **Unexpected Espanso Restarts**: make sure `auto_restart: false` is still set in `config/default.yml` (see "About `auto_restart`" under Setup).
- **Invalid JSON Error**: Check JSON syntax in your custom action or task files
- **Missing Tone/FAQ**: Ensure the files are in the correct directories with proper file extensions
- **F8 does nothing**: the dictation daemon starts at login from the Startup shortcut. Run the installer again to restart it. Errors are in `logs/push_to_talk.log`.
- **Dictation hears nothing**: Windows must let desktop apps use the microphone (Settings > Privacy & security > Microphone).
- **No paste in some apps**: dictation can't paste into, or catch F8 in, apps running as administrator.

## Contributing

Contributions are welcome! Feel free to submit pull requests or open issues to suggest improvements.

## License

MIT
