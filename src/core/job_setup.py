import logging
import re
import threading
import time

from src.config.config import get_config
from src.core.logging_config import setup_logging
from src.core.scheduler import scheduler
from src.core.signal_handlers import shutdown_event
from src.data.database_manager import DatabaseManager
from src.web.processor import (
    add_new_scenes_to_whisparr,
    add_new_scenes_with_prowlarr,
    generate_metadata,
)


def _validate_time_format(time_str):
    """Validate time format (HH:MM)"""
    if not isinstance(time_str, str):
        return False
    pattern = r"^(?[0-9]|2[0-3]):[0-5][0-9]$"
    return bool(re.match(pattern, time_str))


def _validate_scene_id(scene_id):
    """Validate scene ID is a positive integer or string representation of one"""
    if isinstance(scene_id, int):
        return scene_id > 0
    if isinstance(scene_id, str):
        try:
            return int(scene_id) > 0
        except ValueError:
            return False
    return False


def run_scheduler():
    """Run the job scheduler in a separate thread"""
    while not shutdown_event.is_set():
        try:
            scheduler.run_pending()
            time.sleep(1)
        except Exception as e:
            if not shutdown_event.is_set():
                logging.error(f"Error in scheduler: {e}")
            break

    logging.info("Scheduler thread shutting down")


def setup_jobs():
    """Setup scheduled jobs based on configuration"""
    try:
        config = get_config(strict=False)
        if not config:
            logging.error("Could not load config for setting up jobs.")
            return

        # Setup logging
        setup_logging(config)

        # Check if jobs are already set up (for persistence across restarts)
        existing_jobs = scheduler.get_jobs()
        if existing_jobs:
            logging.info(f"Found {len(existing_jobs)} existing jobs, preserving them")
            # Start scheduler in a separate thread if not already running
            scheduler_threads = [
                t for t in threading.enumerate() if t.name.startswith("scheduler")
            ]
            if not scheduler_threads:
                scheduler_thread = threading.Thread(
                    target=run_scheduler, daemon=True, name="scheduler-thread"
                )
                scheduler_thread.start()
                logging.info("Scheduler thread restarted")
            return

        # Clear existing jobs only if none found (fresh setup)
        logging.info("No existing jobs found, setting up fresh schedule")

        # Get job configuration
        jobs_config = config.get("jobs", {})
        enabled_jobs = jobs_config.get("enabled_jobs", [])

        logging.info(f"Setting up jobs: {enabled_jobs}")

        # Setup scheduled jobs
        for job_name in enabled_jobs:
            if job_name == "add_new_scenes_to_whisparr":
                schedule_time = jobs_config.get("add_new_scenes_to_whisparr", {}).get(
                    "time", "06:00"
                )
                if not _validate_time_format(schedule_time):
                    logging.error(
                        f"Invalid time format for {job_name}: {schedule_time}. "
                        "Using default 06:00"
                    )
                    schedule_time = "06:00"
                logging.info(f"Scheduling {job_name} at {schedule_time}")
                scheduler.every().day.at(schedule_time).do(
                    _job_wrapper, job_name
                ).tag(job_name)

            elif job_name == "clean_existing_scenes":
                schedule_time = jobs_config.get("clean_existing_scenes_time", {}).get(
                    "time", "18:00"
                )
                if not _validate_time_format(schedule_time):
                    logging.error(
                        f"Invalid time format for {job_name}: {schedule_time}. "
                        "Using default 18:00"
                    )
                    schedule_time = "18:00"
                logging.info(f"Scheduling {job_name} at {schedule_time}")
                scheduler.every().day.at(schedule_time).do(
                    _job_wrapper, job_name
                ).tag(job_name)

            elif job_name == "scan_and_identify":
                schedule_time = jobs_config.get("scan_and_identify_time", {}).get(
                    "time", "02:00"
                )
                if not _validate_time_format(schedule_time):
                    logging.error(
                        f"Invalid time format for {job_name}: {schedule_time}. "
                        "Using default 02:00"
                    )
                    schedule_time = "02:00"
                logging.info(f"Scheduling {job_name} at {schedule_time}")
                scheduler.every().day.at(schedule_time).do(
                    _job_wrapper, job_name
                ).tag(job_name)

            elif job_name == "generate_metadata":
                schedule_time = jobs_config.get("generate_metadata_time", {}).get(
                    "time", "12:00"
                )
                if not _validate_time_format(schedule_time):
                    logging.error(
                        f"Invalid time format for {job_name}: {schedule_time}. "
                        "Using default 12:00"
                    )
                    schedule_time = "12:00"
                logging.info(f"Scheduling {job_name} at {schedule_time}")
                scheduler.every().day.at(schedule_time).do(
                    _job_wrapper, job_name
                ).tag(job_name)

            elif job_name == "add_new_scenes_with_prowlarr":
                schedule_time = jobs_config.get("add_new_scenes_with_prowlarr", {}).get(
                    "time", "08:00"
                )
                if not _validate_time_format(schedule_time):
                    logging.error(
                        f"Invalid time format for {job_name}: {schedule_time}. "
                        "Using default 08:00"
                    )
                    schedule_time = "08:00"
                logging.info(f"Scheduling {job_name} at {schedule_time}")
                scheduler.every().day.at(schedule_time).do(
                    _job_wrapper, job_name
                ).tag(job_name)

        # Start scheduler in a separate thread
        scheduler_thread = threading.Thread(
            target=run_scheduler, daemon=True, name="scheduler-thread"
        )
        scheduler_thread.start()

        logging.info("Job scheduler initialized successfully")

    except Exception as e:
        logging.error(f"Failed to setup jobs: {e}")


def _job_wrapper(job_name):
    """Wrapper function to execute jobs with proper error handling"""
    try:
        logging.info(f"Starting job: {job_name}")
        config = get_config()

        if not config:
            logging.error("Could not load config for job execution")
            return

        if job_name == "add_new_scenes_to_whisparr":
            from src.api.stash_api import StashAPI

            stashdb_api_key = config.get("stashdb", {}).get("api_key")
            stashdb_api = StashAPI(url="https://stashdb.org", api_key=stashdb_api_key)
            add_new_scenes_to_whisparr(config, stashdb_api)

        elif job_name == "clean_existing_scenes":
            from src.api.stash_api import StashAPI

            local_stash_url = config.get("local_stash", {}).get("url")
            local_stash_api_key = config.get("local_stash", {}).get("api_key")

            if local_stash_url and local_stash_api_key:
                local_stash_api = StashAPI(
                    url=local_stash_url, api_key=local_stash_api_key
                )
                from src.web.processor import clean_existing_scenes_from_stash

                clean_existing_scenes_from_stash(config, local_stash_api)
            else:
                logging.error(
                    "Local Stash configuration missing for clean_existing_scenes job"
                )

        elif job_name == "scan_and_identify":
            # Placeholder for scan_and_identify job - functionality to be implemented
            logging.info(
                "Scan and identify job placeholder - functionality not yet implemented"
            )

        elif job_name == "generate_metadata":
            db = DatabaseManager()
            tasks = db.get_pending_tasks()
            for task in tasks:
                if task["type"] == "generate_metadata":
                    scene_id = task["scene_id"]
                    if not _validate_scene_id(scene_id):
                        logging.error(
                            f"Invalid scene_id in task: {scene_id}. Skipping."
                        )
                        continue
                    generate_metadata(config, scene_id)

        elif job_name == "add_new_scenes_with_prowlarr":
            import os

            from src.api.stash_api import StashAPI

            stash_url = os.environ.get("STASH_URL")
            stash_api_key = os.environ.get("STASH_API_KEY")

            if stash_url and stash_api_key:
                stash_api = StashAPI(url=stash_url, api_key=stash_api_key)
                add_new_scenes_with_prowlarr(config, stash_api)
            else:
                logging.error(
                    "Stash configuration missing for add_new_scenes_with_prowlarr job"
                )

        logging.info(f"Completed job: {job_name}")

    except Exception as e:
        logging.error(f"Job {job_name} failed with error: {e}", exc_info=True)
