# flake8: noqa F722,F821
# type: ignore[report-invalid-property]
"""Blender property definitions for Uthana plugin."""

import bpy
from bpy.props import (
    BoolProperty,
    CollectionProperty,
    FloatProperty,
    IntProperty,
    StringProperty,
)

from ..types import (
    BakeAndUploadRequest,
    GenerateMotionRequest,
    LoadMotionRequest,
    StitchMotionIdsRequest,
    StitchMotionsRequest,
)


class MotionListItem(bpy.types.PropertyGroup):
    """Single motion item for UIList."""

    id: StringProperty(name="ID", description="Motion ID")
    name: StringProperty(name="Name", description="Motion name")
    created: StringProperty(name="Created", description="Creation date")
    is_favorite: BoolProperty(
        name="Favorite", description="Is this motion a favorite", default=False
    )


class CharacterListItem(bpy.types.PropertyGroup):
    """Single character item for UIList."""

    id: StringProperty(name="ID", description="Character ID")
    name: StringProperty(name="Name", description="Character name")
    created: StringProperty(name="Created", description="Creation date")


class UthanaProperties(bpy.types.PropertyGroup):
    """UI properties for Uthana plugin."""

    # Authentication
    api_key: StringProperty(
        name="API key",
        description="Your Uthana API key (get it from uthana.com/app/account)",
        default="",
        subtype="PASSWORD",
    )

    domain: StringProperty(
        name="Domain",
        description="API domain",
        default="uthana.com",
    )

    # Account info (populated from API)
    user_name: StringProperty(name="User", default="")
    org_name: StringProperty(name="Organization", default="")
    download_secs_remaining: FloatProperty(name="Download Seconds Remaining", default=0)

    # Motion list
    motions: CollectionProperty(type=MotionListItem)
    motion_index: IntProperty(name="Motion Index", default=0)

    # Character list
    characters: CollectionProperty(type=CharacterListItem)
    character_index: IntProperty(name="Character Index", default=0)

    # Text to Motion
    prompt: StringProperty(
        name="Prompt",
        description="Enter motion description",
        default="A person ",
        options={"TEXTEDIT_UPDATE"},
    )

    character_id: StringProperty(
        name="Character ID",
        description="Character ID for motion generation",
        default="cXi2eAP19XwQ",
    )

    generate_result_motion_id: StringProperty(
        name="Result Motion ID",
        description="Motion ID from last text-to-motion generation",
        default="",
    )

    # Video to Motion
    video_file_path: StringProperty(
        name="Video File",
        subtype="FILE_PATH",
        description="Video file for motion extraction (.mp4, .mov, .avi)",
    )

    video_motion_name: StringProperty(
        name="Motion Name",
        description="Name for the generated motion",
        default="",
    )

    video_job_id: StringProperty(name="Job ID", default="")
    video_job_status: StringProperty(name="Job Status", default="")
    video_job_progress: FloatProperty(
        name="Progress",
        min=0,
        max=100,
        subtype="PERCENTAGE",
        default=0,
    )

    video_result_motion_id: StringProperty(
        name="Result Motion ID",
        description="Motion ID from video-to-motion generation",
        default="",
    )

    # Pending Motion Preview (for confirmation before download)
    pending_motion_id: StringProperty(
        name="Pending Motion ID",
        description="Motion ID waiting for preview confirmation",
        default="",
    )

    pending_motion_name: StringProperty(
        name="Pending Motion Name",
        description="Name of motion waiting for preview",
        default="",
    )

    pending_character_id: StringProperty(
        name="Pending Character ID",
        description="Character ID for pending motion",
        default="",
    )

    pending_preview_image_path: StringProperty(
        name="Preview Image Path",
        description="Path to downloaded preview image",
        default="",
        subtype="FILE_PATH",
    )

    pending_motion_source: StringProperty(
        name="Pending Motion Source",
        description="Source workflow that generated this pending motion (text or video)",
        default="",
    )

    # Character Upload
    character_file_path: StringProperty(
        name="Character File",
        subtype="FILE_PATH",
        description="Character file for upload (.fbx, .glb, .gltf)",
    )

    character_upload_name: StringProperty(
        name="Character Name",
        description="Name for the uploaded character",
        default="",
    )

    character_auto_rig: BoolProperty(
        name="Auto-Rig",
        description="Automatically rig the character",
        default=True,
    )

    character_auto_import: BoolProperty(
        name="Import to Scene",
        description="Automatically import the character into the scene after upload",
        default=False,
    )

    character_upload_job_id: StringProperty(name="Upload Job ID", default="")
    character_upload_status: StringProperty(name="Upload Status", default="")

    # Load Motion
    load_motion_id: StringProperty(
        name="Motion ID",
        description="Motion ID to load from server",
        default="",
    )

    load_character_id: StringProperty(
        name="Character ID",
        description="Character ID for loading motion",
        default="cXi2eAP19XwQ",
    )

    load_result_motion_id: StringProperty(
        name="Result Motion ID",
        description="Motion ID from last load operation",
        default="",
    )

    # Bake Motion
    bake_character_id: StringProperty(
        name="Character ID",
        description="Character ID for motion creation",
        default="cXi2eAP19XwQ",
    )

    bake_use_frame_range: BoolProperty(
        name="Use Frame Range",
        description="Use current frame range instead of full animation",
        default=True,
    )

    bake_result_motion_id: StringProperty(
        name="Result Motion ID",
        description="Motion ID from last bake operation",
        default="",
    )

    # Stitch Armatures
    stitch_character_id: StringProperty(
        name="Character ID",
        description="Character ID for stitching",
        default="cXi2eAP19XwQ",
    )

    stitch_duration: FloatProperty(
        name="Duration",
        description="Duration of stitching transition in seconds",
        default=1.0,
        min=0.1,
        max=10.0,
        step=10,
        precision=1,
    )

    stitch_use_frame_range: BoolProperty(
        name="Use Frame Range",
        description="Use current frame range instead of full animations",
        default=False,
    )

    stitch_result_motion_id: StringProperty(
        name="Result Motion ID",
        description="Motion ID from last armature stitching",
        default="",
    )

    # Stitch Motion IDs
    stitch_ids_character_id: StringProperty(
        name="Character ID",
        description="Character ID for motion ID stitching",
        default="cXi2eAP19XwQ",
    )

    stitch_ids_leading_motion_id: StringProperty(
        name="Leading Motion ID",
        description="Motion ID for leading animation",
        default="",
    )

    stitch_ids_trailing_motion_id: StringProperty(
        name="Trailing Motion ID",
        description="Motion ID for trailing animation",
        default="",
    )

    stitch_ids_duration: FloatProperty(
        name="Duration",
        description="Duration of stitching transition in seconds",
        default=1.0,
        min=0.1,
        max=10.0,
        step=10,
        precision=1,
    )

    stitch_ids_result_motion_id: StringProperty(
        name="Result Motion ID",
        description="Motion ID from last motion ID stitching",
        default="",
    )

    # Preview Animation State
    preview_frames_loaded: BoolProperty(
        name="Preview Frames Loaded",
        description="Whether preview animation frames are loaded",
        default=False,
    )

    preview_current_frame_idx: IntProperty(
        name="Current Preview Frame",
        description="Current frame index in preview animation",
        default=0,
    )

    pending_preview_video_path: StringProperty(
        name="Preview Video Path",
        description="Path to downloaded preview animation (WebM)",
        default="",
        subtype="FILE_PATH",
    )

    # UI Section Toggles
    show_config: BoolProperty(
        name="Config",
        description="Show/hide configuration settings",
        default=False,
    )

    show_account: BoolProperty(
        name="Account",
        description="Show/hide account info",
        default=False,
    )

    show_motions_browser: BoolProperty(
        name="Motions",
        description="Show/hide motions browser",
        default=True,
    )

    show_characters_browser: BoolProperty(
        name="Characters",
        description="Show/hide characters browser",
        default=False,
    )

    show_text_to_motion: BoolProperty(
        name="Text to Motion",
        description="Show/hide text to motion settings",
        default=True,
    )

    show_video_to_motion: BoolProperty(
        name="Video to Motion",
        description="Show/hide video to motion settings",
        default=False,
    )

    show_character_upload: BoolProperty(
        name="Character Upload",
        description="Show/hide character upload settings",
        default=False,
    )

    show_load_motion: BoolProperty(
        name="Load Motion",
        description="Show/hide load motion settings",
        default=True,
    )

    show_bake: BoolProperty(
        name="Bake",
        description="Show/hide bake settings",
        default=True,
    )

    show_stitching: BoolProperty(
        name="Stitching",
        description="Show/hide stitching settings",
        default=False,
    )

    show_stitch_motion_ids: BoolProperty(
        name="Stitch Motion IDs",
        description="Show/hide stitch motion IDs settings",
        default=True,
    )

    # Request builder methods
    def create_generate_motion_request(self) -> GenerateMotionRequest:
        """Create a GenerateMotionRequest from current UI state."""
        return GenerateMotionRequest(
            domain=self.domain,
            api_key=self.api_key,
            character_id=self.character_id,
            prompt=self.prompt,
        )

    def create_load_motion_request(self) -> LoadMotionRequest:
        """Create a LoadMotionRequest from current UI state."""
        return LoadMotionRequest(
            domain=self.domain,
            api_key=self.api_key,
            character_id=self.load_character_id,
            motion_id=self.load_motion_id,
        )

    def create_bake_request(self) -> BakeAndUploadRequest:
        """Create a BakeAndUploadRequest from current UI state."""
        return BakeAndUploadRequest(
            domain=self.domain,
            api_key=self.api_key,
            character_id=self.bake_character_id,
            use_frame_range=self.bake_use_frame_range,
        )

    def create_stitch_motions_request(self) -> StitchMotionsRequest:
        """Create a StitchMotionsRequest from current UI state."""
        return StitchMotionsRequest(
            domain=self.domain,
            api_key=self.api_key,
            character_id=self.stitch_character_id,
            duration=self.stitch_duration,
            use_frame_range=self.stitch_use_frame_range,
        )

    def create_stitch_motion_ids_request(self) -> StitchMotionIdsRequest:
        """Create a StitchMotionIdsRequest from current UI state."""
        return StitchMotionIdsRequest(
            domain=self.domain,
            api_key=self.api_key,
            character_id=self.stitch_ids_character_id,
            leading_motion_id=self.stitch_ids_leading_motion_id,
            trailing_motion_id=self.stitch_ids_trailing_motion_id,
            duration=self.stitch_ids_duration,
        )


# Classes to register
classes = (
    MotionListItem,
    CharacterListItem,
    UthanaProperties,
)
