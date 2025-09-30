import logging
from typing import Dict, List, Tuple

from src.config.config import get_database

logger = logging.getLogger("stash_manager.rule_sync")


class RuleSyncManager:
    """Manages synchronization of filter rules between add_scenes and clean_scenes contexts."""

    # Hardcoded field mappings - no customization needed
    FIELD_MAPPINGS = {
        "performers.performer.name": "performers.name",
        "performers.performer.ethnicity": "performers.ethnicity",
        "performers.performer.gender": "performers.gender",
        "performers.performer.measurements.cup_size": "performers.cup_size",
        "performers.performer.measurements.waist": "performers.waist",
        "performers.performer.measurements.hip": "performers.hip",
        "studio.name": "studio.name",
        "title": "title",
        "date": "date",
        "tags": "tags",
        "performers.count": "performers.count",
    }

    def __init__(self):
        self.db = get_database()
        self._load_sync_settings()

    def _load_sync_settings(self):
        """Load sync settings from database."""
        # First, ensure the table exists
        self.db.execute_query("""
            CREATE TABLE IF NOT EXISTS rule_sync_settings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                sync_enabled BOOLEAN DEFAULT 0,
                sync_direction TEXT CHECK(sync_direction IN (
        'add_to_clean', 'clean_to_add', 'bidirectional'
    )) DEFAULT 'add_to_clean',
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)

        row = self.db.execute_query(
            "SELECT sync_enabled, sync_direction FROM rule_sync_settings LIMIT 1", fetch="one"
        )

        if row:
            self.sync_enabled, self.sync_direction = row
        else:
            # Default settings - create them
            self.sync_enabled = False
            self.sync_direction = "add_to_clean"

            # Insert default settings
            self.db.execute_query(
                """INSERT INTO rule_sync_settings
                   (sync_enabled, sync_direction)
                   VALUES (?, ?)""",
                (self.sync_enabled, self.sync_direction),
            )

    def get_sync_settings(self) -> Dict:
        """Get current sync settings."""
        self._load_sync_settings()
        return {"enabled": self.sync_enabled, "direction": self.sync_direction}

    def map_field(self, field: str, from_context: str, to_context: str) -> str:
        """Map a field from one context to another."""
        if from_context == "add_scenes" and to_context == "clean_scenes":
            return self.FIELD_MAPPINGS.get(field, field)
        elif from_context == "clean_scenes" and to_context == "add_scenes":
            # Reverse mapping
            reverse_mappings = {v: k for k, v in self.FIELD_MAPPINGS.items()}
            return reverse_mappings.get(field, field)
        return field

    def convert_rule(self, rule: Dict, from_context: str, to_context: str) -> Dict:
        """Convert a rule from one context to another."""
        converted_rule = rule.copy()
        converted_rule["field"] = self.map_field(rule["field"], from_context, to_context)
        return converted_rule

    def are_rules_in_sync(self) -> Tuple[bool, str]:
        """Check if add_scenes and clean_scenes rules are currently in sync."""
        from src.config.config import get_filter_rules

        add_rules = get_filter_rules("add_scenes")
        clean_rules = get_filter_rules("clean_scenes")

        # If both are empty, they're in sync
        if not add_rules and not clean_rules:
            return True, "Both contexts have no rules"

        # If only one has rules, they're not in sync
        if len(add_rules) != len(clean_rules):
            return (
                False,
                f"Rule count mismatch: {len(add_rules)} add rules "
                f"vs {len(clean_rules)} clean rules",
            )

        # Convert add rules to clean format and compare
        for i, add_rule in enumerate(add_rules):
            converted_rule = self.convert_rule(add_rule, "add_scenes", "clean_scenes")
            clean_rule = clean_rules[i]

            # Compare the essential fields
            if (
                converted_rule["field"] != clean_rule["field"]
                or converted_rule.get("match", converted_rule.get("operator"))
                != clean_rule.get("match", clean_rule.get("operator"))
                or converted_rule.get("value") != clean_rule.get("value")
                or converted_rule.get("action") != clean_rule.get("action")
            ):
                return (
                    False,
                    f"Rule {i + 1} mismatch: Add rule converts to different values than Clean rule",
                )

        return True, "All rules are in sync"

    def update_sync_settings(self, enabled: bool, direction: str):
        """Update sync settings."""
        # If trying to enable, check if rules are in sync first
        if enabled and not self.sync_enabled:
            in_sync, reason = self.are_rules_in_sync()
            if not in_sync:
                raise ValueError(
                    f"Rules must be in sync before enabling Rule Synchronization. {reason}"
                )

        # Save to database
        self.db.execute_query(
            """INSERT OR REPLACE INTO rule_sync_settings
               (id, sync_enabled, sync_direction, updated_at)
               VALUES (1, ?, ?, CURRENT_TIMESTAMP)""",
            (enabled, direction),
        )

        # Reload settings after update
        self._load_sync_settings()

    def should_sync_rule(self, source_context: str) -> bool:
        """Check if rules should be synced from the given context."""
        if not self.sync_enabled:
            return False

        if self.sync_direction == "bidirectional":
            return True
        elif self.sync_direction == "add_to_clean" and source_context == "add_scenes":
            return True
        elif self.sync_direction == "clean_to_add" and source_context == "clean_scenes":
            return True

        return False

    def is_context_read_only(self, context: str) -> bool:
        """Check if the given context should be read-only due to sync settings."""
        if not self.sync_enabled:
            return False

        if self.sync_direction == "bidirectional":
            return False  # Both contexts can be edited in bidirectional mode
        elif self.sync_direction == "add_to_clean" and context == "clean_scenes":
            return True  # clean_scenes is read-only when syncing from add_scenes
        elif self.sync_direction == "clean_to_add" and context == "add_scenes":
            return True  # add_scenes is read-only when syncing from clean_scenes

        return False

    def sync_rules(self, source_context: str, rules: List[Dict]):
        """Sync rules from source context to target context."""
        logger.info(f"Starting sync_rules from {source_context} with {len(rules)} rules.")

        target_context = "clean_scenes" if source_context == "add_scenes" else "add_scenes"

        logger.info(f"Syncing {len(rules)} rules from {source_context} to {target_context}")

        # Clear existing rules in target context
        logger.info(f"Deleting existing rules from {target_context}")
        self.db.execute_query("DELETE FROM filter_rules WHERE context = ?", (target_context,))

        # Convert and add rules to target context
        for i, rule in enumerate(rules):
            converted_rule = self.convert_rule(rule, source_context, target_context)
            logger.debug(f"Adding rule {i + 1} to {target_context}: {converted_rule}")
            self.db.add_filter_rule(
                context=target_context,
                name=converted_rule.get("name", f"Synced Rule {i + 1}"),
                field=converted_rule["field"],
                operator=converted_rule.get("match", converted_rule.get("operator", "include")),
                value=converted_rule.get("value", ""),
                action=converted_rule.get("action", "reject"),
                priority=i,
            )

        logger.info(f"Successfully synced {len(rules)} rules to {target_context}")
