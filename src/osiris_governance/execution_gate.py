"""Execution Authority Gate and State Machine."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Mapping, Optional

from .canonical import canonical_sha256, canonicalize_json
from .errors import AuthorityGateError
from .models.release import (
    AuthorizationState,
    ExecutionMode,
    ReleaseDecisionBasis,
)


@dataclass(frozen=True)
class ExecutionContract:
    """Immutable execution contract frozen at launch.
    
    Invariance:
    EXECUTION_MODE IS NOT A CLAIM; EXECUTION_MODE IS AN AUTHORITY CONTRACT.
    Mode promotion is prohibited after contract initialization.
    """
    execution_id: str
    target_artifact_digest: str
    mode: ExecutionMode
    frozen_at_utc: str
    parameters: Mapping[str, Any] = field(default_factory=dict)
    signed_permit_nonce: Optional[str] = None
    canonical_hash: str = ""

    def canonical_bytes(self) -> bytes:
        data = asdict(self)
        data.pop("canonical_hash", None)
        return canonicalize_json(data)

    def compute_hash(self) -> str:
        return canonical_sha256(self.canonical_bytes())


class ExecutionGate:
    """Evaluates admission gates for proposed execution contracts."""

    @staticmethod
    def admit_execution(
        contract: ExecutionContract,
        release_basis: Optional[ReleaseDecisionBasis] = None,
    ) -> ExecutionMode:
        """Evaluates whether the requested execution mode is authorized to proceed.
        
        Fail-Closed Policy: Any unmet prerequisite raises AuthorityGateError.
        """
        # DRY_RUN: Always permitted for deterministic, non-side-effecting analysis
        if contract.mode == ExecutionMode.DRY_RUN:
            return ExecutionMode.DRY_RUN

        # SIMULATION: Permitted if parameters do not require physical hardware
        if contract.mode == ExecutionMode.SIMULATION:
            if contract.parameters.get("require_physical_hardware", False):
                raise AuthorityGateError("Physical hardware execution requested under SIMULATION mode.")
            return ExecutionMode.SIMULATION

        # SANDBOX: Requires verified isolation configuration
        if contract.mode == ExecutionMode.SANDBOX:
            if not contract.parameters.get("sandbox_initialized", False):
                raise AuthorityGateError("Sandbox environment is not initialized or verified.")
            return ExecutionMode.SANDBOX

        # AUTHORIZED: Requires ELIGIBLE release decision and explicit signed permit nonce
        if contract.mode == ExecutionMode.AUTHORIZED:
            if release_basis is None:
                raise AuthorityGateError("Release decision basis is missing for AUTHORIZED execution.")
            if release_basis.authorization_state != AuthorizationState.ELIGIBLE:
                raise AuthorityGateError(
                    f"Release gate state is {release_basis.authorization_state}; must be ELIGIBLE."
                )
            if not contract.signed_permit_nonce:
                raise AuthorityGateError("Signed permit nonce is required for AUTHORIZED execution.")
            return ExecutionMode.AUTHORIZED

        raise AuthorityGateError(f"Unknown or unhandled execution mode: {contract.mode}")
