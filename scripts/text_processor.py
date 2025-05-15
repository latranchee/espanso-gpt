#!/usr/bin/env python3
import os
import sys
# import pyperclip # No longer needed for input text
import io
from openai import OpenAI
from dotenv import load_dotenv
import tkinter as tk
import threading
import time

# Ensure stdout is UTF-8 encoded
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf8')

# --- Loading Popup Configuration ---
loading_popup_obj = {'root': None, 'label': None, 'running': False, 'char_index': 0}
spinner_chars = ["⢿", "⣻", "⣽", "⣾", "⣷", "⣯", "⣟", "⡿"] # Unicode Braille spinner

def _spinner_update():
    if not loading_popup_obj.get('running') or not loading_popup_obj.get('label'):
        return
    char = spinner_chars[loading_popup_obj['char_index']]
    try:
        if loading_popup_obj['label']: # Check if label still exists
             loading_popup_obj['label'].config(text=f"Processing {char}")
    except tk.TclError: # Handle cases where the widget might be destroyed prematurely
        loading_popup_obj['running'] = False 
        return

    loading_popup_obj['char_index'] = (loading_popup_obj['char_index'] + 1) % len(spinner_chars)
    
    if loading_popup_obj.get('root') and loading_popup_obj.get('running'):
        try:
            loading_popup_obj['root'].after(120, _spinner_update) # Schedule next update
        except tk.TclError: # Handle cases where the root window might be destroyed
             loading_popup_obj['running'] = False

def show_loading_popup_in_thread():
    try:
        root = tk.Tk()
        loading_popup_obj['root'] = root
        root.title("Processing")
        root.geometry("220x70") # Adjusted size
        root.resizable(False, False)
        root.attributes('-topmost', True)
        root.overrideredirect(True) # No window decorations

        # Center the window
        screen_width = root.winfo_screenwidth()
        screen_height = root.winfo_screenheight()
        x = (screen_width // 2) - (220 // 2)
        y = (screen_height // 2) - (70 // 2)
        root.geometry(f"+{x}+{y}")

        # Use a frame for better padding and background
        frame = tk.Frame(root, background='#f0f0f0', padx=10, pady=10) # Light grey background
        frame.pack(expand=True, fill=tk.BOTH)

        label = tk.Label(frame, text="Processing...", font=("Arial", 11), background='#f0f0f0')
        label.pack(pady=10, expand=True) # Centered with padding
        loading_popup_obj['label'] = label
        loading_popup_obj['running'] = True
        loading_popup_obj['char_index'] = 0 # Reset char index

        _spinner_update() # Start the animation
        root.mainloop()
    except Exception as e:
        print(f"Error in loading popup thread: {e}", file=sys.stderr)
    finally:
        # Clean up when mainloop ends (either by destroy or error)
        loading_popup_obj['root'] = None
        loading_popup_obj['label'] = None
        loading_popup_obj['running'] = False
# --- End Loading Popup Configuration ---

# Load API key from .env file in the same directory as the script
load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))
API_KEY = os.getenv("OPENAI_API_KEY")

if not API_KEY:
    print("Error: OPENAI_API_KEY not found in .env file.", file=sys.stderr)
    sys.exit(1)

# Initialize OpenAI client
client = OpenAI(api_key=API_KEY)

def get_modified_text(action: str, tone: str, input_text: str, target_language: str) -> str:
    system_message_content = f"You are a versatile AI assistant. Skillfully modify text based on user instructions. Pay close attention to the desired action, tone, and ensure the output is in {target_language}. If the target language is French, use Canadian French unless specified otherwise."
    
    user_prompt = ""

    # Constructing prompts carefully, especially for "Walking on eggshells"
    if tone == "Walking on eggshells":
        tone_instruction = "Please be extremely careful, gentle, and overly polite in your response, as if you are walking on eggshells. Ensure the tone is very considerate and cautious."
    elif tone == "Formal":
        tone_instruction = "Please ensure the response is in a formal tone."
    else: # Friendly or default
        tone_instruction = "Please ensure the response is in a friendly and approachable tone."

    if action == "Rephrase":
        user_prompt = f"{tone_instruction} Rephrase the following text in {target_language}: \n\n\"{input_text}\""
    elif action == "Expand":
        user_prompt = f"{tone_instruction} Expand on the following text in {target_language}, providing more detail, examples, or explanations as appropriate: \n\n\"{input_text}\""
    elif action == "Fix grammar":
        user_prompt = f"{tone_instruction} Correct any grammatical errors, spelling mistakes, and improve the overall clarity of the following text, ensuring the output is in {target_language}. Preserve the original meaning. Text: \n\n\"{input_text}\""
    elif action == "Translate":
        user_prompt = f"{tone_instruction} Translate the following text to {target_language}. If the text is already in {target_language} and no other action is implied by the tone, you can politely state that or offer a minor rephrasing. Text: \n\n\"{input_text}\""
    else:
        return "Error: Unknown action specified."

    messages = [
        {"role": "system", "content": system_message_content},
        {"role": "user", "content": user_prompt}
    ]

    try:
        completion = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=messages,
            max_tokens=2000, # Increased max_tokens for potentially longer expansions/translations
            temperature=0.6
        )
        content = completion.choices[0].message.content.strip()
        # Remove leading/trailing quotes if present
        if len(content) >= 2 and content.startswith('"') and content.endswith('"'):
            content = content[1:-1]
        return content
    except Exception as e:
        return f"OpenAI API Error: {e}"

if __name__ == "__main__":
    # Start loading popup
    loading_thread = threading.Thread(target=show_loading_popup_in_thread, daemon=True)
    loading_thread.start()
    # Brief pause to allow the Tkinter window to initialize and appear.
    # Adjust if the window doesn't appear reliably before the API call starts.
    time.sleep(0.3) 

    modified_text_result = ""
    try:
        if len(sys.argv) != 5:
            print("Usage: python text_processor.py <action> <tone> \"<input_text>\" <target_language>", file=sys.stderr)
            modified_text_result = "Error: Incorrect number of arguments."
            # sys.exit(1) # Don't exit, let finally close the popup, then print error
        else:
            action_arg = sys.argv[1]
            tone_arg = sys.argv[2]
            original_text_arg = sys.argv[3]
            target_language_arg = sys.argv[4]

            if not original_text_arg.strip():
                print("Input text is empty. Please provide some text in the form.", file=sys.stderr)
                modified_text_result = "" # Espanso will just remove the trigger if output is empty
            else:
                # Make the API call
                modified_text_result = get_modified_text(action_arg, tone_arg, original_text_arg, target_language_arg)
    
    except Exception as e_main:
        modified_text_result = f"Script Error: {e_main}"
        print(f"Error in main script execution: {e_main}", file=sys.stderr)
    
    finally:
        # Stop and close the loading window
        if loading_popup_obj.get('root'):
            loading_popup_obj['running'] = False # Signal spinner to stop
            try:
                # Schedule destroy from Tkinter thread to avoid cross-thread issues
                loading_popup_obj['root'].after(0, loading_popup_obj['root'].destroy)
            except tk.TclError:
                pass # Window might already be destroyed or in process
        
        # Ensure the thread has a moment to process the destroy command and terminate.
        # If the popup sometimes lingers, increasing this timeout or ensuring the thread fully exits might be needed.
        if loading_thread.is_alive():
            loading_thread.join(timeout=0.5) 

    print(modified_text_result) 