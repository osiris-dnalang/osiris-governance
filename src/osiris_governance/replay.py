"""Pure in-memory ReplayAdapter possessing zero filesystem or network authority."""

from __future__ import annotations

import copy
from typing import Any, Mapping

from .errors import FixtureNotFoundError


class ReplayAdapter:
    """Deterministic in-memory replay adapter.
    
    INVARIANTS:
    - Zero filesystem authority: does not import pathlib, os.path, or use open().
    - Zero network authority: does not import sockets or HTTP libraries.
    - Zero subprocess authority: does not invoke commands or system dispatchers.
    - Operates purely on registered in-memory fixtures.
    """

    def __init__(self) -> None:
        self._fixtures: dict[str, dict[str, Any]] = {}

    def register_fixture(self, fixture_id: str, payload: Mapping[str, Any]) -> None:
        """Registers a deterministic fixture in memory."""
        self._fixtures[fixture_id] = copy.deepcopy(dict(payload))

    def has_fixture(self, fixture_id: str) -> bool:
        """Returns True if fixture exists in memory."""
        return fixture_id in self._fixtures

    def execute(self, canonical_proposal_bytes: bytes, fixture_id: str) -> dict[str, Any]:
        """Dispatches an authorized replay request to an in-memory fixture.
        
        Guaranteed to only be invoked after CapabilityGovernor has evaluated and validated
        the proposal and its bound permit.
        """
        if not isinstance(canonical_proposal_bytes, bytes):
            raise TypeError("canonical_proposal_bytes must be bytes")

        if fixture_id not in self._fixtures:
            raise FixtureNotFoundError(f"Replay fixture '{fixture_id}' not found in registry")

        # Return deep copy to prevent caller mutation of registered fixture
        return copy.deepcopy(self._fixtures[fixture_id])
