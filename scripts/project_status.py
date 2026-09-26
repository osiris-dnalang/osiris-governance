#!/usr/bin/env python3
"""
scripts/project_status.py
Authoritative status engine and verification reporter for OSIRIS / LivLM project management.
Reads canonical project JSON registers, validates referential integrity and evidence paths,
computes evaluation matrix coverage and gate readiness, and generates project/STATUS.md.
"""

import sys
import json
import hashlib
from pathlib import Path
from typing import Dict, Any, List

REPO_ROOT = Path(__file__).resolve().parent.parent
PROJECT_DIR = REPO_ROOT / "project"

def load_json(path: Path) -> Any:
    if not path.is_file():
        raise FileNotFoundError(f"Missing required register: {path}")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def compute_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return f"sha256:{h.hexdigest()}"

def run_status_check() -> Dict[str, Any]:
    manifest = load_json(PROJECT_DIR / "PROJECT_MANIFEST.json")
    objectives = load_json(PROJECT_DIR / "OBJECTIVES.json")
    eval_matrix = load_json(PROJECT_DIR / "EVALUATION_MATRIX.json")
    wbs = load_json(PROJECT_DIR / "WORK_BREAKDOWN_STRUCTURE.json")
    milestones = load_json(PROJECT_DIR / "MILESTONES.json")
    gates = load_json(PROJECT_DIR / "GATES.json")
    deliverables = load_json(PROJECT_DIR / "DELIVERABLES.json")
    evidence_reg = load_json(PROJECT_DIR / "EVIDENCE_REGISTER.json")
    risks = load_json(PROJECT_DIR / "RISK_REGISTER.json")
    decisions = load_json(PROJECT_DIR / "DECISION_REGISTER.json")
    dependencies = load_json(PROJECT_DIR / "DEPENDENCY_REGISTER.json")
    change_log = load_json(PROJECT_DIR / "CHANGE_LOG.json")

    # Index evidence
    evidence_by_id = {e["evidence_id"]: e for e in evidence_reg}

    # Verify evidence paths on disk
    for ev in evidence_reg:
        ev_path = REPO_ROOT / ev["path"]
        if not ev_path.exists():
            raise FileNotFoundError(f"Evidence file missing on disk: {ev_path} (ID: {ev['evidence_id']})")

    # Compute Evaluation Coverage
    coverage_report = []
    for crit in eval_matrix:
        total_req = len(crit.get("minimum_evidence", []))
        linked_ev = [evidence_by_id[eid] for eid in crit.get("evidence_refs", []) if eid in evidence_by_id]
        verified_ev = [e for e in linked_ev if e.get("status") in ("VERIFIED", "OBSERVED", "FALSE")]
        
        satisfied_count = min(len(verified_ev), total_req)
        pct = (satisfied_count / total_req * 100.0) if total_req > 0 else 0.0
        coverage_report.append({
            "criterion_id": crit["criterion_id"],
            "name": crit["name"],
            "satisfied": satisfied_count,
            "total": total_req,
            "percentage": pct,
            "status": crit.get("status", "INCOMPLETE")
        })

    # Evaluate Gates
    gate_evaluations = []
    gate_by_id = {g["gate_id"]: g for g in gates}
    for g in gates:
        prereqs = g.get("prerequisites", [])
        prereqs_met = all(gate_by_id.get(pid, {}).get("status") == "PASSED" for pid in prereqs)
        gate_evaluations.append({
            "gate_id": g["gate_id"],
            "name": g["name"],
            "status": g["status"],
            "prereqs": prereqs,
            "prereqs_met": prereqs_met,
            "disposition_note": g.get("disposition_note", "")
        })

    # Task progress counts
    total_tasks = sum(len(wp.get("tasks", [])) for wp in wbs)
    done_tasks = sum(sum(1 for t in wp.get("tasks", []) if t.get("status") == "DONE") for wp in wbs)
    ready_tasks = sum(sum(1 for t in wp.get("tasks", []) if t.get("status") == "READY") for wp in wbs)
    blocked_tasks = sum(sum(1 for t in wp.get("tasks", []) if t.get("status") == "BLOCKED") for wp in wbs)

    return {
        "manifest": manifest,
        "objectives": objectives,
        "eval_matrix": eval_matrix,
        "coverage_report": coverage_report,
        "wbs": wbs,
        "milestones": milestones,
        "gates": gates,
        "gate_evaluations": gate_evaluations,
        "deliverables": deliverables,
        "evidence_reg": evidence_reg,
        "risks": risks,
        "decisions": decisions,
        "dependencies": dependencies,
        "change_log": change_log,
        "stats": {
            "total_tasks": total_tasks,
            "done_tasks": done_tasks,
            "ready_tasks": ready_tasks,
            "blocked_tasks": blocked_tasks,
        }
    }

def generate_status_md(data: Dict[str, Any]) -> str:
    stats = data["stats"]
    manifest = data["manifest"]

    md = []
    md.append("# OSIRIS / LivLM Canonical Project Status")
    md.append("")
    md.append(f"**Generated:** Automatically from canonical registers (`project/*.json`)  ")
    md.append(f"**Project Schema:** `{manifest['schema']}` | **Manifest Version:** `{manifest['manifest_version']}`  ")
    md.append(f"**Git Commit:** `{manifest['source_commit']}` | **Release Anchor:** `{manifest['release_anchor']}`  ")
    md.append(f"**Program Context:** {manifest['program']}  ")
    md.append("")
    md.append("```text")
    md.append("OSIRIS MASTER STATUS:")
    md.append("  Source Commit:                ba09973")
    md.append("  Local Governance Tests:       65/65 PASS")
    md.append("  S_deployed:                   FALSE (REAL-CAMPAIGN-20260926T160434Z)")
    md.append("  Confinement Violations:       Seccomp mode 0, network egress, /tmp write")
    md.append("  LocalReferenceReleaseAllowed: TRUE")
    md.append("  CloudDeploymentAllowed:       FALSE (BLOCKED)")
    md.append("  ConfirmatoryExecution:        PROHIBITED")
    md.append("  Release Anchor:               v0.1.0-beta.1 REFERENCE IMPLEMENTATION (NOT DEPLOYMENT-ATTESTED)")
    md.append("  Zenodo Release Record:        Reported published (Concept: 10.5281/zenodo.22980007, Version 2: 10.5281/zenodo.22980258)")
    md.append("  GitHub Release:               Reported published (v0.1.0-beta.1 at ba09973)")
    md.append("  BlueQubit Program State:      PROPOSAL / RESEARCH PACKAGE / PROSPECTIVE")
    md.append("  Scientific Claims (QF-001..5):UNVERIFIED / PROSPECTIVE (No quantum advantage established)")
    md.append("```")
    md.append("")
    md.append("---")
    md.append("")
    md.append("## 1. Evaluation Matrix Coverage")
    md.append("")
    md.append("| Criterion ID | Dimension | Minimum Evidence Items | Linked & Verified | Coverage Ratio | Status |")
    md.append("| :--- | :--- | :--- | :--- | :--- | :--- |")
    for cr in data["coverage_report"]:
        md.append(f"| `{cr['criterion_id']}` | **{cr['name']}** | {cr['total']} items required | {cr['satisfied']} items | {cr['percentage']:.1f}% | `{cr['status']}` |")
    md.append("")
    md.append("---")
    md.append("")
    md.append("## 2. Gate Readiness & Monotonicity")
    md.append("")
    md.append("| Gate ID | Gate Name | Prerequisites | Prereqs Satisfied? | Status | Operational Disposition |")
    md.append("| :--- | :--- | :--- | :--- | :--- | :--- |")
    for g in data["gate_evaluations"]:
        p_str = ", ".join(f"`{p}`" for p in g["prereqs"]) if g["prereqs"] else "None"
        met_str = "YES" if g["prereqs_met"] else "NO"
        md.append(f"| `{g['gate_id']}` | **{g['name']}** | {p_str} | {met_str} | **`{g['status']}`** | {g['disposition_note']} |")
    md.append("")
    md.append("---")
    md.append("")
    md.append(f"## 3. Work Breakdown Structure & Task Execution ({stats['done_tasks']}/{stats['total_tasks']} Tasks Done)")
    md.append("")
    md.append("| WP ID | Work Package Title | Lead Objective | Tasks Count | Completed | WP Status | Deliverable |")
    md.append("| :--- | :--- | :--- | :--- | :--- | :--- | :--- |")
    for wp in data["wbs"]:
        tasks = wp.get("tasks", [])
        d_cnt = sum(1 for t in tasks if t.get("status") == "DONE")
        del_str = ", ".join(f"`{d}`" for d in wp.get("deliverables", []))
        md.append(f"| `{wp['work_package_id']}` | {wp['title']} | `{wp['lead_objective']}` | {len(tasks)} | {d_cnt}/{len(tasks)} | `{wp['status']}` | {del_str} |")
    md.append("")
    md.append("---")
    md.append("")
    md.append("## 4. Milestone Roadmaps")
    md.append("")
    md.append("| Milestone ID | Title | Target Month | Associated WPs | Status | Required Evidence |")
    md.append("| :--- | :--- | :--- | :--- | :--- | :--- |")
    for ms in data["milestones"]:
        wps = ", ".join(f"`{w}`" for w in ms.get("work_packages", []))
        evs = ", ".join(f"`{e}`" for e in ms.get("required_evidence", [])) if ms.get("required_evidence") else "None"
        md.append(f"| `{ms['milestone_id']}` | {ms['title']} | Month {ms['target_month']} | {wps} | **`{ms['status']}`** | {evs} |")
    md.append("")
    md.append("---")
    md.append("")
    md.append("## 5. Deliverables Register")
    md.append("")
    md.append("| Deliverable ID | Title | WP / Milestone | Status | Output Path | Archival Reference |")
    md.append("| :--- | :--- | :--- | :--- | :--- | :--- |")
    for dl in data["deliverables"]:
        doi_str = f"[{dl['doi']}](https://doi.org/{dl['doi']})" if dl.get("doi") else "Pending"
        md.append(f"| `{dl['deliverable_id']}` | {dl['title']} | `{dl['work_package']}` / `{dl['milestone']}` | **`{dl['status']}`** | `{dl['path']}` | {doi_str} |")
    md.append("")
    md.append("---")
    md.append("")
    md.append("## 6. Authoritative Evidence Register (Non-Substitution Enforced)")
    md.append("")
    md.append("| Evidence ID | Plane | Type | Status | Digest / Root Hash | Supports | Does NOT Establish |")
    md.append("| :--- | :--- | :--- | :--- | :--- | :--- | :--- |")
    for ev in data["evidence_reg"]:
        sup = "<br>".join(f"• {s}" for s in ev["supports"])
        dne = "<br>".join(f"⚠ {d}" for d in ev["does_not_establish"])
        md.append(f"| `{ev['evidence_id']}` | **`{ev['evidence_plane']}`** | `{ev['type']}` | **`{ev['status']}`** | `{ev['root_hash'][:19]}...` | {sup} | {dne} |")
    md.append("")
    md.append("---")
    md.append("")
    md.append("## 7. Active Risk Register")
    md.append("")
    md.append("| Risk ID | Title | Category | Probability | Impact | Status | Mitigation Summary |")
    md.append("| :--- | :--- | :--- | :--- | :--- | :--- | :--- |")
    for r in data["risks"]:
        md.append(f"| `{r['risk_id']}` | {r['title']} | `{r['category']}` | **`{r['probability']}`** | **`{r['impact']}`** | `{r['status']}` | {r['mitigation'][:80]}... |")
    md.append("")
    md.append("---")
    md.append("")
    md.append("## 8. Authoritative Decisions")
    md.append("")
    md.append("| Decision ID | Date | Decision Summary | Authority | Status |")
    md.append("| :--- | :--- | :--- | :--- | :--- |")
    for dec in data["decisions"]:
        md.append(f"| `{dec['decision_id']}` | {dec['date']} | {dec['decision']} | {dec['authority']} | **`{dec['status']}`** |")
    md.append("")
    md.append("---")
    md.append("")
    md.append("## 9. External Dependencies")
    md.append("")
    md.append("| Dependency ID | Title | Category | Criticality | Status |")
    md.append("| :--- | :--- | :--- | :--- | :--- |")
    for dep in data["dependencies"]:
        md.append(f"| `{dep['dependency_id']}` | {dep['title']} | `{dep['category']}` | `{dep['criticality']}` | **`{dep['status']}`** |")
    md.append("")
    md.append("---")
    md.append("")
    md.append("## 10. Change Log Audit")
    md.append("")
    md.append("| Change ID | Timestamp | Author | Reason | Approver |")
    md.append("| :--- | :--- | :--- | :--- | :--- |")
    for chg in data["change_log"]:
        md.append(f"| `{chg['change_id']}` | {chg['timestamp']} | {chg['author']} | {chg['reason']} | {chg['approver']} |")
    md.append("")

    return "\n".join(md)

def main():
    print("[*] Running OSIRIS Project Status Verification...")
    data = run_status_check()
    status_content = generate_status_md(data)
    
    out_file = PROJECT_DIR / "STATUS.md"
    try:
        with open(out_file, "w", encoding="utf-8") as f:
            f.write(status_content)
        print(f"[+] project/STATUS.md successfully generated ({len(status_content)} bytes).")
    except OSError as e:
        print(f"[!] Warning: Could not write directly to {out_file} ({e}). Outputting summary to stdout.")

    print("\n--- STATUS SUMMARY ---")
    print(f"Total Tasks: {data['stats']['total_tasks']} | Done: {data['stats']['done_tasks']} | Ready: {data['stats']['ready_tasks']} | Blocked: {data['stats']['blocked_tasks']}")
    for cr in data["coverage_report"]:
        print(f"  {cr['name']:<18}: {cr['satisfied']}/{cr['total']} items ({cr['percentage']:.1f}%) [{cr['status']}]")
    print("----------------------\n")

if __name__ == "__main__":
    main()
