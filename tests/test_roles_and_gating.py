import pytest
import os
from fastapi.testclient import TestClient
from app.main import app
from app.database import init_db, reset_workspace_db

client = TestClient(app)

@pytest.fixture(autouse=True)
def setup_db():
    os.environ["RELAYSTATE_DB"] = "test_roles.db"
    init_db()
    yield
    if os.path.exists("test_roles.db"):
        os.remove("test_roles.db")

def test_successor_403_and_signoff_gating():
    ws = "test_roles_ws"
    reset_workspace_db(ws)
    headers_leaver = {"X-Workspace": ws, "X-Role": "leaver"}
    headers_lead = {"X-Workspace": ws, "X-Role": "lead"}
    headers_successor = {"X-Workspace": ws, "X-Role": "successor"}
    
    # 1. Ingest & extract
    client.post("/api/ingest", headers=headers_leaver)
    client.post("/api/extract", headers=headers_leaver)
    
    # 2. SUCCESSOR 403 TEST: In v0.1 draft, successor MUST get 403 Forbidden!
    res = client.get("/api/claims", headers=headers_successor)
    assert res.status_code == 403
    assert "Access Denied" in res.json()["detail"]
    
    # 3. Lead cannot sign off v1.0 before leaver signs off v0.2
    lead_fail = client.post("/api/signoff/lead", headers=headers_lead, json={"notes": "premature approval"})
    assert lead_fail.status_code == 400
    
    # 4. Leaver performs sign-off -> promotes to v0.2
    leaver_ok = client.post("/api/signoff/leaver", headers=headers_leaver, json={"notes": "leaver verified"})
    assert leaver_ok.status_code == 200
    assert leaver_ok.json()["new_version"] == "v0.2"
    
    # 5. Successor STILL gets 403 in v0.2
    res2 = client.get("/api/claims", headers=headers_successor)
    assert res2.status_code == 403
    
    # 6. Lead approves v1.0
    lead_ok = client.post("/api/signoff/lead", headers=headers_lead, json={"notes": "lead approved"})
    assert lead_ok.status_code == 200
    assert lead_ok.json()["new_version"] == "v1.0"
    
    # 7. Successor view UNBLOCKED in v1.0!
    res3 = client.get("/api/claims", headers=headers_successor)
    assert res3.status_code == 200
    assert res3.json()["version"] == "v1.0"
    
    # 8. Successor acknowledges receipt
    ack_res = client.post("/api/successor/acknowledge", headers=headers_successor)
    assert ack_res.status_code == 200
    assert ack_res.json()["status"] == "acknowledged"
