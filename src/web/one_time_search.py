# src/one_time_search.py

import logging
import threading
from datetime import datetime, timedelta
from typing import Dict  # Import Dict

from flask import Blueprint, jsonify, render_template, request

from src.api.stash_api import StashAPI
from src.config.config import get_config, get_database
from src.core.utils import set_active_page
from src.web.processor import add_new_scenes_to_whisparr

logger = logging.getLogger("stash_manager.one_time_search")

# Create the blueprint
one_time_search_bp = Blueprint("one_time_search", __name__, url_prefix="/one-time-search")

# ============================================================================
# GLOBAL JOB TRACKING (Module-level)
# ============================================================================

_job_lock = threading.Lock()
_active_jobs: Dict = {}  # Store job details
_job_progress: Dict = {}  # Store progress information

# ============================================================================
# JOB MANAGEMENT FUNCTIONS
# ============================================================================


def is_job_running(job_name):
    """Check if a specific job is currently running"""
    return job_name in _active_jobs


def get_job_details(job_name):
    """Get details about a running job"""
    return _active_jobs.get(job_name, {})


def acquire_job_lock(job_name, job_details=None):
    """Try to acquire lock for a job. Returns True if successful."""
    with _job_lock:
        if job_name in _active_jobs:
            return False
        _active_jobs[job_name] = job_details or {}
        _job_progress[job_name] = {
            "status": "starting",
            "progress": 0,
            "message": "Initializing...",
            "start_time": datetime.now().isoformat(),
            "scenes_processed": 0,
            "scenes_added": 0,
            "errors": [],
        }
        return True


def update_job_progress(job_name, **kwargs):
    """Update job progress information"""
    with _job_lock:
        if job_name in _job_progress:
            _job_progress[job_name].update(kwargs)


def release_job_lock(job_name):
    """Release lock for a job"""
    with _job_lock:
        _active_jobs.pop(job_name, None)
        # Keep progress info for a while after completion
        if job_name in _job_progress:
            _job_progress[job_name]["end_time"] = datetime.now().isoformat()


def get_job_progress(job_name):
    """Get current progress for a job"""
    return _job_progress.get(job_name, {})


# ============================================================================
# JOB EXECUTION FUNCTIONS
# ============================================================================


def one_time_search_job(start_date, end_date, search_config=None):
    """
    Enhanced one-time search with progress tracking and detailed logging
    """
    job_name = "one_time_search"
    job_details = {
        "start_date": start_date,
        "end_date": end_date,
        "config": search_config or {},
    }

    if not acquire_job_lock(job_name, job_details):
        logger.warning("One-time search already running - skipping")
        return

    # Extract dry_run flag from search_config
    dry_run = search_config.get("dry_run", False) if search_config else False

    # Record search in database
    db = get_database()
    search_id = db.record_one_time_search(start_date, end_date, "running")

    try:
        update_job_progress(
            job_name,
            status="loading_config",
            message="Loading configuration...",
            progress=5,
            dry_run=dry_run,  # Track dry run status in progress
        )

        config = get_config(strict=True)
        if not config:
            raise Exception("Could not load configuration")

        update_job_progress(
            job_name,
            status="connecting",
            message="Connecting to Stash...",
            progress=10,
            dry_run=dry_run,
        )

        import os

        stash_url = os.environ.get("STASH_URL")
        stash_api_key = os.environ.get("STASH_API_KEY")

        if not stash_url or not stash_api_key:
            raise Exception("Missing Stash configuration")

        stash_api = StashAPI(url=stash_url, api_key=stash_api_key)

        # Log dry run status prominently
        if dry_run:
            logger.info(
                f"🔍 DRY RUN: Searching scenes from {start_date} to {end_date} (no scenes "
                "will be added)"
            )
            update_job_progress(
                job_name,
                status="searching",
                message=(f"DRY RUN: Searching scenes from {start_date} to {end_date}..."),
                progress=20,
                dry_run=True,
            )
        else:
            logger.info(
                f"🔥 LIVE SEARCH: Searching and adding scenes from {start_date} to {end_date}"
            )
            update_job_progress(
                job_name,
                status="searching",
                message=(f"Searching scenes from {start_date} to {end_date}..."),
                progress=20,
                dry_run=False,
            )

        # Enhanced version of add_new_scenes_to_whisparr with progress callbacks
        def progress_callback(current, total, message=""):
            progress = 20 + int((current / total) * 70) if total > 0 else 20
            update_job_progress(
                job_name,
                progress=progress,
                message=message,
                scenes_processed=current,
                dry_run=dry_run,
            )

        # Call the processor with progress tracking AND dry_run flag
        result = add_new_scenes_to_whisparr_with_progress(
            config,
            stash_api,
            start_date=start_date,
            end_date=end_date,
            progress_callback=progress_callback,
            dry_run=dry_run,
            sort_direction="ASC",  # One-time search should start from oldest
        )

        # Log final status with dry run context
        if dry_run:
            status_message = (
                f"Dry run completed - {result.get('scenes_added', 0)} scenes would be added"
            )
            logger.info(f"💧 {status_message}")
        else:
            status_message = f"Search completed - {result.get('scenes_added', 0)} scenes added"
            logger.info(f"✅ {status_message}")

        update_job_progress(
            job_name,
            status="completed",
            message=status_message,
            progress=100,
            scenes_added=result.get("scenes_added", 0),
            total_found=result.get("total_found", 0),
            dry_run=dry_run,
        )

        # Update database record with dry_run info
        result["dry_run"] = dry_run
        db.finish_one_time_search(search_id, "completed", result)

        logger.info(f"One-time search completed: {start_date} to {end_date} (dry_run: {dry_run})")

    except Exception as e:
        error_msg = str(e)
        logger.error(f"Error in one-time search: {error_msg}")

        update_job_progress(
            job_name,
            status="failed",
            message=f"Search failed: {error_msg}",
            progress=0,
            dry_run=dry_run,
        )

        # Update database record
        db.finish_one_time_search(search_id, "failed", {"error": error_msg, "dry_run": dry_run})

    finally:
        release_job_lock(job_name)


def add_new_scenes_to_whisparr_with_progress(
    config,
    stash_api,
    start_date=None,
    end_date=None,
    progress_callback=None,
    dry_run=False,
    sort_direction: str = "ASC",  # Add sort_direction here
):
    """
    Enhanced version of add_new_scenes_to_whisparr with progress tracking.
    This is a wrapper around your existing processor function.
    """

    def update_progress(current: int, total: int, message: str = ""):
        """Helper to safely call progress callback"""
        if progress_callback:
            try:
                progress_callback(current, total, message)
            except Exception as e:
                logger.warning(f"Progress callback error: {e}")

    try:
        # Step 1: Initialize
        update_progress(0, 100, "Initializing search...")

        update_progress(10, 100, "Connecting to StashDB...")
        update_progress(20, 100, f"Searching scenes from {start_date} to {end_date}...")

        # Call your existing function
        result = add_new_scenes_to_whisparr(
            config,
            stash_api,
            start_date,
            end_date,
            progress_callback=progress_callback,
            dry_run=dry_run,
            sort_direction=sort_direction,  # Pass the sort_direction
        )

        update_progress(90, 100, "Finalizing results...")

        # Format results for consistency
        if not isinstance(result, dict):
            result = {"scenes_added": 0, "total_found": 0, "errors": []}

        scenes_added = result.get("scenes_added", 0)
        total_found = result.get("total_found", 0)

        update_progress(100, 100, f"Search completed! Added {scenes_added} of {total_found} scenes")

        return result

    except Exception as e:
        error_msg = f"Search failed: {str(e)}"
        logger.error(error_msg)
        update_progress(0, 100, error_msg)
        return {"scenes_added": 0, "total_found": 0, "errors": [error_msg]}


# ============================================================================
# BLUEPRINT ROUTES
# ============================================================================


@one_time_search_bp.route("/")
def one_time_search_page():
    """Main one-time search page"""
    set_active_page("one_time_search")
    db = get_database()

    # Get recent searches
    recent_searches = db.get_recent_one_time_searches(limit=10)

    # Get current job status
    current_job = get_job_details("one_time_search")
    job_progress = get_job_progress("one_time_search")

    # Get date presets
    today = datetime.now().date()
    presets = {
        "today": {
            "label": "Today",
            "start_date": today.isoformat(),
            "end_date": today.isoformat(),
        },
        "yesterday": {
            "label": "Yesterday",
            "start_date": (today - timedelta(days=1)).isoformat(),
            "end_date": (today - timedelta(days=1)).isoformat(),
        },
        "last_week": {
            "label": "Last Week",
            "start_date": (today - timedelta(days=7)).isoformat(),
            "end_date": today.isoformat(),
        },
        "last_month": {
            "label": "Last Month",
            "start_date": (today - timedelta(days=30)).isoformat(),
            "end_date": today.isoformat(),
        },
    }

    return render_template(
        "one_time_search.html",
        recent_searches=recent_searches,
        current_job=current_job,
        job_progress=job_progress,
        presets=presets,
    )


@one_time_search_bp.route("/start", methods=["POST"])
def start_one_time_search():
    """Start a new one-time search"""
    try:
        start_date = request.form.get("start_date")
        end_date = request.form.get("end_date")
        dry_run = "dry_run" in request.form

        # Validation
        if not start_date or not end_date:
            return jsonify({"success": False, "message": "Both start and end dates are required"})

        try:
            start_dt = datetime.strptime(start_date, "%Y-%m-%d")
            end_dt = datetime.strptime(end_date, "%Y-%m-%d")

            if start_dt > end_dt:
                return jsonify({"success": False, "message": "Start date must be before end date"})

            if end_dt > datetime.now():
                return jsonify({"success": False, "message": "End date cannot be in the future"})

        except ValueError:
            return jsonify({"success": False, "message": "Invalid date format"})

        # Check for conflicts
        if is_job_running("one_time_search"):
            return jsonify({"success": False, "message": "One-time search already running"})

        # Check if main app has any scheduled jobs running
        # Import this from your main app if you want to check conflicts
        # if main_app.is_job_running("add_new_scenes_scheduled"):
        #     return jsonify({'success': False, 'message': 'Scheduled add scenes job is running'})

        # Start the search
        search_config = {"dry_run": dry_run}
        job_thread = threading.Thread(
            target=one_time_search_job,
            args=(start_date, end_date, search_config),
            name=f"OneTimeSearch-{start_date}-{end_date}",
        )
        job_thread.daemon = True
        job_thread.start()

        return jsonify(
            {
                "success": True,
                "message": f"Search started for {start_date} to {end_date}",
                "dry_run": dry_run,
            }
        )

    except Exception as e:
        logger.error(f"Error starting one-time search: {e}")
        return jsonify({"success": False, "message": str(e)})


@one_time_search_bp.route("/progress")
def one_time_search_progress():
    """Get current progress of one-time search"""
    job_progress = get_job_progress("one_time_search")
    is_running = is_job_running("one_time_search")

    return jsonify({"is_running": is_running, "progress": job_progress})


@one_time_search_bp.route("/cancel")
def cancel_one_time_search():
    """Cancel running one-time search"""
    if is_job_running("one_time_search"):
        release_job_lock("one_time_search")
        update_job_progress(
            "one_time_search", status="cancelled", message="Search cancelled by user"
        )
        return jsonify({"success": True, "message": "Search cancelled"})
    else:
        return jsonify({"success": False, "message": "No search running"})


@one_time_search_bp.route("/history")
def one_time_search_history():
    """Get detailed search history"""
    db = get_database()
    searches = db.get_recent_one_time_searches(limit=50)
    return jsonify({"searches": searches})


@one_time_search_bp.route("/rerun/<int:search_id>")
def rerun_one_time_search(search_id):
    """Rerun a previous search"""
    db = get_database()
    search = db.get_one_time_search(search_id)

    if not search:
        return jsonify({"success": False, "message": "Search not found"})

    if is_job_running("one_time_search"):
        return jsonify({"success": False, "message": "Another search is already running"})

    # Start the same search again
    job_thread = threading.Thread(
        target=one_time_search_job,
        args=(search["start_date"], search["end_date"]),
        name=f"Rerun-{search['start_date']}-{search['end_date']}",
    )
    job_thread.daemon = True
    job_thread.start()

    return jsonify(
        {
            "success": True,
            "message": f"Rerunning search for {search['start_date']} to {search['end_date']}",
        }
    )


# ============================================================================
# UTILITY FUNCTIONS FOR EXTERNAL ACCESS
# ============================================================================


def is_one_time_search_running():
    """Utility function for main app to check if one-time search is running"""
    return is_job_running("one_time_search")
