#!/usr/bin/env python3
"""
run_phase.py — Phase runner cho equity-research-vn

Thin orchestrator: chạy từng phase tuần tự, verify sau mỗi phase.

Mỗi phase:
  1. Đọc phases/phaseN-xxx.md (prompt)
  2. Agent (subagent hoặc same-agent) execute theo prompt
  3. Verifier check REQ cho phase đó
  4. FAIL → BLOCK, không qua phase tiếp

Usage:
  python3 run_phase.py [TICKER] [WORK_DIR] [PHASE]
  python3 run_phase.py MSN /path/to/work phase0_sponsor
  python3 run_phase.py MSN /path/to/work --all

Output: cập nhật task-state.json + evidence/
"""
import json, sys, os, re, shlex, subprocess, yaml

TICKER = sys.argv[1] if len(sys.argv) > 1 else "UNKNOWN"
WORK_DIR = sys.argv[2] if len(sys.argv) > 2 else "."
PHASE_ARG = sys.argv[3] if len(sys.argv) > 3 else "--all"

SKILL_DIR = os.path.abspath(os.environ.get(
    "EQUITY_SKILL_DIR", os.path.join(os.path.dirname(__file__), "..")
))
STATE_DIR = os.path.join(WORK_DIR, ".task-state")
STATE_FILE = os.path.join(STATE_DIR, "task-state.json")
PHASE_MAP_FILE = os.path.join(SKILL_DIR, "requirements-phase-map.yaml")

PHASES = [
    ("phase0_sponsor", "phases/phase0-sponsor.md"),
    ("phase1_data", "phases/phase1-data.md"),
    ("phase2_fundamental", "phases/phase2-fundamental.md"),
    ("phase3_valuation", "phases/phase3-valuation.md"),
    ("phase4a_tech_active", "phases/phase4a-tech-active.md"),
    ("phase4b_tech_profile", "phases/phase4b-tech-profile.md"),
    ("phase5_news", "phases/phase5-news.md"),
    ("phase6_dashboard", "phases/phase6-dashboard.md"),
    ("phase7_deploy", "phases/phase7-deploy.md"),
]

def load_state():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE) as f:
            return json.load(f)
    return None

def save_state(state):
    os.makedirs(STATE_DIR, exist_ok=True)
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2, ensure_ascii=False)

def mark_phase_completed(phase_id):
    """P4 (review V4 Flash): run_phase tự ghi status=completed sau verify PASS —
    không phụ thuộc agent tự ghi. REQ-068 phase_completion_check đọc giá trị này."""
    import datetime
    state = load_state()
    if not state:
        return
    phases = state.setdefault("phases", {})
    phases.setdefault(phase_id, {})
    phases[phase_id]["status"] = "completed"
    phases[phase_id]["completed"] = datetime.datetime.now().isoformat()
    state["last_updated"] = datetime.datetime.now().isoformat()
    save_state(state)

def read_phase_prompt(prompt_path):
    full_path = os.path.join(SKILL_DIR, prompt_path)
    if not os.path.exists(full_path):
        return f"Phase prompt not found: {full_path}"
    with open(full_path) as f:
        prompt = f.read()
    # P1 (review V4 Flash): phase 6 có placeholder __TEMPLATE_INLINE_PLACEHOLDER__
    # nhưng không code nào inject → chạy qua run_phase = "cửa tử" (agent tự bịa 22
    # sections). Inject dashboard_template.html thật vào đây.
    if "__TEMPLATE_INLINE_PLACEHOLDER__" in prompt:
        template_candidates = [
            os.path.join(SKILL_DIR, "vn-research-dashboard", "assets", "dashboard_template.html"),
            os.path.join(os.path.expanduser("~/.zcode/skills/vn-research-dashboard/assets/dashboard_template.html")),
        ]
        for tc in template_candidates:
            if os.path.exists(tc):
                with open(tc) as tf:
                    prompt = prompt.replace("__TEMPLATE_INLINE_PLACEHOLDER__", tf.read())
                break
        else:
            print("⚠️ WARNING: __TEMPLATE_INLINE_PLACEHOLDER__ trong prompt phase6 nhưng "
                  "không tìm thấy dashboard_template.html — agent phải tự đọc file.")
    return prompt

TICKER_RE = re.compile(r"^[A-Z][A-Z0-9]{1,9}$")

def validate_inputs(ticker, report):
    """P0-04 (Wave 1): validate input TRƯỚC khi dùng trong bất kỳ command nào.
    - Ticker: allowlist [A-Z][A-Z0-9]{1,9} (chặn ký tự shell)
    - Report: absolute path, phải nằm trong WORK_DIR (realpath chặn symlink traversal)
    Raises ValueError nếu không hợp lệ."""
    if not TICKER_RE.fullmatch(ticker or ""):
        raise ValueError(f"TICKER không hợp lệ (chỉ chữ hoa/số, 2-10 ký tự): {ticker!r}")
    if report:
        rep_abs = os.path.realpath(report)
        work_abs = os.path.realpath(WORK_DIR)
        if not (rep_abs == work_abs or rep_abs.startswith(work_abs + os.sep)):
            raise ValueError(f"REPORT nằm ngoài WORK_DIR: {report!r}")

def run_command_safe(cmd, ticker, report):
    """P0-04: chạy registry command KHÔNG dùng shell.
    - Thay $TICKER/$REPORT bằng giá trị ĐÃ VALIDATE (allowlist) → không thể injection
    - Pipe đơn giản (|) được xử lý thủ công argv→argv; không có shell semantics khác
      (glob, redirect ngoài 2>/dev/null, &&, ;) — chúng KHÔNG được diễn giải.
    Trả về (returncode, stdout_cuối)."""
    validate_inputs(ticker, report)
    cmd = cmd.replace("$TICKER", ticker).replace("$REPORT", report or "")
    stderr = subprocess.DEVNULL if "2>/dev/null" in cmd else None
    parts = [re.sub(r"\s*2>/dev/null\s*$", "", p).strip() for p in cmd.split("|")]
    argv_parts = [shlex.split(p) for p in parts if p]
    if not argv_parts:
        raise ValueError(f"command rỗng: {cmd!r}")
    prev_out = None
    for i, argv in enumerate(argv_parts):
        r = subprocess.run(argv, shell=False, stdout=subprocess.PIPE, text=True,
                           input=prev_out, timeout=30,
                           stderr=stderr if i == len(argv_parts) - 1 else subprocess.DEVNULL)
        prev_out = r.stdout
    return r.returncode, prev_out

def verify_phase(phase_id):
    """Run verifier for specific phase REQs."""
    if not os.path.exists(PHASE_MAP_FILE):
        print("⚠️ No phase map, skipping per-phase verify")
        return True

    with open(PHASE_MAP_FILE) as f:
        phase_map = yaml.safe_load(f) or {}

    phase_reqs = phase_map.get("phase_requirements", {}).get(phase_id, {}).get("reqs", [])
    if not phase_reqs:
        print(f"  ℹ️  Phase {phase_id} has no REQs to verify")
        return True

    # Run full verifier, then filter results for this phase
    state = load_state()
    artifact = state.get("artifact_path") if state else None

    # G9 (review V4 Flash): trước đây phase 6 cũng chỉ chạy command → mọi artifact check
    # SKIP → "verify per-phase" là hình thức. Phase 6 đã có artifact đầy đủ (dashboard
    # build xong) → gọi verifier chính, lọc theo phase map.
    if phase_id == "phase6_dashboard" and artifact and os.path.exists(artifact):
        import sys as _sys
        verifier_path = os.path.join(SKILL_DIR, "scripts", "independent_verifier.py")
        r = subprocess.run([_sys.executable, verifier_path, TICKER, artifact],
                           capture_output=True, text=True, timeout=300)
        # Lọc output chỉ lấy REQ thuộc phase này
        phase_set = set(phase_reqs)
        full_pass = True
        for line in r.stdout.splitlines():
            for rid in phase_set:
                if rid in line and ("PASS" in line or "FAIL" in line or "ADVISORY" in line):
                    print(f"  {line.strip()}")
                    if "FAIL" in line:
                        full_pass = False
                    break
        # advisory (WARN) không block deploy → vẫn pass
        return full_pass

    # For pre-deploy phases (0-5), artifact may not exist yet
    # Run command-based REQs only
    req_file = os.path.join(SKILL_DIR, "requirements.yaml")
    with open(req_file) as f:
        req_data = yaml.safe_load(f)

    all_pass = True
    checked = 0  # P0-03 (Wave 1): đếm REQ thực sự được check — SKIP/deferred không đủ quyền
    for req in req_data.get("requirements", []):
        if req["id"] not in phase_reqs:
            continue
        method = req["verification"]["method"]
        if method == "command":
            checked += 1
            # P1-03 (Wave 1): dùng CHUNG verification engine của verifier (verify_command)
            # — expect_exit/expect_min/expect_max cùng một cách diễn giải, không duy trì
            # hai bộ semantics riêng (runner cũ chỉ so exit code, bỏ qua expect_min/max).
            try:
                import importlib.util as _ilu
                _spec = _ilu.spec_from_file_location(
                    "indep_verifier", os.path.join(SKILL_DIR, "scripts", "independent_verifier.py"))
                _vm = _ilu.module_from_spec(_spec)
                _spec.loader.exec_module(_vm)
                _vm.TICKER = TICKER
                _vm.REPORT = artifact or ""
                # html=None: command REQ (sponsor) không cần artifact; $JS_FILE không dùng ở đây
                passed, ev = _vm.verify_command(req, None)
                if not passed:
                    detail = ev.get("value", ev.get("exit_code", ""))
                    print(f"  ❌ {req['id']} FAIL: {req['text'][:60]} (evidence: {detail})")
                    all_pass = False
                else:
                    print(f"  ✅ {req['id']} PASS: {req['text'][:60]}")
            except Exception as e:
                print(f"  ❌ {req['id']} ERROR: {e}")
                all_pass = False
        else:
            print(f"  ⏭️  {req['id']} DEFERRED (artifact check, verify ở Phase 6/7)")

    # P0-03: phase chỉ có REQ deferred (0 check thật) → KHÔNG được completed.
    # Trạng thái do agent ghi trong task-state sẽ được REQ-068 kiểm (result keys tối thiểu).
    if checked == 0:
        print(f"  ⚠️  Phase {phase_id}: 0 REQ check được ở pre-deploy (tất cả deferred) — "
              f"KHÔNG tự ghi completed; chờ final verify Phase 6/7")
        return False

    return all_pass


def run_single_phase(phase_id, prompt_path):
    """Run one phase: print prompt for agent + verify after."""
    print(f"\n{'='*60}")
    print(f"  PHASE: {phase_id}")
    print(f"{'='*60}\n")

    prompt = read_phase_prompt(prompt_path)
    prompt = prompt.replace("[TICKER]", TICKER).replace("[WORK_DIR]", WORK_DIR)

    print("📋 PHASE PROMPT (agent executes this):")
    print("─" * 60)
    print(prompt)
    print("─" * 60)

    # Check if phase already completed
    state = load_state()
    if state:
        phase_status = state.get("phases", {}).get(phase_id, {}).get("status", "pending")
        if phase_status == "completed":
            print(f"\n✅ Phase {phase_id} already completed")

    # Verify phase REQs
    print(f"\n🔍 VERIFYING Phase {phase_id}...")
    passed = verify_phase(phase_id)

    if passed:
        mark_phase_completed(phase_id)  # P4: tự ghi status (không phụ thuộc agent)
        print(f"\n✅ Phase {phase_id} VERIFIED + marked completed — ready for next phase")
        return True
    else:
        print(f"\n❌ Phase {phase_id} FAILED — fix before proceeding")
        return False


def main():
    state = load_state()
    if not state:
        print("❌ Task state not found. Run: python3 scripts/init_task_state.py [TICKER] [WORK_DIR]")
        sys.exit(1)

    print(f"\n{'='*60}")
    print(f"  Equity Research v2 — {TICKER}")
    print(f"  Work dir: {WORK_DIR}")
    print(f"  Current phase: {state.get('phase', 'init')}")
    print(f"{'='*60}")

    if PHASE_ARG == "--all":
        # Run all phases in sequence
        for phase_id, prompt_path in PHASES:
            passed = run_single_phase(phase_id, prompt_path)
            if not passed:
                print(f"\n🛑 PIPELINE BLOCKED at {phase_id}")
                print(f"   Fix issues, then re-run: python3 run_phase.py {TICKER} {WORK_DIR} {phase_id}")
                sys.exit(1)
        print(f"\n🎉 ALL PHASES COMPLETE — report ready for deploy")
    else:
        # Run single phase
        phase_found = False
        for phase_id, prompt_path in PHASES:
            if phase_id == PHASE_ARG or phase_id.startswith(PHASE_ARG):
                phase_found = True
                passed = run_single_phase(phase_id, prompt_path)
                if not passed:
                    sys.exit(1)
                break
        if not phase_found:
            print(f"❌ Unknown phase: {PHASE_ARG}")
            print(f"   Available: {[p[0] for p in PHASES]}")
            sys.exit(1)


if __name__ == "__main__":
    main()
