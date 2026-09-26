"""Tests for Scientific Evidence Pack Ingestion & Non-Substitution Governance."""

import pytest

from osiris_governance.adjudicator import evaluate_release_gate
from osiris_governance.errors import SubstitutionViolationError
from osiris_governance.models import (
    AuthorizationState,
    DeployedGateStatus,
    EpistemicStatus,
    EvidenceClass,
    EvidenceDomain,
    ReleaseDecisionBasis,
    ReleaseRelevance,
    VerificationResult,
)
from osiris_governance.scientific_evidence import (
    ScientificEvidenceStatus,
    ingest_lpv3_validation_report,
)


def test_lpv3_auditable_pass_ingestion():
    mock_report = {
        "execution_id": "LPV3-2026-000001",
        "provider_job_id": "ibm-job-xyz-123",
        "backend": "ibm_torino",
        "lpv3_execution_auditable": True,
        "status": "AUDITABLE_PASS",
        "checklist_pass_count": 35,
        "checklist_total": 35,
        "hash_errors": [],
        "calculation_errors": [],
        "recomputed_adjudication": "PASS",
    }

    result = ingest_lpv3_validation_report(mock_report)

    assert result.status == ScientificEvidenceStatus.ANALYSIS_REPRODUCED
    assert result.evidence_record.evidence_class == EvidenceClass.MEASURED
    assert result.evidence_record.domain == EvidenceDomain.E_EXTERNAL
    assert result.verification_record.result == VerificationResult.VERIFIED
    assert result.claim_record.status == EpistemicStatus.MEASURED
    assert result.claim_record.release_relevance == ReleaseRelevance.SCIENTIFIC


def test_lpv3_incomplete_evidence_pack():
    mock_report = {
        "execution_id": "LPV3-2026-000002",
        "backend": "ibm_fez",
        "lpv3_execution_auditable": False,
        "status": "NOT_AUDITABLE",
        "checklist_pass_count": 30,
        "checklist_total": 35,
        "hash_errors": [],
        "calculation_errors": [],
        "recomputed_adjudication": "FAIL",
    }

    result = ingest_lpv3_validation_report(mock_report)
    assert result.status == ScientificEvidenceStatus.EVIDENCE_PACK_INCOMPLETE
    assert result.verification_record.result == VerificationResult.NOT_VERIFIED


def test_lpv3_invalid_hashes_pack():
    mock_report = {
        "execution_id": "LPV3-2026-000003",
        "backend": "ibm_torino",
        "lpv3_execution_auditable": False,
        "status": "NOT_AUDITABLE",
        "checklist_pass_count": 35,
        "checklist_total": 35,
        "hash_errors": ["Checksum mismatch for RAW/counts.json"],
        "calculation_errors": [],
        "recomputed_adjudication": "FAIL",
    }

    result = ingest_lpv3_validation_report(mock_report)
    assert result.status == ScientificEvidenceStatus.EVIDENCE_PACK_INVALID
    assert result.claim_record.status == EpistemicStatus.REFUTED
    assert result.verification_record.result == VerificationResult.FAILED


def test_scientific_evidence_cannot_authorize_deployment():
    """Invariant: A scientifically verified claim does NOT grant deployment authorization."""
    mock_report = {
        "execution_id": "LPV3-2026-000001",
        "provider_job_id": "ibm-job-xyz-123",
        "backend": "ibm_torino",
        "lpv3_execution_auditable": True,
        "status": "AUDITABLE_PASS",
        "checklist_pass_count": 35,
        "checklist_total": 35,
        "hash_errors": [],
        "calculation_errors": [],
        "recomputed_adjudication": "PASS",
    }

    # Even prospective replication producing VERIFIED claim status remains strictly SCIENTIFIC
    result = ingest_lpv3_validation_report(mock_report, independent_replicated=True)
    assert result.status == ScientificEvidenceStatus.SCIENTIFICALLY_VERIFIED
    assert result.claim_record.status == EpistemicStatus.VERIFIED
    assert result.claim_record.release_relevance == ReleaseRelevance.SCIENTIFIC

    # Release gate remains blocked if deployed runtime security controls are unverified
    decision = evaluate_release_gate(
        basis=ReleaseDecisionBasis(
            release_id="NCLM1-RG-001",
            artifact_digest="sha256:5678",
            authorization_state=AuthorizationState.NOT_AUTHORIZED,
            s_deployed=DeployedGateStatus.UNVERIFIED,  # Runtime control is UNVERIFIED
            r_deployed=DeployedGateStatus.TRUE,
            prerequisites={
                "locked_artifact": True,
                "preregistration": True,
                "independent_review": True,
            },
            claims_snapshot={"LPV3-HW-001": EpistemicStatus.VERIFIED},
            fixture_may_substitute_for_deployed=False,
        )
    )

    # Even though scientific claim is VERIFIED, deployment remains NOT_AUTHORIZED
    assert decision == AuthorizationState.NOT_AUTHORIZED
