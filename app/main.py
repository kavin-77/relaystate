import os
import json
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any

from fastapi import FastAPI, Header, HTTPException, Depends
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

from app.database import init_db, get_connection, reset_workspace_db, ensure_workspace
from app.models import ReviewClaimRequest, ManualRedactRequest, SignoffRequest
from app.extraction import ingest_corpus, run_extraction_and_grounding, calculate_bus_factor
from app.audit import record_audit_event, verify_audit_log, simulate_tamper, restore_tamper

app = FastAPI(title="RelayState API", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize database schema on startup
@app.on_event("startup")
def on_startup():
    init_db()

# Dependency to extract and guarantee workspace
def get_workspace(x_workspace: Optional[str] = Header("default-workspace")) -> str:
    ws = x_workspace.strip() if x_workspace and x_workspace.strip() else "default-workspace"
    ensure_workspace(ws)
    return ws

@app.get("/healthz")
def healthz():
    return {"status": "ok", "app": "RelayState", "version": "2.0.0"}

# Workspace management
@app.post("/api/workspace/reset")
def reset_workspace(workspace_id: str = Depends(get_workspace)):
    reset_workspace_db(workspace_id)
    ensure_workspace(workspace_id)
    record_audit_event(workspace_id, "WORKSPACE_RESET", "user", {"status": "reset_to_clean_state"})
    return {"status": "reset_complete", "workspace_id": workspace_id}

@app.get("/api/workspace/state")
def get_workspace_state(workspace_id: str = Depends(get_workspace)):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM workspaces WHERE workspace_id = ?", (workspace_id,))
    ws = dict(cursor.fetchone())
    
    cursor.execute("SELECT COUNT(*) as count FROM ingested_artifacts WHERE workspace_id = ?", (workspace_id,))
    artifacts_count = cursor.fetchone()["count"]
    
    cursor.execute("SELECT COUNT(*) as count FROM claims WHERE workspace_id = ?", (workspace_id,))
    claims_count = cursor.fetchone()["count"]
    
    conn.close()
    return {
        "workspace_id": workspace_id,
        "version": ws.get("version", "v0.1"),
        "leaver_signed_at": ws.get("leaver_signed_at"),
        "lead_signed_at": ws.get("lead_signed_at"),
        "successor_acknowledged_at": ws.get("successor_acknowledged_at"),
        "artifacts_count": artifacts_count,
        "claims_count": claims_count
    }

# 1. CONNECT & INGESTION
@app.post("/api/ingest")
def trigger_ingestion(workspace_id: str = Depends(get_workspace), x_role: Optional[str] = Header("leaver")):
    result = ingest_corpus(workspace_id)
    record_audit_event(
        workspace_id, "INGEST_CORPUS", f"role:{x_role}",
        {"ingested_count": result.get("ingested_count"), "excluded_count": result.get("excluded_count")}
    )
    return result

@app.get("/api/sources/summary")
def get_sources_summary(workspace_id: str = Depends(get_workspace)):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
    SELECT artifact_type, COUNT(*) as count 
    FROM ingested_artifacts 
    WHERE workspace_id = ? AND is_excluded = 0 
    GROUP BY artifact_type
    """, (workspace_id,))
    active = {r["artifact_type"]: r["count"] for r in cursor.fetchall()}
    
    cursor.execute("""
    SELECT source_channel, source_title, exclusion_reason 
    FROM ingested_artifacts 
    WHERE workspace_id = ? AND is_excluded = 1
    """, (workspace_id,))
    excluded = [dict(r) for r in cursor.fetchall()]
    conn.close()
    
    return {
        "active_sources": active,
        "excluded_sources": excluded
    }

@app.get("/api/sources/{source_id}")
def get_source_detail(source_id: str, workspace_id: str = Depends(get_workspace)):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
    SELECT source_id, source_title, source_channel, artifact_type, author, timestamp, content_redacted, is_excluded, exclusion_reason
    FROM ingested_artifacts 
    WHERE workspace_id = ? AND source_id = ?
    """, (workspace_id, source_id))
    row = cursor.fetchone()
    conn.close()
    if not row:
        raise HTTPException(status_code=404, detail=f"Source artifact '{source_id}' not found.")
    return dict(row)

# 2. RECONSTRUCT & EXTRACT
@app.post("/api/extract")
def trigger_extraction(workspace_id: str = Depends(get_workspace), x_role: Optional[str] = Header("leaver")):
    result = run_extraction_and_grounding(workspace_id)
    record_audit_event(
        workspace_id, "EXTRACT_CLAIMS", f"role:{x_role}",
        {
            "claims_extracted": result.get("claims_extracted"),
            "grounding_drops": result.get("claims_dropped_for_grounding"),
            "extractor_used": result.get("extractor_used")
        }
    )
    return result

# 3. VERIFY & CLAIMS LIST (WITH 403 ROLE ENFORCEMENT)
@app.get("/api/claims")
def list_claims(workspace_id: str = Depends(get_workspace), x_role: Optional[str] = Header("leaver")):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT version FROM workspaces WHERE workspace_id = ?", (workspace_id,))
    ws = cursor.fetchone()
    current_version = ws["version"] if ws else "v0.1"
    
    # ROLE GATING: Successor gets 403 until v1.0
    if x_role == "successor":
        if current_version != "v1.0":
            conn.close()
            raise HTTPException(
                status_code=403,
                detail=f"Access Denied (403): Handover package is currently in {current_version} draft mode. Successors cannot access handover information until Engineering Lead formally approves v1.0."
            )
        # Successors see only approved claims
        cursor.execute("SELECT * FROM claims WHERE workspace_id = ? AND approved = 1", (workspace_id,))
    else:
        cursor.execute("SELECT * FROM claims WHERE workspace_id = ?", (workspace_id,))
        
    claims = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return {
        "version": current_version,
        "role": x_role,
        "claims": claims
    }

# 4. REVIEW & EDITING
@app.post("/api/claims/{claim_id}/review")
def review_claim(
    claim_id: str,
    req: ReviewClaimRequest,
    workspace_id: str = Depends(get_workspace),
    x_role: Optional[str] = Header("leaver")
):
    if x_role not in ["leaver", "lead"]:
        raise HTTPException(status_code=403, detail="Only 'leaver' or 'lead' roles can modify or approve claims.")
        
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM claims WHERE workspace_id = ? AND id = ?", (workspace_id, claim_id))
    claim = cursor.fetchone()
    if not claim:
        conn.close()
        raise HTTPException(status_code=404, detail="Claim not found.")
        
    updates = []
    params = []
    diff_payload = {}
    
    if req.approved is not None:
        updates.append("approved = ?")
        params.append(1 if req.approved else 0)
        diff_payload["approved"] = req.approved
        if req.approved:
            updates.append("rejected = 0")
            
    if req.rejected is not None:
        updates.append("rejected = ?")
        params.append(1 if req.rejected else 0)
        diff_payload["rejected"] = req.rejected
        if req.rejected:
            updates.append("approved = 0")
            
    if req.summary is not None:
        updates.append("summary = ?")
        params.append(req.summary)
        diff_payload["old_summary"] = claim["summary"]
        diff_payload["new_summary"] = req.summary
        
    if req.manual_notes is not None:
        updates.append("manual_notes = ?")
        params.append(req.manual_notes)
        diff_payload["manual_notes"] = req.manual_notes
        
    if updates:
        params.extend([workspace_id, claim_id])
        query = f"UPDATE claims SET {', '.join(updates)} WHERE workspace_id = ? AND id = ?"
        cursor.execute(query, params)
        conn.commit()
        
    conn.close()
    
    record_audit_event(workspace_id, f"CLAIM_REVIEW_{claim_id[:8]}", f"role:{x_role}", diff_payload)
    return {"status": "updated", "claim_id": claim_id, "changes": diff_payload}

@app.post("/api/claims/manual_redact")
def manual_redact_term(
    req: ManualRedactRequest,
    workspace_id: str = Depends(get_workspace),
    x_role: Optional[str] = Header("leaver")
):
    if x_role != "leaver":
        raise HTTPException(status_code=403, detail="Only the departing leaver can perform custom manual redactions.")
        
    term = req.target_string.strip()
    if len(term) < 3:
        raise HTTPException(status_code=400, detail="Target redaction string must be at least 3 characters.")
        
    replacement = req.replacement or "[MANUALLY_REDACTED]"
    
    conn = get_connection()
    cursor = conn.cursor()
    # Redact in claims
    cursor.execute("""
    UPDATE claims 
    SET summary = REPLACE(summary, ?, ?),
        manual_notes = REPLACE(manual_notes, ?, ?)
    WHERE workspace_id = ?
    """, (term, replacement, term, replacement, workspace_id))
    
    # Redact in source artifacts
    cursor.execute("""
    UPDATE ingested_artifacts
    SET content_redacted = REPLACE(content_redacted, ?, ?)
    WHERE workspace_id = ?
    """, (term, replacement, workspace_id))
    
    conn.commit()
    conn.close()
    
    record_audit_event(
        workspace_id, "MANUAL_REDACTION", f"role:{x_role}",
        {"masked_term_length": len(term), "replacement": replacement}
    )
    return {"status": "redacted", "target": term[:3] + "***", "replacement": replacement}

# 5. VERSION PROGRESSION & SIGN-OFFS
@app.post("/api/signoff/leaver")
def leaver_signoff(
    req: SignoffRequest,
    workspace_id: str = Depends(get_workspace),
    x_role: Optional[str] = Header("leaver")
):
    if x_role != "leaver":
        raise HTTPException(status_code=403, detail="Only the departing leaver can perform the leaver sign-off.")
        
    now = datetime.now(timezone.utc).isoformat()
    # Record audit event
    audit_res = record_audit_event(
        workspace_id, "LEAVER_SIGNOFF", "leaver (Dave)",
        {"version_from": "v0.1", "version_to": "v0.2", "notes": req.notes}
    )
    
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
    UPDATE workspaces
    SET version = 'v0.2', leaver_signed_at = ?, leaver_signoff_hash = ?
    WHERE workspace_id = ?
    """, (now, audit_res["curr_hash"], workspace_id))
    conn.commit()
    conn.close()
    
    return {
        "status": "leaver_signed",
        "new_version": "v0.2",
        "signed_at": now,
        "audit_hash": audit_res["curr_hash"]
    }

@app.post("/api/signoff/lead")
def lead_signoff(
    req: SignoffRequest,
    workspace_id: str = Depends(get_workspace),
    x_role: Optional[str] = Header("lead")
):
    if x_role != "lead":
        raise HTTPException(status_code=403, detail="Only the Engineering Lead can approve v1.0 publication.")
        
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT version FROM workspaces WHERE workspace_id = ?", (workspace_id,))
    ws = cursor.fetchone()
    if not ws or ws["version"] != "v0.2":
        conn.close()
        raise HTTPException(status_code=400, detail="Cannot promote to v1.0. Leaver must review and sign off v0.2 first.")
        
    now = datetime.now(timezone.utc).isoformat()
    audit_res = record_audit_event(
        workspace_id, "LEAD_APPROVAL", "lead (Marcus)",
        {"version_from": "v0.2", "version_to": "v1.0", "notes": req.notes}
    )
    
    cursor.execute("""
    UPDATE workspaces
    SET version = 'v1.0', lead_signed_at = ?, lead_signoff_hash = ?
    WHERE workspace_id = ?
    """, (now, audit_res["curr_hash"], workspace_id))
    conn.commit()
    conn.close()
    
    return {
        "status": "lead_approved",
        "new_version": "v1.0",
        "signed_at": now,
        "audit_hash": audit_res["curr_hash"]
    }

@app.post("/api/successor/acknowledge")
def successor_acknowledge(
    workspace_id: str = Depends(get_workspace),
    x_role: Optional[str] = Header("successor")
):
    if x_role != "successor":
        raise HTTPException(status_code=403, detail="Only the successor role can acknowledge receipt.")
        
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT version FROM workspaces WHERE workspace_id = ?", (workspace_id,))
    ws = cursor.fetchone()
    if not ws or ws["version"] != "v1.0":
        conn.close()
        raise HTTPException(status_code=403, detail="Cannot acknowledge: handover is not yet published in v1.0.")
        
    now = datetime.now(timezone.utc).isoformat()
    audit_res = record_audit_event(
        workspace_id, "SUCCESSOR_ACKNOWLEDGE", "successor (Amina)",
        {"acknowledged_version": "v1.0", "timestamp": now}
    )
    
    cursor.execute("UPDATE workspaces SET successor_acknowledged_at = ? WHERE workspace_id = ?", (now, workspace_id))
    conn.commit()
    conn.close()
    
    return {
        "status": "acknowledged",
        "acknowledged_at": now,
        "audit_hash": audit_res["curr_hash"]
    }

# 6. HASH-CHAINED AUDIT TRAIL ENDPOINTS
@app.get("/api/audit/log")
def get_audit_trail(workspace_id: str = Depends(get_workspace)):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM audit_log WHERE workspace_id = ? ORDER BY seq ASC", (workspace_id,))
    rows = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return {"total_records": len(rows), "records": rows}

@app.get("/api/audit/verify")
def verify_audit_chain(workspace_id: str = Depends(get_workspace)):
    return verify_audit_log(workspace_id)

@app.post("/api/audit/simulate_tamper")
def simulate_audit_tamper(workspace_id: str = Depends(get_workspace)):
    return simulate_tamper(workspace_id)

@app.post("/api/audit/restore")
def restore_audit_tamper(workspace_id: str = Depends(get_workspace)):
    return restore_tamper(workspace_id)

# 7. BUS FACTOR ANALYSIS
@app.get("/api/bus_factor")
def get_bus_factor_data(workspace_id: str = Depends(get_workspace)):
    return calculate_bus_factor(workspace_id)

# 8. STATIC FRONTEND SERVING
STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")
if not os.path.exists(STATIC_DIR):
    os.makedirs(STATIC_DIR, exist_ok=True)

@app.get("/")
def serve_index():
    index_file = os.path.join(STATIC_DIR, "index.html")
    if os.path.exists(index_file):
        return FileResponse(index_file)
    return HTMLResponse("<h1>RelayState API is running. UI compiling...</h1>")

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("app.main:app", host="0.0.0.0", port=port, reload=False)
