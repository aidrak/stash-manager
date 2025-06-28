import logging
import schedule
import time
from src.config import load_config
from src.db import initialize_db
from src.processor import process_scenes
from src.stash_api import StashApi

def main():
    """Main function to run the Stash Manager."""
    config = load_config()
    if not config:
        logging.error("Exiting due to missing configuration.")
        return

    # Configure logging
    log_level = config.get('logs', {}).get('level', 'INFO').upper()
    logging.basicConfig(level=log_level, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

    # Initialize database
    db_path = config.get('database', {}).get('path', '/config/stash_manager.db')
    initialize_db(db_path)

    # Initialize Stash API
    stash_config = config.get('stash', {})
    stash_api = StashApi(stash_config)

    # Get cron frequency
    cron_frequency = config.get('cron', {}).get('frequency', 60)

    # Schedule the main processing job
    schedule.every(cron_frequency).minutes.do(process_scenes, config, stash_api)

    logging.info(f"Stash Manager started. Will run every {cron_frequency} minutes.")

    # Run the scheduler
    while True:
        schedule.run_pending()
        time.sleep(1)

if __name__ == "__main__":
    main()
