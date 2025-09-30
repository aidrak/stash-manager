import logging

from flask import Blueprint, flash, jsonify, redirect, render_template, request, url_for

from src.config.config import get_config, set_setting
from src.core.logging_config import reconfigure_logging
from src.core.utils import set_active_page
from src.services.rule_sync_manager import RuleSyncManager

settings_bp = Blueprint("settings", __name__)
logger = logging.getLogger(__name__)


@settings_bp.route("/sync-settings", methods=["GET", "POST"])
def sync_settings():
    set_active_page("sync_settings")
    sync_manager = RuleSyncManager()

    if request.method == "POST":
        try:
            # Handle both JSON and form data for flexibility
            content_type = request.headers.get("Content-Type", "")
            if "application/json" in content_type:
                data = request.get_json()
            else:  # Default to form data
                data = request.form

            enabled = data.get("sync_enabled") in ["on", "true", True]
            direction = data.get("sync_direction", "add_to_clean")

            sync_manager.update_sync_settings(enabled, direction)

            return jsonify({"success": True, "message": "Sync settings updated successfully"})
        except ValueError as e:
            # This is raised by RuleSyncManager if rules are out of sync
            return jsonify({"success": False, "error": str(e)}), 400
        except Exception as e:
            logger.error(f"Error updating sync settings: {e}", exc_info=True)
            return jsonify({"success": False, "error": "An unexpected error occurred."}), 500

    sync_config = sync_manager.get_sync_settings()
    return render_template("sync_settings.html", sync_config=sync_config)


@settings_bp.route("/settings", methods=["GET", "POST"])
def settings():
    set_active_page("settings")
    config = get_config()

    if request.method == "POST":
        try:
            # Process job enable/disable settings
            jobs_updates = {}

            # Handle individual job enables
            add_new_scenes_enabled = "enable_add_new_scenes" in request.form
            clean_existing_scenes_enabled = "enable_clean_existing_scenes" in request.form
            identify_enabled = "enable_identify" in request.form
            generate_metadata_enabled = "enable_generate_metadata" in request.form

            # Update job configurations
            jobs_updates["add_new_scenes"] = {
                "enabled": add_new_scenes_enabled,
                "schedule": request.form.get("add_new_scenes_schedule", "daily"),
                "search_back_days": int(request.form.get("add_new_scenes_search_back_days", 7)),
            }

            jobs_updates["clean_existing_scenes"] = {
                "enabled": clean_existing_scenes_enabled,
                "schedule": request.form.get("clean_existing_scenes_schedule", "daily"),
            }

            jobs_updates["scan_and_identify"] = {
                "enabled": identify_enabled,
                "schedule": request.form.get("scan_and_identify_schedule", "daily"),
            }

            jobs_updates["generate_metadata"] = {
                "enabled": generate_metadata_enabled,
                "schedule": request.form.get("generate_metadata_schedule", "daily"),
            }

            # Handle identification sources
            identify_sources = []
            if "identify_source_stashdb" in request.form:
                identify_sources.append("stashdb")
            if "identify_source_tpdb" in request.form:
                identify_sources.append("tpdb")

            # Update general settings
            general_updates = {"dry_run": "dry_run" in request.form}

            # Update logs settings
            logs_updates = {"level": request.form.get("log_level", "INFO")}

            # Update identify settings
            identify_updates = {"sources": identify_sources}

            # Apply all updates
            for key, value in jobs_updates.items():
                set_setting("jobs", key, value)

            for key, value in general_updates.items():
                set_setting("general", key, value)

            for key, value in logs_updates.items():
                set_setting("logs", key, value)

            for key, value in identify_updates.items():
                set_setting("identify", key, value)

            # Reconfigure logging if level changed
            if "level" in logs_updates:
                reconfigure_logging(logs_updates["level"])

            flash("Settings updated successfully!", "success")
            logger.info("Settings updated successfully")

        except Exception as e:
            logger.error(f"Error updating settings: {e}")
            flash(f"Error updating settings: {str(e)}", "error")

        return redirect(url_for("settings.settings"))

    return render_template("settings.html", config=config)


@settings_bp.route("/check-sync-status")
def check_sync_status():
    """Check if sync is enabled and return status"""
    try:
        sync_manager = RuleSyncManager()
        in_sync, reason = sync_manager.are_rules_in_sync()

        return jsonify(
            {
                "in_sync": in_sync,
                "reason": reason,
            }
        )
    except Exception as e:
        logger.error(f"Error checking sync status: {e}")
        return jsonify({"in_sync": False, "reason": f"Error checking status: {str(e)}"})


@settings_bp.route("/manual-sync", methods=["POST"])
def manual_sync():
    """Manually trigger rule synchronization"""
    try:
        data = request.get_json()
        direction = data.get("direction")

        if not direction:
            return jsonify({"success": False, "error": "Direction required"})

        # Determine source and target contexts from direction
        if direction == "add_to_clean":
            source_context = "add_scenes"
            target_context = "clean_scenes"
        elif direction == "clean_to_add":
            source_context = "clean_scenes"
            target_context = "add_scenes"
        else:
            return jsonify({"success": False, "error": "Invalid direction"})

        # Get the source rules
        from src.config.config import get_filter_rules

        source_rules = get_filter_rules(source_context)

        sync_manager = RuleSyncManager()

        # Perform the sync
        sync_manager.sync_rules(source_context, source_rules)

        return jsonify(
            {"success": True, "message": f"Rules synced from {source_context} to {target_context}"}
        )

    except Exception as e:
        logger.error(f"Error during manual sync: {e}")
        return jsonify({"success": False, "error": str(e)})
