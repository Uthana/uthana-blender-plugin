import os
from pathlib import Path

# Cross-platform cache directory
if os.name == "nt":  # Windows
    CACHE_DIR = Path(os.path.expandvars("%APPDATA%")) / "uthana"
else:  # Linux/macOS
    CACHE_DIR = Path.home() / ".cache" / "uthana"

CONFIG_PATH = CACHE_DIR / "config.json"

TAR_CHARACTER_ID = "cXi2eAP19XwQ"

# Text-to-motion models, as (API model name, label, description).
# The 3.0 family runs as a background job (create_text_to_motion_job) and needs a
# pay-as-you-go account; the older models return a motion straight away.
TTM_MODELS = (
    (
        "text-to-motion-3.0-lite",
        "TTM 3.0 Lite",
        "Faster version of the latest model. Runs as a background job",
    ),
    (
        "text-to-motion-3.0",
        "TTM 3.0",
        "Latest model, highest quality. Runs as a background job",
    ),
    (
        "text-to-motion-3.0-mini",
        "TTM 3.0 Mini",
        "Compact version of the latest model. Runs as a background job",
    ),
    ("text-to-motion-bucmd", "TTM 2.0", "Earlier model. Returns a motion in a few seconds"),
    ("text-to-motion", "TTM 1.0", "Original model. Returns a motion in a few seconds"),
)
DEFAULT_TTM_MODEL = "text-to-motion-3.0-lite"
TTM_JOB_MODELS = frozenset(
    {"text-to-motion-3.0", "text-to-motion-3.0-lite", "text-to-motion-3.0-mini"}
)
# Clip length the API accepts for the 3.0 family, in whole seconds.
TTM_JOB_MIN_SECONDS = 4
TTM_JOB_MAX_SECONDS = 10
DEFAULT_TTM_SECONDS = 5

# Video-to-motion models, as (API model name, label, description).
VTM_MODELS = (
    ("video-to-motion-3.0", "V2M 3.0", "Latest model, highest quality"),
    ("video-to-motion-2.1", "V2M 2.1", "Earlier model"),
    ("video-to-motion-2.0", "V2M 2.0", "Earlier model"),
)
DEFAULT_VTM_MODEL = "video-to-motion-3.0"
