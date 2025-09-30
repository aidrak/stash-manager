import logging
import os

from src.database_manager import DatabaseManager

# Global database instance
_db = None


def get_database() -> DatabaseManager:
    """Get the global database instance."""
    global _db
    if _db is None:
        db_path = os.environ.get("DATABASE_PATH", "/config/stash_manager.db")
        _db = DatabaseManager(db_path)
    return _db


def validate_config(config, strict=True):
    """Validates the provided configuration."""
    if not config:
        return False

    if strict:
        # Check required environment variables instead of config
        if not os.environ.get("STASH_URL") or not os.environ.get("STASH_API_KEY"):
            logging.error(
                "Stash URL and API key are required. Set STASH_URL and "
                "STASH_API_KEY environment variables."
            )
            return False

        if not os.environ.get("WHISPARR_URL") or not os.environ.get("WHISPARR_API_KEY"):
            logging.error(
                "Whisparr URL and API key are required. Set WHISPARR_URL and "
                "WHISPARR_API_KEY environment variables."
            )
            return False

    return True


def get_config(strict=True):
    """Loads configuration from database and overrides with environment variables."""
    db = get_database()

    try:
        # Get all settings from database
        settings = db.get_all_settings()

        # Build config structure similar to old YAML format
        config = {
            "stash": {
                "url": os.environ.get("STASH_URL"),
                "api_key": os.environ.get("STASH_API_KEY"),
            },
            "whisparr": {
                "url": os.environ.get("WHISPARR_URL"),
                "api_key": os.environ.get("WHISPARR_API_KEY"),
                "root_folder": os.environ.get("WHISPARR_ROOT_FOLDER", "/data"),
            },
            "jobs": {
                "add_new_scenes": settings.get("jobs", {}).get(
                    "add_new_scenes",
                    {"enabled": True, "schedule": "daily", "search_back_days": 7},
                ),
                "clean_existing_scenes": settings.get("jobs", {}).get(
                    "clean_existing_scenes", {"enabled": False, "schedule": "daily"}
                ),
                "scan_and_identify": settings.get("jobs", {}).get(
                    "scan_and_identify", {"enabled": False, "schedule": "daily"}
                ),
                "generate_metadata": settings.get("jobs", {}).get(
                    "generate_metadata", {"enabled": False, "schedule": "daily"}
                ),
            },
            "general": settings.get("general", {"dry_run": True}),
            "identify": settings.get("identify", {"enabled": False, "sources": []}),
            "logs": settings.get("logs", {"level": "INFO"}),
            "one_time_search": settings.get("one_time_search", {"start_date": "", "end_date": ""}),
            # Filter engine now comes from database via separate functions
            "filter_engine": {
                "add_scenes": {"rules": get_filter_rules("add_scenes")},
                "clean_scenes": {"rules": get_filter_rules("clean_scenes")},
            },
        }

        if not validate_config(config, strict=strict):
            if strict:
                logging.error("Configuration validation failed.")
                return None
            else:
                logging.warning(
                    "Configuration validation failed, but continuing in non-strict mode."
                )

        logging.info("Configuration loaded from database successfully.")
        return config

    except Exception as e:
        logging.error(f"Failed to load configuration from database: {e}")
        return None


def get_filter_rules(context: str):
    """Get filter rules for a specific context from database."""
    db = get_database()
    rules = db.get_filter_rules(context)

    # Convert database format to old YAML format for compatibility
    yaml_rules = []
    for rule in rules:
        yaml_rule = {
            "name": rule["name"],
            "field": rule["field"],
            "match": rule["operator"],  # Database uses 'operator', YAML used 'match'
            "value": rule["value"],
            "action": rule["action"],
        }
        yaml_rules.append(yaml_rule)

    return yaml_rules


def save_filter_rules(rules: list, context: str):
    """Save filter rules to database (for backward compatibility)."""
    db = get_database()

    # Clear existing rules for this context
    existing_rules = db.get_filter_rules(context)
    for rule in existing_rules:
        db.delete_filter_rule(rule["id"])

    # Add new rules
    for rule in rules:
        db.add_filter_rule(
            context=context,
            name=rule.get("name", "Rule"),
            field=rule.get("field", ""),
            operator=rule.get("match", "include"),  # Convert 'match' to 'operator'
            value=rule.get("value", ""),
            action=rule.get("action", "reject"),
        )


def get_setting(section: str, key: str, default=None):
    """Get a single setting value."""
    db = get_database()
    return db.get_setting(section, key, default)


def set_setting(section: str, key: str, value):
    """Set a single setting value."""
    db = get_database()
    db.set_setting(section, key, value)


def get_job_timeout():
    """Returns the job timeout in seconds."""
    return get_setting("processing", "job_timeout", 1800)


def get_poll_interval():
    """Returns the poll interval in seconds."""
    return get_setting("processing", "poll_interval", 10)


def get_scene_limit():
    """Returns the scene limit for fetching from Stash."""
    return get_setting("processing", "scene_limit", 10000)


def get_performer_limit():
    """Returns the performer limit for fetching from Stash."""
    return get_setting("processing", "performer_limit", 5000)


def get_identify_sources():
    """Returns the list of identification sources."""
    return get_setting("identify", "sources", [])


# Job run tracking functions
def start_job_run(job_name: str, dry_run: bool = False) -> int:
    """Start tracking a job run."""
    db = get_database()
    return db.start_job_run(job_name, dry_run)


def finish_job_run(job_run_id: int, status: str, **kwargs):
    """Finish tracking a job run."""
    db = get_database()
    db.finish_job_run(job_run_id, status, **kwargs)


def get_last_job_run_time(job_name: str):
    """Get the last run time for a job."""
    db = get_database()
    last_run = db.get_last_job_run(job_name)
    if last_run:
        return last_run["start_time"]
    return None
