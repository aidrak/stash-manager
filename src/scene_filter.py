"""
Scene Filter Module

This module implements the filtering logic for scenes based on performer attributes
"""

import logging
import re
from typing import Dict, Tuple

logger = logging.getLogger("stash_manager.filter")


class SceneFilter:
    """Filter scenes based on configurable criteria"""

    def __init__(self, config: Dict):
        """Initialize the scene filter

        Args:
            config: Filter configuration settings
        """
        self.config = config
        self.filters = config.get("filters", {})

        # Extract ethnicity filter configuration
        self.ethnicity_config = self.filters.get("ethnicity", {})
        self.ethnicity_enabled = self.ethnicity_config.get("enabled", True)
        self.ethnicity_values = self.ethnicity_config.get("values", [])

        # Extract cup size filter configuration
        self.cup_size_config = self.filters.get("cup_size", {})
        self.cup_size_enabled = self.cup_size_config.get("enabled", True)
        self.small_cup_pattern = self.cup_size_config.get("small_cup_pattern", "")
        self.larger_cup_pattern = self.cup_size_config.get("larger_cup_pattern", "")
        self.exceptions_to_large = self.cup_size_config.get("exceptions_to_large", [])
        self.force_to_small = self.cup_size_config.get("force_to_small", [])

        # Extract title keyword filter configuration - FIXED THIS LINE
        # Now checking at top level of config instead of under filters
        self.keyword_config = config.get("unwanted_keywords", {})
        self.keyword_enabled = self.keyword_config.get("enabled", False)
        self.keywords = self.keyword_config.get("keywords", [])
        self.case_sensitive = self.keyword_config.get("case_sensitive", False)

        logger.info(f"Initialized scene filter with {len(self.ethnicity_values)} ethnicity values")
        logger.info(
            f"Cup size exceptions: {len(self.exceptions_to_large)} large, {len(self.force_to_small)} small"  # noqa: E501
        )
        logger.info(
            f"Keyword filter enabled: {self.keyword_enabled} with {len(self.keywords)} keywords: {self.keywords}"  # noqa: E501
        )

    def should_remove_scene(self, scene_data: Dict) -> Tuple[bool, str]:
        """Determine if a scene should be removed based on filter criteria

        Args:
            scene_data: Scene data from Stash API

        Returns:
            Tuple of (should_remove, reason)
        """
        scene_id = scene_data.get("id", "unknown")
        title = scene_data.get("title", "unknown")
        performers = scene_data.get("performers", [])

        # First check title keywords if enabled
        if self.keyword_enabled and self.keywords:
            logger.info(f"Checking title keywords for scene {scene_id} ({title})")
            contains_keyword, reason = self._check_title_keywords(scene_data)
            if contains_keyword:
                logger.info(f"Scene {scene_id} ({title}) matched keyword filter: {reason}")
                return True, reason
            else:
                logger.debug(f"Scene {scene_id} ({title}) passed keyword filter")
        else:
            logger.debug(f"Keyword filter disabled or empty, skipping for scene {scene_id}")

        # Skip if scene has no performers
        if not performers:
            logger.debug(f"Scene {scene_id} ({title}) has no performers, keeping")
            return False, "No performers to filter"

        # Apply ethnicity filter if enabled
        if self.ethnicity_enabled:
            for performer in performers:
                name = performer.get("name", "unknown")
                ethnicity = performer.get("ethnicity", "")

                # Check if ethnicity is in our list of filtered values
                if ethnicity and any(
                    value.lower() in ethnicity.lower() for value in self.ethnicity_values
                ):
                    reason = f"Performer {name} has filtered ethnicity: {ethnicity}"
                    logger.info(f"Scene {scene_id} ({title}) will be removed: {reason}")
                    return True, reason

        # Apply cup size filter if enabled
        if self.cup_size_enabled:
            # Check for females with large cup sizes or unknown cup sizes
            has_female = False
            has_large_cup = False
            has_unknown_cup = False
            small_cup_performers = []

            for performer in performers:
                # FIX: Safe handling of gender - use an empty string if gender is None
                gender = (performer.get("gender") or "").lower()
                name = performer.get("name", "unknown")
                measurements = performer.get("measurements", "")

                # Skip males for cup size check
                if gender == "male":
                    continue

                # Mark as having female performer
                has_female = True

                # Check exceptions first
                if name in self.exceptions_to_large:
                    logger.debug(f"Performer {name} is in exceptions_to_large list")
                    has_large_cup = True
                    continue

                if name in self.force_to_small:
                    logger.debug(f"Performer {name} is in force_to_small list")
                    small_cup_performers.append(name)
                    continue

                # If no measurements info, count as unknown
                if not measurements:
                    logger.debug(f"Performer {name} has no measurements info")
                    has_unknown_cup = True
                    continue

                # Check if performer has large cup size
                if re.search(self.larger_cup_pattern, measurements):
                    logger.debug(f"Performer {name} has large cup size: {measurements}")
                    has_large_cup = True
                # Check if performer has small cup size
                elif re.search(self.small_cup_pattern, measurements):
                    logger.debug(f"Performer {name} has small cup size: {measurements}")
                    small_cup_performers.append(name)
                else:
                    # If we can't determine from the pattern, treat as unknown
                    logger.debug(f"Performer {name} has unknown cup size: {measurements}")
                    has_unknown_cup = True

            # If scene has female performers but none have large cup or unknown cup sizes
            if has_female and not has_large_cup and not has_unknown_cup and small_cup_performers:
                reason = f"Scene only has small cup performers: {', '.join(small_cup_performers)}"
                logger.info(f"Scene {scene_id} ({title}) will be removed: {reason}")
                return True, reason

        # If we get here, scene passes all filters
        logger.debug(f"Scene {scene_id} ({title}) passes all filters, keeping")
        return False, "Passed all filters"

    def _check_title_keywords(self, scene_data: Dict) -> Tuple[bool, str]:
        """Check if scene title contains any unwanted keywords"""
        scene_id = scene_data.get("id", "unknown")
        title = scene_data.get("title", "")

        if not title:
            logger.debug(f"Scene {scene_id} has no title to check")
            return False, "No title to check"

        # Check each keyword
        for keyword in self.keywords:
            if self.case_sensitive:
                if keyword in title:
                    reason = f"Title contains unwanted keyword: '{keyword}'"
                    logger.info(f"Scene {scene_id} ({title}) matched keyword: {keyword}")
                    return True, reason
            else:
                if keyword.lower() in title.lower():
                    reason = f"Title contains unwanted keyword: '{keyword}'"
                    logger.info(f"Scene {scene_id} ({title}) matched keyword: {keyword}")
                    return True, reason

        # If no keywords matched
        logger.debug(f"Scene {scene_id} ({title}) passes keyword filter")
        return False, "No unwanted keywords in title"
