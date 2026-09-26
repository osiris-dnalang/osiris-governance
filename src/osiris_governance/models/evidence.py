"""Immutable Evidence models for OSIRIS Evidence Registry."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, List, Mapping, Optional

from ..canonical import canonical_sha256, canonicalize_json


class EvidenceClass(str, Enum):
    """Answers: 'What nature of evidence is this?'"""
    MEASURED = "MEASURED"
    SIMULATED = "SIMULATED"
    DERIVED = "DERIVED"
    DECLARED = "DECLARED"
    HYPOTHESIS = "HYPOTHESIS"


class EvidenceDomain(str, Enum):
    """Answers: 'In which evidentiary boundary was this captured?'
    
    Hard Invariants:
    E_FIXTURE != E_DEPLOYED
    E_SIMULATION != E_HARDWARE
    """
    E_FIXTURE = "E_FIXTURE"
    E_DEPLOYED = "E_DEPLOYED"
    E_EXTERNAL = "E_EXTERNAL"
    E_CUSTODY = "E_CUSTODY"


@dataclass(frozen=True)
class EvidenceRecord:
    """Immutable evidence record forming the verifiable spine of all claims and gate terms."""
    evidence_id: str
    evidence_class: EvidenceClass
    domain: EvidenceDomain
    claim_ids: List[str]
    artifact_digest: str
    environment_digest: str
    raw_payload_digest: str
    captured_at_utc: str
    immutable: bool = True
    superseded_by: Optional[str] = None
    manifest: Mapping[str, Any] = field(default_factory=dict)
    canonical_hash: str = ""

    def canonical_bytes(self) -> bytes:
        data = asdict(self)
        data.pop("canonical_hash", None)
        return canonicalize_json(data)

    def compute_hash(self) -> str:
        return canonical_sha256(self.canonical_bytes())
