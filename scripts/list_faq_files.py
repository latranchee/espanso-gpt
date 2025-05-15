#!/usr/bin/env python3
import os
import glob

# The script is in <config_root>/scripts/, so markdown folder is ../faq/
markdown_dir = os.path.join(os.path.dirname(__file__), "..", "faq")

# Print "None" as the first option for the dropdown
print("None")

# Find all .md files in the markdown directory
faq_files = glob.glob(os.path.join(markdown_dir, "*.md"))

for f_path in sorted(faq_files):
    # Print just the filename for the dropdown
    print(os.path.basename(f_path)) 