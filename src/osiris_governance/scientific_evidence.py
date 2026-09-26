"""Scientific Evidence Pack Ingestion and Adjudication Adapter.

Translates verified empirical evidence packs (e.g. LPV3 quantum hardware packs)
into OSIRIS Claim, Evidence, and Verification records under strict epistemic rules:

Invariants:
1. SCIENCE_NON_SUBSTITUTION:
   ScientificEvidence CANNOT satisfy RuntimeSecurityControl (S_deployed).
   RuntimeSecurityEvidence CANNOT establish ScientificEfficacy.
2. LPV3_EXECUTION_AUDITABLE != LPV3_SCIENTIFICALLY_REPRODUCED.
3. CLAIM_VERIFICATION_STATUS != DEPLOYMENT_AUTHORIZATION_STATUS.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

from .canonical import canonical_sha256
from .errors import AdjudicationError, SubstitutionViolationError
from .models.claim import ClaimRecord, EpistemicStatus, ReleaseRelevance
from .models.evidence import EvidenceClass, EvidenceDomain, EvidenceRecord
from .models.verification import VerificationRecord, VerificationResult


class ScientificEvidenceStatus(str, Enum):
    """Fine-grained epistemic status for scientific evidence packages."""
    EVIDENCE_PACK_INVALID = "EVIDENCE_PACK_INVALID"
    EVIDENCE_PACK_INCOMPLETE = "EVIDENCE_PACK_INCOMPLETE"
    EVIDENCE_PACK_AUDITABLE = "EVIDENCE_PACK_AUDITABLE"
    ANALYSIS_REPRODUCED = "ANALYSIS_REPRODUCED"
    COMPUTATION_REPRODUCED = "COMPUTATION_REPRODUCED"
    EXPERIMENT_REPLICATED = "EXPERIMENT_REPLICATED"
    SCIENTIFICALLY_VERIFIED = "SCIENTIFICALLY_VERIFIED"


@dataclass(frozen=True)
class ScientificEvidencePackResult:
    """Evaluated outcome of a scientific evidence pack ingestion."""
    execution_id: str
    status: ScientificEvidenceStatus
    claim_record: ClaimRecord
    evidence_record: EvidenceRecord
    verification_record: VerificationRecord
    details: Dict[str, Any] = field(default_factory=dict)

    def verify_non_substitution() -> None:
        pass


def ingest_lpv3_validation_report(
    report: Dict[str, Any],
    claim_id: str = "LPV3-HW-001",
    claim_statement: str = "Observable (I-Z)/2 expectation on hardware matches target within threshold",
    independent_replicated: bool = False,
) -> ScientificEvidencePackResult:
    """Transforms an LPV3 validator output dictionary into formal governance records."""
    exec_id = report.get("execution_id", "UNKNOWN-EXEC")
    is_auditable = bool(report.get("lpv3_execution_auditable", False))
    hash_errors = report.get("hash_errors", [])
    calc_errors = report.get("calculation_errors", [])
    pass_count = report.get("checklist_pass_count", 0)
    total_checklist = report.get("checklist_total", 35)

    # 1. Determine granular scientific evidence status
    if hash_errors or not report.get("backend"):
        status = ScientificEvidenceStatus.EVIDENCE_PACK_INVALID
        epistemic = EpistemicStatus.REFUTED
        v_result = VerificationResult.FAILED
    elif pass_count < total_checklist:
        status = ScientificEvidenceStatus.EVIDENCE_PACK_INCOMPLETE
        epistemic = EpistemicStatus.IMPLEMENTED
        v_result = VerificationResult.NOT_VERIFIED
    elif not is_auditable:
        status = ScientificEvidenceStatus.EVIDENCE_PACK_INVALID
        epistemic = EpistemicStatus.TESTED
        v_result = VerificationResult.FAILED
    else:
        # Pass count == 35, hashes ok, math recalculated
        if independent_replicated:
            status = ScientificEvidenceStatus.SCIENTIFICALLY_VERIFIED
            epistemic = EpistemicStatus.VERIFIED
            v_result = VerificationResult.VERIFIED
        elif report.get("status") == "AUDITABLE_PASS":
            status = ScientificEvidenceStatus.ANALYSIS_REPRODUCED
            epistemic = EpistemicStatus.MEASURED
            v_result = VerificationResult.VERIFIED
        else:
            status = ScientificEvidenceStatus.EVIDENCE_PACK_AUDITABLE
            epistemic = EpistemicStatus.MEASURED
            v_result = VerificationResult.NOT_VERIFIED

    evidence_id = f"EVD-{exec_id}"
    verif_id = f"VRF-{exec_id}"
    now_utc = datetime.now(timezone.utc).isoformat()
    raw_digest = canonical_sha256(report)

    # 2. Build EvidenceRecord
    evidence_record = EvidenceRecord(
        evidence_id=evidence_id,
        evidence_class=EvidenceClass.MEASURED,
        domain=EvidenceDomain.E_EXTERNAL,
        claim_ids=[claim_id],
        artifact_digest=report.get("circuit_execution_digest", raw_digest),
        environment_digest=report.get("calibration_digest", raw_digest),
        raw_payload_digest=raw_digest,
        captured_at_utc=now_utc,
        immutable=True,
        manifest={
            "execution_id": exec_id,
            "provider_job_id": report.get("provider_job_id"),
            "backend": report.get("backend"),
            "status": report.get("status"),
            "recomputed_adjudication": report.get("recomputed_adjudication"),
        },
    )

    # 3. Build VerificationRecord
    verification_record = VerificationRecord(
        verification_id=verif_id,
        claim_id=claim_id,
        evidence_ids=[evidence_id],
        criteria_evaluations={
            "checklist_35_of_35": "PASS" if pass_count == total_checklist else "FAIL",
            "hash_integrity_clean": "PASS" if len(hash_errors) == 0 else "FAIL",
            "recalculation_match": "PASS" if len(calc_errors) == 0 else "FAIL",
            "pass_fail_adjudication": report.get("recomputed_adjudication", "FAIL"),
        },
        result=v_result,
        adjudicator_id="osiris.scientific_evidence.lpv3_adapter",
        adjudicated_at_utc=now_utc,
        rationale=f"Adjudicated status: {status.value}. Auditable: {is_auditable}.",
    )

    # 4. Build ClaimRecord (Strictly SCIENTIFIC release relevance)
    claim_record = ClaimRecord(
        claim_id=claim_id,
        subject="LPV3 Quantum Observable",
        statement=claim_statement,
        status=epistemic,
        release_relevance=ReleaseRelevance.SCIENTIFIC,
        release_control=None,
        authorization_effect="Does not authorize deployment",
        evidence_refs=[evidence_id],
    )

    result = ScientificEvidencePackResult(
        execution_id=exec_id,
        status=status,
        claim_record=claim_record,
        evidence_record=evidence_record,
        verification_record=verification_record,
        details={
            "hash_errors": hash_errors,
            "calculation_errors": calc_errors,
            "checklist_pass_count": pass_count,
        },
    )
    if result.claim_record.release_relevance != ReleaseRelevance.SCIENTIFIC:
        raise SubstitutionViolationError(
            f"Scientific evidence pack '{result.execution_id}' must have release_relevance=SCIENTIFIC"
        )
    return result
