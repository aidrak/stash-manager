import logging
import os
from .add_scenes_filter import AddScenesFilter
from .clean_scenes_filter import CleanScenesFilter
from .stash_api import StashAPI
from .whisparr import WhisparrApi
from .config import get_identify_sources
from .stashdb_conditions import STASHDB_CONDITIONS
from .local_stash_conditions import LOCAL_STASH_CONDITIONS

logger = logging.getLogger(__name__)

def add_new_scenes_to_whisparr(config: dict, stash_api: StashAPI, start_date=None, end_date=None):
    """
    Finds new scenes in StashDB, filters them using AddScenesFilter, and adds them to Whisparr.
    """
    logger.debug("Entering add_new_scenes_to_whisparr function.")
    logger.info("=== STARTING ADD NEW SCENES JOB ===")
    
    # Use dedicated AddScenesFilter with StashDB conditions
    filter_engine = AddScenesFilter(config, STASHDB_CONDITIONS)
    whisparr_api = WhisparrApi(config.get('whisparr', {}))
    
    search_back_days = config.get('jobs', {}).get('add_new_scenes_search_back_days', 7)
    
    dry_run = config.get('general', {}).get('dry_run', False)
    logger.info(f"DRY RUN MODE: {dry_run}")
    
    logger.info("Fetching scenes from StashDB...")
    stashdb_api_key = os.environ.get('STASHDB_API_KEY')
    if not stashdb_api_key:
        logging.error("STASHDB_API_KEY environment variable not set. Cannot fetch scenes.")
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

    logger.info(f"=== RETRIEVED {len(new_scenes)} SCENES ===")

    for i, scene in enumerate(new_scenes):
        scene_title = scene.get('title', 'Untitled')
        logger.debug(f"Processing scene {i+1}/{len(new_scenes)}: {scene_title}")
        
        # Use AddScenesFilter's should_add_scene method
        should_add, reason = filter_engine.should_add_scene(scene)
        
        if should_add:
            logger.info(f"✅ PASSED: {scene_title} - {reason}")
            if not dry_run:
                result = whisparr_api.add_series(scene.get('title'))
                if result:
                    logger.info(f"   Successfully added to Whisparr")
                else:
                    logger.error(f"   Failed to add to Whisparr")
        else:
            logger.debug(f"❌ FILTERED: {scene_title} - {reason}")
            # For rejected scenes, add to Whisparr exclusion list
            if not dry_run:
                exclusion_result = whisparr_api.add_to_exclusion_list(scene.get('title'))
                if exclusion_result:
                    logger.debug(f"   Added to exclusion list")
    
    logger.info("=== COMPLETED ADD NEW SCENES JOB ===")

def clean_existing_scenes_from_stash(config: dict, stash_api: StashAPI):
    """
    Scans all existing scenes in local Stash and deletes ones that don't match the CleanScenesFilter.
    """
    logger.info("=== STARTING CLEAN EXISTING SCENES JOB ===")

    # Use dedicated CleanScenesFilter with Local Stash conditions
    filter_engine = CleanScenesFilter(config, LOCAL_STASH_CONDITIONS)
    
    dry_run = config.get('general', {}).get('dry_run', False)
    logger.info(f"DRY RUN MODE: {dry_run}")
    
    logger.info("Fetching scenes from local Stash...")
    all_scenes = stash_api.get_all_scenes()
    
    if not all_scenes:
        logger.info("No scenes found in local Stash.")
        return
    
    logger.info(f"Found {len(all_scenes)} scenes in local Stash")
    
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
            logger.info(f"🔥 DELETE: {scene_title} - {reason}")
            scenes_to_delete.append((scene_id, scene_title))
    
    # Summary
    logger.info(f"\n=== SUMMARY ===")
    logger.info(f"📊 Total scenes processed: {len(all_scenes)}")
    logger.info(f"✅ Scenes to keep: {len(scenes_to_keep)}")
    logger.info(f"🔥 Scenes to delete: {len(scenes_to_delete)}")
    
    if scenes_to_delete:
        logger.info(f"\n🔥 SCENES TO BE DELETED:")
        for _, title in scenes_to_delete:  # Show all scenes
            logger.info(f"   - {title}")
    
    # Actually delete the scenes (if not dry run)
    if not dry_run and scenes_to_delete:
        logger.info(f"\n🔥 DELETING {len(scenes_to_delete)} SCENES...")
        for scene_id, scene_title in scenes_to_delete:
            logger.info(f"   Deleting: {scene_title}")
            success = stash_api.delete_scene(scene_id, delete_file=True)
            if success:
                logger.info(f"   ✅ Successfully deleted")
            else:
                logger.error(f"   ❌ Failed to delete")
    elif dry_run and scenes_to_delete:
        logger.info(f"\n💧 DRY RUN: Would delete {len(scenes_to_delete)} scenes")
    else:
        logger.info("\n✅ No scenes matched the deletion criteria.")
    
    logger.info("=== COMPLETED CLEAN EXISTING SCENES JOB ===")
