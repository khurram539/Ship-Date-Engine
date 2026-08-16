"""Database persistence layer for Ship Date Engine."""
import sqlite3
from pathlib import Path
from typing import Optional, List, Dict, Any


DB_PATH = Path(__file__).parent.parent / "ship_date.db"


def get_connection():
    """Get database connection with row factory."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Initialize database tables."""
    conn = get_connection()
    cursor = conn.cursor()

    # Uploads table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS uploads (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            file_name TEXT NOT NULL,
            file_path TEXT NOT NULL,
            shipping_id TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Lookups table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS lookups (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            shipping_id TEXT UNIQUE NOT NULL,
            result TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    conn.commit()
    conn.close()


def save_upload(file_name: str, file_path: str, metadata: Optional[Dict[str, Any]] = None):
    """Save uploaded file metadata to database."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            'INSERT INTO uploads (file_name, file_path, shipping_id) VALUES (?, ?, ?)',
            (file_name, file_path, metadata.get("shipping_id") if metadata else None)
        )
        conn.commit()


def save_lookup(shipping_id: str, result: Dict[str, Any]):
    """Cache shipping ID lookup result."""
    import json
    with get_connection() as conn:
        cursor = conn.cursor()
        try:
            cursor.execute(
                'INSERT INTO lookups (shipping_id, result) VALUES (?, ?)',
                (shipping_id, json.dumps(result))
            )
            conn.commit()
            return True
        except sqlite3.IntegrityError:
            return False


def get_cached_lookup(shipping_id: str) -> Optional[Dict[str, Any]]:
    """Retrieve cached lookup result."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT result FROM lookups WHERE shipping_id = ?', (shipping_id,))
        row = cursor.fetchone()
        if row:
            import json
            return json.loads(row["result"])
    return None


def delete_lookup(shipping_id: str):
    """Remove cached lookup for specific shipping ID."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('DELETE FROM lookups WHERE shipping_id = ?', (shipping_id,))
        conn.commit()


def cleanup_old_lookups(days: int = 30) -> int:
    """Remove lookup cache older than specified days."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(f'DELETE FROM lookups WHERE created_at < datetime("now", ? "days")', 
                       (str(-days),))
        conn.commit()
        return cursor.rowcount


def get_all_lookups(limit: int = 100) -> List[Dict[str, Any]]:
    """Get recent lookup history."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT shipping_id, result, created_at FROM lookups 
            ORDER BY created_at DESC LIMIT ?
        ''', (limit,))
        results = cursor.fetchall()
        import json
        return [{"shipping_id": r["shipping_id"], 
                 "result": json.loads(r["result"]),
                 "created_at": r["created_at"]} for r in results]
