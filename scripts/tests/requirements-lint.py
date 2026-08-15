#!/usr/bin/env python3
"""Registry linter (P1-01 — Wave 1): kiểm tính nhất quán giữa requirements.yaml,
requirements-phase-map.yaml và SKILL.md.

Checks:
1. requirements.yaml: id duy nhất, không trống, method có trong verifier METHODS (nếu có thể đọc)
2. phase map: mọi ID trong map phải thuộc registry; không có ID lạ (parse YAML — bắt lỗi
   kiểu "REQ-065 - REQ-069"); không duplicate ngoài policy; mọi registry ID được map ≥1 phase
3. priority index: mọi REQ phải xuất hiện trong đúng 1 danh sách priority

Exit code: 0 = hợp lệ, 1 = có lỗi.
Chạy: python3 scripts/tests/requirements-lint.py
"""
import argparse, os, re, sys, yaml
from pathlib import Path

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--skill-dir",
        default=os.environ.get("EQUITY_SKILL_DIR", str(Path(__file__).resolve().parents[2])),
        help="Skill tree to lint (default: repository root)",
    )
    args = parser.parse_args()
    skill = os.path.abspath(os.path.expanduser(args.skill_dir))
    req_file = os.path.join(skill, "requirements.yaml")
    map_file = os.path.join(skill, "requirements-phase-map.yaml")
    verifier_file = os.path.join(skill, "scripts", "independent_verifier.py")
    errors = []

    # 1. Registry
    registry_doc = yaml.safe_load(open(req_file))
    reqs = registry_doc["requirements"]
    ids = [r["id"] for r in reqs]
    if len(ids) != len(set(ids)):
        dupes = sorted({i for i in ids if ids.count(i) > 1})
        errors.append(f"registry ID trùng: {dupes}")
    if not all(re.fullmatch(r"REQ-\d{3}", i) for i in ids):
        errors.append("registry có ID không đúng format REQ-###")
    registry = set(ids)
    if os.path.exists(verifier_file):
        verifier_text = open(verifier_file).read()
        dispatch_methods = set(re.findall(
            r'^\s{4}"([a-z0-9_]+)"\s*:', verifier_text, flags=re.MULTILINE
        ))
        dispatch_methods.add("all_requirements_pass")  # handled specially in main()
        unknown_methods = sorted({
            r.get("verification", {}).get("method") for r in reqs
            if r.get("verification", {}).get("method") not in dispatch_methods
        })
        if unknown_methods:
            errors.append(f"verification.method chưa có dispatch: {unknown_methods}")
    else:
        errors.append(f"thiếu verifier để lint method: {verifier_file}")

    # 2. Phase map
    pm = yaml.safe_load(open(map_file))["phase_requirements"]
    map_ids = []
    for phase, info in pm.items():
        map_ids.extend(info["reqs"])
    unknown = sorted({i for i in map_ids if i not in registry})
    if unknown:
        errors.append(f"phase map chứa ID không có trong registry: {unknown}")
    # Duplicate policy: REQ có thể xuất hiện ở phase chuyên biệt + phase6/7 (final verify).
    # Duplicate giữa 2 phase chuyên biệt (không phải final) → lỗi.
    FINAL_PHASES = {"phase6_dashboard", "phase7_deploy"}
    seen = {}
    for phase, info in pm.items():
        for r in info["reqs"]:
            seen.setdefault(r, []).append(phase)
    dup_illegal = sorted(r for r, phases in seen.items()
                         if len(phases) > 1 and not any(p in FINAL_PHASES for p in phases))
    if dup_illegal:
        errors.append(f"REQ bị map ở 2 phase chuyên biệt (ngoài final verify): {dup_illegal}")
    unmapped = sorted(registry - set(map_ids))
    if unmapped:
        errors.append(f"registry ID chưa được map phase nào: {unmapped}")

    # 3. Priority index
    # requirements.yaml structure: {"requirements": [...], "critical": [...], ...}
    doc = registry_doc
    listed = []
    for section in ("critical", "high", "medium", "low"):
        listed.extend(doc.get(section, []))
    missing_prio = sorted(registry - set(listed))
    if missing_prio:
        errors.append(f"REQ thiếu trong index priority: {missing_prio}")
    extra_prio = sorted(set(listed) - registry)
    if extra_prio:
        errors.append(f"index priority chứa ID không có trong registry: {extra_prio}")
    if doc.get("total") != len(ids):
        errors.append(f"total={doc.get('total')} nhưng registry có {len(ids)} REQ")
    duplicate_prio = sorted({req_id for req_id in listed if listed.count(req_id) > 1})
    if duplicate_prio:
        errors.append(f"REQ xuất hiện nhiều hơn một priority: {duplicate_prio}")

    if errors:
        print("❌ REGISTRY LINT FAIL:")
        for e in errors:
            print(f"  - {e}")
        sys.exit(1)
    print(f"✅ REGISTRY LINT OK — {len(registry)} REQ, {len(pm)} phases, map khớp registry, priority đầy đủ")

if __name__ == "__main__":
    main()
