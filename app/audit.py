import hashlib
import json
from datetime import datetime, timezone
from typing import Dict, Any, List
from app.database import get_connection

GENESIS_HASH = "0000000000000000000000000000000000000000000000000000000000000000"

def compute_block_hash(seq: int, timestamp: str, workspace_id: str, action: str, actor: str, payload_diff: str, prev_hash: str) -> str:
    content = f"{seq}|{timestamp}|{workspace_id}|{action}|{actor}|{payload_diff}|{prev_hash}"
    return hashlib.sha256(content.encode('utf-8')).hexdigest()

def record_audit_event(workspace_id: str, action: str, actor: str, payload_diff: Any) -> Dict[str, Any]:
    conn = get_connection()
    cursor = conn.cursor()
    
    # Get last block
    cursor.execute("SELECT seq, curr_hash FROM audit_log WHERE workspace_id = ? ORDER BY seq DESC LIMIT 1", (workspace_id,))
    last_block = cursor.fetchone()
    
    if last_block:
        seq = last_block["seq"] + 1
        prev_hash = last_block["curr_hash"]
    else:
        seq = 1
        prev_hash = GENESIS_HASH
        
    timestamp = datetime.now(timezone.utc).isoformat()
    payload_str = json.dumps(payload_diff, sort_keys=True)
    curr_hash = compute_block_hash(seq, timestamp, workspace_id, action, actor, payload_str, prev_hash)
    
    cursor.execute("""
    INSERT INTO audit_log (workspace_id, seq, timestamp, action, actor, payload_diff, prev_hash, curr_hash)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (workspace_id, seq, timestamp, action, actor, payload_str, prev_hash, curr_hash))
    
    conn.commit()
    conn.close()
    
    return {
        "seq": seq,
        "timestamp": timestamp,
        "action": action,
        "actor": actor,
        "prev_hash": prev_hash,
        "curr_hash": curr_hash
    }

def verify_audit_log(workspace_id: str) -> Dict[str, Any]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM audit_log WHERE workspace_id = ? ORDER BY seq ASC", (workspace_id,))
    blocks = cursor.fetchall()
    conn.close()
    
    if not blocks:
        return {"valid": True, "total_blocks": 0, "message": "No audit records found."}
        
    expected_prev = GENESIS_HASH
    for block in blocks:
        # Check chaining
        if block["prev_hash"] != expected_prev:
            return {
                "valid": False,
                "broken_at_seq": block["seq"],
                "reason": f"Hash chain link broken. Expected prev_hash {expected_prev[:12]}... but found {block['prev_hash'][:12]}...",
                "total_blocks": len(blocks)
            }
        
        # Check integrity
        recalculated = compute_block_hash(
            block["seq"],
            block["timestamp"],
            block["workspace_id"],
            block["action"],
            block["actor"],
            block["payload_diff"],
            block["prev_hash"]
        )
        if recalculated != block["curr_hash"]:
            return {
                "valid": False,
                "broken_at_seq": block["seq"],
                "reason": f"Data tampering detected in payload of block #{block['seq']}. Hash mismatch.",
                "expected_hash": recalculated,
                "found_hash": block["curr_hash"],
                "total_blocks": len(blocks)
            }
        expected_prev = block["curr_hash"]
        
    return {
        "valid": True,
        "total_blocks": len(blocks),
        "latest_hash": blocks[-1]["curr_hash"]
    }

# Backup dictionary for restoring simulated tampering
_TAMPER_BACKUPS: Dict[str, Dict[str, Any]] = {}

def simulate_tamper(workspace_id: str) -> Dict[str, Any]:
    conn = get_connection()
    cursor = conn.cursor()
    # Choose block 2 if exists, else block 1
    cursor.execute("SELECT * FROM audit_log WHERE workspace_id = ? ORDER BY seq ASC", (workspace_id,))
    blocks = cursor.fetchall()
    
    if not blocks:
        conn.close()
        return {"status": "error", "message": "Cannot tamper: audit log is empty."}
        
    target_block = blocks[1] if len(blocks) > 1 else blocks[0]
    target_seq = target_block["seq"]
    
    # Backup original
    _TAMPER_BACKUPS[workspace_id] = {
        "seq": target_seq,
        "original_payload": target_block["payload_diff"]
    }
    
    # Tamper payload without updating curr_hash
    malicious_payload = json.dumps({"unauthorized_tampering": "Injected false sign-off signature by malicious agent"}, sort_keys=True)
    cursor.execute("UPDATE audit_log SET payload_diff = ? WHERE workspace_id = ? AND seq = ?", (malicious_payload, workspace_id, target_seq))
    conn.commit()
    conn.close()
    
    return {
        "status": "tampered",
        "seq": target_seq,
        "message": f"Block #{target_seq} payload modified in database without recalculating cryptographic hash. Chain verification will now detect tampering."
    }

def restore_tamper(workspace_id: str) -> Dict[str, Any]:
    backup = _TAMPER_BACKUPS.get(workspace_id)
    if not backup:
        return {"status": "unchanged", "message": "No active tamper backup to restore."}
        
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE audit_log SET payload_diff = ? WHERE workspace_id = ? AND seq = ?", (backup["original_payload"], workspace_id, backup["seq"]))
    conn.commit()
    conn.close()
    
    del _TAMPER_BACKUPS[workspace_id]
    return {
        "status": "restored",
        "seq": backup["seq"],
        "message": f"Block #{backup['seq']} payload restored to authentic original state. Hash chain valid again."
    }
