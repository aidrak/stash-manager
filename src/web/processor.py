import logging
import os

from dotenv import load_dotenv

from src.api.prowlarr_client import ProwlarrClient
from src.api.stash_api import StashAPI
from src.api.whisparr import WhisparrApi
from src.filters.add_scenes_filter import AddScenesFilter
from src.filters.clean_scenes_filter import CleanScenesFilter
from src.filters.conditions.local_stash_conditions import LOCAL_STASH_CONDITIONS
from src.filters.conditions.stashdb_conditions import STASHDB_CONDITIONS

# Load environment variables from .env file
load_dotenv()

logger = logging.getLogger(__name__)


def add_new_scenes_to_whisparr(
    config: dict,
    stash_api: StashAPI,
    start_date=None,
    end_date=None,
    progress_callback=None,
    dry_run=False,
    sort_direction: str = "DESC",  # Add sort_direction parameter, default to DESC (newest first)
):
    """
    Finds new scenes in StashDB, filters them using AddScenesFilter, and adds them to Whisparr.
    """
    scenes_added_to_whisparr = 0
    total_scenes_found = 0
    logger.debug("Entering add_new_scenes_to_whisparr function.")
    logger.info("🚀 === STARTING ADD NEW SCENES JOB ===")

    # Use dedicated AddScenesFilter with StashDB conditions
    filter_engine = AddScenesFilter(config, STASHDB_CONDITIONS)
    whisparr_api = WhisparrApi(config.get("whisparr", {}))

    search_back_days = config.get("jobs", {}).get("add_new_scenes_search_back_days", 7)

    logger.info(f"💧 DRY RUN MODE: {'ENABLED' if dry_run else 'DISABLED'}")

    logger.info("🔍 Fetching scenes from StashDB...")
    stashdb_api_key = os.environ.get("STASHDB_API_KEY")
    if not stashdb_api_key:
        logging.error("❌ STASHDB_API_KEY environment variable not set. Cannot fetch scenes.")
        return
    stashdb_api = StashAPI(url="https://stashdb.org", api_key=stashdb_api_key)

    new_scenes = stashdb_api.get_all_scenes(
        limit=500, start_date=start_date, end_date=end_date, direction=sort_direction
    )

    # Add this debug logging:
    logger.info("Sample scene dates from StashDB:")
    for i, scene in enumerate(new_scenes[:5]):  # Log first 5 scenes
        scene_date = scene.get("date", "No date")
        logger.info(
            f"  Scene {i + 1}: '{scene.get('title', 'No title')[:50]}' - Date: {scene_date}"
        )

    from datetime import datetime, timedelta

    if start_date and end_date:
        start_date = datetime.strptime(start_date, "%Y-%m-%d")
        end_date = datetime.strptime(end_date, "%Y-%m-%d")
    else:
        start_date = datetime.now() - timedelta(days=search_back_days)
        end_date = datetime.now()

    filtered_scenes = []
    for scene in new_scenes:
        scene_date_str = scene.get("date")
        if scene_date_str:
            scene_date = datetime.strptime(scene_date_str, "%Y-%m-%d")
            if start_date <= scene_date <= end_date:
                filtered_scenes.append(scene)
        else:
            logger.debug(
                f"Scene {scene.get('title', 'Untitled')} has no date, skipping date filter."
            )
    new_scenes = filtered_scenes

    logger.info(f"📊 === RETRIEVED {len(new_scenes)} SCENES FROM STASHDB ===")

    # Track statistics
    scenes_passed_filter = 0
    scenes_already_exist = 0
    scenes_added = 0
    scenes_failed = 0
    scenes_filtered = 0

    total_scenes_found = len(new_scenes)
    for i, scene in enumerate(new_scenes):
        if progress_callback:
            progress_callback(
                i + 1,
                total_scenes_found,
                f"Processing scene {i + 1}/{total_scenes_found}: {scene.get('title', 'Untitled')}",
            )

        scene_title = scene.get("title", "Untitled")
        logger.debug(f"Processing scene {i + 1}/{len(new_scenes)}: {scene_title}")

        # Use AddScenesFilter's should_add_scene method
        should_add, reason = filter_engine.should_add_scene(scene)

        if should_add:
            scenes_passed_filter += 1
            # Log at INFO level with emoji for scenes that pass filter
            logger.info(f"✅ PASSED FILTER: {scene_title}")
            logger.debug(f"   Reason: {reason}")

            if not dry_run:
                result = whisparr_api.add_series(scene.get("title"))
                if result and result.get("status") == "added":
                    scenes_added += 1
                    scenes_added_to_whisparr += 1
                    logger.info(f"🎉 ADDED TO WHISPARR: {scene_title}")
                elif result and result.get("status") == "already_exists":
                    scenes_already_exist += 1
                    logger.info(f"ℹ️  ALREADY IN WHISPARR: {scene_title}")
                else:
                    scenes_failed += 1
                    logger.error(f"❌ FAILED TO ADD: {scene_title}")
            else:
                logger.info(f"💧 DRY RUN - Would attempt to add: {scene_title}")
        else:
            scenes_filtered += 1
            # Only show filtered scenes in DEBUG mode to reduce noise
            logger.debug(f"❌ FILTERED: {scene_title} - {reason}")

    # Summary at INFO level
    logger.info("")
    logger.info("📊 === JOB SUMMARY ===")
    logger.info(f"🔍 Total scenes from StashDB: {len(new_scenes)}")
    logger.info(f"✅ Scenes passed filter: {scenes_passed_filter}")
    logger.info(f"❌ Scenes filtered out: {scenes_filtered}")

    if not dry_run:
        logger.info(f"🎉 New scenes added: {scenes_added}")
        logger.info(f"ℹ️  Already existed: {scenes_already_exist}")
        logger.info(f"💥 Failed to add: {scenes_failed}")
    else:
        logger.info("💧 DRY RUN - No scenes were actually added")

    logger.info("🏁 === COMPLETED ADD NEW SCENES JOB ===")

    return {"scenes_added": scenes_added_to_whisparr, "total_found": total_scenes_found}


def clean_existing_scenes_from_stash(config: dict, stash_api: StashAPI):
    """
    Scans all existing scenes in local Stash and deletes ones that
    don't match the CleanScenesFilter.
    """
    logger.info("🧹 === STARTING CLEAN EXISTING SCENES JOB ===")

    # Use dedicated CleanScenesFilter with Local Stash conditions
    filter_engine = CleanScenesFilter(config, LOCAL_STASH_CONDITIONS)

    dry_run = config.get("general", {}).get("dry_run", False)
    logger.info(f"💧 DRY RUN MODE: {'ENABLED' if dry_run else 'DISABLED'}")

    logger.info("🔍 Fetching scenes from local Stash...")
    all_scenes = stash_api.get_all_scenes()

    if not all_scenes:
        logger.info("📭 No scenes found in local Stash.")
        return

    logger.info(f"📊 Found {len(all_scenes)} scenes in local Stash")

    scenes_to_delete = []
    scenes_to_keep = []

    is_debug_mode = logger.isEnabledFor(logging.DEBUG)

    for i, scene in enumerate(all_scenes):
        scene_title = scene.get("title", "Untitled")
        scene_id = scene.get("id")

        if is_debug_mode:
            logger.debug(f"🔍 Processing scene {i + 1}/{len(all_scenes)}: {scene_title}")

        # Use CleanScenesFilter's should_keep_scene method
        should_keep, reason = filter_engine.should_keep_scene(scene)

        if not scene_id:
            logger.warning(f"Scene {scene_title} has no ID, cannot be deleted. Skipping.")
            continue

        if should_keep:
            logger.debug(f"✅ KEEP: {scene_title} - {reason}")
            scenes_to_keep.append(scene_title)
        else:
            logger.info(f"🔥 MARKED FOR DELETION: {scene_title} - {reason}")
            scenes_to_delete.append((scene_id, scene_title))

    # Summary
    logger.info("")
    logger.info("📊 === CLEANING SUMMARY ===")
    logger.info(f"🔍 Total scenes processed: {len(all_scenes)}")
    logger.info(f"✅ Scenes to keep: {len(scenes_to_keep)}")
    logger.info(f"🔥 Scenes to delete: {len(scenes_to_delete)}")

    # Actually delete the scenes (if not dry run)
    if not dry_run and scenes_to_delete:
        logger.info("")
        logger.info(f"🔥 DELETING {len(scenes_to_delete)} SCENES...")
        deleted_count = 0
        failed_count = 0

        for scene_id, scene_title in scenes_to_delete:
            logger.info(f"   🗑️  Deleting: {scene_title}")
            success = stash_api.delete_scene(scene_id, delete_file=True)
            if success:
                deleted_count += 1
                logger.info("   ✅ Successfully deleted")
            else:
                failed_count += 1
                logger.error("   ❌ Failed to delete")

        logger.info("")
        logger.info(f"📊 Deletion results: {deleted_count} deleted, {failed_count} failed")

    elif dry_run and scenes_to_delete:
        logger.info("")
        logger.info(f"💧 DRY RUN: Would delete {len(scenes_to_delete)} scenes")
    else:
        logger.info("")
        logger.info("✅ No scenes matched the deletion criteria.")

    logger.info("🏁 === COMPLETED CLEAN EXISTING SCENES JOB ===")


def generate_metadata(config: dict, stash_api: StashAPI):
    """
    Triggers the generation of metadata for all scenes in Stash.
    """
    logger.info("🚀 === STARTING GENERATE METADATA JOB ===")

    dry_run = config.get("general", {}).get("dry_run", False)
    logger.info(f"💧 DRY RUN MODE: {'ENABLED' if dry_run else 'DISABLED'}")

    if not dry_run:
        try:
            job_id = stash_api.trigger_generate()
            logger.info(f"✅ Successfully triggered metadata generation with job ID: {job_id}")
            stash_api.wait_for_job_completion(job_id)
        except Exception as e:
            logger.error(f"❌ Failed to trigger metadata generation: {e}")
    else:
        logger.info("💧 DRY RUN - Would have triggered metadata generation.")

    logger.info("🏁 === COMPLETED GENERATE METADATA JOB ===")


def add_new_scenes_with_prowlarr(
    config: dict,
    stash_api: StashAPI,
    start_date=None,
    end_date=None,
    progress_callback=None,
    dry_run=False,
    sort_direction: str = "DESC",
):
    """
    Enhanced scene discovery using Prowlarr for direct torrent searching.
    Finds new scenes in StashDB, filters them, searches via Prowlarr, and downloads via qBittorrent.
    """
    scenes_downloaded = 0
    total_scenes_found = 0
    logger.debug("Entering add_new_scenes_with_prowlarr function.")
    logger.info("🚀 === STARTING PROWLARR SEARCH JOB ===")

    # Check if Prowlarr is enabled and configured
    prowlarr_config = config.get("prowlarr", {})
    if not prowlarr_config.get("enabled", False):
        logger.error("❌ Prowlarr is not enabled in configuration")
        return {"scenes_downloaded": 0, "total_found": 0, "error": "Prowlarr not enabled"}

    if not prowlarr_config.get("url") or not prowlarr_config.get("api_key"):
        logger.error("❌ Prowlarr URL or API key not configured")
        return {"scenes_downloaded": 0, "total_found": 0, "error": "Prowlarr not configured"}

    # Use dedicated AddScenesFilter with StashDB conditions
    filter_engine = AddScenesFilter(config, STASHDB_CONDITIONS)

    try:
        # Initialize Prowlarr client
        prowlarr_client = ProwlarrClient(prowlarr_config)

        # Test Prowlarr connection
        if not prowlarr_client.test_connection():
            logger.error("❌ Failed to connect to Prowlarr")
            return {"scenes_downloaded": 0, "total_found": 0, "error": "Prowlarr connection failed"}

        logger.info("✅ Connected to Prowlarr successfully")

    except Exception as e:
        logger.error(f"❌ Error initializing Prowlarr client: {e}")
        return {
            "scenes_downloaded": 0,
            "total_found": 0,
            "error": f"Prowlarr initialization failed: {e}",
        }

    search_back_days = config.get("jobs", {}).get("add_new_scenes_search_back_days", 7)

    logger.info(f"💧 DRY RUN MODE: {'ENABLED' if dry_run else 'DISABLED'}")

    logger.info("🔍 Fetching scenes from StashDB...")
    stashdb_api_key = os.environ.get("STASHDB_API_KEY")
    if not stashdb_api_key:
        logging.error("❌ STASHDB_API_KEY environment variable not set. Cannot fetch scenes.")
        return {"scenes_downloaded": 0, "total_found": 0, "error": "StashDB API key missing"}

    stashdb_api = StashAPI(url="https://stashdb.org", api_key=stashdb_api_key)

    new_scenes = stashdb_api.get_all_scenes(
        limit=500, start_date=start_date, end_date=end_date, direction=sort_direction
    )

    # Date filtering logic (same as original)
    from datetime import datetime, timedelta

    if start_date and end_date:
        start_date = datetime.strptime(start_date, "%Y-%m-%d")
        end_date = datetime.strptime(end_date, "%Y-%m-%d")
    else:
        start_date = datetime.now() - timedelta(days=search_back_days)
        end_date = datetime.now()

    filtered_scenes = []
    for scene in new_scenes:
        scene_date_str = scene.get("date")
        if scene_date_str:
            scene_date = datetime.strptime(scene_date_str, "%Y-%m-%d")
            if start_date <= scene_date <= end_date:
                filtered_scenes.append(scene)
        else:
            logger.debug(
                f"Scene {scene.get('title', 'Untitled')} has no date, skipping date filter."
            )
    new_scenes = filtered_scenes

    logger.info(f"📊 === RETRIEVED {len(new_scenes)} SCENES FROM STASHDB ===")

    # Track statistics
    scenes_passed_filter = 0
    scenes_found_on_prowlarr = 0
    scenes_downloaded = 0
    scenes_failed = 0
    scenes_filtered = 0

    total_scenes_found = len(new_scenes)
    for i, scene in enumerate(new_scenes):
        if progress_callback:
            progress_callback(
                i + 1,
                total_scenes_found,
                f"Processing scene {i + 1}/{total_scenes_found}: {scene.get('title', 'Untitled')}",
            )

        scene_title = scene.get("title", "Untitled")
        logger.debug(f"Processing scene {i + 1}/{len(new_scenes)}: {scene_title}")

        # Use AddScenesFilter's should_add_scene method
        should_add, reason = filter_engine.should_add_scene(scene)

        if should_add:
            scenes_passed_filter += 1
            logger.info(f"✅ PASSED FILTER: {scene_title}")
            logger.debug(f"   Reason: {reason}")

            # Search for scene on Prowlarr
            logger.info(f"🔍 Searching Prowlarr for: {scene_title}")
            try:
                search_results = prowlarr_client.search_scene(scene_title)

                if search_results:
                    scenes_found_on_prowlarr += 1
                    logger.info(
                        f"🎯 Found {len(search_results)} results on Prowlarr for: {scene_title}"
                    )

                    # Get the best result
                    best_result = prowlarr_client.get_best_result(
                        search_results, min_seeders=1, max_size_gb=10.0
                    )

                    if best_result:
                        if not dry_run:
                            # Download the torrent
                            success = prowlarr_client.download_torrent(
                                best_result["download_url"], best_result["indexer_id"]
                            )

                            if success:
                                scenes_downloaded += 1
                                logger.info(f"🎉 DOWNLOADED VIA PROWLARR: {scene_title}")
                                logger.info(f"   From: {best_result.get('indexer_name')}")
                                logger.info(f"   Seeders: {best_result.get('seeders')}")
                                size_gb = best_result.get("size", 0) / (1024 * 1024 * 1024)
                                logger.info(f"   Size: {size_gb:.2f} GB")
                            else:
                                scenes_failed += 1
                                logger.error(f"❌ FAILED TO DOWNLOAD: {scene_title}")
                        else:
                            logger.info(f"💧 DRY RUN - Would download: {best_result.get('title')}")
                            logger.info(f"   From: {best_result.get('indexer_name')}")
                    else:
                        logger.warning(
                            f"⚠️  No suitable results for: {scene_title} "
                            "(quality/seeder criteria not met)"
                        )
                else:
                    logger.warning(f"❌ No results found on Prowlarr for: {scene_title}")

            except Exception as e:
                scenes_failed += 1
                logger.error(f"❌ Error searching Prowlarr for '{scene_title}': {e}")

        else:
            scenes_filtered += 1
            logger.debug(f"❌ FILTERED: {scene_title} - {reason}")

    # Summary at INFO level
    logger.info("")
    logger.info("📊 === PROWLARR SEARCH JOB SUMMARY ===")
    logger.info(f"🔍 Total scenes from StashDB: {len(new_scenes)}")
    logger.info(f"✅ Scenes passed filter: {scenes_passed_filter}")
    logger.info(f"❌ Scenes filtered out: {scenes_filtered}")
    logger.info(f"🎯 Scenes found on Prowlarr: {scenes_found_on_prowlarr}")

    if not dry_run:
        logger.info(f"🎉 Scenes downloaded: {scenes_downloaded}")
        logger.info(f"💥 Failed downloads: {scenes_failed}")
    else:
        logger.info("💧 DRY RUN - No scenes were actually downloaded")

    logger.info("🏁 === COMPLETED PROWLARR SEARCH JOB ===")

    return {"scenes_downloaded": scenes_downloaded, "total_found": total_scenes_found}
