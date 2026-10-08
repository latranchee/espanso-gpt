import sys
from pathlib import Path

# Scripts import each other as top-level modules (Espanso runs them from scripts/).
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
