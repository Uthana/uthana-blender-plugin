import json
from typing import Optional

from .constants import CACHE_DIR, CONFIG_PATH
from .logger import logger
from .types import OperationResult, UthanaConfig

# Track if config was synced to UI
_config_synced = False


def ensure_cache_directory() -> None:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)


def load_config() -> UthanaConfig:
    if not CONFIG_PATH.exists():
        return get_default_config()

    try:
        with open(CONFIG_PATH, "r") as f:
            data = json.load(f) or {}
        return UthanaConfig.from_dict(data)
    except Exception as e:
        logger.warning("Failed to load config: %s, using defaults", e)
        return get_default_config()


def save_config(config: UthanaConfig) -> OperationResult:
    try:
        ensure_cache_directory()
        with open(CONFIG_PATH, "w") as f:
            json.dump(config.to_dict(), f, indent=2)
        return OperationResult(success=True, message="Config saved successfully")
    except Exception as e:
        return OperationResult(success=False, message=f"Failed to save config: {str(e)}")


def get_default_config() -> UthanaConfig:
    return UthanaConfig()


def sync_config_to_ui(config: UthanaConfig, scene) -> None:
    if not hasattr(scene, "uthana_props"):
        logger.warning("No uthana_props found in scene")
        return

    props = scene.uthana_props
    # Auth
    props.domain = config.auth.domain
    props.api_key = config.auth.api_key
    # Text to Motion
    props.prompt = config.prompt
    props.character_id = config.character_id
    props.generate_result_motion_id = config.generate_result_motion_id
    # Load Motion
    props.load_motion_id = config.load_motion_id
    props.load_character_id = config.load_character_id
    props.load_result_motion_id = config.load_result_motion_id
    # Bake Motion
    props.bake_character_id = config.bake_character_id
    props.bake_use_frame_range = config.bake_use_frame_range
    props.bake_result_motion_id = config.bake_result_motion_id
    # Stitch Armatures
    props.stitch_character_id = config.stitch_character_id
    props.stitch_duration = config.stitch_duration
    props.stitch_use_frame_range = config.stitch_use_frame_range
    props.stitch_result_motion_id = config.stitch_result_motion_id
    # Stitch Motion IDs
    props.stitch_ids_character_id = config.stitch_ids_character_id
    props.stitch_ids_leading_motion_id = config.stitch_ids_leading_motion_id
    props.stitch_ids_trailing_motion_id = config.stitch_ids_trailing_motion_id
    props.stitch_ids_duration = config.stitch_ids_duration
    props.stitch_ids_result_motion_id = config.stitch_ids_result_motion_id
    # UI State
    props.show_config = config.ui_state.show_config
    props.show_text_to_motion = config.ui_state.show_text_to_motion
    props.show_load_motion = config.ui_state.show_load_motion
    props.show_bake = config.ui_state.show_bake
    props.show_stitching = config.ui_state.show_stitching
    props.show_stitch_motion_ids = config.ui_state.show_stitch_motion_ids


def safe_sync_to_ui() -> Optional[float]:
    """Safely sync config to UI outside of draw context"""
    global _config_synced

    try:
        import bpy

        if not bpy.context.scene or not hasattr(bpy.context.scene, "uthana_props"):
            return None

        config = load_config()
        sync_config_to_ui(config, bpy.context.scene)
        _config_synced = True
        logger.info("Config synced to UI successfully")
        return None  # Stop timer
    except Exception as e:
        logger.error("Error syncing config to UI: %s", e)
        return None  # Stop timer


def sync_ui_to_config(scene) -> UthanaConfig:
    if not hasattr(scene, "uthana_props"):
        return get_default_config()

    props = scene.uthana_props
    config = UthanaConfig()
    # Auth
    config.auth.domain = props.domain
    config.auth.api_key = props.api_key
    # Text to Motion
    config.prompt = props.prompt
    config.character_id = props.character_id
    config.generate_result_motion_id = props.generate_result_motion_id
    # Load Motion
    config.load_motion_id = props.load_motion_id
    config.load_character_id = props.load_character_id
    config.load_result_motion_id = props.load_result_motion_id
    # Bake Motion
    config.bake_character_id = props.bake_character_id
    config.bake_use_frame_range = props.bake_use_frame_range
    config.bake_result_motion_id = props.bake_result_motion_id
    # Stitch Armatures
    config.stitch_character_id = props.stitch_character_id
    config.stitch_duration = props.stitch_duration
    config.stitch_use_frame_range = props.stitch_use_frame_range
    config.stitch_result_motion_id = props.stitch_result_motion_id
    # Stitch Motion IDs
    config.stitch_ids_character_id = props.stitch_ids_character_id
    config.stitch_ids_leading_motion_id = props.stitch_ids_leading_motion_id
    config.stitch_ids_trailing_motion_id = props.stitch_ids_trailing_motion_id
    config.stitch_ids_duration = props.stitch_ids_duration
    config.stitch_ids_result_motion_id = props.stitch_ids_result_motion_id
    # UI State
    config.ui_state.show_config = props.show_config
    config.ui_state.show_text_to_motion = props.show_text_to_motion
    config.ui_state.show_load_motion = props.show_load_motion
    config.ui_state.show_bake = props.show_bake
    config.ui_state.show_stitching = props.show_stitching
    config.ui_state.show_stitch_motion_ids = props.show_stitch_motion_ids
    return config


def auto_save_config(scene) -> OperationResult:
    try:
        config = sync_ui_to_config(scene)
        return save_config(config)
    except Exception as e:
        return OperationResult(success=False, message=f"Auto-save failed: {str(e)}")


def should_save_config() -> bool:
    return _config_synced


def reset_sync_state() -> None:
    """Reset sync state on plugin reload"""
    global _config_synced
    _config_synced = False
