import os
import sqlite3
from pathlib import Path
import datetime

# Define workspace storage paths
BASE_DIR = Path(__file__).parent.resolve()
STORAGE_DIR = BASE_DIR / "storage"
RAW_DIR = STORAGE_DIR / "raw"
AUDIO_DIR = STORAGE_DIR / "audio"
CLIPS_DIR = STORAGE_DIR / "clips"
DRAFTS_DIR = STORAGE_DIR / "drafts"
DB_PATH = STORAGE_DIR / "video_summary.db"

def init_storage():
    """Initializes all storage directories and SQLite database."""
    # Create directories
    for directory in [RAW_DIR, AUDIO_DIR, CLIPS_DIR, DRAFTS_DIR]:
        directory.mkdir(parents=True, exist_ok=True)
    
    # Initialize DB
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Create videos table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS videos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            file_path TEXT UNIQUE,
            title TEXT,
            duration REAL,
            status TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # Create transcripts table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS transcripts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            video_id INTEGER,
            start_time REAL,
            end_time REAL,
            text TEXT,
            FOREIGN KEY (video_id) REFERENCES videos(id) ON DELETE CASCADE
        )
    """)
    
    # Create clips_meta table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS clips_meta (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            video_id INTEGER,
            start_time REAL,
            end_time REAL,
            description TEXT,
            clip_path TEXT,
            FOREIGN KEY (video_id) REFERENCES videos(id) ON DELETE CASCADE
        )
    """)
    
    conn.commit()
    conn.close()

def get_db_connection():
    """Returns a SQLite connection object."""
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn

# Helper functions to manage database records
def add_video(file_path, title=None, duration=None, status="pending"):
    """Inserts a new video or returns the existing one."""
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "INSERT INTO videos (file_path, title, duration, status) VALUES (?, ?, ?, ?)",
            (str(file_path), title or Path(file_path).name, duration, status)
        )
        conn.commit()
        video_id = cursor.lastrowid
    except sqlite3.IntegrityError:
        cursor.execute("SELECT id FROM videos WHERE file_path = ?", (str(file_path),))
        video_id = cursor.fetchone()[0]
    finally:
        conn.close()
    return video_id

def update_video_status(video_id, status, duration=None):
    """Updates status and optionally duration of a video."""
    conn = get_db_connection()
    cursor = conn.cursor()
    if duration is not None:
        cursor.execute("UPDATE videos SET status = ?, duration = ? WHERE id = ?", (status, duration, video_id))
    else:
        cursor.execute("UPDATE videos SET status = ? WHERE id = ?", (status, video_id))
    conn.commit()
    conn.close()

def add_transcript_segments(video_id, segments):
    """Inserts multiple transcript segments. segments is list of dict with keys (start, end, text)."""
    conn = get_db_connection()
    cursor = conn.cursor()
    # Delete old transcripts first
    cursor.execute("DELETE FROM transcripts WHERE video_id = ?", (video_id,))
    
    for seg in segments:
        cursor.execute(
            "INSERT INTO transcripts (video_id, start_time, end_time, text) VALUES (?, ?, ?, ?)",
            (video_id, seg['start'], seg['end'], seg['text'])
        )
    conn.commit()
    conn.close()

def get_transcripts(video_id):
    """Gets transcripts for a video."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT start_time, end_time, text FROM transcripts WHERE video_id = ? ORDER BY start_time", (video_id,))
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]

def add_clips(video_id, clips):
    """Inserts multiple clips metadata. clips is list of dict with keys (start_time, end_time, description, clip_path)."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM clips_meta WHERE video_id = ?", (video_id,))
    
    for clip in clips:
        cursor.execute(
            "INSERT INTO clips_meta (video_id, start_time, end_time, description, clip_path) VALUES (?, ?, ?, ?, ?)",
            (video_id, clip['start_time'], clip['end_time'], clip['description'], clip.get('clip_path', ''))
        )
    conn.commit()
    conn.close()

def get_clips(video_id):
    """Gets clips metadata for a video."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT start_time, end_time, description, clip_path FROM clips_meta WHERE video_id = ?", (video_id,))
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]

# Initialize storage on load
init_storage()
