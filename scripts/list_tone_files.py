#!/usr/bin/env python3
import os
import glob

# Script is in <config_root>/scripts/
# Tone files are in <config_root>/gpt_tools/tone/
TONE_FILES_DIR = os.path.join(os.path.dirname(__file__), "..", "gpt_tools", "tone")

def list_tone_files():
    try:
        # Find all .txt files in the tone directory
        tone_files_paths = glob.glob(os.path.join(TONE_FILES_DIR, "*.txt"))
        
        if not tone_files_paths:
            # Output a default or placeholder if no files are found, 
            # so the Espanso form doesn't break.
            print("NoTonesFound") 
            return

        tone_names = []
        for f_path in sorted(tone_files_paths):
            # Get filename without extension
            base_name = os.path.basename(f_path)
            tone_name, _ = os.path.splitext(base_name)
            tone_names.append(tone_name)
        
        for name in tone_names:
            print(name)
            
    except Exception as e:
        # Fallback in case of error, to prevent Espanso from breaking
        print(f"ErrorListingTones: {e}")

if __name__ == "__main__":
    list_tone_files() 