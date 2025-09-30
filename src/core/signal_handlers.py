import atexit
import logging
import signal
from threading import Event

from src.core.scheduler import scheduler

shutdown_event = Event()
_cleanup_done = False


def _do_cleanup():
    """Perform cleanup operations (called only once)"""
    global _cleanup_done
    if _cleanup_done:
        return

    _cleanup_done = True
    logging.info("Performing cleanup...")

    try:
        scheduler.clear()
        logging.info("Scheduler cleared")
    except Exception as e:
        logging.error(f"Error clearing scheduler: {e}")


def signal_handler(signum, frame):
    """Handle shutdown signals gracefully"""
    logging.info(f"Received signal {signum}, initiating graceful shutdown...")
    shutdown_event.set()
    _do_cleanup()
    logging.info("Graceful shutdown complete")


def cleanup_on_exit():
    """Cleanup function called on normal exit"""
    logging.info("Application exiting, performing cleanup...")
    _do_cleanup()


def setup_signal_handlers():
    """Setup signal handlers for graceful shutdown"""
    signal.signal(signal.SIGTERM, signal_handler)  # Docker stop sends SIGTERM
    signal.signal(signal.SIGINT, signal_handler)  # Ctrl+C sends SIGINT
    atexit.register(cleanup_on_exit)
