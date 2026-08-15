#!/usr/bin/env python3
"""
init_task_state.py — Khởi tạo persistent task state cho equity-research-vn.

Lớp 2 anti-omission harness: trạng thái nằm trong FILE, không trong conversation.
Khi context bị compact, agent đọc task-state.json để khôi phục.

Tạo structure:
  [WORK_DIR]/
    .task-state/
      task-state.json      — trạng thái tổng (phase, progress)
      evidence/
        REQ-001.json       — evidence per requirement
        REQ-002.json
        ...
      decision-log.md      — ghi quyết định quan trọng
      unresolved.md        — blocker chưa giải

Usage: python3 init_task_state.py MSN /path/to/working/dir

ARC-5/G8: đồng bộ với run_phase.py — 9 phase (phase7_deploy, không tách verify/deploy).
REQ-068 phase_completion_check đọc status của 9 phase này.
"""
import json, sys, os, datetime

TICKER = sys.argv[1] if len(sys.argv) > 1 else "UNKNOWN"
WORK_DIR = sys.argv[2] if len(sys.argv) > 2 else "."
SKILL_DIR = os.path.abspath(os.environ.get(
    "EQUITY_SKILL_DIR", os.path.join(os.path.dirname(__file__), "..")
))

STATE_DIR = os.path.join(WORK_DIR, ".task-state")
EVIDENCE_DIR = os.path.join(STATE_DIR, "evidence")

# Create structure
os.makedirs(EVIDENCE_DIR, exist_ok=True)

# ARC-7 (review V4 Pro): bỏ copy requirements.yaml vào work dir — verifier đọc
# từ SKILL_DIR, không từ WORK_DIR → artifact thừa.

# task-state.json
task_state = {
    "ticker": TICKER,
    "created_at": datetime.datetime.now().isoformat(),
    "last_updated": datetime.datetime.now().isoformat(),
    "phase": "init",
    # ARC-5: 9 phase — đồng bộ run_phase.py PHASES list (phase7_deploy gộp verify+deploy)
    "phases": {
        "phase0_sponsor": {"status": "pending", "started": None, "completed": None},
        "phase1_data": {"status": "pending", "started": None, "completed": None},
        "phase2_fundamental": {"status": "pending", "started": None, "completed": None},
        "phase3_valuation": {"status": "pending", "started": None, "completed": None},
        "phase4a_tech_active": {"status": "pending", "started": None, "completed": None},
        "phase4b_tech_profile": {"status": "pending", "started": None, "completed": None},
        "phase5_news": {"status": "pending", "started": None, "completed": None},
        "phase6_dashboard": {"status": "pending", "started": None, "completed": None},
        "phase7_deploy": {"status": "pending", "started": None, "completed": None},
    },
    "requirements": {},  # REQ-001 → {status: pending/pass/fail, evidence_file, verified_at}
    "artifact_path": None,  # path to output HTML
    "deploy_url": None,
    "blockers": [],
}

# Init all requirements as pending (đọc từ SKILL_DIR, không copy)
import yaml
req_src = os.path.join(SKILL_DIR, "requirements.yaml")
if os.path.exists(req_src):
    with open(req_src) as f:
        req_data = yaml.safe_load(f) or {}
    for req in req_data.get("requirements", []):
        task_state["requirements"][req["id"]] = {
            "status": "pending",
            "priority": req.get("priority", "medium"),
            "evidence_file": f"evidence/{req['id']}.json",
            "verified_at": None,
            "failure_reason": None,
        }

with open(os.path.join(STATE_DIR, "task-state.json"), "w") as f:
    json.dump(task_state, f, indent=2, ensure_ascii=False)

# decision-log.md
with open(os.path.join(STATE_DIR, "decision-log.md"), "w") as f:
    f.write(f"# Decision Log — {TICKER}\n\n")
    f.write(f"Created: {datetime.datetime.now().isoformat()}\n\n")
    f.write("## Decisions\n\n")

# unresolved.md
with open(os.path.join(STATE_DIR, "unresolved.md"), "w") as f:
    f.write(f"# Unresolved Blockers — {TICKER}\n\n")
    f.write("List blocker chưa giải. Format: [REQ-XXX] description\n\n")

print(f"✅ Task state initialized: {STATE_DIR}")
print(f"   Ticker: {TICKER}")
print(f"   Requirements: {len(task_state['requirements'])} tracked")
print(f"   Phases: {len(task_state['phases'])}")
print(f"\nAgent đọc {STATE_DIR}/task-state.json để khôi phục trạng thái khi context compact.")
