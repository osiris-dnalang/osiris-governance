"""Release Gate and Authorization models for OSIRIS Deployment Control Plane."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Mapping

from ..canonical import canonical_sha256, canonicalize_json
from .claim import EpistemicStatus


class DeployedGateStatus(str, Enum):
    """Answers: 'Does the deployed execution environment satisfy mandatory criteria?'
    
    Adjudication Precedence:
    FALSE > BLOCKED > UNVERIFIED > TRUE
    """
    TRUE = "TRUE"
    FALSE = "FALSE"
    BLOCKED = "BLOCKED"
    UNVERIFIED = "UNVERIFIED"


class AuthorizationState(str, Enum):
    """Answers: 'Is this specific execution authorized to proceed?'"""
    NOT_AUTHORIZED = "NOT_AUTHORIZED"
    ELIGIBLE = "ELIGIBLE"
    CONFIRMATORY_AUTHORIZED = "CONFIRMATORY_AUTHORIZED"
    EXECUTING = "EXECUTING"
    SUSPENDED = "SUSPENDED"
    COMPLETED = "COMPLETED"


class ExecutionMode(str, Enum):
    """Answers: 'What runtime authority contract is in effect?'
    
    Hard Invariant:
    EXECUTION_MODE IS NOT A CLAIM; EXECUTION_MODE IS AN AUTHORITY CONTRACT.
    DRY_RUN != SIMULATION != SANDBOX != AUTHORIZED.
    """
    DRY_RUN = "DRY_RUN"
    SIMULATION = "SIMULATION"
    SANDBOX = "SANDBOX"
    AUTHORIZED = "AUTHORIZED"


@dataclass(frozen=True)
class ReleaseDecisionBasis:
    """Machine-readable basis for an explicit release decision."""
    release_id: str
    artifact_digest: str
    authorization_state: AuthorizationState
    s_deployed: DeployedGateStatus
    r_deployed: DeployedGateStatus
    prerequisites: Mapping[str, bool]
    claims_snapshot: Mapping[str, EpistemicStatus]
    fixture_may_substitute_for_deployed: bool = False
    evaluated_at_utc: str = ""
    canonical_hash: str = ""

    def canonical_bytes(self) -> bytes:
        data = asdict(self)
        data.pop("canonical_hash", None)
        return canonicalize_json(data)

    def compute_hash(self) -> str:
        return canonical_sha256(self.canonical_bytes())
