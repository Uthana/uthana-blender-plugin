"""Blender operators for Uthana plugin."""

import bpy

from .. import client, config, motion
from ..logger import logger


class UTHANA_OT_generate_motion(bpy.types.Operator):
    """Generate motion from text prompt."""

    bl_idname = "uthana.generate_motion"
    bl_label = "Generate"
    bl_description = "Generate motion from text prompt"

    def execute(self, context):
        from .. import client

        props = context.scene.uthana_props
        request = props.create_generate_motion_request()

        # Create motion via API (don't download yet)
        motion_request = motion.MotionRequest(
            domain=request.domain,
            api_key=request.api_key,
            character_id=request.character_id,
            prompt=request.prompt,
        )

        api_result = client.create_text_to_motion(motion_request)

        if not api_result.success:
            self.report({"ERROR"}, api_result.message)
            return {"CANCELLED"}

        motion_id = api_result.data.get("motion_id")
        motion_data = api_result.data.get("motion", {})
        motion_name = motion_data.get("name", "Generated Motion")

        if not motion_id:
            self.report({"ERROR"}, "No motion ID returned")
            return {"CANCELLED"}

        # Store pending motion for preview
        props.pending_motion_id = motion_id
        props.pending_motion_name = motion_name
        props.pending_character_id = request.character_id
        props.pending_motion_source = "text"
        props.generate_result_motion_id = motion_id

        # Reset preview state
        props.preview_frames_loaded = False
        props.preview_current_frame_idx = 0
        props.pending_preview_video_path = ""

        self.report({"INFO"}, f"Motion '{motion_name}' generated! Check preview in sidebar.")

        # Auto-start preview animation
        bpy.ops.uthana.play_motion_preview("INVOKE_DEFAULT")

        return {"FINISHED"}


class UTHANA_OT_load_motion(bpy.types.Operator):
    """Load motion from server by Motion ID."""

    bl_idname = "uthana.load_motion"
    bl_label = "Load Motion"
    bl_description = "Load motion from server using Motion ID"

    def execute(self, context):
        props = context.scene.uthana_props
        request = props.create_load_motion_request()

        # Validate inputs
        if not request.motion_id.strip():
            self.report({"ERROR"}, "Motion ID is required")
            return {"CANCELLED"}

        if not request.character_id.strip():
            self.report({"ERROR"}, "Character ID is required")
            return {"CANCELLED"}

        if not request.domain.strip():
            self.report({"ERROR"}, "Domain is required")
            return {"CANCELLED"}

        if not request.api_key.strip():
            self.report({"ERROR"}, "API Key is required")
            return {"CANCELLED"}

        result = motion.load_motion(request)

        if result.success:
            props.load_result_motion_id = request.motion_id
            self.report({"INFO"}, result.message)
            return {"FINISHED"}
        else:
            self.report({"ERROR"}, result.message)
            return {"CANCELLED"}


class UTHANA_OT_bake_motion(bpy.types.Operator):
    """Bake animation to GLTF and upload to Uthana."""

    bl_idname = "uthana.bake_motion"
    bl_label = "Bake"
    bl_description = "Bake animation to GLTF file and upload to Uthana"

    def execute(self, context):
        props = context.scene.uthana_props
        request = props.create_bake_request()
        result = motion.bake_and_upload_motion(request)

        if result.success:
            if result.data and "motion_id" in result.data:
                props.bake_result_motion_id = result.data["motion_id"]
            self.report({"INFO"}, result.message)
            return {"FINISHED"}
        else:
            self.report({"ERROR"}, result.message)
            return {"CANCELLED"}


class UTHANA_OT_save_config(bpy.types.Operator):
    """Save current configuration to file."""

    bl_idname = "uthana.save_config"
    bl_label = "Save"
    bl_description = "Save current configuration to file"

    def execute(self, context):
        result = config.auto_save_config(context.scene)
        if result.success:
            self.report({"INFO"}, "Configuration saved successfully")
            return {"FINISHED"}
        else:
            self.report({"ERROR"}, f"Failed to save configuration: {result.message}")
            return {"CANCELLED"}


class UTHANA_OT_load_config(bpy.types.Operator):
    """Load configuration from file."""

    bl_idname = "uthana.load_config"
    bl_label = "Load"
    bl_description = "Load configuration from file"

    def execute(self, context):
        try:
            loaded_config = config.load_config()
            config.sync_config_to_ui(loaded_config, context.scene)
            self.report({"INFO"}, "Configuration loaded successfully")
            return {"FINISHED"}
        except Exception as e:
            self.report({"ERROR"}, f"Failed to load configuration: {str(e)}")
            return {"CANCELLED"}


class UTHANA_OT_load_default_config(bpy.types.Operator):
    """Load default configuration."""

    bl_idname = "uthana.load_default_config"
    bl_label = "Default"
    bl_description = "Load default configuration settings"

    def execute(self, context):
        try:
            default_config = config.get_default_config()
            config.sync_config_to_ui(default_config, context.scene)
            self.report({"INFO"}, "Default configuration loaded")
            return {"FINISHED"}
        except Exception as e:
            self.report({"ERROR"}, f"Failed to load default configuration: {str(e)}")
            return {"CANCELLED"}


class UTHANA_OT_stitch_armatures(bpy.types.Operator):
    """Stitch two armatures together."""

    bl_idname = "uthana.stitch_armatures"
    bl_label = "Stitch Armatures"
    bl_description = "Stitch two armatures together with transition"

    def execute(self, context):
        props = context.scene.uthana_props

        try:
            request = props.create_stitch_motions_request()
            result = motion.stitch_motions(request)

            if result.success:
                motion_id = result.data.get("stitched_motion_id")
                if motion_id:
                    props.stitch_result_motion_id = motion_id
                self.report({"INFO"}, result.message)
                return {"FINISHED"}
            else:
                self.report({"ERROR"}, result.message)
                return {"CANCELLED"}

        except Exception as e:
            self.report({"ERROR"}, f"Stitching failed: {str(e)}")
            return {"CANCELLED"}


class UTHANA_OT_stitch_motion_ids(bpy.types.Operator):
    """Stitch two motion IDs together."""

    bl_idname = "uthana.stitch_motion_ids"
    bl_label = "Stitch Motion IDs"
    bl_description = "Stitch two motion IDs together with transition"

    def execute(self, context):
        props = context.scene.uthana_props

        try:
            request = props.create_stitch_motion_ids_request()
            result = motion.stitch_motion_ids(request)

            if result.success:
                motion_id = result.data.get("stitched_motion_id")
                if motion_id:
                    props.stitch_ids_result_motion_id = motion_id
                self.report(
                    {"INFO"},
                    f"Motion stitched successfully! Motion ID: {result.data.get('stitched_motion_id')}",
                )
                return {"FINISHED"}
            else:
                self.report({"ERROR"}, f"Motion stitching failed: {result.message}")
                return {"CANCELLED"}

        except Exception as e:
            self.report({"ERROR"}, f"Motion stitching failed: {str(e)}")
            return {"CANCELLED"}


class UTHANA_OT_paste_motion_id(bpy.types.Operator):
    """Paste motion ID from clipboard."""

    bl_idname = "uthana.paste_motion_id"
    bl_label = "Paste Motion ID"
    bl_description = "Paste motion ID from clipboard"

    target: bpy.props.StringProperty(
        name="Target", description="Target field to paste into", default="leading"
    )

    def execute(self, context):
        try:
            clipboard_text = bpy.context.window_manager.clipboard.strip()

            if not clipboard_text:
                self.report({"WARNING"}, "Clipboard is empty")
                return {"CANCELLED"}

            props = context.scene.uthana_props

            if self.target == "leading":
                props.stitch_ids_leading_motion_id = clipboard_text
                self.report({"INFO"}, f"Pasted leading motion ID: {clipboard_text}")
            elif self.target == "trailing":
                props.stitch_ids_trailing_motion_id = clipboard_text
                self.report({"INFO"}, f"Pasted trailing motion ID: {clipboard_text}")
            else:
                self.report({"ERROR"}, f"Unknown target: {self.target}")
                return {"CANCELLED"}

            return {"FINISHED"}

        except Exception as e:
            self.report({"ERROR"}, f"Failed to paste motion ID: {str(e)}")
            return {"CANCELLED"}


class UTHANA_OT_refresh_assets(bpy.types.Operator):
    """Refresh motion and character lists from server."""

    bl_idname = "uthana.refresh_assets"
    bl_label = "Refresh"
    bl_description = "Refresh asset lists from server"

    asset_type: bpy.props.EnumProperty(
        items=[
            ("MOTIONS", "Motions", "Refresh motions list"),
            ("CHARACTERS", "Characters", "Refresh characters list"),
            ("ALL", "All", "Refresh all assets"),
        ],
        default="ALL",
    )

    def execute(self, context):
        from .. import assets

        props = context.scene.uthana_props

        if not props.api_key:
            self.report({"ERROR"}, "API Key is required")
            return {"CANCELLED"}

        manager = assets.AssetManager.instance()

        if self.asset_type in ("MOTIONS", "ALL"):
            result = manager.refresh_motions(props.api_key, props.domain, force=True)
            if result.success:
                self._sync_motions_to_ui(props, manager.get_motions())
            else:
                self.report({"ERROR"}, f"Failed to refresh motions: {result.message}")
                return {"CANCELLED"}

        if self.asset_type in ("CHARACTERS", "ALL"):
            result = manager.refresh_characters(props.api_key, props.domain, force=True)
            if result.success:
                self._sync_characters_to_ui(props, manager.get_characters())
            else:
                self.report({"ERROR"}, f"Failed to refresh characters: {result.message}")
                return {"CANCELLED"}

        self.report({"INFO"}, "Assets refreshed successfully")
        return {"FINISHED"}

    def _sync_motions_to_ui(self, props, motions):
        """Sync motion list to UI collection."""
        props.motions.clear()
        for m in motions:
            item = props.motions.add()
            item.id = m.id
            item.name = m.name
            item.created = m.created
            item.is_favorite = m.is_favorite

    def _sync_characters_to_ui(self, props, characters):
        """Sync character list to UI collection."""
        props.characters.clear()
        for c in characters:
            item = props.characters.add()
            item.id = c.id
            item.name = c.name
            item.created = c.created


class UTHANA_OT_load_selected_motion(bpy.types.Operator):
    """Load the selected motion from the list."""

    bl_idname = "uthana.load_selected_motion"
    bl_label = "Load Selected"
    bl_description = "Load the selected motion from the list"

    def execute(self, context):
        props = context.scene.uthana_props

        if not props.motions or props.motion_index < 0:
            self.report({"ERROR"}, "No motion selected")
            return {"CANCELLED"}

        if props.motion_index >= len(props.motions):
            self.report({"ERROR"}, "Invalid motion selection")
            return {"CANCELLED"}

        selected_motion = props.motions[props.motion_index]

        # Use the selected character or default
        character_id = props.character_id if props.character_id else "cXi2eAP19XwQ"

        result = motion.download_and_import_motion(
            props.domain, props.api_key, character_id, selected_motion.id
        )

        if result.success:
            self.report({"INFO"}, f"Loaded motion: {selected_motion.name}")
            return {"FINISHED"}
        else:
            self.report({"ERROR"}, f"Failed to load motion: {result.message}")
            return {"CANCELLED"}


class UTHANA_OT_test_connection(bpy.types.Operator):
    """Test API connection with current credentials."""

    bl_idname = "uthana.test_connection"
    bl_label = "Test Connection"
    bl_description = "Test API connection with current API key"

    def execute(self, context):
        from .. import client

        props = context.scene.uthana_props

        if not props.api_key:
            self.report({"ERROR"}, "API Key is required")
            return {"CANCELLED"}

        result = client.get_user_info(props.api_key, props.domain)

        if result.success:
            user_data = result.data.get("user", {})
            props.user_name = user_data.get("name", "Unknown")
            self.report({"INFO"}, f"Connected as: {props.user_name}")

            # Also fetch org info
            org_result = client.get_org_info(props.api_key, props.domain)
            if org_result.success:
                org_data = org_result.data.get("org", {})
                props.org_name = org_data.get("name", "")
                props.download_secs_remaining = org_data.get(
                    "motion_download_secs_per_month_remaining", 0
                )

            return {"FINISHED"}
        else:
            self.report({"ERROR"}, f"Connection failed: {result.message}")
            return {"CANCELLED"}


class UTHANA_OT_rename_motion(bpy.types.Operator):
    """Rename the selected motion."""

    bl_idname = "uthana.rename_motion"
    bl_label = "Rename Motion"
    bl_description = "Rename the selected motion"

    new_name: bpy.props.StringProperty(
        name="New Name",
        description="New name for the motion",
        default="",
    )

    def invoke(self, context, event):
        props = context.scene.uthana_props

        if not props.motions or props.motion_index < 0:
            self.report({"ERROR"}, "No motion selected")
            return {"CANCELLED"}

        if props.motion_index >= len(props.motions):
            self.report({"ERROR"}, "Invalid motion selection")
            return {"CANCELLED"}

        # Pre-populate with current name
        selected_motion = props.motions[props.motion_index]
        self.new_name = selected_motion.name

        return context.window_manager.invoke_props_dialog(self)

    def execute(self, context):
        from .. import assets, client

        props = context.scene.uthana_props

        if not props.api_key:
            self.report({"ERROR"}, "API Key is required")
            return {"CANCELLED"}

        if not self.new_name.strip():
            self.report({"ERROR"}, "Name cannot be empty")
            return {"CANCELLED"}

        selected_motion = props.motions[props.motion_index]
        result = client.rename_motion(
            props.api_key, props.domain, selected_motion.id, self.new_name.strip()
        )

        if result.success:
            # Update local data
            selected_motion.name = self.new_name.strip()
            self.report({"INFO"}, f"Motion renamed to '{self.new_name}'")

            # Refresh cache
            manager = assets.AssetManager.instance()
            manager.refresh_motions(props.api_key, props.domain, force=True)

            return {"FINISHED"}
        else:
            self.report({"ERROR"}, f"Failed to rename: {result.message}")
            return {"CANCELLED"}


class UTHANA_OT_toggle_motion_favorite(bpy.types.Operator):
    """Toggle favorite status for the selected motion."""

    bl_idname = "uthana.toggle_motion_favorite"
    bl_label = "Toggle Favorite"
    bl_description = "Toggle favorite status for the selected motion"

    motion_index: bpy.props.IntProperty(default=-1)

    def execute(self, context):
        from .. import assets, client

        props = context.scene.uthana_props

        if not props.api_key:
            self.report({"ERROR"}, "API Key is required")
            return {"CANCELLED"}

        # Use provided index or current selection
        idx = self.motion_index if self.motion_index >= 0 else props.motion_index

        if not props.motions or idx < 0 or idx >= len(props.motions):
            self.report({"ERROR"}, "No valid motion selected")
            return {"CANCELLED"}

        selected_motion = props.motions[idx]
        new_favorite_state = not selected_motion.is_favorite

        result = client.set_motion_favorite(
            props.api_key, props.domain, selected_motion.id, new_favorite_state
        )

        if result.success:
            # Update local data
            selected_motion.is_favorite = new_favorite_state
            action = "added to" if new_favorite_state else "removed from"
            self.report({"INFO"}, f"Motion {action} favorites")

            # Refresh cache
            manager = assets.AssetManager.instance()
            manager.refresh_motions(props.api_key, props.domain, force=True)

            return {"FINISHED"}
        else:
            self.report({"ERROR"}, f"Failed to update favorite: {result.message}")
            return {"CANCELLED"}


class UTHANA_OT_copy_motion_id(bpy.types.Operator):
    """Copy the selected motion's ID to clipboard."""

    bl_idname = "uthana.copy_motion_id"
    bl_label = "Copy Motion ID"
    bl_description = "Copy the selected motion's ID to clipboard"

    def execute(self, context):
        props = context.scene.uthana_props

        if not props.motions or props.motion_index < 0:
            self.report({"ERROR"}, "No motion selected")
            return {"CANCELLED"}

        if props.motion_index >= len(props.motions):
            self.report({"ERROR"}, "Invalid motion selection")
            return {"CANCELLED"}

        selected_motion = props.motions[props.motion_index]
        context.window_manager.clipboard = selected_motion.id
        self.report({"INFO"}, f"Copied motion ID: {selected_motion.id}")
        return {"FINISHED"}


class UTHANA_OT_delete_motion(bpy.types.Operator):
    """Delete the selected motion."""

    bl_idname = "uthana.delete_motion"
    bl_label = "Delete Motion"
    bl_description = "Delete the selected motion (moves to trash)"
    bl_options = {"REGISTER", "UNDO"}

    def invoke(self, context, event):
        return context.window_manager.invoke_confirm(self, event)

    def execute(self, context):
        from .. import assets, client

        props = context.scene.uthana_props

        if not props.api_key:
            self.report({"ERROR"}, "API Key is required")
            return {"CANCELLED"}

        if not props.motions or props.motion_index < 0:
            self.report({"ERROR"}, "No motion selected")
            return {"CANCELLED"}

        if props.motion_index >= len(props.motions):
            self.report({"ERROR"}, "Invalid motion selection")
            return {"CANCELLED"}

        selected_motion = props.motions[props.motion_index]
        result = client.delete_motion(props.api_key, props.domain, selected_motion.id)

        if result.success:
            self.report({"INFO"}, f"Motion '{selected_motion.name}' deleted")

            # Refresh list
            manager = assets.AssetManager.instance()
            result = manager.refresh_motions(props.api_key, props.domain, force=True)
            if result.success:
                self._sync_motions_to_ui(props, manager.get_motions())

            return {"FINISHED"}
        else:
            self.report({"ERROR"}, f"Failed to delete: {result.message}")
            return {"CANCELLED"}

    def _sync_motions_to_ui(self, props, motions):
        """Sync motion list to UI collection."""
        props.motions.clear()
        for m in motions:
            item = props.motions.add()
            item.id = m.id
            item.name = m.name
            item.created = m.created
            item.is_favorite = m.is_favorite


class UTHANA_OT_download_pending_motion(bpy.types.Operator):
    """Download and import the pending motion (charges download seconds)."""

    bl_idname = "uthana.download_pending_motion"
    bl_label = "Download & Import"
    bl_description = (
        "Download the motion and import into Blender (this will charge your download seconds)"
    )

    def execute(self, context):
        props = context.scene.uthana_props

        # Clear preview state to stop animation
        props.preview_frames_loaded = False
        props.preview_current_frame_idx = 0
        props.pending_preview_video_path = ""

        # Check if there's a pending motion
        if not props.pending_motion_id:
            self.report({"ERROR"}, "No pending motion to download")
            return {"CANCELLED"}

        # Get character ID
        character_id = props.pending_character_id or props.character_id

        if not character_id:
            self.report({"ERROR"}, "Character ID is required")
            return {"CANCELLED"}

        # Download and import
        result = motion.download_and_import_motion(
            props.domain, props.api_key, character_id, props.pending_motion_id
        )

        if result.success:
            self.report({"INFO"}, "Motion downloaded and imported successfully!")

            # Clear pending motion
            props.pending_motion_id = ""
            props.pending_motion_name = ""
            props.pending_character_id = ""
            props.pending_motion_source = ""
            props.pending_preview_image_path = ""

            return {"FINISHED"}
        else:
            self.report({"ERROR"}, f"Download failed: {result.message}")
            return {"CANCELLED"}


class UTHANA_OT_cancel_pending_motion(bpy.types.Operator):
    """Cancel the pending motion preview."""

    bl_idname = "uthana.cancel_pending_motion"
    bl_label = "Cancel"
    bl_description = "Cancel and don't download this motion"

    def execute(self, context):
        props = context.scene.uthana_props

        # Clear preview state to stop animation
        props.preview_frames_loaded = False
        props.preview_current_frame_idx = 0
        props.pending_preview_video_path = ""

        # Clear pending motion
        props.pending_motion_id = ""
        props.pending_motion_name = ""
        props.pending_character_id = ""
        props.pending_motion_source = ""
        props.pending_preview_image_path = ""

        self.report({"INFO"}, "Cancelled")
        return {"FINISHED"}


class UTHANA_OT_open_preview_browser(bpy.types.Operator):
    """Open motion preview animation in browser."""

    bl_idname = "uthana.open_preview_browser"
    bl_label = "View Preview"
    bl_description = "Open the motion preview animation in your web browser"

    def execute(self, context):
        from .. import utils

        props = context.scene.uthana_props

        # Check if there's a pending motion to preview
        if not props.pending_motion_id:
            self.report({"ERROR"}, "No motion available for preview")
            return {"CANCELLED"}

        # Build web viewer URL
        character_id = props.pending_character_id or props.character_id
        url = utils.build_web_viewer_url(props.domain, character_id, props.pending_motion_id)

        # Open in default browser
        import webbrowser

        webbrowser.open(url)

        self.report({"INFO"}, "Opening preview in browser...")
        return {"FINISHED"}


class UTHANA_OT_open_web_viewer(bpy.types.Operator):
    """Open motion in web browser for preview."""

    bl_idname = "uthana.open_web_viewer"
    bl_label = "View in Browser"
    bl_description = "Open the motion in your web browser (you need to be logged in)"

    def execute(self, context):
        from .. import utils

        props = context.scene.uthana_props

        # Check if there's a pending motion to preview
        if not props.pending_motion_id:
            self.report({"ERROR"}, "No motion available for preview")
            return {"CANCELLED"}

        # Build web viewer URL
        character_id = props.pending_character_id or props.character_id
        url = utils.build_web_viewer_url(props.domain, character_id, props.pending_motion_id)

        # Open in default browser
        import webbrowser

        webbrowser.open(url)

        self.report({"INFO"}, "Opening web viewer...")
        return {"FINISHED"}


class UTHANA_OT_show_motion_preview_popup(bpy.types.Operator):
    """Show motion preview in a popup dialog."""

    bl_idname = "uthana.show_motion_preview_popup"
    bl_label = "Motion Preview"
    bl_description = "Preview the generated motion before downloading"
    bl_options = {"REGISTER", "INTERNAL"}

    preview_video_path: bpy.props.StringProperty(default="")
    preview_video_format: bpy.props.StringProperty(default="")
    preview_download_failed: bpy.props.BoolProperty(default=False)
    preview_download_message: bpy.props.StringProperty(default="")

    def invoke(self, context, event):
        props = context.scene.uthana_props

        # Download preview animation (WebM)
        self.preview_download_failed = False
        self.preview_download_message = "Downloading preview..."

        result = client.download_preview_video(
            props.domain, props.pending_character_id, props.pending_motion_id, props.api_key
        )

        if result.success:
            self.preview_video_path = result.data.get("file_path", "")
            self.preview_video_format = result.data.get("format", "")
            logger.info(f"Preview downloaded: {self.preview_video_path}")

            # Load preview animation as Blender image (static first frame)
            try:
                # Check if image already exists
                img_name = f"preview_{props.pending_motion_id}"
                if img_name in bpy.data.images:
                    bpy.data.images.remove(bpy.data.images[img_name])

                # Load the preview (will show first frame only - stable approach)
                img = bpy.data.images.load(self.preview_video_path)
                img.name = img_name

                # Pack the image so it's accessible
                img.pack()

                logger.info(f"Preview image loaded: {img_name}")

            except Exception as e:
                logger.error(f"Failed to load preview as image: {e}")
                self.preview_download_failed = True
                self.preview_download_message = f"Preview loaded but display failed: {str(e)}"
        else:
            self.preview_download_failed = True
            self.preview_download_message = result.message
            logger.warning(f"Preview download failed: {result.message}")

        return context.window_manager.invoke_props_dialog(self, width=600)

    def draw(self, context):
        from ..logger import logger

        layout = self.layout
        props = context.scene.uthana_props

        # Motion info
        col = layout.column(align=True)
        col.label(text=f"Motion: {props.pending_motion_name}", icon="ANIM")
        col.label(text=f"ID: {props.pending_motion_id}")

        layout.separator()

        # Preview video display
        if self.preview_video_path and not self.preview_download_failed:
            box = layout.box()
            box.label(text="Preview Animation:", icon="FILE_MOVIE")

            # Display the preview animation
            img_name = f"preview_{props.pending_motion_id}"
            if img_name in bpy.data.images:
                img = bpy.data.images[img_name]

                # Display static preview image
                col = box.column(align=True)

                # Use template_preview for simple, stable image display
                try:
                    col.template_preview(img, show_buttons=False)
                except Exception as e:
                    # Fallback: just show dimensions
                    logger.warning(f"template_preview failed: {e}")
                    col.label(text=f"Preview: {img.size[0]}x{img.size[1]}px", icon="IMAGE_DATA")

                # Info about the preview
                row = box.row()
                row.scale_y = 0.8
                row.label(text="First frame - Full animation available in browser", icon="INFO")
        elif self.preview_download_failed:
            box = layout.box()
            box.label(text=self.preview_download_message, icon="ERROR")
            box.label(text="You can still view in browser or download directly", icon="INFO")

        layout.separator()

        # Warning about download cost
        box = layout.box()
        box.label(text="Downloading will charge your account", icon="INFO")
        if props.download_secs_remaining > 0:
            box.label(text=f"Remaining quota: {props.download_secs_remaining:.1f}s")

        layout.separator()

        # Buttons - emphasize browser preview for full animation
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

    def execute(self, context):
        """Clean up when popup is closed."""
        # Clean up preview image
        props = context.scene.uthana_props
        img_name = f"preview_{props.pending_motion_id}"
        if img_name in bpy.data.images:
            bpy.data.images.remove(bpy.data.images[img_name])

        return {"FINISHED"}


class UTHANA_OT_play_motion_preview(bpy.types.Operator):
    """Play animated motion preview using timer-based frame cycling."""

    bl_idname = "uthana.play_motion_preview"
    bl_label = "Play Motion Preview"
    bl_options = {"REGISTER", "INTERNAL"}

    _timer = None
    _frames = []
    _frame_durations = []
    _current_frame_idx: int = 0
    _time_elapsed: float = 0.0
    _cleanup_done: bool = False
    _active_generation: int = 0  # Class-level: tracks which invoke is current

    def modal(self, context, event):
        # Validate context is still valid
        if not self._validate_context(context):
            return self._safe_cleanup(context, error=True)

        # Check if superseded by a newer preview invocation
        if self._generation != UTHANA_OT_play_motion_preview._active_generation:
            return self._safe_cleanup(context, superseded=True)

        if event.type == "TIMER":
            props = context.scene.uthana_props

            # Check if cancelled externally
            if not props.pending_motion_id:
                return self._safe_cleanup(context)

            # Verify frames still exist
            if not self._frames or not all(self._frame_exists(f) for f in self._frames):
                logger.error("Preview frames were deleted")
                return self._safe_cleanup(context, error=True)

            # Advance frame based on timing
            frame_duration = self._frame_durations[self._current_frame_idx]
            self._time_elapsed += 0.033  # Timer interval

            if self._time_elapsed >= frame_duration:
                self._time_elapsed = 0.0
                self._current_frame_idx = (self._current_frame_idx + 1) % len(self._frames)
                props.preview_current_frame_idx = self._current_frame_idx

                # Ensure current frame's preview is generated
                try:
                    current_frame = self._frames[self._current_frame_idx]
                    if current_frame and current_frame.name in bpy.data.images:
                        # Force preview regeneration (images are already packed during extraction)
                        current_frame.preview_ensure()
                except Exception as e:
                    logger.warning(f"Failed to update frame preview: {e}")

                # Redraw safely
                self._safe_redraw(context)

        elif event.type == "ESC":
            return self._safe_cleanup(context)

        return {"PASS_THROUGH"}

    def _validate_context(self, context):
        """Check context is still valid."""
        try:
            return context.window and context.scene
        except (AttributeError, ReferenceError):
            return False

    def _frame_exists(self, frame):
        """Check if frame image still exists."""
        try:
            return frame and frame.name in bpy.data.images
        except (AttributeError, ReferenceError):
            return False

    def _safe_redraw(self, context):
        """Safely redraw UI."""
        try:
            if context.screen and context.screen.areas:
                for area in context.screen.areas:
                    if area.type == "VIEW_3D":
                        area.tag_redraw()
        except (AttributeError, ReferenceError):
            pass

    def _safe_cleanup(self, context, error=False, superseded=False):
        """Clean up with error handling."""
        if self._cleanup_done:
            return {"CANCELLED"}

        try:
            # Remove timer
            if self._timer and context and context.window_manager:
                context.window_manager.event_timer_remove(self._timer)
                self._timer = None

            # Only remove frames if not superseded — a newer instance owns
            # the frame names and would break if we deleted them
            if not superseded:
                for frame in self._frames:
                    try:
                        if self._frame_exists(frame):
                            bpy.data.images.remove(frame)
                    except Exception as e:
                        logger.warning(f"Failed to remove frame: {e}")

            self._frames.clear()
            self._cleanup_done = True

            # Clear properties only if not superseded (new instance sets its own)
            if not superseded and context and context.scene:
                props = context.scene.uthana_props
                props.preview_frames_loaded = False
                props.preview_current_frame_idx = 0

            if context:
                self._safe_redraw(context)

        except Exception as e:
            logger.error(f"Cleanup error: {e}")

        return {"CANCELLED"}

    def invoke(self, context, event):
        from .. import client, utils

        props = context.scene.uthana_props

        # Claim the active generation so any previous modal knows to exit
        UTHANA_OT_play_motion_preview._active_generation += 1
        self._generation = UTHANA_OT_play_motion_preview._active_generation

        # Reset state
        self._current_frame_idx = 0
        self._time_elapsed = 0.0
        self._cleanup_done = False

        # Download preview WebM if needed
        if not props.pending_preview_video_path:
            result = client.download_preview_video(
                props.domain, props.pending_character_id, props.pending_motion_id, props.api_key
            )

            if not result.success:
                self.report({"ERROR"}, f"Preview download failed: {result.message}")
                return {"CANCELLED"}

            props.pending_preview_video_path = result.data.get("file_path", "")

        # Extract frames using ffmpeg
        self._frames, self._frame_durations = utils.extract_animated_preview_frames(
            props.pending_preview_video_path
        )

        if not self._frames:
            # ffmpeg not available - animated preview cannot be extracted
            # User can still use the browser button to view the animation
            logger.warning("ffmpeg not found - animated preview unavailable")
            self.report(
                {"WARNING"},
                "ffmpeg not installed - install ffmpeg to enable animated preview, or use browser button",
            )
            props.preview_frames_loaded = False
            return {"CANCELLED"}

        # Mark as loaded
        props.preview_frames_loaded = True
        props.preview_current_frame_idx = 0

        # Start timer (30fps)
        wm = context.window_manager
        self._timer = wm.event_timer_add(0.033, window=context.window)
        wm.modal_handler_add(self)

        self.report({"INFO"}, f"Playing preview ({len(self._frames)} frames)")
        return {"RUNNING_MODAL"}


# Classes to register
classes = (
    UTHANA_OT_generate_motion,
    UTHANA_OT_load_motion,
    UTHANA_OT_bake_motion,
    UTHANA_OT_save_config,
    UTHANA_OT_load_config,
    UTHANA_OT_load_default_config,
    UTHANA_OT_stitch_armatures,
    UTHANA_OT_stitch_motion_ids,
    UTHANA_OT_paste_motion_id,
    UTHANA_OT_refresh_assets,
    UTHANA_OT_load_selected_motion,
    UTHANA_OT_test_connection,
    UTHANA_OT_rename_motion,
    UTHANA_OT_toggle_motion_favorite,
    UTHANA_OT_copy_motion_id,
    UTHANA_OT_delete_motion,
    UTHANA_OT_download_pending_motion,
    UTHANA_OT_cancel_pending_motion,
    UTHANA_OT_open_preview_browser,
    UTHANA_OT_open_web_viewer,
    UTHANA_OT_show_motion_preview_popup,
    UTHANA_OT_play_motion_preview,
)
