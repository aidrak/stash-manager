import logging
from src.filter import SceneFilter
from src.stash_api import StashApi
from src.whisparr import WhisparrApi

def process_scenes(config: dict, stash_api: StashApi):
    """
    Processes scenes from Stash, filters them, and adds them to Whisparr.
    """
    logging.info("Starting scene processing job.")
    
    # Initialize APIs
    whisparr_config = config.get('whisparr', {})
    whisparr_api = WhisparrApi(whisparr_config)
    
    # Initialize filter
    scene_filter = SceneFilter(config)
    
    # Get scenes from Stash
    scene_limit = config.get('processing', {}).get('scene_limit', 100)
    all_scenes = stash_api.find_scenes(limit=scene_limit)
    
    if not all_scenes:
        logging.info("No scenes found in Stash to process.")
        return
        
    logging.info(f"Found {len(all_scenes)} scenes to process.")
    
    for scene in all_scenes:
        should_add, reason = scene_filter.should_add_scene(scene)
        
        if should_add:
            logging.info(f"Scene '{scene.get('title')}' passed filters. Adding to Whisparr.")
            # Here you would typically add the scene to a database or directly to Whisparr
            # For this example, we'll just log it.
            # Example: whisparr_api.add_series(scene.get('title'))
        else:
            logging.info(f"Scene '{scene.get('title')}' was filtered out. Reason: {reason}")
            
    logging.info("Scene processing job finished.")
