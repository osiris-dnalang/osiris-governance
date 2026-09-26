"""Sandbox Confinement Attestation Subsystem (Evidence Classes S1 through S5)."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Mapping, Optional

from .canonical import canonical_sha256, canonicalize_json
from .errors import ConfinementViolationError


class AttestationLevel(str, Enum):
    LEVEL_0_DECLARED = "LEVEL_0_DECLARED"                    # Configured intent only
    LEVEL_1_OBSERVED = "LEVEL_1_OBSERVED"                    # Measured by host monitor during execution
    LEVEL_2_INDEPENDENTLY_ATTESTED = "LEVEL_2_INDEPENDENTLY_ATTESTED"  # External observer signed evidence


@dataclass(frozen=True)
class S1ArtifactIdentity:
    """Class S1: Artifact Identity Evidence."""
    container_image_digest: str
    worker_binary_digest: str
    policy_digest: str
    status: str = "PASS"


@dataclass(frozen=True)
class S2RuntimeIdentity:
    """Class S2: Runtime and Kernel Identity Evidence."""
    kernel_version: str
    seccomp_profile_digest: str
    effective_uid: int
    effective_gid: int
    caps_empty: bool
    status: str = "PASS"


@dataclass(frozen=True)
class S3IsolationObservations:
    """Class S3: Runtime Isolation Observations during Execution Interval."""
    host_sentinel_touches: int = 0
    network_egress_frames: int = 0
    dns_queries: int = 0
    host_pids_visible: int = 0
    unauthorized_secrets_accessed: int = 0
    undeclared_open_fds: int = 0
    status: str = "PASS"


@dataclass(frozen=True)
class S4ExecutionTrace:
    """Class S4: Immutable Execution Trace."""
    start_time_monotonic: float
    end_time_monotonic: float
    exit_code: int
    trace_digest: str
    status: str = "PASS"


@dataclass(frozen=True)
class S5EvidenceIntegrity:
    """Class S5: Evidence Integrity and Binding."""
    manifest_digest: str
    audit_log_digest: str
    pcap_digest: Optional[str] = None
    status: str = "PASS"


@dataclass(frozen=True)
class SandboxAttestationRecord:
    """Complete 5-Class Sandbox Attestation Record."""
    execution_id: str
    level: AttestationLevel
    s1_artifact: S1ArtifactIdentity
    s2_runtime: S2RuntimeIdentity
    s3_isolation: S3IsolationObservations
    s4_trace: S4ExecutionTrace
    s5_integrity: S5EvidenceIntegrity
    verdict: str = "PENDING"
    canonical_hash: str = ""

    def evaluate_verdict(self) -> str:
        """Evaluates whether all 5 evidence classes pass confinement."""
        if any(
            section.status != "PASS"
            for section in (
                self.s1_artifact,
                self.s2_runtime,
                self.s3_isolation,
                self.s4_trace,
                self.s5_integrity,
            )
        ):
            return "CONFINEMENT_FAILED"
        if (
            self.s3_isolation.host_sentinel_touches > 0
            or self.s3_isolation.network_egress_frames > 0
            or self.s3_isolation.dns_queries > 0
            or self.s3_isolation.host_pids_visible > 0
            or self.s3_isolation.unauthorized_secrets_accessed > 0
            or self.s3_isolation.undeclared_open_fds > 0
        ):
            return "CONFINEMENT_BREACH"
        return "CONFINEMENT_VERIFIED"

    def canonical_bytes(self) -> bytes:
        data = asdict(self)
        data.pop("canonical_hash", None)
        return canonicalize_json(data)

    def compute_hash(self) -> str:
        return canonical_sha256(self.canonical_bytes())
