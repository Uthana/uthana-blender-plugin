"""Utility functions for Uthana plugin."""

import bpy

from .logger import logger


def get_selected_armatures():
    """Get all selected armatures except the active one.

    Returns:
        list: List of selected armature objects (excluding active object)
    """
    if not bpy.context.selected_objects:
        return []

    active_obj = bpy.context.view_layer.objects.active
    selected_armatures = [obj for obj in bpy.context.selected_objects if obj.type == "ARMATURE"]

    # Remove active object from selected list
    if active_obj and active_obj in selected_armatures:
        selected_armatures.remove(active_obj)

    return selected_armatures


def build_web_viewer_url(domain: str, character_id: str, motion_id: str) -> str:
    """Build the web viewer URL for previewing a motion in browser.

    Args:
        domain: API domain (e.g., "uthana.com")
        character_id: Character ID
        motion_id: Motion ID

    Returns:
        Full URL to web viewer (e.g., "https://uthana.com/app/play/char_id/motion_id")
    """
    return f"https://{domain}/app/play/{character_id}/{motion_id}"


def build_preview_image_url(domain: str, character_id: str, motion_id: str) -> str:
    """Build the preview image URL for a motion.

    Args:
        domain: API domain (e.g., "uthana.com")
        character_id: Character ID
        motion_id: Motion ID

    Returns:
        Full URL to preview WebM video
    """
    return f"https://{domain}/app/preview/{character_id}/{motion_id}/preview.webm"


def extract_animated_preview_frames(preview_path: str):
    """Extract all frames from animated preview into Blender images.

    Requires ffmpeg to be installed. Does not fall back to manual parsing.

    Args:
        preview_path: Path to preview file (WebM or other ffmpeg-supported format)

    Returns:
        tuple: (list of bpy.types.Image, list of frame durations in seconds)
        Returns ([], []) if ffmpeg is not available
    """
    import subprocess
    import tempfile
    import os

    frames = []
    frame_durations = []

    logger.info(f"Starting animated preview extraction from: {preview_path}")

    # Check common locations where ffmpeg might be installed
    ffmpeg_paths = [
        "ffmpeg",  # Try PATH first
        "/opt/homebrew/bin/ffmpeg",  # Homebrew on Apple Silicon
        "/usr/local/bin/ffmpeg",  # Homebrew on Intel Mac
    ]

    for ffmpeg_cmd in ffmpeg_paths:
        try:
            result = subprocess.run([ffmpeg_cmd, "-version"], capture_output=True, timeout=2)
            if result.returncode == 0:
                logger.info(f"ffmpeg found at: {ffmpeg_cmd}")
                return _extract_frames_with_ffmpeg(preview_path, ffmpeg_cmd)
        except (FileNotFoundError, subprocess.TimeoutExpired, Exception):
            continue

    logger.error("ffmpeg not found - cannot extract animated preview frames")
    logger.info("Install ffmpeg to enable in-Blender animated previews:")
    logger.info("  macOS: brew install ffmpeg")
    logger.info("  Windows: choco install ffmpeg (or download from ffmpeg.org)")
    logger.info("  Linux: sudo apt install ffmpeg (or equivalent)")

    # Return empty lists - caller will show message to install ffmpeg
    return [], []


def _extract_frames_with_ffmpeg(preview_path: str, ffmpeg_cmd: str = "ffmpeg"):
    """Extract animated preview frames using ffmpeg.

    Args:
        preview_path: Path to preview file (WebM or other ffmpeg-supported format)
        ffmpeg_cmd: Path to ffmpeg executable

    Returns:
        tuple: (list of bpy.types.Image, list of frame durations in seconds)
    """
    import subprocess
    import tempfile
    import os
    import shutil

    frames = []
    frame_durations = []
    temp_dir = None

    try:
        # Create temp directory for frames
        temp_dir = tempfile.mkdtemp(prefix="uthana_preview_")
        output_pattern = os.path.join(temp_dir, "frame_%04d.png")

        # Extract frames using ffmpeg
        cmd = [ffmpeg_cmd, "-i", preview_path, "-vsync", "0", output_pattern]

        result = subprocess.run(cmd, capture_output=True, timeout=30)
        if result.returncode != 0:
            logger.error(f"ffmpeg failed: {result.stderr.decode()}")
            return [], []

        # Load each frame
        frame_files = sorted([f for f in os.listdir(temp_dir) if f.startswith("frame_")])
        logger.info(f"Extracted {len(frame_files)} frames with ffmpeg")

        for idx, frame_file in enumerate(frame_files):
            frame_path = os.path.join(temp_dir, frame_file)

            # Load image using Blender
            img_name = f"preview_frame_{idx}"
            if img_name in bpy.data.images:
                bpy.data.images.remove(bpy.data.images[img_name])

            blender_img = bpy.data.images.load(frame_path)
            blender_img.name = img_name

            # CRITICAL: Pack the image immediately before temp files are deleted
            blender_img.pack()

            frames.append(blender_img)
            frame_durations.append(0.1)  # Default 10 FPS

        logger.info(f"Successfully loaded {len(frames)} frames from ffmpeg extraction")
        return frames, frame_durations

    except Exception as e:
        logger.error(f"ffmpeg extraction failed: {e}")
        return [], []
    finally:
        # Clean up temp directory
        if temp_dir and os.path.exists(temp_dir):
            try:
                shutil.rmtree(temp_dir)
            except Exception as e:
                logger.warning(f"Failed to clean up temp dir: {e}")
