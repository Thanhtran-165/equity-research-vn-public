#!/usr/bin/env bash
# =========================================================================
# predeploy-gate.sh — PreToolUse hook v3
#
# Rollout 3 cấp (GPT dòng 352-357):
#   shadow   = log only, never block (bắt false positive không hại agent)
#   advisory = warn agent nhưng cho deploy (agent thấy warning)
#   enforced = block deploy (exit 2)
#
# P0-05 (Sol 2026-08-09): Default = ENFORCED — fail-closed mặc định
# Đổi mode: edit ROLLOUT_MODE bên dưới hoặc set env var
# =========================================================================

set -uo pipefail

ROLLOUT_MODE="${EQUITY_GATE_MODE:-enforced}"  # shadow | advisory | enforced

strip_ansi() {
    sed 's/\x1b\[[0-9;]*m//g'
}

parse_fail_count() {
    strip_ansi | grep -oE '[0-9]+ requirement\(s\) failed' | grep -oE '^[0-9]+' | head -1
}

# Test seam: parses stdin only; normal PreToolUse never supplies this argument.
if [ "${1:-}" = "--self-test-parser" ]; then
    PARSED=$(parse_fail_count || true)
    printf '%s\n' "${PARSED:-0}"
    exit 0
fi

# P0-05 (Wave 1): enforced = fail-closed — mọi điều kiện mơ hồ phải BLOCK deploy.
# shadow/advisory giữ nguyên hành vi (allow + log) để đo false positive.
fail_closed() {
    local reason="$1"
    if [ "$ROLLOUT_MODE" = "enforced" ]; then
        echo "🚫 DEPLOY BLOCKED (enforced): $reason" >&2
        exit 2
    fi
    echo "⚠️ [${ROLLOUT_MODE}] $reason — cho phép nhưng ghi log" >&2
}

# Đọc command từ stdin
INPUT=$(cat)
COMMAND=$(echo "$INPUT" | python3 -c "
import json, sys
try:
    d = json.load(sys.stdin)
    ti = d.get('tool_input') or d.get('toolInput') or {}
    print(ti.get('command','') if isinstance(ti, dict) else '')
except: print('')
" 2>/dev/null || echo "") || fail_closed "Không đọc được PreToolUse input (JSON hỏng) — không biết lệnh deploy nào"

# Chỉ kích hoạt cho vercel deploy
if ! echo "$COMMAND" | grep -qiE "vercel.*deploy|vercel.*--prod"; then
    exit 0
fi

PROJECT_DIR="${ZCODE_PROJECT_DIR:-${CLAUDE_PROJECT_DIR:-$(pwd)}}"

# P0-3 v2 (Sol 2026-08-10): xác định scope TRƯỚC khi nhìn index.html.
# index.html là artifact chung của mọi dự án Vercel, tuyệt đối không phải marker VNALL.
IS_EQUITY_PROJECT=0
if [ -d "$PROJECT_DIR/data/vnall" ] || [ -f "$PROJECT_DIR/verified-dashboard-data.json" ] \
   || [ -d "$PROJECT_DIR/.task-state" ] \
   || compgen -G "$PROJECT_DIR/*_Complete_Report.html" >/dev/null; then
    IS_EQUITY_PROJECT=1
fi
if [ "$IS_EQUITY_PROJECT" -ne 1 ]; then
    echo "👁️ SKIP: project không phải equity-research-vn — bypass hook" >&2
    exit 0
fi

# Chỉ sau khi scope đã khóa mới tìm artifact deploy.
REPORT=""
for candidate in \
    "$PROJECT_DIR"/*_Complete_Report.html \
    "$PROJECT_DIR"/index.html; do
    if [ -f "$candidate" ] 2>/dev/null; then
        REPORT="$candidate"
        break
    fi
done

if [ -z "$REPORT" ]; then
    # enforced: project VNALL thiếu artifact = fail closed (không biết deploy cái gì)
    fail_closed "Không tìm thấy HTML report trong $PROJECT_DIR (glob *_Complete_Report.html/index.html)"
    exit 0
fi

# Tìm ticker
TICKER=$(basename "$REPORT" | grep -oE '[A-Z]{2,5}_' | head -1 | tr -d '_' || true)
if [ -z "$TICKER" ]; then
    TICKER=$(basename "$PROJECT_DIR" | grep -oE '^[a-zA-Z]{2,5}' | head -1 | tr 'a-z' 'A-Z' || true)
fi
if [ -z "$TICKER" ]; then
    # enforced: ticker không xác định = không biết verify mã nào
    fail_closed "Không suy ra được TICKER từ report/project dir — không mặc định MSN"
    TICKER="MSN"  # chỉ dùng ở shadow/advisory
fi

SKILL_ROOT="${EQUITY_SKILL_DIR:-$HOME/.zcode/skills/equity-research-vn}"
VERIFIER="$SKILL_ROOT/scripts/independent_verifier.py"
HASH_FILE="$SKILL_ROOT/.verifier-hash"

# ═══ TAMPER CHECK (Gap 1 fix) ═══
# Verify verifier + requirements không bị sửa
if [ ! -f "$HASH_FILE" ]; then
    # W4 (Wave 4): thiếu hash = không thể phát hiện tamper → enforced fail-closed
    fail_closed "Thiếu $HASH_FILE — không kiểm tra được verifier bị sửa chưa"
fi
if [ -f "$HASH_FILE" ]; then
    CURRENT_V_HASH=$(shasum -a 256 "$VERIFIER" 2>/dev/null | cut -d' ' -f1)
    EXPECTED_V_HASH=$(grep verifier_sha256 "$HASH_FILE" 2>/dev/null | cut -d= -f2)

    REQ_FILE_HASH="$SKILL_ROOT/requirements.yaml"
    CURRENT_R_HASH=$(shasum -a 256 "$REQ_FILE_HASH" 2>/dev/null | cut -d' ' -f1)
    EXPECTED_R_HASH=$(grep requirements_sha256 "$HASH_FILE" 2>/dev/null | cut -d= -f2)
    if [ -n "$EXPECTED_R_HASH" ] && [ "$CURRENT_R_HASH" != "$EXPECTED_R_HASH" ]; then
        echo "🚨 TAMPER: requirements.yaml hash mismatch (enforced → block)" >&2
        if [ "$ROLLOUT_MODE" = "enforced" ]; then exit 2; fi
    fi
    if [ -n "$EXPECTED_V_HASH" ] && [ "$CURRENT_V_HASH" != "$EXPECTED_V_HASH" ]; then
        echo "🚨 TAMPER DETECTED: independent_verifier.py hash mismatch!" >&2
        echo "   Expected: $EXPECTED_V_HASH" >&2
        echo "   Actual:   $CURRENT_V_HASH" >&2
        echo "   → Agent may have modified verifier to weaken it." >&2
        echo "   → In enforced mode, this would BLOCK deploy." >&2
        # Even in shadow mode, tamper = suspicious
        if [ "$ROLLOUT_MODE" = "enforced" ]; then
            exit 2
        fi
    fi
fi

if [ ! -f "$VERIFIER" ]; then
    fail_closed "Không tìm thấy verifier: $VERIFIER — không thể verify"
    exit 0
fi

# Chạy verifier
VERIFIER_OUTPUT=$(python3 "$VERIFIER" "$TICKER" "$REPORT" 2>&1)
VERIFIER_EXIT=$?

# Parse recall + verdict + fails (P1-2: strip ANSI before grep; extract fail count not REQ id)
VERIFIER_CLEAN=$(echo "$VERIFIER_OUTPUT" | strip_ansi)
RECALL=$(echo "$VERIFIER_CLEAN" | grep "recall" | grep -oE "[0-9]+%" | head -1)
VERDICT=$(echo "$VERIFIER_CLEAN" | grep "VERDICT" | grep -oE "PASS|FAIL" | head -1)
FAILS=$(echo "$VERIFIER_CLEAN" | parse_fail_count)

# Log gate run (all modes)
LOG_FILE="${EQUITY_GATE_LOG:-$HOME/.cache/equity-research-vn/gate-log.jsonl}"
mkdir -p "$(dirname "$LOG_FILE")"
echo "{\"ts\":\"$(date -Iseconds)\",\"mode\":\"$ROLLOUT_MODE\",\"ticker\":\"$TICKER\",\"report\":\"$REPORT\",\"verdict\":\"$VERDICT\",\"recall\":\"$RECALL\",\"fails\":${FAILS:-0}}" >> "$LOG_FILE"

# ═══ ROLLOUT MODE BEHAVIOR ═══

if [ "$VERIFIER_EXIT" -eq 0 ]; then
    # PASS — all modes allow
    echo "✅ Gate PASS: $VERDICT ($RECALL recall)" >&2
    exit 0
fi

# FAIL — behavior by mode
case "$ROLLOUT_MODE" in
    shadow)
        # Log only, never block — catch false positives safely
        echo "👁️ SHADOW: Gate FAIL ($RECALL recall, $FAILS reqs) — logged, NOT blocked" >&2
        echo "   → Review gate-log.jsonl for false positives before enabling enforced" >&2
        exit 0
        ;;

    advisory)
        # Warn agent, but allow deploy (agent sees warning in stderr)
        echo "⚠️ ADVISORY: Gate FAIL ($RECALL recall, $FAILS reqs failed)" >&2
        echo "$VERIFIER_OUTPUT" | grep -E "❌|FAILED REQ" | head -5 >&2
        echo "   → Deploy allowed but report has issues. Fix recommended." >&2
        exit 0
        ;;

    enforced)
        # Hard block — deploy denied
        echo "╔══════════════════════════════════════════════════════════╗" >&2
        echo "║  🚫 DEPLOY BLOCKED — Independent Verifier FAILED          ║" >&2
        echo "╚══════════════════════════════════════════════════════════╝" >&2
        echo "" >&2
        echo "Recall: $RECALL | Failed: $FAILS requirements" >&2
        echo "" >&2
        echo "$VERIFIER_OUTPUT" | grep -E "❌|FAIL|recall|VERDICT|FAILED REQ" >&2
        echo "" >&2
        echo "→ Evidence: $(dirname "$REPORT")/.task-state/evidence/" >&2
        echo "→ Mode: enforced (change EQUITY_GATE_MODE to advisory/shadow to allow)" >&2
        exit 2
        ;;
esac
