import sqlite3
import os
import json
from typing import List, Dict, Any, Optional

DB_PATH = os.environ.get("RELAYSTATE_DB", "relaystate.db")

def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
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
        artifact_type TEXT, -- git_commit, git_pr, chat_message, jira_issue
        source_id TEXT,
        source_title TEXT,
        source_channel TEXT, -- repo name or chat channel
        author TEXT,
        timestamp TEXT,
        content_original_hash TEXT,
        content_redacted TEXT,
        redactions_applied TEXT, -- JSON array of detected secrets/PII
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
        category TEXT, -- Decision, Blocker, Risk, Contact, Dependency
        title TEXT,
        summary TEXT,
        verbatim_quote TEXT,
        status TEXT, -- EVIDENCED, CHAT_ONLY, SUPERSEDED_BY_CODE, UNCERTAIN, MISSING
        status_reason TEXT,
        source_type TEXT,
        source_id TEXT,
        source_title TEXT,
        superseded_by_id TEXT, -- e.g. commit SHA that superseded a chat decision
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

def reset_workspace_db(workspace_id: str):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM audit_log WHERE workspace_id = ?", (workspace_id,))
    cursor.execute("DELETE FROM claims WHERE workspace_id = ?", (workspace_id,))
    cursor.execute("DELETE FROM ingested_artifacts WHERE workspace_id = ?", (workspace_id,))
    cursor.execute("DELETE FROM workspaces WHERE workspace_id = ?", (workspace_id,))
    conn.commit()
    conn.close()

def ensure_workspace(workspace_id: str):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT workspace_id FROM workspaces WHERE workspace_id = ?", (workspace_id,))
    if not cursor.fetchone():
        cursor.execute("INSERT INTO workspaces (workspace_id, version) VALUES (?, 'v0.1')", (workspace_id,))
        conn.commit()
    conn.close()
