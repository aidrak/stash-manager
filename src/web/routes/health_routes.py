import logging
import os

from flask import Blueprint, jsonify

from src.core.database_manager import DatabaseManager
from src.core.scheduler import scheduler

health_bp = Blueprint("health", __name__)

logger = logging.getLogger(__name__)


@health_bp.route("/health")
def health_check():
    """Health check endpoint for container orchestration"""
    status = "healthy"
    checks = {}

    # Check database connectivity
    try:
        db_path = os.environ.get("DATABASE_PATH", "/config/stash_manager.db")
        db = DatabaseManager(db_path)
        db.execute_query("SELECT 1", fetch="one")
        checks["database"] = {"status": "ok", "path": db_path}
        db.close()
    except Exception as e:
        checks["database"] = {"status": "error", "error": str(e)}
        status = "unhealthy"

    # Check job scheduler
    try:
        job_count = len(scheduler.get_jobs())
        checks["scheduler"] = {"status": "ok", "jobs": job_count}
    except Exception as e:
        checks["scheduler"] = {"status": "error", "error": str(e)}
        status = "unhealthy"

    # Check log directory
    try:
        log_dir = "/config/logs"
        if os.path.exists(log_dir) and os.access(log_dir, os.W_OK):
            checks["logs"] = {"status": "ok", "path": log_dir}
        else:
            checks["logs"] = {"status": "warning", "message": "Log directory not accessible"}
    except Exception as e:
        checks["logs"] = {"status": "error", "error": str(e)}

    response = {
        "status": status,
        "timestamp": scheduler.get_jobs()[0].next_run.isoformat() if scheduler.get_jobs() else None,
        "checks": checks,
    }

    return jsonify(response), 200 if status == "healthy" else 503


@health_bp.route("/ready")
def readiness_check():
    """Readiness check - simpler version for container startup"""
    try:
        # Just check if we can connect to database
        db_path = os.environ.get("DATABASE_PATH", "/config/stash_manager.db")
        db = DatabaseManager(db_path)
        db.execute_query("SELECT 1", fetch="one")
        db.close()
        return jsonify({"status": "ready"}), 200
    except Exception as e:
        logger.error(f"Readiness check failed: {e}")
        return jsonify({"status": "not ready", "error": str(e)}), 503
