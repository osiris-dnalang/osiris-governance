"""OSIRIS Governance: Deterministic Control Plane and Capability Governor."""

from .canonical import (
    CANONICALIZATION_VERSION,
    canonical_sha256,
    canonicalize_json,
)
from .contracts import (
    DEFAULT_ISSUER,
    DEFAULT_POLICY_VERSION,
    REPLAY_ACTION_KIND,
    REPLAY_CAPABILITY,
    REPLAY_SCOPE,
    ActionProposal,
    ReplayExecutionPermit,
    ReplayResultRecord,
)
from .errors import (
    ActionNotPermitted,
    CapabilityNotPermitted,
    EpochMismatch,
    ExecutionBindingMismatch,
    FixtureNotFoundError,
    GovernanceError,
    GovernanceViolation,
    NonceReplayDetected,
    ProposalExpired,
    SchemaValidationError,
    ScopeViolation,
)
from .governor import CapabilityGovernor
from .replay import ReplayAdapter

__version__ = "0.1.0"

__all__ = [
    "CANONICALIZATION_VERSION",
    "canonical_sha256",
    "canonicalize_json",
    "DEFAULT_ISSUER",
    "DEFAULT_POLICY_VERSION",
    "REPLAY_ACTION_KIND",
    "REPLAY_CAPABILITY",
    "REPLAY_SCOPE",
    "ActionProposal",
    "ReplayExecutionPermit",
    "ReplayResultRecord",
    "CapabilityGovernor",
    "ReplayAdapter",
    "GovernanceError",
    "GovernanceViolation",
    "SchemaValidationError",
    "ExecutionBindingMismatch",
    "ActionNotPermitted",
    "CapabilityNotPermitted",
    "ScopeViolation",
    "ProposalExpired",
    "EpochMismatch",
    "NonceReplayDetected",
    "FixtureNotFoundError",
]
