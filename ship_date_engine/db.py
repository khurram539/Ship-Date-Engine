"""Database module for Ship Date Engine API."""
import sqlite3
import json
from typing import Any, Dict, Optional


def get_connection():
    conn = sqlite3.connect("ship_date.db")
    return conn


def init_db():
    conn = get_connection()
    c = conn.cursor()
    c.execute(
        """CREATE TABLE IF NOT EXISTS uploads (
        id INTEGER PRIMARY KEY,
        filename TEXT,
        filepath TEXT,
        metadata TEXT,
        created_at INTEGER DEFAULT (strftime('%s','now'))
        )"""
    )
    c.execute(
        """CREATE TABLE IF NOT EXISTS lookups (
        shipping_id TEXT PRIMARY KEY,
        result TEXT,
        created_at INTEGER DEFAULT (strftime('%s','now'))
        )"""
    )
    conn.commit()
    conn.close()


def save_upload(filename: str, filepath: str, metadata: Optional[Dict[str, Any]] = None) -> bool:
    try:
        conn = get_connection()
        c = conn.cursor()
        c.execute(
            "INSERT INTO uploads (filename, filepath, metadata) VALUES (?, ?, ?)",
            (filename, filepath, json.dumps(metadata) if metadata is not None else None),
        )
        conn.commit()
        conn.close()
        return True
    except Exception:
        return False


def get_cached_lookup(shipping_id):
    try:
        conn = get_connection()
        c = conn.cursor()
        if shipping_id:
            c.execute("SELECT result FROM lookups WHERE shipping_id=?", (shipping_id,))
            row = c.fetchone()
            conn.close()
            return json.loads(row[0]) if row and isinstance(row[0], str) else row[0]
        else:
            c.execute("SELECT shipping_id, result FROM lookups")
            results = {}
            for row in c.fetchall():
                results[row[0]] = row[1]
            conn.close()
            return results
    except Exception:
        return None


def save_lookup(shipping_id, result):
    try:
        conn = get_connection()
        c = conn.cursor()
        c.execute("INSERT OR REPLACE INTO lookups (shipping_id, result) VALUES (?, ?)", (shipping_id, json.dumps(result)))
        conn.commit()
        conn.close()
        return True
    except Exception:
        return False


def cleanup_old_lookups(days: int) -> int:
    try:
        import time

        cutoff = int(time.time() - (days * 24 * 3600))
        conn = get_connection()
        c = conn.cursor()
        c.execute("DELETE FROM lookups WHERE created_at < ?", (cutoff,))
        deleted = c.rowcount or 0
        conn.commit()
        conn.close()
        return deleted
    except Exception:
        return 0


init_db()
