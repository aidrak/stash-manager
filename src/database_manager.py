import json
import logging
import os
import sqlite3
from contextlib import contextmanager
from typing import Any, Dict, List, Optional

logger = logging.getLogger("stash_manager.database")


class DatabaseManager:
    """Manages SQLite database operations for Stash Manager."""

    def __init__(self, db_path: str = "/config/stash_manager.db"):
        self.db_path = db_path
        self.init_database()

    def init_database(self):
        """Initialize database and create tables if they don't exist."""
        try:
            with self.get_connection() as conn:
                # Read and execute schema
                schema_path = os.path.join(os.path.dirname(__file__), "schema.sql")
                if os.path.exists(schema_path):
                    with open(schema_path, "r") as f:
                        schema = f.read()
                    conn.executescript(schema)
                else:
                    # Fallback: create schema inline
                    self._create_tables(conn)

                conn.commit()
                logger.info("Database initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize database: {e}")
            raise

    @contextmanager
    def get_connection(self):
        """Context manager for database connections."""
        conn = sqlite3.connect(self.db_path, timeout=30.0)
        conn.row_factory = sqlite3.Row  # Enable column access by name
        conn.execute("PRAGMA foreign_keys = ON")  # Enable foreign key constraints
        try:
            yield conn
        finally:
            conn.close()

    def _create_tables(self, conn):
        """Fallback method to create tables inline."""
        schema = """
        CREATE TABLE IF NOT EXISTS settings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            section TEXT NOT NULL,
            key TEXT NOT NULL,
            value TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(section, key)
        );

        CREATE TABLE IF NOT EXISTS filter_rules (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            context TEXT NOT NULL CHECK(context IN ('add_scenes', 'clean_scenes')),
            name TEXT NOT NULL,
            field TEXT NOT NULL,
            operator TEXT NOT NULL CHECK(operator IN (
                'include', 'exclude', 'is_larger_than', 'is_smaller_than'
            )),
            value TEXT,
            action TEXT NOT NULL CHECK(action IN ('accept', 'reject')),
            priority INTEGER NOT NULL,
            enabled BOOLEAN DEFAULT 1,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(context, priority)
        );

        CREATE TABLE IF NOT EXISTS job_runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            job_name TEXT NOT NULL,
            status TEXT NOT NULL CHECK(status IN (
                'running', 'completed', 'failed', 'cancelled'
            )),
            start_time DATETIME NOT NULL,
            end_time DATETIME,
            duration_seconds INTEGER,
            scenes_processed INTEGER DEFAULT 0,
            scenes_added INTEGER DEFAULT 0,
            scenes_deleted INTEGER DEFAULT 0,
            error_message TEXT,
            dry_run BOOLEAN DEFAULT 0,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS processed_scenes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            scene_id TEXT NOT NULL,
            scene_title TEXT,
            source TEXT NOT NULL CHECK(source IN ('stashdb', 'local_stash')),
            action_taken TEXT NOT NULL CHECK(action_taken IN (
                'added', 'rejected', 'deleted', 'kept'
            )),
            rule_matched TEXT,
            processed_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            job_run_id INTEGER,
            FOREIGN KEY (job_run_id) REFERENCES job_runs(id),
            UNIQUE(scene_id, source)
        );
        CREATE TABLE IF NOT EXISTS one_time_searches (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            start_date TEXT NOT NULL,
            end_date TEXT NOT NULL,
            status TEXT NOT NULL CHECK(status IN (
                'running', 'completed', 'failed', 'cancelled'
            )),
            results TEXT, -- JSON string with search results
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            completed_at DATETIME,
            duration_seconds REAL
        );

        CREATE INDEX IF NOT EXISTS idx_one_time_searches_date
            ON one_time_searches(created_at);
        CREATE INDEX IF NOT EXISTS idx_one_time_searches_status
            ON one_time_searches(status);
        """
        conn.executescript(schema)

    # ============================================================================
    # SETTINGS MANAGEMENT
    # ============================================================================

    def get_setting(self, section: str, key: str, default: Any = None) -> Any:
        """Get a single setting value."""
        with self.get_connection() as conn:
            cursor = conn.execute(
                "SELECT value FROM settings WHERE section = ? AND key = ?",
                (section, key),
            )
            row = cursor.fetchone()
            if row:
                try:
                    return json.loads(row["value"])
                except json.JSONDecodeError:
                    return row["value"]
            return default

    def set_setting(self, section: str, key: str, value: Any):
        """Set a setting value."""
        json_value = json.dumps(value) if not isinstance(value, str) else value
        with self.get_connection() as conn:
            conn.execute(
                """INSERT OR REPLACE INTO settings (section, key, value, updated_at)
                   VALUES (?, ?, ?, CURRENT_TIMESTAMP)""",
                (section, key, json_value),
            )
            conn.commit()

    def get_all_settings(self) -> Dict[str, Dict[str, Any]]:
        """Get all settings organized by section."""
        with self.get_connection() as conn:
            cursor = conn.execute("SELECT section, key, value FROM settings")
            settings = {}
            for row in cursor:
                section = row["section"]
                if section not in settings:
                    settings[section] = {}
                try:
                    settings[section][row["key"]] = json.loads(row["value"])
                except json.JSONDecodeError:
                    settings[section][row["key"]] = row["value"]
            return settings

    # ============================================================================
    # FILTER RULES MANAGEMENT
    # ============================================================================

    def get_filter_rules(self, context: str) -> List[Dict[str, Any]]:
        """Get filter rules for a specific context, ordered by priority."""
        with self.get_connection() as conn:
            cursor = conn.execute(
                """SELECT id, name, field, operator, value, action, priority, enabled
                   FROM filter_rules
                   WHERE context = ? AND enabled = 1
                   ORDER BY priority""",
                (context,),
            )
            return [dict(row) for row in cursor]

    def add_filter_rule(
        self,
        context: str,
        name: str,
        field: str,
        operator: str,
        value: str,
        action: str,
    ) -> int:
        """Add a new filter rule."""
        with self.get_connection() as conn:
            # Get next priority
            cursor = conn.execute(
                "SELECT COALESCE(MAX(priority), 0) + 1 FROM filter_rules "
                "WHERE context = ?",
                (context,),
            )
            priority = cursor.fetchone()

            # Insert rule
            cursor = conn.execute(
                """INSERT INTO filter_rules
                   (context, name, field, operator, value, action, priority)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (context, name, field, operator, value, action, priority),
            )
            conn.commit()
            return cursor.lastrowid

    def update_filter_rule(
        self, rule_id: int, field: str, operator: str, value: str, action: str
    ):
        """Update an existing filter rule."""
        with self.get_connection() as conn:
            conn.execute(
                """UPDATE filter_rules
                   SET field = ?, operator = ?, value = ?, action = ?,
                       updated_at = CURRENT_TIMESTAMP
                   WHERE id = ?""",
                (field, operator, value, action, rule_id),
            )
            conn.commit()

    def delete_filter_rule(self, rule_id: int):
        """Delete a filter rule and reorder priorities."""
        with self.get_connection() as conn:
            # Get context and priority of rule to delete
            cursor = conn.execute(
                "SELECT context, priority FROM filter_rules WHERE id = ?", (rule_id,)
            )
            row = cursor.fetchone()
            if not row:
                return

            context, deleted_priority = row["context"], row["priority"]

            # Delete the rule
            conn.execute("DELETE FROM filter_rules WHERE id = ?", (rule_id,))

            # Reorder priorities
            conn.execute(
                """UPDATE filter_rules
                   SET priority = priority - 1
                   WHERE context = ? AND priority > ?""",
                (context, deleted_priority),
            )
            conn.commit()

    def reorder_filter_rules(self, context: str, rule_ids: List[int]):
        """Reorder filter rules based on provided list of IDs."""
        with self.get_connection() as conn:
            for new_priority, rule_id in enumerate(rule_ids, 1):
                conn.execute(
                    "UPDATE filter_rules SET priority = ? WHERE id = ? AND context = ?",
                    (new_priority, rule_id, context),
                )
            conn.commit()

    # ============================================================================
    # JOB MANAGEMENT
    # ============================================================================

    def start_job_run(self, job_name: str, dry_run: bool = False) -> int:
        """Start a new job run and return its ID."""
        with self.get_connection() as conn:
            cursor = conn.execute(
                """INSERT INTO job_runs (job_name, status, start_time, dry_run)
                   VALUES (?, 'running', CURRENT_TIMESTAMP, ?)""",
                (job_name, dry_run),
            )
            conn.commit()
            return cursor.lastrowid

    def finish_job_run(
        self,
        job_run_id: int,
        status: str,
        scenes_processed: int = 0,
        scenes_added: int = 0,
        scenes_deleted: int = 0,
        error_message: Optional[str] = None,
    ):
        """Complete a job run with results."""
        with self.get_connection() as conn:
            conn.execute(
                """UPDATE job_runs
                   SET status = ?, end_time = CURRENT_TIMESTAMP,
                       duration_seconds = (julianday(CURRENT_TIMESTAMP) -
                                         julianday(start_time)) * 86400,
                       scenes_processed = ?, scenes_added = ?, scenes_deleted = ?,
                       error_message = ?
                   WHERE id = ?""",
                (
                    status,
                    scenes_processed,
                    scenes_added,
                    scenes_deleted,
                    error_message,
                    job_run_id,
                ),
            )
            conn.commit()

    def get_last_job_run(self, job_name: str) -> Optional[Dict[str, Any]]:
        """Get the most recent job run for a job."""
        with self.get_connection() as conn:
            cursor = conn.execute(
                """SELECT * FROM job_runs
                   WHERE job_name = ? AND status IN ('completed', 'failed')
                   ORDER BY start_time DESC LIMIT 1""",
                (job_name,),
            )
            row = cursor.fetchone()
            return dict(row) if row else None

    # ============================================================================
    # SCENE PROCESSING TRACKING
    # ============================================================================

    def record_scene_processing(
        self,
        scene_id: str,
        scene_title: str,
        source: str,
        action_taken: str,
        rule_matched: Optional[str] = None,
        job_run_id: int = None,
    ):
        """Record that a scene was processed."""
        with self.get_connection() as conn:
            conn.execute(
                """INSERT OR REPLACE INTO processed_scenes
                   (scene_id, scene_title, source, action_taken, rule_matched,
                    job_run_id)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (
                    scene_id,
                    scene_title,
                    source,
                    action_taken,
                    rule_matched,
                    job_run_id,
                ),
            )
            conn.commit()

    def was_scene_processed(self, scene_id: str, source: str) -> bool:
        """Check if a scene was already processed."""
        with self.get_connection() as conn:
            cursor = conn.execute(
                "SELECT 1 FROM processed_scenes WHERE scene_id = ? AND source = ?",
                (scene_id, source),
            )
            return cursor.fetchone() is not None

    # ============================================================================
    # ONE-TIME SEARCH MANAGEMENT
    # ============================================================================

    def record_one_time_search(
        self, start_date: str, end_date: str, status: str = "running"
    ) -> int:
        """Record a new one-time search"""
        with self.get_connection() as conn:
            cursor = conn.execute(
                """INSERT INTO one_time_searches
                   (start_date, end_date, status, created_at)
                   VALUES (?, ?, ?, CURRENT_TIMESTAMP)""",
                (start_date, end_date, status),
            )
            conn.commit()
            return cursor.lastrowid

    def finish_one_time_search(
        self, search_id: int, status: str, results: dict = None
    ):
        """Update a one-time search with completion status and results"""
        results_json = json.dumps(results) if results else None

        with self.get_connection() as conn:
            conn.execute(
                """UPDATE one_time_searches
                   SET status = ?, results = ?, completed_at = CURRENT_TIMESTAMP,
                       duration_seconds = (julianday(CURRENT_TIMESTAMP) -
                                         julianday(created_at)) * 86400
                   WHERE id = ?""",
                (status, results_json, search_id),
            )
            conn.commit()

    def get_recent_one_time_searches(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get recent one-time searches with results"""
        with self.get_connection() as conn:
            cursor = conn.execute(
                """SELECT id, start_date, end_date, status, results,
                           created_at, completed_at, duration_seconds
                   FROM one_time_searches
                   ORDER BY created_at DESC
                   LIMIT ?""",
                (limit,),
            )

            searches = []
            for row in cursor:
                search = dict(row)
                if search["results"]:
                    try:
                        search["results"] = json.loads(search["results"])
                    except json.JSONDecodeError:
                        search["results"] = {}
                else:
                    search["results"] = {}
                searches.append(search)

            return searches

    def get_one_time_search(self, search_id: int) -> Optional[Dict[str, Any]]:
        """Get a specific one-time search by ID"""
        with self.get_connection() as conn:
            cursor = conn.execute(
                """SELECT id, start_date, end_date, status, results,
                           created_at, completed_at, duration_seconds
                   FROM one_time_searches WHERE id = ?""",
                (search_id,),
            )
            row = cursor.fetchone()
            if row:
                search = dict(row)
                if search["results"]:
                    try:
                        search["results"] = json.loads(search["results"])
                    except json.JSONDecodeError:
                        search["results"] = {}
                return search
            return None

    def delete_old_one_time_searches(self, days_old: int = 30):
        """Clean up old one-time search records"""
        with self.get_connection() as conn:
            conn.execute(
                """DELETE FROM one_time_searches
                   WHERE created_at < datetime('now', '-{} days')""".format(
                    days_old
                )
            )
            conn.commit()
