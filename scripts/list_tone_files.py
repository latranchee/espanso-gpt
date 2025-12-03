#!/usr/bin/env python3
import os
import glob

# Script is in <config_root>/scripts/
# Tone files are in <config_root>/gpt_tools/tone/
TONE_FILES_DIR = os.path.join(os.path.dirname(__file__), "..", "gpt_tools", "tone")


def get_tone_display_name(file_path: str) -> str:
    """
    Get display name from a tone file.
    If the first line starts with #, use it as display name (without the #).
    Otherwise, use the filename without extension.
    """
    filename = os.path.basename(file_path)
    name_without_ext, _ = os.path.splitext(filename)

    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            first_line = f.readline().strip()
            if first_line.startswith('#'):
                return first_line[1:].strip()
    except Exception:
        pass

    return name_without_ext


def list_tone_files():
    try:
        # Find all .txt files in the tone directory
        tone_files_paths = glob.glob(os.path.join(TONE_FILES_DIR, "*.txt"))

        if not tone_files_paths:
            print("NoTonesFound")
            return

        for f_path in sorted(tone_files_paths):
            display_name = get_tone_display_name(f_path)
            print(display_name)

    except Exception as e:
        print(f"ErrorListingTones: {e}")


if __name__ == "__main__":
    list_tone_files()
