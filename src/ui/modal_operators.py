"""Modal operators for async operations in Uthana plugin.

These operators use Blender's timer system to poll for job completion
without blocking the UI.
"""

import threading
from typing import Optional

import bpy

from .. import assets, client, motion
from ..constants import TAR_CHARACTER_ID
from ..jobs import JobManager, JobStatus, PendingJob
from ..logger import logger


class UTHANA_OT_video_to_motion(bpy.types.Operator):
    """Generate motion from video file (modal operator with polling)."""

    bl_idname = "uthana.video_to_motion"
    bl_label = "Generate Motion from Video"
    bl_description = "Upload a video and extract motion (async with progress)"
    bl_options = {"REGISTER"}

    _timer = None
    _job_id: str = ""
    _poll_count: int = 0
    _max_polls: int = 600  # 20 minutes at 2s interval
    _upload_thread: Optional[threading.Thread] = None
    _upload_result: Optional[dict] = None
    _upload_error: Optional[str] = None
    _upload_complete: bool = False
    _phase: str = "uploading"  # "uploading" or "processing"

    def modal(self, context, event):
        if event.type == "TIMER":
            props = context.scene.uthana_props

            # Force UI redraw
            for area in context.screen.areas:
                if area.type == "VIEW_3D":
                    area.tag_redraw()

            # Phase 1: Waiting for upload to complete
            if self._phase == "uploading":
                if self._upload_complete:
                    if self._upload_error:
                        self.report({"ERROR"}, self._upload_error)
                        return self.finish(context, cancelled=True)

                    if self._upload_result:
                        self._job_id = self._upload_result.get("job_id", "")
                        props.video_job_id = self._job_id
                        props.video_job_status = self._upload_result.get("status", "RESERVED")
                        props.video_job_progress = 10  # Upload done, processing starts
                        self._phase = "processing"
                        self.report({"INFO"}, "Video uploaded, processing...")
                    else:
                        self.report({"ERROR"}, "Upload failed - no result")
                        return self.finish(context, cancelled=True)
                else:
                    # Still uploading - show indeterminate progress
                    self._poll_count += 1
                    props.video_job_status = "Uploading..."
                    # Animate progress bar during upload (0-10%)
                    props.video_job_progress = min(10, (self._poll_count % 10))
                    return {"PASS_THROUGH"}

            # Phase 2: Polling for job completion
            if self._phase == "processing":
                if not self._job_id:
                    self.report({"ERROR"}, "No job ID")
                    return self.finish(context, cancelled=True)

                result = client.get_job_status(props.api_key, props.domain, self._job_id)

                if not result.success:
                    self.report({"ERROR"}, result.message)
                    return self.finish(context, cancelled=True)

                status_str = result.data.get("status", "UNKNOWN")
                status = JobStatus.from_string(status_str)
                props.video_job_status = status_str

                if status == JobStatus.FINISHED:
                    # Get motion ID from result
                    job_result = result.data.get("result", {})
                    motion_id = None
                    motion_name = props.video_motion_name or "Video Motion"

                    if isinstance(job_result, dict):
                        motion_id = job_result.get("motion", {}).get("id")
                        if not motion_id:
                            motion_id = job_result.get("motion_id")

                    if motion_id:
                        props.video_result_motion_id = motion_id
                        props.video_job_progress = 100

                        # Get character ID
                        char_id = props.character_id or TAR_CHARACTER_ID

                        # Store pending motion for preview
                        props.pending_motion_id = motion_id
                        props.pending_motion_name = motion_name
                        props.pending_character_id = char_id
                        props.pending_motion_source = "video"

                        # Reset preview state
                        props.preview_frames_loaded = False
                        props.preview_current_frame_idx = 0
                        props.pending_preview_video_path = ""

                        self.report(
                            {"INFO"}, f"Motion '{motion_name}' created! Check preview in sidebar."
                        )

                        # Auto-start preview animation
                        bpy.ops.uthana.play_motion_preview("INVOKE_DEFAULT")

                        # Refresh motions list
                        assets.AssetManager.instance().refresh_motions(
                            props.api_key, props.domain, force=True
                        )
                        self._sync_motions_to_ui(props)
                    else:
                        self.report({"WARNING"}, "Motion created but ID not found in result")

                    return self.finish(context, cancelled=False)

                elif status == JobStatus.FAILED:
                    job_result = result.data.get("result", {})
                    error = "Unknown error"
                    if isinstance(job_result, dict):
                        error = job_result.get("error", error)
                    self.report({"ERROR"}, f"Job failed: {error}")
                    return self.finish(context, cancelled=True)

                # Still running - update progress estimate (10-95%)
                self._poll_count += 1
                # Estimate progress based on typical processing time (~2-5 min)
                progress = min(95, 10 + (self._poll_count * 0.5))
                props.video_job_progress = progress

                if self._poll_count >= self._max_polls:
                    self.report({"ERROR"}, "Job timed out")
                    return self.finish(context, cancelled=True)

        elif event.type == "ESC":
            self.report({"WARNING"}, "Job cancelled by user")
            return self.finish(context, cancelled=True)

        # PASS_THROUGH allows other Blender events to be processed
        return {"PASS_THROUGH"}

    def execute(self, context):
        return self.invoke(context, None)

    def invoke(self, context, event):
        props = context.scene.uthana_props

        # Validate inputs
        if not props.api_key:
            self.report({"ERROR"}, "API Key is required")
            return {"CANCELLED"}

        if not props.video_file_path:
            self.report({"ERROR"}, "No video file selected")
            return {"CANCELLED"}

        # Reset state
        self._job_id = ""
        self._poll_count = 0
        self._upload_thread = None
        self._upload_result = None
        self._upload_error = None
        self._upload_complete = False
        self._phase = "uploading"

        motion_name = props.video_motion_name or "Video Motion"
        props.video_job_id = ""
        props.video_job_status = "Starting upload..."
        props.video_job_progress = 0

        # Start upload in background thread
        self._upload_thread = threading.Thread(
            target=self._do_upload,
            args=(props.api_key, props.domain, props.video_file_path, motion_name),
            daemon=True,
        )
        self._upload_thread.start()

        # Start timer for polling
        wm = context.window_manager
        self._timer = wm.event_timer_add(0.5, window=context.window)  # Check every 0.5s
        wm.modal_handler_add(self)

        self.report({"INFO"}, "Video upload started...")
        return {"RUNNING_MODAL"}

    def _do_upload(self, api_key: str, domain: str, video_path: str, motion_name: str):
        """Background thread for video upload."""
        try:
            result = client.create_video_to_motion(api_key, domain, video_path, motion_name)
            if result.success:
                self._upload_result = result.data
            else:
                self._upload_error = result.message
        except Exception as e:
            self._upload_error = str(e)
        finally:
            self._upload_complete = True

    def finish(self, context, cancelled: bool):
        """Clean up and finish the operator."""
        wm = context.window_manager
        if self._timer:
            wm.event_timer_remove(self._timer)
            self._timer = None

        props = context.scene.uthana_props
        props.video_job_id = ""
        if cancelled:
            props.video_job_progress = 0
            props.video_job_status = ""

        # Remove from job manager
        if self._job_id:
            JobManager.instance().remove_job(self._job_id)

        # Force final UI redraw
        for area in context.screen.areas:
            if area.type == "VIEW_3D":
                area.tag_redraw()

        return {"CANCELLED"} if cancelled else {"FINISHED"}

    def import_motion(self, context, motion_id: str):
        """Download and import the generated motion."""
        props = context.scene.uthana_props
        # Use selected character or default
        char_id = props.character_id or TAR_CHARACTER_ID

        result = motion.download_and_import_motion(props.domain, props.api_key, char_id, motion_id)

        if result.success:
            logger.info("Motion imported successfully: %s", motion_id)
            self.report({"INFO"}, "Motion imported into scene")
        else:
            logger.warning("Motion import failed: %s", result.message)
            self.report({"WARNING"}, f"Motion created but import failed: {result.message}")

    def _sync_motions_to_ui(self, props):
        """Sync motion list to UI collection."""
        manager = assets.AssetManager.instance()
        motions = manager.get_motions()
        props.motions.clear()
        for m in motions:
            item = props.motions.add()
            item.id = m.id
            item.name = m.name
            item.created = m.created


class UTHANA_OT_character_upload(bpy.types.Operator):
    """Upload a character file with auto-rigging."""

    bl_idname = "uthana.character_upload"
    bl_label = "Upload Character"
    bl_description = "Upload a character file for auto-rigging"
    bl_options = {"REGISTER"}

    _timer = None
    _upload_thread: Optional[threading.Thread] = None
    _upload_result: Optional[dict] = None
    _upload_error: Optional[str] = None
    _upload_complete: bool = False
    _poll_count: int = 0

    def modal(self, context, event):
        if event.type == "TIMER":
            props = context.scene.uthana_props

            # Force UI redraw
            for area in context.screen.areas:
                if area.type == "VIEW_3D":
                    area.tag_redraw()

            if self._upload_complete:
                if self._upload_error:
                    self.report({"ERROR"}, self._upload_error)
                    return self.finish(context, cancelled=True)

                if self._upload_result:
                    char_id = self._upload_result.get("character_id")
                    char_name = self._upload_result.get("name", "Character")
                    self.report({"INFO"}, f"Character uploaded: {char_name}")
                    props.character_upload_status = "Complete!"

                    # Refresh character list
                    assets.AssetManager.instance().refresh_characters(
                        props.api_key, props.domain, force=True
                    )
                    self._sync_characters_to_ui(props)

                    # Auto-import if requested
                    if props.character_auto_import and char_id:
                        self.import_character(context, char_id)

                    return self.finish(context, cancelled=False)
                else:
                    self.report({"ERROR"}, "Upload failed - no result")
                    return self.finish(context, cancelled=True)
            else:
                # Still uploading
                self._poll_count += 1
                props.character_upload_status = f"Uploading... ({self._poll_count}s)"

        elif event.type == "ESC":
            self.report({"WARNING"}, "Cancelled by user")
            return self.finish(context, cancelled=True)

        return {"PASS_THROUGH"}

    def execute(self, context):
        return self.invoke(context, None)

    def invoke(self, context, event):
        props = context.scene.uthana_props

        # Validate inputs
        if not props.api_key:
            self.report({"ERROR"}, "API Key is required")
            return {"CANCELLED"}

        if not props.character_file_path:
            self.report({"ERROR"}, "No character file selected")
            return {"CANCELLED"}

        # Reset state
        self._upload_thread = None
        self._upload_result = None
        self._upload_error = None
        self._upload_complete = False
        self._poll_count = 0

        character_name = props.character_upload_name or "My Character"
        props.character_upload_status = "Starting upload..."

        # Start upload in background thread
        self._upload_thread = threading.Thread(
            target=self._do_upload,
            args=(
                props.api_key,
                props.domain,
                props.character_file_path,
                character_name,
                props.character_auto_rig,
            ),
            daemon=True,
        )
        self._upload_thread.start()

        # Start timer
        wm = context.window_manager
        self._timer = wm.event_timer_add(1.0, window=context.window)
        wm.modal_handler_add(self)

        self.report({"INFO"}, "Character upload started...")
        return {"RUNNING_MODAL"}

    def _do_upload(self, api_key: str, domain: str, file_path: str, name: str, auto_rig: bool):
        """Background thread for character upload."""
        try:
            result = client.create_character(api_key, domain, file_path, name, auto_rig)
            if result.success:
                self._upload_result = result.data
            else:
                self._upload_error = result.message
        except Exception as e:
            self._upload_error = str(e)
        finally:
            self._upload_complete = True

    def finish(self, context, cancelled: bool):
        """Clean up and finish the operator."""
        wm = context.window_manager
        if self._timer:
            wm.event_timer_remove(self._timer)
            self._timer = None

        props = context.scene.uthana_props
        props.character_upload_job_id = ""
        if cancelled:
            props.character_upload_status = ""

        # Force final UI redraw
        for area in context.screen.areas:
            if area.type == "VIEW_3D":
                area.tag_redraw()

        return {"CANCELLED"} if cancelled else {"FINISHED"}

    def import_character(self, context, character_id: str):
        """Download and import the character."""
        props = context.scene.uthana_props

        result = client.download_character(props.api_key, props.domain, character_id, "fbx")

        if result.success:
            file_path = result.data.get("file_path")
            if file_path:
                # Import FBX with axis correction
                bpy.ops.import_scene.fbx(filepath=file_path, axis_forward="-Z", axis_up="Y")

                logger.info("Character imported: %s", character_id)
                self.report({"INFO"}, "Character imported into scene")
        else:
            logger.warning("Character import failed: %s", result.message)

    def _sync_characters_to_ui(self, props):
        """Sync character list to UI collection."""
        manager = assets.AssetManager.instance()
        characters = manager.get_characters()
        props.characters.clear()
        for c in characters:
            item = props.characters.add()
            item.id = c.id
            item.name = c.name
            item.created = c.created


class UTHANA_OT_use_selected_character(bpy.types.Operator):
    """Set the selected character as the active character for generation."""

    bl_idname = "uthana.use_selected_character"
    bl_label = "Use Selected Character"
    bl_description = "Use the selected character for motion generation"

    def execute(self, context):
        props = context.scene.uthana_props

        if not props.characters or props.character_index < 0:
            self.report({"ERROR"}, "No character selected")
            return {"CANCELLED"}

        if props.character_index >= len(props.characters):
            self.report({"ERROR"}, "Invalid character selection")
            return {"CANCELLED"}

        selected_char = props.characters[props.character_index]
        props.character_id = selected_char.id

        self.report({"INFO"}, f"Using character: {selected_char.name}")
        return {"FINISHED"}


class UTHANA_OT_download_character(bpy.types.Operator):
    """Download and import a character from the list."""

    bl_idname = "uthana.download_character"
    bl_label = "Download Character"
    bl_description = "Download the selected character and import into scene"

    def execute(self, context):
        props = context.scene.uthana_props

        if not props.characters or props.character_index < 0:
            self.report({"ERROR"}, "No character selected")
            return {"CANCELLED"}

        if props.character_index >= len(props.characters):
            self.report({"ERROR"}, "Invalid character selection")
            return {"CANCELLED"}

        selected_char = props.characters[props.character_index]

        result = client.download_character(props.api_key, props.domain, selected_char.id, "fbx")

        if result.success:
            file_path = result.data.get("file_path")
            if file_path:
                # Import FBX with axis correction
                bpy.ops.import_scene.fbx(filepath=file_path, axis_forward="-Z", axis_up="Y")

                self.report({"INFO"}, f"Character imported: {selected_char.name}")
                return {"FINISHED"}

        self.report({"ERROR"}, f"Download failed: {result.message}")
        return {"CANCELLED"}


# Classes to register
classes = (
    UTHANA_OT_video_to_motion,
    UTHANA_OT_character_upload,
    UTHANA_OT_use_selected_character,
    UTHANA_OT_download_character,
)
