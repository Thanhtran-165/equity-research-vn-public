---
name: equity-research-vn
description: "Phân tích equity research đầy đủ cho cổ phiếu Việt Nam — kiến trúc subagent per phase (v3.2.0). Mỗi phase chạy trong context tách biệt, giao tiếp qua task-state.json, verify per-phase. 76 REQ verification (V3+V4+V5 hardening + VN100 cohort: runtime-render, no-meta, zero-data, S/R, text-structure, P/E chuẩn hóa). TRIGGER khi user gõ /equity-research-vn [TICKER]."
---

# equity-research-vn [TICKER]

## ĐỊNH VỊ (bắt buộc đọc trước — v3.2.0, cập nhật 2026-08-02)

Skill tạo **bằng chứng phân tích khách quan (evidence pack)** từ dữ liệu công khai —
**KHÔNG khuyến nghị mua/bán**. Mọi số liệu có nguồn (BCTC kiểm toán / vnstock / báo cáo
ngành), mọi claim bị verifier độc lập kiểm chứng 76 REQ. Quyết định đầu tư và trách
nhiệm thuộc về nhà đầu tư. Xem `DISCLAIMER.md`.

## Pipeline (9 phases, chạy tuần tự — phase 4 tách 4a/4b, FIX-12)

```
Phase 0: Sponsor detection     → phases/phase0-sponsor.md
Phase 1: Data collection       → phases/phase1-data.md
Phase 2: Fundamental analysis  → phases/phase2-fundamental.md
Phase 3: Valuation             → phases/phase3-valuation.md
Phase 4a: Technical ACTIVE     → phases/phase4a-tech-active.md
Phase 4b: Technical PROFILE    → phases/phase4b-tech-profile.md
Phase 5: News digest           → phases/phase5-news.md
Phase 6: Dashboard build       → phases/phase6-dashboard.md
Phase 7: Verify + deploy       → phases/phase7-deploy.md
```

## Cách chạy

```bash
# 1. Init task state
python3 scripts/init_task_state.py [TICKER] [WORK_DIR]

# 2. Chạy từng phase tuần tự — mỗi phase:
#    - Đọc phases/phaseN-xxx.md (prompt riêng cho phase đó)
#    - Đọc [WORK_DIR]/.task-state/task-state.json (input từ phase trước)
#    - Execute
#    - Ghi output vào task-state.json
#    - Verifier check REQ cho phase đó → BLOCK nếu FAIL

# 3. Final verify + deploy
python3 scripts/independent_verifier.py [TICKER] [OUTPUT].html
# PASS → deploy (hook tự verify)
# FAIL → fix trước
```

## Nguyên tắc cốt lõi

1. **Mỗi phase chỉ biết spec của nó** — đọc `phases/phaseN-xxx.md`, không đọc toàn bộ pipeline
2. **Giao tiếp qua file** — task-state.json, không qua conversation context
3. **Verify per-phase** — verifier check REQ sau mỗi phase, block sớm nếu fail
4. **Thin orchestrator** — SKILL.md này chỉ ~80 dòng, detail nằm trong phase files

## Requirements

Xem `requirements.yaml` (76 REQ — index tự sinh tại `references/req_index.md`, KHÔNG copy tay). Mỗi REQ mapped tới 1 phase trong `requirements-phase-map.yaml`.

## Khác v1

| v1 | v2 (này) |
|---|---|
| 486 dòng monolith | 80 dòng thin + 9 phase files |
| 1 agent giữ tất cả | Subagent per phase (context tách) |
| Verify 1 lần cuối | Verify sau mỗi phase |
| Bỏ sót ở handoff | Handoff qua task-state.json |

## Output

1. `[TICKER]_Complete_Report.html` (22 sections canonical)
2. `.task-state/evidence/` (76 evidence files — 1 file/REQ)
3. Vercel URL (nếu deploy pass)
