#!/usr/bin/env python3
"""Generate registry docs (W4-1 — Wave 4): sinh index REQ từ requirements.yaml
canonical — KHÔNG copy tay. Output: references/req_index.md (đồng bộ mọi tài liệu).

Chạy: python3 scripts/tests/generate_registry_docs.py
"""
import os, yaml

SKILL = os.path.expanduser("~/.zcode/skills/equity-research-vn")
REQ_FILE = os.path.join(SKILL, "requirements.yaml")
MAP_FILE = os.path.join(SKILL, "requirements-phase-map.yaml")
OUT = os.path.join(SKILL, "references", "req_index.md")

def main():
    doc = yaml.safe_load(open(REQ_FILE))
    reqs = doc["requirements"]
    prio = {s: doc.get(s, []) for s in ("critical", "high", "medium", "low")}
    pm = yaml.safe_load(open(MAP_FILE))["phase_requirements"]

    # REQ → phases
    req_phases = {}
    for phase, info in pm.items():
        for rid in info["reqs"]:
            req_phases.setdefault(rid, []).append(phase)

    lines = ["# REQ Index (SINH TỰ ĐỘNG từ requirements.yaml — KHÔNG sửa tay)",
             "",
             f"> Tổng: {len(reqs)} REQ · {len(pm)} phases · sinh bởi generate_registry_docs.py",
             ""]
    for section in ("critical", "high", "medium", "low"):
        lines.append(f"## {section.upper()} ({len(prio[section])})")
        lines.append("")
        lines.append("| REQ | Priority | Phases | Tóm tắt |")
        lines.append("|---|---|---|---|")
        for rid in prio[section]:
            r = next((x for x in reqs if x["id"] == rid), None)
            if not r:
                continue
            text = r["text"].split(".")[0][:70]
            phases = ", ".join(req_phases.get(rid, []))
            lines.append(f"| {rid} | {section} | {phases} | {text} |")
        lines.append("")

    with open(OUT, "w") as f:
        f.write("\n".join(lines))
    print(f"✅ Generated {OUT} — {len(reqs)} REQ indexed")

if __name__ == "__main__":
    main()
