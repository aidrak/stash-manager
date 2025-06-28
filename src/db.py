import sqlite3
import logging

def get_db_connection(db_path):
    """Creates a database connection."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn

def initialize_db(db_path):
    """Initializes the database with the required tables."""
    conn = get_db_connection(db_path)
    cursor = conn.cursor()
    
    # Create tables if they don't exist
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS scenes (
            id TEXT PRIMARY KEY,
            title TEXT,
            details TEXT,
            url TEXT,
            date TEXT,
            studio TEXT,
            image TEXT,
            added_to_whisparr BOOLEAN DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS performers (
            id TEXT PRIMARY KEY,
            name TEXT,
            url TEXT,
            twitter TEXT,
            instagram TEXT,
            birthdate TEXT,
            ethnicity TEXT,
            country TEXT,
            eye_color TEXT,
            height TEXT,
            measurements TEXT,
            fake_tits TEXT,
            career_length TEXT,
            tattoos TEXT,
            piercings TEXT,
            aliases TEXT,
            tags TEXT,
            favorite BOOLEAN,
            image TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    conn.commit()
    conn.close()
    logging.info("Database initialized successfully.")
