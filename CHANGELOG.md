## verification-layer 0.3.0 — 2026-07-31 (V5 Wave — data provenance & narrative integrity)

### added (8 new REQs — gap còn lại sau V3/V4)
- **REQ-059** `data_provenance_check` (critical): verifier tự spot-check revenue vs source-pack CSV / API vnstock live (±10%); price bắt buộc có price_fetched_at ở data level; task-state phase1 phải log data_source; peers.json phải có source; contract phải có _provenance. (Chống bịa CẢ data files lẫn report — GIGO.)
- **REQ-060** `internal_identity_check` (high): cross-footing — PE×EPS ≈ giá, PB×BVPS ≈ giá, vốn hóa ≈ giá×cổ phiếu, EPS ≈ NPAT/shares, contract price ≈ financials price (±5%).
- **REQ-061** `derived_metrics_recompute_check` (high): ROE/ROA/net margin/YoY growth/vốn hóa claims phải recompute từ financials.json + balance_sheet.json (±5% hoặc ±1pp).
- **REQ-063** `valuation_methods_check` (high): method định giá (EV/EBITDA, P/CF, P/S, DCF, Graham...) nhắc trong narrative nhưng không giá trị và không N/A → FAIL; Graham recompute ±5%.
- **REQ-064** `trend_consistency_check` (high): từ ngữ tăng/giảm gần metric phải cùng dấu dữ liệu (overall hoặc theo năm).
- **REQ-065** `verdict_consistency_check` (medium): tone exec/thesis phải cùng dấu upside/downside từ valuation targets.
- **REQ-066** `api_fallback_check` (high): phase 0 phải log api_source; community tier phải được flag trong report.
- **REQ-067** `fiscal_year_check` (medium): fiscal_year_type (calendar|custom) phải log; custom → narrative ghi rõ "năm tài chính".

### hardened
- **REQ-010** token check: pattern `{{[A-Z_0-9]+}}` → `{{[^}]+}}` (bắt cả token chữ thường)
- **REQ-007** non_advice: bỏ vacuously-pass — sec-tech-profile bắt buộc tồn tại
- **REQ-031** drawdown_source: V3b guard — có max_drawdown data mà sec-risk không định lượng % → FAIL

---
## verification-layer 0.2.0 — 2026-07-31 (V3 Hardening Wave)

### added (15 new REQs — verifier scope gaps)
- **REQ-044** `news_authenticity_check` (critical): mỗi article phải có URL/source_name; ≥50% coverage
- **REQ-045** `forecast_source_check` (critical): forward-looking claims phải cite nguồn (ĐHCĐ, KHKD, CTCK)
- **REQ-046** `technical_indicator_verify` (high): RSI/MA50/MACD recompute từ price data thật
- **REQ-047** `macro_data_citation_check` (high): GDP/CPI/FDI/lãi suất phải cite (GSO, NHNN, WB)
- **REQ-048** `management_claim_check` (high): claim lãnh đạo/cổ đông phải có nguồn hoặc disclaimer
- **REQ-049** `historical_return_verify` (high): claim "tăng X% trong Y năm" verify từ price data
- **REQ-050** `comparison_baseline_check` (medium): so sánh phải có baseline cụ thể
- **REQ-051** `unit_consistency_check` (medium): thống nhất đơn vị tỷ đồng toàn dashboard
- **REQ-052** `liquidity_check` (medium): dashboard nên có thanh khoản nếu có data
- **REQ-053** `audit_opinion_check` (high): BCTC ngoại trừ → dashboard phải có disclaimer
- **REQ-054** `causal_chain_evidence_check` (high): chuỗi nhân quả phải có evidence
- **REQ-055** `vague_language_check` (medium): >15 hedging phrases → WARN
- **REQ-056** `timeframe_consistency_check` (high): không cherry-pick QoQ không kèm YoY
- **REQ-057** `dividend_claim_check` (medium): claim cổ tức phải có data hoặc cite
- **REQ-058** `support_resistance_method_check` (medium): S/R levels phải kèm method

### added (regression fix)
- **REQ-062** `period_integrity_check` (critical): port từ v1.0.1 period_integrity_gate.py (6 sub-gates chống đảo kỳ ERVN-PERIOD-001)

### hardened (6 existing REQs)
- **REQ-032** peer_provenance: key-specific ticker matching (PATH A) + any-match fallback (PATH B)
- **REQ-033** cross_section_consistency: thêm internal section consistency cho unanchored claims
- **REQ-029** source_citation: tolerance 5→3; key metrics require DIRECT source (không uncertainty marker)
- **REQ-037** tech_recompute: thêm RSI quick sanity check escalated to FAIL
- **REQ-031** drawdown_source: vacuous-pass guard — tech-profile bàn về rủi ro nhưng không có drawdown data → FAIL
- **REQ-041** news_window: sample URL HEAD check (WARN only)

### updated
- `requirements.yaml`: 43→59 REQ total
- `requirements-phase-map.yaml`: map tất cả REQ mới vào phase
- `VERSION`: bump 3.0.1→3.1.0

### total coverage
- critical: 15 REQ (+3 mới)
- high: 29 REQ (+6 mới)
- medium: 15 REQ (+5 mới, +1 hardened)
- **total: 59 REQ**

## verification-layer 0.1.4 — 2026-07-13 (controlled merge of P4 REQ-007 negation-aware check)

### fixed (verification/enforcement only)
- **REQ-007 false-positive on negation/disclaimer context**: the old shell command `grep -ciE 'bullish|bearish|khuyến nghị mua|...'` blindly counted any occurrence of advisory words — including when they appeared in disclaimers like "không phải khuyến nghị mua/bán" (the model explicitly stating it's NOT advice). This caused 3/5 Cohort A‴ runs to FAIL despite containing valid disclaimers. Fixed with `verify_non_advice_check`:
  - Removes valid disclaimer sentences (negation patterns: "không phải khuyến nghị", "không cấu thành lời khuyên", "not investment advice", etc.) before checking.
  - Allows STRONG BUY/STRONG SELL when used as Tech Score verdict labels (machine-readable, not advice).
  - Only FAILs on actionable advice signals that remain AFTER disclaimer removal (nên mua, nhà đầu tư nên, điểm mua, chốt lời, etc.).
  - Handles disclaimer + real advice coexisting → FAIL (doesn't blanket-immunize the section).
  - Method changed from `command` (shell awk+grep) to `artifact_check` (Python with section-scoped extraction).

### validation (post-merge, fresh)
```yaml
req007_fixtures: 10/10
mutation_regression: 16/16
clean_control: PASS (specificity 1.0)
missed_critical_mutations: 0
wrong_reason_failures: 0
cohort_a_triple_prime_rescore: 4/5 PASS (was 2/5 — 3 false positives corrected)
remaining_fail: A-004 REQ-020 (div imbalance, 1/5 — residual variance)
```

### not labeled
- **NOT STABLE.** FUNCTIONAL_WITH_RESIDUAL_VARIANCE on CTD benchmark. REQ-020 (1/5) not yet recurring.

# CHANGELOG — equity-research-vn (verification/enforcement layer + phase prompts)

This file tracks the **verification/enforcement layer** (`scripts/independent_verifier.py` + `requirements.yaml`) AND **phase-prompt patches**, separate from the SKILL.md architecture version (v3.0).

## verification-layer 0.1.2 — 2026-07-13 (controlled merge of P2 REQ-025 valuation-extraction patch)

### fixed (verification/enforcement only)
- **REQ-025 Unicode `×` + Chart.js JS false-match (P2)**: the old global regex `P/E.*?([\d.]+)x` failed on reports using `×` (U+00D7 multiplication sign) instead of ASCII `x`, and false-matched Chart.js tokens (`pe: 'point', x: 100`) capturing `.` → `float('.')` parse failure. Fixed with `_extract_primary_multiple`:
  - Matches both `×` (Unicode) and `x` (ASCII); requires leading digit (`[\d,]+\.?\d*`); filters values >1000 (raw VND amounts).
  - **Semantic multi-section scope**: collects P/E candidates from `sec-valuation` + `sec-hero` + `sec-exec` (not global first-occurrence). Ensures the primary P/E in the hero KPI card is checked even when sec-valuation contains peer/projection values.
  - **Projection filtering**: excludes candidates labeled median/5Y/target/DCF/Graham/EV-EBITDA/P/CF (these are projected values, not the current multiple).
  - **Ambiguity abstention**: if multiple non-projection candidates with distinct values exist and none has a primary semantic marker (TTM/hiện tại/current/val-card) → returns None (AMBIGUOUS_PRIMARY_MULTIPLE) → REQ-025 FAILs. NEVER selects by computed-value match (that would be cherry-picking to PASS).
  - If all non-projection candidates agree → UNAMBIGUOUS → uses that value.
- **REQ-025 company-specific default fallback removed**: the old code used `equity_ty.get("2025", 45079)` (PNJ value) and `price.get("current_price", 68800)` as defaults. Now: missing data → explicit FAIL ("missing equity_ty or issue_share (no default fallback)"). No company-specific constants remain.
- **data-contract builder equity_ty**: `build_data_contract.py` now writes `equity_ty` (in tỷ VND) to `data/financials.json` for correct PB computation.

### validation (post-merge re-run, fresh audit — NOT inherited from candidate)
```yaml
p2_semantic_tests: 8/8
mutation_regression: 16/16 (P0 5/5 + P1 11/11)
clean_control: PASS (specificity 1.0)
missed_critical_mutations: 0
wrong_reason_failures: 0
ctd_artifact_req025: PASS (PE 3.91, PB 1.0)
note: "Results prove coverage of the current test suite. NOT STABLE."
```

### not labeled
- **NOT STABLE.** Verifier 0.1.2 passes the current 16-mutation + 8-semantic suite. Broader coverage (P2 watch-items: stale task-state, cross-run contamination, partial abstention) still pending.
- `agent_execution: NOT_ASSESSED` — Cohort A″ pending.

### versions
```yaml
verification_layer: 0.1.2
agent_eval_runner: 0.2.0 (in agent-eval/, not skill)
protocol: v0.3.0 (POST_REQ025_P2_PATCH)
```

## phase6-dashboard.md patch-1 — 2026-07-12 (controlled merge of Phase-6 output-contract patch)

### root cause (from Cohort A genuine-agent evidence: 5/5 narration, recall 39.3% σ=0)
Phase 6's prompt required `cp template` + `str.replace` token-fill — but the subagent has **no tool/bash channel** in the agent-eval runner's `invoke()` (single-message exchange). GLM-5.2 therefore narrated the steps ("I'll build the dashboard... Let me start by copying the template") instead of emitting the artifact. **Primary cause: harness capability mismatch** (no tool channel), not "lazy model" and not just prompt ambiguity.

### fixed (phase6-dashboard.md)
- **Layer 1 — output contract + inline template:** absolute contract (only `<!DOCTYPE html>`→`</html>`, no narration/markdown/fence); the runner injects `dashboard_template.html` (~17K tokens, within 1M context) into the prompt at `__TEMPLATE_INLINE_PLACEHOLDER__` so the model fills tokens and returns complete HTML in one response — replacing the tool-dependent workflow with direct generation.
- **Layer 2 — phase-local preflight gate (in agent-eval runner, NOT skill):** deterministic gate after phase6 inference: whitespace/attribute-order tolerant checks (DOCTYPE-start, `<section id="sec-">`, `const DATA=`, canvas/chart-wrap, no narration prefix, no fence); OUTPUT_TRUNCATED detection (max_tokens stop, missing `</html>`). On FAIL → retry phase6 (1 initial + max 2 recovery = 3 total), per-attempt artifacts preserved. This is the "tự sửa đúng nghĩa" mechanism — doesn't depend on model adherence.

### not labeled
- **NOT STABLE.** This patch's real-world effectiveness is **NOT yet proven** — it is validated only by 29 unit tests + 8 merge gates. Cohort A′ (5 genuine runs under protocol v0.2.0) will measure actual html_output_rate / narration_rate.
- verification-layer **0.1.1 unchanged** — no verifier or requirements change.
- Success criterion (per owner): `html_output_rate=1.0, narration_rate=0.0, invalid_output_blocked=true`. If HTML emitted but content REQs still fail, the patch solved the *wrong-output-type defect* and content hardening is a separate cycle.

### versions
```yaml
equity_research_vn_skill: phase6-dashboard.md patch-1 (architecture v3.0 unchanged)
verification_layer: 0.1.1 (UNCHANGED)
agent_eval_runner: 0.2.0 (in agent-eval/, not skill)
analyzer: 0.2.0 (in agent-eval/)
protocol: v0.2.0 (d10ea915…, POST_PHASE6_PATCH)
```

### audit trail
- Baseline `PRE_PHASE6_PATCH_COHORT_A` preserved (5 runs, recall 39.3% σ=0, 100% narration).
- Pre-merge backup + candidate manifest at `agent-eval/baseline-pre-phase6-merge/`.

## verification-layer 0.1.1 — 2026-07-12 (controlled merge of P1 audit fixes)

### fixed (verification/enforcement only)
- **REQ-022 data-accuracy (PATCH P1-1)**: replaced global any-number matching with structured, year-bound verification. PATH A reads the report's `DATA` JS object arrays (`years`, `revenue`, `netProfit`, `eps`, `totalAssets`, `equity`) and compares the exact year-indexed value to ground truth within tolerance — eliminates sibling-value substitution (a corrupted year masked by another year's value matching in a shared context window). PATH B (context-anchored match around business synonyms: `Doanh thu`, `LNST`, `Tổng tài sản`, `Vốn chủ sở hữu`, ±400 chars) remains as fallback for fields not in the DATA object. Note: PATH B is a heuristic (P2 will add dedicated fallback-path mutations covering adjacent years / same-window collisions); PATH A stays the preferred path.
- **REQ-027 external-claim flag (PATCH P1-2)**: inverted to per-claim proximity logic. Each matching external claim (WCM/MCH/store-count patterns) MUST have a flag word (`ước tính`/`estimate`) within an adjacent ±200-char window. Previously passed if ANY flag existed ANYWHERE → a far-away flag masked an unflagged claim. No claims → PASS; claims present → PASS only if every claim has an adjacent flag.

### validation (post-merge re-run, fresh audit — NOT inherited from candidate)
```yaml
clean_control: 1/1 PASS (specificity 1.0)
p0_mutations_correctly_detected: 5/5
p1_mutations_correctly_detected: 11/11 (incl 2 holdouts of different form)
total_valid_oracles: 16/16
wrong_reason_failures: 0
missed_critical_mutations: 0
correct_detection_rate: 1.0
note: "Results prove coverage of the CURRENT combined P0+P1+holdout suite only. They do NOT prove absolute verifier correctness — broader coverage pending in P2."
```

### not labeled
- **NOT STABLE** — verification layer passes the current combined suite, but the skill as a whole is not STABLE.
- `agent_execution: NOT_ASSESSED` — no genuine agent runs; agent stability testing blocked until merged 0.1.1 passes a fresh combined suite (done, this release).

### pending (P2 watch-items)
- PATH B fallback heuristic: add mutations covering two-nears-adjacent / same-window collisions / unit ambiguity.
- Additive-oracle consumer-path assertion: distinguish "mutation added to file" from "mutation flowed through the validator's input path" (record `validator_input_contains_mutation` + `expected_pattern_matched`).
- P2 mutation families still unexplored: stale task-state, cross-run contamination, partial abstention, deeper source-claim variants.

### audit trail
- Audit baseline (0.1.0) preserved: `p1-cycle/equity-research-vn-backup-pre-p1/` + tag `equity-research-vn-merged-0.1.0-pre-p1`.
- Audit performed by `skill-harness-evaluator` v0.1.0.

## verification-layer 0.1.0 — 2026-07-12 (controlled merge of P0 audit fixes)

### fixed (verification/enforcement only)
- **REQ-028 false-positive** on valid deployed artifacts: `verify_chart_runtime_check` now distinguishes unconditional canvas refs from conditional (`if ($(id))`) and fallback (`$(primary) || $(fallback)`) refs. A few optional/single required canvases absent → advisory WARN, not deploy-blocking FAIL. Critical FAIL reserved for: duplicate IDs, no DATA, no Chart.js, canvas-after-body, or >30% required canvases missing.
- **REQ-009 canonical signal coverage**: `min_canonical_match` tightened 15→20, plus `required_signal_sections: [sec-hero, sec-exec, sec-valuation]` each individually mandatory (not just counted). Count-based proxy alone was gameable.
- **REQ-025 valuation multiples**: `verify_valuation_recompute` now checks every P/E occurrence in a primary valuation context (val-card / current-price), not first-match regex. Peer/historical/projected multiples remain advisory.
- **REQ-021 evidence provenance binding**: writes `evidence/REQ-021.json` with `{source_run_id, source_artifact, source_artifact_sha256, evidence_generated_after_validation, unresolved_required_failures, all_requirements_pass, requirement_state_at_eval}`. Deploy evidence is now bound to the current run + current artifact + post-validation timestamp — closes the stale/cross-run-evidence provenance gap.

### validation (post-merge re-run, fresh audit — NOT inherited from candidate)
```yaml
clean_controls: 1/1 PASS
mutations_correctly_detected: 5/5 (all valid oracles)
wrong_reason_failures: 0
specificity_rate: 1.0
false_positive_count: 0
correct_detection_rate: 1.0
missed_critical_mutations: 0
note: "Results apply ONLY to the current 5-mutation suite. Broader P1 coverage pending."
```

### not labeled
- **NOT STABLE** — verification layer reaches FUNCTIONAL_OR_ROBUST on the current suite, but the skill as a whole is not STABLE.
- `agent_execution: NOT_ASSESSED` — no genuine agent runs; agent stability testing blocked until P1 mutation expansion completes.

### pending
- P1 mutation expansion: capex, evidence-provenance, runtime-chart, source-claim, partial-abstention, stale-state, cross-run-contamination families. At least one mutation per important validator.
- After P1: genuine agent stability tests (only on a verifier deemed reliable).

### audit trail
- Audit baseline preserved: `skill-harness-evaluator-work/equity-research-vn-backup-pre-p0-merge/` (pre-merge verifier + requirements, version tag `equity-research-vn-pre-p0-audit-baseline`).
- Audit performed by `skill-harness-evaluator` v0.1.0.
