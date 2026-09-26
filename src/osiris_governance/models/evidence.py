"""Immutable Evidence models for OSIRIS Evidence Registry."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, List, Mapping, Optional

from ..canonical import canonical_sha256, canonicalize_json


class EvidencePlane(str, Enum):
    """Answers: 'Which authority and verification plane governs this evidence?'"""
    OPERATIONAL = "OPERATIONAL"
    SCIENTIFIC = "SCIENTIFIC"
    PROVENANCE = "PROVENANCE"
    GOVERNANCE = "GOVERNANCE"


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
    evidence_plane: EvidencePlane = EvidencePlane.OPERATIONAL
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


@dataclass(frozen=True)
class RuntimeProbeReceipt:
    """Operational evidence object for confinement and runtime environment probes."""
    receipt_id: str
    object_type: str = "RUNTIME_PROBE_RECEIPT"
    evidence_plane: EvidencePlane = EvidencePlane.OPERATIONAL
    criterion: str = ""
    status: str = "PASS"
    error_message: Optional[str] = None
    scope: Mapping[str, Any] = field(default_factory=dict)
    captured_at_utc: str = ""

    def canonical_bytes(self) -> bytes:
        return canonicalize_json(asdict(self))

    def compute_hash(self) -> str:
        return canonical_sha256(self.canonical_bytes())


@dataclass(frozen=True)
class RawExperimentalDataReceipt:
    """Scientific evidence object for experimental and classical simulation datasets."""
    receipt_id: str
    object_type: str = "RAW_EXPERIMENTAL_DATA_RECEIPT"
    evidence_plane: EvidencePlane = EvidencePlane.SCIENTIFIC
    dataset_digest: str = ""
    protocol_ref: str = ""
    experiment_id: str = ""
    scope: Mapping[str, Any] = field(default_factory=dict)
    captured_at_utc: str = ""

    def canonical_bytes(self) -> bytes:
        return canonicalize_json(asdict(self))

    def compute_hash(self) -> str:
        return canonical_sha256(self.canonical_bytes())


@dataclass(frozen=True)
class HardwareProviderReceipt:
    """Scientific evidence object specifically for physical quantum hardware execution.
    
    Hard Invariant:
    A HardwareProviderReceipt establishes hardware execution, NOT deployment attestation.
    """
    receipt_id: str
    object_type: str = "HARDWARE_PROVIDER_RECEIPT"
    evidence_plane: EvidencePlane = EvidencePlane.SCIENTIFIC
    execution_domain: str = "QUANTUM_HARDWARE"
    provider: str = "IBM_QUANTUM"
    backend: str = ""
    job_id: str = ""
    calibration_hash: str = ""
    raw_counts_digest: str = ""
    scope: Mapping[str, Any] = field(default_factory=dict)
    captured_at_utc: str = ""

    def canonical_bytes(self) -> bytes:
        return canonicalize_json(asdict(self))

    def compute_hash(self) -> str:
        return canonical_sha256(self.canonical_bytes())


@dataclass(frozen=True)
class CrossPlaneProvenanceRecord:
    """Cross-plane evidence linking operational artifacts to scientific experiments without substitution."""
    record_id: str
    object_type: str = "CROSS_PLANE_PROVENANCE_RECORD"
    evidence_plane: EvidencePlane = EvidencePlane.PROVENANCE
    provenance_only: bool = True
    operational_root: str = ""
    scientific_root: str = ""
    shared_artifact_digest: str = ""
    git_commit_sha: str = ""
    relationship: str = "SCIENTIFIC_PACKAGE_REFERENCES_ARTIFACT"
    substitution_scientific_for_operational: bool = False
    substitution_operational_for_scientific: bool = False
    created_at_utc: str = ""

    def canonical_bytes(self) -> bytes:
        return canonicalize_json(asdict(self))

    def compute_hash(self) -> str:
        return canonical_sha256(self.canonical_bytes())
