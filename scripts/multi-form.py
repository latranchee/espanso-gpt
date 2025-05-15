# gpt_chat.py
import sys, os, io, json
import tkinter
import threading
import time
from openai import OpenAI
import customtkinter
from dotenv import load_dotenv
from action_reader import get_task  # Import our new action reader

# New imports for screenshot functionality
import tempfile
import pyautogui
import base64
import mimetypes
from PIL import Image, UnidentifiedImageError

# Assuming state_io.py is in the same directory or Python's path is configured.
from state_io import load_state, delete_state, STATE_FILE_PATH, CONFIG_DIR

DEBUG_MODE = False # Disable debug mode to prevent Espanso rendering errors

# Ensure stdout handles UTF-8 for Espanso
if sys.stdout.encoding != 'utf-8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# Load API key from .env file in the script's directory
dotenv_path = os.path.join(os.path.dirname(__file__), ".env")
load_dotenv(dotenv_path)
API_KEY = os.getenv("OPENAI_API_KEY")

if not API_KEY:
    if DEBUG_MODE: sys.stderr.write("ERROR: OPENAI_API_KEY not found. Checked .env at: " + dotenv_path + "\n")
    print("ERROR: OPENAI_API_KEY not found. Please ensure it is set in scripts/.env")
    sys.exit(1)

client = OpenAI(api_key=API_KEY)

if DEBUG_MODE:
    sys.stderr.write("DEBUG: gpt_chat.py script started.\n")

# Global GUI and state variables
user_choice = None
app_root = None 
loading_popup_obj = {'root': None, 'label': None, 'running': False, 'char_index': 0}
spinner_chars = ["⢿", "⣻", "⣽", "⣾", "⣷", "⣯", "⣟", "⡿"]
loading_thread = None

# --- Constants for Conversation History ---
CONTEXT_DIR_NAME = "gpt_tools/context"
CONTEXT_DIR_PATH = os.path.join(CONFIG_DIR, CONTEXT_DIR_NAME)
LAST_CONV_ID_FILENAME = "last_conversation_id.txt"
LAST_CONV_ID_FILEPATH = os.path.join(CONFIG_DIR, "gpt_tools", LAST_CONV_ID_FILENAME)

# --- GUI Helper Functions (show_tk_loading_popup_in_thread, setup_root_window, destroy_root_window, etc.) ---
# These functions (_tk_spinner_update, show_tk_loading_popup_in_thread, setup_root_window, destroy_root_window, 
# show_custom_need_dialog, show_options_dialog) are assumed to be defined here as they were in the original script.
# For brevity in this diff, their full code is not repeated but should be present.

def _tk_spinner_update():
    if not loading_popup_obj.get('running') or not loading_popup_obj.get('label'):
        return
    char = spinner_chars[loading_popup_obj['char_index']]
    try:
        if loading_popup_obj['label']:
             loading_popup_obj['label'].config(text=f"Processing {char}")
    except tkinter.TclError:
        loading_popup_obj['running'] = False 
        return
    loading_popup_obj['char_index'] = (loading_popup_obj['char_index'] + 1) % len(spinner_chars)
    if loading_popup_obj.get('root') and loading_popup_obj.get('running'):
        try:
            loading_popup_obj['root'].after(120, _tk_spinner_update)
        except tkinter.TclError:
             loading_popup_obj['running'] = False

def show_tk_loading_popup_in_thread():
    if DEBUG_MODE: sys.stderr.write("DEBUG: show_tk_loading_popup_in_thread started\n")
    try:
        root = tkinter.Tk()
        loading_popup_obj['root'] = root
        root.title("Processing")
        root.geometry("220x70")
        root.resizable(False, False)
        root.attributes('-topmost', True)
        root.overrideredirect(True)
        screen_width = root.winfo_screenwidth()
        screen_height = root.winfo_screenheight()
        x = (screen_width // 2) - (220 // 2)
        y = (screen_height // 2) - (70 // 2)
        root.geometry(f"+{x}+{y}")
        frame = tkinter.Frame(root, background='#f0f0f0', padx=10, pady=10)
        frame.pack(expand=True, fill=tkinter.BOTH)
        label = tkinter.Label(frame, text="Processing...", font=("Arial", 11), background='#f0f0f0')
        label.pack(pady=10, expand=True)
        loading_popup_obj['label'] = label
        loading_popup_obj['running'] = True
        loading_popup_obj['char_index'] = 0
        _tk_spinner_update()
        root.mainloop()
    except Exception as e:
        if DEBUG_MODE: sys.stderr.write(f"DEBUG ERROR in loading popup thread: {e}\n")
    finally:
        if DEBUG_MODE: sys.stderr.write("DEBUG: show_tk_loading_popup_in_thread finished\n")
        loading_popup_obj['root'] = None
        loading_popup_obj['label'] = None
        loading_popup_obj['running'] = False

def setup_root_window():
    global app_root
    if DEBUG_MODE and app_root is None: sys.stderr.write("DEBUG: setup_root_window: app_root is None, creating new CTk root.\n")
    if DEBUG_MODE and app_root is not None and not app_root.winfo_exists(): sys.stderr.write("DEBUG: setup_root_window: app_root exists but window doesn't (destroyed), creating new CTk root.\n")
    if app_root is None or not app_root.winfo_exists():
        app_root = customtkinter.CTk()
        app_root.withdraw()
        if DEBUG_MODE: sys.stderr.write("DEBUG: New CTk root created and withdrawn.\n")
    return app_root

def destroy_root_window():
    global app_root
    if DEBUG_MODE and app_root is not None and app_root.winfo_exists() : sys.stderr.write("DEBUG: destroy_root_window called. Attempting to destroy CTk root.\n")
    if DEBUG_MODE and (app_root is None or (app_root is not None and not app_root.winfo_exists())): sys.stderr.write("DEBUG: destroy_root_window called, but no existing CTk root to destroy.\n")
    if app_root is not None and app_root.winfo_exists():
        try: app_root.destroy()
        except Exception: pass
    app_root = None

def show_custom_need_dialog(question_text, parent_window):
    if DEBUG_MODE: sys.stderr.write(f"DEBUG: show_custom_need_dialog: Question='{question_text[:100]}...'\n")
    dialog_value = None
    dialog = customtkinter.CTkToplevel(parent_window)
    dialog.title("GPT Needs Info")
    dialog.attributes("-topmost", True)
    dialog_width = 450 
    dialog_height = 220
    screen_width = parent_window.winfo_screenwidth()
    screen_height = parent_window.winfo_screenheight()
    x = (screen_width // 2) - (dialog_width // 2)
    y = (screen_height // 2) - (dialog_height // 2)
    dialog.geometry(f"{dialog_width}x{dialog_height}+{x}+{y}")
    dialog.resizable(False, False)
    def on_ok():
        nonlocal dialog_value
        dialog_value = entry.get()
        dialog.destroy()
    def on_cancel():
        nonlocal dialog_value
        dialog_value = None
        dialog.destroy()
    dialog.protocol("WM_DELETE_WINDOW", on_cancel)
    main_frame = customtkinter.CTkFrame(dialog)
    main_frame.pack(padx=10, pady=10, expand=True, fill="both")
    label = customtkinter.CTkLabel(main_frame, text=question_text, wraplength=dialog_width-40)
    label.pack(pady=(10,10), padx=10)
    entry = customtkinter.CTkEntry(main_frame, width=dialog_width-60)
    entry.pack(pady=(0,15), padx=20, fill="x")
    entry.focus_set()
    buttons_frame = customtkinter.CTkFrame(main_frame)
    buttons_frame.pack(pady=(0,5))
    ok_button = customtkinter.CTkButton(buttons_frame, text="OK", command=on_ok, width=100)
    ok_button.pack(side="left", padx=(0,10))
    entry.bind("<Return>", lambda event: on_ok())
    cancel_button = customtkinter.CTkButton(buttons_frame, text="Cancel", command=on_cancel, width=100)
    cancel_button.pack(side="left", padx=(10,0))
    dialog.bind("<Escape>", lambda event: on_cancel())
    dialog.transient(parent_window)
    dialog.grab_set()
    parent_window.wait_window(dialog)
    return dialog_value

def show_options_dialog(intro_text, options, parent_window):
    if DEBUG_MODE: sys.stderr.write(f"DEBUG: show_options_dialog: Intro='{intro_text[:100]}...', Options={options}\n")
    global user_choice
    user_choice = None
    dialog = customtkinter.CTkToplevel(parent_window)
    dialog.title("GPT Suggests Options")
    dialog.attributes("-topmost", True)
    dialog_width = 700
    dialog_height = 500
    screen_width = parent_window.winfo_screenwidth()
    screen_height = parent_window.winfo_screenheight()
    x = (screen_width // 2) - (dialog_width // 2)
    y = (screen_height // 2) - (dialog_height // 2)
    dialog.geometry(f"{dialog_width}x{dialog_height}+{x}+{y}")
    dialog.resizable(False, False)
    dialog.protocol("WM_DELETE_WINDOW", lambda: on_button_click(None))
    label = customtkinter.CTkLabel(dialog, text=intro_text, wraplength=330)
    label.pack(padx=20, pady=(20, 10))
    buttons_frame = customtkinter.CTkScrollableFrame(dialog)
    buttons_frame.pack(padx=10, pady=(0, 10), fill="both", expand=True)
    def on_button_click(choice):
        global user_choice
        user_choice = choice
        dialog.destroy()
    for option_text in options:
        button = customtkinter.CTkButton(buttons_frame, text=option_text, command=lambda opt=option_text: on_button_click(opt))
        button.pack(pady=5, padx=10, fill="x")
    dialog.transient(parent_window)
    dialog.grab_set()
    parent_window.wait_window(dialog)
    return user_choice

def ask_gpt(history):
    global loading_thread
    if DEBUG_MODE: sys.stderr.write(f"DEBUG ask_gpt: Called with history (last msg type: {history[-1]['role'] if history else 'N/A'}, content: '{str(history[-1]['content'])[:50]}...' if history else 'N/A')\n")
    
    # <<< ADDING HISTORY LOGGING TO FILE >>>
    if DEBUG_MODE:
        try:
            debug_file_target = os.path.join(os.path.expanduser("~"), "espanso_debug_paths.txt")
            with open(debug_file_target, "a") as f_debug: # 'a' to append
                f_debug.write(f"\n--- ask_gpt HISTORY (timestamp: {time.time()}) ---\n")
                f_debug.write(json.dumps(history, indent=2))
                f_debug.write("\n--- END ask_gpt HISTORY ---\n")
        except Exception as e_hist_log:
            sys.stderr.write(f"ERROR ask_gpt: Could not write history to debug file: {e_hist_log}\n")
    # <<< END HISTORY LOGGING >>>

    if loading_thread is None or not loading_thread.is_alive():
        loading_thread = threading.Thread(target=show_tk_loading_popup_in_thread, daemon=True)
        loading_thread.start()
        time.sleep(0.3)
    try:
        r = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=history,
            temperature=0.3,
        )
        ai_response_content = r.choices[0].message.content
        if DEBUG_MODE: sys.stderr.write(f"DEBUG ask_gpt: OpenAI API call successful. Response: '{ai_response_content[:100]}...'\n")
        return ai_response_content
    finally:
        if DEBUG_MODE: sys.stderr.write("DEBUG ask_gpt: In finally block, stopping loading indicator.\n")
        if loading_popup_obj.get('root'):
            loading_popup_obj['running'] = False
            try:
                loading_popup_obj['root'].after(0, loading_popup_obj['root'].destroy)
            except tkinter.TclError:
                pass 
            except Exception as e:
                pass
        if loading_thread is not None and loading_thread.is_alive():
            loading_thread.join(timeout=0.5)
        loading_thread = None

# --- Persona Definitions (SPEECH_TO_TEXT_EDITOR_INSTRUCTIONS, base_system_prompt_core) ---
# These are assumed to be defined here as they were in the original script.
# For brevity, their full code is not repeated but should be present.
SPEECH_TO_TEXT_EDITOR_INSTRUCTIONS = (
    "You are a meticulous Speech-to-Text Editor. Your primary function is to receive text that is presumed to be a direct transcription of spoken language, potentially containing errors, disfluencies, and informalities. "
    "Your goal is to transform this raw input into clear, concise, grammatically correct, and easily readable written text, suitable for records or communication.\n\n"
    "Follow these guidelines strictly:\n"
    "1. Interpret Intent: Analyze the input to understand the user's most likely intended meaning, even if the phrasing is awkward or contains errors.\n"
    "2. Correct Errors: Fix spelling mistakes, grammatical errors, and incorrect punctuation.\n"
    "3. Remove Disfluencies: Eliminate filler words (e.g., \"um,\" \"uh,\" \"like,\" \"you know\"), stutters, false starts, and unnecessary repetitions.\n"
    "4. Enhance Clarity & Conciseness: Restructure sentences if necessary to improve clarity and flow. Remove redundant phrases or information without losing the core message. Aim for well-formed sentences.\n"
    "5. Preserve Core Meaning: It is crucial that you DO NOT add new information or opinions, and DO NOT change the fundamental meaning or intent of the original spoken message. Your role is to clarify and correct, not to create or alter substance.\n"
    "6. Handle Ambiguity (NEED): If a specific part of the input is so ambiguous that you cannot confidently determine the intended meaning even with context, you MUST ask for clarification for ONLY that specific ambiguous part. "
    "Preface your question with the exact string 'NEED:'. Example: 'NEED: I understood the part about the project deadline, but could you clarify what you meant by [specific ambiguous phrase]?' Use this sparingly and only when essential.\n"
    "7. Output Format: Your output should be ONLY the cleaned-up, edited text. Do not include any conversational preface, remarks about your process, or any text other than the corrected transcription, unless you are using the 'NEED:' prefix for clarification as described above.\n"
    "8. Interaction Flow: The general interaction rules for 'OPTIONS:' (if you were to offer choices about how to interpret something, though less common for this role) and 'Direct Answer' (which in this case is the cleaned text) still apply from the base instructions. Your primary output will be a 'Direct Answer' consisting of the edited text."
)

base_system_prompt_core = (
    "Your primary goal is to provide a direct and helpful answer whenever possible. Strive to understand the user's intent and provide a substantive response with the information available.\n\n" 
    "1. Clarification (NEED): If, and only if, the user\'s request is critically vague and you cannot provide any meaningful answer or reasonable options, " 
    "you MAY ask for clarification. Preface your clarifying question with the exact string 'NEED:'. "
    "The question should be targeted and aimed at resolving the specific ambiguity preventing a direct answer. "
    "Example: 'NEED: To give you the most relevant information, could you specify which aspect of [topic] you're interested in?'\n\n"
    "IMPORTANT: If you use 'NEED:', the whole reply MUST be prefixed with 'NEED:'. DO NOT include any other text before the prefix. Use this sparingly.\n\n"
    "2. Offering Choices (OPTIONS): If a request is clear but very broad, and offering a few distinct choices would genuinely help the user narrow down their interest more efficiently than a clarifying question, " 
    "you MAY offer these as buttons. Do not offer options if a direct answer to a reasonable interpretation of the request is possible.\n"
    "  * You MUST structure this as follows: Start with a title or question for the user, prefixed by 'TITRE: '. "
    "Immediately follow this with the options themselves, prefixed by 'OPTIONS: ', which must be a valid JSON list of strings. "
    "Each string *within* the JSON list MUST be enclosed in double quotes.\n"
    "  * Example: 'TITRE: Which aspect are you most interested in? OPTIONS: [\"Overview\", \"Key Features\", \"Pricing\"]'\n"
    "  * IMPORTANT: There should be no other text before 'TITRE:' and no text between 'TITRE: ...' and 'OPTIONS: ...' other than a single space if desired.\n"
    "  * Direct Option Elicitation: If the user explicitly asks for \"options\", \"a list of options\", \"choices\", or similar phrasing for a topic, "
    "you MUST make a strong effort to provide these directly using the OPTIONS format. If the topic is still a bit broad, "
    "the options you provide should be the primary, common categories for that topic. You can include an option like \"Other...\" or \"Something Else?\" "
    "if you anticipate the user might have a need not covered by the main categories.\n"
    "  * Convergence after Choice: When the user selects an option, your *primary goal* for the next response is to provide a substantive answer, complete the thought, or take a direct action based on that choice. "
    "If further sub-division is *absolutely essential* and logical, you may offer one more set of options. However, actively avoid falling into a pattern of offering options repeatedly. "
    "After one or two rounds of option selection by the user, you MUST prioritize reaching a conclusion or, if genuinely necessary, asking a final, single clarifying question using the 'NEED:' prefix. "
    "Do not propose more options if a direct answer or a single 'NEED:' question can resolve the interaction. Prioritize reaching a conclusion.\n\n"
    "3. Direct Answer: If the request is clear enough for you to provide a useful response, or if you can make a reasonable inference to answer the likely intent, " 
    "provide a direct answer without any prefix. This should be your default mode of response."
)

# Helper to ensure context directory exists
def ensure_context_dir():
    if not os.path.exists(CONTEXT_DIR_PATH):
        try:
            os.makedirs(CONTEXT_DIR_PATH)
            if DEBUG_MODE: sys.stderr.write(f"DEBUG: Created context directory: {CONTEXT_DIR_PATH}\n")
        except Exception as e:
            if DEBUG_MODE: sys.stderr.write(f"ERROR: Could not create context directory {CONTEXT_DIR_PATH}: {e}\n")
            # This might be a critical error depending on whether we need to save.

# Helper to save conversation state (full conv object including metadata)
def save_conversation_to_file(conversation_object):
    ensure_context_dir()
    conv_id = conversation_object.get("conversation_id")
    if not conv_id:
        if DEBUG_MODE: sys.stderr.write("ERROR: Attempted to save conversation without an ID.\n")
        return
    file_path = os.path.join(CONTEXT_DIR_PATH, f"{conv_id}.json")
    try:
        conversation_object["last_updated_at"] = time.time()
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(conversation_object, f, indent=4)
        if DEBUG_MODE: sys.stderr.write(f"DEBUG: Saved conversation to {file_path}\n")
    except Exception as e:
        if DEBUG_MODE: sys.stderr.write(f"ERROR: Could not save conversation to {file_path}: {e}\n")

# Helper to load a conversation from file
def load_conversation_from_file(conversation_id):
    file_path = os.path.join(CONTEXT_DIR_PATH, f"{conversation_id}.json")
    if os.path.exists(file_path):
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                if DEBUG_MODE: sys.stderr.write(f"DEBUG: Loaded conversation {conversation_id} from {file_path}\n")
                return data
        except Exception as e:
            if DEBUG_MODE: sys.stderr.write(f"ERROR: Could not load conversation {conversation_id} from {file_path}: {e}\n")
    return None

# Helper to update last conversation ID tracker
def update_last_conversation_id(conversation_id):
    try:
        with open(LAST_CONV_ID_FILEPATH, "w") as f:
            f.write(str(conversation_id))
        if DEBUG_MODE: sys.stderr.write(f"DEBUG: Updated last_conversation_id.txt with {conversation_id}\n")
    except Exception as e:
        if DEBUG_MODE: sys.stderr.write(f"ERROR: Could not update last_conversation_id.txt: {e}\n")

def main_logic():
    loaded_form_state = load_state() # This is from gpt_tools/gpt_form_state.json (temporary)
    if DEBUG_MODE:
        sys.stderr.write(f"DEBUG gpt_chat.py: Loaded state: {loaded_form_state}\n")

    if DEBUG_MODE: # Minimal loaded state log to keep focus on screenshot part for now
        try: 
            debug_file_target = os.path.join(os.path.expanduser("~"), "espanso_debug_paths.txt")
            with open(debug_file_target, "a") as f_debug: 
                f_debug.write(f"gpt_chat.py loaded_state (screenshot test): include_screenshot='{loaded_form_state.get('include_screenshot')}'\n") # Corrected quotes
        except: pass # Minimal log here, focus on screenshot logs
    if not loaded_form_state: 
        print("ERROR: Could not retrieve form data.")
        return

    if DEBUG_MODE: sys.stderr.write(f"DEBUG: Loaded state: {loaded_form_state}\n")

    conversation_mode = loaded_form_state.get("conversation_mode", "Start New")
    active_conversation_id = loaded_form_state.get("active_conversation_id")
    if DEBUG_MODE: sys.stderr.write(f"DEBUG main_logic: ConvMode='{conversation_mode}', ActiveID='{active_conversation_id}'\n")

    # Initialize current_conversation object which holds all data for this session
    current_conversation = None 
    conv_messages = [] # This will be the list of role/content dicts for OpenAI
    final_system_message_for_api = "" # The system prompt to use for this interaction

    if conversation_mode == "Continue Last" and active_conversation_id:
        current_conversation = load_conversation_from_file(active_conversation_id)
        if current_conversation:
            final_system_message_for_api = current_conversation.get("initial_system_prompt", "")
            conv_messages = current_conversation.get("messages", [])
            if DEBUG_MODE: sys.stderr.write(f"DEBUG: Continuing conversation {active_conversation_id}. Loaded {len(conv_messages)} messages.\n")
        else:
            if DEBUG_MODE: sys.stderr.write(f"DEBUG: Failed to load last conversation {active_conversation_id}. Starting new.\n")
            conversation_mode = "Start New" # Fallback if load fails
            # active_conversation_id will be regenerated below for Start New
    
    if conversation_mode == "Start New":
        # active_conversation_id should have been generated by handle_form_step1.py if Start New was chosen or fallback
        if not active_conversation_id: # Should ideally not happen if handle_form_step1 is correct
            active_conversation_id = str(time.time())
            if DEBUG_MODE: sys.stderr.write(f"WARN: active_conversation_id was missing for Start New, generated: {active_conversation_id}\n")
        
        # Extract parameters from loaded_form_state for new conversation setup
        selected_task_objective = loaded_form_state.get("task_objective", "General Q&A")
        selected_language = loaded_form_state.get("output_language", "English")
        selected_sentiment = loaded_form_state.get("sentiment", "neutre")
        selected_relation = loaded_form_state.get("relation", "client")
        selected_faq_filename = loaded_form_state.get("selected_faq", "None")
        include_screenshot_str = loaded_form_state.get("include_screenshot", "false")
        include_screenshot = include_screenshot_str.lower() == 'true'
        desired_answer_sketch = loaded_form_state.get("desired_answer_sketch", "")

        # Get task configuration from JSON
        task_config = get_task(selected_task_objective)
        if DEBUG_MODE:
            sys.stderr.write(f"DEBUG: Loaded task config for '{selected_task_objective}': {task_config}\n")

        # --- Construct final_system_message_for_api based on task configuration ---
        faq_content_for_prompt = ""
        if selected_faq_filename and selected_faq_filename.strip().lower() not in ["none", ""]:
            faq_file_path = os.path.join(CONFIG_DIR, "gpt_tools", "faq", selected_faq_filename) # Updated path
            try: 
                with open(faq_file_path, 'r', encoding='utf-8') as f_faq: 
                    faq_data = f_faq.read()
                    faq_content_for_prompt = f"\n\nFAQ: {faq_data}"
            except Exception as e:
                if DEBUG_MODE:
                    sys.stderr.write(f"DEBUG: Error loading FAQ file: {e}\n")
                faq_content_for_prompt = f" (FAQ '{selected_faq_filename}' not found.)"

        # Language instruction
        language_instruction = f"Please respond in {selected_language}."
        if selected_language == "French":
            language_instruction = "Please respond in Canadian French."

        # Sentiment instruction
        sentiment_instruction = ""
        if task_config.get("sentiment_instructions") and selected_sentiment in task_config["sentiment_instructions"]:
            sentiment_instruction = task_config["sentiment_instructions"][selected_sentiment]
        
        # Relation instruction
        relation_instruction = ""
        if task_config.get("relation_instructions") and selected_relation in task_config["relation_instructions"]:
            relation_instruction = task_config["relation_instructions"][selected_relation]

        # Get system message template from task config
        system_message_template = task_config.get("system_message_template", base_system_prompt_core)
        
        # Format the system message with our extracted values
        try:
            final_system_message_for_api = system_message_template.format(
                language_instruction=language_instruction,
                sentiment_instruction=sentiment_instruction,
                relation_instruction=relation_instruction,
                faq_content=faq_content_for_prompt
            )
        except KeyError as e:
            if DEBUG_MODE:
                sys.stderr.write(f"DEBUG: Error formatting system message template: {e}. Using template as-is.\n")
            final_system_message_for_api = system_message_template
        except Exception as e:
            if DEBUG_MODE:
                sys.stderr.write(f"DEBUG: Unexpected error formatting system message: {e}. Using base prompt.\n")
            final_system_message_for_api = f"{base_system_prompt_core}"

        # Ensure base system prompt core is included if it's not already part of the template
        if base_system_prompt_core not in final_system_message_for_api:
            final_system_message_for_api = f"{final_system_message_for_api}\n\n---\n{base_system_prompt_core}"
        # --- End system prompt construction ---

        conv_messages = [{"role": "system", "content": final_system_message_for_api}]
        current_conversation = {
            "conversation_id": active_conversation_id,
            "created_at": time.time(),
            "initial_system_prompt": final_system_message_for_api,
            "original_form_inputs": loaded_form_state, # Store the inputs that started this
            "messages": conv_messages
        }
        if DEBUG_MODE: sys.stderr.write(f"DEBUG: Starting NEW conversation {active_conversation_id}. System prompt set.\n")

    # --- Initial User Message (applies to both new and continued conversations) ---
    initial_user_content_from_form = loaded_form_state.get("initial_prompt", "")
    desired_answer_sketch = loaded_form_state.get("desired_answer_sketch", "")
    include_screenshot = loaded_form_state.get("include_screenshot", "false").lower() == 'true'

    current_initial_user_text = initial_user_content_from_form
    if desired_answer_sketch and desired_answer_sketch.strip():
        current_initial_user_text += f"\n\nGUIDELINE SKETCH:\n«««\n{desired_answer_sketch.strip()}\n»»»"

    user_message_content_parts = [{"type": "text", "text": current_initial_user_text}]
    image_message_for_api = None # Will be set by screenshot logic if successful
    processed_screenshot_path = None 
    temp_file_to_delete = None # For managing the lifecycle of the temp screenshot file

    if include_screenshot:
        if DEBUG_MODE: sys.stderr.write("DEBUG: Attempting to take REAL screenshot.\n")
        try:
            # Create a named temporary file that won't be deleted immediately
            with tempfile.NamedTemporaryFile(delete=False, suffix='.png') as tmp_file:
                processed_screenshot_path = tmp_file.name
                temp_file_to_delete = processed_screenshot_path # Mark this for deletion
            
            pyautogui.screenshot(processed_screenshot_path)
            if DEBUG_MODE: sys.stderr.write(f"DEBUG: pyautogui.screenshot success. Temp path: {processed_screenshot_path}\n")
            
            if not os.path.exists(processed_screenshot_path) or os.path.getsize(processed_screenshot_path) == 0:
                if DEBUG_MODE: sys.stderr.write(f"ERROR: Screenshot file empty or not created at {processed_screenshot_path}\n")
                raise ValueError("Screenshot file empty or not created after pyautogui.screenshot")

            img = Image.open(processed_screenshot_path)
            if DEBUG_MODE: sys.stderr.write(f"DEBUG: Image.open success. Original format: {img.format}, mode: {img.mode}, size: {img.size}\n")
            
            original_format = img.format # Store original format for potential later use, though we mostly control output format
            width, height = img.size
            new_width, new_height = int(width * 0.5), int(height * 0.5)
            img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
            if DEBUG_MODE: sys.stderr.write(f"DEBUG: Image.resize success. New size: {img.size}\n")
            
            current_save_path = processed_screenshot_path # Start with the temp PNG path for saving
            img.save(current_save_path, format="PNG", optimize=True)
            current_mime_type = "image/png"
            if DEBUG_MODE: sys.stderr.write(f"DEBUG: Image saved as PNG. Path: {current_save_path}, Size: {os.path.getsize(current_save_path) if os.path.exists(current_save_path) else 'File not found'}\n")
            
            file_size_bytes = os.path.getsize(current_save_path)
            max_size_bytes = 19 * 1024 * 1024 # Approx 19MB limit

            if file_size_bytes > max_size_bytes:
                if DEBUG_MODE: sys.stderr.write(f"DEBUG: PNG ({file_size_bytes} bytes) > {max_size_bytes} bytes. Converting to JPEG.\n")
                jpeg_output_path = os.path.splitext(current_save_path)[0] + ".jpg"
                if img.mode == 'RGBA' or img.mode == 'P': # Convert to RGB if it has alpha or is palette-based for JPEG
                    img = img.convert('RGB')
                img.save(jpeg_output_path, format="JPEG", quality=85, optimize=True)
                if DEBUG_MODE: sys.stderr.write(f"DEBUG: Image saved as JPEG. Path: {jpeg_output_path}, Size: {os.path.getsize(jpeg_output_path) if os.path.exists(jpeg_output_path) else 'File not found'}\n")
                
                # If the original temp file was PNG and we created a separate JPG, delete the PNG now
                if temp_file_to_delete and temp_file_to_delete.endswith('.png') and temp_file_to_delete != jpeg_output_path and os.path.exists(temp_file_to_delete):
                    try: 
                        os.remove(temp_file_to_delete)
                        if DEBUG_MODE: sys.stderr.write(f"DEBUG: Deleted intermediate PNG file: {temp_file_to_delete}\n")
                    except Exception as e_del_png: 
                        if DEBUG_MODE: sys.stderr.write(f"DEBUG: Could not delete intermediate PNG {temp_file_to_delete}: {e_del_png}\n")
                
                current_save_path = jpeg_output_path # The JPEG is now the file to read and delete
                temp_file_to_delete = current_save_path # Update file to be deleted to the new JPEG path
                current_mime_type = "image/jpeg"
            
            with open(current_save_path, "rb") as img_file_data:
                image_data = img_file_data.read()
            base64_image = base64.b64encode(image_data).decode("utf-8")
            if DEBUG_MODE: 
                sys.stderr.write(f"DEBUG: Base64 encoding success. Length: {len(base64_image)}. Preview (first 50, last 50): '{base64_image[:50]}...' '{base64_image[-50:]}...'\n")
            
            image_message_for_api = {"type": "image_url", "image_url": {"url": f"data:{current_mime_type};base64,{base64_image}"}}
            if DEBUG_MODE: sys.stderr.write(f"DEBUG: Screenshot fully processed for API. MIME: {current_mime_type}\n")

        except Exception as e_screenshot:
            if DEBUG_MODE: sys.stderr.write(f"ERROR gpt_chat.py: Failed during REAL screenshot processing: {e_screenshot}\n")
            # processed_screenshot_path may still be set if pyautogui.screenshot worked but PIL failed, useful for the note
        finally:
            # Ensure the FINAL version of the temp file (PNG or JPG) is deleted
            if temp_file_to_delete and os.path.exists(temp_file_to_delete):
                try:
                    os.remove(temp_file_to_delete)
                    if DEBUG_MODE: sys.stderr.write(f"DEBUG: Deleted final temp screenshot file: {temp_file_to_delete}\n")
                except Exception as e_del_final:
                    if DEBUG_MODE: sys.stderr.write(f"ERROR: Could not delete final temp screenshot file {temp_file_to_delete}: {e_del_final}\n")
    
    if image_message_for_api:
        user_message_content_parts.append(image_message_for_api)
    elif include_screenshot and processed_screenshot_path:
        note_text = f"\n\n(Note: A screenshot was attempted from: {processed_screenshot_path} but may not have been sent to AI if image_message_for_api is None)"
        if user_message_content_parts[0]["text"]:
            user_message_content_parts[0]["text"] += note_text
        else:
            user_message_content_parts[0]["text"] = note_text.strip()
    
    conv_messages.append({"role": "user", "content": user_message_content_parts})
    current_conversation["messages"] = conv_messages # Update messages in our tracking object
    save_conversation_to_file(current_conversation) # Save state after adding initial user message
    if DEBUG_MODE: sys.stderr.write(f"DEBUG: Initial user message added. Total messages: {len(conv_messages)}\n")

    # --- Main Interaction Loop --- 
    max_loop_iterations = 15; loop_counter = 0
    while True:
        loop_counter += 1
        if loop_counter > max_loop_iterations: sys.stderr.write("ERROR: Loop limit.\n"); break

        reply = ask_gpt(conv_messages) # Pass the messages list directly

        if reply.startswith("NEED:"):
            q_raw = reply[5:].strip()
            if DEBUG_MODE: sys.stderr.write(f"DEBUG MainLoop: NEED detected. Question: {q_raw[:100]}...\n")
            a = None
            try:
                current_root = setup_root_window()
                if DEBUG_MODE: sys.stderr.write("DEBUG MainLoop: About to show custom NEED dialog\n")
                a = show_custom_need_dialog(q_raw, current_root)
                if DEBUG_MODE: sys.stderr.write(f"DEBUG MainLoop: Input from custom NEED dialog: {a}\n")
            except Exception as e_dialog:
                if DEBUG_MODE: sys.stderr.write(f"DEBUG ERROR in NEED dialog: {e_dialog}\n")
                print(reply)
                break # Exit while loop
            if a is None:
                if DEBUG_MODE: sys.stderr.write("DEBUG MainLoop: NEED dialog cancelled or error. Exiting script.\n")
                # No explicit stdout, script will end, finally cleans up.
                break # Exit while loop
            if DEBUG_MODE: sys.stderr.write(f"DEBUG MainLoop: Adding to conversation after NEED: User says '{a[:50]}...'\n")
            conv_messages.append({"role": "assistant", "content": reply})
            conv_messages.append({"role": "user", "content": a})
            current_conversation["messages"] = conv_messages
            save_conversation_to_file(current_conversation)
        elif "OPTIONS:" in reply and "TITRE:" in reply:
            try:
                parts_options_split = reply.split("OPTIONS:", 1)
                title_part = parts_options_split[0]
                options_json_str = parts_options_split[1].strip()
                if not title_part.startswith("TITRE:"):
                    raise ValueError("Missing TITRE: prefix or incorrect order.")
                intro_question = title_part.replace("TITRE:", "", 1).strip()
                options_list = json.loads(options_json_str)
                if not (isinstance(options_list, list) and all(isinstance(opt, str) for opt in options_list)):
                    raise ValueError("Parsed JSON from OPTIONS is not a list of strings")
                current_root = setup_root_window()
                if DEBUG_MODE: sys.stderr.write("DEBUG MainLoop: About to show options dialog\n")
                selected_option = show_options_dialog(intro_question, options_list, current_root)
                if DEBUG_MODE: sys.stderr.write(f"DEBUG MainLoop: Selected option: {selected_option}\n")
                if selected_option is None:
                    if DEBUG_MODE: sys.stderr.write("DEBUG MainLoop: OPTIONS dialog cancelled. Exiting script.\n")
                    print("No option selected from dialog.") # Provide some output
                    break # Exit while loop
                if DEBUG_MODE: sys.stderr.write(f"DEBUG MainLoop: Adding to conversation after OPTIONS: User picked '{selected_option[:50]}...'\n")
                conv_messages.append({"role": "assistant", "content": reply})
                conv_messages.append({"role": "user", "content": selected_option})
                current_conversation["messages"] = conv_messages
                save_conversation_to_file(current_conversation)
            except Exception as e_opts_dialog:
                if DEBUG_MODE: sys.stderr.write(f"DEBUG ERROR in TITRE/OPTIONS processing/dialog: {e_opts_dialog}\nOriginal reply was: '{reply[:200]}...'\n")
                print(reply)
                break # Exit while loop
        else: # Direct Answer
            print(reply)
            conv_messages.append({"role": "assistant", "content": reply}) # Save final AI answer
            current_conversation["messages"] = conv_messages
            save_conversation_to_file(current_conversation)
            update_last_conversation_id(active_conversation_id) # Mark this as last successfully completed
            loop_counter = 0; break

if __name__ == "__main__":
    # This main guard is now the entry point when script is run by Espanso
    # (via :gpt_final_processing trigger)
    # or for direct testing if state file is pre-populated.
    if DEBUG_MODE: sys.stderr.write("DEBUG: gpt_chat.py __main__ execution started.\n")
    try:
        ensure_context_dir() # Ensure dir exists when script starts (e.g. for direct testing)
        main_logic()
    except Exception as e:
        if DEBUG_MODE: sys.stderr.write(f"CRITICAL ERROR in gpt_chat.py main_logic: {e}\n")
        # Try to print error to stdout for Espanso visibility if possible
        print(f"An unexpected error occurred in gpt_chat.py: {e}")
    finally:
        if DEBUG_MODE: sys.stderr.write("DEBUG: gpt_chat.py __main__ in finally block. Cleaning up GUI and state.\n")
        delete_state() # Attempt to delete the state file
        try:
            delete_state() # Attempt to delete the state file
            if DEBUG_MODE: sys.stderr.write("DEBUG: State file deleted successfully.\n")
        except Exception as e_del_state:
            if DEBUG_MODE: sys.stderr.write(f"ERROR deleting state file during cleanup: {e_del_state}\n")
    if DEBUG_MODE: sys.stderr.write("DEBUG: gpt_chat.py __main__ execution finished.\n")