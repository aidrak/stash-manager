import logging
import threading
from zoneinfo import ZoneInfo

from flask import Blueprint, jsonify, render_template, request

from src.api.stash_api import StashAPI
from src.config.config import get_config
from src.core.scheduler import scheduler
from src.core.utils import set_active_page
from src.core.validation import ValidationError, validate_job_parameters
from src.core.database_manager import DatabaseManager
from src.web.one_time_search import is_one_time_search_running
from src.web.processor import add_new_scenes_to_whisparr, generate_metadata

task_bp = Blueprint("tasks", __name__)

logger = logging.getLogger(__name__)


@task_bp.route("/tasks")
def tasks():
    set_active_page("tasks")

    config = get_config()

    job_keys = {
        "add_new_scenes": "add_new_scenes_to_whisparr",
        "clean_existing_scenes": "clean_existing_scenes",
        "scan_and_identify": "scan_and_identify",
        "generate_metadata": "generate_metadata",
    }

    last_run_times = {}
    next_run_times = {}

    for key, job_name in job_keys.items():
        jobs = scheduler.get_jobs(job_name)
        if jobs:
            job = jobs[0]  # Get the first (and should be only) job with this tag
            last_run = (
                job.last_run.astimezone(
                    ZoneInfo(config.get("main", {}).get("timezone", "UTC"))
                )
                if job.last_run
                else None
            )
            next_run = (
                job.next_run.astimezone(
                    ZoneInfo(config.get("main", {}).get("timezone", "UTC"))
                )
                if job.next_run
                else None
            )
            last_run_times[key] = (
                last_run.strftime("%Y-%m-%d %H:%M:%S") if last_run else "N/A"
            )
            next_run_times[key] = (
                next_run.strftime("%Y-%m-%d %H:%M:%S")
                if next_run
                else "Not Scheduled"
            )
        else:
            last_run_times[key] = "N/A"
            next_run_times[key] = "Not Scheduled"

    return render_template(
        "tasks.html",
        config=config,
        last_run_times=last_run_times,
        next_run_times=next_run_times,
        is_one_time_search_running=is_one_time_search_running(),
    )


@task_bp.route("/run_job/<job_name>")
def run_job(job_name):
    """Run a specific job manually"""
    try:
        config = get_config()

        if job_name == "add_new_scenes_to_whisparr":
            # Validate parameters from query string
            raw_params = {
                "start_date": request.args.get("start_date"),
                "end_date": request.args.get("end_date"),
                "dry_run": request.args.get("dry_run", "false"),
                "sort_direction": request.args.get("sort_direction", "DESC"),
            }

            try:
                validated_params = validate_job_parameters(job_name, raw_params)
            except ValidationError as e:
                return jsonify(
                    {"success": False, "message": f"Parameter validation failed: {e}"}
                )

            start_date = validated_params.get("start_date")
            end_date = validated_params.get("end_date")
            dry_run = validated_params["dry_run"]
            sort_direction = validated_params["sort_direction"]

            # Setup APIs
            import os

            stashdb_api_key = os.environ.get("STASHDB_API_KEY")
            if not stashdb_api_key:
                return jsonify(
                    {"success": False, "message": "StashDB API key not configured"}
                )

            stashdb_api = StashAPI(url="https://stashdb.org", api_key=stashdb_api_key)

            # Run the job in a background thread
            thread = threading.Thread(
                target=add_new_scenes_to_whisparr,
                args=(
                    config,
                    stashdb_api,
                    start_date,
                    end_date,
                    dry_run,
                    sort_direction,
                ),
            )
            thread.start()

            return jsonify(
                {
                    "success": True,
                    "message": "Job started. Scenes will be added to Whisparr in the background.",
                }
            )

        elif job_name == "clean_existing_scenes":
            # Setup local Stash API
            local_stash_url = config.get("stash", {}).get("url")
            local_stash_api_key = config.get("stash", {}).get("api_key")

            if not local_stash_url or not local_stash_api_key:
                return jsonify(
                    {"success": False, "message": "Local Stash configuration missing"}
                )

            local_stash_api = StashAPI(
                url=local_stash_url, api_key=local_stash_api_key
            )

            # Run the job in a background thread
            from src.web.processor import clean_existing_scenes_from_stash

            thread = threading.Thread(
                target=clean_existing_scenes_from_stash,
                args=(config, local_stash_api),
            )
            thread.start()

            return jsonify(
                {
                    "success": True,
                    "message": "Job started. Scenes will be cleaned from Stash in the background.",
                }
            )

        elif job_name == "scan_and_identify":
            return jsonify(
                {
                    "success": False,
                    "message": "Scan and identify functionality not yet implemented.",
                }
            )

        elif job_name == "generate_metadata":
            # Get pending metadata tasks
            db = DatabaseManager()
            tasks = db.get_pending_tasks("generate_metadata")

            scenes_processed = 0
            for task in tasks:
                if task["type"] == "generate_metadata":
                    generate_metadata(config, task["scene_id"])
                    scenes_processed += 1

            return jsonify(
                {
                    "success": True,
                    "message": f"Generated metadata for {scenes_processed} scenes.",
                }
            )

        else:
            return jsonify({"success": False, "message": f"Unknown job: {job_name}"})

    except Exception as e:
        logger.error(f"Error running job {job_name}: {e}", exc_info=True)
        return jsonify({"success": False, "message": f"Job failed: {str(e)}"})
