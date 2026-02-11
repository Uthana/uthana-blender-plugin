"""Asset management for Uthana plugin.

This module provides caching and management of motions and characters
fetched from the Uthana API.
"""

import time
from dataclasses import dataclass, field
from typing import List, Optional

from . import client
from .logger import logger
from .types import OperationResult


@dataclass
class MotionItem:
    """Represents a motion in the asset list."""

    id: str
    name: str
    created: str = ""
    is_favorite: bool = False


@dataclass
class CharacterItem:
    """Represents a character in the asset list."""

    id: str
    name: str
    created: str = ""


@dataclass
class AssetCache:
    """Cached asset lists with timestamps."""

    motions: List[MotionItem] = field(default_factory=list)
    characters: List[CharacterItem] = field(default_factory=list)
    motions_fetched_at: float = 0
    characters_fetched_at: float = 0
    cache_ttl: float = 60  # 1 minute cache

    def motions_stale(self) -> bool:
        """Check if motions cache is stale."""
        return (time.time() - self.motions_fetched_at) > self.cache_ttl

    def characters_stale(self) -> bool:
        """Check if characters cache is stale."""
        return (time.time() - self.characters_fetched_at) > self.cache_ttl


class AssetManager:
    """Manages asset lists and caching.

    Singleton pattern to maintain state across UI redraws.
    """

    _instance: Optional["AssetManager"] = None
    _cache: AssetCache

    def __init__(self):
        self._cache = AssetCache()

    @classmethod
    def instance(cls) -> "AssetManager":
        """Get the singleton instance."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def refresh_motions(self, api_key: str, domain: str, force: bool = False) -> OperationResult:
        """Refresh motions list from API.

        Args:
            api_key: API key for authentication
            domain: API domain
            force: If True, refresh even if cache is not stale

        Returns:
            OperationResult with success status
        """
        if not force and not self._cache.motions_stale():
            logger.debug("Using cached motions list")
            return OperationResult(success=True, message="Using cached motions")

        logger.info("Fetching motions from API...")
        result = client.list_motions(api_key, domain)

        if result.success and result.data:
            motions_data = result.data.get("motions", [])
            self._cache.motions = [
                MotionItem(
                    id=m.get("id", ""),
                    name=m.get("name", "Unnamed"),
                    created=m.get("created", ""),
                    is_favorite=m.get("is_favorite", False),
                )
                for m in motions_data
            ]
            self._cache.motions_fetched_at = time.time()
            logger.info("Fetched %d motions", len(self._cache.motions))
            return OperationResult(
                success=True,
                message=f"Fetched {len(self._cache.motions)} motions",
                data={"count": len(self._cache.motions)},
            )

        return result

    def refresh_characters(self, api_key: str, domain: str, force: bool = False) -> OperationResult:
        """Refresh characters list from API.

        Args:
            api_key: API key for authentication
            domain: API domain
            force: If True, refresh even if cache is not stale

        Returns:
            OperationResult with success status
        """
        if not force and not self._cache.characters_stale():
            logger.debug("Using cached characters list")
            return OperationResult(success=True, message="Using cached characters")

        logger.info("Fetching characters from API...")
        result = client.list_characters(api_key, domain)

        if result.success and result.data:
            characters_data = result.data.get("characters", [])
            self._cache.characters = [
                CharacterItem(
                    id=c.get("id", ""),
                    name=c.get("name", "Unnamed"),
                    created=c.get("created", ""),
                )
                for c in characters_data
            ]
            self._cache.characters_fetched_at = time.time()
            logger.info("Fetched %d characters", len(self._cache.characters))
            return OperationResult(
                success=True,
                message=f"Fetched {len(self._cache.characters)} characters",
                data={"count": len(self._cache.characters)},
            )

        return result

    def get_motions(self) -> List[MotionItem]:
        """Get cached motions list."""
        return self._cache.motions

    def get_favorite_motions(self) -> List[MotionItem]:
        """Get cached favorite motions only."""
        return [m for m in self._cache.motions if m.is_favorite]

    def get_characters(self) -> List[CharacterItem]:
        """Get cached characters list."""
        return self._cache.characters

    def find_motion_by_id(self, motion_id: str) -> Optional[MotionItem]:
        """Find a motion by ID in the cache."""
        for m in self._cache.motions:
            if m.id == motion_id:
                return m
        return None

    def find_character_by_id(self, character_id: str) -> Optional[CharacterItem]:
        """Find a character by ID in the cache."""
        for c in self._cache.characters:
            if c.id == character_id:
                return c
        return None

    def clear_cache(self) -> None:
        """Clear all cached data."""
        self._cache = AssetCache()
        logger.info("Asset cache cleared")
