"""Mechanical Adjudication Engine for S_deployed and Master Release Gates."""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Mapping, Optional, Sequence

from .errors import AdjudicationError, SubstitutionViolationError
from .models.claim import EpistemicStatus
from .models.release import (
    AuthorizationState,
    DeployedGateStatus,
    ReleaseDecisionBasis,
)

MANDATORY_CONFINEMENT_CRITERIA = ("A", "B", "C", "D", "E", "F", "G", "H", "I", "J")
REQUIRED_FRESH_RUNS = (1, 2, 3)

MANDATORY_RELEASE_PREREQUISITES = (
    "locked_artifact",
    "preregistration",
    "lineage_pinned",
    "independent_review",
    "adversarial_audit",
    "external_custody",
    "governance_approval",
)


@dataclass(frozen=True)
class ConfinementProbeResult:
    """Individual probe observation for a runtime confinement dimension."""
    criterion: str          # Must be in A..J
    run_index: int          # Must be 1, 2, or 3
    status: str             # "PASS", "FAIL", "BLOCKED", "UNRUN"
    evidence_id: str
    error_message: Optional[str] = None
    observed_errno: Optional[str] = None


def evaluate_s_deployed(
    probe_results: Sequence[ConfinementProbeResult],
    evidence_integrity_verified: bool,
    independent_adjudication_verified: bool,
) -> DeployedGateStatus:
    """Mechanically adjudicates S_deployed according to the tightened formula:
    
    S_deployed = TRUE <=> [Conjunction_{r=1..3} (A_r & ... & J_r)] & K_integrity & L_independent
    
    Adjudication Precedence:
        FALSE > BLOCKED > UNVERIFIED > TRUE
    """
    # 1. Any confirmed violation immediately yields FALSE (precedence 1)
    for probe in probe_results:
        if probe.status == "FAIL":
            return DeployedGateStatus.FALSE

    # 2. Any environmental limitation (e.g. ENOSYS / unshare blocked) yields BLOCKED (precedence 2)
    for probe in probe_results:
        if probe.status == "BLOCKED":
            return DeployedGateStatus.BLOCKED

    # 3. Check for completeness of the 30 required probe observations (10 criteria x 3 runs)
    observed_keys = set()
    for probe in probe_results:
        if probe.status == "PASS":
            observed_keys.add((probe.criterion, probe.run_index))

    for run_idx in REQUIRED_FRESH_RUNS:
        for crit in MANDATORY_CONFINEMENT_CRITERIA:
            if (crit, run_idx) not in observed_keys:
                return DeployedGateStatus.UNVERIFIED

    # 4. Check cryptographic evidence binding (K) and independent review (L)
    if not evidence_integrity_verified or not independent_adjudication_verified:
        return DeployedGateStatus.UNVERIFIED

    # 5. Complete conjunction satisfied
    return DeployedGateStatus.TRUE


def evaluate_release_gate(basis: ReleaseDecisionBasis) -> AuthorizationState:
    """Mechanically evaluates the Master Release Gate.
    
    Invariance Rules:
    1. E_FIXTURE != E_DEPLOYED: fixture evidence cannot satisfy deployed prerequisites.
    2. CLAIM_VERIFICATION != DEPLOYMENT_AUTHORIZATION: scientific claim verification cannot
       substitute for security controls.
    """
    # Hard Non-Substitution Boundary
    if basis.fixture_may_substitute_for_deployed:
        raise SubstitutionViolationError(
            "Boundary breach: fixture_may_substitute_for_deployed=True violates non-substitution invariant."
        )

    # Deployed Confinement Check
    if basis.s_deployed != DeployedGateStatus.TRUE:
        return AuthorizationState.NOT_AUTHORIZED

    # Deployed Lineage Check
    if basis.r_deployed != DeployedGateStatus.TRUE:
        return AuthorizationState.NOT_AUTHORIZED

    # Mandatory Release Prerequisites Check
    for prereq in MANDATORY_RELEASE_PREREQUISITES:
        if not basis.prerequisites.get(prereq, False):
            return AuthorizationState.NOT_AUTHORIZED

    # If all release prerequisites are established, artifact is ELIGIBLE for confirmatory execution
    return AuthorizationState.ELIGIBLE
