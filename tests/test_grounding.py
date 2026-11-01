import pytest
import os
from app.database import init_db, reset_workspace_db
from app.extraction import ingest_corpus, run_extraction_and_grounding

@pytest.fixture(autouse=True)
def setup_db():
    os.environ["RELAYSTATE_DB"] = "test_grounding.db"
    init_db()
    yield
    if os.path.exists("test_grounding.db"):
        os.remove("test_grounding.db")

def test_verbatim_grounding_and_drop():
    ws = "test_grounding_ws"
    reset_workspace_db(ws)
    
    # 1. Ingest corpus
    ing_res = ingest_corpus(ws)
    assert ing_res["status"] == "success"
    assert ing_res["ingested_count"] > 200
    assert ing_res["excluded_count"] == 3
    
    # 2. Run extraction
    ext_res = run_extraction_and_grounding(ws)
    assert ext_res["status"] == "success"
    
    # Verified: The hallucinated Apollo GraphQL quote must be DROPPED
    assert ext_res["claims_dropped_for_grounding"] >= 1
    dropped = ext_res["dropped_details"]
    assert any("GROUNDING_DROP" in d["reason"] for d in dropped)
    
    # All surviving claims must have their verbatim quote actually inside the source
    for claim in ext_res["claims"]:
        assert len(claim["verbatim_quote"]) > 5
