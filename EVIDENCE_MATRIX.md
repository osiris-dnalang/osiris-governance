# Evidence Matrix & Claims Ledger

**Release Reference:** `OSIRIS-LIVLM-BETA-0.1.0-REF`  
**Target Release:** `v0.1.0-beta.1`  
**Epistemic Rule:** Strict demarcation of claims; adverse-first precedence; no cross-plane substitution.  

---

## 1. Master Evidence Matrix

| Claim | Artifact | Evidence Type | Status | Reproduction | Deployment Relevance |
|---|---|---|---|---|---|
| **Canonical Serialization Determinism** | `src/osiris_governance/canonical.py` | Governance / Code | `VERIFIED` | `pytest tests/test_canonical_binding.py` | Required for cryptographic permit hashing |
| **Float Rejection in JSON Proposals** | `src/osiris_governance/canonical.py` | Governance / Policy | `VERIFIED` | `test_reject_float_in_strict_parse` | Guarantees identical cross-architecture parsing |
| **Duplicate Key Rejection** | `src/osiris_governance/canonical.py` | Governance / Policy | `VERIFIED` | `test_reject_duplicate_key_in_strict_parse` | Prevents smuggling attacks during canonicalization |
| **Pre-Adapter Capability Enforcement** | `src/osiris_governance/governor.py` | Runtime Security | `VERIFIED` | `pytest tests/test_replay_governor.py` | Proves zero adapter code runs without valid permit |
| **In-Epoch Nonce Deduplication** | `src/osiris_governance/governor.py` | Runtime Security | `VERIFIED` | `test_inv_10_in_epoch_nonce_deduplication` | Prevents execution replay within an epoch |
| **Append-Only Hash Chain Integrity** | `src/osiris_governance/ledger.py` | Reproducibility | `VERIFIED` | `test_ledger_append_and_hash_chain_integrity` | Verifies tamper-evident audit history |
| **Evidence Non-Substitution Invariant** | `src/osiris_governance/ledger.py` | Governance / Policy | `VERIFIED` | `test_cross_plane_substitution_detected` | Blocks runtime evidence from asserting release |
| **Adverse-First Precedence Resolution** | `src/osiris_governance/adjudication.py` | Governance / Logic | `VERIFIED` | `test_s_deployed_fail_precedence` | Adverse finding forces `FALSE`/`BLOCKED` |
| **Mutable Reference Rejection** | `src/osiris_governance/ledger.py` | Governance / Policy | `VERIFIED` | `test_reject_mutable_references` | Rejects `:latest` and branch names |
| **LivLM HTTP Service Liveness & Ready** | `src/osiris_governance/livlm_service.py` | Runtime / Service | `VERIFIED` | `test_livlm_http_server_endpoints` | Confirms `/healthz` and `/readyz` operational |
| **Container Build Readiness** | `Dockerfile`, `cloudbuild.yaml` | Build / Packaging | `VERIFIED` | Multi-stage Docker build audit | Prerequisite for Cloud Run deployment |
| **Google Cloud Run Deployment** | `CLOUD_DEPLOYMENT_RECORD.md` | Cloud Infrastructure | `UNVERIFIED` (`BLOCKED`) | `gcloud run services list` (suspended) | Explicitly blocks $S_{\text{deployed}} = \text{TRUE}$ |
| **DNA-Lang Quantum Circuit Encoding** | `/home/enki/osiris_livlm.py` | Scientific / Simulation | `SIMULATED` | `python3 osiris_livlm.py` (Aer) | Demonstrates circuit synthesis only |
| **Physical IBM Heron QPU Execution** | `flywheel-2026/PROPOSAL.md` | Hardware Execution | `HYPOTHESIS` / `PLANNED` | Grant Milestone 2 execution | Does NOT assert current physical speedup |

---

## 2. Invariant Adjudication Trace

```text
ADJUDICATION QUERY: Is release v0.1.0-beta.1 fully authorized for production release?

EVALUATION:
1. Software correctness terms:
   - canonical_binding == PASS
   - capability_governor == PASS
   - evidence_ledger == PASS
   - http_service == PASS
   => S_software = TRUE

2. Scientific efficacy terms:
   - qpu_hardware_execution == SIMULATED / HYPOTHESIS
   => S_scientific = HYPOTHESIS (Explicitly non-blocking for governance beta)

3. Deployment terms:
   - cloud_run_live_attestation == BLOCKED_BY_CONSUMER_SUSPENSION
   => S_deployed = UNVERIFIED (BLOCKED)

FINAL ADJUDICATION DECISION:
   Because S_deployed is UNVERIFIED / BLOCKED,
   Release Status cannot be AUTHORIZED.
   Release Status = RELEASE_READY_WITH_EXPLICIT_LIMITATIONS.
```
