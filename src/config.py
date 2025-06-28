import yaml
import logging
import os

def validate_config(config):
    """Validates the provided configuration."""
    if not config:
        return False
    
    if not config.get('stash', {}).get('url') or not config.get('stash', {}).get('api_key'):
        logging.error("Stash URL and API key are required. Set STASH_URL and STASH_API_KEY environment variables.")
        return False
        
    if not config.get('whisparr', {}).get('url') or not config.get('whisparr', {}).get('api_key'):
        logging.error("Whisparr URL and API key are required. Set WHISPARR_URL and WHISPARR_API_KEY environment variables.")
        return False
        
    return True

def override_with_env_vars(config):
    """Overrides configuration with environment variables if they are set."""
    
    # Stash settings
    if os.environ.get('STASH_URL'):
        config['stash']['url'] = os.environ.get('STASH_URL')
    if os.environ.get('STASH_API_KEY'):
        config['stash']['api_key'] = os.environ.get('STASH_API_KEY')

    # Whisparr settings
    if os.environ.get('WHISPARR_URL'):
        config['whisparr']['url'] = os.environ.get('WHISPARR_URL')
    if os.environ.get('WHISPARR_API_KEY'):
        config['whisparr']['api_key'] = os.environ.get('WHISPARR_API_KEY')
    if os.environ.get('STASHDB_API_KEY'):
        config['whisparr']['stashdb_api_key'] = os.environ.get('STASHDB_API_KEY')

    # Cron settings
    if os.environ.get('CRON_FREQUENCY'):
        config['cron']['frequency'] = int(os.environ.get('CRON_FREQUENCY'))

    # Log settings
    if os.environ.get('LOG_LEVEL'):
        config['logs']['level'] = os.environ.get('LOG_LEVEL')

    # Processing settings
    if os.environ.get('SCENE_LIMIT'):
        config['processing']['scene_limit'] = int(os.environ.get('SCENE_LIMIT'))

    # Filter controls
    if os.environ.get('ENABLE_TITLE_FILTERS'):
        config['filter_controls']['enable_title_filters'] = os.environ.get('ENABLE_TITLE_FILTERS').lower() in ['true', '1', 'yes']
    if os.environ.get('ENABLE_PERFORMER_FILTERS'):
        config['filter_controls']['enable_performer_filters'] = os.environ.get('ENABLE_PERFORMER_FILTERS').lower() in ['true', '1', 'yes']
    if os.environ.get('ENABLE_STUDIO_FILTERS'):
        config['filter_controls']['enable_studio_filters'] = os.environ.get('ENABLE_STUDIO_FILTERS').lower() in ['true', '1', 'yes']
    if os.environ.get('ENABLE_ETHNICITY_FILTERS'):
        config['filter_controls']['enable_ethnicity_filters'] = os.environ.get('ENABLE_ETHNICITY_FILTERS').lower() in ['true', '1', 'yes']
    if os.environ.get('ENABLE_BREAST_SIZE_FILTERS'):
        config['filter_controls']['enable_breast_size_filters'] = os.environ.get('ENABLE_BREAST_SIZE_FILTERS').lower() in ['true', '1', 'yes']
    if os.environ.get('ENABLE_TAG_FILTERS'):
        config['filter_controls']['enable_tag_filters'] = os.environ.get('ENABLE_TAG_FILTERS').lower() in ['true', '1', 'yes']

    return config

def load_config(config_path='/config/config.yaml'):
    """Loads configuration from YAML and overrides with environment variables."""
    try:
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)
    except FileNotFoundError:
        logging.error(f"Configuration file not found at {config_path}")
        # Create a default config structure if file doesn't exist
        config = {
            'stash': {}, 'whisparr': {}, 'cron': {}, 'logs': {},
            'processing': {}, 'filter_controls': {}
        }
    except yaml.YAMLError as e:
        logging.error(f"Error parsing YAML file: {e}")
        return None

    # Override with environment variables
    config = override_with_env_vars(config)

    if not validate_config(config):
        logging.error("Configuration validation failed.")
        return None
        
    logging.info("Configuration loaded and validated successfully.")
    return config
