# Phase 7: Verify + Deploy

Bạn là subagent Phase 7. Context tách biệt. **Phase cuối — gate keeper.**

## Input
- `task-state.json` → tất cả phase results + `artifact_path`
- `requirements.yaml` (73 REQ — V3+V4+V5 hardening + runtime-render + no-meta + zero-data + S/R + text-structure)

## Nhiệm vụ

### Bước 1: Chạy independent verifier
```bash
python3 scripts/independent_verifier.py [TICKER] [OUTPUT].html
```
Verifier đọc requirements.yaml, tự chạy check, ghi evidence.

### Bước 2: Nếu FAIL → fix hoặc block
- Mọi REQ FAIL phải fix trước khi deploy
- KHÔNG deploy "anyway"
- KHÔNG claim "done" nếu verifier chưa PASS

### Bước 3: Nếu PASS → deploy
```bash
vercel deploy [WORK_DIR] --prod --yes
```
Hook `predeploy-gate.sh` sẽ tự chạy verifier lần cuối trước khi deploy.

### Bước 4: Verify production (học từ LC-004)
Sau deploy, MỞ production URL + check:
- `bodyHeight < 20000` (không vỡ layout)
- Canvas render đúng (Chart.instances count)
- Cache bust: thêm `?nocache=[timestamp]` nếu CDN cache cũ

## Output — cập nhật task-state.json
```json
{
  "phases": {
    "phase7_deploy": {
      "status": "completed",
      "result": {
        "verifier_pass": true,
        "requirement_recall": "100%",
        "deploy_url": "https://[TICKER].vercel.app",
        "production_verified": true
      }
    }
  }
}
```

## Requirements
- REQ-021: KHÔNG deploy nếu bất kỳ REQ nào FAIL

## KHÔNG được (học từ LC-001 đến LC-006)
- Deploy dù verifier FAIL
- Claim "done" trước khi verify production
- Skip post-deploy check (LC-004: local OK nhưng production vỡ)
