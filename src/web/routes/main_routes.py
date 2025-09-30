from flask import Blueprint, redirect, render_template, url_for

from src.config.config import get_filter_rules
from src.filters.conditions.local_stash_conditions import LOCAL_STASH_CONDITIONS
from src.filters.conditions.stashdb_conditions import STASHDB_CONDITIONS
from src.services.rule_sync_manager import RuleSyncManager

main_bp = Blueprint("main", __name__)

# Filter contexts for different operations
FILTER_CONTEXTS = {
    "add_scenes": {
        "label": "Add New Scenes",
        "description": (
            "Rules for adding new scenes from StashDB to Whisparr (Conservative: "
            "only add explicit accepts)"
        ),
    },
    "clean_scenes": {
        "label": "Clean Existing Scenes",
        "description": (
            "Rules for removing scenes from local Stash (Conservative: "
            "only delete explicit rejects)"
        ),
    },
}


@main_bp.route("/")
def index():
    return redirect(url_for("main.add_scenes"))


@main_bp.route("/add-scenes")
def add_scenes():
    filter_rules = get_filter_rules("add_scenes")
    sync_manager = RuleSyncManager()
    is_read_only = sync_manager.is_context_read_only("add_scenes")
    sync_settings = sync_manager.get_sync_settings()

    return render_template(
        "add_scenes.html",
        filter_rules=filter_rules,
        conditions=STASHDB_CONDITIONS,
        filter_context=FILTER_CONTEXTS["add_scenes"],
        active_page="add_scenes",
        is_read_only=is_read_only,
        sync_settings=sync_settings,
    )


@main_bp.route("/clean-scenes")
def clean_scenes():
    filter_rules = get_filter_rules("clean_scenes")
    sync_manager = RuleSyncManager()
    is_read_only = sync_manager.is_context_read_only("clean_scenes")
    sync_settings = sync_manager.get_sync_settings()

    import logging

    logging.info(f"Rendering clean_scenes.html with {len(filter_rules)} rules: {filter_rules}")
    return render_template(
        "clean_scenes.html",
        rules=filter_rules,
        conditions=LOCAL_STASH_CONDITIONS,
        active_page="clean_scenes",
        filter_context=FILTER_CONTEXTS["clean_scenes"],
        is_read_only=is_read_only,
        sync_settings=sync_settings,
    )
