# Round 2 Project Documentation: RelayState
**Team InnoviX | Problem Statement 01: Prevent Critical Knowledge From Leaving With People**
**Participant & Lead:** Kavin S S G (Solo Full-Stack AI Engineer)

---

## 1. Executive Summary & Core Workflow
RelayState is a provenance-grounded knowledge handover engine that converts scattered asynchronous trails into an actionable, role-tailored transition package. For Round 2, the complete 5-stage product journey runs end-to-end without external dependencies:

```
[01. CONNECT]      --> Ingests Project Hyperion (55 commits, 25 PRs, 121 chats, 13 Jira tickets)
      ↓
[02. RECONSTRUCT]  --> Extracts decisions, blockers, dependencies, and bus-factor concentration
      ↓
[03. VERIFY]       --> Enforces verbatim grounding check (drops ungrounded quotes); detects supersession
      ↓
[04. REVIEW]       --> Leaver/Lead review studio with custom redaction, v0.1 -> v1.0 version promotion
      ↓
[05. HANDOVER]     --> Unlocks successor Day-1 view (403 forbidden until v1.0) + audit receipt
```

---

## 2. Changes from the Round 1 Plan (Justification)

In accordance with Round 2 requirements, we document the following deliberate architectural optimizations:

| Component | Round 1 Proposal | Round 2 Implementation | Justification for Change |
| :--- | :--- | :--- | :--- |
| **Tech Stack** | Next.js 14 + PostgreSQL + ChromaDB | **FastAPI + SQLite + Single Static `index.html` (Vanilla JS)** | **Zero-Failure Deployment:** Eliminates external DB connection pool drops, Docker memory limits, and React hydration errors during evaluation. Enables a lightweight, 1-second boot on any cloud host. |
| **Authentication** | OAuth 2.0 / RBAC accounts | **No-Login Role Picker (`leaver`, `lead`, `successor`) with Dismissible Banner** | **Zero-Friction Evaluation:** Judges can test all three perspectives instantly without creating dummy credentials or going through third-party login flows. Server still strictly enforces role access rules. |
| **Data Isolation** | Session Cookies | **Per-Visitor Workspace (`X-Workspace` Header + `localStorage` UUID)** | Allows multiple judges to test simultaneously in isolated sandboxes with a dedicated "Reset Workspace" button. |
| **Audit Log** | Relational Audit Table | **Cryptographic Hash-Chained Log (`SHA-256`) with Interactive Tamper Simulator** | Replaced abstract audit claims with a tangible, interactive cryptographic proof (`/api/audit/verify`) and physical tamper-simulation buttons. |

---

## 3. Implemented Features & Planted Evaluation Traps

### A. Strict Pre-Storage Redaction & Exclusions
* **Excluded Sources (3 Streams):** `#hr-confidential` (HR discussions), `dm-dave-sarah` (private 1-on-1 notice), and `hr-payroll-tools` (compensation code) are detected at ingestion and blocked from entering the knowledge store with explicit justifications displayed in the UI.
* **Automated Redaction:** AWS access keys (`AKIAIOSFODNN7EXAMPLE`), personal phone numbers, and emails are scrubbed using pre-storage regex rules before any synthesis occurs.
* **Manual Redaction Studio:** The departing member can type any arbitrary string (e.g. vendor names, compensation figures) and scrub it across all project trails.

### B. Grounding Verification & Temporal Contradiction Detection
* **Verbatim Grounding Check:** Every extracted claim must have its quoted justification present verbatim in the ingested redacted source. Fabricated or hallucinated quotes are automatically dropped and logged.
* **Temporal Supersession Trap:** Dave’s Oct 10 chat agreement to use Redis for session caching is cross-checked against git commit history. The engine detects Dave’s subsequent commit `commit-7a89b1` (Oct 18) implementing Memcached, demoting the chat claim to `SUPERSEDED_BY_CODE`.
* **Uncertainty & Orphaned Tasks:**
  * Unanswered SMS gateway ownership question in `#infra-oncall` is tagged `UNCERTAIN`.
  * Jira ticket `HYP-107` with `Assignee: Unassigned` is tagged `MISSING OWNER`.
  * Ticket `HYP-104` is extracted as an active `BLOCKER`.

### C. Server-Enforced Role Gating & Version Progression
* **Successor 403 Forbidden Gate:** When the successor role attempts to view claims while the handover is in `v0.1` or `v0.2`, the server returns a hard `HTTP 403 Forbidden` response.
* **Two-Step Sign-Off:** Leaver signs off `v0.1` $\rightarrow$ `v0.2`. Engineering Lead approves `v0.2` $\rightarrow$ `v1.0`. Only upon `v1.0` approval is the successor view unlocked.
* **Successor Acknowledgement:** Successor formally logs digital receipt of the handover package.

### D. Bus-Factor Analysis
* Analyzes commit volume per subsystem. Correctly surfaces that Dave authored **97.7% of commits in `billing/`**, tagging it as a `CRITICAL (Single Point of Failure)` risk for the incoming team.

---

## 4. Cryptographic Hash-Chained Audit Trail

Each system state mutation is recorded in an immutable ledger:
$$\text{curr\_hash} = \text{SHA-256}(\text{seq} \parallel \text{timestamp} \parallel \text{workspace\_id} \parallel \text{action} \parallel \text{actor} \parallel \text{payload\_diff} \parallel \text{prev\_hash})$$

* **Verification Endpoint:** `GET /api/audit/verify` traverses the chain from Genesis (`0000...0000`) and recalculates all hashes.
* **Interactive Tampering Demonstration:**
  * Judges can click **"Simulate Tampering"** to modify a block's payload directly in the SQLite database.
  * Running verification immediately flags: `TAMPERING DETECTED at block #2`.
  * Clicking **"Restore Authentic State"** heals the block and restores green cryptographic validity.

---

## 5. Testing Evidence (Pytest Suite)

Six automated test suites validate all core requirements (`pytest tests -v`):
* `test_redaction.py`: Verifies AWS key scrubbing, phone/email masking, and source exclusion rules.
* `test_grounding.py`: Confirms that hallucinated claims are dropped by the verbatim grounding check.
* `test_supersession.py`: Confirms Redis-to-Memcached supersession, unanswered question uncertainty, and unassigned ticket detection.
* `test_roles_and_gating.py`: Verifies server-enforced `HTTP 403 Forbidden` for successors prior to `v1.0`, leaver-to-lead sign-off gating, and receipt acknowledgement.
* `test_audit.py`: Validates hash-chain integrity, tamper detection, and state restoration.

---

## 6. Three Substantial Commitments for Round 3

In compliance with Round 2 judging criteria, we commit to delivering three major functional expansions in Round 3:

1. **Generalized Semantic & Temporal Contradiction Engine:**  
   Expand beyond rule-based triggers by using embedding cosine clustering and an LLM referee to cross-examine asynchronous chat debates against merged pull-request code diffs across unconstrained domains.
2. **Multi-Role RBAC with Cryptographic Key-Pair Signatures & OAuth:**  
   Replace client-side role switching with verified Google OAuth 2.0 / GitHub Enterprise authentication, signing handover receipts using asymmetric Ed25519 cryptographic key-pairs.
3. **Interactive Day-1 Onboarding Navigator with Real-Time Sandbox Verification:**  
   Transform the successor view from a static checklist into an active sandbox that runs automated test suites against the new joiner's local environment, confirming staging access and repo readiness.
