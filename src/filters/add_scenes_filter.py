import logging
from typing import Tuple

from src.filters.filter import _check_condition, _get_value_from_path

logger = logging.getLogger("stash_manager.add_scenes_filter")


class AddScenesFilter:
    """
    Filter engine specifically for adding scenes from StashDB to Whisparr.
    Uses StashDB data structure and conservative logic.
    Default: REJECT (only add explicitly accepted scenes)
    """

    def __init__(self, config: dict, conditions: dict):
        # Get rules directly from database instead of from config
        from src.config.config import get_filter_rules

        rules = get_filter_rules("add_scenes")
        self.filter_config = {"rules": rules}
        self.conditions = conditions
        logger.info(f"Initialized AddScenesFilter with {len(rules)} rules from database")

    def should_add_scene(self, scene: dict) -> Tuple[bool, str]:
        """
        Evaluates if a scene from StashDB should be added to Whisparr.
        Conservative approach: only add scenes that explicitly match 'accept' rules.
        """
        scene_title = scene.get("title", "Untitled")
        logger.debug(f"Filtering scene for addition: {scene_title}")

        rules = self.filter_config.get("rules", [])
        if not rules:
            logger.warning("No add_scenes rules found - will reject by default")

        # Process rules in order - first match wins
        for i, rule in enumerate(rules):
            rule_name = rule.get("name", f"Rule {i + 1}")

            field = rule.get("field")
            operator = rule.get("match")
            value = rule.get("value")
            action = rule.get("action", "reject")

            if not all([field, operator]):
                logger.warning(f"Skipping malformed rule '{rule_name}'")
                continue

            scene_value = _get_value_from_path(scene, field)
            condition_matches, matched_value = _check_condition(scene_value, operator, value, field)

            if condition_matches:
                field_label = self.conditions.get(field, {}).get("label", field)
                reason = f"{field_label} {operator} {matched_value}"

                if action.lower() == "accept":
                    logger.debug(f"Scene '{scene_title}' ACCEPTED by rule '{rule_name}': {reason}")
                    return True, f"Accepted: {reason}"
                else:
                    logger.debug(f"Scene '{scene_title}' REJECTED by rule '{rule_name}': {reason}")
                    return False, f"Rejected: {reason}"

        # No rules matched - default REJECT for safety
        logger.debug(f"Scene '{scene_title}' did not match any rules → REJECT (add_scenes default)")
        return False, "No rules matched - default reject"
