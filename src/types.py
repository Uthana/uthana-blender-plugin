from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Optional

from .constants import TAR_CHARACTER_ID


@dataclass
class AuthConfig:
    domain: str = "uthana.com"
    api_key: str = ""

    def is_valid(self) -> bool:
        return bool(self.domain and self.api_key)


@dataclass
class MotionRequest:
    domain: str
    api_key: str
    character_id: str
    prompt: str
    model: str = "text-to-motion-ucmd"


@dataclass
class ExportRequest:
    domain: str
    api_key: str
    character_id: str
    motion_name: str
    gltf_content: str


@dataclass
class StitchRequest:
    domain: str
    api_key: str
    character_id: str
    leading_motion_id: str
    trailing_motion_id: str
    duration: float


@dataclass
class DownloadRequest:
    domain: str
    api_key: str
    character_id: str
    motion_id: str


@dataclass
class BakeRequest:
    character_id: str
    use_frame_range: bool = True


@dataclass
class GenerateMotionRequest:
    domain: str
    api_key: str
    character_id: str
    prompt: str


@dataclass
class LoadMotionRequest:
    domain: str
    api_key: str
    character_id: str
    motion_id: str


@dataclass
class StitchMotionsRequest:
    domain: str
    api_key: str
    character_id: str
    duration: float
    use_frame_range: bool = False


@dataclass
class StitchMotionIdsRequest:
    domain: str
    api_key: str
    character_id: str
    leading_motion_id: str
    trailing_motion_id: str
    duration: float


@dataclass
class BakeAndUploadRequest:
    domain: str
    api_key: str
    character_id: str
    use_frame_range: bool = True


@dataclass
class OperationResult:
    success: bool
    message: str
    data: Optional[Dict[str, Any]] = None
    error_code: Optional[str] = None


@dataclass
class UIState:
    show_config: bool = False
    show_text_to_motion: bool = True
    show_load_motion: bool = True
    show_bake: bool = True
    show_stitching: bool = False
    show_stitch_motion_ids: bool = True


@dataclass
class UthanaConfig:
    auth: AuthConfig = field(default_factory=AuthConfig)
    # Text to Motion
    prompt: str = "A person "
    character_id: str = TAR_CHARACTER_ID
    generate_result_motion_id: str = ""
    # Load Motion
    load_motion_id: str = ""
    load_character_id: str = TAR_CHARACTER_ID
    load_result_motion_id: str = ""
    # Bake Motion
    bake_character_id: str = TAR_CHARACTER_ID
    bake_use_frame_range: bool = True
    bake_result_motion_id: str = ""
    # Stitch Armatures
    stitch_character_id: str = TAR_CHARACTER_ID
    stitch_duration: float = 1.0
    stitch_use_frame_range: bool = False
    stitch_result_motion_id: str = ""
    # Stitch Motion IDs
    stitch_ids_character_id: str = TAR_CHARACTER_ID
    stitch_ids_leading_motion_id: str = ""
    stitch_ids_trailing_motion_id: str = ""
    stitch_ids_duration: float = 1.0
    stitch_ids_result_motion_id: str = ""
    # UI State
    ui_state: UIState = field(default_factory=UIState)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "auth": {
                "domain": self.auth.domain,
                "api_key": self.auth.api_key,
            },
            "prompt": self.prompt,
            "character_id": self.character_id,
            "generate_result_motion_id": self.generate_result_motion_id,
            "load_motion_id": self.load_motion_id,
            "load_character_id": self.load_character_id,
            "load_result_motion_id": self.load_result_motion_id,
            "bake_character_id": self.bake_character_id,
            "bake_use_frame_range": self.bake_use_frame_range,
            "bake_result_motion_id": self.bake_result_motion_id,
            "stitch_character_id": self.stitch_character_id,
            "stitch_duration": self.stitch_duration,
            "stitch_use_frame_range": self.stitch_use_frame_range,
            "stitch_result_motion_id": self.stitch_result_motion_id,
            "stitch_ids_character_id": self.stitch_ids_character_id,
            "stitch_ids_leading_motion_id": self.stitch_ids_leading_motion_id,
            "stitch_ids_trailing_motion_id": self.stitch_ids_trailing_motion_id,
            "stitch_ids_duration": self.stitch_ids_duration,
            "stitch_ids_result_motion_id": self.stitch_ids_result_motion_id,
            "ui_state": {
                "show_config": self.ui_state.show_config,
                "show_text_to_motion": self.ui_state.show_text_to_motion,
                "show_load_motion": self.ui_state.show_load_motion,
                "show_bake": self.ui_state.show_bake,
                "show_stitching": self.ui_state.show_stitching,
                "show_stitch_motion_ids": self.ui_state.show_stitch_motion_ids,
            },
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> UthanaConfig:
        auth_data = data.get("auth", {})
        ui_data = data.get("ui_state", {})

        # Support migration from old session_id format
        api_key = auth_data.get("api_key", "")
        if not api_key and "session_id" in auth_data:
            # Old configs used session_id - user will need to re-enter API key
            api_key = ""

        return cls(
            auth=AuthConfig(domain=auth_data.get("domain", "uthana.com"), api_key=api_key),
            prompt=data.get("prompt", "A person "),
            character_id=data.get(
                "character_id", data.get("motion_character_id", TAR_CHARACTER_ID)
            ),  # Backward compatibility
            generate_result_motion_id=data.get("generate_result_motion_id", ""),
            load_motion_id=data.get("load_motion_id", ""),
            load_character_id=data.get("load_character_id", TAR_CHARACTER_ID),
            load_result_motion_id=data.get("load_result_motion_id", ""),
            bake_character_id=data.get("bake_character_id", TAR_CHARACTER_ID),
            bake_use_frame_range=data.get("bake_use_frame_range", True),
            bake_result_motion_id=data.get("bake_result_motion_id", ""),
            stitch_character_id=data.get("stitch_character_id", TAR_CHARACTER_ID),
            stitch_duration=data.get("stitch_duration", 1.0),
            stitch_use_frame_range=data.get("stitch_use_frame_range", False),
            stitch_result_motion_id=data.get("stitch_result_motion_id", ""),
            stitch_ids_character_id=data.get("stitch_ids_character_id", TAR_CHARACTER_ID),
            stitch_ids_leading_motion_id=data.get("stitch_ids_leading_motion_id", ""),
            stitch_ids_trailing_motion_id=data.get("stitch_ids_trailing_motion_id", ""),
            stitch_ids_duration=data.get("stitch_ids_duration", 1.0),
            stitch_ids_result_motion_id=data.get("stitch_ids_result_motion_id", ""),
            ui_state=UIState(
                show_config=ui_data.get("show_config", False),
                show_text_to_motion=ui_data.get("show_text_to_motion", True),
                show_load_motion=ui_data.get("show_load_motion", True),
                show_bake=ui_data.get("show_bake", True),
                show_stitching=ui_data.get("show_stitching", False),
                show_stitch_motion_ids=ui_data.get("show_stitch_motion_ids", True),
            ),
        )
