#!/usr/bin/env python3
"""Test self-contained cho scope và exit code của predeploy gate."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
HOOK = ROOT / "scripts" / "hooks" / "predeploy-gate.sh"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def make_stub_skill(root: Path) -> None:
    scripts = root / "scripts"
    scripts.mkdir(parents=True)
    verifier = scripts / "independent_verifier.py"
    verifier.write_text(
        "#!/usr/bin/env python3\n"
        "import pathlib, sys\n"
        "text = pathlib.Path(sys.argv[2]).read_text()\n"
        "if 'MUTATED_FAIL' in text:\n"
        "    print('FAILED REQ: REQ-026')\n"
        "    print('1 requirement(s) failed')\n"
        "    print('requirement recall: 75/76 (98%)')\n"
        "    print('VERDICT: FAIL')\n"
        "    raise SystemExit(1)\n"
        "print('requirement recall: 76/76 (100%)')\n"
        "print('VERDICT: PASS')\n"
    )
    requirements = root / "requirements.yaml"
    requirements.write_text("requirements: []\n")
    (root / ".verifier-hash").write_text(
        f"verifier_sha256={sha256(verifier)}\n"
        f"requirements_sha256={sha256(requirements)}\n"
    )


def run_hook(skill: Path, project: Path, mode: str | None,
             command: str = "npx vercel deploy --prod") -> tuple[int, str]:
    env = os.environ.copy()
    env["EQUITY_SKILL_DIR"] = str(skill)
    env["EQUITY_GATE_LOG"] = str(skill / "gate-log.jsonl")
    env["ZCODE_PROJECT_DIR"] = str(project)
    if mode is None:
        env.pop("EQUITY_GATE_MODE", None)
    else:
        env["EQUITY_GATE_MODE"] = mode
    payload = json.dumps({"tool_input": {"command": command}})
    result = subprocess.run(
        ["bash", str(HOOK)], input=payload, capture_output=True,
        text=True, env=env, timeout=30,
    )
    return result.returncode, result.stderr


def main() -> int:
    temp = Path(tempfile.mkdtemp(prefix="public_gate_test_"))
    issues: list[str] = []
    try:
        skill = temp / "skill"
        make_stub_skill(skill)

        clean = temp / "clean"
        clean.mkdir()
        (clean / "AAA_Complete_Report.html").write_text("CLEAN")
        for mode in ("shadow", "advisory", "enforced", None):
            code, _ = run_hook(skill, clean, mode)
            if code != 0:
                issues.append(f"clean/{mode}: {code} != 0")

        failed = temp / "failed"
        failed.mkdir()
        (failed / "AAA_Complete_Report.html").write_text("MUTATED_FAIL")
        for mode in ("shadow", "advisory"):
            code, _ = run_hook(skill, failed, mode)
            if code != 0:
                issues.append(f"failed/{mode}: {code} != 0")
        for mode in ("enforced", None):
            code, stderr = run_hook(skill, failed, mode)
            if code != 2 or "DEPLOY BLOCKED" not in stderr:
                issues.append(f"failed/{mode}: expected block exit 2")

        missing = temp / "missing"
        missing.mkdir()
        (missing / "verified-dashboard-data.json").write_text("{}")
        code, _ = run_hook(skill, missing, "enforced")
        if code != 2:
            issues.append(f"missing artifact: {code} != 2")

        unrelated = temp / "unrelated"
        unrelated.mkdir()
        (unrelated / "index.html").write_text("<html>other project</html>")
        code, _ = run_hook(skill, unrelated, "enforced")
        if code != 0:
            issues.append(f"unrelated project: {code} != 0")

        code, _ = run_hook(skill, unrelated, "enforced", "npm run build")
        if code != 0:
            issues.append(f"non-vercel command: {code} != 0")

        verifier = skill / "scripts" / "independent_verifier.py"
        verifier.rename(verifier.with_suffix(".removed"))
        code, _ = run_hook(skill, clean, "enforced")
        if code != 2:
            issues.append(f"missing verifier: {code} != 2")
    finally:
        shutil.rmtree(temp, ignore_errors=True)

    if issues:
        print("DEPLOY GATE TEST: FAIL")
        for issue in issues:
            print(f"- {issue}")
        return 1
    print("DEPLOY GATE TEST: PASS (clean, mutation, missing, unrelated, default)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
