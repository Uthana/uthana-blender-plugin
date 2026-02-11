"""Blender operators for Uthana plugin."""

import bpy

from .. import config, motion


class UTHANA_OT_generate_motion(bpy.types.Operator):
    """Generate motion from text prompt."""

    bl_idname = "uthana.generate_motion"
    bl_label = "Generate"
    bl_description = "Generate motion from text prompt"

    def execute(self, context):
        props = context.scene.uthana_props
        request = props.create_generate_motion_request()
        result = motion.generate_motion(request)

        if result.success:
            motion_id = result.data.get("motion_id")
            if motion_id:
                props.generate_result_motion_id = motion_id
            self.report({"INFO"}, result.message)
            return {"FINISHED"}
        else:
            self.report({"ERROR"}, result.message)
            return {"CANCELLED"}


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
)
