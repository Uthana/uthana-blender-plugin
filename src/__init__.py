# flake8: noqa
bl_info = {
    "name": "Uthana",
    "author": "Uthana, Inc.",
    "version": (1, 0, 1),
    "blender": (4, 0, 0),
    "location": "View3D > Sidebar > Uthana",
    "description": "AI-powered motion generation plugin for Uthana: Text to Motion, Video to Motion, and more.",
    "category": "Animation",
    "doc_url": "https://uthana.com/docs/api",
    "tracker_url": "https://github.com/Uthana/uthana/issues",
}

import bpy
from bpy.props import PointerProperty

from . import config
from .constants import CACHE_DIR
from .logger import logger, setup_logger
from .ui import UthanaProperties, classes as ui_classes

setup_logger()


def register():
    """Register plugin classes and initialize configuration"""
    logger.info("Registering Uthana plugin...")

    # Ensure cache directory exists
    config.ensure_cache_directory()
    logger.info("Cache directory ensured: %s", CACHE_DIR)

    # Register UI classes
    for cls in ui_classes:
        bpy.utils.register_class(cls)

    # Add properties to scene
    bpy.types.Scene.uthana_props = PointerProperty(type=UthanaProperties)

    # Reset config sync state
    config.reset_sync_state()

    # Load configuration
    try:
        config.load_config()
        logger.info("Uthana configuration loaded successfully")
    except Exception as e:
        logger.error("Failed to load Uthana configuration: %s", e)

    logger.info("Uthana plugin registered successfully")


def unregister():
    """Unregister plugin and save configuration"""
    logger.info("Unregistering Uthana plugin...")

    # Unregister UI classes
    for cls in reversed(ui_classes):
        bpy.utils.unregister_class(cls)

    # Remove properties
    if hasattr(bpy.types.Scene, "uthana_props"):
        del bpy.types.Scene.uthana_props

    logger.info("Uthana plugin unregistered successfully")


if __name__ == "__main__":
    register()
