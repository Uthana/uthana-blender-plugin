"""Authentication utilities for Uthana API.

This module provides Basic Auth header creation for API key authentication.
The Uthana API uses HTTP Basic Auth with the API key as the username and
an empty password.
"""

import base64
from typing import Dict

APP_NAME = "uthana-blender"
DEFAULT_VERSION = "0.0.0"
_client_version = DEFAULT_VERSION


def set_client_version(version: str) -> None:
    """Set client version used in request headers."""
    global _client_version
    normalized = version.strip() if version else ""
    _client_version = normalized or DEFAULT_VERSION


def create_basic_auth_header(api_key: str) -> str:
    """Creates Basic Auth header value from API key.

    The Uthana API expects Basic Auth with format: base64(API_KEY:)
    where the password is empty.

    Args:
        api_key: The Uthana API key

    Returns:
        The Authorization header value (e.g., "Basic dXNlcm5hbWU6")
    """
    credentials = f"{api_key}:"
    encoded = base64.b64encode(credentials.encode()).decode()
    return f"Basic {encoded}"


def create_api_headers(api_key: str) -> Dict[str, str]:
    """Creates headers for GraphQL API requests.

    Args:
        api_key: The Uthana API key

    Returns:
        Dictionary of headers for API requests
    """
    return {
        "Content-Type": "application/json",
        "Authorization": create_basic_auth_header(api_key),
        "User-Agent": f"{APP_NAME}/{_client_version}",
        "X-Uthana-Client": f"{APP_NAME}/{_client_version}",
    }


def create_download_headers(api_key: str) -> Dict[str, str]:
    """Creates headers for file download requests.

    Args:
        api_key: The Uthana API key

    Returns:
        Dictionary of headers for download requests
    """
    return {
        "Authorization": create_basic_auth_header(api_key),
        "User-Agent": f"{APP_NAME}/{_client_version}",
        "X-Uthana-Client": f"{APP_NAME}/{_client_version}",
    }


def validate_api_key(api_key: str) -> bool:
    """Basic validation of API key format.

    Args:
        api_key: The API key to validate

    Returns:
        True if the API key appears to be valid format
    """
    if not api_key:
        return False
    # API keys should be non-empty strings without whitespace
    return len(api_key.strip()) > 0 and api_key == api_key.strip()
