import random
import string
from datetime import datetime
from typing import Any, List, Optional, Tuple

from .logger import logger

try:
    import bpy

    BLENDER_AVAILABLE = True
except ImportError:
    BLENDER_AVAILABLE = False


def generate_timestamp_filename(ext: str) -> str:
    """Generates filename with timestamp and random salt"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    salt = "".join(random.choices(string.ascii_lowercase + string.digits, k=6))
    return f"{timestamp}_{salt}.{ext}"


def backup_selection() -> Tuple[List, Optional[Any]]:
    """Backs up current Blender selection"""
    if not BLENDER_AVAILABLE:
        return [], None

    original_selection = bpy.context.selected_objects.copy()
    original_active = bpy.context.view_layer.objects.active
    return original_selection, original_active


def restore_selection(selection: List, active: Optional[Any]) -> None:
    """Restores Blender selection"""
    if not BLENDER_AVAILABLE:
        return

    logger.debug("=== RESTORE_SELECTION START ===")
    logger.debug("Restoring selection: %s", [obj.name for obj in selection])
    logger.debug("Restoring active: %s", active.name if active else "None")

    # Log current state before restore
    current_selected = [obj.name for obj in bpy.context.selected_objects]
    current_active = (
        bpy.context.view_layer.objects.active.name
        if bpy.context.view_layer.objects.active
        else "None"
    )
    logger.debug(
        "Current state before restore - Selected: %s, Active: %s", current_selected, current_active
    )

    bpy.ops.object.select_all(action="DESELECT")
    logger.debug("Cleared all selection")

    restored_objects = []
    failed_objects = []

    for obj in selection:
        if obj.name in bpy.context.scene.objects:
            obj.select_set(True)
            restored_objects.append(obj.name)
            logger.debug("Restored selection for: %s", obj.name)
        else:
            failed_objects.append(obj.name)
            logger.warning(
                "Failed to restore selection for: %s (object not found in scene)", obj.name
            )

    logger.debug("Successfully restored selection for: %s", restored_objects)
    if failed_objects:
        logger.warning("Failed to restore selection for: %s", failed_objects)

    if active and active.name in bpy.context.scene.objects:
        bpy.context.view_layer.objects.active = active
        logger.debug("Restored active object: %s", active.name)
    else:
        if active:
            logger.warning(
                "Failed to restore active object: %s (object not found in scene)", active.name
            )
        else:
            logger.debug("No active object to restore")

    # Log final state after restore
    final_selected = [obj.name for obj in bpy.context.selected_objects]
    final_active = (
        bpy.context.view_layer.objects.active.name
        if bpy.context.view_layer.objects.active
        else "None"
    )
    logger.debug(
        "Final state after restore - Selected: %s, Active: %s", final_selected, final_active
    )
    logger.debug("=== RESTORE_SELECTION END ===")


def get_armature_objects() -> List[Any]:
    """Returns all Armature objects in scene"""
    if not BLENDER_AVAILABLE:
        return []

    return [obj for obj in bpy.context.scene.objects if obj.type == "ARMATURE"]


def get_selected_armatures() -> List[Any]:
    """Returns selected Armature objects"""
    if not BLENDER_AVAILABLE:
        return []

    return [obj for obj in bpy.context.selected_objects if obj.type == "ARMATURE"]


def get_active_armature() -> Optional[Any]:
    """Returns active Armature object if selected"""
    if not BLENDER_AVAILABLE:
        return None

    active_obj = bpy.context.view_layer.objects.active
    if active_obj and active_obj.type == "ARMATURE":
        return active_obj
    return None


def validate_blender_context() -> bool:
    """Checks if Blender context is valid"""
    if not BLENDER_AVAILABLE:
        return False

    try:
        return bpy.context.scene is not None
    except Exception:
        return False


def get_selected_but_not_active_armatures() -> List[Any]:
    """Returns selected Armature objects excluding the active one"""
    if not BLENDER_AVAILABLE:
        return []

    active_obj = bpy.context.view_layer.objects.active
    selected_armatures = [obj for obj in bpy.context.selected_objects if obj.type == "ARMATURE"]

    # Remove active object from selected list
    if active_obj and active_obj in selected_armatures:
        selected_armatures.remove(active_obj)

    return selected_armatures
