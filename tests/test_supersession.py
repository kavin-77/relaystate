import pytest
import os
from app.database import init_db, reset_workspace_db
from app.extraction import ingest_corpus, run_extraction_and_grounding

@pytest.fixture(autouse=True)
def setup_db():
    os.environ["RELAYSTATE_DB"] = "test_supersession.db"
    init_db()
    yield
    if os.path.exists("test_supersession.db"):
        os.remove("test_supersession.db")

def test_temporal_supersession_and_uncertainty():
    ws = "test_supersession_ws"
    reset_workspace_db(ws)
    ingest_corpus(ws)
    ext_res = run_extraction_and_grounding(ws)
    claims = ext_res["claims"]
    
    # 1. Check Redis superseded by Memcached
    redis_claim = next((c for c in claims if "Redis" in c["title"]), None)
    assert redis_claim is not None
    assert redis_claim["status"] == "SUPERSEDED_BY_CODE"
    assert redis_claim["superseded_by_id"] == "commit-7a89b1"
    
    # 2. Check Unanswered SMS question -> UNCERTAIN
    sms_claim = next((c for c in claims if "Twilio SMS" in c["title"]), None)
    assert sms_claim is not None
    assert sms_claim["status"] == "UNCERTAIN"
    
    # 3. Check Unassigned ticket -> MISSING
    missing_claim = next((c for c in claims if "Invoice Reconciliation" in c["title"]), None)
    assert missing_claim is not None
    assert missing_claim["status"] == "MISSING"
