"""Admin-managed knowledge for Z1. SQLite requires persistent storage for durability."""
import os
import sqlite3
from pathlib import Path

DB_PATH = os.getenv("Z1_DB_PATH", "/tmp/z1_knowledge.sqlite3")

def connection():
    Path(DB_PATH).parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(DB_PATH, timeout=10)
    db.execute("CREATE TABLE IF NOT EXISTS knowledge (id INTEGER PRIMARY KEY CHECK(id=1), content TEXT NOT NULL)")
    return db

def read_knowledge():
    with connection() as db:
        row = db.execute("SELECT content FROM knowledge WHERE id=1").fetchone()
        return row[0] if row else ""

def save_knowledge(content):
    with connection() as db:
        db.execute("INSERT INTO knowledge(id, content) VALUES(1, ?) ON CONFLICT(id) DO UPDATE SET content=excluded.content", (content,))
