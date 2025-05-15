#!/usr/bin/env python3
import os, sys
import io
import tempfile
import tkinter as tk
import threading
import time
try:
    import pyautogui
except ImportError:
    print("pyautogui not found. Please install it with 'pip install pyautogui'.")
    sys.exit(1)
from dotenv import load_dotenv
import base64, mimetypes
from openai import OpenAI
from PIL import Image, UnidentifiedImageError

# --- Loading Popup Configuration (Copied from text_processor.py) ---
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
        root.geometry("220x70")
        root.resizable(False, False)
        root.attributes('-topmost', True)
        root.overrideredirect(True) # No window decorations

        screen_width = root.winfo_screenwidth()
        screen_height = root.winfo_screenheight()
        x = (screen_width // 2) - (220 // 2)
        y = (screen_height // 2) - (70 // 2)
        root.geometry(f"+{x}+{y}")

        frame = tk.Frame(root, background='#f0f0f0', padx=10, pady=10)
        frame.pack(expand=True, fill=tk.BOTH)

        label = tk.Label(frame, text="Processing...", font=("Arial", 11), background='#f0f0f0')
        label.pack(pady=10, expand=True)
        loading_popup_obj['label'] = label
        loading_popup_obj['running'] = True
        loading_popup_obj['char_index'] = 0

        _spinner_update()
        root.mainloop()
    except Exception as e:
        print(f"Error in loading popup thread: {e}", file=sys.stderr)
    finally:
        loading_popup_obj['root'] = None
        loading_popup_obj['label'] = None
        loading_popup_obj['running'] = False
# --- End Loading Popup Configuration ---

# Ensure stdout is UTF-8 encoded
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf8')

# charge la clé API depuis .env placé dans CE dossier
load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))
API_KEY = os.getenv("OPENAI_API_KEY")
if not API_KEY:
    sys.exit("OPENAI_API_KEY manquante dans .env")

# Initialize OpenAI client
client = OpenAI(api_key=API_KEY)

if __name__ == "__main__":
    # Start loading popup
    loading_thread = threading.Thread(target=show_loading_popup_in_thread, daemon=True)
    loading_thread.start()
    time.sleep(0.3) # Brief pause for popup to appear

    final_output = "" # Variable to hold the final text to be printed by Espanso
    try:
        # Args: sentiment, relation, selected_faq_filename, target_language, include_screenshot, user_message_text, desired_answer_sketch
        if len(sys.argv) != 8:
            error_message = "Usage: python customer_support.py <sentiment> <relation> <faq_file> <target_language> <include_screenshot> \"<user_message>\" [\"<desired_answer_sketch>\"]"
            print(error_message, file=sys.stderr)
            final_output = f"Error: {error_message}"
            # sys.exit(1) # Don't exit yet, let finally close popup
        else:
            sentiment = sys.argv[1]
            relation = sys.argv[2]
            selected_faq_filename = sys.argv[3]
            target_language = sys.argv[4]
            include_screenshot_str = sys.argv[5]
            user_message_from_arg = sys.argv[6]
            desired_answer_sketch_from_arg = sys.argv[7]

            include_screenshot = include_screenshot_str.lower() == 'true'

            if not user_message_from_arg.strip():
                print("Input text from form is empty.", file=sys.stderr)
                final_output = "" # Empty output for Espanso if no input
            else:
                # --- Main script logic (screenshot, prompt construction, API call) ---
                # This is where your existing logic for handling screenshots, FAQs,
                # building prompts, and calling OpenAI client goes.
                # For brevity, it's represented here, but it should be the full logic.
                
                screenshot_path = None # Initialize for the note logic
                image_message = None # Initialize for payload construction

                if include_screenshot:
                    try:
                        # ... (Full screenshot taking, resizing, optimizing, JPEG conversion logic) ...
                        # This part creates screenshot_path and image_message if successful
                        # For this example, let's assume it populates image_message and screenshot_path correctly.
                        # Make sure your actual screenshot code is here.
                        # Example placeholder for where your screenshot code that sets image_message would be:
                        # if screenshot_is_successfully_processed:
                        #    image_message = { ... details ... }
                        #    screenshot_path = "path/to/temp_screenshot.png_or_jpg"
                        # else:
                        #    print("Screenshot failed.", file=sys.stderr)
                        #    screenshot_path = None
                        #    image_message = None
                        
                        # --- Paste actual screenshot logic here from your script ---
                        # For the purpose of this edit, I'll assume it results in image_message and screenshot_path being set.
                        # This is a simplified representation of your complex screenshot logic.
                        # The actual, full screenshot logic from your script should be here.
                        # Initialize to simulate no screenshot if not implemented here for brevity
                        temp_screenshot_file = tempfile.NamedTemporaryFile(delete=False, suffix='.png')
                        screenshot_path = temp_screenshot_file.name
                        temp_screenshot_file.close()
                        pyautogui.screenshot(screenshot_path)
                        img = Image.open(screenshot_path)
                        original_format = img.format
                        current_mime_type = f"image/{original_format.lower() if original_format else 'png'}"
                        width, height = img.size
                        new_width = int(width * 0.5); new_height = int(height * 0.5)
                        img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
                        img.save(screenshot_path, format="PNG", optimize=True)
                        current_mime_type = "image/png"
                        file_size_bytes = os.path.getsize(screenshot_path)
                        max_size_bytes = 19 * 1024 * 1024
                        if file_size_bytes > max_size_bytes:
                            print(f"Resized PNG > 19MB. Converting to JPEG.")
                            if img.mode == 'RGBA' or img.mode == 'P': img = img.convert('RGB')
                            img.save(screenshot_path, format="JPEG", quality=85, optimize=True)
                            current_mime_type = "image/jpeg"
                        with open(screenshot_path, "rb") as img_file_data:
                            image_data = img_file_data.read()
                        base64_image = base64.b64encode(image_data).decode("utf-8")
                        image_message = {"type": "image_url", "image_url": {"url": f"data:{current_mime_type};base64,{base64_image}"}}
                        # --- End of pasted screenshot logic placeholder ---

                    except Exception as e_screenshot:
                        print(f"Failed to take/process screenshot: {e_screenshot}", file=sys.stderr)
                        screenshot_path = None
                        image_message = None
                
                # Base system prompt - Modified to incorporate target_language
                base_system_prompt_intro = f"You are a concise, friendly customer support agent. Your response must be in {target_language}."
                if target_language.lower() == "french":
                    base_system_prompt_intro += " Use Canadian French unless specified otherwise."
                
                system_prompt_content = f"""{base_system_prompt_intro}
Be clear, concise, and well-written, using a 7th-grade level vocabulary and sentence structure.
The input may come from speech recognition, so if you encounter unusual phrasing, infer the intended meaning.
Always respect the original language of the input unless a specific output language is requested.
Avoid slang.
Format your response in short paragraphs.
Preserve idioms and write in a simple, conversational style.
Use natural punctuation (e.g., !, ?, ..., —), ensuring there are no spaces before terminal punctuation marks like ! or ?.
NEVER ask for more context; Just use your judgment.
"""
                
                if selected_faq_filename != "None" and selected_faq_filename.strip() != "":
                    faq_file_path = os.path.join(os.path.dirname(__file__), "..", "markdown", selected_faq_filename)
                    try:
                        with open(faq_file_path, 'r', encoding='utf-8') as f_faq:
                            faq_content = f_faq.read()
                        system_prompt_content += "\n\nFor your reference, here is some relevant FAQ information:\n---\n" + faq_content + """\n--- 
            If the question of the user is in the FAQ, DO NOT DEVIATE from the FAQ.
            If the question is not in the FAQ, answer the question based on your knowledge and the context provided.
            DO NOT make any assumptions about company policy or troubleshooting procedures."""
                    except FileNotFoundError:
                        system_prompt_content += "\n\n(Note: The selected FAQ file '" + selected_faq_filename + "' was not found.)"
                    except Exception as e_faq:
                        system_prompt_content += "\n\n(Note: Error reading FAQ file '" + selected_faq_filename + "': " + str(e_faq) + ")"

                main_user_prompt_text = (
                    f"Réponds de façon {sentiment} à un·e {relation} en {target_language}.\\n\\n"
                    f"Message reçu :\\n« {user_message_from_arg} »\\n\\n"
                    f"Réponse courte, familière mais polie, en {target_language}."
                )

                if desired_answer_sketch_from_arg and desired_answer_sketch_from_arg.strip():
                    main_user_prompt_text += (
                        f"\\n\\nIMPORTANT GUIDELINE: Here is a sketch of the desired answer. "
                        f"Use it as a strong inspiration for the tone, content, and key points of your response, "
                        f"but adapt it to ensure natural language and coherence with other instructions (like FAQs or politeness). "
                        f"Do not just rephrase it; integrate its essence into your reply.\\n"
                        f"Desired Answer Sketch:\\n« {desired_answer_sketch_from_arg.strip()} »"
                    )

                user_message_list_content = []
                user_message_list_content.append({"type": "text", "text": main_user_prompt_text})

                if image_message:
                    user_message_list_content.append(image_message)
                elif screenshot_path:
                    text_part_found = False
                    for part in user_message_list_content:
                        if part["type"] == "text":
                            part["text"] += f"\n\n(Note: A screenshot of the full screen was taken and saved at: {screenshot_path})"
                            text_part_found = True; break
                    if not text_part_found: user_message_list_content.append({"type": "text", "text": f"\n\n(Note: Screenshot at {screenshot_path})"})
                
                api_payload = {
                    "model": "gpt-4o-mini",
                    "messages": [
                        {"role": "system", "content": system_prompt_content.strip()},
                        {"role": "user", "content": user_message_list_content if image_message else main_user_prompt_text}
                    ],
                    "max_tokens": 4000,
                    "temperature": 0.6
                }

                completion = client.chat.completions.create(
                    model=api_payload["model"],
                    messages=api_payload["messages"],
                    max_tokens=api_payload["max_tokens"],
                    temperature=api_payload["temperature"]
                )
                content = completion.choices[0].message.content.strip()
                if len(content) >= 2 and content.startswith('"') and content.endswith('"'):
                    content = content[1:-1]
                final_output = content
                # --- End of main script logic ---

    except Exception as e_main:
        final_output = f"Script Error: {e_main}"
        print(f"Error in main script execution: {e_main}", file=sys.stderr)
    
    finally:
        if loading_popup_obj.get('root'):
            loading_popup_obj['running'] = False
            try:
                loading_popup_obj['root'].after(0, loading_popup_obj['root'].destroy)
            except tk.TclError:
                pass # Window might already be destroyed
        if loading_thread.is_alive():
            loading_thread.join(timeout=0.5)

    print(final_output)
