import logging
from typing import Tuple

from src.filters.filter import _check_condition, _get_value_from_path

logger = logging.getLogger("stash_manager.clean_scenes_filter")


class CleanScenesFilter:
    """
    Filter engine specifically for cleaning scenes from local Stash.
    Uses Local Stash data structure and conservative logic.
    Default: ACCEPT (only delete explicitly rejected scenes)
    """

    def __init__(self, config: dict, conditions: dict):
        self.conditions = conditions
        logger.info("Initialized CleanScenesFilter")

    def should_keep_scene(self, scene: dict) -> Tuple[bool, str]:
        """
        Evaluates if a scene in local Stash should be kept.
        Conservative approach: only delete scenes that explicitly match 'reject' rules.
        """
        # Get rules directly from database instead of from config
        from src.config.config import get_filter_rules

        rules = get_filter_rules("clean_scenes")

        scene_title = scene.get("title", "Untitled")
        logger.debug(f"Filtering scene for cleaning: {scene_title}")

        if not rules:
            logger.warning("No clean_scenes rules found - will keep by default")

        # Process rules in order - first match wins
        for i, rule in enumerate(rules):
            rule_name = rule.get("name", f"Rule {i + 1}")

            field = rule.get("field")
            operator = rule.get("match")
            value = rule.get("value")
            action = rule.get("action", "accept")  # Default to accept for safety

            if not all([field, operator]):
                logger.warning(f"Skipping malformed rule '{rule_name}'")
                continue

            scene_value = _get_value_from_path(scene, field)
            condition_matches, matched_value = _check_condition(scene_value, operator, value, field)

            if condition_matches:
                field_label = self.conditions.get(field, {}).get("label", field)

                display_value = matched_value
                if isinstance(matched_value, dict) and "name" in matched_value:
                    display_value = matched_value["name"]

                reason = f"{field_label} {operator} {display_value}"

                if action.lower() == "reject":
                    logger.debug(f"Scene '{scene_title}' REJECTED by rule '{rule_name}': {reason}")
                    return False, f"Rejected: {reason}"
                else:
                    logger.debug(f"Scene '{scene_title}' ACCEPTED by rule '{rule_name}': {reason}")
                    return True, f"Accepted: {reason}"

        # No rules matched - default ACCEPT for safety (preserve curated library)
        logger.debug(f"Scene '{scene_title}' did not match any rules and will be kept by default.")
        return True, "No rules matched - default keep"
