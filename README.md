# RelayState — Knowledge Handover Engine
**Team InnoviX | Problem Statement 01: Prevent Critical Knowledge From Leaving With People**  
**Participant & Lead:** Kavin S S G (Solo Full-Stack AI Engineer)

RelayState is an intelligent, evidence-grounded knowledge handover platform that transforms scattered project activity into a verifiable, role-tailored transition package when a team member leaves.

---

## Key Features in Round 2 (Working MVP)

* **5-Stage End-to-End Workflow:** Connect $\rightarrow$ Reconstruct $\rightarrow$ Verify $\rightarrow$ Review $\rightarrow$ Handover.
* **Pre-Storage Secret & PII Scrubbing:** Automated regex detection strips AWS keys, bearer tokens, emails, and phone numbers before data enters storage.
* **Source Exclusion Boundaries:** Excludes private streams (`#hr-confidential`, `dm-dave-sarah`, `hr-payroll-tools`) with visible justifications.
* **Verbatim Grounding Check:** Drops hallucinated claims whose cited quotes do not appear verbatim in the ingested source.
* **Temporal Supersession Radar:** Detects when code commits override earlier chat consensus (e.g. Memcached commit superseding Redis chat agreement).
* **Server-Enforced Role Gating:** Successors receive an `HTTP 403 Forbidden` until the Engineering Lead formally approves version `v1.0`.
* **Hash-Chained Audit Ledger:** Sequential SHA-256 block ledger with interactive **Simulate Tampering** and **Restore** verification.
* **Bus-Factor Heatmap:** Automatically identifies single points of failure (e.g. `billing/` module authored 97.7% by leaver).

---

## Quickstart (Run Locally in 60 Seconds)

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Run the Application
```bash
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```
Open **`http://localhost:8000`** in your browser.

### 3. Run the Test Suite
```bash
python -m pytest tests -v
```

---

## Docker Deployment
```bash
docker build -t relaystate .
docker run -p 8000:8000 -e PORT=8000 relaystate
```

---

## How Judges Can Test the Workflow

1. Open `http://localhost:8000` (or the deployed link).
2. Click **"Run Guided Walkthrough"** (or click **"Load Demo Project"**).
3. Inspect the **Extracted Claims**:
   * Note the `SUPERSEDED BY CODE` badge on the Redis proposal.
   * Click any **Citation Pill** to open the slide-out **Source Drawer**.
4. Test the **Successor 403 Gate**:
   * In the top-right role dropdown, switch to **Successor (Amina)**.
   * Click tab **02. Successor Day-1 Navigator** $\rightarrow$ Observe the `HTTP 403 Forbidden` security block.
5. Publish the Handover:
   * Switch role to **Leaver (Dave)** $\rightarrow$ Click **"Leaver Sign-Off (Promote to v0.2)"**.
   * Switch role to **Lead (Marcus)** $\rightarrow$ Click **"Lead Sign-Off (Publish v1.0)"**.
   * Switch role to **Successor** $\rightarrow$ Notice the view is now unlocked! Click **"Acknowledge Receipt"**.
6. Test Cryptographic Tampering:
   * Click tab **03. Cryptographic Audit Trail**.
   * Click **"Verify Audit Chain"** $\rightarrow$ Observe green valid status.
   * Click **"Simulate Tampering"** $\rightarrow$ Notice immediate red alert detecting hash mismatch at block #2.
   * Click **"Restore Authentic State"** $\rightarrow$ Notice the chain heals back to green.

---

## Honest Limitations (Judges' Evaluation Principle)

* **Demo Authentication:** For hackathon evaluation convenience, roles are selected via dropdown rather than verified logins so judges can try all perspectives without creating accounts. Access rules are strictly enforced by the server based on the active role header.
* **Data Sources:** Current demonstration uses the synthetic *Project Hyperion* fixture dataset to guarantee privacy compliance (no real corporate secrets exposed). Live OAuth connectors for GitHub/Slack are planned for enterprise deployment.

---

## AI Tools & Disclosures (Rule 7)

In accordance with hackathon rules, development utilized **Google Antigravity / Gemini** for code boilerplate assistance, architecture planning, and synthetic dataset drafting. Runtime inference supports the Gemini API with rule-based fallback.
