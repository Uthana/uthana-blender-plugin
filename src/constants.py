import os
from pathlib import Path

# Cross-platform cache directory
if os.name == "nt":  # Windows
    CACHE_DIR = Path(os.path.expandvars("%APPDATA%")) / "uthana"
else:  # Linux/macOS
    CACHE_DIR = Path.home() / ".cache" / "uthana"

CONFIG_PATH = CACHE_DIR / "config.json"

TAR_CHARACTER_ID = "cXi2eAP19XwQ"
