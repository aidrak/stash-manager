"""
Prowlarr job management routes
"""

import logging
import threading
from datetime import datetime

from flask import Blueprint, jsonify, render_template, request

from src.api.stash_api import StashAPI
from src.config.config import get_config
from src.core.utils import set_active_page
from src.web.processor import add_new_scenes_with_prowlarr

logger = logging.getLogger("stash_manager.prowlarr_routes")

# Create the blueprint
prowlarr_bp = Blueprint("prowlarr", __name__, url_prefix="/prowlarr")

# Job tracking for Prowlarr searches
_prowlarr_job_lock = threading.Lock()
_prowlarr_active_jobs = {}
_prowlarr_job_progress = {}


def is_prowlarr_job_running(job_name):
    """Check if a Prowlarr job is currently running"""
    return job_name in _prowlarr_active_jobs


def acquire_prowlarr_job_lock(job_name, job_details=None):
    """Try to acquire lock for a Prowlarr job. Returns True if successful."""
    with _prowlarr_job_lock:
        if job_name in _prowlarr_active_jobs:
            return False
        _prowlarr_active_jobs[job_name] = job_details or {}
        _prowlarr_job_progress[job_name] = {
            "status": "starting",
            "progress": 0,
            "message": "Initializing Prowlarr search...",
            "start_time": datetime.now().isoformat(),
            "scenes_processed": 0,
            "scenes_downloaded": 0,
            "errors": [],
        }
        return True


def update_prowlarr_job_progress(job_name, **kwargs):
    """Update Prowlarr job progress information"""
    with _prowlarr_job_lock:
        if job_name in _prowlarr_job_progress:
            _prowlarr_job_progress[job_name].update(kwargs)


def release_prowlarr_job_lock(job_name):
    """Release lock for a Prowlarr job"""
    with _prowlarr_job_lock:
        _prowlarr_active_jobs.pop(job_name, None)
        if job_name in _prowlarr_job_progress:
            _prowlarr_job_progress[job_name]["end_time"] = datetime.now().isoformat()


def get_prowlarr_job_progress(job_name):
    """Get current progress for a Prowlarr job"""
    return _prowlarr_job_progress.get(job_name, {})


def prowlarr_search_job(start_date=None, end_date=None, dry_run=False):
    """
    Execute Prowlarr search job in background thread
    """
    job_name = "prowlarr_search"
    job_details = {
        "start_date": start_date,
        "end_date": end_date,
        "dry_run": dry_run,
    }

    if not acquire_prowlarr_job_lock(job_name, job_details):
        logger.warning("Prowlarr search already running - skipping")
        return

    try:
        update_prowlarr_job_progress(
            job_name,
            status="loading_config",
            message="Loading configuration...",
            progress=5,
            dry_run=dry_run,
        )

        config = get_config(strict=True)
        if not config:
            raise Exception("Could not load configuration")

        # Check if Prowlarr is enabled
        if not config.get("prowlarr", {}).get("enabled", False):
            raise Exception("Prowlarr is not enabled in configuration")

        update_prowlarr_job_progress(
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

        # Progress callback for the processor
        def progress_callback(current, total, message=""):
            progress = 10 + int((current / total) * 80) if total > 0 else 10
            update_prowlarr_job_progress(
                job_name,
                progress=progress,
                message=message,
                scenes_processed=current,
                dry_run=dry_run,
            )

        logger.info(
            f"Starting Prowlarr search job: {start_date} to {end_date} (dry_run: {dry_run})"
        )

        # Call the Prowlarr processor
        result = add_new_scenes_with_prowlarr(
            config,
            stash_api,
            start_date=start_date,
            end_date=end_date,
            progress_callback=progress_callback,
            dry_run=dry_run,
            sort_direction="ASC",
        )

        if "error" in result:
            raise Exception(result["error"])

        status_message = (
            f"Prowlarr search completed - {result.get('scenes_downloaded', 0)} scenes downloaded"
        )
        logger.info(f"✅ {status_message}")

        update_prowlarr_job_progress(
            job_name,
            status="completed",
            message=status_message,
            progress=100,
            scenes_downloaded=result.get("scenes_downloaded", 0),
            total_found=result.get("total_found", 0),
            dry_run=dry_run,
        )

        logger.info(f"Prowlarr search completed: {start_date} to {end_date} (dry_run: {dry_run})")

    except Exception as e:
        error_msg = str(e)
        logger.error(f"Error in Prowlarr search: {error_msg}")

        update_prowlarr_job_progress(
            job_name,
            status="failed",
            message=f"Prowlarr search failed: {error_msg}",
            progress=0,
            dry_run=dry_run,
        )

    finally:
        release_prowlarr_job_lock(job_name)


@prowlarr_bp.route("/")
def prowlarr_dashboard():
    """Main Prowlarr dashboard page"""
    set_active_page("prowlarr")

    # Get current job status
    current_job = _prowlarr_active_jobs.get("prowlarr_search", {})
    job_progress = get_prowlarr_job_progress("prowlarr_search")

    # Check if Prowlarr is configured
    config = get_config(strict=False)
    prowlarr_config = config.get("prowlarr", {}) if config else {}

    prowlarr_enabled = prowlarr_config.get("enabled", False)
    prowlarr_configured = bool(prowlarr_config.get("url") and prowlarr_config.get("api_key"))

    return render_template(
        "prowlarr_dashboard.html",
        current_job=current_job,
        job_progress=job_progress,
        prowlarr_enabled=prowlarr_enabled,
        prowlarr_configured=prowlarr_configured,
    )


@prowlarr_bp.route("/start", methods=["POST"])
def start_prowlarr_search():
    """Start a new Prowlarr search job"""
    try:
        start_date = request.form.get("start_date")
        end_date = request.form.get("end_date")
        dry_run = "dry_run" in request.form

        # Validation
        if start_date and end_date:
            try:
                start_dt = datetime.strptime(start_date, "%Y-%m-%d")
                end_dt = datetime.strptime(end_date, "%Y-%m-%d")

                if start_dt > end_dt:
                    return jsonify(
                        {"success": False, "message": "Start date must be before end date"}
                    )

                if end_dt > datetime.now():
                    return jsonify(
                        {"success": False, "message": "End date cannot be in the future"}
                    )

            except ValueError:
                return jsonify({"success": False, "message": "Invalid date format"})

        # Check for conflicts
        if is_prowlarr_job_running("prowlarr_search"):
            return jsonify({"success": False, "message": "Prowlarr search already running"})

        # Start the search
        job_thread = threading.Thread(
            target=prowlarr_search_job,
            args=(start_date, end_date, dry_run),
            name=f"ProwlarrSearch-{start_date or 'auto'}-{end_date or 'auto'}",
        )
        job_thread.daemon = True
        job_thread.start()

        date_range = (
            f"{start_date} to {end_date}" if start_date and end_date else "automatic date range"
        )
        return jsonify(
            {
                "success": True,
                "message": f"Prowlarr search started for {date_range}",
                "dry_run": dry_run,
            }
        )

    except Exception as e:
        logger.error(f"Error starting Prowlarr search: {e}")
        return jsonify({"success": False, "message": str(e)})


@prowlarr_bp.route("/progress")
def prowlarr_search_progress():
    """Get current progress of Prowlarr search"""
    job_progress = get_prowlarr_job_progress("prowlarr_search")
    is_running = is_prowlarr_job_running("prowlarr_search")

    return jsonify({"is_running": is_running, "progress": job_progress})


@prowlarr_bp.route("/cancel")
def cancel_prowlarr_search():
    """Cancel running Prowlarr search"""
    if is_prowlarr_job_running("prowlarr_search"):
        release_prowlarr_job_lock("prowlarr_search")
        update_prowlarr_job_progress(
            "prowlarr_search", status="cancelled", message="Prowlarr search cancelled by user"
        )
        return jsonify({"success": True, "message": "Prowlarr search cancelled"})
    else:
        return jsonify({"success": False, "message": "No Prowlarr search running"})


@prowlarr_bp.route("/test-connection")
def test_prowlarr_connection():
    """Test connection to Prowlarr"""
    try:
        config = get_config(strict=False)
        prowlarr_config = config.get("prowlarr", {}) if config else {}

        if not prowlarr_config.get("enabled", False):
            return jsonify({"success": False, "message": "Prowlarr is not enabled"})

        if not prowlarr_config.get("url") or not prowlarr_config.get("api_key"):
            return jsonify({"success": False, "message": "Prowlarr URL or API key not configured"})

        from src.api.prowlarr_client import ProwlarrClient

        prowlarr_client = ProwlarrClient(prowlarr_config)

        if prowlarr_client.test_connection():
            indexers = prowlarr_client.get_indexers()
            message = f"Connected successfully. Found {len(indexers)} enabled torrent indexers."
            return jsonify({"success": True, "message": message})
        else:
            return jsonify({"success": False, "message": "Failed to connect to Prowlarr"})

    except Exception as e:
        logger.error(f"Error testing Prowlarr connection: {e}")
        return jsonify({"success": False, "message": f"Connection test failed: {str(e)}"})


# Utility function for external access
def is_prowlarr_search_running():
    """Utility function for main app to check if Prowlarr search is running"""
    return is_prowlarr_job_running("prowlarr_search")
