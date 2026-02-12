"""Blender panel classes for Uthana plugin."""

import bpy

from .. import config, utils
from ..logger import logger


class UTHANA_PT_main(bpy.types.Panel):
    """Main Uthana panel in 3D viewport sidebar."""

    bl_idname = "UTHANA_PT_main"
    bl_label = "Uthana"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Uthana"

    def draw(self, context):
        layout = self.layout

        if not hasattr(context.scene, "uthana_props"):
            layout.label(text="Properties not initialized")
            return

        props = context.scene.uthana_props

        # Schedule safe config sync using timer
        if not config.should_save_config():
            bpy.app.timers.register(config.safe_sync_to_ui, first_interval=0.1)

        # Auth status indicator
        if props.api_key:
            row = layout.row()
            if props.user_name:
                row.label(text=f"Connected: {props.user_name}", icon="CHECKMARK")
            else:
                row.label(text="API Key set", icon="KEY_HLT")
                row.operator("uthana.test_connection", text="Test", icon="URL")
        else:
            box = layout.box()
            box.label(text="Not authenticated", icon="ERROR")
            box.label(text="Set API Key in Config section")


class UTHANA_PT_config(bpy.types.Panel):
    """Configuration subpanel."""

    bl_idname = "UTHANA_PT_config"
    bl_label = "Config"
    bl_parent_id = "UTHANA_PT_main"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_options = {"DEFAULT_CLOSED"}

    def draw(self, context):
        layout = self.layout
        props = context.scene.uthana_props

        col = layout.column(align=True)
        col.label(text="API Key:")
        col.prop(props, "api_key", text="")
        col.separator()
        col.label(text="Domain:")
        col.prop(props, "domain", text="")

        col.separator()
        row = col.row(align=True)
        row.operator("uthana.test_connection", text="Test", icon="URL")
        row.operator("uthana.save_config", text="Save", icon="FILE_TICK")
        row.operator("uthana.load_config", text="Load", icon="FILE_REFRESH")


class UTHANA_PT_account(bpy.types.Panel):
    """Account info subpanel."""

    bl_idname = "UTHANA_PT_account"
    bl_label = "Account"
    bl_parent_id = "UTHANA_PT_main"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_options = {"DEFAULT_CLOSED"}

    def draw(self, context):
        layout = self.layout
        props = context.scene.uthana_props

        if not props.api_key:
            layout.label(text="Set API Key first", icon="INFO")
            return

        col = layout.column()
        if props.user_name:
            col.label(text=f"User: {props.user_name}")
        if props.org_name:
            col.label(text=f"Organization: {props.org_name}")
        if props.download_secs_remaining > 0:
            col.label(text=f"Download quota: {props.download_secs_remaining:.1f}s remaining")

        col.separator()
        col.operator("uthana.test_connection", text="Refresh", icon="FILE_REFRESH")


class UTHANA_PT_motions(bpy.types.Panel):
    """Motions browser subpanel."""

    bl_idname = "UTHANA_PT_motions"
    bl_label = "Motions"
    bl_parent_id = "UTHANA_PT_main"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"

    def draw(self, context):
        layout = self.layout
        props = context.scene.uthana_props

        if not props.api_key:
            layout.label(text="Set API Key first", icon="INFO")
            return

        # Motion list with refresh button
        row = layout.row()
        row.template_list(
            "UTHANA_UL_motions",
            "",
            props,
            "motions",
            props,
            "motion_index",
            rows=5,
        )

        # Actions column
        col = row.column(align=True)
        col.operator("uthana.refresh_assets", text="", icon="FILE_REFRESH").asset_type = "MOTIONS"
        col.separator()
        col.operator("uthana.load_selected_motion", text="", icon="IMPORT")
        col.operator("uthana.toggle_motion_favorite", text="", icon="SOLO_ON")
        col.operator("uthana.rename_motion", text="", icon="OUTLINER_DATA_FONT")
        col.separator()
        col.operator("uthana.copy_motion_id", text="", icon="COPYDOWN")
        col.operator("uthana.delete_motion", text="", icon="TRASH")

        # Selected motion info
        if props.motions and 0 <= props.motion_index < len(props.motions):
            selected = props.motions[props.motion_index]
            box = layout.box()
            row = box.row()
            row.label(text=f"ID: {selected.id}")
            if selected.is_favorite:
                row.label(text="", icon="SOLO_ON")
            if selected.created:
                box.label(text=f"Created: {selected.created}")


class UTHANA_PT_favorites(bpy.types.Panel):
    """Favorite motions subpanel."""

    bl_idname = "UTHANA_PT_favorites"
    bl_label = "Favorites"
    bl_parent_id = "UTHANA_PT_main"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_options = {"DEFAULT_CLOSED"}

    def draw(self, context):
        layout = self.layout
        props = context.scene.uthana_props

        if not props.api_key:
            layout.label(text="Set API Key first", icon="INFO")
            return

        # Count favorites
        favorites = [m for m in props.motions if m.is_favorite]

        if not favorites:
            layout.label(text="No favorite motions", icon="INFO")
            layout.label(text="Use the star icon to add favorites")
            return

        # Show favorites in a list
        for i, motion in enumerate(props.motions):
            if not motion.is_favorite:
                continue

            box = layout.box()
            row = box.row(align=True)
            row.label(text=motion.name, icon="SOLO_ON")

            # Find the actual index in the motions list
            actual_idx = -1
            for j, m in enumerate(props.motions):
                if m.id == motion.id:
                    actual_idx = j
                    break

            # Action buttons
            sub = row.row(align=True)
            sub.scale_x = 0.8
            op = sub.operator("uthana.load_selected_motion", text="", icon="IMPORT")
            # Set the motion index before loading
            op_unfav = sub.operator("uthana.toggle_motion_favorite", text="", icon="X")
            op_unfav.motion_index = actual_idx

        layout.separator()
        layout.label(text=f"{len(favorites)} favorite(s)")


class UTHANA_PT_characters(bpy.types.Panel):
    """Characters browser subpanel."""

    bl_idname = "UTHANA_PT_characters"
    bl_label = "Characters"
    bl_parent_id = "UTHANA_PT_main"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_options = {"DEFAULT_CLOSED"}

    def draw(self, context):
        layout = self.layout
        props = context.scene.uthana_props

        if not props.api_key:
            layout.label(text="Set API Key first", icon="INFO")
            return

        # Character list with refresh button
        row = layout.row()
        row.template_list(
            "UTHANA_UL_characters",
            "",
            props,
            "characters",
            props,
            "character_index",
            rows=4,
        )

        # Actions column
        col = row.column(align=True)
        col.operator(
            "uthana.refresh_assets", text="", icon="FILE_REFRESH"
        ).asset_type = "CHARACTERS"
        col.separator()
        col.operator("uthana.download_character", text="", icon="IMPORT")

        # Selected character info
        if props.characters and 0 <= props.character_index < len(props.characters):
            selected = props.characters[props.character_index]
            box = layout.box()
            box.label(text=f"ID: {selected.id}")
            if selected.created:
                box.label(text=f"Created: {selected.created}")

            # Buttons for selected character
            row = box.row(align=True)
            row.operator(
                "uthana.use_selected_character", text="Use for Generation", icon="CHECKMARK"
            )
            row.operator("uthana.download_character", text="Import", icon="IMPORT")


class UTHANA_PT_text_to_motion(bpy.types.Panel):
    """Text to Motion subpanel."""

    bl_idname = "UTHANA_PT_text_to_motion"
    bl_label = "Text to Motion"
    bl_parent_id = "UTHANA_PT_main"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"

    def draw(self, context):
        layout = self.layout
        props = context.scene.uthana_props

        col = layout.column(align=True)
        col.prop(props, "prompt")
        col.prop(props, "character_id")
        col.operator("uthana.generate_motion", icon="MOD_WAVE")

        # Show result motion ID if available
        if props.generate_result_motion_id:
            col.separator()
            col.label(text="Result Motion ID:")
            col.prop(props, "generate_result_motion_id", text="")


class UTHANA_PT_text_to_motion_preview(bpy.types.Panel):
    """Preview panel for text-to-motion results."""

    bl_idname = "UTHANA_PT_text_to_motion_preview"
    bl_label = "Motion Preview"
    bl_parent_id = "UTHANA_PT_text_to_motion"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"

    @classmethod
    def poll(cls, context):
        """Only show when there's a pending motion from text-to-motion."""
        props = context.scene.uthana_props
        return props.pending_motion_id != "" and props.pending_motion_source == "text"

    def draw(self, context):
        layout = self.layout
        props = context.scene.uthana_props

        # Motion info
        box = layout.box()
        box.label(text=f"Motion: {props.pending_motion_name}", icon="ANIM")
        box.label(text=f"ID: {props.pending_motion_id}")

        layout.separator()

        # Animated preview display
        if props.preview_frames_loaded:
            preview_box = layout.box()
            preview_box.label(text="Preview Animation:", icon="FILE_MOVIE")

            # Display current frame
            frame_idx = props.preview_current_frame_idx
            img_name = f"preview_frame_{frame_idx}"

            if img_name in bpy.data.images:
                img = bpy.data.images[img_name]

                # Ensure preview exists and is up to date
                # (Images are already packed during extraction)
                img.preview_ensure()

                # Display using the image's preview
                col = preview_box.column(align=True)

                # Use template_icon with larger scale
                if img.preview and img.preview.icon_id:
                    col.template_icon(icon_value=img.preview.icon_id, scale=10.0)
                else:
                    # Fallback: show image info
                    col.label(text=f"Frame {frame_idx + 1}")
                    col.label(text=f"Resolution: {img.size[0]}x{img.size[1]}")

                # Frame counter
                row = preview_box.row()
                row.scale_y = 0.8
                row.label(text=f"Frame {frame_idx + 1}", icon="PLAY")
            else:
                preview_box.label(text="Loading frames...", icon="TIME")
        else:
            # No animated preview - show ffmpeg installation message
            preview_box = layout.box()
            preview_box.label(text="Animated preview requires ffmpeg", icon="INFO")
            preview_box.label(text="Install: brew install ffmpeg (macOS)")
            preview_box.label(text="Or use browser button below to view")

        layout.separator()

        # Warning about download cost
        warning_box = layout.box()
        warning_box.label(text="Downloading will charge your account", icon="INFO")
        if props.download_secs_remaining > 0:
            warning_box.label(text=f"Remaining quota: {props.download_secs_remaining:.1f}s")

        # Action buttons
        layout.separator()
        row = layout.row(align=True)
        row.scale_y = 2.0
        row.operator(
            "uthana.open_preview_browser", text="View Full Animation in Browser (FREE)", icon="PLAY"
        )

        layout.separator()
        row = layout.row(align=True)
        row.scale_y = 1.5
        row.operator(
            "uthana.download_pending_motion", text="Download & Import (Uses Quota)", icon="IMPORT"
        )

        row = layout.row(align=True)
        row.operator("uthana.cancel_pending_motion", text="Cancel", icon="CANCEL")


class UTHANA_PT_video_to_motion(bpy.types.Panel):
    """Video to Motion subpanel."""

    bl_idname = "UTHANA_PT_video_to_motion"
    bl_label = "Video to Motion"
    bl_parent_id = "UTHANA_PT_main"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_options = {"DEFAULT_CLOSED"}

    def draw(self, context):
        layout = self.layout
        props = context.scene.uthana_props

        col = layout.column(align=True)
        col.prop(props, "video_file_path")
        col.prop(props, "video_motion_name")

        # Show progress if job is running
        if props.video_job_id:
            box = col.box()
            box.label(text=f"Status: {props.video_job_status}")
            box.prop(props, "video_job_progress", text="Progress")
            box.label(text="Press ESC to cancel")
        else:
            col.operator("uthana.video_to_motion", icon="FILE_MOVIE")

        # Show result
        if props.video_result_motion_id:
            col.separator()
            col.label(text="Result Motion ID:")
            col.prop(props, "video_result_motion_id", text="")


class UTHANA_PT_video_to_motion_preview(bpy.types.Panel):
    """Preview panel for video-to-motion results."""

    bl_idname = "UTHANA_PT_video_to_motion_preview"
    bl_label = "Motion Preview"
    bl_parent_id = "UTHANA_PT_video_to_motion"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"

    @classmethod
    def poll(cls, context):
        """Only show when there's a pending motion from video-to-motion."""
        props = context.scene.uthana_props
        return props.pending_motion_id != "" and props.pending_motion_source == "video"

    def draw(self, context):
        layout = self.layout
        props = context.scene.uthana_props

        # Motion info
        box = layout.box()
        box.label(text=f"Motion: {props.pending_motion_name}", icon="ANIM")
        box.label(text=f"ID: {props.pending_motion_id}")

        layout.separator()

        # Animated preview display
        if props.preview_frames_loaded:
            preview_box = layout.box()
            preview_box.label(text="Preview Animation:", icon="FILE_MOVIE")

            # Display current frame
            frame_idx = props.preview_current_frame_idx
            img_name = f"preview_frame_{frame_idx}"

            if img_name in bpy.data.images:
                img = bpy.data.images[img_name]

                # Ensure preview exists and is up to date
                # (Images are already packed during extraction)
                img.preview_ensure()

                # Display using the image's preview
                col = preview_box.column(align=True)

                # Use template_icon with larger scale
                if img.preview and img.preview.icon_id:
                    col.template_icon(icon_value=img.preview.icon_id, scale=10.0)
                else:
                    # Fallback: show image info
                    col.label(text=f"Frame {frame_idx + 1}")
                    col.label(text=f"Resolution: {img.size[0]}x{img.size[1]}")

                # Frame counter
                row = preview_box.row()
                row.scale_y = 0.8
                row.label(text=f"Frame {frame_idx + 1}", icon="PLAY")
            else:
                preview_box.label(text="Loading frames...", icon="TIME")
        else:
            # No animated preview - show ffmpeg installation message
            preview_box = layout.box()
            preview_box.label(text="Animated preview requires ffmpeg", icon="INFO")
            preview_box.label(text="Install: brew install ffmpeg (macOS)")
            preview_box.label(text="Or use browser button below to view")

        layout.separator()

        # Warning about download cost
        warning_box = layout.box()
        warning_box.label(text="Downloading will charge your account", icon="INFO")
        if props.download_secs_remaining > 0:
            warning_box.label(text=f"Remaining quota: {props.download_secs_remaining:.1f}s")

        # Action buttons
        layout.separator()
        row = layout.row(align=True)
        row.scale_y = 2.0
        row.operator(
            "uthana.open_preview_browser", text="View Full Animation in Browser (FREE)", icon="PLAY"
        )

        layout.separator()
        row = layout.row(align=True)
        row.scale_y = 1.5
        row.operator(
            "uthana.download_pending_motion", text="Download & Import (Uses Quota)", icon="IMPORT"
        )

        row = layout.row(align=True)
        row.operator("uthana.cancel_pending_motion", text="Cancel", icon="CANCEL")


class UTHANA_PT_character_upload(bpy.types.Panel):
    """Character Upload subpanel."""

    bl_idname = "UTHANA_PT_character_upload"
    bl_label = "Character Upload"
    bl_parent_id = "UTHANA_PT_main"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_options = {"DEFAULT_CLOSED"}

    def draw(self, context):
        layout = self.layout
        props = context.scene.uthana_props

        col = layout.column(align=True)
        col.prop(props, "character_file_path")
        col.prop(props, "character_upload_name")
        col.prop(props, "character_auto_rig")
        col.prop(props, "character_auto_import")

        if props.character_upload_status:
            box = col.box()
            box.label(text=f"Status: {props.character_upload_status}")
        else:
            col.operator("uthana.character_upload", icon="ARMATURE_DATA")


class UTHANA_PT_load_motion(bpy.types.Panel):
    """Load Motion subpanel."""

    bl_idname = "UTHANA_PT_load_motion"
    bl_label = "Load Motion"
    bl_parent_id = "UTHANA_PT_main"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_options = {"DEFAULT_CLOSED"}

    def draw(self, context):
        layout = self.layout
        props = context.scene.uthana_props

        col = layout.column(align=True)
        col.prop(props, "load_motion_id")
        col.prop(props, "load_character_id")
        col.operator("uthana.load_motion")

        if props.load_result_motion_id:
            col.separator()
            col.label(text="Loaded Motion ID:")
            col.prop(props, "load_result_motion_id", text="")


class UTHANA_PT_bake(bpy.types.Panel):
    """Bake Motion subpanel."""

    bl_idname = "UTHANA_PT_bake"
    bl_label = "Bake Motion"
    bl_parent_id = "UTHANA_PT_main"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_options = {"DEFAULT_CLOSED"}

    def draw(self, context):
        layout = self.layout
        props = context.scene.uthana_props

        col = layout.column(align=True)
        col.label(text="Character ID:")
        col.prop(props, "bake_character_id", text="")
        col.separator()

        col.prop(props, "bake_use_frame_range")

        # Show frame range info
        if props.bake_use_frame_range:
            frame_start = context.scene.frame_start
            frame_end = context.scene.frame_end
            col.label(text=f"Frame Range: {frame_start}-{frame_end}", icon="TIME")

        col.separator()

        # Show selected armature info
        active_obj = context.view_layer.objects.active
        if active_obj and active_obj.type == "ARMATURE":
            col.label(text=f"Selected: {active_obj.name}", icon="ARMATURE_DATA")
        else:
            col.label(text="Select armature to bake", icon="INFO")

        col.separator()
        col.operator("uthana.bake_motion", text="Bake", icon="MOD_SOLIDIFY")

        if props.bake_result_motion_id:
            col.separator()
            col.label(text="Result Motion ID:", icon="CHECKMARK")
            col.prop(props, "bake_result_motion_id", text="")


class UTHANA_PT_stitch_armatures(bpy.types.Panel):
    """Stitch Armatures subpanel."""

    bl_idname = "UTHANA_PT_stitch_armatures"
    bl_label = "Stitch Armatures"
    bl_parent_id = "UTHANA_PT_main"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_options = {"DEFAULT_CLOSED"}

    def draw(self, context):
        layout = self.layout
        props = context.scene.uthana_props

        col = layout.column(align=True)
        col.label(text="Character ID:")
        col.prop(props, "stitch_character_id", text="")

        col.separator()
        col.label(text="Duration (seconds):")
        col.prop(props, "stitch_duration", text="")

        col.separator()
        col.prop(props, "stitch_use_frame_range")

        if props.stitch_use_frame_range:
            frame_start = context.scene.frame_start
            frame_end = context.scene.frame_end
            col.label(text=f"Frame Range: {frame_start}-{frame_end}", icon="TIME")

        col.separator()

        # Show armature status
        selected_but_not_active = utils.get_selected_but_not_active_armatures()
        active_armature = context.view_layer.objects.active

        if len(selected_but_not_active) == 1:
            col.label(text=f"Leading: {selected_but_not_active[0].name}", icon="ARMATURE_DATA")
        elif len(selected_but_not_active) > 1:
            col.label(
                text=f"Leading: {len(selected_but_not_active)} selected (need 1)",
                icon="ERROR",
            )
        else:
            col.label(text="Leading: No armature selected", icon="INFO")

        if active_armature and active_armature.type == "ARMATURE":
            col.label(text=f"Trailing: {active_armature.name}", icon="ARMATURE_DATA")
        else:
            col.label(text="Trailing: No active armature", icon="INFO")

        if (
            len(selected_but_not_active) == 1
            and active_armature
            and active_armature.type == "ARMATURE"
        ):
            col.label(text="Ready to stitch!", icon="CHECKMARK")
        else:
            col.label(text="Select 1 armature, make another active", icon="INFO")

        col.separator()
        col.operator("uthana.stitch_armatures", text="Stitch Armatures", icon="LINKED")

        if props.stitch_result_motion_id:
            col.separator()
            col.label(text="Result Motion ID:", icon="CHECKMARK")
            col.prop(props, "stitch_result_motion_id", text="")


class UTHANA_PT_stitch_motion_ids(bpy.types.Panel):
    """Stitch Motion IDs subpanel."""

    bl_idname = "UTHANA_PT_stitch_motion_ids"
    bl_label = "Stitch Motion IDs"
    bl_parent_id = "UTHANA_PT_main"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_options = {"DEFAULT_CLOSED"}

    def draw(self, context):
        layout = self.layout
        props = context.scene.uthana_props

        col = layout.column(align=True)
        col.label(text="Character ID:")
        col.prop(props, "stitch_ids_character_id", text="")

        col.separator()
        col.label(text="Leading Motion ID:")
        leading_row = col.row(align=True)
        leading_row.prop(props, "stitch_ids_leading_motion_id", text="")
        leading_row.operator("uthana.paste_motion_id", text="", icon="PASTEDOWN").target = "leading"

        col.separator()
        col.label(text="Trailing Motion ID:")
        trailing_row = col.row(align=True)
        trailing_row.prop(props, "stitch_ids_trailing_motion_id", text="")
        trailing_row.operator(
            "uthana.paste_motion_id", text="", icon="PASTEDOWN"
        ).target = "trailing"

        col.separator()
        col.label(text="Duration (seconds):")
        col.prop(props, "stitch_ids_duration", text="")

        col.separator()

        # Status validation
        ready = (
            props.stitch_ids_leading_motion_id.strip()
            and props.stitch_ids_trailing_motion_id.strip()
            and props.stitch_ids_character_id.strip()
        )

        if ready:
            col.label(text="Ready to stitch!", icon="CHECKMARK")
        else:
            col.label(text="Enter both Motion IDs", icon="INFO")

        col.separator()
        col.operator("uthana.stitch_motion_ids", text="Stitch Motion IDs", icon="LINKED")

        if props.stitch_ids_result_motion_id:
            col.separator()
            col.label(text="Result Motion ID:", icon="CHECKMARK")
            col.prop(props, "stitch_ids_result_motion_id", text="")


# Classes to register
classes = (
    UTHANA_PT_main,
    UTHANA_PT_config,
    UTHANA_PT_account,
    UTHANA_PT_motions,
    UTHANA_PT_favorites,
    UTHANA_PT_characters,
    UTHANA_PT_text_to_motion,
    UTHANA_PT_text_to_motion_preview,
    UTHANA_PT_video_to_motion,
    UTHANA_PT_video_to_motion_preview,
    UTHANA_PT_character_upload,
    # Deprecated panels - kept for future reference
    # UTHANA_PT_load_motion,
    # UTHANA_PT_bake,
    # UTHANA_PT_stitch_armatures,
    # UTHANA_PT_stitch_motion_ids,
)


def register():
    """Register panels."""
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    """Unregister panels."""
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
