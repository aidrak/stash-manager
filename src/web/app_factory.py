import os

from flask import Flask, g

from src.core.database_manager import DatabaseManager
from src.core.job_setup import setup_jobs
from src.core.signal_handlers import setup_signal_handlers
from src.web.one_time_search import one_time_search_bp
from src.web.routes.filter_routes import filter_bp
from src.web.routes.health_routes import health_bp
from src.web.routes.log_routes import log_bp
from src.web.routes.main_routes import main_bp
from src.web.routes.prowlarr_routes import prowlarr_bp
from src.web.routes.settings_routes import settings_bp
from src.web.routes.task_routes import task_bp


def create_app():
    """Create and configure Flask application"""
    app = Flask(__name__, template_folder="templates")

    # Get or generate persistent SECRET_KEY
    db = DatabaseManager()
    secret_key = db.get_setting("flask", "secret_key")
    if not secret_key:
        secret_key = os.urandom(24).hex()
        db.set_setting("flask", "secret_key", secret_key)
    app.config["SECRET_KEY"] = secret_key

    # Context processor to make active_page available in templates
    @app.context_processor
    def inject_active_page():
        return {"active_page": getattr(g, "active_page", None)}

    # Register blueprints
    app.register_blueprint(main_bp)
    app.register_blueprint(filter_bp)
    app.register_blueprint(task_bp)
    app.register_blueprint(settings_bp)
    app.register_blueprint(one_time_search_bp)
    app.register_blueprint(prowlarr_bp)
    app.register_blueprint(log_bp)
    app.register_blueprint(health_bp)

    # Setup signal handlers for graceful shutdown
    setup_signal_handlers()

    # Setup scheduled jobs
    setup_jobs()

    return app
