"""
tests/test_project_system.py
Comprehensive test suite validating the OSIRIS / LivLM Canonical Project Management System.
Validates:
  1. Referential Integrity
  2. ID Uniqueness
  3. Evidence Path Integrity
  4. Root Hash Integrity
  5. Gate Monotonicity
  6. Evidence Non-Substitution Invariant
  7. Historical Immutability of REAL-CAMPAIGN-20260926T160434Z
  8. Status Derivation and Coverage Reporting
  9. Release Identity Consistency
 10. Prohibition of Unsupported Advantage Claims
"""

import os
import json
import hashlib
from pathlib import Path
import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
PROJECT_DIR = REPO_ROOT / "project"

def load_json(rel_path: str):
    path = REPO_ROOT / rel_path
    assert path.is_file(), f"File {rel_path} does not exist"
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

# Fixtures for project registers
@pytest.fixture
def manifest():
    return load_json("project/PROJECT_MANIFEST.json")

@pytest.fixture
def objectives():
    return load_json("project/OBJECTIVES.json")

@pytest.fixture
def eval_matrix():
    return load_json("project/EVALUATION_MATRIX.json")

@pytest.fixture
def wbs():
    return load_json("project/WORK_BREAKDOWN_STRUCTURE.json")

@pytest.fixture
def milestones():
    return load_json("project/MILESTONES.json")

@pytest.fixture
def gates():
    return load_json("project/GATES.json")

@pytest.fixture
def deliverables():
    return load_json("project/DELIVERABLES.json")

@pytest.fixture
def evidence():
    return load_json("project/EVIDENCE_REGISTER.json")

@pytest.fixture
def risks():
    return load_json("project/RISK_REGISTER.json")

@pytest.fixture
def decisions():
    return load_json("project/DECISION_REGISTER.json")

@pytest.fixture
def dependencies():
    return load_json("project/DEPENDENCY_REGISTER.json")

@pytest.fixture
def change_log():
    return load_json("project/CHANGE_LOG.json")


def test_referential_integrity(manifest, objectives, eval_matrix, wbs, milestones, gates, deliverables, evidence, risks, decisions, dependencies):
    """Test 1: Every referenced object in work packages, milestones, gates, deliverables, and criteria exists in its respective register."""
    obj_ids = {o["objective_id"] for o in objectives}
    crit_ids = {c["criterion_id"] for c in eval_matrix}
    wp_ids = {w["work_package_id"] for w in wbs}
    ms_ids = {m["milestone_id"] for m in milestones}
    gate_ids = {g["gate_id"] for g in gates}
    ev_ids = {e["evidence_id"] for e in evidence}
    risk_ids = {r["risk_id"] for r in risks}
    dec_ids = {d["decision_id"] for d in decisions}
    dep_ids = {dp["dependency_id"] for dp in dependencies}

    # Manifest checks
    for oid in manifest["objectives"]:
        assert oid in obj_ids, f"Manifest references unknown objective {oid}"
    for cid in manifest["evaluation_criteria"]:
        assert cid in crit_ids, f"Manifest references unknown criterion {cid}"
    for wid in manifest["work_packages"]:
        assert wid in wp_ids, f"Manifest references unknown work package {wid}"
    for mid in manifest["milestones"]:
        assert mid in ms_ids, f"Manifest references unknown milestone {mid}"
    for gid in manifest["gates"]:
        assert gid in gate_ids, f"Manifest references unknown gate {gid}"
    for eid in manifest["evidence_packages"]:
        assert eid in ev_ids, f"Manifest references unknown evidence {eid}"
    for rid in manifest["risks"]:
        assert rid in risk_ids, f"Manifest references unknown risk {rid}"
    for did in manifest["decisions"]:
        assert did in dec_ids, f"Manifest references unknown decision {did}"
    for dpid in manifest["dependencies"]:
        assert dpid in dep_ids, f"Manifest references unknown dependency {dpid}"

    # Objectives checks
    for obj in objectives:
        for cid in obj["evaluation_criteria"]:
            assert cid in crit_ids, f"Objective {obj['objective_id']} references unknown criterion {cid}"
        for wid in obj["associated_work_packages"]:
            assert wid in wp_ids, f"Objective {obj['objective_id']} references unknown work package {wid}"

    # WBS checks
    for wp in wbs:
        assert wp["lead_objective"] in obj_ids, f"WP {wp['work_package_id']} references unknown lead objective"
        for t in wp["tasks"]:
            for er in t.get("evidence_refs", []):
                assert er in ev_ids or er in {d["deliverable_id"] for d in deliverables}, f"Task {t['task_id']} references unknown evidence/deliverable {er}"

    # Milestones checks
    for ms in milestones:
        for wid in ms["work_packages"]:
            assert wid in wp_ids, f"Milestone {ms['milestone_id']} references unknown work package {wid}"
        for er in ms.get("required_evidence", []):
            assert er in ev_ids or er in {d["deliverable_id"] for d in deliverables}, f"Milestone {ms['milestone_id']} references unknown evidence {er}"

    # Gates checks
    for g in gates:
        for prereq in g["prerequisites"]:
            assert prereq in gate_ids, f"Gate {g['gate_id']} references unknown prereq gate {prereq}"
        for er in g["evidence_refs"]:
            assert er in ev_ids, f"Gate {g['gate_id']} references unknown evidence {er}"

    # Deliverables checks
    for dl in deliverables:
        assert dl["work_package"] in wp_ids, f"Deliverable {dl['deliverable_id']} references unknown work package {dl['work_package']}"
        assert dl["milestone"] in ms_ids, f"Deliverable {dl['deliverable_id']} references unknown milestone {dl['milestone']}"
        for er in dl["evidence_refs"]:
            assert er in ev_ids, f"Deliverable {dl['deliverable_id']} references unknown evidence {er}"


def test_id_uniqueness(objectives, eval_matrix, wbs, milestones, gates, deliverables, evidence, risks, decisions, dependencies, change_log):
    """Test 2: Every identifier across all project management registers is globally unique."""
    seen_ids = {}

    def check_id(item_id, item_type):
        assert item_id not in seen_ids, f"Duplicate ID detected: {item_id} (found in {seen_ids[item_id]} and {item_type})"
        seen_ids[item_id] = item_type

    for o in objectives:
        check_id(o["objective_id"], "OBJECTIVE")
    for c in eval_matrix:
        check_id(c["criterion_id"], "CRITERION")
    for w in wbs:
        check_id(w["work_package_id"], "WORK_PACKAGE")
        for t in w["tasks"]:
            check_id(t["task_id"], "TASK")
    for m in milestones:
        check_id(m["milestone_id"], "MILESTONE")
    for g in gates:
        check_id(g["gate_id"], "GATE")
    for d in deliverables:
        check_id(d["deliverable_id"], "DELIVERABLE")
    for e in evidence:
        check_id(e["evidence_id"], "EVIDENCE")
    for r in risks:
        check_id(r["risk_id"], "RISK")
    for dec in decisions:
        check_id(dec["decision_id"], "DECISION")
    for dep in dependencies:
        check_id(dep["dependency_id"], "DEPENDENCY")
    for chg in change_log:
        check_id(chg["change_id"], "CHANGE")


def test_evidence_path_integrity(evidence, deliverables):
    """Test 3: Every referenced evidence and deliverable path exists on disk."""
    for ev in evidence:
        path = REPO_ROOT / ev["path"]
        assert path.exists(), f"Evidence path for {ev['evidence_id']} not found on disk: {path}"

    for dl in deliverables:
        if dl.get("status") in ("PUBLISHED", "READY"):
            path = REPO_ROOT / dl["path"]
            assert path.exists(), f"Deliverable path for {dl['deliverable_id']} not found on disk: {path}"


def test_root_hash_integrity(evidence):
    """Test 4: Evidence root hashes match the actual manifests on disk."""
    ev_map = {e["evidence_id"]: e for e in evidence}

    # Test Operational Failed Campaign root hash
    op_ev = ev_map["EVD-OPS-001"]
    op_manifest = load_json(op_ev["path"])
    expected_op_hash = "sha256:fcb966e6b010c282531a7bc8c962b1154c156f71b9543e09968940e79dc314da"
    assert op_ev["root_hash"] == expected_op_hash
    assert op_manifest["root_hash"] == expected_op_hash

    # Test Scientific Evidence Package root hash
    sci_ev = ev_map["EVD-SCI-001"]
    sci_manifest = load_json(sci_ev["path"])
    assert sci_ev["root_hash"] == sci_manifest["root_hash"]

    # Test Cross-Plane Provenance Package root hash
    xpl_ev = ev_map["EVD-XPL-001"]
    xpl_root_doc = load_json("evidence/provenance/XPL-2026-09-26-001/ROOT_HASH.json")
    assert xpl_ev["root_hash"] == xpl_root_doc["root_hash"]


def test_gate_monotonicity(gates):
    """Test 5: Gate Monotonicity - A dependent gate cannot be PASSED if any prerequisite is NOT PASSED."""
    gate_by_id = {g["gate_id"]: g for g in gates}

    for g in gates:
        status = g["status"]
        prereqs = g.get("prerequisites", [])
        if status == "PASSED":
            for pid in prereqs:
                prereq_gate = gate_by_id.get(pid)
                assert prereq_gate is not None, f"Prerequisite {pid} not found"
                assert prereq_gate["status"] == "PASSED", (
                    f"Gate monotonicity violation: Gate {g['gate_id']} is PASSED, "
                    f"but its prerequisite {pid} is {prereq_gate['status']}"
                )

    # Specific check: GATE-003 (QPU Eligibility) MUST NOT be PASSED when GATE-002 is NOT_READY
    gate_002 = gate_by_id["GATE-002"]
    gate_003 = gate_by_id["GATE-003"]
    if gate_002["status"] != "PASSED":
        assert gate_003["status"] in ("BLOCKED", "NOT_READY"), "GATE-003 must be BLOCKED when GATE-002 is not passed"


def test_evidence_non_substitution(evidence, eval_matrix, gates):
    """Test 6: Evidence Non-Substitution Invariant - Planes cannot substitute for one another."""
    ev_by_id = {e["evidence_id"]: e for e in evidence}

    # Operational evidence cannot support scientific criteria
    op_ev = ev_by_id["EVD-OPS-001"]
    assert "scientific_validity" in op_ev["does_not_establish"]
    assert "quantum_advantage" in op_ev["does_not_establish"]

    # Scientific evidence cannot support operational deployment
    sci_ev = ev_by_id["EVD-SCI-001"]
    assert "deployment_authorization" in sci_ev["does_not_establish"]

    # In evaluation matrix, check that operational criteria do not list purely scientific evidence and vice-versa
    crit_by_id = {c["criterion_id"]: c for c in eval_matrix}
    val_crit = crit_by_id["CRIT-VAL-001"]  # VALIDATION_RIGOR is scientific
    for eid in val_crit["evidence_refs"]:
        assert ev_by_id[eid]["evidence_plane"] != "OPERATIONAL", f"Operational evidence {eid} improperly linked to scientific validation criterion"

    # Provenance cannot substitute for primary claims
    xpl_ev = ev_by_id["EVD-XPL-001"]
    assert "scientific_claim_validity" in xpl_ev["does_not_establish"]
    assert "operational_deployment_authorization" in xpl_ev["does_not_establish"]


def test_historical_immutability(evidence):
    """Test 7: Historical Immutability - REAL-CAMPAIGN-20260926T160434Z is permanently frozen with S_deployed = FALSE."""
    op_ev = next(e for e in evidence if e["evidence_id"] == "EVD-OPS-001")
    manifest = load_json(op_ev["path"])

    assert op_ev["status"] == "FALSE", "Operational failed campaign status must be FALSE"
    assert manifest["campaign_id"] == "REAL-CAMPAIGN-20260926T160434Z"
    assert manifest["adjudication_summary"]["s_deployed"] == "FALSE"
    assert manifest["adjudication_summary"]["cloud_deployment_status"] == "BLOCKED"
    assert manifest["root_hash"] == "sha256:fcb966e6b010c282531a7bc8c962b1154c156f71b9543e09968940e79dc314da"

    # Adjudication must record negative gate decisions
    adj = load_json("evidence/operational/REAL-CAMPAIGN-20260926T160434Z/ADJUDICATION.json")
    assert adj["gate_outcomes"]["s_deployed"] == "FALSE"
    assert adj["gate_outcomes"]["cloud_deployment_allowed"] is False
    assert adj["gate_outcomes"]["confirmatory_execution_allowed"] is False


def test_status_derivation():
    """Test 8: scripts/project_status.py runs and derives consistent metrics."""
    from scripts.project_status import run_status_check, generate_status_md

    data = run_status_check()
    assert data["stats"]["total_tasks"] == 32
    assert data["stats"]["done_tasks"] >= 16

    # Verify coverage calculations
    cov = {c["name"]: c for c in data["coverage_report"]}
    assert cov["NOVELTY"]["satisfied"] >= 1
    assert cov["FEASIBILITY"]["satisfied"] >= 1
    assert cov["VALIDATION_RIGOR"]["percentage"] < 50.0  # Cannot be completed before adversarial campaign
    assert cov["RESOURCE_USE"]["percentage"] == 0.0      # Zero QPU resources consumed

    # Verify STATUS.md text output
    md_text = generate_status_md(data)
    assert "OSIRIS MASTER STATUS:" in md_text
    assert "S_deployed:                   FALSE" in md_text
    assert "CloudDeploymentAllowed:       FALSE (BLOCKED)" in md_text


def test_release_identity_consistency(manifest):
    """Test 9: Release identity consistency between manifest, tags, and commit hashes."""
    assert manifest["source_commit"] == "ba09973"
    assert manifest["release_anchor"] == "v0.1.0-beta.1"

    rel_manifest = load_json("RELEASE_MANIFEST.json")
    assert rel_manifest["tag"] == "v0.1.0-beta.1"
    assert rel_manifest["git_commit"] in ("8b3f047", "ba09973")
    assert "REFERENCE IMPLEMENTATION (NOT DEPLOYMENT-ATTESTED)" in rel_manifest["release_designation"]


def test_no_unsupported_quantum_claims(objectives, eval_matrix, gates, deliverables):
    """Test 10: No unsupported quantum advantage claims anywhere in project system."""
    # Objectives must not claim quantum advantage is achieved
    for o in objectives:
        assert "proven quantum advantage" not in o["description"].lower()
        if o["objective_id"] == "OBJ-002":
            assert o["status"] != "DONE", "Hardware confrontation cannot be marked DONE"

    # Gates must not show hardware execution passed
    gate_by_id = {g["gate_id"]: g for g in gates}
    assert gate_by_id["GATE-003"]["status"] == "BLOCKED"
    assert gate_by_id["GATE-004"]["status"] == "NOT_READY"

    # Evaluation matrix criteria must not declare validation complete
    crit_by_id = {c["criterion_id"]: c for c in eval_matrix}
    assert crit_by_id["CRIT-VAL-001"]["status"] != "COMPLETE"
    assert crit_by_id["CRIT-RES-001"]["status"] != "COMPLETE"
