"""Typed error hierarchy for OSIRIS Governance control plane."""

from __future__ import annotations


class GovernanceError(Exception):
    """Base exception for all governance control plane errors."""
    pass


class GovernanceViolation(GovernanceError):
    """Base exception for policy, schema, or authorization violations."""
    pass


class SchemaValidationError(GovernanceViolation):
    """Raised when an action proposal fails structural schema validation."""
    pass


class ExecutionBindingMismatch(GovernanceViolation):
    """Raised when proposal canonical bytes do not match the permit's bound hash."""
    pass


class ActionNotPermitted(GovernanceViolation):
    """Raised when an action kind is not permitted by policy."""
    pass


class CapabilityNotPermitted(GovernanceViolation):
    """Raised when a capability is not granted or allowlisted."""
    pass


class ScopeViolation(GovernanceViolation):
    """Raised when a permit or proposal requests unauthorized scope."""
    pass


class ProposalExpired(GovernanceViolation):
    """Raised when a proposal or permit has expired."""
    pass


class EpochMismatch(GovernanceViolation):
    """Raised when a permit's process epoch does not match the active runtime epoch."""
    pass


class NonceReplayDetected(GovernanceViolation):
    """Raised when a nonce replay attempt is detected within the active process epoch."""
    pass


class FixtureNotFoundError(GovernanceError):
    """Raised when an in-memory replay fixture lookup fails."""
    pass
