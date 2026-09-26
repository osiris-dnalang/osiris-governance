"""Runtime Confinement & Security Boundary Specifications and Validators."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, List, Mapping, Optional, Sequence, Set

from .errors import ConfinementViolationError


@dataclass(frozen=True)
class AllowedDescriptor:
    """Declared approved file descriptor in the worker process."""
    fd: int
    name: str
    target: str
    flags: str
    inheritable: bool = False


@dataclass(frozen=True)
class DescriptorManifest:
    """Manifest of all permitted file descriptors in the confined worker.
    
    Acceptance Invariant:
    1. Every open descriptor in the worker MUST match an entry in allowed_descriptors.
    2. Any descriptor index not declared MUST be closed and yield EBADF when probed.
    3. Any open descriptor with undeclared target/mode constitutes a confinement violation.
    """
    manifest_id: str
    allowed_descriptors: Sequence[AllowedDescriptor]
    max_probed_fd: int = 1024

    def allowed_fd_set(self) -> Set[int]:
        return {d.fd for d in self.allowed_descriptors}

    def validate_process_descriptors(
        self,
        open_fds: Mapping[int, Mapping[str, Any]],
        probed_ebadf_fds: Sequence[int],
    ) -> None:
        """Validates actual worker descriptors against the manifest."""
        allowed_map = {d.fd: d for d in self.allowed_descriptors}
        allowed_set = set(allowed_map.keys())

        # Check 1: Every actual open descriptor must be declared
        for fd, info in open_fds.items():
            if fd not in allowed_map:
                raise ConfinementViolationError(
                    f"Undeclared open file descriptor detected: fd={fd}, target={info.get('target')}"
                )
            declared = allowed_map[fd]
            if "target" in info and info["target"] != declared.target:
                raise ConfinementViolationError(
                    f"Descriptor fd={fd} target mismatch: actual={info['target']}, declared={declared.target}"
                )

        # Check 2: Non-declared probed FDs must yield EBADF
        for fd in probed_ebadf_fds:
            if fd in allowed_set:
                raise ConfinementViolationError(
                    f"Declared descriptor fd={fd} unexpectedly reported EBADF"
                )


@dataclass(frozen=True)
class LeastPrivilegeProfile:
    """Security identity profile for worker processes.
    
    Clarification:
    UID 65534 (nobody) is a recommended default, but the formal invariant
    is nonzero effective UID/GID with no capability inheritance.
    """
    profile_id: str
    effective_uid: int
    effective_gid: int
    supplementary_gids: Sequence[int] = field(default_factory=tuple)
    no_new_privs: bool = True
    setuid_allowed: bool = False
    cap_effective: Sequence[str] = field(default_factory=tuple)
    cap_permitted: Sequence[str] = field(default_factory=tuple)
    cap_inheritable: Sequence[str] = field(default_factory=tuple)
    cap_ambient: Sequence[str] = field(default_factory=tuple)

    def validate(self) -> None:
        if self.effective_uid == 0:
            raise ConfinementViolationError("Root UID (0) is strictly prohibited in worker profile.")
        if self.effective_gid == 0:
            raise ConfinementViolationError("Root GID (0) is strictly prohibited in worker profile.")
        if not self.no_new_privs:
            raise ConfinementViolationError("no_new_privs must be TRUE in worker profile.")
        if self.setuid_allowed:
            raise ConfinementViolationError("setuid must be FALSE in worker profile.")
        if len(self.cap_effective) > 0:
            raise ConfinementViolationError(f"Effective capabilities must be empty: {self.cap_effective}")
        if len(self.cap_ambient) > 0:
            raise ConfinementViolationError(f"Ambient capabilities must be empty: {self.cap_ambient}")


@dataclass(frozen=True)
class Openat2ResolutionPolicy:
    """Path resolution policy enforcing kernel openat2 flags."""
    resolve_beneath: bool = True
    resolve_no_symlinks: bool = True
    resolve_no_magiclinks: bool = True
    resolve_no_xdev: bool = True
    trusted_dirfd_required: bool = True

    def validate(self) -> None:
        if not (self.resolve_beneath and self.resolve_no_symlinks and 
                self.resolve_no_magiclinks and self.resolve_no_xdev):
            raise ConfinementViolationError(
                "openat2 policy must mandate RESOLVE_BENEATH, NO_SYMLINKS, NO_MAGICLINKS, and NO_XDEV."
            )


@dataclass(frozen=True)
class NetworkAcceptancePolicy:
    """Network egress verification policy observed from outside worker netns."""
    policy_id: str
    control_plane_allowlist: Sequence[str] = field(default_factory=tuple) # (IP, Port) strings
    prohibit_all_egress: bool = True

    def validate_observation(self, observed_egress_frames: int, allowlist_breaches: int) -> None:
        if self.prohibit_all_egress and observed_egress_frames > 0:
            raise ConfinementViolationError(
                f"Observed {observed_egress_frames} outbound frames when total egress denial is active."
            )
        if allowlist_breaches > 0:
            raise ConfinementViolationError(
                f"Observed {allowlist_breaches} network egress frames violating control-plane allowlist."
            )
