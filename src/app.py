import os
import sys
import yaml
import logging
import threading
import schedule
import time
import datetime
import json  # NEW: Added for one-time search
from datetime import timedelta  # NEW: Added for one-time search
from zoneinfo import ZoneInfo
from flask import Flask, render_template, request, redirect, url_for, jsonify, flash

# Add the src directory to Python path for absolute imports FIRST
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

# THEN import from src (after path is set)
from src.scheduler import scheduler
from src.processor import add_new_scenes_to_whisparr, clean_existing_scenes_from_stash, generate_metadata
from src.stash_api import StashAPI
from src.stashdb_conditions import STASHDB_CONDITIONS  # Changed: separate files
from src.local_stash_conditions import LOCAL_STASH_CONDITIONS  # Changed: separate files
from src.config import get_config
from src.database_manager import DatabaseManager
from src.config import get_database, get_filter_rules, save_filter_rules, get_setting, set_setting
from src.one_time_search import one_time_search_bp, is_one_time_search_running
from src.utils import set_active_page

app = Flask(__name__)
app.config['SECRET_KEY'] = os.urandom(24)

# Register the one-time search blueprint
app.register_blueprint(one_time_search_bp)

CONFIG_PATH = '/config/app_state.yaml'

# ============================================================================
# FILTER CONTEXTS
# ============================================================================

# Filter contexts for different operations
FILTER_CONTEXTS = {
    'add_scenes': {
        'label': 'Add New Scenes',
        'description': 'Rules for adding new scenes from StashDB to Whisparr (Conservative: only add explicit accepts)'
    },
    'clean_scenes': {
        'label': 'Clean Existing Scenes', 
        'description': 'Rules for removing scenes from local Stash (Conservative: only delete explicit rejects)'
    }
}

def run_scheduler():
    """Run the job scheduler in a separate thread"""
    while True:
        scheduler.run_pending()
        time.sleep(1)

import coloredlogs

def setup_logging(config):
    """Setup logging based on configuration"""
    log_level = config.get('logs', {}).get('level', 'INFO').upper()
    
    # Configure the root logger
    coloredlogs.install(
        level=log_level,
        fmt='%(asctime)s - %(levelname)s - %(message)s',
        logger=logging.getLogger()
    )

    # Update werkzeug logger level
    werkzeug_logger = logging.getLogger('werkzeug')
    if log_level != 'DEBUG':
        werkzeug_logger.setLevel(logging.WARNING)
    else:
        werkzeug_logger.setLevel(logging.INFO)

    logging.info(f"Logging level set to {log_level}")

def setup_jobs():
    """Setup scheduled jobs based on configuration"""
    try:
        config = get_config(strict=False)
        if not config:
            logging.error("Could not load config for setting up jobs.")
            return

        # Setup logging
        setup_logging(config)

        # Clear existing jobs
        scheduler.clear()
        
        # Setup jobs based on config
        jobs_config = config.get('jobs', {})
        
        if jobs_config.get('add_new_scenes', {}).get('enabled'):
            interval_str = jobs_config.get('add_new_scenes', {}).get('schedule', 'daily')
            try:
                if 'hour' in interval_str:
                    hours = int(interval_str.split('-')[0])
                    job = scheduler.every(hours).hours.do(add_new_scenes_job)
                elif interval_str == 'daily':
                    job = scheduler.every().day.at("01:00").do(add_new_scenes_job)
                job.tag = 'add_new_scenes'
                logging.info(f"Scheduled 'Add New Scenes' job with interval: {interval_str}")
            except (ValueError, IndexError) as e:
                logging.error(f"Invalid interval format for add_new_scenes: {interval_str}. Error: {e}")


        if jobs_config.get('clean_existing_scenes', {}).get('enabled'):
            interval_str = jobs_config.get('clean_existing_scenes', {}).get('schedule', 'daily')
            try:
                if 'hour' in interval_str:
                    hours = int(interval_str.split('-')[0])
                    job = scheduler.every(hours).hours.do(clean_existing_scenes_job)
                elif interval_str == 'daily':
                    job = scheduler.every().day.at("01:00").do(clean_existing_scenes_job)
                job.tag = 'clean_existing_scenes'
                logging.info(f"Scheduled 'Clean Existing Scenes' job with interval: {interval_str}")
            except (ValueError, IndexError) as e:
                logging.error(f"Invalid interval format for clean_existing_scenes: {interval_str}. Error: {e}")

        if jobs_config.get('scan_and_identify', {}).get('enabled'):
            interval_str = jobs_config.get('scan_and_identify', {}).get('schedule', 'daily')
            try:
                if 'hour' in interval_str:
                    hours = int(interval_str.split('-')[0])
                    job = scheduler.every(hours).hours.do(scan_and_identify_job)
                elif interval_str == 'daily':
                    job = scheduler.every().day.at("02:00").do(scan_and_identify_job)
                job.tag = 'scan_and_identify'
                logging.info(f"Scheduled 'Scan & Identify' job with interval: {interval_str}")
            except (ValueError, IndexError) as e:
                logging.error(f"Invalid interval format for scan_and_identify: {interval_str}. Error: {e}")

        if jobs_config.get('generate_metadata', {}).get('enabled'):
            interval_str = jobs_config.get('generate_metadata', {}).get('schedule', 'daily')
            try:
                if 'hour' in interval_str:
                    hours = int(interval_str.split('-')[0])
                    job = scheduler.every(hours).hours.do(generate_metadata_job)
                elif interval_str == 'daily':
                    job = scheduler.every().day.at("03:00").do(generate_metadata_job)
                job.tag = 'generate_metadata'
                logging.info(f"Scheduled 'Generate Metadata' job with interval: {interval_str}")
            except (ValueError, IndexError) as e:
                logging.error(f"Invalid interval format for generate_metadata: {interval_str}. Error: {e}")
            
    except Exception as e:
        logging.error(f"Error setting up jobs: {e}")

def get_local_time():
    """Get current time in the container's timezone"""
    # Get timezone from environment variable or default to UTC
    tz_name = os.environ.get('TZ', 'UTC')
    try:
        tz = ZoneInfo(tz_name)
        return datetime.datetime.now(tz)
    except:
        # Fallback to UTC if timezone is invalid
        return datetime.datetime.now(ZoneInfo('UTC'))

def add_new_scenes_job(start_date=None, end_date=None):
    """Wrapper for add_new_scenes_to_whisparr job"""
    try:
        config = get_config(strict=True)
        if not config:
            logging.error("Could not load config for add_new_scenes job.")
            return

        setup_logging(config)

        # Get Stash connection details
        stash_url = os.environ.get('STASH_URL')
        stash_api_key = os.environ.get('STASH_API_KEY')
        if stash_url and stash_api_key:
            stash_api = StashAPI(url=stash_url, api_key=stash_api_key)
            add_new_scenes_to_whisparr(config, stash_api, start_date=start_date, end_date=end_date)
        else:
            logging.error("Missing Stash configuration")
        
        save_last_run_time('add_new_scenes')
        logging.info("Scheduled 'Add New Scenes' job completed")
    except Exception as e:
        logging.error(f"Error in add_new_scenes job: {e}")


def clean_existing_scenes_job():
    """Wrapper for clean_existing_scenes_from_stash job"""
    print("DEBUG: clean_existing_scenes_job thread started.")
    try:
        logging.info("Clean Existing Scenes Task Triggered")
        
        config = get_config(strict=True)
        if not config:
            print("DEBUG: Could not load config for clean_existing_scenes job.")
            logging.error("Could not load config for clean_existing_scenes job.")
            return

        setup_logging(config)

        dry_run = config.get('general', {}).get('dry_run', True)
        logging.info(f"Dry run mode: {dry_run}")
        
        stash_url = os.environ.get('STASH_URL')
        stash_api_key = os.environ.get('STASH_API_KEY')
        
        if stash_url and stash_api_key:
            print("DEBUG: Stash URL and API key found. Creating Stash API connection...")
            logging.info("Creating Stash API connection...")
            stash_api = StashAPI(url=stash_url, api_key=stash_api_key)
            
            print("DEBUG: Calling clean_existing_scenes_from_stash...")
            logging.info("Calling clean_existing_scenes_from_stash...")
            from src.processor import clean_existing_scenes_from_stash
            clean_existing_scenes_from_stash(config, stash_api)
            
            print("DEBUG: clean_existing_scenes_from_stash function completed.")
            logging.info("Clean function completed")
        else:
            print("DEBUG: Missing Stash configuration.")
            logging.error("Missing Stash configuration")
            return
        
        print("DEBUG: Job seems to have completed successfully.")
        logging.info("=== COMPLETED CLEAN EXISTING SCENES JOB ===")
        logging.info("Scheduled 'Clean Existing Scenes' job completed")
        save_last_run_time('clean_existing_scenes')
        
    except Exception as e:
        print(f"FATAL ERROR in clean_existing_scenes_job: {e}")
        logging.error(f"Error in clean_existing_scenes job: {e}")
        import traceback
        traceback.print_exc()

def scan_and_identify_job():
    """Combined wrapper for scan + identify job"""
    try:
        config = get_config(strict=True)
        if not config:
            logging.error("Could not load config for scan_and_identify job.")
            return

        setup_logging(config)

        stash_url = os.environ.get('STASH_URL')
        stash_api_key = os.environ.get('STASH_API_KEY')
        
        if stash_url and stash_api_key:
            stash_api = StashAPI(url=stash_url, api_key=stash_api_key)
            
            # Step 1: Trigger scan
            logging.info("Starting scan job...")
            scan_job_id = stash_api.trigger_scan()
            
            # Step 2: Wait for scan to complete
            logging.info("Waiting for scan to complete...")
            scan_success = stash_api.wait_for_job_completion(scan_job_id)
            
            if scan_success:
                logging.info("Scan completed successfully. Starting identify...")
                
                # Step 3: Trigger identify
                identify_job_id = stash_api.trigger_identify()
                
                # Step 4: Wait for identify to complete
                logging.info("Waiting for identify to complete...")
                identify_success = stash_api.wait_for_job_completion(identify_job_id)
                
                if identify_success:
                    logging.info("Scan + Identify completed successfully")
                else:
                    logging.error("Identify job failed")
            else:
                logging.error("Scan job failed - skipping identify")
        else:
            logging.error("Missing Stash configuration")
        
        save_last_run_time('scan_and_identify')
    except Exception as e:
        logging.error(f"Error in scan_and_identify job: {e}")

def generate_metadata_job():
    """Wrapper for generate_metadata job"""
    try:
        config = get_config(strict=True)
        if not config:
            logging.error("Could not load config for generate_metadata job.")
            return

        setup_logging(config)

        stash_url = os.environ.get('STASH_URL')
        stash_api_key = os.environ.get('STASH_API_KEY')
        if stash_url and stash_api_key:
            stash_api = StashAPI(url=stash_url, api_key=stash_api_key)
            generate_metadata(config, stash_api)
        else:
            logging.error("Missing Stash configuration")
        
        save_last_run_time('generate_metadata')
        logging.info("Scheduled 'Generate Metadata' job completed")
    except Exception as e:
        logging.error(f"Error in generate_metadata job: {e}")

def save_last_run_time(job_name):
    """Save the last run time for a job to the config file"""
    try:
        db = get_database()
        db.set_setting('jobs', f'{job_name}_last_run', get_local_time().isoformat())
    except Exception as e:
        logging.error(f"Error saving last run time for {job_name}: {e}")

def get_last_run_time(job_name):
    """Get the last run time for a job from the config file"""
    try:
        db = get_database()
        last_run_str = db.get_setting('jobs', f'{job_name}_last_run')
        if last_run_str:
            return datetime.datetime.fromisoformat(last_run_str)
        return None
    except Exception as e:
        logging.error(f"Error getting last run time for {job_name}: {e}")
        return None

# Job name mapping for user-friendly messages
JOB_NAMES = {
    'add_new_scenes': 'Add New Scenes',
    'clean_existing_scenes': 'Clean Existing Scenes', 
    'scan_and_identify': 'Scan & Identify',
    'generate_metadata': 'Generate Content'
}

# Start scheduler in background thread
scheduler_thread = threading.Thread(target=run_scheduler, daemon=True)
scheduler_thread.start()
logging.info("Job scheduler started in background thread")

CONFIG_PATH = '/config/app_state.yaml'

def get_rules(context='add_scenes'):
    return get_filter_rules(context)

def save_rules(rules, context='add_scenes'):
    save_filter_rules(rules, context)


@app.route('/')
def index():
    return redirect(url_for('add_scenes'))

@app.route('/add-scenes')
@set_active_page('add_scenes')
def add_scenes():
    rules = get_rules('add_scenes')
    current_context = FILTER_CONTEXTS['add_scenes']
    return 'add_scenes.html', {
        'rules': rules,
        'conditions': STASHDB_CONDITIONS,
        'current_context': current_context
    }

@app.route('/clean-scenes')
@set_active_page('clean_scenes')
def clean_scenes():
    rules = get_rules('clean_scenes')
    current_context = FILTER_CONTEXTS['clean_scenes']
    return 'clean_scenes.html', {
        'rules': rules,
        'conditions': LOCAL_STASH_CONDITIONS,
        'current_context': current_context
    }

@app.route('/add-scenes/add', methods=['POST'])
def add_add_rule():
    return handle_add_rule('add_scenes', 'add_scenes')

@app.route('/clean-scenes/add', methods=['POST'])
def add_clean_rule():
    return handle_add_rule('clean_scenes', 'clean_scenes')

@app.route('/add-scenes/edit/<int:rule_index>', methods=['POST'])
def edit_add_rule(rule_index):
    return handle_edit_rule('add_scenes', 'add_scenes', rule_index)

@app.route('/clean-scenes/edit/<int:rule_index>', methods=['POST'])
def edit_clean_rule(rule_index):
    return handle_edit_rule('clean_scenes', 'clean_scenes', rule_index)

@app.route('/add-scenes/delete/<int:rule_index>')
def delete_add_rule(rule_index):
    return handle_delete_rule('add_scenes', 'add_scenes', rule_index)

@app.route('/clean-scenes/delete/<int:rule_index>')
def delete_clean_rule(rule_index):
    return handle_delete_rule('clean_scenes', 'clean_scenes', rule_index)

@app.route('/add-scenes/reorder', methods=['POST'])
def reorder_add_rules():
    return handle_reorder_rules('add_scenes')

@app.route('/clean-scenes/reorder', methods=['POST'])
def reorder_clean_rules():
    return handle_reorder_rules('clean_scenes')

# Replace the rule handler functions in app.py with these:

def handle_add_rule(context, redirect_endpoint):
    try:
        rules = get_rules(context)
        print(f"Current {context} rules count: {len(rules)}")
        
        # Get the single condition and action from the form
        condition_type = request.form.get('condition-type')
        operator = request.form.get('condition-operator') 
        value = request.form.get('condition-value')
        action = request.form.get('action', 'reject')  # Default to reject for safety

        # Create new rule with single condition structure
        new_rule = {
            'name': f'Rule {len(rules) + 1}',
            'field': condition_type,
            'match': operator, 
            'value': value,
            'action': action
        }

        print(f"New {context} rule created: {new_rule}")
        rules.append(new_rule)
        print(f"Total {context} rules after append: {len(rules)}")
        
        save_rules(rules, context)
        flash('Rule added successfully!', 'success')
        
    except Exception as e:
        print(f"Error in add_rule for {context}: {e}")
        import traceback
        traceback.print_exc()
        flash(f'Error adding rule: {e}', 'error')
        
    return redirect(url_for(redirect_endpoint))

def handle_edit_rule(context, redirect_endpoint, rule_index):
    rules = get_rules(context)
    
    # Get the single condition and action from the form
    condition_type = request.form.get('condition-type')
    operator = request.form.get('condition-operator')
    value = request.form.get('condition-value') 
    action = request.form.get('action', 'reject')

    # Update rule with new single condition structure
    updated_rule = {
        'name': f'Rule {rule_index + 1}',
        'field': condition_type,
        'match': operator,
        'value': value, 
        'action': action
    }
    
    rules[rule_index] = updated_rule
    save_rules(rules, context)
    flash('Rule updated successfully!', 'success')
    return redirect(url_for(redirect_endpoint))

def handle_delete_rule(context, redirect_endpoint, rule_index):
    rules = get_rules(context)
    del rules[rule_index]
    save_rules(rules, context)
    flash('Rule deleted successfully!', 'success')
    return redirect(url_for(redirect_endpoint))

def handle_reorder_rules(context):
    rules = get_rules(context)
    new_order = request.json.get('new_order')
    if new_order:
        # Validate that all indices are within range
        if all(0 <= i < len(rules) for i in new_order):
            reordered_rules = [rules[i] for i in new_order]
            save_rules(reordered_rules, context)
        else:
            # If indices are invalid, just return current state
            pass
    return '', 204

@app.route('/tasks')
@set_active_page('tasks')
def tasks():
    config = get_config(strict=False)
    jobs_config = config.get('jobs', {})
    
    next_run_times = {}
    last_run_times = {}
    
    # Get schedule information using tags
    for job in scheduler.jobs:
        job_name = getattr(job, 'tag', 'unknown')
        
        if job.next_run:
            next_run_times[job_name] = job.next_run.strftime("%Y-%m-%d %H:%M:%S")
        else:
            next_run_times[job_name] = "Not scheduled"
        
        # Try to get last run time from config file first, then fallback to memory
        config_last_run = get_last_run_time(job_name)
        if config_last_run:
            last_run_times[job_name] = config_last_run.strftime("%Y-%m-%d %H:%M:%S")
        elif job.last_run:
            last_run_times[job_name] = job.last_run.strftime("%Y-%m-%d %H:%M:%S")
        else:
            last_run_times[job_name] = "Never run"

    # Ensure we have entries for all possible jobs
    job_names = ['add_new_scenes', 'clean_existing_scenes', 'scan_and_identify', 'generate_metadata']
    for job_name in job_names:
        if job_name not in next_run_times:
            next_run_times[job_name] = "Not scheduled"
        if job_name not in last_run_times:
            # Check config file for last run time even if job isn't scheduled
            config_last_run = get_last_run_time(job_name)
            if config_last_run:
                last_run_times[job_name] = config_last_run.strftime("%Y-%m-%d %H:%M:%S")
            else:
                last_run_times[job_name] = "Never run"

    return 'tasks.html', {
        'config': jobs_config,
        'next_run_times': next_run_times,
        'last_run_times': last_run_times
    }

def run_job_in_background(job_func, *args):
    """Runs a job in a background thread."""
    job_thread = threading.Thread(target=job_func, args=args)
    job_thread.start()
    job_thread.join()

@app.route('/run_job/<job_name>')
def run_job(job_name):
    try:
        # Check if we have the required credentials for this job
        stash_url = os.environ.get('STASH_URL')
        stash_api_key = os.environ.get('STASH_API_KEY')
        
        if not stash_url or not stash_api_key:
            return jsonify({'success': False, 'message': 'Missing Stash credentials. Please set STASH_URL and STASH_API_KEY environment variables.'}), 400

        # NEW: Check for conflicts with one-time search
        if job_name == 'add_new_scenes' and is_one_time_search_running():
            return jsonify({'success': False, 'message': 'One-time search is running. Please wait for completion.'}), 409

        if job_name == 'add_new_scenes':
            job_thread = threading.Thread(target=add_new_scenes_job)
            job_thread.daemon = True
            job_thread.start()
            friendly_name = "Add New Scenes"
            
        elif job_name == 'clean_existing_scenes':
            print("DEBUG: Entered 'clean_existing_scenes' block in run_job.")
            job_thread = threading.Thread(target=clean_existing_scenes_job)
            job_thread.daemon = True
            job_thread.start()
            friendly_name = "Clean Existing Scenes"
            
        elif job_name == 'scan_and_identify':
            job_thread = threading.Thread(target=scan_and_identify_job)
            job_thread.daemon = True
            job_thread.start()
            friendly_name = "Scan & Identify"
        elif job_name == 'generate_metadata':
            job_thread = threading.Thread(target=generate_metadata_job)
            job_thread.daemon = True
            job_thread.start()
            friendly_name = "Generate Content"
        else:
            return jsonify({'success': False, 'message': f'Unknown job: {job_name}'}), 400

        return jsonify({'success': True, 'message': f'{friendly_name} job started in background. Check logs for progress and completion.'})
        
    except Exception as e:
        logging.error(f"Error starting job: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'message': f"Error starting job: {str(e)}"}), 500

@app.route('/settings', methods=['GET', 'POST'])
@set_active_page('settings')
def settings():
    if request.method == 'POST':
        # Update settings in database
        set_setting('jobs', 'add_new_scenes', {
            'enabled': 'enable_add_new_scenes' in request.form,
            'schedule': request.form['add_new_scenes_schedule'],
            'search_back_days': int(request.form['add_new_scenes_search_back_days'])
        })
        set_setting('jobs', 'clean_existing_scenes', {
            'enabled': 'enable_clean_existing_scenes' in request.form,
            'schedule': request.form['clean_existing_scenes_schedule']
        })
        set_setting('jobs', 'scan_and_identify', {
            'enabled': 'enable_identify' in request.form,
            'schedule': request.form['scan_and_identify_schedule']
        })
        set_setting('jobs', 'generate_metadata', {
            'enabled': 'enable_generate_metadata' in request.form,
            'schedule': request.form['generate_metadata_schedule']
        })
        
        sources = []
        if 'identify_source_stashdb' in request.form:
            sources.append('stashdb')
        if 'identify_source_tpdb' in request.form:
            sources.append('tpdb')
        set_setting('identify', 'sources', sources)
        
        set_setting('logs', 'level', request.form['log_level'])
        set_setting('general', 'dry_run', 'dry_run' in request.form)

        # Refresh job schedule with new settings
        setup_jobs()
        logging.info("Job schedule refreshed after settings update")

        flash('Settings saved successfully!', 'success')
        return redirect(url_for('settings'))

    # Load current settings for GET request
    settings = get_config(strict=False)
    return 'settings.html', {'settings': settings}

# Setup jobs on startup
setup_jobs()

if __name__ == '__main__':
    # Load config to setup logging before running app
    try:
        config = get_config(strict=False)
        if config:
            setup_logging(config)
        else:
            # Fallback to basic config if config fails
            coloredlogs.install(level='INFO', fmt='%(asctime)s - %(levelname)s - %(message)s')
    except Exception as e:
        coloredlogs.install(level='INFO', fmt='%(asctime)s - %(levelname)s - %(message)s')
        logging.warning(f"Could not load config to set log level: {e}")

    # Get log level from config for debug mode
    config = get_config(strict=False) or {}
    log_level = config.get('logs', {}).get('level', 'INFO').upper()
    is_debug = log_level == 'DEBUG'

    app.run(host='0.0.0.0', port=5001, debug=is_debug)
