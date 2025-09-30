-- Stash Manager Database Schema
-- Settings table - replaces YAML config sections
CREATE TABLE IF NOT EXISTS settings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    section TEXT NOT NULL,
    key TEXT NOT NULL,
    value TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(section, key)
);
-- Filter rules table - replaces YAML filter_engine rules
CREATE TABLE IF NOT EXISTS filter_rules (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    context TEXT NOT NULL CHECK(context IN ('add_scenes', 'clean_scenes')),
    name TEXT NOT NULL,
    field TEXT NOT NULL,
    operator TEXT NOT NULL CHECK(operator IN ('include', 'exclude', 'is_larger_than', 'is_smaller_than')),
    value TEXT,
    action TEXT NOT NULL CHECK(action IN ('accept', 'reject')),
    priority INTEGER NOT NULL,
    enabled BOOLEAN DEFAULT 1,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(context, priority)
);
-- Job execution history
CREATE TABLE IF NOT EXISTS job_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_name TEXT NOT NULL,
    status TEXT NOT NULL CHECK(status IN ('running', 'completed', 'failed', 'cancelled')),
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
-- Processed scenes tracking (prevents duplicate processing)
CREATE TABLE IF NOT EXISTS processed_scenes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    scene_id TEXT NOT NULL,
    scene_title TEXT,
    source TEXT NOT NULL CHECK(source IN ('stashdb', 'local_stash')),
    action_taken TEXT NOT NULL CHECK(action_taken IN ('added', 'rejected', 'deleted', 'kept')),
    rule_matched TEXT,
    processed_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    job_run_id INTEGER,
    FOREIGN KEY (job_run_id) REFERENCES job_runs(id),
    UNIQUE(scene_id, source)
);
-- One-time search tracking (NEW TABLE)
CREATE TABLE IF NOT EXISTS one_time_searches (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    start_date TEXT NOT NULL,
    end_date TEXT NOT NULL,
    status TEXT NOT NULL CHECK(status IN ('running', 'completed', 'failed', 'cancelled')),
    results TEXT, -- JSON string with search results
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    completed_at DATETIME,
    duration_seconds REAL
);
-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_filter_rules_context ON filter_rules(context, priority);
CREATE INDEX IF NOT EXISTS idx_filter_rules_enabled ON filter_rules(enabled);
CREATE INDEX IF NOT EXISTS idx_job_runs_name_time ON job_runs(job_name, start_time);
CREATE INDEX IF NOT EXISTS idx_processed_scenes_source ON processed_scenes(source, processed_at);
CREATE INDEX IF NOT EXISTS idx_settings_section ON settings(section);
CREATE INDEX IF NOT EXISTS idx_one_time_searches_date ON one_time_searches(created_at);
CREATE INDEX IF NOT EXISTS idx_one_time_searches_status ON one_time_searches(status);
-- Triggers to update timestamps
CREATE TRIGGER IF NOT EXISTS update_settings_timestamp 
    AFTER UPDATE ON settings
BEGIN
    UPDATE settings SET updated_at = CURRENT_TIMESTAMP WHERE id = NEW.id;
END;
CREATE TRIGGER IF NOT EXISTS update_filter_rules_timestamp 
    AFTER UPDATE ON filter_rules
BEGIN
    UPDATE filter_rules SET updated_at = CURRENT_TIMESTAMP WHERE id = NEW.id;
END;
-- Add to existing schema.sql
CREATE TABLE IF NOT EXISTS rule_sync_settings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sync_enabled BOOLEAN DEFAULT 0,
    sync_direction TEXT CHECK(sync_direction IN ('add_to_clean', 'clean_to_add', 'bidirectional')) DEFAULT 'add_to_clean',
    field_mappings TEXT, -- JSON mapping between StashDB and Local Stash fields
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Insert default field mappings
INSERT OR IGNORE INTO rule_sync_settings (sync_enabled, sync_direction, field_mappings) VALUES (
    0, 
    'add_to_clean',
    '{
        "performers.performer.name": "performers.name",
        "performers.performer.ethnicity": "performers.ethnicity", 
        "performers.performer.gender": "performers.gender",
        "performers.performer.measurements.cup_size": "performers.cup_size",
        "performers.performer.measurements.waist": "performers.waist",
        "performers.performer.measurements.hip": "performers.hip",
        "studio.name": "studio.name",
        "title": "title",
        "date": "date",
        "tags": "tags"
    }'
);
