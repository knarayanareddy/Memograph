# Memograph remediation plan

This is a future-work plan, not a record of fixes. Entry: the [review](REVIEW.md), pinned snapshot and an owner-authorized isolated environment with synthetic data. Exit: each applicable task below has independently observed evidence; exceptions require explicit owner acceptance. Commands below are planned, not executed.

## P0 — Baseline and reproduction

**Entry gate:** pinned review, authorized isolated environment and access to the failed run's logs. **Exit gate:** T-01's cause and verification evidence are recorded, or an approved exception identifies the unresolved blocker. P1 may start independently; P2 depends on T-01 as shown below.

### T-01 — Diagnose documentation failure (M-01)
**Prerequisites:** maintainer access to pinned run logs; observed `.github/workflows/docs.yml`. 1. Identify the failed job and step in run 41643182480, redacting any sensitive output. 2. Reproduce its build or Pages condition in isolation using the pinned revision and workflow settings. 3. Record the cause, make the narrow correction, and rerun the unchanged relevant gate and deployment path.

**Deliverable/verification:** failure-to-fix record with fresh build and, where authorized, independently observed Pages output; distinguish infrastructure permissions from source errors.
- [ ] Actual failing step and root cause supported by logs.
- [ ] Fresh build and authorized deployment observed, or remaining deployment blocker recorded.

## P1 — Confirmed controls and security boundaries

**Entry gate:** authorized environment and owner-selected trust model for T-02; this phase can overlap P0. **Exit gate:** T-02 through T-04 have their individual DoD evidence or approved exceptions, with the chosen deployment boundary and residual risks documented. Task prerequisites still govern work within the phase.

### T-02 — Define trust and data policy (M-02; preventive)
**Prerequisites:** owner chooses private single-trust-domain or multi-tenant operation; observed `src/memograph/api/app.py`, `src/memograph/api/auth.py`, and `SECURITY.md`. 1. Map every HTTP/WebSocket route, manager instance, agent identity, transcript archive and provider egress. 2. For single-trust use, enforce a documented network boundary; for multi-tenant use, design and implement identity-scoped reads, writes and events before exposure. 3. Define secret rotation, TLS termination, retention/deletion and redaction for logs, provider traffic and backups.

**Deliverable/verification:** owner-approved threat model and enforced boundary; synthetic wrong-key and, if applicable, cross-tenant read/write/event tests must fail closed. Deliberately bypass the guard and demonstrate that a negative test fails.
- [ ] Deployment and data policy approved and implemented.
- [ ] Actual route and WebSocket authorization tests demonstrate the selected boundary.

### T-03 — Protect authentication and quota (M-04, M-05)
**Prerequisites:** T-02 deployment topology and owner approval of edge infrastructure; observed `src/memograph/api/app.py` and `src/memograph/api/rate_limit.py`. 1. Choose a pre-auth limit at a trusted proxy or equivalent layer, including an explicit trusted-client-address policy. 2. Decide whether the authenticated shared-key limit must be global across workers; implement shared enforcement or document the single-process constraint. 3. Test repeated invalid HTTP and WebSocket handshakes and valid-key traffic across at least two workers, including proxy failure and recovery.

**Deliverable/verification:** configuration and synthetic request evidence showing bounded attempts and the intended aggregate quota; deliberately disable the chosen limiter and show its negative test fails. Avoid recording key values.
- [ ] Pre-auth protection tested on both transports.
- [ ] Cross-worker behavior and failure policy match the approved deployment.

### T-04 — Validate persistence and hostile input (preventive; supports M-02)
**Prerequisites:** T-02 data-flow map; observed `README.md`, `SECURITY.md`; inspect `src/memograph/db.py`, `src/memograph/consolidation/`, `src/memograph/validation.py` and `sdk/typescript/src/local.ts` before changing them. 1. Trace SQLite writes, topic-file generation, consolidation locks and TypeScript local-store containment. 2. Add independent fixtures for malicious topic paths, transcript/prompt content, SQL-shaped inputs and concurrent consolidation or interrupted writes. 3. Assert that unauthorized file paths and unsafe operations are rejected and that restart preserves committed facts while reconciling views.

**Deliverable/verification:** code-path map and tests against real entry points; break a containment or reconciliation guard in an isolated mutation and confirm the corresponding test fails.
- [ ] Adversarial cases cover Python and TypeScript boundaries where applicable.
- [ ] Crash/concurrency behavior and residual limitations are documented with evidence.

## P2 — Automation and release integrity

**Entry gate:** T-01 diagnosis and T-03/T-04 test designs are available, or their specific prerequisites have approved exceptions; release rehearsal additionally requires owner authorization. **Exit gate:** T-05 and T-06 have candidate-gate and artifact evidence or approved exceptions, including any blocked publication rehearsal.

### T-05 — Establish meaningful gates (M-01, M-03; preventive)
**Prerequisites:** T-01 diagnosis and T-03/T-04 test designs; observed `.github/workflows/ci.yml`, `pyproject.toml`, `uv.lock`, `sdk/typescript/package.json` and lockfile. 1. Verify locked Python and npm installs in clean runners and review dependency advisories, including optional extras. 2. Run the existing workflow's non-integration Python matrix and existing SDK `test` script; add isolated API/provider integration checks with synthetic credentials. 3. Pin reviewed workflow actions to immutable commits, scope permissions and rerun the original gates without lowering thresholds.

**Deliverable/verification:** candidate-SHA gate results and dependency/action review; intentionally break an SDK contract or auth assertion and observe a test failure before restoring it. A missing scanner is reported as skipped, not clean.
- [ ] Existing and added gates are independently observed on the candidate SHA.
- [ ] Dependency/advisory and action-pin decisions recorded; no thresholds weakened.

### T-06 — Rehearse release (M-03; preventive)
**Prerequisites:** T-05; owner approval for non-production publishing, PyPI/npm access and signing/provenance policy; observed `.github/workflows/release.yml`. 1. Inspect environment protection, tag authority, PyPI OIDC trust and npm token scope without revealing credentials. 2. Build candidate distributions and rehearse publication to approved non-production destinations, or document a blocked rehearsal if none exists. 3. Independently inspect artifact contents, versions, provenance and consumer installation; define safe revocation and rollback for both ecosystems.

**Deliverable/verification:** linked release rehearsal and artifact inspection, not merely a successful workflow exit.
- [ ] Publisher controls and artifact provenance verified or explicitly blocked.
- [ ] Rollback owners and package/version compatibility approved.

## P3 — Recovery, usability and independent acceptance

**Entry gate:** T-04 and T-05 are complete or have approved exceptions, with recovery targets and storage approved for T-07. **Exit gate:** T-07 and T-08 have independent restore, interface and acceptance evidence or approved exceptions, and the owner records a scoped go/no-go decision.

### T-07 — Restore and exercise interfaces (preventive)
**Prerequisites:** T-04, T-05; owner-approved RPO/RTO and storage target; observed `README.md` and API/SDK entry points; proposed operations runbook. 1. Design SQLite-consistent backups and protect transcripts, generated files and keys according to T-02. 2. Restore synthetic data into an isolated environment, rebuild views, compare known facts and measure recovery time and loss. 3. Exercise missing-key CLI/SDK errors, WebSocket disconnect behavior and documentation keyboard/screen-reader use; record defects and corrections.

**Deliverable/verification:** restore drill with timestamps, data comparison and usability observations; a backup job exit code is insufficient.
- [ ] Measured recovery meets approved targets or an exception is accepted.
- [ ] Interface failures and accessibility outcomes have evidence and owners.

### T-08 — Independent acceptance (all findings)
**Prerequisites:** T-01 through T-07 complete or approved exceptions. 1. A reviewer outside implementation compares every finding and task with candidate-SHA evidence. 2. Repeat representative broken-guard negative tests and inspect the restored data and release artifacts. 3. Record residual risks, owner decisions and explicit go/no-go without equating test counts with completeness.

**Deliverable/verification:** dated acceptance record and links to independently observed results.
- [ ] Findings and exceptions have accountable owners.
- [ ] Security, release and recovery evidence supports the approved deployment scope.

## Dependencies, approval and rollback

T-01 and T-02 can start independently; T-02 → T-03 and T-04; T-01/T-03/T-04 → T-05; T-05 → T-06; T-04/T-05 → T-07; T-01–T-07 → T-08. To progress with an exception, the owner must record the unmet gate, reason, residual risk, affected scope, accountable owner and review date; downstream prerequisites remain binding unless specifically excepted. An exception permits only the recorded progression, not an automatic production release. Owner approval is required for tenancy, external access, credentials, provider retention, infrastructure, publishing and recovery targets. Release only a reviewed candidate after independent acceptance; if rollback is needed, compare database and package compatibility first, preserve newer data, and restore only with owner authorization. Do not assume that reverting a package reverses data migrations.

**Production acceptance:** [ ] docs failure resolved or accepted; [ ] chosen auth and quota boundaries demonstrated; [ ] injection and persistence tests meaningful; [ ] locks and release provenance checked; [ ] restore drill meets approved targets; [ ] independent reviewer and owner accept remaining risks.
