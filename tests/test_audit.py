import pytest
import os
from app.database import init_db, reset_workspace_db
from app.audit import record_audit_event, verify_audit_log, simulate_tamper, restore_tamper

@pytest.fixture(autouse=True)
def setup_db():
    os.environ["RELAYSTATE_DB"] = "test_audit_db.db"
    init_db()
    yield
    if os.path.exists("test_audit_db.db"):
        os.remove("test_audit_db.db")

def test_hash_chain_integrity_tamper_and_restore():
    ws = "test_audit_ws"
    reset_workspace_db(ws)
    
    # 1. Record series of events
    record_audit_event(ws, "INGEST_CORPUS", "system", {"count": 212})
    record_audit_event(ws, "EXTRACT_CLAIMS", "system", {"claims": 9})
    record_audit_event(ws, "LEAVER_SIGNOFF", "leaver (Dave)", {"version": "v0.2"})
    record_audit_event(ws, "LEAD_APPROVAL", "lead (Marcus)", {"version": "v1.0"})
    
    # 2. Verify audit chain is cryptographically sound
    v1 = verify_audit_log(ws)
    assert v1["valid"] is True
    assert v1["total_blocks"] == 4
    
    # 3. Simulate unauthorized database modification (tamper)
    t_res = simulate_tamper(ws)
    assert t_res["status"] == "tampered"
    
    # 4. Verification must DETECT tampering immediately
    v2 = verify_audit_log(ws)
    assert v2["valid"] is False
    assert v2["broken_at_seq"] == t_res["seq"]
    assert "tampering detected" in v2["reason"].lower()
    
    # 5. Restore authentic state
    r_res = restore_tamper(ws)
    assert r_res["status"] == "restored"
    
    # 6. Verification returns to valid state
    v3 = verify_audit_log(ws)
    assert v3["valid"] is True
    assert v3["total_blocks"] == 4
