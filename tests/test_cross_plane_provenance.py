"""Tests for Cross-Plane Provenance and Primary Evidence Object taxonomy."""

import json
from pathlib import Path
import pytest

from osiris_governance.models.evidence import (
    CrossPlaneProvenanceRecord,
    EvidencePlane,
    HardwareProviderReceipt,
    RawExperimentalDataReceipt,
    RuntimeProbeReceipt,
)


def test_typed_primary_evidence_planes():
    """Ensure every primary evidence object declares its explicit non-overlapping plane."""
    probe = RuntimeProbeReceipt(
        receipt_id="PRB-001",
        criterion="SECCOMP_FILTER_ACTIVE",
        status="PASS",
        captured_at_utc="2026-09-26T12:00:00Z",
    )
    assert probe.evidence_plane == EvidencePlane.OPERATIONAL
    assert probe.object_type == "RUNTIME_PROBE_RECEIPT"

    raw_data = RawExperimentalDataReceipt(
        receipt_id="RAW-001",
        dataset_digest="sha256:" + "0" * 64,
        protocol_ref="PROTO-001",
        captured_at_utc="2026-09-26T12:00:00Z",
    )
    assert raw_data.evidence_plane == EvidencePlane.SCIENTIFIC
    assert raw_data.object_type == "RAW_EXPERIMENTAL_DATA_RECEIPT"

    hw = HardwareProviderReceipt(
        receipt_id="HW-001",
        backend="ibm_heron",
        job_id="job-12345",
        calibration_hash="sha256:" + "1" * 64,
        raw_counts_digest="sha256:" + "2" * 64,
        captured_at_utc="2026-09-26T12:00:00Z",
    )
    assert hw.evidence_plane == EvidencePlane.SCIENTIFIC
    assert hw.execution_domain == "QUANTUM_HARDWARE"
    assert hw.object_type == "HARDWARE_PROVIDER_RECEIPT"

    xpl = CrossPlaneProvenanceRecord(
        record_id="XPL-001",
        operational_root="sha256:" + "3" * 64,
        scientific_root="sha256:" + "4" * 64,
        shared_artifact_digest="sha256:" + "5" * 64,
        git_commit_sha="abcdef1",
        created_at_utc="2026-09-26T12:00:00Z",
    )
    assert xpl.evidence_plane == EvidencePlane.PROVENANCE
    assert xpl.provenance_only is True
    assert xpl.substitution_scientific_for_operational is False
    assert xpl.substitution_operational_for_scientific is False


def test_xpl_manifest_schema_compliance():
    """Validate the frozen XPL package manifest against cross_plane_provenance schema."""
    repo_root = Path(__file__).parent.parent
    schema_path = repo_root / "schemas" / "cross_plane_provenance.schema.json"
    manifest_path = repo_root / "evidence" / "provenance" / "XPL-2026-09-26-001" / "MANIFEST.json"

    assert schema_path.exists(), f"Schema missing at {schema_path}"
    assert manifest_path.exists(), f"Manifest missing at {manifest_path}"

    with open(schema_path, "r", encoding="utf-8") as f:
        schema = json.load(f)
    with open(manifest_path, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    # Basic schema requirement assertions
    for req in schema["required"]:
        assert req in manifest, f"Missing required field: {req}"

    assert manifest["evidence_plane"] == "PROVENANCE"
    assert manifest["provenance_only"] is True
    assert manifest["substitution"]["scientific_for_operational"] is False
    assert manifest["substitution"]["operational_for_scientific"] is False
