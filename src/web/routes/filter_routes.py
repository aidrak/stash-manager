import logging

from flask import Blueprint, flash, jsonify, redirect, request, url_for

from src.config.config import get_filter_rules, save_filter_rules
from src.core.validation import ValidationError, validate_filter_rule
from src.services.rule_sync_manager import RuleSyncManager

filter_bp = Blueprint("filters", __name__)


def _check_context_read_only(context: str) -> bool:
    """Check if context is read-only and flash error if so."""
    try:
        sync_manager = RuleSyncManager()
        if sync_manager.is_context_read_only(context):
            flash(
                (
                    f"Cannot modify rules in {context.replace('_', ' ').title()} - "
                    "this context is read-only due to Rule Sync settings. "
                    "Please modify rules in the source context or change sync direction."
                ),
                "error",
            )
            return True
    except Exception as e:
        logging.error(f"Error checking context read-only status: {e}", exc_info=True)
    return False


def _sync_if_enabled(source_context: str):
    """Check if sync is enabled and trigger it if necessary."""
    try:
        sync_manager = RuleSyncManager()
        if sync_manager.should_sync_rule(source_context):
            logging.info(f"Auto-syncing rules from {source_context}...")
            rules = get_filter_rules(source_context)
            sync_manager.sync_rules(source_context, rules)
            flash("Rules automatically synced to the other context.", "info")
    except Exception as e:
        logging.error(
            f"Error during auto-sync from {source_context}: {e}", exc_info=True
        )
        flash(f"Error during auto-sync: {e}", "warning")


@filter_bp.route("/add-scenes/add", methods=["POST"])
def add_add_scenes_rule():
    return _add_rule("add_scenes")


@filter_bp.route("/clean-scenes/add", methods=["POST"])
def add_clean_scenes_rule():
    return _add_rule("clean_scenes")


@filter_bp.route("/add-scenes/edit/<int:rule_index>", methods=["POST"])
def edit_add_scenes_rule(rule_index):
    return _edit_rule("add_scenes", rule_index)


@filter_bp.route("/clean-scenes/edit/<int:rule_index>", methods=["POST"])
def edit_clean_scenes_rule(rule_index):
    return _edit_rule("clean_scenes", rule_index)


@filter_bp.route("/add-scenes/delete/<int:rule_index>")
def delete_add_scenes_rule(rule_index):
    return _delete_rule("add_scenes", rule_index)


@filter_bp.route("/clean-scenes/delete/<int:rule_index>")
def delete_clean_scenes_rule(rule_index):
    return _delete_rule("clean_scenes", rule_index)


@filter_bp.route("/add-scenes/reorder", methods=["POST"])
def reorder_add_scenes_rules():
    return _reorder_rules("add_scenes")


@filter_bp.route("/clean-scenes/reorder", methods=["POST"])
def reorder_clean_scenes_rules():
    return _reorder_rules("clean_scenes")


def _add_rule(context):
    """Add a new filter rule"""
    # Check if context is read-only
    if _check_context_read_only(context):
        return redirect(url_for(f"main.{context}"))

    try:
        logging.info(f"Adding rule for context '{context}': {request.form.to_dict()}")
        validated_rule = validate_filter_rule(request.form)
        logging.info(f"Validated rule: {validated_rule}")
        rules = get_filter_rules(context)
        rules.append(validated_rule)
        save_filter_rules(rules, context)
        flash("Filter rule added successfully", "success")
        _sync_if_enabled(context)
    except ValidationError as e:
        logging.error(f"Validation error: {e}")
        flash(f"Validation error: {e}", "error")
    except Exception as e:
        logging.error(f"Error adding rule: {e}", exc_info=True)
        flash(f"Error adding rule: {e}", "error")

    return redirect(url_for(f"main.{context}"))


def _edit_rule(context, rule_index):
    """Edit an existing filter rule"""
    # Check if context is read-only
    if _check_context_read_only(context):
        return redirect(url_for(f"main.{context}"))

    try:
        rules = get_filter_rules(context)

        if not (0 <= rule_index < len(rules)):
            flash("Invalid rule index", "error")
            return redirect(url_for(f"main.{context}"))

        validated_rule = validate_filter_rule(request.form)
        rules[rule_index] = validated_rule
        save_filter_rules(rules, context)
        flash("Filter rule updated successfully", "success")
        _sync_if_enabled(context)
    except ValidationError as e:
        flash(f"Validation error: {e}", "error")
    except Exception as e:
        flash(f"Error updating rule: {e}", "error")

    return redirect(url_for(f"main.{context}"))


def _delete_rule(context, rule_index):
    """Delete a filter rule"""
    # Check if context is read-only
    if _check_context_read_only(context):
        return redirect(url_for(f"main.{context}"))

    rules = get_filter_rules(context)

    if 0 <= rule_index < len(rules):
        del rules[rule_index]
        save_filter_rules(rules, context)
        _sync_if_enabled(context)

    return redirect(url_for(f"main.{context}"))


def _reorder_rules(context):
    """Reorder filter rules based on new order"""
    # Check if context is read-only
    sync_manager = RuleSyncManager()
    if sync_manager.is_context_read_only(context):
        return jsonify(
            {
                "success": False,
                "error": (
                    f"Cannot reorder rules in {context.replace('_', ' ').title()} - "
                    "this context is read-only due to Rule Sync settings."
                ),
            }
        )

    rules = get_filter_rules(context)
    new_order = request.json.get("order", [])

    if len(new_order) == len(rules):
        reordered_rules = [rules[i] for i in new_order if 0 <= i < len(rules)]
        save_filter_rules(reordered_rules, context)
        _sync_if_enabled(context)
        return jsonify({"success": True})

    return jsonify({"success": False, "error": "Invalid order"})
