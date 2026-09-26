"""Epistemic claim models for OSIRIS Claim Registry."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import List, Optional

from ..canonical import canonical_sha256, canonicalize_json


class EpistemicStatus(str, Enum):
    """Answers: 'What do we know about this claim?'
    
    This describes epistemic status ONLY.
    Invariance: VERIFIED never equals authorized.
    """
    DECLARED = "DECLARED"
    IMPLEMENTED = "IMPLEMENTED"
    TESTED = "TESTED"
    MEASURED = "MEASURED"
    REPRODUCED = "REPRODUCED"
    VERIFIED = "VERIFIED"
    SIMULATED = "SIMULATED"
    HYPOTHESIS = "HYPOTHESIS"
    REFUTED = "REFUTED"


class ReleaseRelevance(str, Enum):
    """Categorizes the claim's impact on release and deployment."""
    INFORMATIONAL = "INFORMATIONAL"
    SCIENTIFIC = "SCIENTIFIC"
    SECURITY = "SECURITY"
    RELEASE_CRITICAL = "RELEASE_CRITICAL"


@dataclass(frozen=True)
class ClaimRecord:
    """Universal Claim Object representing an explicit scientific, operational, or security assertion."""
    claim_id: str
    subject: str
    statement: str
    status: EpistemicStatus
    release_relevance: ReleaseRelevance
    release_control: Optional[str] = None
    authorization_effect: Optional[str] = None
    evidence_refs: List[str] = field(default_factory=list)
    limitations: List[str] = field(default_factory=list)
    canonical_hash: str = ""

    def canonical_bytes(self) -> bytes:
        data = asdict(self)
        data.pop("canonical_hash", None)
        return canonicalize_json(data)

    def compute_hash(self) -> str:
        return canonical_sha256(self.canonical_bytes())
