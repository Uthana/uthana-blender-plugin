from datetime import datetime
from pathlib import Path
from typing import Any

from . import client, utils
from .constants import CACHE_DIR
from .logger import logger
from .types import (
    BakeAndUploadRequest,
    DownloadRequest,
    ExportRequest,
    GenerateMotionRequest,
    LoadMotionRequest,
    MotionRequest,
    OperationResult,
    StitchMotionIdsRequest,
    StitchMotionsRequest,
    StitchRequest,
)

try:
    import bpy

    BLENDER_AVAILABLE = True
except ImportError:
    BLENDER_AVAILABLE = False


def generate_motion(request: GenerateMotionRequest) -> OperationResult:
    """Generate motion from text prompt"""
    logger.info("Generating motion: %s", request.prompt)

    try:
        # Create motion request
        motion_request = MotionRequest(
            domain=request.domain,
            api_key=request.api_key,
            character_id=request.character_id,
            prompt=request.prompt,
        )

        # Call API to generate motion
        api_result = client.create_text_to_motion(motion_request)
        if not api_result.success:
            return OperationResult(success=False, message=api_result.message)

        motion_id = api_result.data.get("motion_id")
        if not motion_id:
            return OperationResult(success=False, message="No motion ID returned")

        logger.info("Motion generated successfully: %s", motion_id)

        # Download and import the motion
        download_request = DownloadRequest(
            domain=request.domain,
            api_key=request.api_key,
            character_id=request.character_id,
            motion_id=motion_id,
        )

        import_result = download_and_import_motion(
            download_request.domain,
            download_request.api_key,
            download_request.character_id,
            download_request.motion_id,
        )

        if import_result.success:
            return OperationResult(
                success=True,
                message="Motion generated and imported successfully",
                data={"motion_id": motion_id},
            )
        else:
            return OperationResult(
                success=False,
                message=f"Motion generated but import failed: {import_result.message}",
                data={"motion_id": motion_id},
            )

    except Exception as e:
        logger.error("Error generating motion: %s", str(e))
        return OperationResult(success=False, message=f"Error generating motion: {str(e)}")


def download_and_import_motion(
    domain: str, api_key: str, character_id: str, motion_id: str
) -> OperationResult:
    """Downloads motion file and imports to Blender"""
    request = DownloadRequest(
        domain=domain, api_key=api_key, character_id=character_id, motion_id=motion_id
    )
    download_result = client.download_motion_file(request)
    if not download_result.success:
        return download_result

    file_path = download_result.data.get("file_path")
    if not file_path:
        return OperationResult(success=False, message="No file path in download result")

    return import_fbx_to_blender(file_path, motion_id)


def import_fbx_to_blender(fbx_path: str, motion_id: str = None) -> OperationResult:
    """Imports FBX file to Blender scene"""
    if not BLENDER_AVAILABLE:
        return OperationResult(success=False, message="Blender not available")

    if not utils.validate_blender_context():
        return OperationResult(success=False, message="Invalid Blender context")

    try:
        # Get objects and data before import to identify new ones
        objects_before = set(bpy.context.scene.objects)
        actions_before = set(bpy.data.actions)
        materials_before = set(bpy.data.materials)
        images_before = set(bpy.data.images)
        collections_before = set(bpy.data.collections)

        # Import FBX with axis correction
        bpy.ops.import_scene.fbx(filepath=fbx_path, axis_forward="-Z", axis_up="Y")
        logger.debug("FBX file imported: %s", fbx_path)

        # Rename imported objects with unique names (always add timestamp)
        objects_after = set(bpy.context.scene.objects)
        actions_after = set(bpy.data.actions)
        materials_after = set(bpy.data.materials)
        images_after = set(bpy.data.images)
        collections_after = set(bpy.data.collections)

        new_objects = objects_after - objects_before
        new_actions = actions_after - actions_before
        new_materials = materials_after - materials_before
        new_images = images_after - images_before
        new_collections = collections_after - collections_before

        # Create a new name
        timestamp = datetime.now().strftime("%H%M%S")
        if motion_id:
            base_name = f"{timestamp}-{motion_id}"
        else:
            base_name = timestamp

        # Rename all new data types
        for i, action in enumerate(new_actions):
            action.name = f"{base_name}-Action_{i}" if i > 0 else f"{base_name}-Action"
            logger.debug("Renamed action to: %s", action.name)

        for i, material in enumerate(new_materials):
            material.name = f"{base_name}-Material_{i}" if i > 0 else f"{base_name}-Material"
            logger.debug("Renamed material to: %s", material.name)

        for i, image in enumerate(new_images):
            image.name = f"{base_name}-Image_{i}" if i > 0 else f"{base_name}-Image"
            logger.debug("Renamed image to: %s", image.name)

        for i, collection in enumerate(new_collections):
            collection.name = f"{base_name}-Collection_{i}" if i > 0 else f"{base_name}-Collection"
            logger.debug("Renamed collection to: %s", collection.name)

        # Rename objects and their data
        for i, obj in enumerate(new_objects):
            # Unified naming for all object types
            suffix = f"_{i}" if i > 0 else ""
            obj.name = f"{base_name}-{obj.type}{suffix}"

            # Rename object data if it exists
            if hasattr(obj, "data") and obj.data:
                obj.data.name = f"{base_name}-{obj.type}Data{suffix}"
                logger.debug("Renamed data to: %s", obj.data.name)

            logger.debug("Renamed imported object to: %s", obj.name)

        # Fix scale issues for imported objects
        # For MESH: apply transforms to fix visual scale
        # For ARMATURE: reset transforms to identity to prevent animation distortion
        mesh_objects_to_transform = []
        armature_objects_to_fix = []

        for obj in new_objects:
            has_transforms = (
                obj.location != (0, 0, 0)
                or obj.rotation_euler != (0, 0, 0)
                or obj.scale != (1, 1, 1)
            )

            if has_transforms:
                if obj.type == "MESH":
                    mesh_objects_to_transform.append(obj)
                    logger.debug(
                        "Mesh %s has transforms: loc=%s, rot=%s, scale=%s",
                        obj.name,
                        obj.location,
                        obj.rotation_euler,
                        obj.scale,
                    )
                elif obj.type == "ARMATURE":
                    armature_objects_to_fix.append(obj)
                    logger.debug(
                        "Armature %s has transforms: loc=%s, rot=%s, scale=%s",
                        obj.name,
                        obj.location,
                        obj.rotation_euler,
                        obj.scale,
                    )

        # Apply transforms to mesh objects
        if mesh_objects_to_transform:
            logger.debug("Applying transforms to %d mesh objects", len(mesh_objects_to_transform))

            # Backup current selection
            original_selection = [obj for obj in bpy.context.selected_objects]
            original_active = bpy.context.view_layer.objects.active

            try:
                bpy.ops.object.select_all(action="DESELECT")
                for obj in mesh_objects_to_transform:
                    obj.select_set(True)

                if mesh_objects_to_transform:
                    bpy.context.view_layer.objects.active = mesh_objects_to_transform[0]

                bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
                logger.debug("Transforms applied successfully to mesh objects")

            except Exception as e:
                logger.warning("Failed to apply transforms to mesh objects: %s", e)

            finally:
                # Restore original selection
                bpy.ops.object.select_all(action="DESELECT")
                for obj in original_selection:
                    if obj:
                        obj.select_set(True)
                if original_active:
                    bpy.context.view_layer.objects.active = original_active

        # Reset armature transforms to identity without applying them
        # This prevents animation distortion when user manually applies transforms
        for obj in armature_objects_to_fix:
            logger.debug("Resetting armature %s transforms to identity", obj.name)
            obj.location = (0, 0, 0)
            obj.rotation_euler = (0, 0, 0)
            obj.scale = (1, 1, 1)
            logger.debug("Armature %s transforms reset successfully", obj.name)

        return OperationResult(
            success=True,
            message=f"FBX imported successfully: {Path(fbx_path).name}",
            data={"file_path": fbx_path},
        )
    except Exception as e:
        return OperationResult(success=False, message=f"FBX import failed: {str(e)}")


def export_armatures_to_gltf(output_path: str, use_frame_range: bool = True) -> OperationResult:
    """Exports active armature to GLTF file"""
    if not BLENDER_AVAILABLE:
        return OperationResult(success=False, message="Blender not available")

    # Get all selected armatures and use the first one, or fall back to active
    selected_armatures = utils.get_selected_armatures()
    active_armature = utils.get_active_armature()

    # Debug logging
    logger.debug("Selected armatures: %s", [obj.name for obj in selected_armatures])
    logger.debug("Active armature: %s", active_armature.name if active_armature else "None")

    # Debug: log ALL selected objects and their types
    all_selected = [(obj.name, obj.type) for obj in bpy.context.selected_objects]
    logger.debug("All selected objects: %s", all_selected)

    # Debug: log which objects are visible/hidden
    all_armatures = [obj.name for obj in bpy.context.scene.objects if obj.type == "ARMATURE"]
    logger.debug("All armatures in scene: %s", all_armatures)

    # Debug: log selection state of each armature
    for obj in bpy.context.scene.objects:
        if obj.type == "ARMATURE":
            logger.debug(
                "Armature %s: selected=%s, active=%s",
                obj.name,
                obj.select_get(),
                obj == bpy.context.view_layer.objects.active,
            )

    # Prefer the first selected armature over active armature
    target_armature = None
    if selected_armatures:
        target_armature = selected_armatures[0]
        logger.debug("Using first selected armature: %s", target_armature.name)
    elif active_armature:
        target_armature = active_armature
        logger.debug("Using active armature: %s", target_armature.name)

    if not target_armature:
        return OperationResult(success=False, message="No Armature object selected")

    # Backup current selection and visibility
    original_selection, original_active = utils.backup_selection()
    hidden_objects = []
    # No need to backup actions with unique naming system

    try:
        # Hide all other armatures and their children to ensure single animation export
        for obj in bpy.context.scene.objects:
            if obj.type == "ARMATURE" and obj != target_armature:
                if not obj.hide_viewport:
                    hidden_objects.append(obj)
                    obj.hide_viewport = True
                # Also hide mesh children of other armatures
                for child in bpy.context.scene.objects:
                    if child.type == "MESH" and child.parent == obj and not child.hide_viewport:
                        hidden_objects.append(child)
                        child.hide_viewport = True

        # Select only the target armature and its children (mesh objects)
        bpy.ops.object.select_all(action="DESELECT")
        target_armature.select_set(True)
        bpy.context.view_layer.objects.active = target_armature

        # Also select mesh objects that are children of this armature
        for obj in bpy.context.scene.objects:
            if obj.type == "MESH" and obj.parent == target_armature:
                obj.select_set(True)

        logger.debug("Exporting armature: %s", target_armature.name)
        logger.debug("Temporarily hidden %d objects", len(hidden_objects))
        logger.debug("Exporting to: %s", output_path)

        # Debug: Log selected objects and their actions
        selected_objects = [obj for obj in bpy.context.selected_objects]
        logger.debug("Selected objects for export: %s", [obj.name for obj in selected_objects])

        # Debug: Log all actions in the scene
        all_actions = [action.name for action in bpy.data.actions]
        logger.debug("All actions in scene: %s", all_actions)

        # Find and set the correct action for the selected armature
        # Actions are typically named after the armature they belong to
        # With our naming scheme: armature="HHMMSS-motionId-ARMATURE_X", action="HHMMSS-motionId-Action"
        target_action_name = None
        for action in bpy.data.actions:
            # Extract the timestamp-motionId prefix from both names
            armature_prefix = target_armature.name.split("-", 2)[:2]  # ['HHMMSS', 'motionId']
            action_prefix = action.name.split("-", 2)[:2]  # ['HHMMSS', 'motionId']

            if len(armature_prefix) >= 2 and len(action_prefix) >= 2:
                if armature_prefix == action_prefix:
                    target_action_name = action.name
                    break

        # Set the correct action for the selected armature
        if target_action_name:
            target_action = bpy.data.actions.get(target_action_name)
            if target_action:
                # Ensure the armature has animation data
                if not target_armature.animation_data:
                    target_armature.animation_data_create()

                # Set the correct action
                target_armature.animation_data.action = target_action
                logger.debug(
                    "Set action '%s' for armature '%s'", target_action_name, target_armature.name
                )
            else:
                logger.warning("Could not find action '%s'", target_action_name)
        else:
            logger.warning("Could not find matching action for armature '%s'", target_armature.name)

        # Clear actions from other armatures to prevent animation conflicts
        # Even with unique naming, we need to clear actions to prevent multiple animations
        # from being exported when using ACTIVE_ACTIONS mode
        backed_up_actions = []
        for obj in bpy.context.scene.objects:
            if obj.type == "ARMATURE" and obj != target_armature:
                if obj.animation_data and obj.animation_data.action:
                    # Backup the action so we can restore it later
                    backed_up_actions.append((obj, obj.animation_data.action))
                    obj.animation_data.action = None
                    logger.debug("Temporarily cleared action from armature '%s'", obj.name)

        # Check if armature has non-identity transforms
        has_transforms = (
            target_armature.location != (0, 0, 0)
            or target_armature.rotation_euler != (0, 0, 0)
            or target_armature.scale != (1, 1, 1)
        )

        if has_transforms:
            logger.info("Armature has transforms that will be applied automatically:")
            logger.info("  Location: %s", target_armature.location)
            logger.info("  Rotation: %s", target_armature.rotation_euler)
            logger.info("  Scale: %s", target_armature.scale)

            # Apply transforms to armature and its mesh children before export
            logger.debug("Applying transforms to include them in baked motion")

            # Backup current selection
            original_selection = [obj for obj in bpy.context.selected_objects]
            original_active = bpy.context.view_layer.objects.active

            try:
                # Select armature and its mesh children
                bpy.ops.object.select_all(action="DESELECT")
                target_armature.select_set(True)

                # Also select mesh children
                mesh_children = []
                for obj in bpy.context.scene.objects:
                    if obj.type == "MESH" and obj.parent == target_armature:
                        obj.select_set(True)
                        mesh_children.append(obj.name)

                bpy.context.view_layer.objects.active = target_armature

                logger.debug("Applying transforms to armature and mesh children: %s", mesh_children)
                bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
                logger.debug(
                    "Transforms applied successfully - they will be included in baked motion"
                )

            except Exception as e:
                logger.warning("Failed to apply transforms automatically: %s", e)
                logger.warning("Continuing with bake, but transforms will not be included")

            finally:
                # Restore original selection
                bpy.ops.object.select_all(action="DESELECT")
                for obj in original_selection:
                    if obj:
                        obj.select_set(True)
                if original_active:
                    bpy.context.view_layer.objects.active = original_active

        # Force update the scene to ensure animation data is refreshed
        bpy.context.view_layer.update()
        bpy.context.scene.frame_set(bpy.context.scene.frame_current)

        # Debug: Log actions on selected armatures
        for obj in selected_objects:
            if obj.type == "ARMATURE":
                if obj.animation_data and obj.animation_data.action:
                    logger.debug(
                        "Armature %s has action: %s", obj.name, obj.animation_data.action.name
                    )
                else:
                    logger.debug("Armature %s has NO active action", obj.name)

        # Debug: Check what actions are active before export
        active_actions = []
        for obj in bpy.context.scene.objects:
            if obj.type == "ARMATURE" and obj.animation_data and obj.animation_data.action:
                active_actions.append(f"{obj.name}: {obj.animation_data.action.name}")
        logger.debug("Active actions before GLTF export: %s", active_actions)

        # Store original frame range to restore later
        original_frame_start = bpy.context.scene.frame_start
        original_frame_end = bpy.context.scene.frame_end
        original_frame_current = bpy.context.scene.frame_current

        try:
            # If using frame range, temporarily set scene frame range to current timeline selection
            if use_frame_range:
                # Get current timeline frame range from UI
                frame_start = bpy.context.scene.frame_start
                frame_end = bpy.context.scene.frame_end

                logger.debug("Using frame range: %d - %d", frame_start, frame_end)

                # Ensure the scene frame range matches what user selected
                bpy.context.scene.frame_start = frame_start
                bpy.context.scene.frame_end = frame_end

                # Set current frame to start to ensure proper export
                bpy.context.scene.frame_set(frame_start)
            else:
                logger.debug("Using full animation range")

            # Export GLTF with animation only for selected objects
            # Always use SCENE mode when we've cleared other actions to avoid conflicts
            animation_mode = "SCENE"

            logger.debug(
                "Exporting with animation_mode: %s, export_frame_range: %s",
                animation_mode,
                use_frame_range,
            )

            bpy.ops.export_scene.gltf(
                filepath=output_path,
                export_format="GLTF_EMBEDDED",
                export_materials="NONE",
                export_cameras=False,
                export_lights=False,
                export_animations=True,
                export_animation_mode=animation_mode,
                export_frame_range=use_frame_range,
                export_frame_step=1,
                export_force_sampling=True,
                export_bake_animation=True,
                export_nla_strips=False,
                export_def_bones=False,
                export_optimize_animation_size=False,
                export_anim_single_armature=True,
                export_reset_pose_bones=True,
                export_current_frame=False,
                export_yup=True,
                use_selection=True,
                use_active_collection=False,
                use_active_scene=False,
                export_extras=False,
                export_texcoords=False,
                export_normals=False,
                export_colors=False,
                export_attributes=False,
                export_tangents=False,
                export_apply=False,
                export_skins=True,
                export_morph=False,
                export_draco_mesh_compression_enable=False,
                use_mesh_edges=False,
                use_mesh_vertices=False,
            )

        finally:
            # Always restore original frame range and current frame
            bpy.context.scene.frame_start = original_frame_start
            bpy.context.scene.frame_end = original_frame_end
            bpy.context.scene.frame_set(original_frame_current)
            logger.debug(
                "Restored frame range: %d - %d, current: %d",
                original_frame_start,
                original_frame_end,
                original_frame_current,
            )

        # Check if file was actually created
        if not Path(output_path).exists():
            return OperationResult(
                success=False, message=f"GLTF file was not created at {output_path}"
            )

        file_size = Path(output_path).stat().st_size
        logger.debug("GLTF export completed, file size: %d bytes", file_size)

        # Create informative message about what was exported
        if use_frame_range:
            export_message = f"GLTF exported successfully: {Path(output_path).name} (frames {original_frame_start}-{original_frame_end})"
        else:
            export_message = (
                f"GLTF exported successfully: {Path(output_path).name} (full animation)"
            )

        return OperationResult(
            success=True,
            message=export_message,
            data={
                "file_path": output_path,
                "armature_name": target_armature.name,
                "frame_start": original_frame_start if use_frame_range else None,
                "frame_end": original_frame_end if use_frame_range else None,
                "use_frame_range": use_frame_range,
                "file_size": file_size,
            },
        )

    except Exception as e:
        return OperationResult(success=False, message=f"GLTF export failed: {str(e)}")
    finally:
        # Restore visibility of hidden objects
        for obj in hidden_objects:
            obj.hide_viewport = False

        # Restore actions to other armatures
        for obj, action in backed_up_actions:
            if obj.animation_data:
                obj.animation_data.action = action
                logger.debug("Restored action '%s' to armature '%s'", action.name, obj.name)

        # Restore original selection
        utils.restore_selection(original_selection, original_active)


def bake_and_upload_motion(request: BakeAndUploadRequest) -> OperationResult:
    """Complete pipeline for baking and uploading motion"""
    logger.info("Baking motion: %s", request.character_id)

    # Validate inputs
    validation = validate_bake_inputs(request)
    if not validation.success:
        return validation

    filename = utils.generate_timestamp_filename(ext="gltf")
    output_path = str(CACHE_DIR / filename)

    # Export armatures to GLTF
    logger.debug("Attempting to export to: %s", output_path)
    export_result = export_armatures_to_gltf(output_path, request.use_frame_range)
    if not export_result.success:
        return export_result

    try:
        # Read GLTF content
        with open(output_path, "r") as f:
            gltf_content = f.read()

        logger.debug("Successfully read %d characters from GLTF file", len(gltf_content))

        # Upload to server
        export_request = ExportRequest(
            domain=request.domain,
            api_key=request.api_key,
            character_id=request.character_id,
            motion_name=Path(filename).stem,
            gltf_content=gltf_content,
        )

        upload_result = client.create_motion_from_gltf(export_request)

        if upload_result.success:
            motion_id = upload_result.data.get("motion_id")
            logger.info("Motion baked successfully: %s", motion_id)

            # Download and import the baked motion back to scene
            logger.debug("Downloading and importing baked motion...")
            import_result = download_and_import_motion(
                request.domain, request.api_key, request.character_id, motion_id
            )

            if import_result.success:
                logger.debug("Baked motion imported successfully")
                return OperationResult(
                    success=True,
                    message=f"Motion baked, uploaded and imported successfully! ID: {motion_id}",
                    data={
                        "motion_id": motion_id,
                        "export_stats": export_result.data,
                        "import_result": import_result.data,
                    },
                )
            else:
                logger.warning(
                    "Motion baked and uploaded but import failed: %s", import_result.message
                )
                return OperationResult(
                    success=True,
                    message=f"Motion baked and uploaded successfully! ID: {motion_id}. Import failed: {import_result.message}",
                    data={
                        "motion_id": motion_id,
                        "export_stats": export_result.data,
                        "import_error": import_result.message,
                    },
                )
        else:
            return upload_result

    except Exception as e:
        return OperationResult(success=False, message=f"Upload failed: {str(e)}")


def validate_motion_inputs(request: GenerateMotionRequest) -> OperationResult:
    """Validates inputs for motion generation"""
    if not request.character_id.strip():
        return OperationResult(success=False, message="Character ID is required")

    if not request.prompt.strip():
        return OperationResult(success=False, message="Prompt is required")

    if not request.domain.strip():
        return OperationResult(success=False, message="Domain is required")

    if not request.api_key.strip():
        return OperationResult(success=False, message="Session ID is required")

    return OperationResult(success=True, message="Inputs valid")


def validate_bake_inputs(request: BakeAndUploadRequest) -> OperationResult:
    """Validates inputs for motion baking"""
    if not BLENDER_AVAILABLE:
        return OperationResult(success=False, message="Blender not available")

    if not utils.validate_blender_context():
        return OperationResult(success=False, message="Invalid Blender context")

    if not request.character_id.strip():
        return OperationResult(success=False, message="Character ID is required")

    if not request.domain.strip():
        return OperationResult(success=False, message="Domain is required")

    if not request.api_key.strip():
        return OperationResult(success=False, message="Session ID is required")

    return OperationResult(success=True, message="Inputs valid")


def validate_stitch_inputs(request: StitchMotionsRequest) -> OperationResult:
    """Validates inputs for motion stitching"""
    if not request.character_id.strip():
        return OperationResult(success=False, message="Character ID is required")

    if request.duration <= 0:
        return OperationResult(success=False, message="Duration must be greater than 0")

    if not request.domain.strip():
        return OperationResult(success=False, message="Domain is required")

    if not request.api_key.strip():
        return OperationResult(success=False, message="Session ID is required")

    # Check for exactly one active and one selected (but not active) armature
    selected_but_not_active_armatures = utils.get_selected_but_not_active_armatures()
    active_armature = utils.get_active_armature()

    if not active_armature:
        return OperationResult(
            success=False, message="Please make one armature active (trailing motion)"
        )

    if active_armature.type != "ARMATURE":
        return OperationResult(success=False, message="Active object must be an armature")

    if len(selected_but_not_active_armatures) == 0:
        return OperationResult(success=False, message="Please select one armature (leading motion)")

    if len(selected_but_not_active_armatures) > 1:
        return OperationResult(
            success=False, message="Please select only one armature (leading motion)"
        )

    return OperationResult(success=True, message="Inputs valid")


def validate_stitch_motion_ids_inputs(request: StitchMotionIdsRequest) -> OperationResult:
    """Validates inputs for motion ID stitching"""
    if not request.character_id.strip():
        return OperationResult(success=False, message="Character ID is required")

    if not request.leading_motion_id.strip():
        return OperationResult(success=False, message="Leading Motion ID is required")

    if not request.trailing_motion_id.strip():
        return OperationResult(success=False, message="Trailing Motion ID is required")

    if request.duration <= 0:
        return OperationResult(success=False, message="Duration must be greater than 0")

    if not request.domain.strip():
        return OperationResult(success=False, message="Domain is required")

    if not request.api_key.strip():
        return OperationResult(success=False, message="Session ID is required")

    return OperationResult(success=True, message="Inputs valid")


def bake_specific_armature(
    armature_obj: Any, character_id: str, domain: str, api_key: str, use_frame_range: bool = True
) -> OperationResult:
    """Bakes specific armature to GLTF and uploads, returns motion_id"""
    if not BLENDER_AVAILABLE:
        return OperationResult(success=False, message="Blender not available")

    # Generate unique filename
    filename = utils.generate_timestamp_filename(ext="gltf")
    output_path = str(CACHE_DIR / filename)

    logger.debug("=== BAKE_SPECIFIC_ARMATURE START ===")
    logger.debug("Target armature: %s", armature_obj.name)

    # Log state before backup
    current_selected = [obj.name for obj in bpy.context.selected_objects]
    current_active = (
        bpy.context.view_layer.objects.active.name
        if bpy.context.view_layer.objects.active
        else "None"
    )
    logger.debug("Before backup - Selected: %s, Active: %s", current_selected, current_active)

    # Backup current selection and active state
    original_selection, original_active = utils.backup_selection()
    logger.debug("Backed up selection: %s", [obj.name for obj in original_selection])
    logger.debug("Backed up active: %s", original_active.name if original_active else "None")

    try:
        # Clear selection and set only target armature as active and selected
        logger.debug("Clearing selection and setting target armature")
        bpy.ops.object.select_all(action="DESELECT")
        armature_obj.select_set(True)
        bpy.context.view_layer.objects.active = armature_obj

        # Also select mesh children of this armature
        mesh_children = []
        for obj in bpy.context.scene.objects:
            if obj.type == "MESH" and obj.parent == armature_obj:
                obj.select_set(True)
                mesh_children.append(obj.name)

        # Log state after setting selection
        new_selected = [obj.name for obj in bpy.context.selected_objects]
        new_active = (
            bpy.context.view_layer.objects.active.name
            if bpy.context.view_layer.objects.active
            else "None"
        )
        logger.debug("After setting selection - Selected: %s, Active: %s", new_selected, new_active)
        logger.debug("Mesh children selected: %s", mesh_children)

        logger.debug("Baking armature for stitching: %s", armature_obj.name)

        # Use existing export logic - it already handles multiple armatures correctly
        logger.debug("Calling export_armatures_to_gltf with path: %s", output_path)
        export_result = export_armatures_to_gltf(output_path, use_frame_range)
        if not export_result.success:
            logger.error("Export failed: %s", export_result.message)
            return export_result

        logger.debug("Export successful, reading GLTF content")
        # Read GLTF content and upload
        with open(output_path, "r") as f:
            gltf_content = f.read()

        logger.debug(
            "Successfully read %d characters from GLTF file for stitching", len(gltf_content)
        )

        # Upload to server
        request = ExportRequest(
            domain=domain,
            api_key=api_key,
            character_id=character_id,
            motion_name=f"stitch_{Path(filename).stem}",
            gltf_content=gltf_content,
        )

        logger.debug("Uploading to server...")
        upload_result = client.create_motion_from_gltf(request)

        if upload_result.success:
            motion_id = upload_result.data.get("motion_id")
            logger.debug(
                "Armature %s baked and uploaded successfully, motion_id: %s",
                armature_obj.name,
                motion_id,
            )
            return OperationResult(
                success=True,
                message=f"Armature {armature_obj.name} baked successfully",
                data={"motion_id": motion_id},
            )
        else:
            logger.error("Upload failed: %s", upload_result.message)
            return upload_result

    except Exception as e:
        logger.error("Exception in bake_specific_armature: %s", str(e))
        return OperationResult(
            success=False, message=f"Bake failed for {armature_obj.name}: {str(e)}"
        )
    finally:
        logger.debug("=== BAKE_SPECIFIC_ARMATURE RESTORE ===")
        # Log state before restore
        before_restore_selected = [obj.name for obj in bpy.context.selected_objects]
        before_restore_active = (
            bpy.context.view_layer.objects.active.name
            if bpy.context.view_layer.objects.active
            else "None"
        )
        logger.debug(
            "Before restore - Selected: %s, Active: %s",
            before_restore_selected,
            before_restore_active,
        )

        # Always restore original selection
        logger.debug("Restoring selection to: %s", [obj.name for obj in original_selection])
        logger.debug("Restoring active to: %s", original_active.name if original_active else "None")
        utils.restore_selection(original_selection, original_active)

        # Log state after restore
        after_restore_selected = [obj.name for obj in bpy.context.selected_objects]
        after_restore_active = (
            bpy.context.view_layer.objects.active.name
            if bpy.context.view_layer.objects.active
            else "None"
        )
        logger.debug(
            "After restore - Selected: %s, Active: %s", after_restore_selected, after_restore_active
        )

        # Clean up temporary file
        try:
            if Path(output_path).exists():
                Path(output_path).unlink()
                logger.debug("Cleaned up temporary file: %s", output_path)
        except Exception as e:
            logger.warning("Could not clean up temporary file %s: %s", output_path, str(e))

        logger.debug("=== BAKE_SPECIFIC_ARMATURE END ===")


def stitch_motions(request: StitchMotionsRequest) -> OperationResult:
    """Complete pipeline for motion stitching"""
    logger.info(
        "Stitching motions: %s, %s, %s, %s, %s",
        request.domain,
        request.api_key,
        request.character_id,
        request.duration,
        request.use_frame_range,
    )

    # Validate inputs
    validation = validate_stitch_inputs(request)
    if not validation.success:
        return validation

    # Get armatures and log initial state
    selected_but_not_active_armatures = utils.get_selected_but_not_active_armatures()
    active_armature = utils.get_active_armature()

    leading_armature = selected_but_not_active_armatures[0]  # selected (but not active) = leading
    trailing_armature = active_armature  # active = trailing

    logger.debug("=== STITCH MOTIONS INITIAL STATE ===")
    logger.debug("Leading armature (selected but not active): %s", leading_armature.name)
    logger.debug("Trailing armature (active): %s", trailing_armature.name)

    # Log all selected objects for debugging
    all_selected = [obj.name for obj in bpy.context.selected_objects]
    logger.debug("All currently selected objects: %s", all_selected)
    logger.debug(
        "Current active object: %s",
        bpy.context.view_layer.objects.active.name
        if bpy.context.view_layer.objects.active
        else "None",
    )

    # Backup original state
    original_selection, original_active = utils.backup_selection()
    logger.debug("Backed up selection: %s", [obj.name for obj in original_selection])
    logger.debug("Backed up active: %s", original_active.name if original_active else "None")

    try:
        # Bake leading motion (selected armature)
        logger.info("Baking leading motion: %s", leading_armature.name)
        logger.debug("=== BAKING LEADING MOTION ===")
        logger.debug("About to bake leading motion from armature: %s", leading_armature.name)

        # Check state before baking leading
        current_selected = [obj.name for obj in bpy.context.selected_objects]
        current_active = (
            bpy.context.view_layer.objects.active.name
            if bpy.context.view_layer.objects.active
            else "None"
        )
        logger.debug(
            "Before leading bake - Selected: %s, Active: %s", current_selected, current_active
        )

        leading_result = bake_specific_armature(
            leading_armature,
            request.character_id,
            request.domain,
            request.api_key,
            request.use_frame_range,
        )
        if not leading_result.success:
            return OperationResult(
                success=False, message=f"Failed to bake leading motion: {leading_result.message}"
            )

        leading_motion_id = leading_result.data.get("motion_id")
        logger.info("Leading motion baked: %s", leading_motion_id)

        # Check state after leading bake and before trailing bake
        current_selected = [obj.name for obj in bpy.context.selected_objects]
        current_active = (
            bpy.context.view_layer.objects.active.name
            if bpy.context.view_layer.objects.active
            else "None"
        )
        logger.debug(
            "After leading bake - Selected: %s, Active: %s", current_selected, current_active
        )

        # Verify armatures still exist and are accessible
        logger.debug("Verifying armatures after leading bake:")
        logger.debug(
            "Leading armature still exists: %s", leading_armature.name in bpy.context.scene.objects
        )
        logger.debug(
            "Trailing armature still exists: %s",
            trailing_armature.name in bpy.context.scene.objects,
        )

        # Bake trailing motion (active armature)
        logger.info("Baking trailing motion: %s", trailing_armature.name)
        logger.debug("=== BAKING TRAILING MOTION ===")
        logger.debug("About to bake trailing motion from armature: %s", trailing_armature.name)

        # Check state before baking trailing
        current_selected = [obj.name for obj in bpy.context.selected_objects]
        current_active = (
            bpy.context.view_layer.objects.active.name
            if bpy.context.view_layer.objects.active
            else "None"
        )
        logger.debug(
            "Before trailing bake - Selected: %s, Active: %s", current_selected, current_active
        )

        trailing_result = bake_specific_armature(
            trailing_armature,
            request.character_id,
            request.domain,
            request.api_key,
            request.use_frame_range,
        )
        if not trailing_result.success:
            return OperationResult(
                success=False, message=f"Failed to bake trailing motion: {trailing_result.message}"
            )

        trailing_motion_id = trailing_result.data.get("motion_id")
        logger.info("Trailing motion baked: %s", trailing_motion_id)

        # Check final state after both bakes
        current_selected = [obj.name for obj in bpy.context.selected_objects]
        current_active = (
            bpy.context.view_layer.objects.active.name
            if bpy.context.view_layer.objects.active
            else "None"
        )
        logger.debug(
            "After trailing bake - Selected: %s, Active: %s", current_selected, current_active
        )

        # Create stitched motion via API
        logger.info("Creating stitched motion: %s -> %s", leading_motion_id, trailing_motion_id)
        logger.debug("=== CREATING STITCHED MOTION ===")
        logger.debug(
            "Creating stitched motion: leading_id=%s, trailing_id=%s",
            leading_motion_id,
            trailing_motion_id,
        )
        logger.debug("Leading armature was: %s", leading_armature.name)
        logger.debug("Trailing armature was: %s", trailing_armature.name)

        stitch_request = StitchRequest(
            domain=request.domain,
            api_key=request.api_key,
            character_id=request.character_id,
            leading_motion_id=leading_motion_id,
            trailing_motion_id=trailing_motion_id,
            duration=request.duration,
        )
        stitch_result = client.create_stitched_motion(stitch_request)

        if stitch_result.success:
            stitched_motion_id = stitch_result.data.get("motion_id")
            logger.info("Stitched motion created: %s", stitched_motion_id)

            # Download and import the stitched motion
            logger.debug("Downloading and importing stitched motion...")
            import_result = download_and_import_motion(
                request.domain, request.api_key, request.character_id, stitched_motion_id
            )

            if import_result.success:
                logger.debug("Stitched motion imported successfully")
                return OperationResult(
                    success=True,
                    message=f"Motion stitching completed and imported successfully! ID: {stitched_motion_id}",
                    data={
                        "stitched_motion_id": stitched_motion_id,
                        "leading_motion_id": leading_motion_id,
                        "trailing_motion_id": trailing_motion_id,
                        "leading_armature": leading_armature.name,
                        "trailing_armature": trailing_armature.name,
                        "import_result": import_result.data,
                    },
                )
            else:
                logger.warning(
                    "Stitched motion created but import failed: %s", import_result.message
                )
                return OperationResult(
                    success=True,
                    message=f"Motion stitching completed! ID: {stitched_motion_id}. Import failed: {import_result.message}",
                    data={
                        "stitched_motion_id": stitched_motion_id,
                        "leading_motion_id": leading_motion_id,
                        "trailing_motion_id": trailing_motion_id,
                        "leading_armature": leading_armature.name,
                        "trailing_armature": trailing_armature.name,
                        "import_error": import_result.message,
                    },
                )
        else:
            return OperationResult(
                success=False, message=f"Motion stitching API failed: {stitch_result.message}"
            )

    except Exception as e:
        logger.error("Exception in stitch_motions: %s", str(e))
        return OperationResult(success=False, message=f"Motion stitching failed: {str(e)}")
    finally:
        # Always restore original selection state
        logger.debug("=== RESTORING SELECTION ===")
        logger.debug("Restoring to: %s", [obj.name for obj in original_selection])
        logger.debug("Restoring active to: %s", original_active.name if original_active else "None")
        utils.restore_selection(original_selection, original_active)
        logger.debug("Restored original selection state")

        # Log final state
        final_selected = [obj.name for obj in bpy.context.selected_objects]
        final_active = (
            bpy.context.view_layer.objects.active.name
            if bpy.context.view_layer.objects.active
            else "None"
        )
        logger.debug("Final state - Selected: %s, Active: %s", final_selected, final_active)


def stitch_motion_ids(request: StitchMotionIdsRequest) -> OperationResult:
    """Direct stitching using motion IDs without baking armatures"""
    logger.info(
        "Stitching motion IDs: %s, %s, %s, %s, %s, %s",
        request.domain,
        request.api_key,
        request.character_id,
        request.leading_motion_id,
        request.trailing_motion_id,
        request.duration,
    )

    # Validate inputs
    validation = validate_stitch_motion_ids_inputs(request)
    if not validation.success:
        return validation

    try:
        # Create stitched motion via API
        logger.info(
            "Creating stitched motion: %s -> %s",
            request.leading_motion_id,
            request.trailing_motion_id,
        )
        logger.debug(
            "Creating stitched motion: leading_id=%s, trailing_id=%s, duration=%f",
            request.leading_motion_id,
            request.trailing_motion_id,
            request.duration,
        )

        stitch_request = StitchRequest(
            domain=request.domain,
            api_key=request.api_key,
            character_id=request.character_id,
            leading_motion_id=request.leading_motion_id,
            trailing_motion_id=request.trailing_motion_id,
            duration=request.duration,
        )
        stitch_result = client.create_stitched_motion(stitch_request)

        if stitch_result.success:
            stitched_motion_id = stitch_result.data.get("motion_id")
            logger.info("Stitched motion created: %s", stitched_motion_id)

            # Download and import the stitched motion
            logger.debug("Downloading and importing stitched motion...")
            import_result = download_and_import_motion(
                request.domain, request.api_key, request.character_id, stitched_motion_id
            )

            if import_result.success:
                logger.debug("Stitched motion imported successfully")
                return OperationResult(
                    success=True,
                    message=f"Motion IDs stitched and imported successfully! ID: {stitched_motion_id}",
                    data={
                        "stitched_motion_id": stitched_motion_id,
                        "leading_motion_id": request.leading_motion_id,
                        "trailing_motion_id": request.trailing_motion_id,
                        "import_result": import_result.data,
                    },
                )
            else:
                logger.warning(
                    "Stitched motion created but import failed: %s", import_result.message
                )
                return OperationResult(
                    success=True,
                    message=f"Motion IDs stitched! ID: {stitched_motion_id}. Import failed: {import_result.message}",
                    data={
                        "stitched_motion_id": stitched_motion_id,
                        "leading_motion_id": request.leading_motion_id,
                        "trailing_motion_id": request.trailing_motion_id,
                        "import_error": import_result.message,
                    },
                )
        else:
            return OperationResult(
                success=False, message=f"Motion IDs stitching API failed: {stitch_result.message}"
            )

    except Exception as e:
        return OperationResult(success=False, message=f"Motion IDs stitching failed: {str(e)}")


def load_motion(request: LoadMotionRequest) -> OperationResult:
    """Load motion from server by Motion ID"""
    logger.info("Loading motion: %s", request.motion_id)

    try:
        # Download and import the motion
        import_result = download_and_import_motion(
            request.domain,
            request.api_key,
            request.character_id,
            request.motion_id,
        )

        if import_result.success:
            logger.info("Motion loaded successfully: %s", request.motion_id)
            return OperationResult(
                success=True,
                message="Motion loaded successfully",
                data={"motion_id": request.motion_id},
            )
        else:
            return OperationResult(
                success=False,
                message=f"Failed to load motion: {import_result.message}",
            )

    except Exception as e:
        logger.error("Error loading motion: %s", str(e))
        return OperationResult(success=False, message=f"Error loading motion: {str(e)}")
