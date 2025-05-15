# Espanso GPT

A powerful Espanso configuration with GPT-powered text enhancements, emoji packs, utilities, and productivity tools.

## Features

- **Multi-step AI Task Form**: Configure AI tasks with customizable parameters
- **Text Transformation**: Rephrase, expand, fix grammar, or translate text with a simple shortcut
- **Custom GPT Prompts**: Easily create and manage your own GPT prompts
- **Context-Aware AI**: The system will ask for additional information when needed
- **JSON Configuration**: Easily add or modify AI actions and tasks without coding
- **FAQ Integration**: Provide context-specific information to guide AI responses

## Screenshots

### Multi-step AI Task Form

![AI Task Form](https://github.com/latranchee/espanso-gpt/raw/master/screenshots/step_1.jpg)

![AI Task Form](https://github.com/latranchee/espanso-gpt/raw/master/screenshots/step_2.jpg)

### Text Transformation

![Text Transformation](https://github.com/latranchee/espanso-gpt/raw/master/screenshots/text_transform.png)

### Context Requests

![AI Task Form](https://github.com/latranchee/espanso-gpt/raw/master/screenshots/context.jpg)

## Setup Instructions

### 1. Install Espanso

First, install Espanso by following the instructions at [espanso.org](https://espanso.org/install/).

### 2. Clone this Repository

```bash
git clone https://github.com/latranchee/espanso-gpt.git
cd espanso-gpt
```

### 3. Set Up Python Environment

```bash
# Create and activate a virtual environment (optional but recommended)
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### 4. Create an .env File

Create a file named `.env` in the `scripts` directory with the following content:

```
OPENAI_API_KEY=your_openai_api_key_here
```

Replace `your_openai_api_key_here` with your actual OpenAI API key.

### 5. Configure Espanso

Copy the contents of this repository to your Espanso configuration directory:

- Windows: `%APPDATA%\espanso`
- macOS: `~/Library/Application Support/espanso`
- Linux: `~/.config/espanso`

### 6. Restart Espanso

```bash
espanso restart
```

**Important Note on `auto_restart`:**
Many scripts in this configuration (especially the `:gpt:` task assistant) save conversation history and temporary state files within the `gpt_tools/` subdirectory. If Espanso's `auto_restart` feature is enabled (which it might be by default), these file operations can trigger frequent and unwanted Espanso restarts, interrupting your workflow.

It is **highly recommended** to set `auto_restart: false` in your main Espanso configuration file (usually `config/default.yml` located in your Espanso config directory). With `auto_restart: false`, you will need to manually run `espanso restart` only when you make intentional changes to your Espanso configuration files (e.g., editing `.yml` match files or Python scripts).

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

## Customization

You can customize triggers and add your own shortcuts by modifying the YAML files in the `match` directory.

## JSON Configuration System

One of the powerful features of this system is its JSON-based configuration system, allowing you to modify AI behaviors without changing code.

### Actions (Text Transformations)

The `gpt_tools/actions/` directory contains JSON files defining text transformations available in the `:rephrase:` form:

```json
{
    "name": "Rephrase",
    "requires_second_form": false,
    "prompt_template": "{tone_instruction} Rephrase the following text in {target_language}: \n\n\"{input_text}\"",
    "temperature": 0.6,
    "max_tokens": 2000,
    "model": "gpt-4o-mini"
}
```

#### Key Fields in Action JSON Files

- `name`: Display name of the action
- `requires_second_form`: Whether this action needs additional input (usually false)
- `prompt_template`: Template for the AI prompt with variables:
  - `{tone_instruction}`: Loaded from tone files
  - `{target_language}`: Selected language
  - `{input_text}`: The text to transform
- `temperature`: Controls randomness (0.0-1.0)
- `max_tokens`: Maximum response length
- `model`: OpenAI model to use

#### Adding a New Action

To add a new action, create a JSON file in `gpt_tools/actions/` with the appropriate fields. The file name (without .json) becomes the action name in the dropdown.

Example (`Summarize.json`):

```json
{
    "name": "Summarize",
    "requires_second_form": false,
    "prompt_template": "{tone_instruction} Summarize the following text in {target_language}: \n\n\"{input_text}\"",
    "temperature": 0.4,
    "max_tokens": 1500,
    "model": "gpt-4o-mini"
}
```

### Tasks (AI Assistants)

The `gpt_tools/tasks/` directory contains JSON files defining the AI personas available in the `:gpt:` form:

```json
{
    "name": "Speech-to-Text Editor",
    "requires_second_form": false,
    "second_form_fields": [],
    "system_message_template": "You are a meticulous Speech-to-Text Editor. Your primary function is to...[detailed instructions]... {language_instruction}",
    "temperature": 0.3,
    "max_tokens": 2000,
    "model": "gpt-4o-mini"
}
```

#### Key Fields in Task JSON Files

- `name`: Display name of the task
- `requires_second_form`: Whether this task needs a second form (like Customer Support)
- `second_form_fields`: List of additional fields needed
- `system_message_template`: Base system prompt with variables:
  - `{language_instruction}`: Language preference
  - `{sentiment_instruction}`: Sentiment (for customer support)
  - `{relation_instruction}`: Relationship type (for customer support)
  - `{faq_content}`: FAQ content (if selected)
- `temperature`, `max_tokens`, `model`: Same as Actions

#### Adding a New Task

To add a new task, create a JSON file in `gpt_tools/tasks/` with the appropriate fields. The file name (without .json) becomes the task name in the dropdown.

Example (`Code_Reviewer.json`):

```json
{
    "name": "Code Reviewer",
    "requires_second_form": false,
    "second_form_fields": [],
    "system_message_template": "You are an experienced code reviewer. Help identify issues, improve code quality, and suggest better practices. {language_instruction}",
    "temperature": 0.2,
    "max_tokens": 2500,
    "model": "gpt-4o-mini"
}
```

### FAQ System

The FAQ system allows you to provide context-specific information to guide AI responses, particularly for customer support tasks.

#### How to Use FAQs

1. **Create FAQ Files**: Place Markdown (.md) files in the `gpt_tools/faq/` directory
2. **Structure**: Write Q&A style content with headers and lists as needed
3. **Select in Forms**: When using `:gpt:` with "Customer Support Task", you can select an FAQ file
4. **Effect**: The AI will prioritize information from the FAQ when answering related questions

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

The `gpt_tools/tone/` directory contains text files that define different tones for text transformations:

- `Friendly.txt`: For warm, approachable language
- `Formal.txt`: For professional, business-like language
- `Conspiro.txt`: For conspiracy theorist style language (humorous)

To add a new tone, simply create a .txt file with instructions for the AI on how to speak in that tone.

## Troubleshooting

- **Python Errors**: Ensure Python 3.6+ is installed and in your PATH
- **OpenAI API Issues**: Verify your API key is correctly set in the `.env` file
- **Form Not Appearing**: Make sure Espanso is running (`espanso status`)
- **Unexpected Espanso Restarts**: If Espanso restarts frequently when using the `:gpt:` trigger, ensure `auto_restart: false` is set in your `config/default.yml` file (see "Important Note on `auto_restart`" in the Setup Instructions section).
- **Invalid JSON Error**: Check JSON syntax in your custom action or task files
- **Missing Tone/FAQ**: Ensure the files are in the correct directories with proper file extensions

## Contributing

Contributions are welcome! Feel free to submit pull requests or open issues to suggest improvements.

## License

MIT
