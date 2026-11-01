import sqlite3
import os
import json
from typing import List, Dict, Any, Optional

def get_db_path() -> str:
    return os.environ.get("RELAYSTATE_DB", "relaystate.db")

def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(get_db_path())
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_connection()
    cursor = conn.cursor()
    
    # 1. Workspaces & metadata
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS workspaces (
        workspace_id TEXT PRIMARY KEY,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        version TEXT DEFAULT 'v0.1',
        leaver_signed_at TIMESTAMP,
        leaver_signoff_hash TEXT,
        lead_signed_at TIMESTAMP,
        lead_signoff_hash TEXT,
        successor_acknowledged_at TIMESTAMP
    )
    """)

    # 2. Ingested artifacts (redacted before insertion)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS ingested_artifacts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        workspace_id TEXT,
        artifact_type TEXT,
        source_id TEXT,
        source_title TEXT,
        source_channel TEXT,
        author TEXT,
        timestamp TEXT,
        content_original_hash TEXT,
        content_redacted TEXT,
        redactions_applied TEXT,
        is_excluded INTEGER DEFAULT 0,
        exclusion_reason TEXT,
        FOREIGN KEY(workspace_id) REFERENCES workspaces(workspace_id)
    )
    """)

    # 3. Extracted claims
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS claims (
        id TEXT PRIMARY KEY,
        workspace_id TEXT,
        category TEXT,
        title TEXT,
        summary TEXT,
        verbatim_quote TEXT,
        status TEXT,
        status_reason TEXT,
        source_type TEXT,
        source_id TEXT,
        source_title TEXT,
        superseded_by_id TEXT,
        approved INTEGER DEFAULT 0,
        rejected INTEGER DEFAULT 0,
        manual_notes TEXT,
        FOREIGN KEY(workspace_id) REFERENCES workspaces(workspace_id)
    )
    """)

    # 4. Hash-chained audit log
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS audit_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        workspace_id TEXT,
        seq INTEGER,
        timestamp TEXT,
        action TEXT,
        actor TEXT,
        payload_diff TEXT,
        prev_hash TEXT,
        curr_hash TEXT,
        FOREIGN KEY(workspace_id) REFERENCES workspaces(workspace_id)
    )
    """)

    conn.commit()
    conn.close()

# Auto-initialize
init_db()

def reset_workspace_db(workspace_id: str):
    init_db()
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM audit_log WHERE workspace_id = ?", (workspace_id,))
    cursor.execute("DELETE FROM claims WHERE workspace_id = ?", (workspace_id,))
    cursor.execute("DELETE FROM ingested_artifacts WHERE workspace_id = ?", (workspace_id,))
    cursor.execute("DELETE FROM workspaces WHERE workspace_id = ?", (workspace_id,))
    conn.commit()
    conn.close()

def ensure_workspace(workspace_id: str):
    init_db()
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT workspace_id FROM workspaces WHERE workspace_id = ?", (workspace_id,))
    if not cursor.fetchone():
        cursor.execute("INSERT INTO workspaces (workspace_id, version) VALUES (?, 'v0.1')", (workspace_id,))
        conn.commit()
    conn.close()
