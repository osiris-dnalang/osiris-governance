"""Tests for Mechanical S_deployed Adjudication, Precedence, and Master Release Gate."""

import pytest
from osiris_governance.adjudicator import (
    MANDATORY_CONFINEMENT_CRITERIA,
    REQUIRED_FRESH_RUNS,
    ConfinementProbeResult,
    evaluate_release_gate,
    evaluate_s_deployed,
)
from osiris_governance.errors import SubstitutionViolationError
from osiris_governance.models.claim import EpistemicStatus
from osiris_governance.models.release import (
    AuthorizationState,
    DeployedGateStatus,
    ReleaseDecisionBasis,
)


def _make_passing_probe_set():
    """Generates the full set of 30 passing probe results (10 criteria x 3 runs)."""
    results = []
    for run_idx in REQUIRED_FRESH_RUNS:
        for crit in MANDATORY_CONFINEMENT_CRITERIA:
            results.append(
                ConfinementProbeResult(
                    criterion=crit,
                    run_index=run_idx,
                    status="PASS",
                    evidence_id=f"E-PROBE-{crit}-{run_idx}",
                )
            )
    return results


def test_s_deployed_complete_pass():
    probes = _make_passing_probe_set()
    status = evaluate_s_deployed(
        probe_results=probes,
        evidence_integrity_verified=True,
        independent_adjudication_verified=True,
    )
    assert status == DeployedGateStatus.TRUE


def test_s_deployed_fail_precedence():
    probes = _make_passing_probe_set()
    # Replace one probe with FAIL and another with BLOCKED
    probes[0] = ConfinementProbeResult(
        criterion="A",
        run_index=1,
        status="FAIL",
        evidence_id="E-PROBE-A-1-FAIL",
        error_message="Host filesystem escape succeeded",
    )
    probes[1] = ConfinementProbeResult(
        criterion="B",
        run_index=1,
        status="BLOCKED",
        evidence_id="E-PROBE-B-1-BLK",
        error_message="unshare ENOSYS",
    )

    # FALSE must take precedence over BLOCKED and UNVERIFIED
    status = evaluate_s_deployed(
        probe_results=probes,
        evidence_integrity_verified=True,
        independent_adjudication_verified=True,
    )
    assert status == DeployedGateStatus.FALSE


def test_s_deployed_blocked_precedence():
    probes = _make_passing_probe_set()
    # Replace one probe with BLOCKED (environmental limitation)
    probes[5] = ConfinementProbeResult(
        criterion="D",
        run_index=1,
        status="BLOCKED",
        evidence_id="E-PROBE-D-1-BLK",
        error_message="Namespace isolation blocked: ENOSYS",
    )

    status = evaluate_s_deployed(
        probe_results=probes,
        evidence_integrity_verified=True,
        independent_adjudication_verified=True,
    )
    assert status == DeployedGateStatus.BLOCKED


def test_s_deployed_incomplete_is_unverified():
    # Only 1 run instead of 3
    probes = [
        ConfinementProbeResult(
            criterion=crit,
            run_index=1,
            status="PASS",
            evidence_id=f"E-PROBE-{crit}-1",
        )
        for crit in MANDATORY_CONFINEMENT_CRITERIA
    ]
    status = evaluate_s_deployed(
        probe_results=probes,
        evidence_integrity_verified=True,
        independent_adjudication_verified=True,
    )
    assert status == DeployedGateStatus.UNVERIFIED


def test_s_deployed_integrity_or_independent_missing_is_unverified():
    probes = _make_passing_probe_set()
    assert evaluate_s_deployed(probes, False, True) == DeployedGateStatus.UNVERIFIED
    assert evaluate_s_deployed(probes, True, False) == DeployedGateStatus.UNVERIFIED


def test_release_gate_substitution_prohibited():
    basis = ReleaseDecisionBasis(
        release_id="REL-001",
        artifact_digest="sha256:1234",
        authorization_state=AuthorizationState.NOT_AUTHORIZED,
        s_deployed=DeployedGateStatus.TRUE,
        r_deployed=DeployedGateStatus.TRUE,
        prerequisites={"locked_artifact": True},
        claims_snapshot={"CLAIM-1": EpistemicStatus.VERIFIED},
        fixture_may_substitute_for_deployed=True, # Prohibited!
    )
    with pytest.raises(SubstitutionViolationError):
        evaluate_release_gate(basis)


def test_release_gate_eligible_when_all_pass():
    basis = ReleaseDecisionBasis(
        release_id="REL-002",
        artifact_digest="sha256:abcd",
        authorization_state=AuthorizationState.NOT_AUTHORIZED,
        s_deployed=DeployedGateStatus.TRUE,
        r_deployed=DeployedGateStatus.TRUE,
        prerequisites={
            "locked_artifact": True,
            "preregistration": True,
            "lineage_pinned": True,
            "independent_review": True,
            "adversarial_audit": True,
            "external_custody": True,
            "governance_approval": True,
        },
        claims_snapshot={"CLAIM-1": EpistemicStatus.VERIFIED},
        fixture_may_substitute_for_deployed=False,
    )
    result = evaluate_release_gate(basis)
    assert result == AuthorizationState.ELIGIBLE


def test_release_gate_blocked_by_s_deployed():
    basis = ReleaseDecisionBasis(
        release_id="REL-003",
        artifact_digest="sha256:abcd",
        authorization_state=AuthorizationState.NOT_AUTHORIZED,
        s_deployed=DeployedGateStatus.BLOCKED, # Blocks authorization
        r_deployed=DeployedGateStatus.TRUE,
        prerequisites={
            "locked_artifact": True,
            "preregistration": True,
            "lineage_pinned": True,
            "independent_review": True,
            "adversarial_audit": True,
            "external_custody": True,
            "governance_approval": True,
        },
        claims_snapshot={"CLAIM-1": EpistemicStatus.VERIFIED}, # Verified claim does not authorize!
        fixture_may_substitute_for_deployed=False,
    )
    result = evaluate_release_gate(basis)
    assert result == AuthorizationState.NOT_AUTHORIZED
