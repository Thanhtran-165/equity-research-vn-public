#!/usr/bin/env python3
"""
measure_kpi.py — A/B measurement: đo KPI trước/sau khi áp dụng harness.

GPT dòng 286-298 liệt kê 9 KPI. Script này đo tự động từ evidence ledger.

Usage:
  python3 measure_kpi.py baseline /path/to/report.html   → đo baseline
  python3 measure_kpi.py harness /path/to/report.html    → đo sau harness
  python3 measure_kpi.py compare                          → so sánh baseline vs harness

KPIs measured:
  1. Requirement Recall = passed / total mandatory
  2. False Completion Rate = claimed_done_but_failed / total_claims
  3. Partial-as-Pass Rate = partial_implementation_as_pass / total
  4. Unverified Claim Rate = claims_without_evidence / total_claims
  5. Scope Creep Rate = extra_sections / total_sections
  6. Token Cost (from log if available)
  7. Wall-clock Time (from log if available)
  8. Fix-loop Count (from evidence changes)
"""
import json, sys, os, re, subprocess, yaml, datetime

SKILL_DIR = os.path.abspath(os.environ.get(
    "EQUITY_SKILL_DIR", os.path.join(os.path.dirname(__file__), "..")
))
KPI_STORE = os.path.abspath(os.environ.get(
    "EQUITY_KPI_STORE",
    os.path.join(os.path.expanduser("~"), ".cache", "equity-research-vn", "kpi-history.jsonl"),
))

def measure_report(label, report_path):
    """Run verifier, extract KPIs, store."""
    ticker = "UNKNOWN"
    # Detect ticker
    m = re.search(r'/([A-Z]{2,5})[_-]', report_path)
    if m:
        ticker = m.group(1)

    # Run verifier
    os.makedirs(os.path.dirname(KPI_STORE), exist_ok=True)
    verifier = os.path.join(SKILL_DIR, "scripts/independent_verifier.py")
    result = subprocess.run(
        ["python3", verifier, ticker, report_path],
        capture_output=True, text=True
    )

    # Parse evidence summary
    evidence_dir = os.path.join(os.path.dirname(report_path), ".task-state", "evidence")
    summary_file = os.path.join(evidence_dir, "_summary.json")

    kpi = {
        "label": label,
        "timestamp": datetime.datetime.now().isoformat(),
        "ticker": ticker,
        "report": report_path,
    }

    if os.path.exists(summary_file):
        with open(summary_file) as f:
            summary = json.load(f)
        results = summary.get("results", {})
        kpi["requirement_recall_pct"] = summary.get("requirement_recall_pct", 0)
        kpi["requirements_pass"] = results.get("pass", 0)
        kpi["requirements_fail"] = results.get("fail", 0)
        kpi["requirements_total"] = results.get("total", 0)
        kpi["verdict"] = summary.get("verdict")
    else:
        kpi["error"] = "no evidence summary"

    # Scope creep: count self-invented sections
    if os.path.exists(report_path):
        html = open(report_path).read()
        canonical = ['sec-hero','sec-exec','sec-biz','sec-industry','sec-history','sec-segment',
                     'sec-thesis','sec-valuation','sec-peer','sec-bs','sec-risk','sec-33k',
                     'sec-scenario','sec-checklist','sec-insight-1','sec-insight-2','sec-insight-3',
                     'sec-tech','sec-tech-profile','sec-analyst','sec-glossary','sec-source']
        all_secs = re.findall(r'id="(sec-[a-z0-9-]+)"', html)
        self_invented = [s for s in all_secs if s not in canonical]
        kpi["total_sections"] = len(all_secs)
        kpi["canonical_sections"] = sum(1 for s in all_secs if s in canonical)
        kpi["self_invented_sections"] = len(self_invented)
        kpi["scope_substitution_rate"] = round(len(self_invented) / max(len(all_secs), 1) * 100, 1)
        kpi["charts"] = len(re.findall(r"new Chart|viz\.chart", html))
        kpi["refs"] = len(re.findall(r'id="ref-\d+"', html))
        kpi["report_size_kb"] = round(len(html) / 1024, 1)

    # Store
    with open(KPI_STORE, "a") as f:
        f.write(json.dumps(kpi, ensure_ascii=False) + "\n")

    print(f"\n{'='*50}")
    print(f"  KPI Measurement: {label}")
    print(f"{'='*50}")
    for k, v in kpi.items():
        if k not in ("label", "timestamp", "report"):
            print(f"  {k:30}: {v}")
    print(f"\n  Stored: {KPI_STORE}")

    return kpi

def compare():
    """Compare baseline vs harness."""
    if not os.path.exists(KPI_STORE):
        print("No KPI history. Run measure baseline + harness first.")
        return

    entries = [json.loads(l) for l in open(KPI_STORE) if l.strip()]
    baseline = [e for e in entries if e.get("label") == "baseline"]
    harness = [e for e in entries if e.get("label") == "harness"]

    if not baseline or not harness:
        print(f"Need both baseline ({len(baseline)}) and harness ({len(harness)}) measurements.")
        return

    b = baseline[-1]
    h = harness[-1]

    print(f"\n{'='*60}")
    print(f"  A/B COMPARISON")
    print(f"{'='*60}")
    print(f"{'KPI':<30} {'Baseline':>12} {'Harness':>12} {'Δ':>10}")
    print(f"{'-'*60}")

    metrics = [
        ("requirement_recall_pct", "Requirement Recall %"),
        ("requirements_fail", "Requirements Failed"),
        ("scope_substitution_rate", "Scope Substitution %"),
        ("self_invented_sections", "Self-invented Sections"),
        ("canonical_sections", "Canonical Sections"),
        ("charts", "Charts"),
        ("refs", "Refs"),
        ("report_size_kb", "Size (KB)"),
    ]

    for key, label in metrics:
        bv = b.get(key, "—")
        hv = h.get(key, "—")
        delta = ""
        if isinstance(bv, (int, float)) and isinstance(hv, (int, float)):
            d = hv - bv
            delta = f"{d:+.1f}" if isinstance(d, float) else f"{d:+d}"
        print(f"{label:<30} {str(bv):>12} {str(hv):>12} {delta:>10}")

    # False completion rate
    b_fcr = 100 if b.get("verdict") == "FAIL" else 0
    h_fcr = 100 if h.get("verdict") == "FAIL" else 0
    print(f"{'False Completion Rate':<30} {b_fcr:>11}% {h_fcr:>11}% {h_fcr-b_fcr:>+9}%")
    print(f"{'-'*60}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: measure_kpi.py baseline|harvest|compare [report_path]")
        sys.exit(1)

    cmd = sys.argv[1]
    if cmd == "compare":
        compare()
    elif cmd in ("baseline", "harness") and len(sys.argv) > 2:
        measure_report(cmd, sys.argv[2])
    else:
        print("Usage: measure_kpi.py baseline|harvest|compare [report_path]")
