import json
import logging
import sqlite3
import threading
import time
from datetime import datetime, timezone
from typing import Any, Optional, Union


class DatabaseManager:
    _instances = {}
    _lock = threading.Lock()

    def __new__(cls, db_path: str = None):
        if db_path is None:
            import os

            db_path = os.environ.get("DATABASE_PATH", "/config/stash_manager.db")

        with cls._lock:
            if db_path not in cls._instances:
                instance = super().__new__(cls)
                cls._instances[db_path] = instance
            return cls._instances[db_path]

    def __init__(self, db_path: str = None) -> None:
        if hasattr(self, "_initialized"):
            return

        if db_path is None:
            import os

            db_path = os.environ.get("DATABASE_PATH", "/config/stash_manager.db")

        self.db_path = db_path
        self.conn = None
        self._initialized = True
        self.connect()
        self.init_db()

    def connect(self) -> None:
        try:
            self.conn = sqlite3.connect(
                self.db_path,
                check_same_thread=False,
                timeout=30.0,
                isolation_level=None,
            )
            self.conn.row_factory = sqlite3.Row
            self.conn.execute("PRAGMA journal_mode=WAL")
            self.conn.execute("PRAGMA busy_timeout=30000")
            self.conn.execute("PRAGMA synchronous=NORMAL")
            logging.info(f"Database connected at {self.db_path}")
        except sqlite3.Error as e:
            logging.error(f"Database connection error: {e}")
            raise

    def close(self) -> None:
        if self.conn:
            self.conn.close()
            self.conn = None
            logging.info("Database connection closed.")

    def execute_query(
        self,
        query: str,
        params: tuple = (),
        fetch: Optional[str] = None,
        retries: int = 3,
    ) -> Union[sqlite3.Row, list[sqlite3.Row], int, None]:
        for attempt in range(retries):
            if not self.conn:
                try:
                    self.connect()
                except Exception as e:
                    logging.error(
                        f"Failed to reconnect to database (attempt {attempt + 1}): {e}"
                    )
                    if attempt == retries - 1:
                        return None
                    time.sleep(0.5 * (attempt + 1))
                    continue

            try:
                with self.conn:
                    cursor = self.conn.cursor()
                    cursor.execute(query, params)
                    if fetch == "one":
                        return cursor.fetchone()
                    if fetch == "all":
                        return cursor.fetchall()
                    return cursor.lastrowid
            except (sqlite3.OperationalError, sqlite3.DatabaseError) as e:
                logging.error(f"Database query failed (attempt {attempt + 1}): {e}")
                if (
                    "database is locked" in str(e).lower()
                    or "disk I/O error" in str(e).lower()
                ):
                    if attempt < retries - 1:
                        time.sleep(0.5 * (attempt + 1))
                        self.conn = None
                        continue
                return None
            except sqlite3.Error as e:
                logging.error(f"Database query failed: {e}")
                return None
        return None

    def init_db(self) -> None:
        # Main settings table (key-value store for JSON blobs)
        self.execute_query(
            """
            CREATE TABLE IF NOT EXISTS settings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                section TEXT NOT NULL,
                key TEXT NOT NULL,
                value TEXT NOT NULL,
                UNIQUE(section, key)
            );
        """
        )

        # Filter rules table
        self.execute_query(
            """
            CREATE TABLE IF NOT EXISTS filter_rules (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                context TEXT NOT NULL,
                name TEXT NOT NULL,
                field TEXT NOT NULL,
                operator TEXT NOT NULL,
                value TEXT NOT NULL,
                action TEXT NOT NULL,
                priority INTEGER NOT NULL DEFAULT 0
            );
        """
        )

        # Job run tracking table
        self.execute_query(
            """
            CREATE TABLE IF NOT EXISTS job_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                job_name TEXT NOT NULL,
                start_time DATETIME NOT NULL,
                end_time DATETIME,
                status TEXT NOT NULL,
                dry_run BOOLEAN NOT NULL,
                details TEXT
            );
        """
        )
        # Tasks table
        self.execute_query(
            """
            CREATE TABLE IF NOT EXISTS tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                type TEXT NOT NULL,
                scene_id TEXT,
                status TEXT NOT NULL DEFAULT 'pending',
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            );
        """
        )

        # One-time searches table
        self.execute_query(
            """
            CREATE TABLE IF NOT EXISTS one_time_searches (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                start_date TEXT NOT NULL,
                end_date TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'running',
                results TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                completed_at DATETIME,
                duration_seconds REAL
            );
        """
        )
        logging.info("Database initialized.")

    def get_all_settings(self) -> dict[str, dict[str, Any]]:
        rows = self.execute_query(
            "SELECT section, key, value FROM settings", fetch="all"
        )
        settings = {}
        if isinstance(rows, list):
            for row in rows:
                if row["section"] not in settings:
                    settings[row["section"]] = {}
                try:
                    settings[row["section"]][row["key"]] = json.loads(row["value"])
                except json.JSONDecodeError:
                    settings[row["section"]][row["key"]] = row["value"]
        return settings

    def get_setting(self, section: str, key: str, default: Any = None) -> Any:
        row = self.execute_query(
            "SELECT value FROM settings WHERE section = ? AND key = ?",
            (section, key),
            fetch="one",
        )
        if isinstance(row, sqlite3.Row):
            try:
                return json.loads(row["value"])
            except json.JSONDecodeError:
                return row["value"]
        return default

    def set_setting(self, section: str, key: str, value: Any) -> None:
        # Overwrite existing or insert new
        query = """
            INSERT INTO settings (section, key, value) VALUES (?, ?, ?)
            ON CONFLICT(section, key) DO UPDATE SET value = excluded.value;
        """
        self.execute_query(query, (section, key, json.dumps(value)))

    def get_filter_rules(self, context: str) -> list[dict[str, Any]]:
        rows = self.execute_query(
            "SELECT * FROM filter_rules WHERE context = ?", (context,), fetch="all"
        )
        if isinstance(rows, list):
            return [dict(row) for row in rows]
        return []

    def add_filter_rule(
        self,
        context: str,
        name: str,
        field: str,
        operator: str,
        value: str,
        action: str,
        priority: int,
    ) -> Optional[int]:
        query = """
            INSERT INTO filter_rules (context, name, field, operator, value, action, priority)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """
        result = self.execute_query(
            query, (context, name, field, operator, value, action, priority)
        )
        return result if isinstance(result, int) else None

    def delete_filter_rule(self, rule_id: int) -> None:
        self.execute_query("DELETE FROM filter_rules WHERE id = ?", (rule_id,))

    def delete_filter_rules_by_context(self, context: str) -> None:
        self.execute_query("DELETE FROM filter_rules WHERE context = ?", (context,))

    def start_job_run(self, job_name: str, dry_run: bool = False) -> Optional[int]:
        query = """
            INSERT INTO job_runs (job_name, start_time, status, dry_run)
            VALUES (?, ?, ?, ?)
        """
        start_time = datetime.now(timezone.utc)
        result = self.execute_query(
            query, (job_name, start_time, "running", dry_run)
        )
        return result if isinstance(result, int) else None

    def finish_job_run(self, job_run_id: int, status: str, **kwargs: Any) -> None:
        query = """
            UPDATE job_runs
            SET end_time = ?, status = ?, details = ?
            WHERE id = ?
        """
        end_time = datetime.now(timezone.utc)
        details = json.dumps(kwargs)
        self.execute_query(query, (end_time, status, details, job_run_id))

    def get_last_job_run(self, job_name: str) -> Optional[dict[str, Any]]:
        query = (
            "SELECT * FROM job_runs WHERE job_name = ? ORDER BY start_time DESC LIMIT 1"
        )
        row = self.execute_query(query, (job_name,), fetch="one")
        return dict(row) if isinstance(row, sqlite3.Row) else None

    def get_pending_tasks(self, task_type: str) -> list[dict[str, Any]]:
        query = "SELECT * FROM tasks WHERE type = ? AND status = 'pending' ORDER BY created_at ASC"
        rows = self.execute_query(query, (task_type,), fetch="all")
        if rows and isinstance(rows, list):
            return [dict(row) for row in rows]
        return []

    # One-time search methods
    def record_one_time_search(
        self, start_date: str, end_date: str, status: str = "running"
    ) -> Optional[int]:
        """Record a new one-time search"""
        query = """
            INSERT INTO one_time_searches (start_date, end_date, status, created_at)
            VALUES (?, ?, ?, datetime('now'))
        """
        result = self.execute_query(query, (start_date, end_date, status))
        return result if isinstance(result, int) else None

    def finish_one_time_search(
        self, search_id: int, status: str, results: Optional[dict] = None
    ):
        """Update a one-time search with completion status and results"""
        import json

        results_json = json.dumps(results) if results else None

        query = """
            UPDATE one_time_searches
            SET status = ?, results = ?, completed_at = datetime('now'),
                duration_seconds = (julianday(datetime('now')) - julianday(created_at)) * 86400
            WHERE id = ?
        """
        self.execute_query(query, (status, results_json, search_id))

    def get_recent_one_time_searches(self, limit: int = 10) -> list[dict[str, Any]]:
        """Get recent one-time searches with results"""
        import json

        query = """
            SELECT id, start_date, end_date, status, results,
                   created_at, completed_at, duration_seconds
            FROM one_time_searches
            ORDER BY created_at DESC
            LIMIT ?
        """
        rows = self.execute_query(query, (limit,), fetch="all")
        if not rows or not isinstance(rows, list):
            return []

        searches = []
        for row in rows:
            if isinstance(row, sqlite3.Row):
                search = dict(row)
                if search.get("results"):
                    try:
                        search["results"] = json.loads(search["results"])
                    except json.JSONDecodeError:
                        search["results"] = {}
                else:
                    search["results"] = {}
                searches.append(search)
        return searches

    def get_one_time_search(self, search_id: int) -> Optional[dict[str, Any]]:
        """Get a specific one-time search by ID"""
        import json

        query = """
            SELECT id, start_date, end_date, status, results,
                   created_at, completed_at, duration_seconds
            FROM one_time_searches WHERE id = ?
        """
        row = self.execute_query(query, (search_id,), fetch="one")
        if isinstance(row, sqlite3.Row):
            search = dict(row)
            if search.get("results"):
                try:
                    search["results"] = json.loads(search["results"])
                except json.JSONDecodeError:
                    search["results"] = {}
            else:
                search["results"] = {}
            return search
        return None
