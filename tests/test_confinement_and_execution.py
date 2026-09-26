"""Tests for Confinement, Execution Gate, and Attestation."""

import pytest
from osiris_governance.attestation import (
    AttestationLevel,
    S1ArtifactIdentity,
    S2RuntimeIdentity,
    S3IsolationObservations,
    S4ExecutionTrace,
    S5EvidenceIntegrity,
    SandboxAttestationRecord,
)
from osiris_governance.confinement import (
    AllowedDescriptor,
    DescriptorManifest,
    LeastPrivilegeProfile,
    NetworkAcceptancePolicy,
)
from osiris_governance.errors import AuthorityGateError, ConfinementViolationError
from osiris_governance.execution_gate import ExecutionContract, ExecutionGate
from osiris_governance.models.claim import EpistemicStatus
from osiris_governance.models.release import (
    AuthorizationState,
    DeployedGateStatus,
    ExecutionMode,
    ReleaseDecisionBasis,
)


def test_descriptor_manifest_clean():
    manifest = DescriptorManifest(
        manifest_id="DM-01",
        allowed_descriptors=[
            AllowedDescriptor(fd=0, name="stdin", target="/dev/null", flags="O_RDONLY"),
            AllowedDescriptor(fd=1, name="stdout", target="pipe:[100]", flags="O_WRONLY"),
            AllowedDescriptor(fd=2, name="stderr", target="pipe:[101]", flags="O_WRONLY"),
        ],
    )
    open_fds = {
        0: {"target": "/dev/null"},
        1: {"target": "pipe:[100]"},
        2: {"target": "pipe:[101]"},
    }
    probed_ebadf = [3, 4, 5, 6, 7]

    # Should pass without error
    manifest.validate_process_descriptors(open_fds, probed_ebadf)


def test_descriptor_manifest_undeclared_open_fd():
    manifest = DescriptorManifest(
        manifest_id="DM-01",
        allowed_descriptors=[
            AllowedDescriptor(fd=0, name="stdin", target="/dev/null", flags="O_RDONLY"),
            AllowedDescriptor(fd=1, name="stdout", target="pipe:[100]", flags="O_WRONLY"),
        ],
    )
    open_fds = {
        0: {"target": "/dev/null"},
        1: {"target": "pipe:[100]"},
        3: {"target": "/etc/shadow"}, # Undeclared open FD!
    }
    with pytest.raises(ConfinementViolationError, match="Undeclared open file descriptor"):
        manifest.validate_process_descriptors(open_fds, [4, 5])


def test_descriptor_manifest_declared_ebadf():
    manifest = DescriptorManifest(
        manifest_id="DM-01",
        allowed_descriptors=[
            AllowedDescriptor(fd=0, name="stdin", target="/dev/null", flags="O_RDONLY"),
            AllowedDescriptor(fd=1, name="stdout", target="pipe:[100]", flags="O_WRONLY"),
        ],
    )
    open_fds = {0: {"target": "/dev/null"}}
    probed_ebadf = [1, 2, 3] # fd 1 is declared but unexpectedly reported EBADF!

    with pytest.raises(ConfinementViolationError, match="unexpectedly reported EBADF"):
        manifest.validate_process_descriptors(open_fds, probed_ebadf)


def test_least_privilege_profile():
    valid = LeastPrivilegeProfile(
        profile_id="LP-01",
        effective_uid=65534,
        effective_gid=65534,
        no_new_privs=True,
        cap_effective=(),
    )
    valid.validate()

    root_uid = LeastPrivilegeProfile(
        profile_id="LP-ROOT",
        effective_uid=0,
        effective_gid=65534,
    )
    with pytest.raises(ConfinementViolationError, match="Root UID"):
        root_uid.validate()

    caps_violation = LeastPrivilegeProfile(
        profile_id="LP-CAPS",
        effective_uid=65534,
        effective_gid=65534,
        cap_effective=("CAP_SYS_ADMIN",),
    )
    with pytest.raises(ConfinementViolationError, match="Effective capabilities must be empty"):
        caps_violation.validate()


def test_network_acceptance_policy():
    policy = NetworkAcceptancePolicy(policy_id="NET-01", prohibit_all_egress=True)
    with pytest.raises(ConfinementViolationError, match="outbound frames"):
        policy.validate_observation(observed_egress_frames=1, allowlist_breaches=0)


def test_execution_gate_modes():
    # 1. DRY_RUN always admitted
    c_dry = ExecutionContract(
        execution_id="EX-DRY",
        target_artifact_digest="sha256:1",
        mode=ExecutionMode.DRY_RUN,
        frozen_at_utc="2026-09-26T10:00:00Z",
    )
    assert ExecutionGate.admit_execution(c_dry) == ExecutionMode.DRY_RUN

    # 2. SIMULATION rejects physical hardware
    c_sim_hw = ExecutionContract(
        execution_id="EX-SIM-HW",
        target_artifact_digest="sha256:1",
        mode=ExecutionMode.SIMULATION,
        frozen_at_utc="2026-09-26T10:00:00Z",
        parameters={"require_physical_hardware": True},
    )
    with pytest.raises(AuthorityGateError, match="Physical hardware execution requested under SIMULATION"):
        ExecutionGate.admit_execution(c_sim_hw)

    # 3. AUTHORIZED requires ELIGIBLE basis and signed permit nonce
    c_auth = ExecutionContract(
        execution_id="EX-AUTH",
        target_artifact_digest="sha256:1",
        mode=ExecutionMode.AUTHORIZED,
        frozen_at_utc="2026-09-26T10:00:00Z",
        signed_permit_nonce="nonce_secret_123",
    )
    basis_eligible = ReleaseDecisionBasis(
        release_id="REL-OK",
        artifact_digest="sha256:1",
        authorization_state=AuthorizationState.ELIGIBLE,
        s_deployed=DeployedGateStatus.TRUE,
        r_deployed=DeployedGateStatus.TRUE,
        prerequisites={"locked_artifact": True},
        claims_snapshot={"CLAIM-1": EpistemicStatus.VERIFIED},
    )
    assert ExecutionGate.admit_execution(c_auth, basis_eligible) == ExecutionMode.AUTHORIZED

    # Without permit nonce -> rejected
    c_auth_no_permit = ExecutionContract(
        execution_id="EX-AUTH-NO-PERMIT",
        target_artifact_digest="sha256:1",
        mode=ExecutionMode.AUTHORIZED,
        frozen_at_utc="2026-09-26T10:00:00Z",
    )
    with pytest.raises(AuthorityGateError, match="Signed permit nonce is required"):
        ExecutionGate.admit_execution(c_auth_no_permit, basis_eligible)


def test_sandbox_attestation_record():
    record = SandboxAttestationRecord(
        execution_id="EXEC-001",
        level=AttestationLevel.LEVEL_1_OBSERVED,
        s1_artifact=S1ArtifactIdentity("sha256:img", "sha256:bin", "sha256:pol"),
        s2_runtime=S2RuntimeIdentity("6.8.0", "sha256:sec", 65534, 65534, True),
        s3_isolation=S3IsolationObservations(host_sentinel_touches=0, network_egress_frames=0),
        s4_trace=S4ExecutionTrace(100.0, 102.5, 0, "sha256:trc"),
        s5_integrity=S5EvidenceIntegrity("sha256:man", "sha256:aud"),
    )
    assert record.evaluate_verdict() == "CONFINEMENT_VERIFIED"

    # Breach test:
    breached_record = SandboxAttestationRecord(
        execution_id="EXEC-002",
        level=AttestationLevel.LEVEL_1_OBSERVED,
        s1_artifact=S1ArtifactIdentity("sha256:img", "sha256:bin", "sha256:pol"),
        s2_runtime=S2RuntimeIdentity("6.8.0", "sha256:sec", 65534, 65534, True),
        s3_isolation=S3IsolationObservations(host_sentinel_touches=1), # Breach!
        s4_trace=S4ExecutionTrace(100.0, 102.5, 0, "sha256:trc"),
        s5_integrity=S5EvidenceIntegrity("sha256:man", "sha256:aud"),
    )
    assert breached_record.evaluate_verdict() == "CONFINEMENT_BREACH"
