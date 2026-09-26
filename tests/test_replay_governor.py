"""Deterministic 13-point security and authority invariant suite for CapabilityGovernor."""

import ast
from dataclasses import replace
from datetime import timedelta
from pathlib import Path
from unittest.mock import MagicMock
import pytest

from osiris_governance.contracts import (
    REPLAY_ACTION_KIND,
    REPLAY_CAPABILITY,
    REPLAY_SCOPE,
    ActionProposal,
)
from osiris_governance.errors import (
    ActionNotPermitted,
    CapabilityNotPermitted,
    EpochMismatch,
    ExecutionBindingMismatch,
    FixtureNotFoundError,
    GovernanceViolation,
    NonceReplayDetected,
    ProposalExpired,
    ScopeViolation,
)
from osiris_governance.governor import CapabilityGovernor
from osiris_governance.replay import ReplayAdapter


def test_inv_01_exact_proposal_executes(governor, adapter, valid_proposal, fixed_now):
    """INV-01: Valid canonical bytes bound to a permit execute deterministically."""
    permit = governor.issue_replay_permit(valid_proposal, now=fixed_now)
    proposal_bytes = valid_proposal.canonical_bytes()

    result = governor.submit(proposal_bytes, permit, adapter, now=fixed_now)

    assert result.status == "REPLAYED"
    assert result.proposal_sha256 == valid_proposal.proposal_sha256()
    assert result.fixture_id == valid_proposal.fixture_id
    assert result.permit_nonce == valid_proposal.nonce
    assert result.payload["status"] == "COMPUTATION_SUCCESS"
    assert result.payload["result_data"]["energy_level"] == 420


def test_inv_02_changed_operation_rejected(governor, adapter, valid_proposal, fixed_now):
    """INV-02: Proposal requesting non-replay action kind is rejected fail-closed."""
    bad_proposal = replace(valid_proposal, action_kind="SYSTEM_COMMAND_EXECUTION")
    permit = governor.issue_replay_permit(bad_proposal, now=fixed_now)
    proposal_bytes = bad_proposal.canonical_bytes()

    with pytest.raises(ActionNotPermitted, match="must be 'REPLAY_FIXTURE'"):
        governor.submit(proposal_bytes, permit, adapter, now=fixed_now)


def test_inv_03_changed_scope_rejected(governor, adapter, valid_proposal, fixed_now):
    """INV-03: Permit requesting unauthorized scope is rejected fail-closed."""
    valid_permit = governor.issue_replay_permit(valid_proposal, now=fixed_now)
    tampered_permit = replace(valid_permit, scope="UNRESTRICTED_ROOT_AUTHORITY")
    proposal_bytes = valid_proposal.canonical_bytes()

    with pytest.raises(ScopeViolation, match="Unauthorized permit scope"):
        governor.submit(proposal_bytes, tampered_permit, adapter, now=fixed_now)


def test_inv_04_changed_argument_rejected(governor, adapter, valid_proposal, fixed_now):
    """INV-04: Altered argument value causes an execution binding mismatch."""
    permit = governor.issue_replay_permit(valid_proposal, now=fixed_now)
    # Propose with iterations=999 instead of 100
    tampered_proposal = replace(
        valid_proposal,
        arguments={"algorithm": "vqe", "iterations": 999, "qubits": 4},
    )
    proposal_bytes = tampered_proposal.canonical_bytes()

    with pytest.raises(ExecutionBindingMismatch, match="Proposal hash mismatch"):
        governor.submit(proposal_bytes, permit, adapter, now=fixed_now)


def test_inv_05_added_argument_rejected(governor, adapter, valid_proposal, fixed_now):
    """INV-05: Injected unexpected argument key causes an execution binding mismatch."""
    permit = governor.issue_replay_permit(valid_proposal, now=fixed_now)
    tampered_args = dict(valid_proposal.arguments)
    tampered_args["injected_backdoor_param"] = 1
    tampered_proposal = replace(valid_proposal, arguments=tampered_args)
    proposal_bytes = tampered_proposal.canonical_bytes()

    with pytest.raises(ExecutionBindingMismatch, match="Proposal hash mismatch"):
        governor.submit(proposal_bytes, permit, adapter, now=fixed_now)


def test_inv_06_removed_argument_rejected(governor, adapter, valid_proposal, fixed_now):
    """INV-06: Stripped argument key causes an execution binding mismatch."""
    permit = governor.issue_replay_permit(valid_proposal, now=fixed_now)
    tampered_proposal = replace(
        valid_proposal,
        arguments={"algorithm": "vqe", "qubits": 4},  # missing iterations
    )
    proposal_bytes = tampered_proposal.canonical_bytes()

    with pytest.raises(ExecutionBindingMismatch, match="Proposal hash mismatch"):
        governor.submit(proposal_bytes, permit, adapter, now=fixed_now)


def test_inv_07_changed_capability_rejected(governor, adapter, valid_proposal, fixed_now):
    """INV-07: Ungranted capability is rejected before execution."""
    bad_proposal = replace(valid_proposal, capability="SHELL_EXECUTION")
    permit = governor.issue_replay_permit(bad_proposal, now=fixed_now)
    proposal_bytes = bad_proposal.canonical_bytes()

    with pytest.raises(CapabilityNotPermitted, match="must be 'REPLAY'"):
        governor.submit(proposal_bytes, permit, adapter, now=fixed_now)


def test_inv_08_changed_canonical_bytes_rejected(governor, adapter, valid_proposal, fixed_now):
    """INV-08: Even a single flipped byte in the raw serialized payload fails binding."""
    permit = governor.issue_replay_permit(valid_proposal, now=fixed_now)
    original_bytes = valid_proposal.canonical_bytes()

    # Flip the last byte from } to something else or alter a character
    tampered_bytes = original_bytes.replace(b'"vqe"', b'"vqx"')

    with pytest.raises(ExecutionBindingMismatch, match="Proposal hash mismatch"):
        governor.submit(tampered_bytes, permit, adapter, now=fixed_now)


def test_inv_09_pre_adapter_denial_guarantee(governor, valid_proposal, fixed_now):
    """INV-09: Adapter is NEVER invoked when a proposal or permit is denied."""
    permit = governor.issue_replay_permit(valid_proposal, now=fixed_now)
    tampered_bytes = valid_proposal.canonical_bytes().replace(b'"vqe"', b'"vqx"')

    mock_adapter = MagicMock(spec=ReplayAdapter)

    with pytest.raises(GovernanceViolation):
        governor.submit(tampered_bytes, permit, mock_adapter, now=fixed_now)

    # Crucial assertion: adapter.execute was called exactly 0 times
    assert mock_adapter.execute.call_count == 0


def test_inv_10_in_epoch_nonce_deduplication(governor, adapter, valid_proposal, fixed_now):
    """INV-10: In-epoch duplicate nonce is rejected fail-closed on second attempt."""
    permit = governor.issue_replay_permit(valid_proposal, now=fixed_now)
    proposal_bytes = valid_proposal.canonical_bytes()

    # First execution succeeds
    res = governor.submit(proposal_bytes, permit, adapter, now=fixed_now)
    assert res.status == "REPLAYED"

    # Second execution with same permit & nonce fails immediately
    with pytest.raises(NonceReplayDetected, match="has already been consumed"):
        governor.submit(proposal_bytes, permit, adapter, now=fixed_now)


def test_inv_11_missing_fixture_fail_closed(governor, valid_proposal, fixed_now):
    """INV-11: Missing in-memory fixture raises typed FixtureNotFoundError with no fallback."""
    empty_adapter = ReplayAdapter()
    permit = governor.issue_replay_permit(valid_proposal, now=fixed_now)
    proposal_bytes = valid_proposal.canonical_bytes()

    with pytest.raises(FixtureNotFoundError, match="not found in registry"):
        governor.submit(proposal_bytes, permit, empty_adapter, now=fixed_now)


def test_inv_12_post_restart_nonce_boundary_documented(adapter, valid_proposal, fixed_now):
    """INV-12: Documents the explicit boundary: post-restart nonce defense is NOT_YET_IMPLEMENTED.
    
    Demonstrates that instantiating a new governor (simulating process restart)
    resets the in-memory nonce set. This limitation is explicitly acknowledged and
    labeled as NOT_YET_IMPLEMENTED pending append-only ledger integration.
    """
    gov_epoch_1 = CapabilityGovernor(process_epoch_id="epoch_1")
    permit_1 = gov_epoch_1.issue_replay_permit(valid_proposal, now=fixed_now)
    proposal_bytes = valid_proposal.canonical_bytes()

    # Consumed in epoch 1
    gov_epoch_1.submit(proposal_bytes, permit_1, adapter, now=fixed_now)

    # Process restarts -> epoch 2 governor instantiated
    gov_epoch_2 = CapabilityGovernor(process_epoch_id="epoch_2")

    # If old permit from epoch 1 is submitted to epoch 2, epoch check catches it:
    with pytest.raises(EpochMismatch, match="Epoch mismatch"):
        gov_epoch_2.submit(proposal_bytes, permit_1, adapter, now=fixed_now)

    # However, if a permit is forged/reissued with the same nonce under epoch 2:
    permit_2 = gov_epoch_2.issue_replay_permit(valid_proposal, now=fixed_now)
    # The new governor accepts it because in-memory store was reset:
    res = gov_epoch_2.submit(proposal_bytes, permit_2, adapter, now=fixed_now)
    assert res.status == "REPLAYED"
    # This test asserts and documents why multi-process/restart protection requires durable ledger.


def test_inv_13_zero_side_effect_static_review():
    """INV-13: Static AST inspection verifies zero forbidden primitives in osiris_governance."""
    package_dir = Path(__file__).resolve().parent.parent / "src" / "osiris_governance"
    forbidden_modules = {"socket", "subprocess", "urllib", "requests", "httpx", "shutil", "tempfile"}
    forbidden_calls = {"open", "system", "popen", "exec", "eval"}

    for py_file in package_dir.glob("*.py"):
        tree = ast.parse(py_file.read_text(encoding="utf-8"), filename=str(py_file))
        for node in ast.walk(tree):
            # Check imports
            if isinstance(node, ast.Import):
                for alias in node.names:
                    assert alias.name not in forbidden_modules, f"Forbidden import '{alias.name}' in {py_file.name}"
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    assert node.module not in forbidden_modules, f"Forbidden from-import '{node.module}' in {py_file.name}"
            # Check function calls
            elif isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name):
                    assert node.func.id not in forbidden_calls, f"Forbidden call '{node.func.id}()' in {py_file.name}"
