"""Modal operators for async operations in Uthana plugin.

These operators use Blender's timer system to poll for job completion
without blocking the UI.
"""

import threading
import time
from typing import Any, Callable, Optional

import bpy

from .. import assets, client, motion
from ..constants import DEFAULT_VTM_MODEL, TAR_CHARACTER_ID, TTM_JOB_MODELS
from ..jobs import JobManager, JobStatus
from ..logger import logger
from ..types import MotionRequest, OperationResult

# Seconds between job status checks while a job is running.
JOB_POLL_SECONDS = 3.0


class _BackgroundCall:
    """Runs one blocking API call on a thread so the Blender UI stays responsive."""

    def __init__(self, func: Callable[..., OperationResult], *args: Any):
        self.result: Optional[OperationResult] = None
        self.done = False
        self._thread = threading.Thread(target=self._run, args=(func, *args), daemon=True)
        self._thread.start()

    def _run(self, func: Callable[..., OperationResult], *args: Any) -> None:
        try:
            self.result = func(*args)
        except Exception as e:  # noqa: BLE001 - surfaced to the user by the operator
            self.result = OperationResult(success=False, message=str(e))
        finally:
            self.done = True


def _start_preview(operator: bpy.types.Operator) -> None:
    """Auto-start the sidebar preview; a missing preview must not fail the generation."""
    try:
        bpy.ops.uthana.play_motion_preview("INVOKE_DEFAULT")
    except RuntimeError as e:
        logger.warning("Preview not available yet: %s", e)
        operator.report({"INFO"}, "Preview not ready yet. Use the browser preview button.")


def _scene_key(scene: bpy.types.Scene) -> int:
    """A value that identifies a scene for as long as it exists, even if it is renamed."""
    return getattr(scene, "session_uid", None) or scene.as_pointer()


def _find_scene(key: int) -> Optional[bpy.types.Scene]:
    """The scene a generation started in, or None if it has been deleted."""
    for scene in bpy.data.scenes:
        if _scene_key(scene) == key:
            return scene
    return None


class UTHANA_OT_generate_motion(bpy.types.Operator):
    """Generate motion from a text prompt with the selected model.

    The 3.0 models run as a background job that is polled until it finishes; the
    older models answer in one request. Both run off the main thread.
    """

    bl_idname = "uthana.generate_motion"
    bl_label = "Generate"
    bl_description = "Generate motion from the text prompt with the selected model"
    bl_options = {"REGISTER"}

    # Only one generation is tracked at a time; panels read this to swap the button
    # for a status line. A class flag (not a scene property) so it resets on restart.
    _running: bool = False

    _timer = None
    # The scene the generation was started in. The result and the status line belong
    # to that scene, whichever scene is on screen when the job finishes.
    _origin_scene: int = 0
    _request: Optional[MotionRequest] = None
    _is_job: bool = False
    _job_id: str = ""
    _phase: str = "submitting"  # "submitting" or "processing"
    _started: float = 0.0
    _last_poll: float = 0.0
    _call: Optional[_BackgroundCall] = None
    _poll_failures: int = 0
    _timeout_seconds: float = 900.0
    _max_poll_failures: int = 5

    @classmethod
    def is_running(cls) -> bool:
        return cls._running

    def execute(self, context):
        return self.invoke(context, None)

    def invoke(self, context, event):
        props = context.scene.uthana_props

        if UTHANA_OT_generate_motion._running:
            self.report({"WARNING"}, "A generation is already running")
            return {"CANCELLED"}
        if not props.api_key:
            self.report({"ERROR"}, "API key is required")
            return {"CANCELLED"}
        if not props.prompt.strip():
            self.report({"ERROR"}, "Enter a prompt first")
            return {"CANCELLED"}

        request = props.create_generate_motion_request()
        self._request = MotionRequest(
            domain=request.domain,
            api_key=request.api_key,
            character_id=request.character_id,
            prompt=request.prompt,
            model=request.model,
            length=request.length,
        )
        self._origin_scene = _scene_key(context.scene)
        self._is_job = request.model in TTM_JOB_MODELS
        self._job_id = ""
        self._phase = "submitting"
        self._started = time.time()
        self._last_poll = 0.0
        self._poll_failures = 0

        submit = client.create_text_to_motion_job if self._is_job else client.create_text_to_motion
        self._call = _BackgroundCall(submit, self._request)

        UTHANA_OT_generate_motion._running = True
        props.ttm_job_status = "Sending request..."

        wm = context.window_manager
        self._timer = wm.event_timer_add(0.5, window=context.window)
        wm.modal_handler_add(self)
        return {"RUNNING_MODAL"}

    def modal(self, context, event):
        if event.type == "ESC":
            if self._job_id:
                self.report(
                    {"WARNING"},
                    "Stopped waiting. The job keeps running; the motion will show up in Motions.",
                )
            else:
                self.report({"WARNING"}, "Stopped waiting for the request")
            return self.finish(context, cancelled=True)

        if event.type != "TIMER":
            return {"PASS_THROUGH"}

        scene = _find_scene(self._origin_scene)
        if scene is None:
            self.report(
                {"WARNING"},
                "The scene this generation started in was removed. If the motion was "
                "created it will show up in Motions.",
            )
            return self.finish(context, cancelled=True)
        props = scene.uthana_props
        elapsed = int(time.time() - self._started)
        self._redraw(context)

        # The overall deadline applies in every phase, including while a network call
        # is still waiting for an answer.
        if elapsed > self._timeout_seconds:
            waited = self._waited_label()
            if self._job_id:
                self.report(
                    {"ERROR"},
                    f"Still running after {waited}. Check Motions later; do not regenerate yet.",
                )
            else:
                self.report(
                    {"ERROR"},
                    f"No answer after {waited}. The request may still have gone through; "
                    "check Motions before generating again.",
                )
            return self.finish(context, cancelled=True)

        if self._phase == "submitting":
            if not self._call or not self._call.done:
                props.ttm_job_status = f"Sending request... {elapsed}s"
                return {"PASS_THROUGH"}

            result = self._call.result
            self._call = None
            if not result or not result.success or not result.data:
                message = result.message if result else "Request failed"
                # The paid request is never sent twice. When its outcome is unknown,
                # say so instead of retrying.
                if result and result.error_code in client.OUTCOME_UNKNOWN_CODES:
                    message += (
                        ". The request may still have gone through; check Motions "
                        "before generating again."
                    )
                self.report({"ERROR"}, message)
                return self.finish(context, cancelled=True)

            if not self._is_job:
                motion_data = result.data.get("motion") or {}
                return self._complete(
                    context, result.data.get("motion_id"), motion_data.get("name")
                )

            self._job_id = result.data.get("job_id", "")
            if not self._job_id:
                self.report({"ERROR"}, "No job ID returned")
                return self.finish(context, cancelled=True)
            self._phase = "processing"
            return {"PASS_THROUGH"}

        # Processing: check the job every few seconds, off the main thread.
        props.ttm_job_status = f"Generating... {elapsed}s"

        if self._call is None:
            if time.time() - self._last_poll >= JOB_POLL_SECONDS:
                self._last_poll = time.time()
                self._call = _BackgroundCall(
                    client.get_job_status, self._request.api_key, self._request.domain, self._job_id
                )
            return {"PASS_THROUGH"}

        if not self._call.done:
            return {"PASS_THROUGH"}

        result = self._call.result
        self._call = None
        if not result or not result.success or not result.data:
            # A failed status check is not a failed job: retry a few times first.
            self._poll_failures += 1
            if self._poll_failures >= self._max_poll_failures:
                self.report(
                    {"ERROR"},
                    "Lost contact with the job. It may still finish; check Motions before "
                    "generating again.",
                )
                return self.finish(context, cancelled=True)
            return {"PASS_THROUGH"}
        self._poll_failures = 0

        status = JobStatus.from_string(str(result.data.get("status", "UNKNOWN")))
        job_result = result.data.get("result")

        if status == JobStatus.FINISHED:
            motion_id = client.extract_job_motion_id(job_result)
            if not motion_id:
                self.report({"WARNING"}, "Job finished but no motion ID was returned")
                return self.finish(context, cancelled=True)
            return self._complete(context, motion_id, client.extract_job_motion_name(job_result))

        if status == JobStatus.FAILED:
            self.report({"ERROR"}, f"Generation failed: {client.extract_job_error(job_result)}")
            return self.finish(context, cancelled=True)

        return {"PASS_THROUGH"}

    def _complete(self, context, motion_id: Optional[str], motion_name: Optional[str]):
        scene = _find_scene(self._origin_scene)
        if scene is None:
            self.report(
                {"WARNING"},
                "Motion generated, but its scene was removed. Find it in Motions.",
            )
            return self.finish(context, cancelled=True)
        props = scene.uthana_props
        if not motion_id:
            self.report({"ERROR"}, "No motion ID returned")
            return self.finish(context, cancelled=True)

        motion_name = motion_name or "Generated Motion"

        # Store pending motion for preview
        props.pending_motion_id = motion_id
        props.pending_motion_name = motion_name
        props.pending_character_id = self._request.character_id if self._request else ""
        props.pending_motion_source = "text"
        props.generate_result_motion_id = motion_id

        # Reset preview state
        props.preview_frames_loaded = False
        props.preview_current_frame_idx = 0
        props.pending_preview_video_path = ""

        result = self.finish(context, cancelled=False)
        if context.scene == scene:
            self.report({"INFO"}, f"Motion '{motion_name}' generated! Check preview in sidebar.")
            _start_preview(self)
        else:
            # The preview operator works on the scene on screen, so leave it for when
            # the user is back in the scene that owns this motion.
            self.report(
                {"INFO"},
                f"Motion '{motion_name}' generated in scene '{scene.name}'. "
                "Switch to it to preview.",
            )
        return result

    def _waited_label(self) -> str:
        minutes = int(self._timeout_seconds // 60)
        if minutes >= 1:
            return f"{minutes} minutes"
        return f"{int(self._timeout_seconds)} seconds"

    def cancel(self, context):
        # Blender calls this when it ends the operator itself, for example when a
        # window closes or another file is opened.
        self.finish(context, cancelled=True)

    def finish(self, context, cancelled: bool):
        if self._timer:
            try:
                context.window_manager.event_timer_remove(self._timer)
            except (AttributeError, ReferenceError, RuntimeError) as e:
                logger.warning("Could not remove the generation timer: %s", e)
            self._timer = None
        # A call that is still waiting is abandoned, not retried: its thread ends
        # when the network timeout fires.
        self._call = None
        UTHANA_OT_generate_motion._running = False
        scene = _find_scene(self._origin_scene)
        if scene is not None:
            scene.uthana_props.ttm_job_status = ""
        self._redraw(context)
        return {"CANCELLED"} if cancelled else {"FINISHED"}

    @staticmethod
    def _redraw(context) -> None:
        if not getattr(context, "screen", None):
            return
        for area in context.screen.areas:
            if area.type == "VIEW_3D":
                area.tag_redraw()


class UTHANA_OT_video_to_motion(bpy.types.Operator):
    """Generate motion from a video file.

    The upload and every status check run off the main thread. Like text to motion,
    the job belongs to the scene it was started in.
    """

    bl_idname = "uthana.video_to_motion"
    bl_label = "Generate motion from video"
    bl_description = "Upload a 2D video and extract motion (can take 60+ seconds)"
    bl_options = {"REGISTER"}

    # Only one upload is tracked at a time; the panel reads this to hide the button
    # while a video is uploading, so the paid request cannot be sent twice by accident.
    _running: bool = False

    _timer = None
    _origin_scene: int = 0
    _api_key: str = ""
    _domain: str = ""
    _character_id: str = ""
    _motion_name: str = ""
    _job_id: str = ""
    _poll_count: int = 0
    _phase: str = "uploading"  # "uploading" or "processing"
    _started: float = 0.0
    _last_poll: float = 0.0
    _call: Optional[_BackgroundCall] = None
    _poll_failures: int = 0
    _timeout_seconds: float = 1200.0
    _max_poll_failures: int = 5

    @classmethod
    def is_running(cls) -> bool:
        return cls._running

    def execute(self, context):
        return self.invoke(context, None)

    def invoke(self, context, event):
        props = context.scene.uthana_props

        if UTHANA_OT_video_to_motion._running:
            self.report({"WARNING"}, "A video is already being processed")
            return {"CANCELLED"}
        if not props.api_key:
            self.report({"ERROR"}, "API key is required")
            return {"CANCELLED"}
        if not props.video_file_path:
            self.report({"ERROR"}, "No video file selected")
            return {"CANCELLED"}

        # Everything the job needs is read once, here, from the scene that starts it.
        self._origin_scene = _scene_key(context.scene)
        self._api_key = props.api_key
        self._domain = props.domain
        self._character_id = props.character_id or TAR_CHARACTER_ID
        self._motion_name = props.video_motion_name or "Video Motion"
        self._job_id = ""
        self._poll_count = 0
        self._phase = "uploading"
        self._started = time.time()
        self._last_poll = 0.0
        self._poll_failures = 0

        props.video_job_id = ""
        props.video_job_status = "Starting upload..."
        props.video_job_progress = 0

        self._call = _BackgroundCall(
            client.create_video_to_motion,
            self._api_key,
            self._domain,
            props.video_file_path,
            self._motion_name,
            props.vtm_model or DEFAULT_VTM_MODEL,
        )
        UTHANA_OT_video_to_motion._running = True

        wm = context.window_manager
        self._timer = wm.event_timer_add(0.5, window=context.window)
        wm.modal_handler_add(self)

        self.report({"INFO"}, "Video upload started...")
        return {"RUNNING_MODAL"}

    def modal(self, context, event):
        if event.type == "ESC":
            if self._job_id:
                self.report(
                    {"WARNING"},
                    "Stopped waiting. The job keeps running; the motion will show up in Motions.",
                )
            else:
                self.report({"WARNING"}, "Stopped waiting for the upload")
            return self.finish(context, cancelled=True)

        if event.type != "TIMER":
            return {"PASS_THROUGH"}

        scene = _find_scene(self._origin_scene)
        if scene is None:
            self.report(
                {"WARNING"},
                "The scene this job started in was removed. If the motion was created "
                "it will show up in Motions.",
            )
            return self.finish(context, cancelled=True)
        props = scene.uthana_props
        self._redraw(context)

        # The overall deadline applies in every phase, including while a network call
        # is still waiting for an answer.
        if time.time() - self._started > self._timeout_seconds:
            minutes = max(1, int(self._timeout_seconds // 60))
            if self._job_id:
                self.report(
                    {"ERROR"},
                    f"Still running after {minutes} minutes. Check Motions later; "
                    "do not upload again yet.",
                )
            else:
                self.report(
                    {"ERROR"},
                    f"No answer after {minutes} minutes. The upload may still have gone "
                    "through; check Motions before uploading again.",
                )
            return self.finish(context, cancelled=True)

        if self._phase == "uploading":
            if not self._call or not self._call.done:
                self._poll_count += 1
                props.video_job_status = "Uploading..."
                props.video_job_progress = min(10, (self._poll_count % 10))
                return {"PASS_THROUGH"}

            result = self._call.result
            self._call = None
            if not result or not result.success or not result.data:
                message = result.message if result else "Upload failed - no result"
                # The paid upload is never sent twice. When its outcome is unknown,
                # say so instead of retrying.
                if result and result.error_code in client.OUTCOME_UNKNOWN_CODES:
                    message += (
                        ". The upload may still have gone through; check Motions "
                        "before uploading again."
                    )
                self.report({"ERROR"}, message)
                return self.finish(context, cancelled=True)

            self._job_id = result.data.get("job_id", "")
            if not self._job_id:
                self.report({"ERROR"}, "No job ID")
                return self.finish(context, cancelled=True)
            props.video_job_id = self._job_id
            props.video_job_status = result.data.get("status", "RESERVED")
            props.video_job_progress = 10  # Upload done, processing starts
            self._poll_count = 0
            self._phase = "processing"
            self.report({"INFO"}, "Video uploaded, processing...")
            return {"PASS_THROUGH"}

        # Processing: check the job every few seconds, off the main thread.
        if self._call is None:
            if time.time() - self._last_poll >= JOB_POLL_SECONDS:
                self._last_poll = time.time()
                self._call = _BackgroundCall(
                    client.get_job_status, self._api_key, self._domain, self._job_id
                )
            return {"PASS_THROUGH"}

        if not self._call.done:
            return {"PASS_THROUGH"}

        result = self._call.result
        self._call = None
        if not result or not result.success or not result.data:
            # A failed status check is not a failed job: retry a few times first.
            self._poll_failures += 1
            if self._poll_failures >= self._max_poll_failures:
                self.report(
                    {"ERROR"},
                    "Lost contact with the job. It may still finish; check Motions before "
                    "uploading again.",
                )
                return self.finish(context, cancelled=True)
            return {"PASS_THROUGH"}
        self._poll_failures = 0

        status_str = str(result.data.get("status", "UNKNOWN"))
        status = JobStatus.from_string(status_str)
        props.video_job_status = status_str
        job_result = result.data.get("result")

        if status == JobStatus.FINISHED:
            motion_id = client.extract_job_motion_id(job_result)
            if not motion_id:
                self.report({"WARNING"}, "Motion created but ID not found in result")
                return self.finish(context, cancelled=False)

            props.video_result_motion_id = motion_id
            props.video_job_progress = 100

            # Store pending motion for preview
            props.pending_motion_id = motion_id
            props.pending_motion_name = self._motion_name
            props.pending_character_id = self._character_id
            props.pending_motion_source = "video"

            # Reset preview state
            props.preview_frames_loaded = False
            props.preview_current_frame_idx = 0
            props.pending_preview_video_path = ""

            if context.scene == scene:
                self.report(
                    {"INFO"}, f"Motion '{self._motion_name}' created! Check preview in sidebar."
                )
                _start_preview(self)
            else:
                # The preview operator works on the scene on screen, so leave it for
                # when the user is back in the scene that owns this motion.
                self.report(
                    {"INFO"},
                    f"Motion '{self._motion_name}' created in scene '{scene.name}'. "
                    "Switch to it to preview.",
                )

            # Refresh motions list
            assets.AssetManager.instance().refresh_motions(self._api_key, self._domain, force=True)
            self._sync_motions_to_ui(props)
            return self.finish(context, cancelled=False)

        if status == JobStatus.FAILED:
            self.report({"ERROR"}, f"Job failed: {client.extract_job_error(job_result)}")
            return self.finish(context, cancelled=True)

        # Still running - progress estimate (10-95%) from typical processing time.
        self._poll_count += 1
        props.video_job_progress = min(95, 10 + (self._poll_count * 1.5))
        return {"PASS_THROUGH"}

    def cancel(self, context):
        # Blender calls this when it ends the operator itself, for example when a
        # window closes or another file is opened.
        self.finish(context, cancelled=True)

    def finish(self, context, cancelled: bool):
        """Clean up and finish the operator."""
        if self._timer:
            try:
                context.window_manager.event_timer_remove(self._timer)
            except (AttributeError, ReferenceError, RuntimeError) as e:
                logger.warning("Could not remove the video job timer: %s", e)
            self._timer = None
        # A call that is still waiting is abandoned, not retried: its thread ends
        # when the network timeout fires.
        self._call = None
        UTHANA_OT_video_to_motion._running = False

        scene = _find_scene(self._origin_scene)
        if scene is not None:
            props = scene.uthana_props
            props.video_job_id = ""
            if cancelled:
                props.video_job_progress = 0
                props.video_job_status = ""

        # Remove from job manager
        if self._job_id:
            JobManager.instance().remove_job(self._job_id)

        self._redraw(context)
        return {"CANCELLED"} if cancelled else {"FINISHED"}

    @staticmethod
    def _redraw(context) -> None:
        if not getattr(context, "screen", None):
            return
        for area in context.screen.areas:
            if area.type == "VIEW_3D":
                area.tag_redraw()

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
    bl_label = "Upload character"
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
            self.report({"ERROR"}, "API key is required")
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
    bl_label = "Use selected character"
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
    bl_label = "Download character"
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
    UTHANA_OT_generate_motion,
    UTHANA_OT_video_to_motion,
    UTHANA_OT_character_upload,
    UTHANA_OT_use_selected_character,
    UTHANA_OT_download_character,
)
