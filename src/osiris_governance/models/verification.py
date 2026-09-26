"""Verification models for OSIRIS Verification Registry."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import List, Mapping

from ..canonical import canonical_sha256, canonicalize_json


class VerificationResult(str, Enum):
    """Result of formal adjudication of a claim against evidence packages."""
    VERIFIED = "VERIFIED"
    NOT_VERIFIED = "NOT_VERIFIED"
    FAILED = "FAILED"


@dataclass(frozen=True)
class VerificationRecord:
    """Record linking a claim to its evaluated evidence package and pass/fail criteria."""
    verification_id: str
    claim_id: str
    evidence_ids: List[str]
    criteria_evaluations: Mapping[str, str]
    result: VerificationResult
    adjudicator_id: str
    adjudicated_at_utc: str
    rationale: str
    canonical_hash: str = ""

    def canonical_bytes(self) -> bytes:
        data = asdict(self)
        data.pop("canonical_hash", None)
        return canonicalize_json(data)

    def compute_hash(self) -> str:
        return canonical_sha256(self.canonical_bytes())
