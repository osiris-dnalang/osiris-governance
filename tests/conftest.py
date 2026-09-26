"""Shared test fixtures for osiris_governance."""

from datetime import datetime, timedelta, timezone
import pytest

from osiris_governance.contracts import (
    REPLAY_ACTION_KIND,
    REPLAY_CAPABILITY,
    ActionProposal,
)
from osiris_governance.governor import CapabilityGovernor
from osiris_governance.replay import ReplayAdapter


@pytest.fixture
def fixed_now() -> datetime:
    return datetime(2026, 9, 26, 12, 0, 0, tzinfo=timezone.utc)


@pytest.fixture
def fixed_epoch() -> str:
    return "epoch_test_fixed_123"


@pytest.fixture
def valid_fixture_payload() -> dict:
    return {
        "status": "COMPUTATION_SUCCESS",
        "output_tokens": 42,
        "result_data": {"energy_level": 420, "converged": True},
    }


@pytest.fixture
def valid_proposal(fixed_now: datetime) -> ActionProposal:
    return ActionProposal(
        proposal_id="prop-001",
        request_id="req-001",
        proposer_id="agent-proposer-alpha",
        action_kind=REPLAY_ACTION_KIND,
        capability=REPLAY_CAPABILITY,
        fixture_id="fixture-energy-test-v1",
        arguments={"algorithm": "vqe", "iterations": 100, "qubits": 4},
        nonce="nonce-unique-001",
        created_at_utc=fixed_now.isoformat(),
        expires_at_utc=(fixed_now + timedelta(seconds=300)).isoformat(),
        schema_version="action-proposal/v1",
    )


@pytest.fixture
def adapter(valid_fixture_payload: dict) -> ReplayAdapter:
    adp = ReplayAdapter()
    adp.register_fixture("fixture-energy-test-v1", valid_fixture_payload)
    return adp


@pytest.fixture
def governor(fixed_epoch: str) -> CapabilityGovernor:
    return CapabilityGovernor(process_epoch_id=fixed_epoch)
