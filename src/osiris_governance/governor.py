"""Deterministic CapabilityGovernor enforcing pre-adapter authorization boundaries."""

from __future__ import annotations

from datetime import datetime, timezone
import json
from typing import Any
import uuid

from .canonical import CANONICALIZATION_VERSION, _validate_types_recursive, canonical_sha256
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
    NonceReplayDetected,
    ProposalExpired,
    SchemaValidationError,
    ScopeViolation,
)
from .replay import ReplayAdapter


def _parse_iso_utc(timestamp_str: str) -> datetime:
    """Parses ISO 8601 string into timezone-aware UTC datetime."""
    try:
        dt = datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            return dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except Exception as exc:
        raise SchemaValidationError(f"Invalid ISO 8601 UTC timestamp '{timestamp_str}': {exc}") from exc


class CapabilityGovernor:
    """Central deterministic governor mediating execution authority.
    
    MECHANICAL PRE-ADAPTER EVALUATION GUARANTEE:
    This governor verifies deserialization, schema, canonical hash binding, capability,
    scope, expiry, epoch, and nonce BEFORE any call to an adapter can occur.
    """

    def __init__(
        self,
        process_epoch_id: str | None = None,
        policy_version: str = DEFAULT_POLICY_VERSION,
    ) -> None:
        self._process_epoch_id = process_epoch_id or f"epoch_{uuid.uuid4().hex[:16]}"
        self._policy_version = policy_version
        self._used_nonces: set[str] = set()

    @property
    def process_epoch_id(self) -> str:
        """Active process epoch identifier."""
        return self._process_epoch_id

    @property
    def used_nonces_count(self) -> int:
        """Number of nonces consumed during this process epoch."""
        return len(self._used_nonces)

    def issue_replay_permit(
        self,
        proposal: ActionProposal,
        now: datetime | None = None,
    ) -> ReplayExecutionPermit:
        """Constructs a deterministic, non-authoritative permit bound to a proposal."""
        current_time = now or datetime.now(timezone.utc)
        issued_at_utc = current_time.isoformat()

        return ReplayExecutionPermit(
            proposal_sha256=proposal.proposal_sha256(),
            canonicalization_version=CANONICALIZATION_VERSION,
            policy_version=self._policy_version,
            fixture_id=proposal.fixture_id,
            nonce=proposal.nonce,
            process_epoch_id=self._process_epoch_id,
            issued_at_utc=issued_at_utc,
            expires_at_utc=proposal.expires_at_utc,
            scope=REPLAY_SCOPE,
            issuer=DEFAULT_ISSUER,
        )

    def submit(
        self,
        proposal_bytes: bytes,
        permit: ReplayExecutionPermit,
        adapter: ReplayAdapter,
        now: datetime | None = None,
    ) -> ReplayResultRecord:
        """Evaluates proposal bytes against permit and dispatches to adapter if and only if valid.
        
        Mechanical evaluation sequence:
        1. Deserialization & structural schema validation
        2. Canonical SHA-256 computation over exact input bytes
        3. Proposal SHA-256 == permit.proposal_sha256
        4. Fixture ID binding
        5. ActionKind == REPLAY_FIXTURE
        6. Capability == REPLAY
        7. Scope == REPLAY_ONLY_NON_CRYPTOGRAPHIC
        8. Canonicalization version match
        9. Expiry checks (now < expires_at_utc)
        10. Process epoch verification
        11. In-epoch nonce deduplication
        12. Record nonce in epoch registry
        13. ONLY NOW -> adapter.execute(...)
        """
        current_time = now or datetime.now(timezone.utc)

        # 1. Deserialization & structural validation
        if not isinstance(proposal_bytes, bytes):
            raise SchemaValidationError("Proposal payload must be bytes")

        try:
            raw_text = proposal_bytes.decode("utf-8")
            parsed: dict[str, Any] = json.loads(raw_text)
        except Exception as exc:
            raise SchemaValidationError(f"Invalid proposal JSON: {exc}") from exc

        if not isinstance(parsed, dict):
            raise SchemaValidationError("Proposal root must be a JSON mapping")

        # Validate against canonical forbidden types (e.g. floats)
        _validate_types_recursive(parsed)

        required_fields = (
            "proposal_id",
            "request_id",
            "proposer_id",
            "action_kind",
            "capability",
            "fixture_id",
            "arguments",
            "nonce",
            "created_at_utc",
            "expires_at_utc",
        )
        for field in required_fields:
            if field not in parsed:
                raise SchemaValidationError(f"Missing required proposal field: '{field}'")

        # 2. Canonical SHA-256 calculation over exact proposal bytes
        computed_sha256 = canonical_sha256(proposal_bytes)

        # 3. Execution binding comparison
        if computed_sha256 != permit.proposal_sha256:
            raise ExecutionBindingMismatch(
                f"Proposal hash mismatch: computed '{computed_sha256}' != bound '{permit.proposal_sha256}'"
            )

        # 4. Fixture ID binding
        if parsed["fixture_id"] != permit.fixture_id:
            raise ExecutionBindingMismatch(
                f"Fixture ID mismatch: proposal '{parsed['fixture_id']}' != permit '{permit.fixture_id}'"
            )

        # 5. ActionKind check
        if parsed["action_kind"] != REPLAY_ACTION_KIND:
            raise ActionNotPermitted(
                f"Action '{parsed['action_kind']}' is not permitted in replay slice (must be '{REPLAY_ACTION_KIND}')"
            )

        # 6. Capability check
        if parsed["capability"] != REPLAY_CAPABILITY:
            raise CapabilityNotPermitted(
                f"Capability '{parsed['capability']}' is not permitted in replay slice (must be '{REPLAY_CAPABILITY}')"
            )

        # 7. Scope verification
        if permit.scope != REPLAY_SCOPE:
            raise ScopeViolation(
                f"Unauthorized permit scope '{permit.scope}' (must be '{REPLAY_SCOPE}')"
            )

        # 8. Canonicalization version match
        if permit.canonicalization_version != CANONICALIZATION_VERSION:
            raise SchemaValidationError(
                f"Unsupported canonicalization version '{permit.canonicalization_version}'"
            )

        # 9. Expiry checks
        permit_expires = _parse_iso_utc(permit.expires_at_utc)
        proposal_expires = _parse_iso_utc(parsed["expires_at_utc"])

        if current_time >= permit_expires:
            raise ProposalExpired(f"Replay permit expired at '{permit.expires_at_utc}' (current: '{current_time.isoformat()}')")
        if current_time >= proposal_expires:
            raise ProposalExpired(f"Proposal expired at '{parsed['expires_at_utc']}' (current: '{current_time.isoformat()}')")

        # 10. Process epoch verification
        if permit.process_epoch_id != self._process_epoch_id:
            raise EpochMismatch(
                f"Epoch mismatch: permit '{permit.process_epoch_id}' != active '{self._process_epoch_id}'"
            )

        # 11. In-epoch nonce freshness check
        if permit.nonce in self._used_nonces:
            raise NonceReplayDetected(f"Nonce '{permit.nonce}' has already been consumed in epoch '{self._process_epoch_id}'")
        if parsed["nonce"] != permit.nonce:
            raise ExecutionBindingMismatch(
                f"Nonce mismatch: proposal '{parsed['nonce']}' != permit '{permit.nonce}'"
            )

        # 12. Record nonce
        self._used_nonces.add(permit.nonce)

        # 13. ONLY NOW: dispatch to in-memory ReplayAdapter
        payload = adapter.execute(proposal_bytes, permit.fixture_id)

        # 14. Construct normalized immutable result record
        return ReplayResultRecord(
            status="REPLAYED",
            proposal_sha256=computed_sha256,
            fixture_id=permit.fixture_id,
            permit_nonce=permit.nonce,
            process_epoch_id=self._process_epoch_id,
            payload=payload,
            executed_at_utc=current_time.isoformat(),
        )
