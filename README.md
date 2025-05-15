# Espanso GPT

A powerful Espanso configuration with GPT-powered text enhancements, emoji packs, utilities, and productivity tools.

## Features

- **Multi-step AI Task Form**: Configure AI tasks with customizable parameters
- **Text Transformation**: Rephrase, expand, fix grammar, or translate text with a simple shortcut
- **Custom GPT Prompts**: Easily create and manage your own GPT prompts
- **Context-Aware AI**: The system will ask for additional information when needed

## Screenshots

### Multi-step AI Task Form

![AI Task Form](https://github.com/latranchee/espanso-gpt/raw/master/screenshots/ai_task_form.png)

### Text Transformation

![Text Transformation](https://github.com/latranchee/espanso-gpt/raw/master/screenshots/text_transformation.png)

### Context Requests

![Context Requests](https://github.com/latranchee/espanso-gpt/raw/master/screenshots/context_request.png)

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

## Usage

### AI Task Assistant

Type `:gpt` and a form will appear, letting you:

- Select conversation mode (new or continue last)
- Choose task objective (Q&A, Speech-to-Text, Customer Support)
- Set output language
- Provide initial prompt or use clipboard content
- Optionally include screenshots

This multi-step form adapts to your selected objective, asking additional questions when more context is needed to provide the most relevant assistance.

### Text Transformations

Type `:txt` to open the text transformation menu where you can:

- Rephrase text in different tones (friendly, formal, etc.)
- Expand on ideas
- Fix grammar
- Translate between languages

## Customization

You can customize triggers and add your own shortcuts by modifying the YAML files in the `match` directory.

## Troubleshooting

- **Python Errors**: Ensure Python 3.6+ is installed and in your PATH
- **OpenAI API Issues**: Verify your API key is correctly set in the `.env` file
- **Form Not Appearing**: Make sure Espanso is running (`espanso status`)

## Contributing

Contributions are welcome! Feel free to submit pull requests or open issues to suggest improvements.

## License

MIT
