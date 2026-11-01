#!/usr/bin/env python3
"""
scripts/smoke_test.py
End-to-End HTTP Smoke Test for Deployed RelayState Handover Platform.

Tests the live web service over HTTP using requests:
1. GET /healthz returns 200.
2. Ingest demo project: checks counts (56 commits, 25 PRs, 121 messages, 13 tickets)
   and verifies exclusions for HR channel, private DM, and payroll repo with justifications.
3. Get claims: verifies zero planted secrets (AKIAIOSFODNN7EXAMPLE, sk_test, email, phone)
   appear anywhere in API responses.
4. Semantic checks: Redis is SUPERSEDED_BY_CODE, SMS is UNCERTAIN, unassigned is MISSING,
   and billing module is flagged as a critical bus-factor risk.
5. Successor role gating: requests handover in draft mode and asserts HTTP 403 Forbidden.
6. Review & Sign-off gating: rejects lead approval before leaver, approves claims,
   signs off Dave (v0.2), then Marcus (v1.0).
7. Successor view in v1.0: returns HTTP 200 with approved claims only; acknowledges receipt.
8. Cryptographic audit trail: verify valid -> simulate tamper (verify fails) -> restore (verify valid).

Usage:
    python scripts/smoke_test.py [BASE_URL]
Default:
    https://relaystate-innovix.onrender.com
"""

import sys
import time
import uuid
import json

try:
    import requests
except ImportError:
    print("FATAL: 'requests' library not found. Install it with: pip install requests")
    sys.exit(1)


def run_smoke_test(base_url: str):
    base_url = base_url.rstrip("/")
    ws_id = f"smoke-{int(time.time())}-{uuid.uuid4().hex[:6]}"
    
    print(f"============================================================")
    print(f"RelayState Live Smoke Test Suite")
    print(f"Target URL:    {base_url}")
    print(f"Test Workspace:{ws_id}")
    print(f"Timestamp:     {time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime())}")
    print(f"============================================================\n")

    passed_steps = 0
    total_steps = 8

    # Helper headers
    def get_headers(role: str = "leaver", ws: str = ws_id):
        return {
            "Content-Type": "application/json",
            "X-Workspace": ws,
            "X-Role": role
        }

    # -------------------------------------------------------------
    # 1. GET /healthz returns 200
    # -------------------------------------------------------------
    step_num = 1
    try:
        url = f"{base_url}/healthz"
        res = requests.get(url, timeout=15)
        if res.status_code == 200 and res.json().get("status") == "ok":
            print(f"[PASS] Step 1: GET /healthz returned 200 OK (status: ok, app: {res.json().get('app')})")
            passed_steps += 1
        else:
            print(f"[FAIL] Step 1: GET /healthz returned status {res.status_code}: {res.text}")
            sys.exit(1)
    except Exception as e:
        print(f"[FAIL] Step 1: GET /healthz failed with exception: {e}")
        sys.exit(1)

    # -------------------------------------------------------------
    # 2. Ingest demo project & check counts + exclusions
    # -------------------------------------------------------------
    step_num = 2
    try:
        # Trigger ingestion
        ingest_res = requests.post(f"{base_url}/api/ingest", headers=get_headers("leaver"), json={}, timeout=20)
        if ingest_res.status_code != 200:
            print(f"[FAIL] Step 2: POST /api/ingest returned status {ingest_res.status_code}: {ingest_res.text}")
            sys.exit(1)

        # Query source summary
        summary_res = requests.get(f"{base_url}/api/sources/summary", headers=get_headers("leaver"), timeout=15)
        if summary_res.status_code != 200:
            print(f"[FAIL] Step 2: GET /api/sources/summary returned status {summary_res.status_code}")
            sys.exit(1)

        summary = summary_res.json()
        active = summary.get("active_sources", {})
        excluded = summary.get("excluded_sources", [])

        # Calculate counts
        # Excluded items: 1 commit (hr-payroll-tools), 2 chats (#hr-confidential, dm-dave-sarah)
        excl_commits = sum(1 for e in excluded if "payroll" in e.get("source_channel", "").lower())
        excl_chats = sum(1 for e in excluded if e.get("source_channel", "") in ["#hr-confidential", "dm-dave-sarah"])

        total_commits = active.get("git_commit", 0) + excl_commits
        total_prs = active.get("git_pr", 0)
        total_chats = active.get("chat_message", 0) + excl_chats
        total_tickets = active.get("jira_issue", 0)

        counts_ok = (total_commits == 56 and total_prs == 25 and total_chats == 121 and total_tickets == 13)

        # Check required excluded sources
        excl_channels = {e.get("source_channel", "").lower(): e.get("exclusion_reason", "") for e in excluded}
        has_hr_channel = any("#hr-confidential" in k for k in excl_channels)
        has_dm_channel = any("dm-dave-sarah" in k for k in excl_channels)
        has_payroll_repo = any("hr-payroll-tools" in k for k in excl_channels)

        all_reasons_present = all(len(v.strip()) > 0 for v in excl_channels.values())

        if counts_ok and has_hr_channel and has_dm_channel and has_payroll_repo and all_reasons_present:
            print(f"[PASS] Step 2: Load demo project: verified 56 commits, 25 PRs, 121 messages, 13 tickets; "
                  f"HR channel, private DM, and payroll repo excluded with justifications (HTTP 200)")
            passed_steps += 1
        else:
            print(f"[FAIL] Step 2: Counts or exclusions mismatch:")
            print(f"       Counts: commits={total_commits} (exp 56), prs={total_prs} (exp 25), "
                  f"chats={total_chats} (exp 121), tickets={total_tickets} (exp 13)")
            print(f"       Exclusions: HR={has_hr_channel}, DM={has_dm_channel}, Payroll={has_payroll_repo}")
            sys.exit(1)
    except Exception as e:
        print(f"[FAIL] Step 2: Failed with exception: {e}")
        sys.exit(1)

    # -------------------------------------------------------------
    # 3. Extract claims & verify planted secrets are never exposed
    # -------------------------------------------------------------
    step_num = 3
    try:
        extract_res = requests.post(f"{base_url}/api/extract", headers=get_headers("leaver"), json={}, timeout=20)
        if extract_res.status_code != 200:
            print(f"[FAIL] Step 3: POST /api/extract returned status {extract_res.status_code}: {extract_res.text}")
            sys.exit(1)

        claims_res = requests.get(f"{base_url}/api/claims", headers=get_headers("leaver"), timeout=15)
        if claims_res.status_code != 200:
            print(f"[FAIL] Step 3: GET /api/claims returned status {claims_res.status_code}")
            sys.exit(1)

        claims_data = claims_res.json()
        raw_text = claims_res.text + " " + extract_res.text

        # Planted secret strings that must NEVER leak
        leaked_secrets = []
        if "AKIAIOSFODNN7EXAMPLE" in raw_text:
            leaked_secrets.append("AKIAIOSFODNN7EXAMPLE")
        if "sk_test_51Mz" in raw_text or "sk_test" in raw_text:
            leaked_secrets.append("sk_test_secret")
        if "dave.personal@gmail.com" in raw_text or "dave.miller@hyperion-corp.internal" in raw_text:
            leaked_secrets.append("email_pii")
        if "+1-555-019-2834" in raw_text or "555-0199" in raw_text:
            leaked_secrets.append("phone_pii")

        if not leaked_secrets:
            print(f"[PASS] Step 3: Get claims: zero planted secrets (AKIAIOSFODNN7EXAMPLE, sk_test, email, phone) "
                  f"found in any API response (HTTP 200)")
            passed_steps += 1
        else:
            print(f"[FAIL] Step 3: Secrets leaked in API responses: {leaked_secrets}")
            sys.exit(1)
    except Exception as e:
        print(f"[FAIL] Step 3: Failed with exception: {e}")
        sys.exit(1)

    # -------------------------------------------------------------
    # 4. Check Redis = SUPERSEDED, SMS = UNCERTAIN, Unassigned = MISSING, Billing = Bus Factor
    # -------------------------------------------------------------
    step_num = 4
    try:
        claims = claims_data.get("claims", [])
        
        redis_claim = next((c for c in claims if "Redis" in c.get("title", "") or "Redis" in c.get("summary", "")), None)
        sms_claim = next((c for c in claims if "Twilio" in c.get("title", "") or "SMS" in c.get("title", "")), None)
        missing_claim = next((c for c in claims if c.get("status") == "MISSING" or "Invoice" in c.get("title", "")), None)

        redis_ok = redis_claim is not None and redis_claim.get("status") == "SUPERSEDED_BY_CODE"
        sms_ok = sms_claim is not None and sms_claim.get("status") == "UNCERTAIN"
        missing_ok = missing_claim is not None and missing_claim.get("status") == "MISSING"

        # Check bus factor endpoint
        bf_res = requests.get(f"{base_url}/api/bus_factor", headers=get_headers("leaver"), timeout=15)
        if bf_res.status_code != 200:
            print(f"[FAIL] Step 4: GET /api/bus_factor returned status {bf_res.status_code}")
            sys.exit(1)

        bf_data = bf_res.json()
        billing = next((b for b in bf_data if "billing" in b.get("module", "").lower()), None)
        billing_ok = (billing is not None and 
                      billing.get("leaver_share_pct", 0) > 80 and 
                      "CRITICAL" in billing.get("risk_level", "").upper())

        if redis_ok and sms_ok and missing_ok and billing_ok:
            print(f"[PASS] Step 4: Claim statuses verified (Redis = SUPERSEDED_BY_CODE, SMS = UNCERTAIN, "
                  f"Unassigned ticket = MISSING) and billing module flagged as critical bus-factor risk ({billing.get('leaver_share_pct')}%) (HTTP 200)")
            passed_steps += 1
        else:
            print(f"[FAIL] Step 4: Semantic claim check failed:")
            print(f"       Redis={redis_ok} ({redis_claim.get('status') if redis_claim else 'not found'})")
            print(f"       SMS={sms_ok} ({sms_claim.get('status') if sms_claim else 'not found'})")
            print(f"       Missing={missing_ok} ({missing_claim.get('status') if missing_claim else 'not found'})")
            print(f"       Billing={billing_ok} ({billing})")
            sys.exit(1)
    except Exception as e:
        print(f"[FAIL] Step 4: Failed with exception: {e}")
        sys.exit(1)

    # -------------------------------------------------------------
    # 5. Successor role gating: Expect 403 Forbidden
    # -------------------------------------------------------------
    step_num = 5
    try:
        succ_res = requests.get(f"{base_url}/api/claims", headers=get_headers("successor"), timeout=15)
        if succ_res.status_code == 403 and "Access Denied" in succ_res.text:
            print(f"[PASS] Step 5: Successor request in draft mode rejected with HTTP 403 Forbidden (expected security gate)")
            passed_steps += 1
        else:
            print(f"[FAIL] Step 5: Expected 403 Forbidden for successor, got status {succ_res.status_code}: {succ_res.text}")
            sys.exit(1)
    except Exception as e:
        print(f"[FAIL] Step 5: Failed with exception: {e}")
        sys.exit(1)

    # -------------------------------------------------------------
    # 6. Review & Sign-Off Gating Sequence
    # -------------------------------------------------------------
    step_num = 6
    try:
        # A) Test rejection of premature lead signoff on a fresh workspace
        fresh_ws = f"{ws_id}-leadgate"
        lead_early = requests.post(f"{base_url}/api/signoff/lead", headers=get_headers("lead", fresh_ws), json={"notes": "premature approval"}, timeout=15)
        if lead_early.status_code != 400:
            print(f"[FAIL] Step 6: Expected HTTP 400 for premature lead sign-off, got {lead_early.status_code}: {lead_early.text}")
            sys.exit(1)

        # B) Test rejection of lead signoff before leaver signoff on main workspace
        lead_early_main = requests.post(f"{base_url}/api/signoff/lead", headers=get_headers("lead"), json={"notes": "premature approval"}, timeout=15)
        if lead_early_main.status_code != 400:
            print(f"[FAIL] Step 6: Expected HTTP 400 for lead signoff prior to leaver, got {lead_early_main.status_code}")
            sys.exit(1)

        # C) As leaver, review and approve all claims
        for claim in claims:
            cid = claim["id"]
            rev_res = requests.post(f"{base_url}/api/claims/{cid}/review", headers=get_headers("leaver"), json={"approved": True, "rejected": False}, timeout=15)
            if rev_res.status_code != 200:
                print(f"[FAIL] Step 6: Claim review for {cid} failed with status {rev_res.status_code}")
                sys.exit(1)

        # D) As leaver, sign off -> v0.2
        leaver_res = requests.post(f"{base_url}/api/signoff/leaver", headers=get_headers("leaver"), json={"notes": "Leaver Dave approved claims"}, timeout=15)
        if leaver_res.status_code != 200 or leaver_res.json().get("new_version") != "v0.2":
            print(f"[FAIL] Step 6: Leaver signoff failed: {leaver_res.status_code} {leaver_res.text}")
            sys.exit(1)

        # E) As lead, sign off -> v1.0
        lead_res = requests.post(f"{base_url}/api/signoff/lead", headers=get_headers("lead"), json={"notes": "Lead Marcus approved v1.0 publication"}, timeout=15)
        if lead_res.status_code != 200 or lead_res.json().get("new_version") != "v1.0":
            print(f"[FAIL] Step 6: Lead signoff failed: {lead_res.status_code} {lead_res.text}")
            sys.exit(1)

        # F) Verify workspace version is v1.0
        ws_res = requests.get(f"{base_url}/api/workspace/state", headers=get_headers("lead"), timeout=15)
        if ws_res.status_code != 200 or ws_res.json().get("version") != "v1.0":
            print(f"[FAIL] Step 6: Workspace version confirmation failed: {ws_res.text}")
            sys.exit(1)

        print(f"[PASS] Step 6: Sign-off gating confirmed: premature lead sign-off rejected (HTTP 400); "
              f"Dave signed off v0.2 -> Marcus published v1.0 (HTTP 200)")
        passed_steps += 1
    except Exception as e:
        print(f"[FAIL] Step 6: Failed with exception: {e}")
        sys.exit(1)

    # -------------------------------------------------------------
    # 7. Successor Handover Access & Receipt Acknowledgment
    # -------------------------------------------------------------
    step_num = 7
    try:
        # Handover now returns 200 with approved claims only
        succ_claims_res = requests.get(f"{base_url}/api/claims", headers=get_headers("successor"), timeout=15)
        if succ_claims_res.status_code != 200:
            print(f"[FAIL] Step 7: Expected HTTP 200 for successor view in v1.0, got {succ_claims_res.status_code}")
            sys.exit(1)

        succ_data = succ_claims_res.json()
        succ_claims = succ_data.get("claims", [])
        all_approved = len(succ_claims) > 0 and all(c.get("approved") == 1 for c in succ_claims)

        if not all_approved:
            print(f"[FAIL] Step 7: Successor claims contain unapproved items or are empty: count={len(succ_claims)}")
            sys.exit(1)

        # Acknowledge receipt
        ack_res = requests.post(f"{base_url}/api/successor/acknowledge", headers=get_headers("successor"), json={}, timeout=15)
        if ack_res.status_code == 200 and ack_res.json().get("status") == "acknowledged":
            print(f"[PASS] Step 7: Successor view unblocked in v1.0 (HTTP 200 with {len(succ_claims)} approved claims); "
                  f"receipt acknowledged and logged to audit trail (HTTP 200)")
            passed_steps += 1
        else:
            print(f"[FAIL] Step 7: Acknowledge receipt failed: {ack_res.status_code} {ack_res.text}")
            sys.exit(1)
    except Exception as e:
        print(f"[FAIL] Step 7: Failed with exception: {e}")
        sys.exit(1)

    # -------------------------------------------------------------
    # 8. Cryptographic Audit Trail: Verify, Tamper, Restore
    # -------------------------------------------------------------
    step_num = 8
    try:
        # 1. Initial audit verify -> valid
        v1_res = requests.get(f"{base_url}/api/audit/verify", headers=get_headers("leaver"), timeout=15)
        if v1_res.status_code != 200 or not v1_res.json().get("valid"):
            print(f"[FAIL] Step 8: Initial audit verification failed: {v1_res.text}")
            sys.exit(1)

        # 2. Simulate tamper
        t_res = requests.post(f"{base_url}/api/audit/simulate_tamper", headers=get_headers("leaver"), json={}, timeout=15)
        if t_res.status_code != 200:
            print(f"[FAIL] Step 8: Simulate tamper endpoint returned {t_res.status_code}")
            sys.exit(1)

        # 3. Audit verify -> must FAIL (valid = False)
        v2_res = requests.get(f"{base_url}/api/audit/verify", headers=get_headers("leaver"), timeout=15)
        if v2_res.status_code != 200 or v2_res.json().get("valid") is not False:
            print(f"[FAIL] Step 8: Expected audit verification failure after tampering, got: {v2_res.text}")
            sys.exit(1)

        # 4. Restore
        r_res = requests.post(f"{base_url}/api/audit/restore", headers=get_headers("leaver"), json={}, timeout=15)
        if r_res.status_code != 200:
            print(f"[FAIL] Step 8: Restore audit endpoint returned {r_res.status_code}")
            sys.exit(1)

        # 5. Audit verify -> must PASS (valid = True)
        v3_res = requests.get(f"{base_url}/api/audit/verify", headers=get_headers("leaver"), timeout=15)
        if v3_res.status_code != 200 or not v3_res.json().get("valid"):
            print(f"[FAIL] Step 8: Final audit verification after restore failed: {v3_res.text}")
            sys.exit(1)

        print(f"[PASS] Step 8: Cryptographic ledger verified: authentic chain (valid) -> simulated tamper (verify detected break) -> restored chain (valid) (HTTP 200)")
        passed_steps += 1
    except Exception as e:
        print(f"[FAIL] Step 8: Failed with exception: {e}")
        sys.exit(1)

    print(f"\n============================================================")
    print(f"SMOKE TEST SUMMARY: {passed_steps}/{total_steps} STEPS PASSED (100% SUCCESS)")
    print(f"Target Live Service: {base_url}")
    print(f"Status: ALL SYSTEMS NOMINAL AND DEPLOYED CORRECTLY")
    print(f"============================================================")
    return 0


if __name__ == "__main__":
    target_url = sys.argv[1] if len(sys.argv) > 1 else "https://relaystate-innovix.onrender.com"
    sys.exit(run_smoke_test(target_url))
