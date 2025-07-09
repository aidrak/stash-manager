import logging
import os
from src.add_scenes_filter import AddScenesFilter
from src.clean_scenes_filter import CleanScenesFilter
from src.stash_api import StashAPI
from src.whisparr import WhisparrApi
from src.config import get_identify_sources
from src.stashdb_conditions import STASHDB_CONDITIONS
from src.local_stash_conditions import LOCAL_STASH_CONDITIONS

logger = logging.getLogger(__name__)

def add_new_scenes_to_whisparr(config: dict, stash_api: StashAPI, start_date=None, end_date=None):
    """
    Finds new scenes in StashDB, filters them using AddScenesFilter, and adds them to Whisparr.
    """
    logger.debug("Entering add_new_scenes_to_whisparr function.")
    logger.info("🚀 === STARTING ADD NEW SCENES JOB ===")
    
    # Use dedicated AddScenesFilter with StashDB conditions
    filter_engine = AddScenesFilter(config, STASHDB_CONDITIONS)
    whisparr_api = WhisparrApi(config.get('whisparr', {}))
    
    search_back_days = config.get('jobs', {}).get('add_new_scenes_search_back_days', 7)
    
    dry_run = config.get('general', {}).get('dry_run', False)
    logger.info(f"💧 DRY RUN MODE: {'ENABLED' if dry_run else 'DISABLED'}")
    
    logger.info("🔍 Fetching scenes from StashDB...")
    stashdb_api_key = os.environ.get('STASHDB_API_KEY')
    if not stashdb_api_key:
        logging.error("❌ STASHDB_API_KEY environment variable not set. Cannot fetch scenes.")
        return
    stashdb_api = StashAPI(url="https://stashdb.org", api_key=stashdb_api_key)
    
    new_scenes = stashdb_api.get_all_scenes(limit=500, start_date=start_date, end_date=end_date)
    
    from datetime import datetime, timedelta
    
    if start_date and end_date:
        start_date = datetime.strptime(start_date, '%Y-%m-%d')
        end_date = datetime.strptime(end_date, '%Y-%m-%d')
    else:
        start_date = datetime.now() - timedelta(days=search_back_days)
        end_date = datetime.now()

    filtered_scenes = []
    for scene in new_scenes:
        scene_date = datetime.strptime(scene.get('date'), '%Y-%m-%d')
        if start_date <= scene_date <= end_date:
            filtered_scenes.append(scene)
    new_scenes = filtered_scenes

    logger.info(f"📊 === RETRIEVED {len(new_scenes)} SCENES FROM STASHDB ===")

    # Track statistics
    scenes_passed_filter = 0
    scenes_already_exist = 0
    scenes_added = 0
    scenes_failed = 0
    scenes_filtered = 0

    for i, scene in enumerate(new_scenes):
        scene_title = scene.get('title', 'Untitled')
        logger.debug(f"Processing scene {i+1}/{len(new_scenes)}: {scene_title}")
        
        # Use AddScenesFilter's should_add_scene method
        should_add, reason = filter_engine.should_add_scene(scene)
        
        if should_add:
            scenes_passed_filter += 1
            # Log at INFO level with emoji for scenes that pass filter
            logger.info(f"✅ PASSED FILTER: {scene_title}")
            logger.debug(f"   Reason: {reason}")
            
            if not dry_run:
                result = whisparr_api.add_series(scene.get('title'))
                if result and result.get('status') == 'added':
                    scenes_added += 1
                    logger.info(f"🎉 ADDED TO WHISPARR: {scene_title}")
                elif result and result.get('status') == 'already_exists':
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
    logger.info(f"")
    logger.info(f"📊 === JOB SUMMARY ===")
    logger.info(f"🔍 Total scenes from StashDB: {len(new_scenes)}")
    logger.info(f"✅ Scenes passed filter: {scenes_passed_filter}")
    logger.info(f"❌ Scenes filtered out: {scenes_filtered}")
    
    if not dry_run:
        logger.info(f"🎉 New scenes added: {scenes_added}")
        logger.info(f"ℹ️  Already existed: {scenes_already_exist}")
        logger.info(f"💥 Failed to add: {scenes_failed}")
    else:
        logger.info(f"💧 DRY RUN - No scenes were actually added")
    
    logger.info("🏁 === COMPLETED ADD NEW SCENES JOB ===")

def clean_existing_scenes_from_stash(config: dict, stash_api: StashAPI):
    """
    Scans all existing scenes in local Stash and deletes ones that don't match the CleanScenesFilter.
    """
    logger.info("🧹 === STARTING CLEAN EXISTING SCENES JOB ===")

    # Use dedicated CleanScenesFilter with Local Stash conditions
    filter_engine = CleanScenesFilter(config, LOCAL_STASH_CONDITIONS)
    
    dry_run = config.get('general', {}).get('dry_run', False)
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
        scene_title = scene.get('title', 'Untitled')
        scene_id = scene.get('id')
        
        if is_debug_mode:
            logger.debug(f"🔍 Processing scene {i+1}/{len(all_scenes)}: {scene_title}")
        
        # Use CleanScenesFilter's should_keep_scene method
        should_keep, reason = filter_engine.should_keep_scene(scene)
        
        if should_keep:
            logger.debug(f"✅ KEEP: {scene_title} - {reason}")
            scenes_to_keep.append(scene_title)
        else:
            logger.info(f"🔥 MARKED FOR DELETION: {scene_title} - {reason}")
            scenes_to_delete.append((scene_id, scene_title))
    
    # Summary
    logger.info(f"")
    logger.info(f"📊 === CLEANING SUMMARY ===")
    logger.info(f"🔍 Total scenes processed: {len(all_scenes)}")
    logger.info(f"✅ Scenes to keep: {len(scenes_to_keep)}")
    logger.info(f"🔥 Scenes to delete: {len(scenes_to_delete)}")
    
    
    # Actually delete the scenes (if not dry run)
    if not dry_run and scenes_to_delete:
        logger.info(f"")
        logger.info(f"🔥 DELETING {len(scenes_to_delete)} SCENES...")
        deleted_count = 0
        failed_count = 0
        
        for scene_id, scene_title in scenes_to_delete:
            logger.info(f"   🗑️  Deleting: {scene_title}")
            success = stash_api.delete_scene(scene_id, delete_file=True)
            if success:
                deleted_count += 1
                logger.info(f"   ✅ Successfully deleted")
            else:
                failed_count += 1
                logger.error(f"   ❌ Failed to delete")
        
        logger.info(f"")
        logger.info(f"📊 Deletion results: {deleted_count} deleted, {failed_count} failed")
        
    elif dry_run and scenes_to_delete:
        logger.info(f"")
        logger.info(f"💧 DRY RUN: Would delete {len(scenes_to_delete)} scenes")
    else:
        logger.info(f"")
        logger.info("✅ No scenes matched the deletion criteria.")
    
    logger.info("🏁 === COMPLETED CLEAN EXISTING SCENES JOB ===")
