import uuid

import requests  # type: ignore[import-untyped]

from .auth import create_basic_auth_header
from .logger import logger

APP_NAME = "uthana-blender"


def log_initialized_event(domain: str, api_key: str, version: str) -> None:
    """Send one plugin initialized telemetry event.

    This is best-effort and should never raise, so plugin startup is unaffected.
    """
    if not domain or not api_key:
        logger.debug("Skipping initialization telemetry (missing domain or API key).")
        return

    headers = {
        "Content-Type": "application/json",
        "Authorization": create_basic_auth_header(api_key),
        "User-Agent": f"{APP_NAME}/{version}",
        "X-Uthana-Client": f"{APP_NAME}/{version}",
    }

    try:
        user_response = requests.post(
            f"https://{domain}/graphql",
            json={"query": "{user{id}}"},
            headers=headers,
            timeout=10,
        )
        user_response.raise_for_status()

        user = user_response.json().get("data", {}).get("user")
        if not user or "id" not in user:
            logger.warning("Initialization telemetry skipped: no user id in GraphQL response")
            return

        anon_id = "00000000" + str(uuid.uuid1(clock_seq=1))[8:]
        event_payload = {
            "type": "track",
            "event": "initialized",
            "app": APP_NAME,
            "userId": user["id"],
            "anonymousId": anon_id,
        }

        event_response = requests.post(
            f"https://{domain}/event", json=event_payload, headers=headers, timeout=10
        )
        event_response.raise_for_status()
        logger.debug("Initialization telemetry sent")
    except requests.exceptions.RequestException as exc:
        logger.warning("Initialization telemetry failed: %s", exc)
    except Exception as exc:  # pragma: no cover - defensive guard
        logger.warning("Unexpected initialization telemetry error: %s", exc)
