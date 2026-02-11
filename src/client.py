from typing import Any, Dict, Optional

import requests

from .auth import create_api_headers, create_download_headers
from .constants import CACHE_DIR, TAR_CHARACTER_ID
from .logger import logger
from .types import DownloadRequest, ExportRequest, MotionRequest, OperationResult, StitchRequest


def make_graphql_request(
    url: str, api_key: str, query: str, variables: Optional[Dict[str, Any]] = None
) -> OperationResult:
    """Universal function for GraphQL requests"""
    try:
        payload = {"query": query}
        if variables:
            payload["variables"] = variables

        headers = create_api_headers(api_key)
        logger.info("Sending request to %s", url)
        response = requests.post(url, headers=headers, json=payload)
        response.raise_for_status()

        result = response.json()
        logger.info("Response JSON: %s", result)

        if "errors" in result:
            error_msg = (
                result["errors"][0]["message"] if result["errors"] else "Unknown GraphQL error"
            )
            return OperationResult(
                success=False, message=f"GraphQL Error: {error_msg}", error_code="GRAPHQL_ERROR"
            )

        return OperationResult(
            success=True, message="Request successful", data=result.get("data", {})
        )

    except requests.exceptions.RequestException as e:
        return OperationResult(
            success=False, message=f"Request failed: {str(e)}", error_code="REQUEST_ERROR"
        )
    except Exception as e:
        return OperationResult(
            success=False, message=f"Unexpected error: {str(e)}", error_code="UNKNOWN_ERROR"
        )


def create_text_to_motion(request: MotionRequest) -> OperationResult:
    """Creates text-to-motion via GraphQL"""
    query = """
    mutation CreateTextToMotion($prompt: String!) {
      create_text_to_motion(prompt: $prompt) {
        motion {
          id
          name
        }
      }
    }
    """

    variables = {"prompt": request.prompt}

    url = f"https://{request.domain}/graphql"
    result = make_graphql_request(url, request.api_key, query, variables)

    if result.success and result.data:
        motion_data = result.data.get("create_text_to_motion", {})
        motion = motion_data.get("motion", {})
        if motion and motion.get("id"):
            motion_id = motion.get("id")
            return OperationResult(
                success=True,
                message=f"Motion created successfully! ID: {motion_id}",
                data={"motion_id": motion_id, "motion": motion},
            )
        else:
            return OperationResult(
                success=False, message="Motion creation failed - no motion ID returned"
            )

    return result


def create_motion_from_gltf(request: ExportRequest) -> OperationResult:
    """Uploads GLTF as new motion"""
    query = """
        mutation create_motion_from_gltf(
          $gltf: String!,
          $motionName: String!,
          $characterId: String,
        ) {
          create_motion_from_gltf(
            gltf: $gltf,
            motion_name: $motionName,
            character_id: $characterId,
          ) {
            motion {id}
          }
        }
    """

    variables = {
        "motionName": request.motion_name,
        "characterId": TAR_CHARACTER_ID,
        "gltf": request.gltf_content,
    }

    url = f"https://{request.domain}/graphql"
    result = make_graphql_request(url, request.api_key, query, variables)

    if result.success and result.data:
        gltf_data = result.data.get("create_motion_from_gltf", {})
        if gltf_data.get("ok"):
            motion_id = gltf_data.get("motion").get("id")
            return OperationResult(
                success=True,
                message=f"Motion uploaded successfully! ID: {motion_id}",
                data={"motion_id": motion_id},
            )
        else:
            return OperationResult(success=False, message="Motion upload failed")

    return result


def download_motion_file(request: DownloadRequest) -> OperationResult:
    """Downloads motion file from server"""
    try:
        ext = "fbx"
        download_url = f"https://{request.domain}/motion/file/motion_viewer/{request.character_id}/{request.motion_id}/{ext}/{request.character_id}-{request.motion_id}.{ext}"

        headers = create_download_headers(request.api_key)

        logger.info("Downloading motion file: %s", download_url)
        response = requests.get(download_url, headers=headers, stream=True)
        response.raise_for_status()

        # Save file
        filename = f"{request.character_id}-{request.motion_id}.{ext}"
        output_path = str(CACHE_DIR / filename)

        with open(output_path, "wb") as f:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)

        logger.info("Motion file saved to: %s", output_path)

        return OperationResult(
            success=True,
            message=f"Motion file downloaded: {filename}",
            data={"file_path": output_path, "filename": filename},
        )

    except requests.exceptions.RequestException as e:
        return OperationResult(
            success=False, message=f"Download failed: {str(e)}", error_code="DOWNLOAD_ERROR"
        )
    except Exception as e:
        return OperationResult(
            success=False, message=f"Download error: {str(e)}", error_code="UNKNOWN_ERROR"
        )


def list_motions(api_key: str, domain: str) -> OperationResult:
    """List all motions for the authenticated user."""
    query = """
    query {
        motions {
            id
            name
            created
            updated
            tags
            favorite {
                id
            }
        }
    }
    """

    url = f"https://{domain}/graphql"
    result = make_graphql_request(url, api_key, query)

    if result.success and result.data:
        # Process motions to add is_favorite boolean
        motions = result.data.get("motions", [])
        for motion in motions:
            motion["is_favorite"] = motion.get("favorite") is not None
        return OperationResult(
            success=True,
            message="Motions fetched successfully",
            data={"motions": motions},
        )

    return result


def list_characters(api_key: str, domain: str) -> OperationResult:
    """List all characters for the authenticated user."""
    query = """
    query {
        characters {
            id
            name
            created
            updated
        }
    }
    """

    url = f"https://{domain}/graphql"
    result = make_graphql_request(url, api_key, query)

    if result.success and result.data:
        return OperationResult(
            success=True,
            message="Characters fetched successfully",
            data={"characters": result.data.get("characters", [])},
        )

    return result


def get_user_info(api_key: str, domain: str) -> OperationResult:
    """Get current user information."""
    query = """
    query {
        user {
            id
            name
            email
            email_verified
        }
    }
    """

    url = f"https://{domain}/graphql"
    result = make_graphql_request(url, api_key, query)

    if result.success and result.data:
        return OperationResult(
            success=True,
            message="User info fetched successfully",
            data={"user": result.data.get("user", {})},
        )

    return result


def get_org_info(api_key: str, domain: str) -> OperationResult:
    """Get current organization information."""
    query = """
    query {
        org {
            id
            name
            motion_download_secs_per_month
            motion_download_secs_per_month_remaining
        }
    }
    """

    url = f"https://{domain}/graphql"
    result = make_graphql_request(url, api_key, query)

    if result.success and result.data:
        return OperationResult(
            success=True,
            message="Org info fetched successfully",
            data={"org": result.data.get("org", {})},
        )

    return result


def create_video_to_motion(
    api_key: str, domain: str, video_path: str, motion_name: str
) -> OperationResult:
    """Create a motion from a video file.

    This initiates an async job that needs to be polled for completion.

    Args:
        api_key: API key for authentication
        domain: API domain
        video_path: Path to the video file
        motion_name: Name for the created motion

    Returns:
        OperationResult with job_id in data if successful
    """
    import os

    from .auth import create_basic_auth_header

    if not os.path.exists(video_path):
        return OperationResult(
            success=False,
            message=f"Video file not found: {video_path}",
            error_code="FILE_NOT_FOUND",
        )

    # GraphQL multipart request for file upload
    query = """
    mutation ($file: Upload!, $motion_name: String!) {
        create_video_to_motion(file: $file, motion_name: $motion_name) {
            job {
                id
                status
            }
        }
    }
    """

    try:
        # Prepare multipart form data per GraphQL multipart spec
        operations = {
            "query": query,
            "variables": {"file": None, "motion_name": motion_name},
        }

        map_data = {"0": ["variables.file"]}

        import json

        url = f"https://{domain}/graphql"
        headers = {"Authorization": create_basic_auth_header(api_key)}

        with open(video_path, "rb") as video_file:
            files = {
                "operations": (None, json.dumps(operations)),
                "map": (None, json.dumps(map_data)),
                "0": (os.path.basename(video_path), video_file, "video/mp4"),
            }

            logger.info("Uploading video for motion extraction: %s", video_path)
            response = requests.post(url, headers=headers, files=files)
            response.raise_for_status()

        result = response.json()
        logger.info("Video upload response: %s", result)

        if "errors" in result:
            error_msg = (
                result["errors"][0]["message"] if result["errors"] else "Unknown GraphQL error"
            )
            return OperationResult(
                success=False,
                message=f"Video upload failed: {error_msg}",
                error_code="GRAPHQL_ERROR",
            )

        v2m_data = result.get("data", {}).get("create_video_to_motion", {})
        job_data = v2m_data.get("job", {})
        job_id = job_data.get("id")

        if job_id:
            return OperationResult(
                success=True,
                message=f"Video upload started. Job ID: {job_id}",
                data={"job_id": job_id, "status": job_data.get("status", "RESERVED")},
            )
        else:
            return OperationResult(
                success=False, message="No job ID returned", error_code="NO_JOB_ID"
            )

    except requests.exceptions.RequestException as e:
        return OperationResult(
            success=False,
            message=f"Video upload failed: {str(e)}",
            error_code="REQUEST_ERROR",
        )
    except Exception as e:
        return OperationResult(
            success=False,
            message=f"Video upload error: {str(e)}",
            error_code="UNKNOWN_ERROR",
        )


def get_job_status(api_key: str, domain: str, job_id: str) -> OperationResult:
    """Get the status of an async job.

    Args:
        api_key: API key for authentication
        domain: API domain
        job_id: The job ID to check

    Returns:
        OperationResult with status and result data
    """
    query = """
    query GetJob($job_id: String!) {
        job(job_id: $job_id) {
            id
            status
            result
        }
    }
    """

    variables = {"job_id": job_id}

    url = f"https://{domain}/graphql"
    result = make_graphql_request(url, api_key, query, variables)

    if result.success and result.data:
        job_data = result.data.get("job", {})
        status = job_data.get("status", "UNKNOWN")
        job_result = job_data.get("result")

        # Parse result if it's a string (JSON)
        if isinstance(job_result, str):
            import json

            try:
                job_result = json.loads(job_result)
            except json.JSONDecodeError:
                pass

        return OperationResult(
            success=True,
            message=f"Job status: {status}",
            data={
                "job_id": job_id,
                "status": status,
                "result": job_result,
            },
        )

    return result


def create_character(
    api_key: str,
    domain: str,
    file_path: str,
    name: str,
    auto_rig: bool = True,
) -> OperationResult:
    """Upload a character file for auto-rigging.

    Args:
        api_key: API key for authentication
        domain: API domain
        file_path: Path to the character file (FBX, GLB, GLTF)
        name: Name for the character
        auto_rig: Whether to auto-rig the character

    Returns:
        OperationResult with character_id in data if successful
    """
    import os

    from .auth import create_basic_auth_header

    if not os.path.exists(file_path):
        return OperationResult(
            success=False,
            message=f"Character file not found: {file_path}",
            error_code="FILE_NOT_FOUND",
        )

    query = """
    mutation create_character($file: Upload!, $name: String!, $auto_rig: Boolean) {
        create_character(file: $file, name: $name, auto_rig: $auto_rig) {
            character {
                id
                name
            }
        }
    }
    """

    try:
        operations = {
            "query": query,
            "variables": {"file": None, "name": name, "auto_rig": auto_rig},
        }

        map_data = {"0": ["variables.file"]}

        import json

        # Determine MIME type
        ext = os.path.splitext(file_path)[1].lower()
        mime_types = {
            ".fbx": "application/octet-stream",
            ".glb": "model/gltf-binary",
            ".gltf": "model/gltf+json",
        }
        mime_type = mime_types.get(ext, "application/octet-stream")

        url = f"https://{domain}/graphql"
        headers = {"Authorization": create_basic_auth_header(api_key)}

        with open(file_path, "rb") as char_file:
            files = {
                "operations": (None, json.dumps(operations)),
                "map": (None, json.dumps(map_data)),
                "0": (os.path.basename(file_path), char_file, mime_type),
            }

            logger.info("Uploading character: %s", file_path)
            response = requests.post(url, headers=headers, files=files)
            response.raise_for_status()

        result = response.json()
        logger.info("Character upload response: %s", result)

        if "errors" in result:
            error_msg = (
                result["errors"][0]["message"] if result["errors"] else "Unknown GraphQL error"
            )
            return OperationResult(
                success=False,
                message=f"Character upload failed: {error_msg}",
                error_code="GRAPHQL_ERROR",
            )

        char_data = result.get("data", {}).get("create_character", {}).get("character", {})
        char_id = char_data.get("id")

        if char_id:
            return OperationResult(
                success=True,
                message=f"Character uploaded successfully. ID: {char_id}",
                data={"character_id": char_id, "name": char_data.get("name", name)},
            )
        else:
            return OperationResult(
                success=False, message="No character ID returned", error_code="NO_CHAR_ID"
            )

    except requests.exceptions.RequestException as e:
        return OperationResult(
            success=False,
            message=f"Character upload failed: {str(e)}",
            error_code="REQUEST_ERROR",
        )
    except Exception as e:
        return OperationResult(
            success=False,
            message=f"Character upload error: {str(e)}",
            error_code="UNKNOWN_ERROR",
        )


def download_character(
    api_key: str, domain: str, character_id: str, format: str = "fbx"
) -> OperationResult:
    """Download a character file.

    Args:
        api_key: API key for authentication
        domain: API domain
        character_id: ID of the character to download
        format: File format (fbx or glb)

    Returns:
        OperationResult with file_path in data if successful
    """
    from .auth import create_download_headers

    download_url = f"https://{domain}/motion/bundle/{character_id}/character.{format}"
    headers = create_download_headers(api_key)

    try:
        logger.info("Downloading character: %s", download_url)
        response = requests.get(download_url, headers=headers, stream=True)
        response.raise_for_status()

        # Save file
        filename = f"{character_id}.{format}"
        output_path = str(CACHE_DIR / filename)

        with open(output_path, "wb") as f:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)

        logger.info("Character file saved to: %s", output_path)

        return OperationResult(
            success=True,
            message=f"Character downloaded: {filename}",
            data={"file_path": output_path, "filename": filename},
        )

    except requests.exceptions.RequestException as e:
        return OperationResult(
            success=False,
            message=f"Character download failed: {str(e)}",
            error_code="DOWNLOAD_ERROR",
        )
    except Exception as e:
        return OperationResult(
            success=False,
            message=f"Character download error: {str(e)}",
            error_code="UNKNOWN_ERROR",
        )


def delete_motion(api_key: str, domain: str, motion_id: str) -> OperationResult:
    """Delete a motion by ID."""
    query = """
    mutation update_motion($id: String!, $deleted: Boolean) {
        update_motion(id: $id, deleted: $deleted) {
            id
            name
            deleted
        }
    }
    """

    variables = {"id": motion_id, "deleted": True}

    url = f"https://{domain}/graphql"
    result = make_graphql_request(url, api_key, query, variables)

    if result.success and result.data:
        return OperationResult(
            success=True,
            message=f"Motion {motion_id} deleted successfully",
            data=result.data.get("update_motion", {}),
        )

    return result


def rename_motion(api_key: str, domain: str, motion_id: str, new_name: str) -> OperationResult:
    """Rename a motion by ID."""
    query = """
    mutation update_motion($id: String!, $name: String) {
        update_motion(id: $id, name: $name) {
            id
            name
        }
    }
    """

    variables = {"id": motion_id, "name": new_name}

    url = f"https://{domain}/graphql"
    result = make_graphql_request(url, api_key, query, variables)

    if result.success and result.data:
        updated = result.data.get("update_motion", {})
        return OperationResult(
            success=True,
            message=f"Motion renamed to '{updated.get('name', new_name)}'",
            data=updated,
        )

    return result


def set_motion_favorite(
    api_key: str, domain: str, motion_id: str, favorite: bool
) -> OperationResult:
    """Set or unset a motion as favorite."""
    if favorite:
        query = """
        mutation create_motion_favorite($motion_id: String!) {
            create_motion_favorite(motion_id: $motion_id) {
                id
                motion_id
            }
        }
        """
        variables = {"motion_id": motion_id}
    else:
        query = """
        mutation delete_motion_favorite($motion_id: String!) {
            delete_motion_favorite(motion_id: $motion_id) {
                id
            }
        }
        """
        variables = {"motion_id": motion_id}

    url = f"https://{domain}/graphql"
    result = make_graphql_request(url, api_key, query, variables)

    if result.success:
        action = "added to" if favorite else "removed from"
        return OperationResult(
            success=True,
            message=f"Motion {action} favorites",
            data=result.data,
        )

    return result


def create_stitched_motion(request: StitchRequest) -> OperationResult:
    """Creates stitched motion via GraphQL"""
    query = """
    mutation create_stitched_motion(
        $character_id: String!,
        $leading_motion_id: String!,
        $trailing_motion_id: String!,
        $duration: Float!
    ) {
        create_stitched_motion(
            character_id: $character_id,
            leading_motion_id: $leading_motion_id,
            trailing_motion_id: $trailing_motion_id,
            duration: $duration
        ) {
            ok
            motion_id
        }
    }
    """

    variables = {
        "character_id": request.character_id,
        "leading_motion_id": request.leading_motion_id,
        "trailing_motion_id": request.trailing_motion_id,
        "duration": request.duration,
    }

    url = f"https://{request.domain}/graphql"
    result = make_graphql_request(url, request.api_key, query, variables)

    if result.success and result.data:
        stitch_data = result.data.get("create_stitched_motion", {})
        if stitch_data.get("ok"):
            motion_id = stitch_data.get("motion_id")
            return OperationResult(
                success=True,
                message=f"Stitched motion created successfully! ID: {motion_id}",
                data={"motion_id": motion_id},
            )
        else:
            return OperationResult(success=False, message="Motion stitching failed")

    return result
