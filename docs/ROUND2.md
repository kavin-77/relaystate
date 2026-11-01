# Round 2 Project Documentation: RelayState
**Team InnoviX | Problem Statement 01: Prevent Critical Knowledge From Leaving With People**  
**Participant & Lead:** Kavin S S G (Solo Builder)

---

## 1. Executive Summary & Core Workflow
RelayState is a provenance-grounded knowledge handover engine that converts scattered asynchronous trails into an actionable, role-tailored transition package. For Round 2, the complete 5-stage product journey operates end-to-end:

```
[01. CONNECT]      --> Ingests Project Hyperion (56 commits, 25 PRs, 121 chats, 13 Jira tickets)
      ↓
[02. RECONSTRUCT]  --> Extracts decisions, blockers, dependencies, and bus-factor concentration
      ↓
[03. VERIFY]       --> Enforces verbatim grounding check (drops ungrounded quotes); flags supersession
      ↓
[04. REVIEW]       --> Leaver/Lead review studio with custom redaction, v0.1 -> v1.0 version promotion
      ↓
[05. HANDOVER]     --> Unlocks successor Day-1 view (403 forbidden until v1.0) + audit receipt
```

---

## 2. Changes from the Round 1 Plan (Justifications)

| Component | Round 1 Proposal | Round 2 Implementation | Engineering Justification |
| :--- | :--- | :--- | :--- |
| **Architecture & Stack** | Next.js 14 + Postgres + ChromaDB | **FastAPI + SQLite + Vanilla JS (Single HTML) + Docker** | **Self-Contained Deployment:** Eliminates external DB connection pool drops and client-side hydration issues for evaluators. Runs as a single process that boots in under 1 second. |
| **Authentication** | OAuth 2.0 / RBAC accounts | **No-Login Role Picker (`leaver`, `lead`, `successor`) with Dismissible Banner** | **Accessible Evaluation:** Evaluators can inspect all three user journeys immediately without account creation friction. Access boundaries are enforced by the server based on the active role header. |
| **Data Isolation** | Session Cookies | **Per-Visitor Workspace (`X-Workspace` Header + `localStorage` UUID)** | Allows multiple evaluators to test simultaneously in isolated sandboxes with a dedicated "Reset Workspace" button. |
| **Audit Ledger** | Relational Audit Table | **Cryptographic Hash-Chained Log (`SHA-256`) with Interactive Tamper Simulator** | Replaced passive database logging with an active cryptographic ledger (`/api/audit/verify`) and interactive tamper-testing controls. |

---

## 3. Implemented Features & Planted Evaluation Traps

### A. Pre-Storage Redaction & Exclusions
* **Excluded Sources (3 Streams):** `#hr-confidential` (HR discussions), `dm-dave-sarah` (private 1-on-1 notice), and `hr-payroll-tools` (compensation code) are detected at ingestion and blocked from entering the knowledge store with explicit justifications displayed in the UI.
* **Automated Redaction:** AWS access keys (`AKIAIOSFODNN7EXAMPLE`), personal phone numbers, and emails are scrubbed using pre-storage regex rules before any synthesis occurs.
* **Manual Redaction Studio:** The departing member can type any arbitrary string (e.g. vendor names, compensation figures) and scrub it across all project trails.

### B. Grounding Verification & Temporal Contradiction Detection
* **Verbatim Grounding Check:** Every candidate claim must have its cited quote present verbatim in the ingested redacted source. Fabricated or hallucinated quotes are automatically dropped and logged (`GROUNDING_DROP`).
* **Temporal Supersession Trap:** Dave’s Oct 10 chat agreement to use Redis for session caching is cross-checked against git commit history. The engine detects Dave’s subsequent commit `commit-7a89b1` (Oct 18) implementing Memcached, demoting the chat claim to `SUPERSEDED_BY_CODE`.
* **Uncertainty & Orphaned Tasks:**
  * Unanswered SMS gateway ownership question in `#infra-oncall` is tagged `UNCERTAIN`.
  * Jira ticket `HYP-107` with `Assignee: Unassigned` is tagged `MISSING OWNER`.
  * Ticket `HYP-104` is extracted as an active `BLOCKER`.

### C. Server-Enforced Role Gating & Version Progression
* **Successor 403 Forbidden Gate:** When the successor role attempts to view claims while the handover is in `v0.1` or `v0.2`, the server returns an `HTTP 403 Forbidden` response.
* **Two-Step Sign-Off:** Leaver signs off `v0.1` $\rightarrow$ `v0.2`. Engineering Lead approves `v0.2` $\rightarrow$ `v1.0`. Only upon `v1.0` approval is the successor view unlocked.
* **Successor Acknowledgement:** Successor logs digital receipt of the handover package.

### D. Bus-Factor Analysis
* Analyzes commit volume per subsystem. Identifies that Dave authored **97.7% of commits in `billing/`**, tagging it as a `CRITICAL (Single Point of Failure)` risk for the incoming team.

---

## 4. Cryptographic Hash-Chained Audit Trail

Each state mutation is recorded in an immutable ledger:
$$\text{curr\_hash} = \text{SHA-256}(\text{seq} \parallel \text{timestamp} \parallel \text{workspace\_id} \parallel \text{action} \parallel \text{actor} \parallel \text{payload\_diff} \parallel \text{prev\_hash})$$

* **Verification Endpoint:** `GET /api/audit/verify` traverses the chain from Genesis (`0000...0000`) and recalculates all hashes.
* **Interactive Tampering Demonstration:**
  * Evaluators can click **"Simulate Tampering"** to modify a block's payload directly in the SQLite database.
  * Running verification immediately flags: `TAMPERING DETECTED at block #2`.
  * Clicking **"Restore Authentic State"** heals the block and restores green cryptographic validity.

---

## 5. Testing Evidence (Automated Test Suite)

All 6 test suites pass in the local test runner (`pytest tests -v`):
* `test_redaction.py`: Verifies AWS key scrubbing, phone/email masking, and source exclusion rules.
* `test_grounding.py`: Confirms that candidate claims with ungrounded quotes are dropped.
* `test_supersession.py`: Confirms Redis-to-Memcached supersession, unanswered question uncertainty, and unassigned ticket detection.
* `test_roles_and_gating.py`: Verifies server-enforced `HTTP 403 Forbidden` for successors prior to `v1.0`, leaver-to-lead sign-off gating, and receipt acknowledgement.
* `test_audit.py`: Validates hash-chain integrity, tamper detection, and state restoration.

---

## 6. Three Major Commitments for Round 3

In compliance with Round 2 judging criteria, Team InnoviX commits to delivering three substantial product additions in Round 3:

1. **Semantic & LLM Temporal Contradiction Engine:**  
   Expand beyond predefined topics by combining embedding-based semantic claim clustering with an LLM evaluation pass that cross-examines arbitrary chat assertions against pull request diffs and commit histories across unconstrained project topics.
2. **Role-Tailored Developer vs. Manager Views with Sensitivity Levels:**  
   Implement granular claim sensitivity classifications (e.g. internal technical debt and debugging quirks visible strictly to technical successors, while executive roadmaps, risk registers, and ownership milestones surface in management views).
3. **Interactive Day-1 Navigator with Evidence Links & Progress Tracking:**  
   Upgrade the successor view into a step-by-step onboarding walkthrough featuring direct evidence links, task progress tracking (checkboxes and verification checks), with completion milestones formally recorded into the cryptographic audit trail.

---

## 7. Known Limitations

* **Demo Role Picker:** For evaluation convenience, roles are selected from a dropdown menu without verified logins. Access controls are enforced by the backend using request headers rather than cryptographic sessions.
* **Extractor Scope:** The deterministic rule-based extractor is calibrated to the planted Project Hyperion topics. Unconstrained topic extraction across arbitrary codebases relies on the Gemini LLM pipeline.
* **Synthetic Corpus:** The system operates on simulated Project Hyperion fixtures (commits, PRs, chat, Jira) to maintain data privacy rather than live OAuth webhooks into corporate tools.
* **LLM Environment Dependency:** The Gemini extraction pipeline requires a valid `GEMINI_API_KEY` in the environment; if omitted or unavailable, the system defaults to deterministic extraction.
* **Free-Host Cold Starts:** On free hosting services (e.g. Render free tier), inactive instances spin down and may experience a 30–50 second delay on initial load.
* **Ephemeral Database on Free Hosting:** On container platforms without attached persistent volumes, the SQLite database resets if the container instance restarts.
