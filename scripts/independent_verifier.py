#!/usr/bin/env python3
"""
independent_verifier.py — Independent Verifier (Lớp 3 + 4 anti-omission harness)

Lớp 3 (Evidence ledger): mỗi REQ gắn file evidence JSON với byproduct.
Lớp 4 (Independent verifier): đọc requirements.yaml (KHÔNG đọc SKILL.md prose),
tự chạy verification command, ghi evidence, output pass/fail.

KHÁC BIỆT VỚI enforce_spec.sh (cũ):
  - enforce_spec.sh = hardcode checks trong bash → agent có thể sửa
  - independent_verifier.py = đọc requirements.yaml (data-driven) → thêm/sửa REQ không cần code
  - Verifier KHÔNG tin agent claim → tự chạy command + kiểm artifact

Usage:
  python3 independent_verifier.py MSN /path/to/report.html
  → output: evidence/*.json + verdict (PASS/FAIL + requirement recall)

Exit code: 0 = all pass, 1 = any fail
"""
import json, sys, os, re, shlex, subprocess, yaml, datetime, hashlib

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)
from statement_adapter import annual_rows, normalize_statement

TICKER = sys.argv[1] if len(sys.argv) > 1 else "UNKNOWN"
REPORT = sys.argv[2] if len(sys.argv) > 2 else None
SKILL_DIR = os.path.abspath(os.environ.get(
    "EQUITY_SKILL_DIR", os.path.join(os.path.dirname(__file__), "..")
))
REQ_FILE = os.path.join(SKILL_DIR, "requirements.yaml")

# Colors
RED = "\033[0;31m"; GREEN = "\033[0;32m"; YELLOW = "\033[1;33m"; NC = "\033[0m"

def read_report():
    if not REPORT or not os.path.exists(REPORT):
        return None
    with open(REPORT) as f:
        return f.read()

def extract_section_text(html, section_id):
    """Extract innerText of a section."""
    if not html:
        return ""
    # Find section block
    pattern = rf'<section[^>]*id="{section_id}"[^>]*>(.*?)</section>'
    m = re.search(pattern, html, re.DOTALL)
    if not m:
        return ""
    inner = m.group(1)
    # Strip tags
    text = re.sub(r"<[^>]+>", " ", inner)
    text = re.sub(r"\s+", " ", text).strip()
    return text

def extract_all_text(html):
    if not html:
        return ""
    text = re.sub(r"<[^>]+>", " ", html)
    return re.sub(r"\s+", " ", text).strip()

def _narrative_text(html):
    """Text thuần của narrative — strip <style>/<script> từ HTML GỐC trước khi
    extract tags (extract_all_text giữ nội dung script vì chỉ thay tags bằng space)."""
    if not html:
        return ""
    cleaned = re.sub(r"<style[^>]*>.*?</style>", " ", html, flags=re.DOTALL)
    cleaned = re.sub(r"<script[^>]*>.*?</script>", " ", cleaned, flags=re.DOTALL)
    return extract_all_text(cleaned)

def _ci_find(lst, name):
    """Tìm phần tử khớp case-insensitive (FIX cohort V2 8/2026 — VCB):
    API bank trả cột IN HOA ('TOTAL ASSETS', \"OWNER'S EQUITY\") còn code cũ
    so Title Case chính xác → equity rỗng. Trả phần tử gốc trong lst."""
    target = str(name).strip().lower()
    for x in lst or []:
        if str(x).strip().lower() == target:
            return x
    return None

def _dict_get_ci(d, key):
    """d.get() không phân biệt hoa/thường — data file do agent ghi có thể
    giữ nguyên key từ API (UPPERCASE). Ưu tiên key chính xác trước."""
    if not isinstance(d, dict):
        return None
    if key in d:
        return d[key]
    target = str(key).lower()
    for k, v in d.items():
        if str(k).lower() == target:
            return v
    return None

def _strip_vi_diacritics(s):
    """Bỏ toàn bộ dấu tiếng Việt (NFD → loại combining marks) + đ→d.
    'chuẩn hóa'/'chuẩn hoá'/'chuan hoa' → 'chuan hoa' — khớp từ khóa không
    phụ thuộc biến thể dấu (bug regex Unicode cohort V3: 'ẩ' U+1EA9 nằm
    ngoài [âa])."""
    import unicodedata
    s = unicodedata.normalize("NFD", str(s))
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    s = unicodedata.normalize("NFC", s)
    return s.replace("đ", "d").replace("Đ", "D")

# ═══════════════════════════════════════════════════════════════
# VERIFICATION METHODS (data-driven from requirements.yaml)
# ═══════════════════════════════════════════════════════════════

def verify_non_advice_check(req, html):
    """REQ-007: Check tech-profile section for actionable investment advice.
    P4 FIX: negation-aware. Removes valid disclaimers before checking.
    P5 FIX (v0.1.5): entity-interruption-tolerant disclaimer matching.
      Problem: "không khuyến nghị mua/bán VCB" was flagged because the old
      pattern required "không phải khuyến nghị mua/bán" (exact "phải" + no entity
      after "bán"). Ticker/company names between disclaimer words broke matching.
      Fix: use grammar-level rules that allow entity tokens between negation
      and the advice keyword, while still FAILing real advice.
    STRONG BUY/STRONG SELL as Tech Score verdict is allowed (machine-readable, not advice)."""
    if not html:
        return False, {"error": "no html"}
    # Extract sec-tech-profile section text
    sec_text = extract_section_text(html, "sec-tech-profile")
    if not sec_text:
        return False, {"section_found": False, "note": "KHÔNG có sec-tech-profile — REQ-007 FAIL (section bắt buộc, không vacuously PASS)"}

    # Step 1: Remove valid disclaimer sentences (negation context)
    # P5: Entity-interruption-tolerant patterns.
    # Key insight: a disclaimer has the STRUCTURE "không [entity] khuyến nghị [entity] mua [entity] bán"
    # where [entity] can be ticker names, company names, or connective words.
    # We use .{0,40}? to allow up to 40 chars of interruption between key tokens.
    disclaimer_patterns = [
        # "không [phải] [entity] khuyến nghị mua [/entity] bán [entity]"
        # Handles: "không khuyến nghị mua/bán VCB", "không phải khuyến nghị mua/bán",
        #          "không phải là khuyến nghị mua bán VCB"
        r"không\s+(?:phải\s+(?:là\s+)?)?(?:[A-Z]{2,5}\s+)?khuyến\s+nghị\s+mua[/\s]*bán",
        # "không [entity] khuyến nghị mua" (standalone negation, no "bán" needed)
        r"không\s+(?:phải\s+(?:là\s+)?)?(?:[A-Z]{2,5}\s+)?khuyến\s+nghị\s+mua(?!\s*[/\s]*bán)",
        # "không [entity] khuyến nghị bán" (standalone negation)
        r"không\s+(?:phải\s+(?:là\s+)?)?(?:[A-Z]{2,5}\s+)?khuyến\s+nghị\s+bán",
        # "không cấu thành [entity] khuyến nghị đầu tư"
        r"không\s+cấu\s+thành\s+(?:[A-Z]{2,5}\s+)?(?:khuyến\s+nghị\s+đầu\s+tư|lời\s+khuyên\s+đầu\s+tư)",
        # "không [phải] [entity] lời khuyên tài chính"
        r"không\s+(?:phải\s+)?(?:[A-Z]{2,5}\s+)?lời\s+khuyên\s+tài\s+chính",
        # "không nên được hiểu/xem là [entity] khuyến nghị"
        r"không\s+nên\s+được\s+(?:hiểu|xem)\s+(?:là|như)\s+(?:[A-Z]{2,5}\s+)?khuyến\s+nghị",
        # "chỉ mang tính tham khảo [entity] không phải"
        r"chỉ\s+mang\s+tính\s+tham\s+khảo[^.]*?không\s+phải",
        # "không [entity] khuyến nghị mua/bán" — broader: negation anywhere before "khuyến nghị mua/bán"
        # within same sentence (handles "thông tin về VCB không phải là khuyến nghị mua/bán")
        r"(?:đây|nội\s+dung|thông\s+tin|đánh\s+giá|báo\s+cáo)[^.]{0,30}?không\s+(?:phải\s+(?:là\s+)?)?khuyến\s+nghị\s+mua[/\s]*bán",
        # English
        r"not\s+(?:investment\s+)?advice",
        r"for\s+educational\s+purposes\s+only",
    ]
    cleaned_text = sec_text
    disclaimers_removed = []
    for pat in disclaimer_patterns:
        matches = re.findall(pat, cleaned_text, re.I)
        if matches:
            disclaimers_removed.extend(matches)
            cleaned_text = re.sub(pat, "", cleaned_text, flags=re.I)

    # Step 1b: Also remove full sentences containing "không" + "khuyến nghị" within 60 chars
    # This catches cases like "VCB không phải khuyến nghị mua" where VCB precedes the negation.
    # CRITICAL: a sentence is ONLY removed as a disclaimer if it has NO actionable advice.
    # "không phải khuyến nghị chung, nhưng có thể mua VCB" = disclaimer + real advice → KEEP (FAIL).
    sentences = re.split(r'([.!?]\s+)', cleaned_text)
    rebuilt = []
    for i, s in enumerate(sentences):
        if i % 2 == 0:  # actual sentence (odd indices are delimiters)
            has_negation = bool(re.search(r"không\s|không$", s, re.I))
            has_advice_word = bool(re.search(r"khuyến\s+nghị|lời\s+khuyên|đầu\s+tư|advice", s, re.I))
            # Actionable = real advice signal that must FAIL even in a negation sentence
            has_actionable = bool(re.search(
                r"nên\s+mua|nên\s+bán|điểm\s+mua|điểm\s+bán|chốt\s+lời|cắt\s+lỗ|giải\s+ngân|"
                r"nhà\s+đầu\s+tư\s+nên|có\s+thể\s+mua|có\s+thể\s+bán|"
                r"khuyến\s+nghị\s+mua(?!\s*[/\s]*bán)|khuyến\s+nghị\s+bán",
                s, re.I))
            # Also check for "nhưng" (but) introducing actionable advice after a disclaimer
            has_but_clause = bool(re.search(r"nhưng[^.]{0,40}(?:mua|bán|nên|giải\s+ngân)", s, re.I))
            if has_negation and has_advice_word and not has_actionable and not has_but_clause:
                disclaimers_removed.append(s.strip()[:80])
                rebuilt.append("")  # remove this sentence
            else:
                rebuilt.append(s)
        else:
            rebuilt.append(s)
    cleaned_text = "".join(rebuilt)

    # Step 2: Allow STRONG BUY/STRONG SELL when used as Tech Score verdict (machine-readable)
    verdict_patterns = [
        r"(?:tech\s*score|verdict|kết\s+luận)\s*[:\s-]*\s*(?:STRONG\s+(?:BUY|SELL)|BUY|SELL|NEUTRAL)",
        r'data-verdict="(?:STRONG\s+(?:BUY|SELL)|BUY|SELL|NEUTRAL)"',
        r"(?:STRONG\s+(?:BUY|SELL)|BUY|SELL|NEUTRAL)\s*[×x]?\s*(?:/6|trên\s+6\s+tín\s+hiệu)",
    ]
    for pat in verdict_patterns:
        cleaned_text = re.sub(pat, "[VERDICT_LABEL]", cleaned_text, flags=re.I)

    # Step 3: Check remaining text for actionable advice signals
    # P5b: distinguish "nhà đầu tư nên mua" (actionable) from "nhà đầu tư nên tự đánh giá" (disclaimer)
    advice_signals = [
        r"nên\s+mua", r"nên\s+bán", r"khuyến\s+nghị\s+mua", r"khuyến\s+nghị\s+bán",
        r"nhà\s+đầu\s+tư\s+nên\s+(?!tự\s+đánh\s+giá|tham\s+vấn|cân\s+nhắc|hạn\s+chế)",  # NOT "nên tự đánh giá/tham vấn"
        r"điểm\s+mua", r"điểm\s+bán",
        r"chốt\s+lời", r"cắt\s+lỗ(?!\s+(?:cá\s+nhân|kỷ\s+luật|khẩu\s+vị))", r"giải\s+ngân",
        r"có\s+thể\s+mua", r"có\s+thể\s+bán",
        r"bullish.{0,30}(?:mua|buy|nên)", r"bearish.{0,30}(?:bán|sell|nên)",
    ]
    violations = []
    for pat in advice_signals:
        for m in re.finditer(pat, cleaned_text, re.I):
            ctx = cleaned_text[max(0,m.start()-30):m.end()+30]
            # v0.14.9: Clause-level negation guard — check up to 60 chars before
            pre_context = cleaned_text[max(0,m.start()-60):m.start()].lower()
            # Direct negation: "không nên mua"
            if re.search(r"không\s+(?:phải\s+)?$", pre_context):
                continue
            # v0.14.9: Clause-level negation patterns (must NOT contain 'nhưng' which overrides)
            # Clause boundaries: . ! ? ; — stop negation scope
            if "nhưng" not in pre_context:
                # "không khuyến nghị ... mua/bán"
                if re.search(r"không\s+khuyến\s+nghị[^.!?;]{0,50}$", pre_context):
                    continue
                # "không phải lúc nào (cũng) nên mua/bán"
                if re.search(r"không\s+phải\s+lúc\s+nào[^.!?;]{0,30}$", pre_context):
                    continue
                # "không đưa ra / không có / không phải ... (thời) điểm mua/bán"
                if re.search(r"không\s+(?:đưa\s+ra|có|phải)[^.!?;]{0,40}$", pre_context):
                    continue
            violations.append({"pattern": pat[:30], "context": ctx.strip()[:80]})

    passed = len(violations) == 0
    return passed, {
        "section_length": len(sec_text),
        "disclaimers_removed": len(disclaimers_removed),
        "advice_violations": violations[:3],
        "patch_note": "P5: entity-interruption-tolerant disclaimers + sentence-level negation removal + final negation guard",
    }

TICKER_RE_SAFE = re.compile(r"^[A-Z][A-Z0-9]{1,9}$")

def run_command_safe(cmd, ticker, report):
    """P0-04 (Wave 1): chạy registry command KHÔNG shell.
    - Ticker validate allowlist; report phải absolute trong work dir (realpath)
    - Pipe đơn giản xử lý argv→argv; shell semantics khác không được diễn giải.
    Trả về (returncode, stdout_cuối)."""
    if not TICKER_RE_SAFE.fullmatch(ticker or ""):
        raise ValueError(f"TICKER không hợp lệ: {ticker!r}")
    # REPORT: không validate work-dir (verifier nhận path từ CLI — không có WORK_DIR),
    # nhưng path có metacharacter sẽ bị shlex.split tách → không có shell semantics
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

def verify_command(req, html):
    """Run shell command, check exit code / output."""
    import tempfile as _tempfile
    cmd = req["verification"]["command"]
    js_file = None
    # If JS check, extract JS from HTML first
    if "$JS_FILE" in cmd and html:
        scripts = re.findall(r"<script>(.*?)</script>", html, re.DOTALL)
        with _tempfile.NamedTemporaryFile(
            mode="w", suffix=".js", prefix=f"equity_verify_{TICKER}_", delete=False
        ) as f:
            js_file = f.name
            f.write("\n".join(s for s in scripts if "cdn.jsdelivr" not in s))
        cmd = cmd.replace("$JS_FILE", js_file)
    else:
        cmd = cmd.replace("$JS_FILE", "/dev/null")
    try:
        exit_code, _out = run_command_safe(cmd, TICKER, REPORT)
        output = (_out or "").strip()

        if "expect_exit" in req["verification"]:
            passed = exit_code == req["verification"]["expect_exit"]
            return passed, {"output": output[:200], "exit_code": exit_code, "command": cmd[:100]}

        if "expect_min" in req["verification"]:
            try:
                # G11 (REQ-002): output có thể nhiều số ("41 41 41" cho 3 báo cáo)
                # → lấy MIN: yêu cầu "CẢ 3 ≥ ngưỡng" thì số nhỏ nhất phải đạt
                nums = [int(x) for x in re.findall(r"\d+", output)]
                val = min(nums) if nums else None
                passed = val is not None and val >= req["verification"]["expect_min"]
            except:
                passed = False
                val = None
            return passed, {"output": output, "value": val, "min_expected": req["verification"]["expect_min"]}

        if "expect_max" in req["verification"]:
            try:
                val = int(output)
                passed = val <= req["verification"]["expect_max"]
            except:
                passed = False
                val = None
            return passed, {"output": output, "value": val, "max_expected": req["verification"]["expect_max"]}
    except Exception as e:
        return False, {"error": str(e)}
    finally:
        if js_file:
            try:
                os.unlink(js_file)
            except FileNotFoundError:
                pass
    return False, {"error": "unknown verification"}


def verify_artifact_check(req, html):
    """Check artifact content for patterns."""
    check = req["verification"].get("check", "")
    text = extract_all_text(html) if html else ""

    if "split-adjusted" in check.lower() or "bẫy 5b" in check.lower():
        # G13 (review V4 Flash): keyword-check "report chứa chữ split-adjusted" lách
        # được bằng cách thả chữ. Verify từ task-state phase1: split_audit phải log
        # kết quả audit (cp_consistent) — report mention chỉ là điều kiện phụ.
        ts = _load_json_rel(".task-state/task-state.json")
        audit = None
        if ts:
            p1 = (ts.get("phases", {}).get("phase1_data", {}) or {}).get("result") or {}
            audit = p1.get("split_audit") or ts.get("split_audit")
        report_mentions = any(w in text.lower() for w in ["split-adjusted", "bẫy 5b", "cross-check eps", "audit split"])
        if isinstance(audit, dict):
            cp_ok = audit.get("cp_consistent") in (True, "true", "True")
            if not cp_ok:
                return False, {"found": report_mentions, "split_audit": audit,
                               "error": "task-state split_audit có cp_consistent != true — audit split không đạt"}
            # W4 (Flash review): recompute CP = LNST/EPS độc lập — chống self-attestation.
            # Lệch >20% so issue_share → cảnh báo; phân biệt SPLIT (phải restate — FAIL)
            # vs DILUTION/phát hành thêm (không bắt buộc restate theo chuẩn — advisory).
            fin = _load_json_rel("data/financials.json")
            ov = _load_json_rel("data/overview.json")
            cp_warn = None
            if fin and ov:
                issue = ov.get("issue_share")
                eps = fin.get("eps_vnd") or {}
                npat = fin.get("npatmi_ty") or {}
                if issue and eps and npat:
                    for y in sorted(eps.keys()):
                        if eps[y] and npat.get(y):
                            cp = npat[y] * 1e9 / eps[y]
                            diff = abs(cp - issue) / issue
                            if diff > 0.20:
                                cp_warn = f"{y}: CP back-calc {cp/1e6:.0f}M vs issue_share {issue/1e6:.0f}M (lệch {diff*100:.0f}%) — xác nhận split hay dilution trước khi so P/E lịch sử"
                                break
            if cp_warn:
                cause = str(audit.get("cp_variation_cause", "") or "").lower()
                if "dilution" in cause or "phát hành" in cause or "issue" in cause:
                    # Dilution (phát hành thêm) — EPS lịch sử theo BCTC là chuẩn kế toán,
                    # KHÔNG bắt buộc restate. Chấp nhận + cảnh báo rõ để người đọc biết.
                    return True, {"found": report_mentions, "split_audit": audit,
                                  "independent_cp_warning": cp_warn,
                                  "note": "CP lệch >20% do dilution đã ghi rõ cause — EPS lịch sử giữ theo BCTC (đúng chuẩn); so P/E lịch sử cần chú ý"}
                return False, {"found": report_mentions, "split_audit": audit,
                               "independent_cp_warning": cp_warn,
                               "error": f"REQ-003: {cp_warn} — nếu là split phải restate EPS lịch sử; nếu là dilution ghi rõ cp_variation_cause trong task-state"}
            if not report_mentions:
                return False, {"found": False, "split_audit": audit,
                               "error": "split_audit OK nhưng report không mention 'split-adjusted/Bẫy 5B/cross-check EPS'"}
            return True, {"found": True, "split_audit": audit, "audit_verified_from_task_state": True}
        if audit:
            return False, {"found": report_mentions, "split_audit": audit,
                           "error": "split_audit không đúng format (cần dict với cp_consistent)"}
        # Không có log audit trong task-state → fail-closed (không tin chữ trong report)
        if report_mentions:
            return False, {"found": report_mentions,
                           "error": "report mention split-adjusted NHƯNG task-state phase1 không log split_audit — nghi keyword-stuffing (G13 fail-closed)"}
        return False, {"found": False, "error": "không có split_audit trong task-state và report không mention"}

    if "placeholder" in check.lower() or "oracle" in check.lower():
        # Check for Oracle placeholder data in VISIBLE TEXT (not JS/CSS/comments)
        # "oracle" in JS comments is OK; in visible body text = bad
        # Strip script/style blocks first
        body_text = re.sub(r"<script.*?</script>", "", html or "", flags=re.DOTALL)
        body_text = re.sub(r"<style.*?</style>", "", body_text, flags=re.DOTALL)
        body_text = re.sub(r"<!--.*?-->", "", body_text, flags=re.DOTALL)
        body_text = re.sub(r"<[^>]+>", " ", body_text)
        body_text = re.sub(r"\s+", " ", body_text).strip().lower()
        # P3 FIX: context-scoped Oracle detection. Standalone "oracle" (including Vietnamese
        # business term meaning "chủ đầu tư then chốt") must NOT trigger. Require specific
        # Oracle Corporation signals: company name, ticker, product names, or USD financials.
        oracle_corp_signals = [
            r"oracle\s+corporation",
            r"\bORCL\b",
            r"NYSE:?\s*ORCL",
            r"oracle\s+oci",
            r"oracle\s+cloud",
            r"oracle\s+database",
            r"oracle[^a-z]{0,20}(?:revenue|capex|earnings|billion|usd)",
            r"\$\s*billions.*oracle",
            r"usd\s*billions.*oracle",
        ]
        has_oracle = any(re.search(pat, body_text, re.I) for pat in oracle_corp_signals)
        passed = not has_oracle
        return passed, {"no_placeholder": passed, "has_oracle": has_oracle,
                        "patch_note": "P3: context-scoped — standalone 'oracle' no longer triggers"}

    if "non_advice" in check.lower() or "neutral_descriptive" in check.lower():
        return verify_non_advice_check(req, html)

    if "tech score" in check.lower() or "verdict" in check.lower():
        sec = extract_section_text(html, "sec-tech")
        passed = bool(re.search(r"-?[0-9]\s*/\s*6|STRONG (SELL|BUY)|SELL|BUY|NEUTRAL", sec))
        return passed, {"has_tech_score": passed, "section_length": len(sec)}

    if "sec-tech-profile" in check.lower() or "non-advice" in check.lower():
        sec = extract_section_text(html, "sec-tech-profile")
        passed = len(sec) > 100
        return passed, {"section_length": len(sec)}

    if "sentiment" in check.lower():
        passed = bool(re.search(r"sentiment|tích cực|tiêu cực|trung tính", text.lower()))
        return passed, {"has_sentiment": passed}

    if "callout" in check.lower() or "limitation" in check.lower() or "honest" in check.lower():
        passed = any(w in text.lower() for w in ["ước tính", "limitation", "stale", "honest", "data limitation"])
        return passed, {"has_honest_flag": passed}

    if "risk" in check.lower():
        sec = extract_section_text(html, "sec-risk")
        passed = len(sec) > 100
        return passed, {"risk_section_length": len(sec)}

    if "dương" in check.lower() or "valuation" in check.lower():
        prices = re.findall(r'class="price[^"]*"[^>]*>\s*([-\d,]+)', html or "")
        negative = [p for p in prices if p.startswith("-")]
        passed = len(negative) == 0
        return passed, {"negative_prices": negative[:3], "total_prices": len(prices)}

    # G12 (review V4 Flash): nhánh "split-adjusted" lặp lần 2 (dòng 314 cũ) là dead
    # code — nhánh chính ở dòng 250 đã return. Đã xóa; keyword "audit split" đã có
    # trong nhánh chính.
    return False, {"error": f"unknown check: {check[:60]}"}


def verify_section_map(req, html):
    """Check section ids match canonical."""
    canonical = req["verification"]["canonical_sections"]
    min_match = req["verification"]["min_canonical_match"]
    # PATCH P0-2: high-signal sections must each be present (count proxy alone was gameable).
    required_signal = req["verification"].get("required_signal_sections", [])
    found = 0
    found_ids = []
    missing_ids = []
    for sec_id in canonical:
        if html and f'id="{sec_id}"' in html:
            found += 1
            found_ids.append(sec_id)
        else:
            missing_ids.append(sec_id)
    missing_signal = [s for s in required_signal if not (html and f'id="{s}"' in html)]
    # PATCH P0-2: PASS requires BOTH count threshold AND every signal section present.
    passed = found >= min_match and len(missing_signal) == 0
    return passed, {"found": found, "total": len(canonical), "min_required": min_match,
                    "missing": missing_ids[:10],
                    "missing_signal_sections": missing_signal,
                    "patch_note": "P0-2: tightened min 15→20 + required_signal_sections each-present"}


def verify_count_check(req, html):
    """Count charts, sections, refs."""
    mins = req["verification"]
    charts = len(re.findall(r"new Chart|viz\.chart", html or "")) if html else 0
    sections = len(re.findall(r"<section", html or "")) if html else 0
    refs = len(re.findall(r'id="ref-\d+"', html or "")) if html else 0
    passed = (charts >= mins.get("min_charts", 0) and
              sections >= mins.get("min_sections", 0) and
              refs >= mins.get("min_refs", 0))
    return passed, {"charts": charts, "sections": sections, "refs": refs,
                    "min_charts": mins.get("min_charts"), "min_sections": mins.get("min_sections"),
                    "min_refs": mins.get("min_refs")}


def verify_content_depth(req, html):
    """Check each section has enough content."""
    min_chars = req["verification"]["min_chars_per_section"]
    exempt = req["verification"].get("exempt_sections", [])
    all_secs = re.findall(r'<section[^>]*id="(sec-[^"]+)"', html or "")
    shallow = []
    for sec_id in all_secs:
        if sec_id in exempt:
            continue
        text = extract_section_text(html, sec_id)
        if len(text) < min_chars:
            shallow.append({"section": sec_id, "chars": len(text)})
    passed = len(shallow) == 0
    return passed, {"min_chars": min_chars, "shallow_sections": shallow[:5], "total_checked": len(all_secs)}


def verify_section_content(req, html):
    """Check specific sections have content."""
    secs = req["verification"]["sections"]
    min_chars = req["verification"]["min_chars_each"]
    results = {}
    passed = True
    for sec_id in secs:
        text = extract_section_text(html, sec_id)
        ok = len(text) >= min_chars
        results[sec_id] = {"chars": len(text), "ok": ok}
        if not ok:
            passed = False
    return passed, results


def verify_canvas_check(req, html):
    """Check canvas elements have height-wrapper."""
    if not html:
        return False, {"error": "no html"}
    canvases = list(re.finditer(r"<canvas\s", html))
    bare = 0
    bare_ids = []
    for m in canvases:
        before = html[max(0, m.start() - 80):m.start()]
        if not any(p in before for p in ["chart-wrap", "tech-chart-wrap", "height:", "height="]):
            bare += 1
            # Try to find canvas id
            id_match = re.search(r'id="([^"]*)"', html[m.start():m.start()+100])
            bare_ids.append(id_match.group(1) if id_match else "unknown")
    passed = bare == 0
    return passed, {"bare_canvas_count": bare, "bare_canvas_ids": bare_ids, "total_canvas": len(canvases)}


def verify_valuation_sanity(req, html):
    """Check val-card prices positive + DCF negative flag."""
    prices = re.findall(r'class="price[^"]*"[^>]*>\s*([-\d,]+)', html or "")
    negative = [p for p in prices if p.startswith("-")]
    # Check if negative prices have explanation note
    text = extract_all_text(html) if html else ""
    has_fcF_note = any(w in text.lower() for w in ["fcf", "fcf âm", "fcf<0", "không hợp lệ", "ev/ebitda"])
    passed = len(negative) == 0 or (len(negative) > 0 and has_fcF_note)
    return passed, {"negative_prices": negative[:3], "total_prices": len(prices), "has_fcf_note": has_fcF_note}


def _context_anchored_match(text, anchor_label, gt_val, tolerance_pct, fallback_key=None, window=400):
    """PATCH P1-1 (REQ-022): find gt_val within ±tolerance ONLY in a context window around
    an anchor. Prevents a corrupted value being masked by a sibling value matching globally.

    Anchors (in priority order):
      1. the YEAR label (for per-year table cells where year is adjacent)
      2. the field key (revenue_ty, npatmi_ty) — internal data label
      3. business synonyms for the field key (revenue↔Doanh thu, npatmi↔LNST/lợi nhuận)
    A value matches only if it appears within `window` chars of SOME anchor — not anywhere.
    Handles US/VN number formats."""
    def parse_num(s):
        try:
            c = s.strip()
            if "." in c and "," in c: c = c.replace(",", "")
            elif "." in c and "," not in c:
                parts = c.split(".")
                if len(parts) > 1 and all(len(p) == 3 for p in parts[1:]): c = c.replace(".", "")
            return float(c)
        except Exception:
            return None
    def within_tol(n):
        return n is not None and abs(n - gt_val) / max(abs(gt_val), 0.001) * 100 <= tolerance_pct
    # build anchor synonym map keyed by the field key
    synonyms = {
        "revenue_ty": ["revenue_ty", "Doanh thu", "Revenue", "Tổng doanh thu"],
        "npatmi_ty": ["npatmi_ty", "LNST", "lợi nhuận sau thuế", "Net profit", "Net income", "Net Profit"],
        "eps_vnd": ["eps_vnd", "EPS", "EPS adj", " Thu nhập trên mỗi cổ phiếu"],
        "Total Assets": ["Total Assets", "Tổng tài sản"],
        "Owner's Equity": ["Owner's Equity", "Vốn chủ sở hữu"],
    }
    anchor_terms = synonyms.get(fallback_key, []) or ([fallback_key] if fallback_key else [])
    if anchor_label:
        anchor_terms = anchor_terms + [anchor_label]
    anchor_terms = [t for t in anchor_terms if t]
    positions = []
    for term in anchor_terms:
        positions.extend(m.start() for m in re.finditer(re.escape(term), text, re.I))
    if not positions:
        positions = [0]
    for a in positions:
        seg = text[max(0, a-window):a+window]
        for num_str in re.findall(r'(-?\d[\d.,]+)', seg):
            if within_tol(parse_num(num_str)):
                return True
    return False

def _extract_data_js_arrays(html):
    """PATCH P1-1 (REQ-022): pull structured arrays from the report's `const DATA = {...}` JS
    object. Returns {years, revenue, netProfit, eps, ...} as lists of floats/strings. Used for
    unambiguous per-year verification (eliminates sibling-value substitution)."""
    if not html:
        return {}
    out = {}
    for name in ["years", "revenue", "netProfit", "net_profit", "eps", "capex", "totalAssets", "equity", "ownersEquity"]:
        m = re.search(rf'["\']?{name}["\']?\s*:\s*\[([^\]]*)\]', html)
        if m:
            vals = []
            for tok in m.group(1).split(","):
                tok = tok.strip().strip("'\"")
                if not tok:
                    continue
                if tok.lower() in ("null", "none", "nan"):
                    vals.append(None)
                    continue
                try:
                    vals.append(float(tok))
                except ValueError:
                    vals.append(tok)
            out[name] = vals
    return out

def verify_data_accuracy(req, html):
    """Verify report numbers match data files (ground truth). Anti-fabrication."""
    import json as _json
    work_dir = os.path.dirname(REPORT) if REPORT else "."
    data_path = os.path.join(work_dir, req["verification"]["data_file"])

    if not os.path.exists(data_path):
        return False, {"error": f"data file not found: {data_path}"}

    with open(data_path) as f:
        ground_truth = _json.load(f)

    text = extract_all_text(html) if html else ""
    # PATCH P1-1 (REQ-022): parse the structured DATA JS object for unambiguous per-year
    # verification. This eliminates sibling-value substitution (a corrupted year being masked
    # by another year's value matching in a shared context window).
    data_arrays = _extract_data_js_arrays(html)  # {years:[...], revenue:[...], netProfit:[...], eps:[...]}
    mismatches = []
    checked = 0

    for field in req["verification"].get("fields", []):
        key = field["key"]
        tolerance = field.get("tolerance_pct", 5)

        # Get ground truth value
        gt_val = _dict_get_ci(ground_truth, key)
        if gt_val is None:
            continue

        # Map field key → DATA array name
        data_arr_map = {"revenue_ty": "revenue", "npatmi_ty": "netProfit", "eps_vnd": "eps",
                        "Total Assets": "totalAssets", "Owner's Equity": "equity"}

        # If dict (per-year), check each year
        if isinstance(gt_val, dict):
            years = field.get("years", list(gt_val.keys()))
            if years == ["latest"]:
                annual = [str(y) for y in gt_val.keys() if str(y).isdigit()]
                years = [max(annual, key=int)] if annual else []
            else:
                # Some delisted/short-history issuers only have older annual data
                # (for example 2018-2020). A fixed 2021-2025 policy used to make
                # REQ-022 vacuously check zero cells. Prefer the configured window
                # when it overlaps; otherwise verify every available annual year
                # (capped to the latest five) instead of passing/failing empty.
                available = sorted(
                    (str(y) for y in gt_val.keys() if str(y).isdigit()),
                    key=int,
                )
                requested = [str(y) for y in years]
                overlap = [y for y in requested if y in available]
                years = overlap if overlap else available[-5:]
            divisor = field.get("divisor", 1)
            data_arr_name = data_arr_map.get(key)
            data_arr = data_arrays.get(data_arr_name, []) if data_arr_name else []
            data_years = data_arrays.get("years", [])
            for yr in years:
                # Zero is a valid reported value; do not turn it into a miss via
                # boolean ``or``.
                if str(yr) in gt_val:
                    yr_val = gt_val[str(yr)]
                elif yr in gt_val:
                    yr_val = gt_val[yr]
                else:
                    yr_val = None
                if yr_val is None:
                    continue
                yr_val = float(yr_val) / divisor
                checked += 1
                # PATH A (preferred): exact-index match via DATA JS array
                # normalize years to int-strings ("2025" not "2025.0")
                data_years_norm = [str(int(float(y))) if isinstance(y,(int,float)) else str(y) for y in data_years]
                if data_arr and str(yr) in data_years_norm:
                    try:
                        idx = data_years_norm.index(str(yr))
                        report_val = float(data_arr[idx]) if idx < len(data_arr) else None
                        # ground truth for revenue_ty is in tỷ (÷1e9 done); DATA revenue is in tỷ VND too
                        # eps_vnd is per-share VND (no divisor scaling needed vs DATA eps)
                        # normalize: compare magnitudes with tolerance
                        if report_val is not None:
                            denom = max(abs(yr_val), abs(report_val), 0.001)
                            diff_pct = abs(yr_val - report_val) / denom * 100
                            if diff_pct > tolerance:
                                mismatches.append(f"{key}[{yr}]: DATA array value {report_val} ≠ ground_truth {yr_val:,.1f} (diff {diff_pct:.1f}% > {tolerance}%)")
                                continue
                            else:
                                continue  # matched at exact index
                    except (ValueError, IndexError):
                        pass
                # PATH B (fallback): context-anchored match (for fields not in DATA, e.g. balance sheet)
                yr_str = str(yr)
                found_match = _context_anchored_match(text, yr_str, yr_val, tolerance, fallback_key=key)
                if not found_match:
                    mismatches.append(f"{key}[{yr}]: ground_truth={yr_val:,.1f} not found (DATA-array miss + context-anchored fallback miss, ±{tolerance}%)")
        else:
            # Single value — PATCH P1-1: context-anchored (around the field key)
            gt_val = float(gt_val)
            checked += 1
            found_match = _context_anchored_match(text, key, gt_val, tolerance, fallback_key=key)
            if not found_match:
                mismatches.append(f"{key}: ground_truth={gt_val:,.0f} not found near its label (±{tolerance}% context-anchored)")

    passed = len(mismatches) == 0 and checked > 0
    return passed, {"checked": checked, "mismatches": mismatches[:5], "ground_truth_file": req["verification"]["data_file"]}


def verify_capex_accuracy(req, html):
    """Verify capex chart data matches cash_flow.json. Anti-fabrication."""
    import json as _json
    work_dir = os.path.dirname(REPORT) if REPORT else "."
    data_path = os.path.join(work_dir, req["verification"]["data_file"])

    if not os.path.exists(data_path):
        return False, {"error": f"cash_flow.json not found"}

    with open(data_path) as f:
        cf = _json.load(f)

    capex_key = req["verification"].get("capex_key", "Purchases of fixed assets and other long term assets")

    # Get capex from ground truth (sponsor format: dict with per-period values)
    if isinstance(cf, dict):
        capex_data = cf.get(capex_key)
        if capex_data is None:
            return False, {"error": f"capex key '{capex_key}' not in cash_flow.json", "available_keys": list(cf.keys())[:10]}

        # Handle dict (per-period): retain year binding; do not compare averages
        # from arrays that may cover different fiscal years.
        if isinstance(capex_data, dict):
            gt_by_year = {str(y): (abs(float(v)) / 1e9 if v is not None else None)
                          for y, v in capex_data.items() if str(y).isdigit()}
        elif isinstance(capex_data, (int, float)):
            return False, {"error": "scalar capex has no fiscal-year binding"}
        elif isinstance(capex_data, list):
            return False, {"error": "list capex has no fiscal-year binding"}
        else:
            return False, {"error": f"unexpected capex data type: {type(capex_data)}"}
    else:
        return False, {"error": "unexpected cash_flow.json format"}

    arrays = _extract_data_js_arrays(html)
    report_years = [str(int(y)) if isinstance(y, float) else str(y) for y in arrays.get("years", [])]
    report_capex = arrays.get("capex")
    if not report_years or not isinstance(report_capex, list):
        return False, {"error": "capex/years arrays not found in report JS DATA"}
    if len(report_years) != len(report_capex):
        return False, {"error": "capex array length does not match years", "years": len(report_years), "capex": len(report_capex)}

    tolerance = req["verification"].get("tolerance_pct", 10)
    issues, checked = [], 0
    report_by_year = dict(zip(report_years, report_capex))
    for year, gt in gt_by_year.items():
        if gt is None:
            if report_by_year.get(year) not in (None, "null"):
                issues.append(f"capex[{year}] report={report_by_year.get(year)} nhưng nguồn là null")
            continue
        checked += 1
        rv = report_by_year.get(year)
        if not isinstance(rv, (int, float)):
            issues.append(f"capex[{year}] thiếu trong report; nguồn={gt:.3f} tỷ")
            continue
        # DATA displays two decimals: accept half a display step as well as 10%.
        abs_tol = max(abs(gt) * tolerance / 100, 0.005)
        if abs(abs(float(rv)) - gt) > abs_tol:
            issues.append(f"capex[{year}] report={rv} ≠ nguồn={gt:.3f} tỷ (tol={abs_tol:.3f})")
    return len(issues) == 0 and checked > 0, {
        "checked": checked, "issues": issues[:8], "tolerance_pct": tolerance,
        "note": "year-bound DATA capex vs cash_flow.json"
    }


def _extract_primary_multiple(text, label_pattern, computed_val, tolerance_pct):
    """PATCH P2: extract a valuation multiple (P/E, P/B) from visible report text.
    Handles × (U+00D7) and ASCII x. Requires leading digit. Avoids Chart.js JS tokens.

    Strategy:
      1. Find all occurrences of `label <number>(×|x)` in the scoped text (sec-valuation or sec-hero).
      2. Normalize to floats.
      3. If all candidates are the same value → UNAMBIGUOUS, return it.
      4. If multiple distinct values:
         a. If a primary semantic marker (data-metric, TTM/hiện tại/current label, val-card) identifies one → return it.
         b. If no marker → FAIL_AMBIGUOUS (return None with ambiguity detail).
      5. NEVER select by computed-value match — that would be cherry-picking to PASS, not verifying.
      6. If no candidates at all → None (value not found)."""
    # match: label (P/E or P/B), optional descriptive text, then NUMBER, then × or x
    pat = re.compile(rf'{label_pattern}[^0-9\n]{{0,30}}([\d,]+\.?\d*)\s*[×x]', re.I)
    # v0.14.1: identify the OTHER multiple label to detect cross-contamination
    other_label = "p/e" if "p/?b" in label_pattern.lower() else "p/b"
    candidates = []  # list of (value, is_primary, is_projection)
    for m in pat.finditer(text):
        # v0.14.1: skip if the text between label and number contains the OTHER label
        # (prevents "P/B vs lịch sử P/E (TTM) 7.35×" from matching 7.35 as P/B)
        gap_text = text[m.start()+2:m.start()+len(m.group(0))].lower()  # text after "P/B"
        if other_label in gap_text:
            continue  # cross-contaminated match — the number belongs to the other multiple
        # FIX V6 (HPG cohort 2026-08-01): "PB method (chuẩn hóa 1.0x)" — tên phương pháp
        # trong bảng định giá bị nhầm thành P/B multiple → tạo candidate 1.0 giả → mâu
        # thuẫn với P/B thật 1.30 → AMBIGUOUS → fail oan. Tên cột phương pháp → skip.
        if "method" in gap_text:
            continue
        # v0.14.5: handle Vietnamese decimal notation (4,8 = 4.8, not 48)
        raw_orig = m.group(1)
        # If comma is followed by exactly 1-2 digits at the end → decimal separator
        if re.search(r',\d{1,2}$', raw_orig) and '.' not in raw_orig:
            raw = raw_orig.replace(',', '.')  # 4,8 → 4.8, 4,80 → 4.80
        else:
            raw = raw_orig.replace(',', '')  # 1,234.56 → 1234.56 (thousands)
        try:
            val = float(raw)
            # P/E có thể thực sự >1.000x khi EPS dương nhưng rất nhỏ.
            # Regex đã bind chặt với nhãn P/E|P/B; cắt >1.000 làm verifier
            # bỏ current multiple và nhầm peer median thành giá trị hiện tại.
            label_to_num = text[m.start():m.start()+len(m.group(0))].lower()
            has_primary = any(kw in label_to_num for kw in ["data-metric","ttm","hiện tại","current","val-card","mono","kpi-value"])
            # FP-M6 (batch-3): "P/E trung bình NGÀNH 12x" là claim ngành, không phải
            # multiple của CTD → thêm ngành/trung bình/bình quân vào projection filter
            has_projection = any(kw in label_to_num for kw in ["median","target","5y","projected","fcf","graham","ev/ebitda","p/cf","dcf","wacc","ngành","trung bình","bình quân"])
            is_primary = has_primary and not has_projection
            candidates.append((val, is_primary, has_projection))
        except ValueError:
            continue
    if not candidates:
        return None
    # Filter out projection candidates (median/5Y/target/DCF are NOT the current multiple)
    non_projection = [(v, ip) for v, ip, proj in candidates if not proj]
    if not non_projection:
        return None  # all candidates are projections — no current multiple found
    distinct = set(v for v, _ in non_projection)
    # Rule 3: all non-projection values same → unambiguous
    if len(distinct) == 1:
        return non_projection[0][0]
    # v0.14.8: majority vote — CONSTRAINED to valuation scope only
    # Only applies when: no canonical marker, candidates from valuation section,
    # projections removed, no P/E cross-contamination in candidate gaps
    from collections import Counter
    val_counts = Counter(v for v, _ in non_projection)
    most_common_val, most_common_count = val_counts.most_common(1)[0]
    if most_common_count >= 3 and most_common_count >= len(non_projection) * 0.6:
        return most_common_val
    # Rule 4a: multiple distinct non-projection → need primary marker
    marked = [(v, ip) for v, ip in non_projection if ip]
    if len(marked) >= 1:
        return marked[0][0]
    # Rule 4b: multiple distinct, no marker → AMBIGUOUS
    return None  # caller will report AMBIGUOUS_PRIMARY_MULTIPLE

def verify_valuation_recompute(req, html):
    """REQ-025: recompute narrative PE/PB, including explicit N/A semantics."""
    import json as _json, math as _math
    work_dir = os.path.dirname(REPORT) if REPORT else "."
    fin_path = os.path.join(work_dir, "data/financials.json")

    if not os.path.exists(fin_path):
        return False, {"error": "financials.json not found"}

    with open(fin_path) as f:
        fin = _json.load(f)

    def _finite_number(value):
        return (isinstance(value, (int, float)) and not isinstance(value, bool)
                and _math.isfinite(float(value)))

    def _latest_value(values):
        if not isinstance(values, dict):
            return None, None
        years = sorted((str(y) for y in values if str(y).isdigit()), key=int)
        if not years:
            return None, None
        year = years[-1]
        value = values.get(year)
        return year, float(value) if _finite_number(value) else None

    def _narrative_has_na(text, label):
        patterns = [
            rf"P\s*/?\s*{label}.{{0,90}}(?:N\s*/?\s*A|không áp dụng|không tính được)",
            rf"(?:N\s*/?\s*A|không áp dụng|không tính được).{{0,90}}P\s*/?\s*{label}",
        ]
        return any(re.search(pattern, text, re.I | re.S) for pattern in patterns)

    price = (fin.get("overview") or {}).get("current_price")
    eps_year, eps_latest = _latest_value(fin.get("eps_vnd"))
    equity_year, equity_latest = _latest_value(fin.get("equity_ty"))
    shares = (fin.get("overview") or {}).get("issue_share")

    full_text = extract_all_text(html) if html else ""
    val_text_parts = []
    for sec_id in ["sec-valuation", "sec-hero", "sec-exec"]:
        st = extract_section_text(html, sec_id) if html else ""
        if st:
            val_text_parts.append(st)
    val_text = "\n".join(val_text_parts) if val_text_parts else full_text

    results_check = {}
    all_pass = True

    for formula in req["verification"].get("formulas", []):
        name = formula["name"]
        tolerance = formula.get("tolerance_pct", 2)

        if name == "PE":
            if eps_latest is None:
                results_check[name] = {"error": "latest EPS missing/invalid", "year": eps_year}
                all_pass = False
                continue
            if eps_latest <= 0:
                narrative_na = _narrative_has_na(val_text, "E")
                results_check[name] = {
                    "status": "NOT_COMPUTABLE", "reason": f"EPS={eps_latest} <= 0",
                    "year": eps_year, "narrative_na": narrative_na,
                }
                if not narrative_na:
                    all_pass = False
                continue
            computed = float(price) / eps_latest if _finite_number(price) and price > 0 else None
            report_val = _extract_primary_multiple(val_text, "P/?E", computed, tolerance)

        elif name == "PB":
            if equity_latest is None or not _finite_number(shares) or shares <= 0:
                results_check[name] = {
                    "error": "latest equity_ty or issue_share missing/invalid",
                    "year": equity_year,
                }
                all_pass = False
                continue
            bvps = equity_latest * 1e9 / float(shares)
            if bvps <= 0:
                narrative_na = _narrative_has_na(val_text, "B")
                results_check[name] = {
                    "status": "NOT_COMPUTABLE", "reason": f"BVPS={bvps:.2f} <= 0",
                    "year": equity_year, "narrative_na": narrative_na,
                }
                if not narrative_na:
                    all_pass = False
                continue
            computed = float(price) / bvps if _finite_number(price) and price > 0 else None
            report_val = _extract_primary_multiple(val_text, "P/?B", computed, tolerance)
        else:
            continue

        if computed is not None and computed > 0 and report_val is not None:
            abs_diff = abs(computed - report_val)
            abs_tolerance = max(abs(computed) * tolerance / 100, 0.0050000001)
            diff_pct = abs_diff / abs(computed) * 100
            ok = abs_diff <= abs_tolerance
            results_check[name] = {
                "computed": round(computed, 6), "report": report_val,
                "diff_pct": round(diff_pct, 2), "abs_diff": round(abs_diff, 6),
                "abs_tolerance": round(abs_tolerance, 6), "ok": ok,
            }
            if not ok:
                all_pass = False
        else:
            results_check[name] = {"error": "could not extract or compute", "computed": computed, "report": report_val}
            all_pass = False

    return all_pass, results_check


def verify_chart_data_accuracy(req, html):
    """Verify DATA JS object arrays match financials.json."""
    import json as _json
    work_dir = os.path.dirname(REPORT) if REPORT else "."
    data_path = os.path.join(work_dir, req["verification"]["data_file"])

    if not os.path.exists(data_path):
        return False, {"error": "financials.json not found"}

    with open(data_path) as f:
        fin = _json.load(f)

    check_arrays = req["verification"].get("check_arrays", [])
    mismatches = []

    for arr_name in check_arrays:
        # Get ground truth
        if arr_name == "revenue":
            gt = list(fin.get("revenue_ty", {}).values())
        elif arr_name == "netProfit":
            gt = list(fin.get("npatmi_ty", {}).values())
        elif arr_name == "eps":
            gt = list(fin.get("eps_vnd", {}).values())
        elif arr_name == "cfo":
            gt = list(fin.get("cfo_ty", {}).values())
        elif arr_name == "inventory":
            # inventory thật không nằm trong financials.json — dùng contract financials
            # (key JS chart là "inventory", ground truth là contract financials.inventory_fin)
            vdd = _load_json_rel("verified-dashboard-data.json")
            gt = ((vdd or {}).get("financials") or {}).get("inventory_fin", [])
        else:
            continue

        # Get report JS value — P0 (Sol checkpoint 2): hỗ trợ null (cfo/inventory thiếu)
        js_match = re.search(rf'["\']?{arr_name}["\']?\s*:\s*\[([^\]]+)\]', html or "")
        if not js_match:
            mismatches.append(f"{arr_name}: not found in JS DATA")
            continue

        report_vals = []
        for x in js_match.group(1).split(","):
            x = x.strip()
            if x in ("null", "None", ""):
                report_vals.append(None)
            else:
                try:
                    report_vals.append(float(x))
                except ValueError:
                    report_vals.append(None)

        # Compare arrays — P0 (Sol checkpoint 2): mutation mảng CFO/inventory phải bị bắt;
        # None vs số = mismatch; số lệch >5% = mismatch
        min_len = min(len(gt), len(report_vals))
        for i in range(min_len):
            g, r = gt[i], report_vals[i]
            if g is None and r is None:
                continue
            if g is None or r is None:
                mismatches.append(f"{arr_name}[{i}]: gt={g} vs report={r} (null mismatch)")
                continue
            if abs(r - g) / max(abs(g), 0.001) * 100 > 5:
                mismatches.append(f"{arr_name}[{i}]: gt={g:.0f} vs report={r:.0f}")

    passed = len(mismatches) == 0
    return passed, {"checked_arrays": check_arrays, "mismatches": mismatches[:5]}


def verify_external_claim_flag(req, html):
    """Check that external claims are flagged appropriately.

    TWO-TIER PROVENANCE (v0.1.6, owner directive 2026-07-14):
      Tier A — Financial/Valuation claims (WCM, MCH, analyst targets):
        100% provenance required. Must have explicit flag (ước tính, estimate, source).
      Tier B — Widely-known company descriptors (store count, market share, factories):
        Memory allowed IF qualified as general background. Accepted qualifiers:
        "theo công bố" / "according to disclosures" / "ước tính" / "~" / "khoảng"
        This mirrors sell-side research: "Apple has 2B+ active devices" is background;
        "Revenue grew 18.6%" requires a source.

    A claim is UNFLAGGED only when it's a Tier A claim without provenance, OR a Tier B
    claim with NO qualifier whatsoever.
    """
    text = extract_all_text(html) if html else ""
    patterns = req["verification"].get("patterns", [])
    must_flag = req["verification"].get("must_flag", "ước tính|estimate")
    adjacent_window = req["verification"].get("adjacent_window", 200)

    # Tier B qualifiers — these make widely-known company descriptors acceptable
    # without requiring inline citation (like sell-side research).
    tier_b_qualifiers = [
        r"theo\s+(?:công\s+ bố|báo\s+cáo|disclosure|bctc|issuer|company)",
        r"according\s+to\s+(?:company|disclosure|report)",
        r"ước\s+tính", r"estimate", r"external", r"marketing",
        r"~",  # approximate marker (~38% thị phần)
        r"khoảng", r"xấp\s+xỉ", r"approximately", r"roughly",
        r"general\s+background", r"thông\s+tin\s+chung",
        r"nổi\s+tiếng", r"widely\s+known", r"phổ\s+biến",
        r"market\s+leader", r"thống\s+trị", r"dẫn\s+đầu",
    ]
    tier_b_qualifier_pattern = "|".join(tier_b_qualifiers)

    # Classify patterns into tiers
    # Tier A: financial/analyst claims (WCM, MCH — require strict provenance)
    tier_a_patterns = [p for p in patterns if "WCM" in p or "MCH" in p]
    # Tier B: company descriptors (store count, market share — allow qualifier)
    tier_b_patterns = [p for p in patterns if p not in tier_a_patterns]

    unflagged_claims = []
    total_claims = 0
    for pattern in patterns:
        is_tier_a = pattern in tier_a_patterns
        for m in re.finditer(pattern, text, re.I):
            total_claims += 1
            ctx = text[max(0, m.start()-adjacent_window):m.end()+adjacent_window]
            if is_tier_a:
                # Tier A: must have strict provenance flag
                if not re.search(must_flag, ctx, re.I):
                    unflagged_claims.append({"pattern": pattern, "match": m.group(0)[:40],
                                            "tier": "A", "reason": "strict provenance required"})
            else:
                # Tier B: accept either strict flag OR a tier-B qualifier
                if not re.search(must_flag, ctx, re.I) and not re.search(tier_b_qualifier_pattern, ctx, re.I):
                    unflagged_claims.append({"pattern": pattern, "match": m.group(0)[:40],
                                            "tier": "B", "reason": "needs qualifier (~, khoảng, theo công bố, or ước tính)"})
    passed = (total_claims == 0) or (len(unflagged_claims) == 0)
    return passed, {"external_claims_found": total_claims,
                    "unflagged": unflagged_claims[:5],
                    "adjacent_window": adjacent_window,
                    "tier_a_patterns": len(tier_a_patterns),
                    "tier_b_patterns": len(tier_b_patterns),
                    "patch_note": "v0.1.6: two-tier provenance — Tier A strict, Tier B qualifier-allowed"}


def verify_div_balance(req, html):
    """Check div open = div close."""
    if not html:
        return False, {"error": "no html"}
    opens = len(re.findall(r"<div[ >]", html))
    closes = len(re.findall(r"</div>", html))
    passed = opens == closes
    return passed, {"opens": opens, "closes": closes}


def _check_claim_citation(text, claim_patterns, source_kws, window=150, uncertainty_kws=None):
    """FIX-6/G14 (review V4 Pro + V4 Flash) — helper citation dùng chung.

    5 hàm kiểm tra (REQ-029 source, REQ-038 claim basis, REQ-039 industry,
    REQ-047 macro, REQ-054 causal) chia sẻ cùng pattern: quét claim → check
    source keyword trong cửa sổ. Hiện tại các hàm đó vẫn giữ code riêng (rủi ro
    phá 67/67 nếu refactor nội dung), nhưng helper này là cơ sở để gộp trong
    refactor tương lai — ưu tiên thấp theo cả 2 review.

    Args:
      text: narrative text (đã strip script/style qua _narrative_text)
      claim_patterns: list regex — mẫu claim cần kiểm tra
      source_kws: list str — keyword nguồn hợp lệ (named, không generic)
      window: số chars quanh claim để tìm source
      uncertainty_kws: list str — marker ước tính (claim có marker → OK)
    Returns: (issues, checked) — issues list, số claim đã check
    """
    issues = []
    checked = 0
    for pat in claim_patterns:
        for m in re.finditer(pat, text, re.I):
            checked += 1
            ctx = text[max(0, m.start() - 60):m.end() + window].lower()
            has_source = any(kw in ctx for kw in source_kws)
            has_uncert = uncertainty_kws and any(kw in ctx for kw in uncertainty_kws)
            if not has_source and not has_uncert:
                issues.append(f"claim '{m.group(0)}' không có named source trong ±{window} chars")
    return issues, checked


def verify_source_citation(req, html):
    """REQ-029: Source citation check — mọi số liệu trong narrative phải có nguồn.

    Quét narrative (text content, không CSS/JS) tìm số liệu định lượng
    không có source keyword gần đó. Key metrics phải cite ít nhất 1 lần.

    Lesson Learned #7-10: agent đưa %, multiples, drawdown không cite nguồn.
    """
    if not html:
        return False, {"error": "no html"}

    # Extract text content only (strip tags, CSS, JS)
    # Remove <style> and <script> blocks
    text_html = re.sub(r'<style[^>]*>.*?</style>', '', html, flags=re.DOTALL)
    text_html = re.sub(r'<script[^>]*>.*?</script>', '', text_html, flags=re.DOTALL)
    text = re.sub(r'<[^>]+>', ' ', text_html)
    text = re.sub(r'\s+', ' ', text).strip()

    source_keywords = ['bctc', 'theo', 'nguồn', 'source', 'ref-', 'vnstock', 'data',
                       'ước tính', 'giả định', 'khoảng', 'tiếp cận', 'estimate',
                       'tính từ', 'recompute', 'sponsor', 'kiểm toán', 'công bố']
    uncertainty_markers = ['ước tính', 'giả định', 'khoảng', 'có thể', 'xấp xỉ',
                           'tiếp cận', 'estimate', 'approximate']

    # Find all quantitative claims: numbers with units
    # Pattern: digits + (tỷ/nghìn/%/×/x/VND)
    number_pattern = re.compile(
        r'(\d[\d.,]*)\s*(tỷ\s*(?:vnd|đồng)?|nghìn\s*tỷ|ngàn\s*tỷ|%|phần\s*trăm|×|x\b|lần|vnd)',
        re.IGNORECASE
    )

    issues = []
    checked = 0
    unsourced = 0

    for m in number_pattern.finditer(text):
        val_str = m.group(1)
        unit = m.group(2).lower().strip()

        # Skip if value is 0 or clearly not a data point
        try:
            val = float(val_str.replace(',', '.'))
        except ValueError:
            continue
        if val == 0 or val == 100:
            continue

        checked += 1
        # Context window: 200 chars before and after
        start = max(0, m.start() - 200)
        end = min(len(text), m.end() + 200)
        context = text[start:end].lower()

        has_source = any(kw in context for kw in source_keywords)
        has_uncertainty = any(kw in context for kw in uncertainty_markers)

        if not has_source and not has_uncertainty:
            unsourced += 1
            snippet = text[max(0, m.start()-40):m.end()+40].strip()
            issues.append(f'"{val_str} {unit}" không có source gần — ...{snippet}...')

    # Key metrics must have at least 1 DIRECT source citation (V3: not just uncertainty)
    # FIX-3b (review V4 Pro M4): 'data'/'theo' là từ generic xuất hiện khắp narrative
    # ("không có data", "theo đánh giá"...) → trước đây key metric vẫn PASS dù không
    # có nguồn thật. Key metrics giờ yêu cầu NAMED source: tên nguồn cụ thể.
    key_metrics = ['P/E', 'P/B', 'CAGR', 'ROE', 'ROA', 'EPS']
    direct_source_kws = ['bctc', 'vnstock', 'ref-', 'sponsor', 'kiểm toán', 'công bố',
                         'hose', 'filings', 'báo cáo tài chính', 'cafef', 'vietstock',
                         'finance', 'api']
    key_metric_issues = []
    for km in key_metrics:
        if km.lower() in text.lower():
            # Find first occurrence
            idx = text.lower().find(km.lower())
            # FIX-3b (review V4 Pro M4): window 300 quá rộng → source của metric
            # KHÁC ("theo BCTC" của EPS) nằm trong window → P/E "mượn nguồn".
            # Giới hạn: source phải nằm trong CÙNG CÂU chứa metric (đến dấu câu,
            # tối đa 120 chars) — "P/E 9.3x, P/B 0.85x (theo vnstock)" hợp lệ,
            # "P/E 9.3x (ước tính). EPS... theo BCTC" không hợp lệ.
            # Lưu ý: dấu chấm trong số thập phân ("9.3x", "2.5%") KHÔNG phải hết câu.
            end = len(text)
            seg = text[idx:min(idx + 120, len(text))]
            m_sep = re.search(r"[.!?;](?!\d)", seg)
            if m_sep:
                end = idx + m_sep.start()
            context = text[idx:end].lower()
            if not any(kw in context for kw in direct_source_kws):
                key_metric_issues.append(f'{km}: không có DIRECT source cite trong CÙNG CÂU (V3: uncertainty marker không đủ; FIX-3b: từ generic "data"/"theo" không tính)')

    passed = (unsourced <= 3) and (len(key_metric_issues) == 0)
    evidence = {
        "checked_numbers": checked,
        "unsourced_numbers": unsourced,
        "threshold": "≤3 unsourced (V3: giảm từ 5 xuống 3)",
        "unsourced_examples": issues[:5],
        "key_metrics_without_source": key_metric_issues,
        "hardening": "V3 tightened tolerance 5→3; key metrics require DIRECT source (not uncertainty marker)",
    }
    return passed, evidence


def verify_price_source(req, html):
    """REQ-030: Price freshness check — giá phải fetch từ API, không tự điền.

    Check: price trong DATA object phải có source traceability.
    Nếu verified-dashboard-data.json có price nhưng không có price_fetched_at → suspect.

    Lesson Learned #6: price=62000 tự điền tay.
    """
    if not html:
        return False, {"error": "no html"}

    issues = []

    # Extract DATA object price
    data_match = re.search(r'price["\']?\s*[:=]\s*(\d+)', html)
    if not data_match:
        return True, {"note": "no price found in HTML (may be absent)"}

    price_val = int(data_match.group(1))
    if price_val == 0:
        issues.append("price = 0 in DATA")
        return False, {"price": 0, "issues": issues}

    # Check for price_fetched_at or price_source in DATA
    has_timestamp = bool(re.search(r'price_fetched_at|price_source|priceFetchedAt', html, re.IGNORECASE))
    has_api_source = bool(re.search(r'vnstock|sponsor|api.*price|fetch.*price', html, re.IGNORECASE))

    # Check for round numbers that suggest manual entry (60000, 50000, etc.)
    is_round = price_val % 1000 == 0

    if not has_timestamp and not has_api_source:
        if is_round:
            issues.append(f"price={price_val} là số tròn + không có price_fetched_at → NGHI NGOẠI tự điền tay")
        else:
            issues.append(f"price={price_val} không có price_fetched_at hoặc API source reference")

    # P2 (review V4 Flash): giá cũ vẫn PASS nếu chỉ check field tồn tại. Parse ngày
    # price_fetched_at — nếu >7 ngày so với hôm nay → FAIL "giá không fresh".
    # Kịch bản lọt: agent giữ timestamp 3 tháng trước + giá cũ → 67/67 PASS oan.
    # Check TẤT CẢ nguồn (data/overview.json, financials.json, task-state, HTML) —
    # bất kỳ nguồn nào cũ → FAIL (chống agent cập nhật 1 file, để file khác cũ).
    import datetime as _dt
    ts_candidates = []
    for src in ("data/overview.json", "data/financials.json"):
        d = _load_json_rel(src)
        if d and isinstance(d, dict):
            cand = (d.get("overview", {}) or {}).get("price_fetched_at") or d.get("price_fetched_at")
            if cand:
                ts_candidates.append((src, str(cand)))
    ts_state = _load_json_rel(".task-state/task-state.json")
    if ts_state:
        p1 = (ts_state.get("phases", {}).get("phase1_data", {}) or {}).get("result") or {}
        if p1.get("price_fetched_at"):
            ts_candidates.append(("task-state", str(p1["price_fetched_at"])))
    ts_html = re.search(r'price_fetched_at["\']?\s*[:=]\s*["\']?(\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2})', html or "")
    if ts_html:
        ts_candidates.append(("html", ts_html.group(1)))
    evidence_fresh = {"sources_checked": [s[0] for s in ts_candidates]}
    if ts_candidates:
        for source, ts_str in ts_candidates:
            try:
                fetched = _dt.datetime.fromisoformat(ts_str[:19].replace(" ", "T"))
                age_days = (_dt.datetime.now() - fetched).days
                if age_days > 7:
                    issues.append(f"price_fetched_at ({source}) = {ts_str} cũ {age_days} ngày (>7) — giá không fresh")
                evidence_fresh.setdefault("per_source", {})[source] = {"ts": ts_str, "age_days": age_days, "fresh": age_days <= 7}
            except (ValueError, TypeError):
                evidence_fresh.setdefault("per_source", {})[source] = {"ts": ts_str, "parsed": False}
        per_src = evidence_fresh.get("per_source", {})
        evidence_fresh["any_fresh"] = any(v.get("fresh") for v in per_src.values()) if per_src else False

    passed = len(issues) == 0
    evidence = {
        "price_value": price_val,
        "has_price_fetched_at": has_timestamp,
        "has_api_source_reference": has_api_source,
        "is_round_number": is_round,
        "freshness": evidence_fresh,
        "issues": issues,
    }
    return passed, evidence


def verify_drawdown_source(req, html):
    """REQ-031: Drawdown verification — claim drawdown phải có data thật.

    Nếu narrative nói "drawdown X%" → phải có max_drawdown trong DATA.
    Nếu KHÔNG có data → phải ghi "ước tính".

    Lesson Learned #9: "30-50% drawdown" không có data thật.
    """
    if not html:
        return False, {"error": "no html"}

    # Extract text content
    text_html = re.sub(r'<style[^>]*>.*?</style>', '', html, flags=re.DOTALL)
    text_html = re.sub(r'<script[^>]*>.*?</script>', '', text_html, flags=re.DOTALL)
    text = re.sub(r'<[^>]+>', ' ', text_html)
    text = re.sub(r'\s+', ' ', text).strip()
    # FIX VN100 (ACB 2026-08-02): cắt disclaimer/glossary trước khi quét —
    # "Cổ phiếu có thể giảm 30–50%" (disclaimer chuẩn mọi report) từng bị bắt
    # là drawdown claim → fail 71/71 mã. Claim trong disclaimer không phải phân tích.
    for marker in ("Giải thích thuật ngữ", "THUẬT NGỮ", "Glossary", "DISCLAIMER", "Disclaimer"):
        idx = text.find(marker)
        if idx > 0:
            text = text[:idx]
            break

    issues = []

    # Find drawdown claims: "drawdown X%" or "giảm X%" or "mất X triệu"
    # FIX cohort V4 (HPG): (1) chặn bắt nhầm "Max drawdown 52 tuần: -22,3%" —
    #     số "52" (tuần) từng bị bắt làm value; (2) cho phép dấu âm -22,3%.
    # FIX VN100 (ACB): chặn "(" trước số — "giảm mạnh (>3%)" (ngưỡng tần suất,
    #     không phải drawdown); pattern 2 chỉ còn "%" (drawdown đo bằng %,
    #     "mất 50 triệu" không so được với max_drawdown → false positive).
    drawdown_patterns = [
        r'(?:drawdown|sụt giảm|giảm(?:\s+xuống)?)[^.(%0-9]{0,30}?(-?\d+(?:[.,]\d+)?)(?!\s*tuần)\s*%',
        r'(?:mất|tổn\s*thất)[^.(%0-9]{0,30}?(-?\d+(?:[.,]\d+)?)(?!\s*tuần)\s*%',
        r'(?:có\s*thể\s*giảm|rủi\s*ro\s*giảm)[^.(%0-9]{0,30}?(\d+(?:[.,]\d+)?)\s*[-–]\s*(\d+(?:[.,]\d+)?)\s*%',
    ]

    drawdown_claims = []
    for pat in drawdown_patterns:
        for m in re.finditer(pat, text, re.IGNORECASE):
            val = m.group(1) if m.lastindex >= 1 else '?'
            context = text[max(0, m.start()-100):m.end()+100]
            drawdown_claims.append({
                'value': val,
                'context': context.strip()[:120],
            })

    # Check if DATA has max_drawdown — FIX-3a (review V4 Pro M3): trước đây check
    # regex trên TOÀN BỘ html → JS config/chart data attribute cũng làm match
    # ('drawdownData' trong script) → guard không trigger dù narrative không dùng.
    # Giờ chỉ tin 2 nguồn: narrative text (script/style đã strip) HOẶC data file.
    narrative_lower = _narrative_text(html).lower()
    has_drawdown_data = bool(re.search(r'max_drawdown|drawdown\s*52|drawdown\s*data|sụt\s*\d+%|giảm\s*từ.*đỉnh', narrative_lower))
    dd_data_file = _load_json_rel("verified-dashboard-data.json")
    if dd_data_file and isinstance(dd_data_file, dict):
        if dd_data_file.get("max_drawdown_52w") or dd_data_file.get("drawdown"):
            has_drawdown_data = True

    # Giá trị max_drawdown THẬT (nếu có): từ narrative ("max drawdown 52 tuần của 28.5%")
    # hoặc data file — dùng để so khớp claim, không chỉ "có data" là đủ.
    # Lưu ý: ".{0,60}?" vượt qua số trung gian ("52 tuần") — [^0-9] sẽ kẹt.
    dd_value = None
    m_dd = re.search(r'max[_\s]*drawdown.{0,60}?(-?\d+(?:[.,]\d+)?)\s*%', narrative_lower)
    if m_dd:
        try:
            dd_value = float(m_dd.group(1).replace(',', '.'))
        except ValueError:
            dd_value = None
    if dd_value is None and dd_data_file and isinstance(dd_data_file, dict):
        try:
            dd_value = float(dd_data_file.get("max_drawdown_52w"))
        except (TypeError, ValueError):
            dd_value = None

    # Check if claims have uncertainty markers — "có thể" KHÔNG đủ (M3: "giá có thể
    # sụt giảm 60-70%" vẫn là claim số cụ thể cần nguồn). Marker hợp lệ phải là
    # "ước tính/giả định/khoảng..." — thể hiện số KHÔNG phải từ data thật.
    uncertainty_keywords = ['ước tính', 'giả định', 'khoảng', 'ngành', 'history',
                            'lịch sử', 'thường', 'trung bình', 'estimate']

    for claim in drawdown_claims:
        ctx_lower = claim['context'].lower()
        has_uncertainty = any(kw in ctx_lower for kw in uncertainty_keywords)
        # FIX-3a: claim có số phải KHỚP dd_value thật (±15pp) — "có data ở đâu đó
        # trong report" không còn đủ. Report sạch có "max drawdown 52 tuần của 33%"
        # nhưng claim "sụt giảm 30-50%" bịa vẫn phải bị bắt.
        # FIX V4: so theo TRỊ TUYỆT ĐỐI — dd_value có thể âm (-40.6%), claim "giảm 50%"
        # dương; so dấu trực tiếp làm claim hợp lệ thành fail (bug phá golden CTD).
        matches_dd = False
        if dd_value is not None:
            try:
                claim_val = float(claim['value'].replace(',', '.'))
                matches_dd = abs(abs(claim_val) - abs(dd_value)) <= 15
            except ValueError:
                matches_dd = False
        if not has_drawdown_data and not has_uncertainty:
            issues.append(f"drawdown claim '{claim['value']}%' không có data thật và không có marker 'ước tính'")
        elif has_drawdown_data and not matches_dd and not has_uncertainty:
            issues.append(f"drawdown claim '{claim['value']}%' KHÔNG khớp max_drawdown thật ({dd_value}% nếu có) và không có marker 'ước tính'")

    # If no drawdown claims at all → check vacuous-pass guard (V3)
    if not drawdown_claims:
        # V3: If tech-profile section exists AND mentions "rủi ro giảm" → should have drawdown
        tech_profile_text = extract_section_text(html, "sec-tech-profile") or ""
        has_risk_discussion = bool(re.search(r"rủi ro.*giảm|drawdown|sụt giảm", tech_profile_text, re.I))
        if has_risk_discussion and not has_drawdown_data:
            return False, {
                "note": "tech-profile discusses price risk but no drawdown data AND no drawdown claim",
                "hint": "nếu bàn về rủi ro giảm giá, phải có max_drawdown từ data hoặc ghi 'ước tính'",
                "hardening": "V3: vacuous-pass guard — risk discussion without drawdown data → FAIL",
            }
        # V3b: nếu CÓ max_drawdown data mà sec-risk không định lượng rủi ro giảm giá → FAIL
        # FIX-1 (review V4 Pro): `_contract()` không tồn tại → NameError crash. Thay bằng
        # _load_json_rel (helper có sẵn). Trước đây nhánh này là "bom nổ chậm".
        contract = _load_json_rel("verified-dashboard-data.json")
        has_dd_data = has_drawdown_data or bool(contract and contract.get("max_drawdown_52w"))
        sec_risk = extract_section_text(html, "sec-risk")
        if has_dd_data and sec_risk and len(sec_risk) > 100:
            if not re.search(r'\d[.,\d]*\s*%', sec_risk):
                return False, {
                    "note": "CÓ max_drawdown data nhưng sec-risk không định lượng rủi ro giảm giá (%)",
                    "hint": "sec-risk phải trích max_drawdown_52w từ data thay vì bỏ qua",
                    "hardening": "V3b: data-exists-but-risk-unquantified guard",
                }
        return True, {"note": "no drawdown claims found in narrative"}

    passed = len(issues) == 0
    evidence = {
        "drawdown_claims_found": len(drawdown_claims),
        "claims": [c['context'] for c in drawdown_claims[:5]],
        "has_max_drawdown_data": has_drawdown_data,
        "issues": issues,
    }
    return passed, evidence


def verify_chart_runtime_check(req, html):
    """REQ-028: Render-readiness proxy cho runtime chart render.

    Không có browser trong verifier, nhưng check 3 điều kiện cần cho chart render:
    1. Mỗi canvas ID referenced trong Chart(...) call phải có <canvas id="..."> element
    2. Mỗi Chart(...) call phải có data.datasets (không rỗng)
    3. Không có duplicate canvas ID (Chart.js strict mode fail)

    Học từ PNJ v2 test: 13 charts claimed render nhưng template có duplicate canvas
    sau </body> → Playwright strict mode violation.
    """
    if not html:
        return False, {"error": "no html"}

    issues = []

    # 1. Extract all canvas IDs from HTML
    canvas_ids = re.findall(r'<canvas[^>]*id=["\']([^"\']+)["\']', html)
    canvas_id_counts = {}
    for cid in canvas_ids:
        canvas_id_counts[cid] = canvas_id_counts.get(cid, 0) + 1

    # 2. Extract Chart(...) targets: $('chartId') or getElementById('chartId')
    # PATCH (P0-1): distinguish UNCONDITIONAL refs from CONDITIONAL/fallback refs.
    #   - conditional:  `if ($(id)) new Chart($(id)...)`        → canvas optional, not required
    #   - fallback:     `new Chart($(primary) || $(fallback))`  → only primary required
    # Previously ALL chart-like refs were treated as required → false positives on reports
    # that legitimately guard optional charts. (Audit 2026-07-12: REQ-028 FP on clean PNJ.)
    chart_targets = re.findall(r"""\$\(['"]([^'"]+)['"]\)|getElementById\(['"]([^'"]+)['"]\)""", html)
    referenced_ids = set()
    unconditional_required = set()   # ids that MUST have a canvas
    for t in chart_targets:
        cid = t[0] or t[1]
        if not (cid.startswith('chart') or cid.startswith('Chart')):
            continue
        referenced_ids.add(cid)
        # find the JS statement containing this ref to classify it
        for m in re.finditer(re.escape(cid), html):
            ctx = html[max(0, m.start()-90):m.end()+20]
            if re.search(r'\bif\s*\(\s*\$\(\s*[\'"]' + re.escape(cid), ctx) or \
               re.search(r'\bif\s*\(\s*document\.getElementById', ctx):
                break  # conditional — not required
            # fallback pattern: $(primary) || $(cid)  → cid is the fallback, primary required
            if re.search(r"\$\([^)]+\)\s*\|\|\s*\$\(\s*[\"']" + re.escape(cid), ctx):
                break  # this cid is a fallback, not required
            unconditional_required.add(cid)

    # 3. Check each UNCONDITIONAL referenced chart ID has canvas element
    # PATCH (P0-1): only missing *unconditional* canvases count. A handful of optional
    # charts absent is a WARN (defect), not a deploy-blocking FAIL.
    missing_canvas_required = [rid for rid in unconditional_required if rid not in canvas_id_counts]
    missing_canvas_optional = [rid for rid in (referenced_ids - unconditional_required) if rid not in canvas_id_counts]

    # 4. Check duplicate canvas IDs
    duplicates = {cid: count for cid, count in canvas_id_counts.items() if count > 1}

    # 5. Check DATA object exists (charts depend on it)
    has_data_obj = bool(re.search(r'const\s+DATA\s*=', html))

    # 6. Check Chart.js loaded
    has_chart_js = bool(re.search(r'new\s+Chart\s*\(', html))

    # PATCH (P0-1): split issues into critical (FAIL) vs advisory (WARN).
    #   FAIL: duplicate canvas IDs (strict-mode crash), no DATA, no Chart.js,
    #         canvas after </body>, OR many required canvases missing (>30%).
    #   WARN (not FAIL): a few optional/single required canvas absent.
    critical_issues = []
    advisory = []
    if duplicates:
        critical_issues.append(f"Duplicate canvas IDs (strict mode risk): {duplicates}")
    if not has_data_obj:
        critical_issues.append("No `const DATA =` object found — charts will crash")
    if not has_chart_js:
        critical_issues.append("No `new Chart(` calls found")
    if missing_canvas_required:
        pct_missing = len(missing_canvas_required) / max(len(unconditional_required), 1)
        msg = f"Required canvas missing: {missing_canvas_required} ({pct_missing:.0%} of {len(unconditional_required)} unconditional charts)"
        if pct_missing > 0.30:
            critical_issues.append(msg)
        else:
            advisory.append(msg)
    if missing_canvas_optional:
        advisory.append(f"Optional canvas absent (not deploy-blocking): {missing_canvas_optional}")
    issues = critical_issues + [f"WARN: {a}" for a in advisory]

    # Also check: canvas after </body> (template illustration leak — PNJ bug)
    body_close = html.rfind('</body>')
    html_close = html.rfind('</html>')
    if body_close >= 0 and html_close >= 0 and body_close < html_close:
        trailing = html[body_close:html_close]
        trailing_canvas = re.findall(r'<canvas[^>]*id=["\']([^"\']+)["\']', trailing)
        if trailing_canvas:
            critical_issues.append(f"Canvas elements after </body> (illustration leak): {trailing_canvas}")

    # PATCH (P0-1): PASS unless a CRITICAL issue. Advisory warnings don't block.
    passed = len(critical_issues) == 0
    return passed, {
        "canvas_ids_found": list(canvas_id_counts.keys()),
        "chart_ids_referenced": list(referenced_ids),
        "unconditional_required": list(unconditional_required),
        "missing_canvas_required": missing_canvas_required,
        "missing_canvas_optional": missing_canvas_optional,
        "duplicates": duplicates,
        "has_data_object": has_data_obj,
        "has_chart_js": has_chart_js,
        "critical_issues": critical_issues,
        "advisory": advisory,
        "issues": issues,
        "patch_note": "P0-1: conditional/fallback refs excluded from required; advisory split from critical",
    }


# ═══════════════════════════════════════════════════════════════
# V2 REVIEW-AGENT CHECKS (REQ-032..043)
# Chống 8 evasion patterns: keyword-stuffing, vacuous pass, bịa peer/segment/
# industry/tech data, trộn năm, cross-section mâu thuẫn, identity nhầm ticker.
# ═══════════════════════════════════════════════════════════════

_KNOWN_TICKERS = [
    # HOSE
    "ACB","BCM","BID","BVH","CTG","DIG","FPT","GAS","GEX","GMD","HDB","HPG","KDH",
    "MBB","MSN","MWG","NVL","OCB","PDR","PLX","PNJ","POW","REE","SAB","SSB","SSI",
    "STB","TCB","TPB","VCB","VHM","VIC","VJC","VNM","VPB","VRE","VSC","SBT",
    # HNX
    "CE1","IDC","MBS","NDN","NTP","PVS","SHB","SHS","TIG","VCS","VGS","VCG",
    # UpCOM
    "ACV","BAB","BVB","DPM","GVR","LPB","MCH","MSB","NAB","NKG","SMC","TCH","VGI",
    # NOTE: "VND" cố ý KHÔNG có trong danh sách — VND là đơn vị tiền tệ, xuất hiện
    # khắp report (giá 62,000 VND). VNDirect không nên được check như ticker lạ.
]

def _work_dir():
    return os.path.dirname(REPORT) if REPORT else "."

def _load_json_rel(path):
    """Load JSON relative to report work dir. Returns None on any failure."""
    full = os.path.join(_work_dir(), path)
    if not os.path.exists(full):
        return None
    try:
        with open(full) as f:
            return json.load(f)
    except Exception:
        return None

def _normalize_number(tok):
    """'12.345,6' / '12,345' / '9,078' / '12345' → float. VN thousands='.', decimal=','.
    Heuristic VN tiền tệ: 3 chữ số sau dấu phẩy = nghìn separator (9,078 = 9078);
    1-2 chữ số sau dấu phẩy = decimal (1,5 = 1.5). Dấu chấm luôn là nghìn separator
    khi có 3 chữ số sau (12.345 = 12345), nếu không (1.5) là decimal.

    FIX-9 (review V4 Pro): heuristic này ĐÃ phân biệt đúng '1,5 tỷ' (=1.5 tỷ, 1 digit
    sau phẩy → decimal) vs '1,500 tỷ' (=1500 tỷ, 3 digits sau phẩy → thousands).
    Bổ sung guard: nếu kết quả thousands-parse > 10^9 và không có dấu chấm nghìn đi kèm
    → khả năng cao là decimal bị hiểu nhầm → vẫn giữ thousands (VN tiền tệ ước lớn bình
    thường) nhưng note trong caller nếu cần. Không đổi logic."""
    tok = tok.strip().replace(" ", "").replace("đ", "")
    if not tok:
        return None
    # Both separators → phải phân biệt format (FIX VN100 v4 2026-08-02, bug GLM
    # tìm thấy: "33,797.9" từng parse thành 33.7979):
    #   VN: dot=thousands, comma=decimal   ("12.345,6"  → 12345.6)
    #   EN: comma=thousands, dot=decimal   ("33,797.9"  → 33797.9)
    # Heuristic: nhóm sau COMMA — 3 digits → EN (comma=thousand); 1-2 → VN.
    if "." in tok and "," in tok:
        after_comma = tok.split(",")[1].split(".")[0]
        if len(after_comma) == 3:
            tok = tok.replace(",", "")  # EN format
        else:
            tok = tok.replace(".", "").replace(",", ".")  # VN format
    elif "," in tok:
        after = tok.split(",")[1]
        if len(after) == 3:
            tok = tok.replace(",", "")
        else:
            tok = tok.replace(",", ".")
    elif "." in tok:
        after = tok.split(".")[1]
        if len(after) == 3:
            tok = tok.replace(".", "")
    try:
        return float(tok)
    except ValueError:
        return None

def _scale_to_tỷ(text_val, unit):
    """Convert a number+unit pair to tỷ VND."""
    unit = (unit or "").lower()
    if "nghìn tỷ" in unit or "ngan ty" in unit:
        return text_val * 1000
    if "triệu" in unit or "m" == unit.strip() or "tr" == unit.strip():
        return text_val / 1000
    if "tỷ" in unit or "tỉ" in unit or "b" == unit.strip():
        return text_val
    if "%" in unit:
        return text_val  # percent, no scaling
    return text_val

def _find_numeric_claims(text, keywords, window=120):
    """Find (keyword, value, context) claims: keyword then number within window."""
    claims = []
    for kw in keywords:
        # FIX V6 (HPG cohort 2026-08-01): nhận dấu âm — "CAGR lợi nhuận đạt -18.2%"
        # bị bắt thành 18.2 dương (pattern bắt đầu bằng \d) → mismatch 36.4pp.
        pat = re.compile(re.escape(kw) + r"[^0-9%]{0," + str(window) + r"}?(-?\d[\d.,]*)\s*(nghìn tỷ|tỷ|tỉ|triệu|tr|m|%)?", re.I)
        for m in pat.finditer(text):
            val = _normalize_number(m.group(1))
            if val is None:
                continue
            unit = m.group(2) or ""
            # V5 fix: số bắt được là năm (vd "CAGR giai đoạn 2021-2025 đạt 35.6%")
            # → lấy số có đơn vị/% theo sau trong cửa sổ, nếu không → bỏ qua claim
            if not unit and 1900 <= val <= 2100:
                look = text[m.end():m.end()+window]
                replaced = False
                for lm in re.finditer(r"(-?\d[\d.,]*)\s*(%|nghìn tỷ|tỷ|tỉ|triệu|tr|m)?", look):
                    nv = _normalize_number(lm.group(1))
                    if nv is None or (1900 <= nv <= 2100 and not lm.group(2)):
                        continue
                    val, unit = nv, lm.group(2) or ""
                    replaced = True
                    break
                if not replaced:
                    continue
            claims.append({
                "keyword": kw,
                "value": val,
                "unit": unit,
                "context": text[max(0, m.start()-80):m.end()+80].strip()[:160],
            })
    return claims


def verify_peer_provenance(req, html):
    """REQ-032: Peer data phải có nguồn (peers.json / verified-dashboard-data.json).

    Chống bịa peer (Lesson Learned #4): nếu narrative có số liệu định lượng về peer
    (P/E, P/B, market cap của công ty khác) → phải có peer data file, value khớp ±10%.

    V3 HARDENING: key-specific verification — mỗi peer claim "TICKER_X có P/E=Y" phải
    được verify với đúng ticker đó trong peers.json, không phải any-match toàn blob.
    """
    if not html:
        return False, {"error": "no html"}
    peer_text = extract_section_text(html, "sec-peer")
    fallback_narrative = False
    if not peer_text:
        # GAP-2 FIX (V4 Flash, đợt so sánh 31-vs-68): report không có sec-peer → KHÔNG
        # vacuous pass. Quét narrative chung tìm peer claim (ticker lạ + số + unit).
        # Trước đây `return True` → peer claim bịa ở section khác (sec-biz/thesis) lọt.
        peer_text = _narrative_text(html)
        fallback_narrative = True
        if not peer_text:
            return True, {"note": "no narrative text — nothing to check"}

    # Find quantitative peer claims (number near ticker/company or P/E P/B x-value)
    claims = []
    # pattern 1: ticker + number nearby (e.g. "HBC P/E 8x", "SSI vốn hóa 50.000 tỷ")
    # GAP-2 FIX: chế độ fallback siết hơn — bắt buộc unit (x|tỷ|tỉ|triệu|nghìn tỷ) sau số
    # + stoplist: EPS/ROE/CFO/DCF/DDM/ROS/RSI... là chỉ số của CHÍNH CTD, không phải peer
    # ticker; không siết thì "ROE 8.65%", "EPS 6,987x", "CFO 421" thành peer claim giả.
    ticker_pat = (r"\b([A-Z]{3})\b[^.%0-9]{0,60}?(\d[\d.,]*)\s*(x|tỷ|tỉ|triệu|nghìn tỷ)"
                  if fallback_narrative
                  else r"\b([A-Z]{3})\b[^.%0-9]{0,60}?(\d[\d.,]*)\s*(x|tỷ|tỉ|triệu|nghìn tỷ)?")
    STOPLIST = {"JSC", "VND", "USD", "EUR", "JPY", "GBP", "HKD", "CNY", "KRW",
                "HNX", "HSX", "OTC", "IPO", "EPS", "ROE", "ROA", "CFO", "DCF",
                "DDM", "DPS", "ROS", "RSI", "YTD", "EBITDA", "BVPS", "NII", "CASA",
                "NPL", "CAR", "P/E", "P/B", "PEG"}
    for m in re.finditer(ticker_pat, peer_text):
        ticker = m.group(1)
        # Skip if ticker is the target TICKER itself
        if ticker.upper() == TICKER.upper():
            continue
        # P0 (Sol 2026-08-09): stoplist áp dụng MỌI mode — "VND 32" (đơn vị + số trong
        # ticker A32) từng tạo peer claim giả cho 76 mã có chữ số trong ticker
        if ticker.upper() in STOPLIST:
            continue
        claims.append({"type": "ticker_value", "ticker": ticker, "value": m.group(2), "unit": m.group(3) or ""})
    # pattern 2: P/E or P/B multiple without ticker (e.g. "P/E 5x" — must come from data)
    # chỉ áp dụng trong sec-peer — narrative chung thì "P/E 10.4x" là của CTD, không phải peer
    if not fallback_narrative:
        vdd_pe = None
        _vdd = _load_json_rel("verified-dashboard-data.json")
        if isinstance(_vdd, dict):
            vdd_pe = _vdd.get("pe")
        # P0 (Sol 2026-08-09): chặn CHỮ CÁI giữa "P/E" và số — "P/E P/B C21 (chủ thể) 29.44"
        # từng bắt "21" (số trong ticker) thay vì 29.44 (giá trị thật)
        for m in re.finditer(r"P/\s*[EB]\s*[^0-9A-Za-z]{0,12}?(\d[\d.,]*)\s*x?", peer_text, re.I):
            try:
                val = float(m.group(1).replace(",", "."))
            except ValueError:
                continue
            # P0 (Sol 2026-08-09): P/E-P/B của CHỦ THỂ trong bảng peer (vd "A32 P/E 32")
            # không phải peer claim — bỏ qua nếu khớp định giá chủ thể ±10%
            if vdd_pe and abs(val - float(vdd_pe)) / max(abs(float(vdd_pe)), 0.001) <= 0.10:
                continue
            claims.append({"type": "multiple", "value": m.group(1)})

    # Check peer data source
    peers_data = None
    for cand in ("peers.json", "data/peers.json", "verified-dashboard-data.json"):
        d = _load_json_rel(cand)
        if d is not None:
            if cand.endswith("peers.json"):
                peers_data = d
            elif isinstance(d, dict) and ("peers" in d or "peer" in d):
                peers_data = d
        if peers_data is not None:
            break

    if not peers_data:
        # No peer data file → quantitative peer claims are unprovenanced
        if claims:
            return False, {
                "peer_claims_found": len(claims),
                "claims": [c for c in claims[:5]],
                "error": "quantitative peer claims without peers.json / verified-dashboard-data.json.peers",
                "hint": "phase1 phải fetch peers.json; nếu không fetch được → ghi 'chưa có data peer'",
            }
        return True, {"note": "peer names mentioned without quantitative claims — acceptable"}

    # V3 HARDENING: Key-specific verification
    # Extract peer list from peers_data
    peer_list = []
    if isinstance(peers_data, dict):
        peer_list = peers_data.get("peers", [])
        if not peer_list and "data" in peers_data:
            peer_list = peers_data["data"].get("peers", [])

    if not peer_list:
        # Fallback to old any-match behavior for unstructured peer data
        peers_blob = json.dumps(peers_data, ensure_ascii=False)
    else:
        peers_blob = None

    mismatches = []
    checked = 0
    for c in claims:
        v = _normalize_number(c.get("value"))
        if v is None:
            continue
        ticker = c.get("ticker")
        found = False

        # PATH A (V3): key-specific lookup if peer list is structured
        # V5 fix: claim KHÔNG kèm ticker (vd "P/E 15.2x") → so với MỌI peer
        if peer_list:
            for peer in peer_list:
                if not isinstance(peer, dict):
                    continue
                if ticker and peer.get("ticker", "").upper() != ticker.upper():
                    continue
                # Check all numeric fields of this peer
                for pv in peer.values():
                    if isinstance(pv, (int, float)):
                        if abs(v - pv) / max(abs(pv), 0.001) <= 0.10:
                            found = True
                            break
                if found:
                    break
            if found:
                checked += 1
                continue

        # PATH B (fallback): any-match in blob (for unstructured data)
        if not found and peers_blob:
            for pv in re.findall(r"\d[\d.,]*", peers_blob):
                pv_f = _normalize_number(pv)
                if pv_f is None or pv_f == 0:
                    continue
                if abs(v - pv_f) / max(abs(pv_f), 0.001) <= 0.10:
                    found = True
                    checked += 1
                    break

        if not found:
            ticker_info = f" (ticker {ticker})" if ticker else ""
            mismatches.append(f"peer claim value {c.get('value')}{c.get('unit','')}{ticker_info} not in peer data (±10%)")

    passed = len(mismatches) == 0
    return passed, {
        "peer_data_source": "peers.json" if peers_data else "verified-dashboard-data.json",
        "scan_source": "sec-peer" if not fallback_narrative else "narrative-fallback (no sec-peer)",
        "peer_list_structured": len(peer_list) > 0,
        "peer_claims_found": len(claims),
        "claims_verified": checked,
        "mismatches": mismatches[:5],
        "hardening": "V3 key-specific ticker matching (PATH A) + any-match fallback (PATH B)",
    }


def _verify_history_table(html, fin):
    """P0-A (Sol checkpoint 2026-08-08): parse BẢNG 5 năm trong report và đối chiếu
    TỪNG CELL (năm, cột) với financials.json — mutation 1 ô trong bảng phải FAIL.
    Bảng dạng: Năm | {rev_label} (tỷ VND) | Lợi nhuận (tỷ VND) | EPS (VND) | ROE (%) | VCSH (tỷ VND)."""
    issues = []
    if not html or not fin:
        return issues
    # tìm bảng có header Năm + cột tỷ VND
    for tbl in re.finditer(r"<table[^>]*class=\"tbl\"[^>]*>(.*?)</table>", html, re.DOTALL | re.I):
        body = tbl.group(1)
        if "Năm" not in body or "tỷ VND" not in body:
            continue
        headers = re.findall(r"<th[^>]*>(.*?)</th>", body, re.I)
        headers = [re.sub(r"<[^>]+>", "", h).strip().lower() for h in headers]
        # headers dạng: năm, doanh thu thuần (tỷ vnd), lợi nhuận (tỷ vnd), eps (vnd), roe (%), vcsh (tỷ vnd)
        col_map = {}
        for i, h in enumerate(headers):
            if h == "năm":
                col_map["year"] = i
            elif "doanh thu" in h or "operating income" in h:
                col_map["revenue"] = i
            elif "lợi nhuận" in h or "profit" in h:
                col_map["npat"] = i
            elif h.startswith("eps"):
                col_map["eps"] = i
            elif "vcsh" in h or "equity" in h:
                col_map["equity"] = i
        if "year" not in col_map or "revenue" not in col_map:
            continue
        for row_m in re.finditer(r"<tr[^>]*>(.*?)</tr>", body, re.DOTALL | re.I):
            cells = re.findall(r"<td[^>]*>(.*?)</td>", row_m.group(1), re.I)
            if len(cells) <= col_map.get("year", 99):
                continue
            y = re.sub(r"<[^>]+>", "", cells[col_map["year"]]).strip()
            if not re.match(r"^20\d\d$", y):
                continue
            def cellval(idx):
                if idx is None or idx >= len(cells):
                    return None
                v = re.sub(r"<[^>]+>", "", cells[idx]).strip().replace(",", "")
                try:
                    return float(v)
                except ValueError:
                    return None
            checks = [("revenue", "revenue_ty", 1.0, 2.0, 0.05), ("npat", "npatmi_ty", 1.0, 2.0, 0.05),
                      ("eps", "eps_vnd", 1.0, 2.0, 0.5), ("equity", "equity_ty", 1.0, 2.0, 0.05)]
            for col_key, fin_key, scale, tol, half_step in checks:
                idx = col_map.get(col_key)
                if idx is None:
                    continue
                gt = (fin.get(fin_key) or {}).get(y)
                cell = cellval(idx)
                if gt is None or cell is None:
                    continue
                gt_scaled = float(gt) * scale
                denom = max(abs(gt_scaled), abs(cell), 0.001)
                # P0 (CB-2 REQ-033 2026-08-08): bảng hiển thị 1 decimal — giá trị nhỏ
                # (npat 0.02 tỷ → "0.0") bị false mismatch. Tolerance động theo sai số
                # hiển thị tối đa (0.05 tỷ = nửa bước 0.1).
                tol_dyn = max(tol, (half_step + 0.001) / max(abs(gt_scaled), 0.001) * 100)
                if abs(cell - gt_scaled) / denom * 100 > tol_dyn:
                    issues.append(
                        f"BẢNG history: {col_key} {y} cell={cell:,.2f} ≠ data {gt_scaled:,.2f} (lệch >{tol_dyn:.1f}%)")
    return issues


def verify_cross_section_consistency(req, html):
    """REQ-033: Cùng 1 số liệu key ở nhiều section phải khớp (±5%).

    Trích (metric, year?, value) từ mọi section. Nếu 2 section cùng year-metric
    lệch >5% → FAIL. Nếu metric không gắn year → so chung nhóm.

    V3 HARDENING: also check unanchored claims within same section — nếu cùng section
    mention cùng 1 metric 2 lần khác số → FAIL (internal inconsistency).
    """
    if not html:
        return False, {"error": "no html"}

    metrics = {
        "revenue": [r"doanh thu", r"revenue"],
        "net_profit": [r"lợi nhuận ròng", r"lợi nhuận sau thuế", r"LNST", r"npatmi", r"net profit", r"NPAT"],
        "eps": [r"EPS"],
        "pe": [r"P\s*/\s*E", r"P/E"],
        "pb": [r"P\s*/\s*B", r"P/B"],
        "market_cap": [r"vốn hóa", r"market cap", r"marketcap"],
        "total_assets": [r"tổng tài sản", r"total assets"],
        "equity": [r"vốn chủ sở hữu", r"equity"],
    }
    # Metric không đo bằng % (revenue/profit/eps/assets/equity/market cap là số tuyệt đối)
    NO_PCT_UNIT = {"revenue", "net_profit", "eps", "market_cap", "total_assets", "equity"}

    # Collect per-section claims
    CLAIM_SECTIONS = {
        "sec-hero", "sec-exec", "sec-biz", "sec-industry", "sec-history",
        "sec-segment", "sec-thesis", "sec-valuation", "sec-bs",
        "sec-risk", "sec-scenario", "sec-insight-1", "sec-insight-2", "sec-insight-3",
    }
    section_ids = set(re.findall(r'<section[^>]*id="(sec-[a-z0-9-]+)"', html)) & CLAIM_SECTIONS
    per_metric = {}  # metric → [(year_or_None, value, section, context)]
    for sid in sorted(section_ids):
        sec_text = extract_section_text(html, sid)
        if not sec_text or len(sec_text) < 30:
            continue
        for metric, kws in metrics.items():
            for kw in kws:
                # FIX-4b (nghiệm thu V4 Pro M2 gốc): regex cũ `[^0-9]{0,60}?(\d...)`
                # ăn "2025" (năm) làm số trước, rồi skip year → số THẬT phía sau
                # ("Doanh thu thuần năm 2025 đạt 50,000 tỷ") không bao giờ capture.
                # Thêm optional year prefix: keyword → ... → (năm)? → ... → SỐ.
                pat = re.compile(kw + r"[^0-9]{0,60}?(?:20\d\d(?!\d)(?![.,]\d)[^0-9]{0,60}?)?(?<![A-Za-z])(-?\d[\d.,]*)\s*(nghìn tỷ|tỷ|tỉ|triệu|tr|x|%)?", re.I)
                for m in pat.finditer(sec_text):
                    val = _normalize_number(m.group(1))
                    if val is None:
                        continue
                    unit = m.group(2) or ""
                    # Fallback dự phòng: nếu bắt được năm-as-value (regex không ăn
                    # optional year vì lý do nào đó) → quét số kế tiếp trong 60 chars
                    if 2000 <= val <= 2099 and not unit:
                        nxt = re.search(r"(-?\d[\d.,]*)\s*(nghìn tỷ|tỷ|tỉ|triệu|tr|x|%)?", sec_text[m.end():m.end()+60])
                        if nxt:
                            val = _normalize_number(nxt.group(1))
                            unit = nxt.group(2) or ""
                        else:
                            continue
                    if unit == "%" and metric in NO_PCT_UNIT:
                        continue
                    between = sec_text[m.start():m.start(1)]
                    # VN100 v4 (VJC 2026-08-02): số đầu tiên sau kw trong 60 chars có
                    # thể thuộc CLAIM KHÁC — "LNST ... P/E raw = 33.53×" (33.53 là P/E)
                    # và "EPS × BVPS) ... P/E 33.53" bị gán nhầm metric → false
                    # inconsistency. between chứa nhãn metric khác = contamination.
                    if re.search(r"P\s*/\s*E|P\s*E\b|P\s*/\s*B|P\s*B\b|ROE\b|ROA\b|Graham|BVPS|WACC|Tech\s*Score", between, re.I):
                        continue
                    # G4 (review V4 Flash): "P/E trung bình ngành 12x" là claim NGÀNH,
                    # không phải claim của CTD → exclude ngữ cảnh này
                    # VN100 v4 (2026-08-02, VJC): thêm expand/co/bull/bear — P/E của
                    # KỊCH BẢN khác nhau (bull expand 170.8× vs bear co 23.5×) là thiết
                    # kế, không phải internal inconsistency.
                    if re.search(r"cagr|tăng trưởng|growth|biên|margin|ngành|thị trường|"
                                 r"trung bình|median|bình quân|5\s*năm|5y|peer|dự phóng|"
                                 r"forward|target|ước tính|khoảng|expand|co\s+về|co\s+lại|"
                                 r"bull|bear", between, re.I):
                        continue
                    # VN100 v4 (VJC): P/E/P/B phải có đơn vị × — "P/E (peer median)
                    # 636,742" (giá trị VND của phương pháp) bị bắt nhầm thành P/E
                    # value → so với "P/E 33.53×" → false mismatch.
                    if metric in ("pe", "pb") and unit not in ("x", "×"):
                        continue
                    scaled = _scale_to_tỷ(val, unit)
                    if 2000 <= scaled <= 2099 and not unit:
                        continue
                    if not unit and scaled < 20:
                        continue
                    # FIX-4b (review V4 Pro M2): năm có thể cách claim >60 chars
                    # ("...50.000 tỷ đồng ... trong năm 2025"). Nới window ±100 và
                    # chọn năm GẦN claim nhất (trước hoặc sau) — tránh hút năm câu khác.
                    # G5 (review V4 Flash, bảng transposed sec-history): ym.start() đếm
                    # trong ctx (0→~200) còn m.start() đếm trong sec_text (0→full) —
                    # 2 hệ tọa độ lệch offset → "2025" cách 10 ký tự bị tính 134,
                    # "2021" cách 123 ký tự bị tính 21 → gán nhầm năm cho claim.
                    # Fix: cộng offset để đưa về cùng hệ tọa độ sec_text.
                    base = max(0, m.start() - 100)
                    ctx = sec_text[base:m.end()+100]
                    best_year, best_dist = None, None
                    for ym in re.finditer(r"20\d\d", ctx):
                        y_abs = base + ym.start()
                        dist = min(abs(y_abs - m.start()), abs(y_abs + 2 - m.start()))
                        if best_year is None or dist < best_dist:
                            best_year, best_dist = ym.group(0), dist
                    year = best_year
                    per_metric.setdefault(metric, []).append({
                        "year": year, "value": scaled, "section": sid,
                        "context": ctx.strip()[:120],
                    })
                # FIX-4 (review V4 Pro): không break — chạy cả 2 keyword của metric
                # (vd cả "doanh thu" lẫn "revenue") để không bỏ sót match

    # V3 HARDENING: Internal section consistency (unanchored → check within same section)
    # For each section, if a metric appears twice with different values → internal inconsistency
    internal_issues = []
    for sid in sorted(section_ids):
        sec_items = {}
        for metric, items in per_metric.items():
            sec_vals = [it for it in items if it["section"] == sid and it["year"] is None]
            if len(sec_vals) >= 2:
                vmin, vmax = min(it["value"] for it in sec_vals), max(it["value"] for it in sec_vals)
                if vmin > 0 and (vmax - vmin) / vmin > 0.05:
                    internal_issues.append(
                        f"section {sid}: {metric} values {vmin:,.1f} vs {vmax:,.1f} internally inconsistent"
                    )

    issues = list(internal_issues)
    checked_pairs = 0
    for metric, items in per_metric.items():
        if len(items) < 2:
            continue
        # group by year (None = "current" bucket)
        buckets = {}
        for it in items:
            buckets.setdefault(it["year"], []).append(it)
        for year, group in buckets.items():
            if len(group) < 2:
                continue
            vals = [g["value"] for g in group]
            vmin, vmax = min(vals), max(vals)
            if vmin == 0:
                continue
            diff_pct = (vmax - vmin) / vmin * 100
            checked_pairs += 1
            if diff_pct > 5:
                issues.append(
                    f"{metric}{'/'+year if year else ''}: {vmin:,.1f} vs {vmax:,.1f} (lệch {diff_pct:.1f}% > 5%) — "
                    + "; ".join(f"{g['section']}: {g['value']:,.1f}" for g in group)
                )

    # P0-A (Sol checkpoint 2026-08-08): đối chiếu TỪNG CELL bảng history với financials —
    # mutation 1 ô trong bảng phải FAIL (trước đây chỉ DATA JS + prose được so).
    fin_tbl = _load_json_rel("data/financials.json")
    if fin_tbl:
        issues += _verify_history_table(html, fin_tbl)

    passed = len(issues) == 0
    return passed, {
        "sections_scanned": len(section_ids),
        "metrics_with_multiple_claims": {m: len(v) for m, v in per_metric.items() if len(v) > 1},
        "pairs_compared": checked_pairs,
        "internal_inconsistencies": internal_issues[:5],
        "issues": issues[:5],
        "note": "V3: thêm internal section consistency check cho unanchored claims; P0-A: table cells vs financials",
    }


def verify_temporal_alignment(req, html):
    """REQ-034: Số liệu theo năm trong narrative phải khớp data file đúng năm.

    Chống trộn năm: 'doanh thu 2024 = 30.000' khi data 2024 = 22.905 → FAIL.
    Chart years phải khớp financials years.
    """
    if not html:
        return False, {"error": "no html"}
    fin = _load_json_rel(req["verification"].get("data_file", "data/financials.json"))
    if not fin:
        return False, {"error": f"financials.json not found: {req['verification'].get('data_file')}"}

    issues = []
    checked = 0

    # 1. Narrative claims with explicit year (năm có thể đứng TRƯỚC keyword
    #    "năm 2025 doanh thu..." HOẶC SAU số "...30,699 tỷ (FY2025)")
    # Tables have their own exact year/cell oracle in REQ-033.  Flattening a
    # multi-row table destroys row boundaries and can attach an EPS cell to the
    # neighbouring row's year, so temporal prose checking excludes tables.
    prose_html = re.sub(r"<table[^>]*>.*?</table>", " ", html, flags=re.I | re.S)
    text = _narrative_text(prose_html)
    metric_kws = {
        "revenue_ty": [r"doanh thu", r"revenue"],
        "npatmi_ty": [r"lợi nhuận ròng", r"lợi nhuận sau thuế", r"LNST", r"npatmi"],
        "eps_vnd": [r"EPS"],
    }
    NO_PCT_UNIT = {"revenue_ty", "npatmi_ty", "eps_vnd"}
    for field, kws in metric_kws.items():
        gt = fin.get(field)
        if not isinstance(gt, dict):
            continue
        for kw in kws:
            pat = re.compile(kw + r"[^0-9]{0,80}?(?<![A-Za-z])(-?\d[\d.,]*)\s*(nghìn tỷ|tỷ|tỉ|triệu|tr|vnd|đồng)?", re.I)
            for m in pat.finditer(text):
                claimed = _normalize_number(m.group(1))
                unit = m.group(2) or ""
                if claimed is None:
                    continue
                # V5 fix: "34%" — unit regex lazy-empty bỏ qua % → kiểm tra ký tự sau số
                if not unit and "%" in text[m.end(1):m.end(1)+2]:
                    unit = "%"
                # Batch-3 (FP phát hiện khi test G6): "doanh thu ... giá hiện tại
                # 71.700 VND" — window ăn số của câu khác. Số đơn vị VND/đồng là GIÁ,
                # không phải revenue/npatmi/eps → bỏ qua.
                if unit.lower() in ("vnd", "đồng"):
                    continue
                # Skip year-as-value / tiny unitless numbers
                if 2000 <= claimed <= 2099 and not unit:
                    continue
                if not unit and claimed < 20:
                    continue
                if unit == "%" and field in NO_PCT_UNIT:
                    continue
                scaled = _scale_to_tỷ(claimed, unit)
                # Only tokens explicitly marked as fiscal years count.  A bare
                # target price such as "2,024 VND" must not become year 2024.
                base = max(0, m.start()-80)
                ctx = text[base:m.end()+80]
                year_marks = list(re.finditer(r"(?:năm|FY)\s*(20\d\d)", ctx, re.I))
                if not year_marks:
                    continue  # claim không gắn năm cụ thể — không verify được
                ym = min(year_marks, key=lambda z: abs((base + z.start(1)) - m.start()))
                year = ym.group(1)
                if year not in gt:
                    continue
                truth = float(gt[year])
                if truth == 0:
                    continue
                checked += 1
                half_step = 0.5 if field == "eps_vnd" else 0.05
                if abs(scaled - truth) > max(abs(truth) * 0.05, half_step):
                    issues.append(f"{field}[{year}]: narrative nói {scaled:,.0f}, data = {truth:,.1f} (>5%)")
            break  # one keyword per field

    # 2. Chart years vs financials years
    # FIX-7 (review V4 Pro): `gt` chỉ gán trong for loop — nếu loop không chạy
    # (mọi field không phải dict) → UnboundLocalError. Khởi tạo trước.
    gt = {}
    for field, kws in metric_kws.items():
        cand = fin.get(field)
        if isinstance(cand, dict):
            gt = cand
            break
    data_arrays = _extract_data_js_arrays(html)
    chart_years = data_arrays.get("years", [])
    gt_years = sorted(gt.keys())
    if chart_years:
        norm_chart = [str(int(float(y))) if isinstance(y, (int, float)) else str(y) for y in chart_years]
        if norm_chart and sorted(norm_chart) != [str(y) for y in gt_years]:
            issues.append(f"chart years {norm_chart} ≠ data years {gt_years}")

    # No numeric prose claim is not itself a temporal error.  The structured
    # chart-year binding still provides a non-vacuous check for zero/N/A cases.
    chart_checked = bool(chart_years) and not any(str(i).startswith("chart years") for i in issues)
    passed = len(issues) == 0 and (checked > 0 or chart_checked)
    return passed, {
        "checked": checked,
        "chart_years": chart_years,
        "data_years": gt_years,
        "issues": issues[:5],
        "note": "narrative claim theo năm phải khớp data đúng năm; CAGR baseline phải là năm đầu data",
    }


def verify_segment_check(req, html):
    """REQ-035: Segment breakdown phải có nguồn (segments.json/company_profile.json).

    Nếu sec-segment có % contribution hoặc revenue per segment → cần data source.
    Không có data → phải có marker 'ước tính'.
    """
    if not html:
        return False, {"error": "no html"}
    seg_text = extract_section_text(html, "sec-segment")
    if not seg_text:
        return False, {"error": "sec-segment rỗng/không tồn tại — REQ-009 yêu cầu section canonical, không thể vacuous pass"}, {"note": "no sec-segment — nothing to check"}

    # Quantitative segment claims?
    has_numbers = bool(re.search(r"\d[\d.,]*\s*(?:%|tỷ|tỉ|triệu)", seg_text))
    if not has_numbers:
        return True, {"note": "sec-segment present but no quantitative breakdown"}

    # Source: segments.json / company_profile.json / financials.json segment keys
    segment_source = None
    for cand in ("segments.json", "data/segments.json", "company_profile.json"):
        d = _load_json_rel(cand)
        if d is not None:
            blob = json.dumps(d, ensure_ascii=False).lower()
            if any(k in blob for k in ("segment", "mảng", "cơ cấu", "contribution", "doanh thu theo")):
                segment_source = cand
                break
    # fallback: verified-dashboard-data.json may carry segments
    if not segment_source:
        d = _load_json_rel("verified-dashboard-data.json")
        if d and isinstance(d, dict) and any(k in json.dumps(d).lower() for k in ("segment", "contribution")):
            segment_source = "verified-dashboard-data.json"

    if not segment_source:
        # no data → numbers must be flagged as estimate
        has_estimate = bool(re.search(r"ước tính|giả định|estimate|theo công bố|khoảng", seg_text, re.I))
        if not has_estimate:
            return False, {
                "error": "segment numbers without segment data source AND without 'ước tính' marker",
                "segment_text": seg_text[:200],
                "hint": "phase1 phải tạo segments.json; nếu không có data → ghi 'ước tính'",
            }
        return True, {"note": "segment numbers flagged as estimate — acceptable"}

    return True, {"segment_source": segment_source, "note": "segment data source found"}


def verify_cagr_recompute(req, html):
    """REQ-036: CAGR claims phải recompute từ financials.json (±2%).

    Chống bịa CAGR: không chỉ keyword-check mà tính thật từ data.
    CAGR = (last/first)^(1/(n-1)) - 1. So với mọi claim 'CAGR X%'.
    """
    if not html:
        return False, {"error": "no html"}
    fin = _load_json_rel(req["verification"].get("data_file", "data/financials.json"))
    if not fin:
        return False, {"error": f"financials.json not found: {req['verification'].get('data_file')}"}

    text = _narrative_text(html)
    claims = _find_numeric_claims(text, ["CAGR", "tăng trưởng kép", "compound annual"], window=60)
    if not claims:
        # vacuous-pass guard: if "CAGR" mentioned without number → FAIL; absent → PASS note
        if re.search(r"(?:CAGR|tăng trưởng kép)[^\n.]{0,80}(?:N/A|không áp dụng|không tính)", text, re.I):
            return True, {"note": "CAGR explicitly N/A; no numeric claim"}
        if re.search(r"CAGR|tăng trưởng kép", text, re.I):
            return False, {"error": "CAGR mentioned without numeric claim — cannot verify"}
        return True, {"note": "no CAGR claim in narrative"}

    def _claim_metric(ctx):
        """Xác định claim CAGR nói về metric nào từ ngữ cảnh."""
        c = ctx.lower()
        if any(k in c for k in ("doanh thu", "revenue")):
            return "revenue_ty"
        if any(k in c for k in ("lợi nhuận", "lnst", "npat", "profit")):
            return "npatmi_ty"
        return None  # không rõ → so với mọi field

    issues = []
    checked = 0
    for field in req["verification"].get("fields", ["revenue_ty", "npatmi_ty"]):
        gt = fin.get(field)
        if not isinstance(gt, dict) or len(gt) < 2:
            continue
        years = sorted(int(y) for y in gt.keys())
        first, last = str(years[0]), str(years[-1])
        v0, v1 = float(gt[first]), float(gt[last])
        if v0 <= 0:
            continue
        n = len(years)
        cagr = (v1 / v0) ** (1 / (n - 1)) - 1
        cagr_pct = cagr * 100
        tolerance = req["verification"].get("tolerance_pct", 2)
        for c in claims:
            claim_metric = _claim_metric(c["context"])
            if claim_metric is not None and claim_metric != field:
                continue  # claim này thuộc metric khác — không so với field này
            claim_pct = c["value"]
            diff = abs(claim_pct - cagr_pct)
            # relative tolerance, floor 1.0pp cho CAGR nhỏ
            tol_pp = max(tolerance, abs(cagr_pct) * tolerance / 100)
            checked += 1
            if diff > tol_pp:
                issues.append(
                    f"CAGR claim {claim_pct:.1f}% ≠ recomputed {cagr_pct:.1f}% for {field} ({first}-{last}, lệch {diff:.1f}pp > {tol_pp:.1f}pp)"
                )

    passed = len(issues) == 0 and checked > 0
    return passed, {
        "cagr_claims_found": len(claims),
        "claims": [c["context"] for c in claims[:5]],
        "checked": checked,
        "issues": issues[:5],
        "recompute_basis": "financials.json first→last year",
    }


def verify_tech_recompute(req, html):
    """REQ-037: Tech Score + Verdict phải khớp technical_active.json (±2).

    Chống bịa tech score: report score phải bằng data file score. Verdict phải
    tương ứng dấu score (≥+3 BUY side, ≤-3 SELL side, giữa NEUTRAL).

    V3 HARDENING: nếu REQ-046 (technical_indicator_verify) đã chạy và tìm thấy
    discrepancy ở RSI/MA50 → escalate lên FAIL ở đây (cross-ref).
    """
    if not html:
        return False, {"error": "no html"}
    tech = _load_json_rel("technical_active.json")
    if not tech:
        vdd = _load_json_rel("verified-dashboard-data.json")
        tech = vdd.get("technical") if vdd and isinstance(vdd, dict) else None
    if not tech:
        return False, {"error": "technical_active.json / verified-dashboard-data.json.technical not found — thiếu nguồn"}

    data_score = tech.get("tech_score")
    data_verdict = (tech.get("verdict") or "").upper()
    scale_min = tech.get("scale_min", -6)
    scale_max = tech.get("scale_max", 6)
    if data_score is None:
        return False, {"error": "tech data file missing tech_score"}

    # Extract report tech score from sec-tech
    tech_text = extract_section_text(html, "sec-tech")
    m = re.search(r"([-+]?\d+)\s*/\s*" + re.escape(str(scale_max)), tech_text) if tech_text else None
    if not m:
        m = re.search(r"(?:tech score|điểm kỹ thuật|score)[^\d-]{0,20}([-+]?\d+)", tech_text or "", re.I)
    if not m:
        return False, {"error": "no tech score number found in sec-tech"}

    report_score = int(m.group(1))
    issues = []
    if abs(report_score - data_score) > 2:
        issues.append(f"report Tech Score {report_score}/{scale_max} ≠ data {data_score}/{scale_max} (lệch >2)")

    # Verdict sign consistency
    report_verdict_m = re.search(r"(STRONG SELL|SELL|NEUTRAL|BUY|STRONG BUY)", tech_text or "", re.I)
    report_verdict = report_verdict_m.group(1).upper() if report_verdict_m else ""
    def verdict_side(v):
        v = v.upper()
        if "SELL" in v:
            return "sell"
        if "BUY" in v:
            return "buy"
        return "neutral"
    if report_verdict:
        rv_side = verdict_side(report_verdict)
        dv_side = verdict_side(data_verdict)
        if rv_side != dv_side:
            issues.append(f"report verdict '{report_verdict}' ≠ data verdict '{data_verdict}'")
        # scale consistency: score ≥ +3 → BUY; ≤ -3 → SELL; else NEUTRAL acceptable
        if report_score >= 3 and rv_side == "sell":
            issues.append(f"score +{report_score} nhưng verdict '{report_verdict}' (SELL side) — mâu thuẫn")
        if report_score <= -3 and rv_side == "buy":
            issues.append(f"score {report_score} nhưng verdict '{report_verdict}' (BUY side) — mâu thuẫn")

    # V3 HARDENING: cross-ref with indicator-level verification
    # Quick RSI sanity from price data (if available)
    price_data = _load_json_rel("data/price_weekly.json") or _load_json_rel("data/price_daily.json")
    if price_data and isinstance(price_data, list):
        closes = [float(d.get("close") or d.get("price") or 0) for d in price_data if isinstance(d, dict)]
        closes = [c for c in closes if c > 0]
        if len(closes) >= 15:
            # Simple RSI(14) sanity
            deltas = [closes[i] - closes[i-1] for i in range(1, len(closes))]
            gains = [d if d > 0 else 0 for d in deltas[-14:]]
            losses = [-d if d < 0 else 0 for d in deltas[-14:]]
            avg_gain = sum(gains) / 14
            avg_loss = sum(losses) / 14 if sum(losses) > 0 else 0.001
            rs = avg_gain / avg_loss
            computed_rsi = 100.0 - 100.0 / (1.0 + rs)
            rsi_m = re.search(r"RSI[^\d(]{0,20}(\d+(?:[.,]\d+)?)", tech_text, re.I)
            if rsi_m:
                claimed_rsi = float(rsi_m.group(1).replace(",", "."))
                if abs(computed_rsi - claimed_rsi) > 10:
                    issues.append(f"RSI quick-check: computed {computed_rsi:.0f} ≠ claimed {claimed_rsi:.0f} (lệch >10 — V3 escalated)")

    passed = len(issues) == 0
    return passed, {
        "data_tech_score": data_score,
        "report_tech_score": report_score,
        "data_verdict": data_verdict,
        "report_verdict": report_verdict,
        "issues": issues,
        "hardening": "V3: added RSI quick sanity check escalated to FAIL",
    }


def verify_claim_basis(req, html):
    """REQ-038: Superlative/comparative claims phải có basis (số liệu/nguồn gần đó).

    Chống claim rỗng: 'dẫn đầu thị trường' không kèm số/nguồn → FAIL.
    """
    if not html:
        return False, {"error": "no html"}
    text = _narrative_text(html)

    superlatives = [
        r"dẫn đầu", r"lớn nhất", r"cao nhất", r"thấp nhất", r"nhanh nhất", r"tốt nhất",
        r"top\s*\d", r"số\s*1", r"duy nhất", r"vượt trội", r"đứng đầu", r"leading", r"dominant",
        r"chiếm\s*ưu thế", r"mạnh nhất",
    ]
    issues = []
    found = 0
    for pat in superlatives:
        for m in re.finditer(pat, text, re.I):
            found += 1
            ctx = text[max(0, m.start()-80):m.end()+200]
            has_basis = bool(re.search(r"\d[\d.,]*\s*(?:%|tỷ|tỉ|triệu|x)|ref-\d|BCTC|vnstock|data", ctx))
            if not has_basis:
                issues.append(f"claim '{m.group(0)}' không có số liệu/nguồn hỗ trợ trong ±200 chars: ...{ctx.strip()[:120]}...")

    # comparative claims vs peer: "cao hơn/thấp hơn X" needs a number
    for m in re.finditer(r"(?:cao|thấp|nhiều|ít)\s+hơn[^.%0-9]{0,40}?(\d[\d.,]*)\s*(?:%|x|tỷ|tỉ|triệu)", text, re.I):
        found += 1
        ctx = text[max(0, m.start()-80):m.end()+150]
        has_basis = bool(re.search(r"ref-\d|BCTC|vnstock|peers\.json|data|ước tính", ctx, re.I))
        if not has_basis:
            issues.append(f"so sánh '{m.group(1)}' không có nguồn gần đó: ...{ctx.strip()[:120]}...")

    passed = len(issues) == 0
    return passed, {
        "superlative_claims_found": found,
        "unbased_claims": issues[:5],
    }


def verify_industry_claim(req, html):
    """REQ-039: Claim về ngành (thị phần, quy mô thị trường, tăng trưởng ngành)
    phải cite nguồn. Chống bịa số ngành.
    """
    if not html:
        return False, {"error": "no html"}
    text = _narrative_text(html)

    industry_kws = [
        r"thị phần", r"quy mô thị trường", r"tăng trưởng ngành", r"toàn ngành",
        r"thị trường\s+(?:xây dựng|bán lẻ|ngân hàng|thép|bất động sản|sữa|vàng|dược)",
        # Batch-4: bỏ "chứng khoán" — "thị trường chứng khoán" thường chỉ sàn giao dịch
        # chung (nơi niêm yết), không phải claim quy mô ngành → FP trên sec-peer
        r"market share", r"industry growth", r"market size",
    ]
    source_kws = [
        r"báo cáo", r"công bố", r"ước tính", r"theo\s+", r"nghiên cứu", r"khảo sát",
        r"ref-\d", r"statista", r"fiinpro", r"world bank", r"imf", r"vietnam report",
        r"bộ xây dựng", r"gso", r"tổng cục thống kê", r"vneconomy", r"vir", r"cafef",
    ]
    issues = []
    found = 0
    for kw in industry_kws:
        for m in re.finditer(kw, text, re.I):
            ctx = text[max(0, m.start()-60):m.end()+200]
            has_number = bool(re.search(r"\d[\d.,]*\s*%?", ctx))
            if not has_number:
                continue  # mention without figure — not a claim
            found += 1
            if not re.search("|".join(source_kws), ctx, re.I):
                issues.append(f"industry claim '{m.group(0)}' không có nguồn: ...{ctx.strip()[:130]}...")

    passed = len(issues) == 0
    return passed, {
        "industry_claims_with_figures": found,
        "uncited_claims": issues[:5],
    }


SECTOR_ALIASES = {
    # canonical → tập alias tiếng Việt/viết tắt thường gặp (normalize trước khi so)
    "banking": ["ngân hàng", "ngan hang", "nganhang", "ngân hàng thương mại", "ngân hàng tmcp", "ngân hàng cổ phần"],
    "insurance": ["bảo hiểm", "bao hiem", "baohiem"],
    "securities": ["chứng khoán", "chung khoan", "chungkhoan"],
    "finance": ["tài chính", "tai chinh", "taichinh", "dịch vụ tài chính", "dich vu tai chinh"],
    "realestate": ["bất động sản", "bat dong san", "batdongsan", "bds", "bđs", "bất động sản và xây dựng"],
    "materials": ["vật liệu", "vat lieu", "vật liệu xây dựng", "vlxd", "nguyên vật liệu", "hóa chất", "hoa chat", "thép", "xi măng"],
    "energy": ["năng lượng", "nang luong", "dầu khí", "dau khi", "điện", "điện lực", "gas", "khí"],
    "consumer": ["hàng tiêu dùng", "hang tieu dung", "tiêu dùng", "tieu dung", "bán lẻ", "ban le", "thực phẩm", "thuc pham", "đồ uống", "do uong", "dược phẩm tiêu dùng"],
    "industrial": ["công nghiệp", "cong nghiep", "công nghiệp & sản xuất", "xây dựng", "xay dung", "sản xuất", "san xuat", "cơ khí", "co khi", "vận tải", "van tai", "logistics", "hạ tầng", "ha tang"],
    "tech": ["công nghệ", "cong nghe", "cntt", "công nghệ thông tin", "phần mềm", "phan mem"],
    "pharma": ["dược phẩm", "duoc pham", "dược", "duoc"],
    "agriculture": ["nông nghiệp", "nong nghiep", "thủy sản", "thuy san", "nông sản", "nong san"],
    "utilities": ["tiện ích", "tien ich", "điện nước", "dịch vụ tiện ích"],
    "telecom": ["viễn thông", "vien thong"],
    "general": ["đa ngành", "da nganh", "khác", "khac"],
}

# P0-2 (Sol lần 2, 2026-08-10): pin hash nguồn preflight — preflight_p0_sectors.json
# là nguồn sector chuẩn (ICB+sàn). Verifier xác thực sidecar bằng cách TỰ đọc nguồn:
# rehash nguồn == sidecar.source_sha256 == PINNED_PREFLIGHT_SHA. Khi preflight được
# tái tạo chính thức (không phải sửa tay), cập nhật hằng số này cùng freeze mới.
PINNED_PREFLIGHT_SHA = "79355ec56aa58691942630deab513c27e1a2005738d3ce79fa9b5b5a5a50f5b0"

PREFLIGHT_SOURCE_PATHS = [
    os.environ.get("VNALL_PREFLIGHT_SECTORS", ""),
    os.path.join(SKILL_DIR, "config", "preflight_p0_sectors.json"),
    os.path.join(os.getcwd(), "data/vnall/preflight_p0_sectors.json"),
]

def _load_preflight_source():
    """Đọc nguồn preflight thật (dict {ticker: sector}) — None nếu không có."""
    for p in PREFLIGHT_SOURCE_PATHS:
        if p and os.path.exists(p):
            try:
                with open(p) as f:
                    return json.load(f), p
            except Exception:
                return None, None
    return None, None


def normalize_sector(raw):
    """Chuẩn hóa sector về canonical (lowercase, trim, map alias tiếng Việt)."""
    if not raw:
        return None
    s = str(raw).strip().lower()
    for canon, aliases in SECTOR_ALIASES.items():
        for a in aliases:
            if a in s:
                return canon
    for canon in SECTOR_ALIASES:
        if canon in s:
            return canon
    return s


def verify_identity(req, html):
    """REQ-040: Ticker + company name khớp target; không nhầm ticker khác.

    Ticker lạ trong narrative (ngoài sec-peer/sec-source) → FAIL.
    """
    if not html:
        return False, {"error": "no html"}
    profile = _load_json_rel("company_profile.json")
    company_name = None
    if profile and isinstance(profile, dict):
        company_name = profile.get("company_name") or profile.get("organ_name")

    issues = []
    text = extract_all_text(html)

    # 1. Target ticker present
    if TICKER != "UNKNOWN" and not re.search(rf"\b{TICKER}\b", text):
        issues.append(f"report không nhắc ticker {TICKER}")

    # 2. Company name present (fuzzy: first word of name)
    if company_name:
        name_words = [w for w in company_name.replace("JSC", "").replace("Corp", "").split() if len(w) > 3]
        if name_words and not any(w.lower() in text.lower() for w in name_words[:2]):
            issues.append(f"report không nhắc company name '{company_name}'")

    # 3. Foreign tickers outside allowed sections
    allowed_sections = {"sec-peer", "sec-source", "sec-glossary", "sec-analyst"}
    foreign = []
    for ticker in _KNOWN_TICKERS:
        if ticker == TICKER:
            continue
        for m in re.finditer(rf"\b{ticker}\b", html):
            # which section contains this occurrence?
            before = html[:m.start()]
            sec_open = list(re.finditer(r'<section[^>]*id="(sec-[a-z0-9-]+)"', before))
            sec = sec_open[-1].group(1) if sec_open else "pre-section"
            if sec not in allowed_sections:
                foreign.append((ticker, sec))
                break  # one hit per ticker is enough
    if foreign:
        issues.append(f"ticker khác xuất hiện ngoài peer/source: {foreign[:5]}")

    # P0-04 (Sol 2026-08-09): SECTOR BINDING — sector phải nhất quán giữa
    # verified-dashboard-data.json ↔ task-state ↔ narrative HTML. Mutation contract
    # sector (finance→banking) phải bị bắt: narrative/task-state vẫn giữ sector cũ.
    vdd = _load_json_rel("verified-dashboard-data.json")
    ts = _load_json_rel(".task-state/task-state.json")
    d_sec = (vdd or {}).get("sector")
    ts_sec = None
    if isinstance(ts, dict):
        ts_sec = (((ts.get("phases") or {}).get("phase2_fundamental") or {}).get("result") or {}).get("sector")
    nar_sec = None
    m_sec = re.search(r"trong ngành ([^,.<]+)", text, re.I)
    if m_sec:
        nar_sec = m_sec.group(1).strip()
    # P0-04 (Sol): cũng đối chiếu sector trong DATA JS nhúng (mutation HTML JS phải bị bắt)
    js_sec = None
    mjs = re.search(r'["\']?sector["\']?\s*:\s*"([^"]+)"', html)
    if mjs:
        js_sec = mjs.group(1)
    sec_sources = [x for x in (d_sec, ts_sec, nar_sec, js_sec) if x]
    # Sol §7.4 (2026-08-10): normalize trước khi so — "ngân hàng thương mại cổ phần"
    # (narrative tiếng Việt) phải khớp "banking" (canonical), không tạo false positive.
    if len({normalize_sector(x) for x in sec_sources if x}) > 1:
        issues.append(f"sector binding lệch: DATA={d_sec} | task-state={ts_sec} | narrative={nar_sec} | JS={js_sec}")

    # P0-04 v2 (Sol 2026-08-10): BIND VỚI NGUỒN CHUẨN — preflight-sector.json có
    # canonical sector + provenance (source/hash/thời điểm). Sector sai nhưng đồng
    # nhất ở 4 output (vd build TJC với 'tech') phải bị bắt khi canonical != output.
    pf = _load_json_rel("preflight-sector.json")
    canonical = None
    runner_input = None
    pf_src = None
    pf_errors = []
    if not isinstance(pf, dict):
        pf_errors.append("thiếu preflight-sector.json — không bind được sector với nguồn chuẩn")
    else:
        runner_input = pf.get("runner_input_sector")
        pf_src = pf.get("source")
        if pf_src != "preflight_p0_sectors":
            pf_errors.append(
                f"preflight-sidecar source={pf_src!r} không hợp lệ "
                "(cần 'preflight_p0_sectors')"
            )
        else:
            # P0-2 (Sol lần 2): xác thực sidecar với NGUỒN — không tin canonical trong sidecar
            pf_ticker = pf.get("ticker")
            if pf_ticker != TICKER:
                pf_errors.append(f"preflight-sidecar ticker={pf_ticker} ≠ {TICKER}")
            src_map, src_path = _load_preflight_source()
            if src_map is None:
                pf_errors.append("không đọc được preflight_p0_sectors.json nguồn — không xác thực được sector")
            else:
                # rehash nguồn so với source_sha256 trong sidecar
                try:
                    import hashlib as _hl
                    actual_sha = _hl.sha256(open(src_path, 'rb').read()).hexdigest()
                except Exception:
                    actual_sha = None
                sidecar_sha = pf.get("source_sha256")
                if not sidecar_sha:
                    pf_errors.append("preflight-sidecar thiếu source_sha256")
                elif actual_sha and sidecar_sha != actual_sha:
                    pf_errors.append(f"preflight source_sha256 sidecar={pf.get('source_sha256')[:12]}… ≠ rehash thật={actual_sha[:12]}… (nguồn bị sửa?)")
                if actual_sha and actual_sha != PINNED_PREFLIGHT_SHA:
                    pf_errors.append(f"preflight nguồn hash {actual_sha[:12]}… ≠ PINNED {PINNED_PREFLIGHT_SHA[:12]}… (cần cập nhật pin chính thức)")
                declared_path = pf.get("source_path")
                if not declared_path:
                    pf_errors.append("preflight-sidecar thiếu source_path")
                elif os.path.realpath(os.path.expanduser(str(declared_path))) != os.path.realpath(src_path):
                    pf_errors.append(
                        f"preflight source_path sidecar={declared_path} ≠ nguồn verifier={src_path}"
                    )
                # canonical = mapping từ NGUỒN (không tin sidecar)
                if TICKER in src_map:
                    canonical = normalize_sector(src_map[TICKER])
                    sidecar_canonical = normalize_sector(pf.get("canonical_sector"))
                    if sidecar_canonical != canonical:
                        pf_errors.append(
                            f"preflight-sidecar canonical={sidecar_canonical} ≠ nguồn={canonical}"
                        )
                else:
                    pf_errors.append(f"ticker {TICKER} không có trong preflight nguồn")
    output_map = {"DATA": d_sec, "task-state": ts_sec, "narrative": nar_sec, "JS": js_sec}
    missing_outputs = [name for name, value in output_map.items() if not value]
    if missing_outputs:
        issues.append(f"thiếu sector ở output bắt buộc: {missing_outputs}")
    if not runner_input:
        issues.append("preflight-sidecar thiếu runner_input_sector")
    if canonical and not pf_errors:
        outputs_norm = {normalize_sector(x) for x in output_map.values() if x}
        if outputs_norm and canonical not in outputs_norm:
            issues.append(
                f"sector KHÔNG khớp nguồn chuẩn (preflight): canonical={canonical} "
                f"| DATA={normalize_sector(d_sec)} task-state={normalize_sector(ts_sec)} "
                f"narrative={normalize_sector(nar_sec)} JS={normalize_sector(js_sec)}"
            )
        if runner_input and normalize_sector(runner_input) != canonical:
            issues.append(
                f"runner_input_sector={normalize_sector(runner_input)} ≠ canonical preflight={canonical}"
            )
    elif pf_errors:
        issues.append("preflight sidecar không hợp lệ: " + "; ".join(pf_errors))

    passed = len(issues) == 0
    return passed, {
        "ticker": TICKER,
        "company_name": company_name,
        "foreign_tickers": foreign[:5],
        "sector_binding": {"data": d_sec, "task_state": ts_sec, "narrative": nar_sec, "js": js_sec,
                           "canonical_preflight": canonical, "runner_input_sector": runner_input,
                           "preflight_source": pf_src, "preflight_errors": pf_errors},
        "issues": issues,
    }


def _csv_period_rows(path):
    """Đếm số dòng dữ liệu (kỳ) trong CSV sponsor — bỏ header và dòng rỗng."""
    import csv as _csv
    if not os.path.exists(path):
        return None
    n = 0
    with open(path) as f:
        for row in _csv.reader(f):
            if row and any(str(c).strip() for c in row):
                n += 1
    return max(n - 1, 0)


def verify_task_state_oracle(req, html):
    """REQ-075 (Sol 2026-08-10): Task-state metadata phải khớp dữ liệu gốc.

    Recompute số kỳ từ 3 sponsor CSV trong source-pack; xác thực tier/sponsor_ok
    theo policy (golden = ≥42 kỳ, sponsor_ok = ≥42 kỳ). Mutation
    periods/tier/sponsor_ok trong task-state → critical FAIL (exit 1).
    """
    work = _work_dir()
    ts = _load_json_rel(".task-state/task-state.json")
    if not isinstance(ts, dict):
        return False, {"error": "task-state.json không tồn tại"}
    phase0 = (((ts.get("phases") or {}).get("phase0_sponsor") or {}).get("result") or {})
    phase1 = (((ts.get("phases") or {}).get("phase1_data") or {}).get("result") or {})
    ts_periods = phase0.get("periods")
    ts_tier = phase0.get("tier")
    ts_sponsor_ok = phase0.get("sponsor_ok")
    rows = {
        "income_statement": _csv_period_rows(os.path.join(work, "source-pack", "income_statement_sponsor.csv")),
        "balance_sheet": _csv_period_rows(os.path.join(work, "source-pack", "balance_sheet_sponsor.csv")),
        "cash_flow": _csv_period_rows(os.path.join(work, "source-pack", "cash_flow_sponsor.csv")),
    }
    issues = []
    if type(ts_periods) is not int:
        issues.append(f"phase0.periods phải là integer thật, nhận {ts_periods!r}")
    if not isinstance(ts_tier, str) or not ts_tier:
        issues.append(f"phase0.tier thiếu/không hợp lệ: {ts_tier!r}")
    if type(ts_sponsor_ok) is not bool:
        issues.append(f"phase0.sponsor_ok phải là boolean thật, nhận {ts_sponsor_ok!r}")
    # Sol lần 2 (P0-1): FAIL khi BẤT KỲ sponsor CSV nào thiếu — không được "PASS rỗng"
    missing = [k for k, v in rows.items() if v is None]
    if missing:
        return False, {
            "task_state": {"periods": ts_periods, "tier": ts_tier, "sponsor_ok": ts_sponsor_ok},
            "recomputed": {"income_rows": rows["income_statement"], "balance_rows": rows["balance_sheet"],
                           "cashflow_rows": rows["cash_flow"], "expected_periods": None,
                           "missing_csvs": missing, "policy_tier": None, "policy_sponsor_ok": None},
            "issues": [f"thiếu sponsor CSV: {missing} — không recompute được số kỳ"],
        }
    # Policy sponsor qualification: MINIMUM của 3 báo cáo (fail-closed — một báo cáo
    # thiếu kỳ ⇒ không thể gọi đủ kỳ). Golden = min ≥ 42.
    exp = min(rows.values())
    # phase0 và phase1 phải nhất quán (mutation sửa 1 trong 2 → bị bắt)
    ts_ph1_periods = phase1.get("periods")
    if type(ts_ph1_periods) is not int:
        issues.append(f"phase1.periods phải tồn tại và là integer thật, nhận {ts_ph1_periods!r}")
    elif ts_ph1_periods != ts_periods:
        issues.append(f"phase0.periods={ts_periods} ≠ phase1.periods={ts_ph1_periods} — task-state nội bộ lệch")
    if ts_periods != exp:
        issues.append(f"periods task-state={ts_periods} ≠ recomputed={exp} (income/balance/cashflow={rows['income_statement']}/{rows['balance_sheet']}/{rows['cash_flow']})")
    policy_tier = "golden" if exp >= 42 else "silver"
    if ts_tier != policy_tier:
        issues.append(f"tier task-state={ts_tier} ≠ policy={policy_tier} (min-periods={exp})")
    policy_ok = exp >= 42
    if type(ts_sponsor_ok) is bool and ts_sponsor_ok != policy_ok:
        issues.append(f"sponsor_ok task-state={ts_sponsor_ok} ≠ policy={policy_ok} (min-periods={exp})")
    return len(issues) == 0, {
        "task_state": {"periods": ts_periods, "tier": ts_tier, "sponsor_ok": ts_sponsor_ok,
                       "phase1_periods": ts_ph1_periods},
        "recomputed": {"income_rows": rows["income_statement"], "balance_rows": rows["balance_sheet"],
                       "cashflow_rows": rows["cash_flow"], "expected_periods": exp,
                       "policy_min_of_3": True, "policy_tier": policy_tier, "policy_sponsor_ok": policy_ok},
        "issues": issues,
    }


def verify_sponsor_period_check(req, html):
    """REQ-002: đếm contract source-pack, không phụ thuộc orientation API live."""
    work = _work_dir()
    rows = {
        "income_statement": _csv_period_rows(os.path.join(work, "source-pack", "income_statement_sponsor.csv")),
        "balance_sheet": _csv_period_rows(os.path.join(work, "source-pack", "balance_sheet_sponsor.csv")),
        "cash_flow": _csv_period_rows(os.path.join(work, "source-pack", "cash_flow_sponsor.csv")),
    }
    missing = [name for name, count in rows.items() if count is None]
    minimum = min((count for count in rows.values() if count is not None), default=None)
    threshold = int(req.get("verification", {}).get("expect_min", 20))
    issues = []
    if missing:
        issues.append(f"thiếu sponsor CSV: {missing}")
    if minimum is None or minimum < threshold:
        issues.append(f"min periods={minimum}, yêu cầu >= {threshold}")
    return not issues, {"rows": rows, "minimum": minimum, "expect_min": threshold, "issues": issues}


def verify_sponsor_import_check(req, html):
    """REQ-001: import trong chính interpreter đang chạy verifier.

    Không spawn ``python3`` theo PATH vì builder có thể được gọi bằng đường dẫn
    tuyệt đối tới virtualenv trong HOME sạch.
    """
    try:
        import vnstock_data
        from vnstock_data import Fundamental
        version = getattr(vnstock_data, "__version__", None)
        return True, {
            "python": sys.executable,
            "vnstock_data_version": version,
            "fundamental_api": bool(Fundamental),
        }
    except (ImportError, ModuleNotFoundError) as exc:
        return False, {
            "python": sys.executable,
            "error": str(exc),
            "fix": "Cài/đăng nhập vnstock Sponsor theo README.md trong cùng virtualenv",
        }


def verify_news_window(req, html):
    """REQ-041: News phải trong 30 ngày (news_digest.json hoặc date trong HTML).

    Article cũ >30 ngày hoặc thiếu date (khi không phải source standard) → FAIL.

    V3 HARDENING: sample URL check — pick 1-2 articles có URL, HEAD request.
    Nếu URL chết → WARN (không FAIL vì network issue).
    """
    if not html:
        return False, {"error": "no html"}
    nd = _load_json_rel("news_digest.json")
    today = datetime.date.today()

    # Kết quả fetch hiện tại nhưng không có bài là một kết quả hợp lệ,
    # không phải "tin cũ". Chỉ PASS khi artifact ghi rõ ok_empty và fetched_at
    # còn tươi; lỗi API/thiếu provenance vẫn fail-closed.
    if nd and isinstance(nd, dict) and not nd.get("articles"):
        status = nd.get("fetch_status")
        fetched_at = str(nd.get("fetched_at") or "")[:10]
        try:
            fetched_date = datetime.date.fromisoformat(fetched_at)
            fetch_age = (today - fetched_date).days
        except Exception:
            fetched_date, fetch_age = None, None
        if status == "ok_empty" and fetch_age is not None and 0 <= fetch_age <= 30:
            return True, {"articles_checked": 0, "fetch_status": status,
                          "fetched_at": fetched_at, "fetch_age_days": fetch_age,
                          "note": "API fetch tươi, không có bài trong window 30 ngày"}
        return False, {"articles_checked": 0, "fetch_status": status,
                       "fetched_at": fetched_at or None, "fetch_age_days": fetch_age,
                       "error": "news fetch không thành công hoặc thiếu provenance tươi"}

    # Try digest articles
    if nd and isinstance(nd, dict) and nd.get("articles"):
        articles = nd["articles"]
        issues = []
        checked = 0
        for a in articles:
            ds = a.get("date") or a.get("published_at") or a.get("time") or ""
            if not ds:
                issues.append(f"article thiếu date: {(a.get('title') or '')[:60]}")
                continue
            m = re.search(r"(\d{4})-(\d{2})-(\d{2})", str(ds)) or re.search(r"(\d{2})/(\d{2})/(\d{4})", str(ds))
            if not m:
                issues.append(f"article date không parse được: {ds}")
                continue
            if m.group(1) and len(m.group(1)) == 4:  # YYYY-MM-DD
                d = datetime.date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
            else:  # DD/MM/YYYY
                d = datetime.date(int(m.group(3)), int(m.group(2)), int(m.group(1)))
            checked += 1
            age = (today - d).days
            if age > 30:
                issues.append(f"article {d.isoformat()} cũ {age} ngày (>30): {(a.get('title') or '')[:50]}")

        # V3 HARDENING: sample URL check (1-2 articles)
        url_warnings = []
        for a in articles[:2]:
            url = a.get("url") or a.get("link") or ""
            if url:
                try:
                    import urllib.request as _urllib
                    req_h = _urllib.Request(url, method="HEAD")
                    req_h.add_header("User-Agent", "ZCode-Verifier/1.0")
                    resp = _urllib.urlopen(req_h, timeout=5)
                    if resp.status >= 400:
                        url_warnings.append(f"URL {resp.status}: {url[:80]}")
                except Exception:
                    url_warnings.append(f"URL unreachable: {url[:80]}")

        passed = len(issues) == 0
        return passed, {
            "articles_checked": checked,
            "issues": issues[:5],
            "url_warnings": url_warnings,
            "hardening": "V3: sample URL HEAD check on first 2 articles (WARN only)",
        }

    # Fallback: dates in HTML (e.g. "31/07/2026")
    text = re.sub(r'<[^>]+>', ' ', html)
    dates = re.findall(r"\b(\d{2})/(\d{2})/(\d{4})\b|\b(\d{4})-(\d{2})-(\d{2})\b", text)
    parsed = []
    for d1, m1, y1, y2, m2, d2 in dates:
        if y1:
            parsed.append(datetime.date(int(y1), int(m1), int(d1)))
        else:
            parsed.append(datetime.date(int(y2), int(m2), int(d2)))
    if not parsed:
        return False, {"error": "no news_digest.json articles AND no dates in HTML — không verify được news window"}

    latest = max(parsed)
    oldest_ok = today - datetime.timedelta(days=30)
    stale = [p.isoformat() for p in parsed if p < oldest_ok]
    passed = len(stale) == 0
    return passed, {
        "dates_found": [p.isoformat() for p in sorted(set(parsed))],
        "stale_dates": stale,
        "note": "news_digest.json rỗng — fallback check date trong HTML",
    }


def verify_investment_amount(req, html):
    """REQ-042: investment_amount từ task-state phải xuất hiện trong narrative.

    task-state không có amount → PASS note. Có amount → narrative phải nhắc ±10%.
    """
    if not html:
        return False, {"error": "no html"}
    ts = _load_json_rel(".task-state/task-state.json")
    amount = None
    if ts and isinstance(ts, dict):
        amount = ts.get("investment_amount")
        if amount is None:
            # nested? some runs store under state
            for k, v in ts.items():
                if isinstance(v, dict) and "investment_amount" in v:
                    amount = v["investment_amount"]
                    break
    if amount is None:
        return True, {"note": "task-state không có investment_amount — không có gì để check"}

    text = extract_all_text(html)
    # normalize amount to number: 100000000, 100tr, 100 triệu, 1 tỷ
    target = float(amount)
    found = False
    # numeric form with commas
    if re.search(rf"{int(target):,}".replace(",", "[.,]"), text):
        found = True
    # "100 triệu" / "100tr" / "1 tỷ" forms
    for m in re.finditer(r"(\d[\d.,]*)\s*(triệu|tr|tỷ|tỉ)\b", text, re.I):
        v = _scale_to_tỷ(_normalize_number(m.group(1)), m.group(2))
        if v and abs(v * 1e9 - target) / target <= 0.10:
            found = True
            break

    if not found:
        return False, {
            "error": f"investment_amount={amount:,} không xuất hiện trong narrative (sec-scenario/insight)",
            "hint": "phase0 thu amount từ user; phase6 phải dùng đúng amount trong kịch bản",
        }
    return True, {"investment_amount": amount, "found_in_narrative": True}


def verify_source_freshness(req, html):
    """REQ-043: References phải có date/năm (standard sources được miễn).

    Ref rỗng date và không phải standard → FAIL. Ref năm < report năm - 2 → FAIL.
    """
    if not html:
        return False, {"error": "no html"}
    text = extract_all_text(html)
    if "ref-" not in text:
        return True, {"note": "no refs found (REQ-018 sẽ check số lượng)"}

    standard_kws = ["standard", "bctc", "filings", "disclosure", "báo cáo tài chính", "công bố"]
    # collect ref blocks: id="ref-N" ... up to next ref or 200 chars
    refs = []
    for m in re.finditer(r'id="ref-\d+"[^>]*>(.{0,220}?)', html, re.DOTALL):
        block = re.sub(r'<[^>]+>', ' ', m.group(1))
        block = re.sub(r'\s+', ' ', block).strip()
        refs.append(block)

    issues = []
    checked = 0
    report_year = datetime.date.today().year
    for b in refs:
        if not b:
            continue
        checked += 1
        has_year = bool(re.search(r"20\d\d", b))
        is_standard = any(kw in b.lower() for kw in standard_kws)
        if not has_year and not is_standard:
            issues.append(f"ref không date và không phải standard: '{b[:80]}'")
        elif has_year:
            ym = re.search(r"(20\d\d)", b)
            yr = int(ym.group(1))
            if yr < report_year - 2 and not is_standard:
                issues.append(f"ref năm {yr} stale (>2 năm so với {report_year}): '{b[:80]}'")

    passed = len(issues) == 0
    return passed, {
        "refs_checked": checked,
        "refs_total": len(refs),
        "issues": issues[:5],
        "note": "standard sources (BCTC, filings, disclosure) được miễn date",
    }


# ═══════════════════════════════════════════════════════════════
# V3 HARDENING CHECKS (REQ-044..058, 062) — Wave 1-4 regressions
# ═══════════════════════════════════════════════════════════════

def verify_news_authenticity(req, html):
    """REQ-044: News authenticity — article phải có URL/source_name xác định được.

    G2 (review V4 Flash): trước đây chỉ đếm sự hiện diện URL → tin giả
    (example.com, .xyz không tồn tại) vẫn PASS dù REQ-044 là critical.
    Fix: whitelist báo chí VN + HEAD check. Domain lạ + không truy cập được → FAIL.
    Domain whitelist không cần mạng (không HEAD) → an toàn khi offline.
    """
    if not html:
        return False, {"error": "no html"}
    nd = _load_json_rel("news_digest.json")
    if not nd or not isinstance(nd, dict):
        return True, {"note": "no news_digest.json — REQ-041 checks date window separately"}

    articles = nd.get("articles", [])
    if not articles:
        return True, {"note": "news_digest.json has no articles — nothing to check"}

    # Báo chí + sàn giao dịch + nguồn tài chính hợp lệ (domain không cần HEAD check)
    WHITELIST_DOMAINS = (
        "cafef.vn", "vnexpress.net", "vietstock.vn", "ndh.vn", "vietnamfinance.vn",
        "baodautu.vn", "stockbiz.vn", "tinnhanhchungkhoan.vn", "vietnamnet.vn",
        "tuoitre.vn", "thanhnien.vn", "vtv.vn", "voh.com.vn", "zingnews.vn",
        "cafebiz.vn", "vietnambiz.vn", "dantri.com.vn", "tienphong.vn", "plo.vn",
        "kinhtedothi.vn", "doanhnghiepvn.vn", "vietq.vn", "vneconomy.vn", "vietnamplus.vn",
        "hsx.vn", "hnx.vn", "upcom.vn", "vnstock.vn", "ssi.com.vn", "vndirect.com.vn",
        "tcbs.com.vn", "bvsc.com.vn", "vcbs.com.vn", "fpts.com.vn", "msi.com.vn",
        "sbsi.vn", "wsi.com.vn", "dragoncapital.com.vn", "reuters.com", "bloomberg.com",
        "investing.com", "financialtimes.com",
    )
    FAKE_HINTS = ("example.com", "example.org", "test", "lorem", "localhost", ".xyz", ".top", ".info", "12345")

    import urllib.request as _urllib
    from urllib.parse import urlparse
    total = len(articles)
    has_url = 0
    has_source_name = 0
    url_accessible = 0
    fake_unreachable = []  # URL domain lạ + không truy cập được → tin giả
    issues = []

    for a in articles:
        url = a.get("url") or a.get("link") or ""
        src = a.get("source_name") or a.get("source") or ""
        title = (a.get("title") or "")[:60]

        if url:
            has_url += 1
            domain = ""
            try:
                domain = (urlparse(url).netloc or "").lower()
            except Exception:
                pass
            is_fake_hint = any(h in url.lower() for h in FAKE_HINTS)
            is_whitelisted = any(domain == w or domain.endswith("." + w) for w in WHITELIST_DOMAINS)
            if is_whitelisted:
                url_accessible += 1  # nguồn tin cậy — không cần HEAD
            elif not is_fake_hint and domain:
                # domain lạ nhưng có thể là site thật → HEAD chứng minh
                try:
                    req_h = _urllib.Request(url, method="HEAD")
                    req_h.add_header("User-Agent", "ZCode-Verifier/1.0")
                    resp = _urllib.urlopen(req_h, timeout=5)
                    if resp.status < 400:
                        url_accessible += 1
                    else:
                        fake_unreachable.append(f"{domain} (HTTP {resp.status})")
                        issues.append(f"URL {resp.status}: {url[:80]} — {title}")
                except Exception as e:
                    fake_unreachable.append(domain or "no-domain")
                    issues.append(f"URL unreachable ({str(e)[:40]}): {url[:80]} — {title}")
            else:
                # domain rỗng hoặc chứa fake hint (example.com/.xyz/...) → tin giả mặc định
                fake_unreachable.append(domain or "no-domain")
                issues.append(f"URL nghi tin giả (domain '{domain or '?'}'): {url[:80]} — {title}")
        elif src:
            has_source_name += 1
            if any(h in src.lower() for h in FAKE_HINTS):
                fake_unreachable.append(f"source '{src[:30]}'")
                issues.append(f"source_name nghi tin giả: {src[:60]} — {title}")
        else:
            issues.append(f"article không URL và không source_name: {title}")

    # G2: ≥50% có URL/source_name VÀ không có tin giả (domain lạ unreachable)
    coverage = (has_url + has_source_name) / max(total, 1)
    passed = coverage >= 0.5 and len(fake_unreachable) == 0
    return passed, {
        "total_articles": total,
        "has_url": has_url,
        "url_accessible": url_accessible,
        "has_source_name": has_source_name,
        "coverage_pct": round(coverage * 100, 1),
        "threshold": "≥50% + 0 fake/unreachable",
        "fake_unreachable": fake_unreachable[:5],
        "issues": issues[:5],
    }


def verify_forecast_source(req, html):
    """REQ-045: Forecast source — forward-looking claims phải cite nguồn.

    Tìm forward-looking phrases + số → cần cite hoặc DCF assumption table.
    """
    if not html:
        return False, {"error": "no html"}
    text = _narrative_text(html)

    forecast_phrases = [
        r"dự kiến", r"kế hoạch", r"dự phóng", r"mục tiêu", r"triển vọng",
        r"ước đạt", r"forecast", r"target", r"outlook", r"guidance",
        r"dự báo", r"kỳ vọng", r"ước tính.*năm\s+20\d\d",
    ]
    cite_keywords = [
        r"ref-\d", r"BCTC", r"ĐHCĐ", r"nghị quyết", r"kế hoạch kinh doanh",
        r"KHKD", r"guidance", r"công ty chứng khoán", r"VCSC", r"SSI", r"HSC",
        r"VNDirect", r"MAS", r"BVSC", r"FPTS", r"VCI", r"công bố", r"theo",
        r"sponsor", r"vnstock", r"DCF", r"định giá", r"assumption",
    ]

    issues = []
    found_total = 0
    for phrase in forecast_phrases:
        for m in re.finditer(phrase, text, re.I):
            # Check if there's a number nearby (within 150 chars)
            nearby = text[m.start():min(len(text), m.end() + 150)]
            has_number = bool(re.search(r"\d[\d.,]*\s*(%|tỷ|tỉ|triệu|nghìn)", nearby))
            if not has_number:
                continue
            found_total += 1
            ctx = text[max(0, m.start() - 200):m.end() + 200]
            has_cite = any(re.search(kw, ctx, re.I) for kw in cite_keywords)
            if not has_cite:
                issues.append(
                    f"forecast '{m.group(0)}' có số nhưng không cite nguồn: ...{ctx.strip()[:120]}..."
                )

    tolerated = req["verification"].get("rules", [""])[2]
    max_uncited = 2
    passed = len(issues) <= max_uncited
    return passed, {
        "forecast_claims_with_numbers": found_total,
        "uncited": len(issues),
        "max_tolerated": max_uncited,
        "issues": issues[:5],
    }


def verify_technical_indicator(req, html):
    """REQ-046: Technical indicator verify — RSI/MA50/MACD phải tính được từ price data.

    Load price_daily.json → tính RSI(14), MA50, MACD → compare với dashboard claims.
    """
    if not html:
        return False, {"error": "no html"}

    # Load price data
    price_data = _load_json_rel("data/price_daily.json") or _load_json_rel("data/price_weekly.json")
    tech = _load_json_rel("technical_active.json")
    vdd = _load_json_rel("verified-dashboard-data.json")
    if vdd and isinstance(vdd, dict):
        tech = tech or vdd.get("technical")

    # Extract closing prices
    closes = []
    if price_data and isinstance(price_data, list):
        closes = [d.get("close") or d.get("price") or 0 for d in price_data if isinstance(d, dict)]
        closes = [float(c) for c in closes if c]
    elif tech and isinstance(tech, dict):
        closes_raw = tech.get("closes") or tech.get("prices") or []
        closes = [float(c) for c in closes_raw if c]

    if len(closes) < 50:
        return True, {"note": f"insufficient price data ({len(closes)} points) — cannot verify indicators"}

    issues = []

    # RSI(14) compute
    def compute_rsi(prices, period=14):
        if len(prices) < period + 1:
            return None
        deltas = [prices[i] - prices[i - 1] for i in range(1, len(prices))]
        gains = [d if d > 0 else 0 for d in deltas[-period:]]
        losses = [-d if d < 0 else 0 for d in deltas[-period:]]
        avg_gain = sum(gains) / period
        avg_loss = sum(losses) / period
        if avg_loss == 0:
            return 100.0
        rs = avg_gain / avg_loss
        return 100.0 - 100.0 / (1.0 + rs)

    computed_rsi = compute_rsi(closes)
    if computed_rsi is not None:
        # Extract RSI from dashboard
        tech_text = extract_section_text(html, "sec-tech") or ""
        rsi_m = re.search(r"RSI[^\d(]{0,30}(\d+(?:[.,]\d+)?)", tech_text, re.I)
        if rsi_m:
            claimed_rsi = float(rsi_m.group(1).replace(",", "."))
            if abs(computed_rsi - claimed_rsi) > 5:
                issues.append(f"RSI: computed {computed_rsi:.1f} ≠ claimed {claimed_rsi:.1f} (lệch >5)")

    # MA50 compute
    if len(closes) >= 50:
        ma50 = sum(closes[-50:]) / 50
        tech_text = extract_section_text(html, "sec-tech") or ""
        ma_m = re.search(r"MA\s*50[^\d]{0,30}(\d[\d.,]*)", tech_text, re.I)
        if ma_m:
            claimed_ma = _normalize_number(ma_m.group(1))
            if claimed_ma and abs(ma50 - claimed_ma) / max(ma50, 0.001) > 0.10:
                issues.append(f"MA50: computed {ma50:,.0f} ≠ claimed {claimed_ma:,.0f} (lệch >10%)")

    # MACD histogram sign
    if len(closes) >= 26:
        ema12 = closes[-1]
        ema26 = closes[-1]
        alpha12 = 2.0 / 13
        alpha26 = 2.0 / 27
        for i in range(len(closes) - 26, len(closes)):
            ema12 = closes[i] * alpha12 + ema12 * (1 - alpha12)
            ema26 = closes[i] * alpha26 + ema26 * (1 - alpha26)
        macd_line = ema12 - ema26
        # Signal: 9-period EMA of MACD
        signal = macd_line  # simplified — just check histogram sign
        histogram = macd_line - signal
        macd_sign = "positive" if histogram > 0 else "negative"

        # Check dashboard MACD description
        all_text = _narrative_text(html)
        if macd_sign == "positive" and re.search(r"MACD.*?(?:bearish|tiêu cực|cắt xuống|sell)", all_text, re.I):
            if not re.search(r"MACD.*?(?:bullish|tích cực|cắt lên|buy|dương)", all_text, re.I):
                issues.append(f"MACD histogram dương nhưng narrative mô tả bearish")

    passed = len(issues) == 0
    return passed, {
        "price_points": len(closes),
        "computed_rsi": round(computed_rsi, 1) if computed_rsi else None,
        "computed_ma50": round(ma50, 1) if len(closes) >= 50 else None,
        "macd_histogram_sign": macd_sign if len(closes) >= 26 else None,
        "issues": issues,
    }


def verify_macro_data_citation(req, html):
    """REQ-047: Macro data citation — số vĩ mô/ngành phải cite nguồn."""
    if not html:
        return False, {"error": "no html"}
    text = _narrative_text(html)

    macro_kws = [
        r"GDP", r"CPI", r"lạm phát", r"lãi suất", r"FDI", r"tăng trưởng ngành",
        r"tổng mức bán lẻ", r"IIP", r"PMI", r"xuất khẩu", r"nhập khẩu", r"tỷ giá",
        r"vốn đầu tư", r"giải ngân", r"tín dụng", r"cung tiền",
    ]
    source_kws = [
        r"GSO", r"Tổng cục Thống kê", r"NHNN", r"Ngân hàng Nhà nước",
        r"World Bank", r"IMF", r"ADB", r"FiinPro", r"báo cáo ngành",
        r"CTCK", r"công ty chứng khoán", r"Bộ", r"Tổng cục", r"ref-\d",
        r"công bố", r"theo", r"ước tính", r"Bloomberg", r"Reuters",
    ]

    issues = []
    found = 0
    for kw in macro_kws:
        for m in re.finditer(kw, text, re.I):
            # CPI cũng là mã cổ phiếu. Khi report của chính CPI, chỉ coi
            # token này là claim vĩ mô nếu ngay cạnh có ngữ nghĩa chỉ số giá
            # hoặc một số %. Header "CPI | Evidence Pack 1–3 năm" không phải claim.
            if TICKER.upper() == "CPI" and m.group(0).upper() == "CPI":
                local = text[max(0, m.start()-35):m.end()+35]
                if not (re.search(r"lạm\s*phát|chỉ\s*số\s*giá", local, re.I)
                        or re.search(r"CPI\s*(?:tăng|giảm|ở|=|:)\s*-?\d[\d.,]*\s*%", local, re.I)):
                    continue
            ctx = text[max(0, m.start() - 60):m.end() + 200]
            has_number = bool(re.search(r"\d[\d.,]*\s*%?", ctx))
            if not has_number:
                continue
            found += 1
            has_source = any(re.search(sk, ctx, re.I) for sk in source_kws)
            if not has_source:
                issues.append(f"macro claim '{m.group(0)}' có số nhưng không cite: ...{ctx.strip()[:120]}...")

    passed = len(issues) == 0
    return passed, {
        "macro_claims_with_numbers": found,
        "uncited": len(issues),
        "issues": issues[:5],
    }


def verify_management_claim(req, html):
    """REQ-048: Management claim — claim về lãnh đạo/cổ đông phải có nguồn."""
    if not html:
        return False, {"error": "no html"}
    text = _narrative_text(html)
    profile = _load_json_rel("company_profile.json")
    known_names = set()
    if profile and isinstance(profile, dict):
        for k in ("ceo", "chairman", "ceo_name", "chairman_name", "company_name"):
            v = profile.get(k)
            if v:
                known_names.update(v.lower().split())

    mgmt_kws = [
        r"\b(?:ông|bà)\s+[A-Z][a-zà-ỹ]+\s+[A-Z][a-zà-ỹ]+",
        r"CEO", r"Chủ tịch\s+HĐQT", r"Tổng\s+giám\s+đốc", r"Giám\s+đốc\s+tài\s+chính",
        r"cổ đông lớn", r"sở hữu\s+\d+%", r"ban\s+lãnh\s+đạo",
    ]
    # Lưu ý VN100 (2026-08-02): "CFO" đã BỊ LOẠI khỏi keywords quản lý — trong báo cáo
    # VN "CFO" gần như luôn = Cash Flow from Operations (dòng tiền hoạt động), còn giám
    # đốc tài chính được viết đầy đủ "Giám đốc tài chính" (có ở trên). Trước đây fail
    # 71/71 mã: "CFO biến động theo hoạt động" + mô tả meta "…inventory, cfo…" bị bắt.
    issues = []
    found = 0
    for kw in mgmt_kws:
        for m in re.finditer(kw, text, re.I):
            # CEO cũng là mã cổ phiếu. Token identity trong title/nav không
            # tạo management claim; vẫn kiểm nếu có ngữ cảnh chức vụ thật.
            if TICKER.upper() == "CEO" and m.group(0).upper() == "CEO":
                local = text[max(0, m.start()-45):m.end()+45]
                if not re.search(r"tổng\s*giám\s*đốc|lãnh\s*đạo|bổ\s*nhiệm|miễn\s*nhiệm|"
                                 r"điều\s*hành|chức\s*vụ|\b(?:ông|bà)\b", local, re.I):
                    continue
            found += 1
            ctx = text[max(0, m.start() - 100):m.end() + 200]
            # FIX VN100 (ACB 2026-08-02): "CFO" trong tài chính VN = cash flow from
            # operations (dòng tiền hoạt động), KHÔNG phải Chief Financial Officer —
            # context ±60 có dấu hiệu dòng tiền → bỏ qua, không coi là claim quản lý
            # (trước đây fail 71/71 mã: "CFO biến động theo hoạt động" bị bắt).
            if m.group(0).upper() == "CFO" and re.search(
                    r"dòng tiền|cash flow|hoạt động kinh doanh|lưu chuyển|thanh khoản|biến động|dương|âm",
                    text[max(0, m.start() - 60):m.end() + 60], re.I):
                continue
            # Known name from company_profile → PASS
            if profile and any(n in ctx.lower() for n in known_names if len(n) > 3):
                continue
            has_source = bool(re.search(r"ref-\d|BCTC|theo|công bố|disclaimer|CHƯA KIỂM CHỨNG", ctx, re.I))
            if not has_source:
                issues.append(f"mgmt claim '{m.group(0)[:40]}' không có nguồn: ...{ctx.strip()[:100]}...")

    passed = len(issues) == 0
    return passed, {
        "management_claims_found": found,
        "uncited": len(issues),
        "issues": issues[:5],
        "note": "tên từ company_profile.json được miễn cite",
    }


def verify_historical_return(req, html):
    """REQ-049: Historical return verify — claim 'tăng X%' phải tính được từ price."""
    if not html:
        return False, {"error": "no html"}
    text = _narrative_text(html)

    # Load price weekly data
    price_data = _load_json_rel("data/price_weekly.json") or _load_json_rel("data/price_daily.json")
    closes = []
    if price_data and isinstance(price_data, list):
        closes = [float(d.get("close") or d.get("price") or 0) for d in price_data if isinstance(d, dict)]
        closes = [c for c in closes if c > 0]

    if len(closes) < 20:
        return True, {"note": f"insufficient price data ({len(closes)} points) — cannot verify returns"}

    # Find return claims: "tăng/giảm X% trong Y năm/tháng"
    issues = []
    found = 0
    for m in re.finditer(r"(?:tăng|giảm|mất)\s+(\d+(?:[.,]\d+)?)\s*%[^.]{0,60}?(?:trong\s+)?(\d+)\s*(năm|tháng|tuần|phiên|ngày)", text, re.I):
        found += 1
        claimed_pct = float(m.group(1).replace(",", "."))
        period_val = int(m.group(2))
        period_unit = m.group(3).lower()

        # Approx bars: năm~52w, tháng~4w, tuần~1w, phiên/ngày~1d
        if "năm" in period_unit:
            bars = period_val * 52
        elif "tháng" in period_unit:
            bars = period_val * 4
        else:
            bars = period_val

        if bars < len(closes):
            start_price = closes[-bars - 1] if bars + 1 <= len(closes) else closes[0]
            end_price = closes[-1]
            actual_pct = (end_price - start_price) / start_price * 100

            # Allow ±20% tolerance (different start dates)
            if abs(claimed_pct - actual_pct) > max(20, abs(actual_pct) * 0.5):
                direction = "tăng" if actual_pct > 0 else "giảm"
                issues.append(
                    f"return claim {claimed_pct:+.1f}% trong {period_val} {period_unit} ≠ actual {actual_pct:+.1f}%"
                )

    passed = len(issues) == 0
    return passed, {
        "return_claims_found": found,
        "price_data_points": len(closes),
        "issues": issues[:5],
        "tolerance": "±20% hoặc ±50% relative (khác ngày bắt đầu)",
    }


def verify_comparison_baseline(req, html):
    """REQ-050: Comparison baseline — so sánh phải có baseline cụ thể."""
    if not html:
        return False, {"error": "no html"}
    text = _narrative_text(html)

    comparative_kws = [
        r"cao\s+hơn", r"thấp\s+hơn", r"tốt\s+hơn", r"kém\s+hơn",
        r"vượt\s+trội", r"cải\s+thiện", r"suy\s+giảm", r"tăng\s+trưởng\s+mạnh",
        r"vượt\s+qua", r"hơn\s+hẳn",
    ]
    issues = []
    found = 0
    for kw in comparative_kws:
        for m in re.finditer(kw, text, re.I):
            found += 1
            ctx = text[max(0, m.start() - 100):m.end() + 100]
            has_baseline = bool(re.search(r"\d[\d.,]*\s*(%|tỷ|tỉ|x|lần|điểm)", ctx))
            has_cite = bool(re.search(r"ref-\d|BCTC|vnstock|theo|nguồn|data", ctx, re.I))
            if not has_baseline and not has_cite:
                issues.append(f"so sánh '{m.group(0)}' không có số baseline: ...{ctx.strip()[:100]}...")

    # Batch-4 (nghiệm thu V4 Flash): bỏ hardcode return True — main() xử lý
    # priority=advisory → WARN không block. passed = kết quả thật để "1 nguồn sự thật":
    # đổi YAML priority thành high sẽ làm REQ này block deploy.
    passed = len(issues) == 0
    return passed, {
        "comparative_claims_found": found,
        "missing_baseline": len(issues),
        "warnings": issues[:5],
        "note": "advisory — main() WARN không block deploy",
    }


def verify_unit_consistency(req, html):
    """REQ-051: Unit consistency — thống nhất đơn vị tỷ đồng trong toàn dashboard."""
    if not html:
        return False, {"error": "no html"}

    # Collect all VND amounts with units from different sections
    metric_patterns = {
        "revenue": [r"doanh thu", r"revenue"],
        "profit": [r"lợi nhuận", r"LNST", r"NPAT", r"profit"],
    }

    issues = []
    for metric_name, kws in metric_patterns.items():
        all_values = []  # (value_in_ty, unit_str, section, context)
        for sid in re.findall(r'<section[^>]*id="(sec-[a-z0-9-]+)"', html):
            sec_text = extract_section_text(html, sid)
            if not sec_text or len(sec_text) < 50:
                continue
            for kw in kws:
                pat = re.compile(kw + r"[^0-9]{0,60}?(\d[\d.,]*)\s*(nghìn tỷ|ngàn tỷ|tỷ|tỉ|triệu|tr)?", re.I)
                for m in pat.finditer(sec_text):
                    v = _normalize_number(m.group(1))
                    if v is None:
                        continue
                    unit = m.group(2) or ""
                    # V5 fix: số không đơn vị (năm 2025, giá 60.000 đồng, tỷ lệ 2.5%)
                    # không thể đánh giá "trộn đơn vị" → bỏ qua
                    if not unit or (1900 <= v <= 2100):
                        continue
                    scaled = _scale_to_tỷ(v, unit)
                    if scaled > 0.1:
                        all_values.append((scaled, unit, sid, m.group(0)[:80]))

        if all_values:
            magnitudes = [v[0] for v in all_values]
            vmin, vmax = min(magnitudes), max(magnitudes)
            # If max/min > 100x → possible unit inconsistency
            if vmax > 0 and vmin > 0 and vmax / vmin > 100:
                # Check if the difference is due to "nghìn tỷ" vs "tỷ" (~1000x)
                if vmax / vmin > 500:
                    issues.append(
                        f"{metric_name}: magnitude range {vmin:,.0f}–{vmax:,.0f} tỷ chênh >500x → possible unit mix"
                    )

    passed = len(issues) == 0
    return passed, {
        "unit_inconsistencies": issues[:5],
        "note": "MEDIUM — flag potential nghìn tỷ vs tỷ confusion",
    }


def verify_liquidity(req, html):
    """REQ-052: Liquidity — dashboard nên có thông tin thanh khoản nếu có data."""
    if not html:
        return False, {"error": "no html"}
    text = _narrative_text(html)

    has_liquidity = any(kw in text.lower() for kw in [
        "thanh khoản", "khối lượng giao dịch", "KLGD", "volume",
        "giá trị giao dịch", "free float", "room ngoại",
    ])

    # Check if source pack has volume data
    price_data = _load_json_rel("data/price_daily.json")
    has_volume_data = False
    if price_data and isinstance(price_data, list) and len(price_data) > 0:
        has_volume_data = any(
            isinstance(d, dict) and (d.get("volume") or d.get("vol"))
            for d in price_data[:5]
        )

    # Batch-4 (nghiệm thu V4 Flash): bỏ hardcode — main() xử lý advisory.
    # passed = kết quả thật. Nếu source có volume data mà dashboard thiếu liquidity
    # → missing (advisory sẽ WARN, không block).
    if has_volume_data and not has_liquidity:
        return False, {"warning": "source pack has volume data but dashboard missing liquidity info",
                      "note": "advisory — main() WARN không block deploy"}

    return True, {
        "has_liquidity_info": has_liquidity,
        "has_volume_data": has_volume_data,
        "note": "PASS" if has_liquidity else "no liquidity section but no volume data either",
    }


def verify_audit_opinion(req, html):
    """REQ-053: Audit opinion — BCTC ngoại trừ phải có disclaimer."""
    if not html:
        return False, {"error": "no html"}
    text = _narrative_text(html)

    # Check company_profile for audit_opinion
    profile = _load_json_rel("company_profile.json")
    audit_opinion = None
    if profile and isinstance(profile, dict):
        audit_opinion = (profile.get("audit_opinion") or
                        profile.get("audit_opinion_type") or
                        profile.get("kiem_toan") or "")

    # Also check financials for audit field
    fin = _load_json_rel("data/financials.json")
    if fin and isinstance(fin, dict):
        audit_opinion = audit_opinion or fin.get("audit_opinion") or ""

    if not audit_opinion:
        return True, {"note": "no audit_opinion field in source data — cannot verify"}

    audit_lower = audit_opinion.lower()
    is_qualified = any(kw in audit_lower for kw in [
        "ngoại trừ", "không chấp nhận", "từ chối", "qualified",
        "adverse", "disclaimer", "except",
    ])

    if not is_qualified:
        return True, {"audit_opinion": audit_opinion, "status": "clean — PASS"}

    # Qualified opinion → dashboard MUST have disclaimer
    has_disclaimer = any(kw in text.lower() for kw in [
        "ý kiến ngoại trừ", "kiểm toán ngoại trừ", "qualified opinion",
        "hạn chế", "không đảm bảo", "lưu ý kiểm toán", "audit disclaimer",
    ])

    if not has_disclaimer:
        return False, {
            "audit_opinion": audit_opinion,
            "error": "BCTC có ý kiến kiểm toán KHÔNG sạch nhưng dashboard không có disclaimer",
            "hint": "phải ghi chú rõ hạn chế của BCTC trong sec-risk hoặc sec-checklist",
        }

    return True, {
        "audit_opinion": audit_opinion,
        "has_disclaimer": True,
        "note": "qualified opinion properly disclosed",
    }


def verify_causal_chain(req, html):
    """REQ-054: Causal chain evidence — chuỗi nhân quả phải có evidence."""
    if not html:
        return False, {"error": "no html"}
    text = _narrative_text(html)

    causal_connectors = [
        r"\bnhờ\s+(?!vào\s+đó)", r"\bdo\s+(?!đó|vậy|vì\s+vậy)", r"\bvì\s+(?!vậy)", r"\bbởi\s+",
        r"\bdẫn\s+đến", r"\bkhiến\s+", r"\bgây\s+ra", r"\btác\s+động", r"\bảnh\s+hưởng",
        r"\bkết\s+quả\s+của", r"\bnguyên\s+nhân", r"\bđộng\s+lực",
        r"\bnhờ\s+vào", r"\bđược\s+hỗ\s+trợ\s+bởi",
    ]

    issues = []
    found = 0
    for conn in causal_connectors:
        for m in re.finditer(conn, text, re.I):
            # FIX-3c (review V4 Pro M5): chỉ bắt causal claim ĐỊNH LƯỢNG — số kết quả
            # nằm TRƯỚC connector ("Lợi nhuận tăng 35% nhờ...") HOẶC sau
            # ("nhờ X, doanh thu đạt 30.699 tỷ"). Claim thuần định tính ("ngành hồi
            # phục nhờ giải ngân") là phát biểu chung hợp lệ — bỏ qua để tránh FP.
            before = text[max(0, m.start() - 80):m.start()]
            after = text[m.end():m.end() + 80]
            if not re.search(r"\d[\d.,]*\s*(?:%|tỷ|tỉ|triệu|x|lần)", before + " " + after):
                continue
            found += 1
            # Evidence CỤ THỂ trong CÙNG CÂU chứa connector. FIX-3c: số "%" của CHÍNH
            # claim ("tăng 35% nhờ...") không được tính là evidence — cần số định lượng
            # khác (tỷ/triệu/x) hoặc named source. Từ generic "theo/nguồn/data" KHÔNG
            # tính. Window sau nới +140 (câu dài: evidence "tính từ BCTC" có thể cách
            # connector ~90 chars) nhưng vẫn dừng ở dấu câu — không ăn sang câu sau.
            ctx = text[m.start():m.end() + 140]
            m_sep = re.search(r"[.!?;](?!\d)", ctx)
            if m_sep:
                ctx = ctx[:m_sep.start() + 1]
            # Vùng TRƯỚC connector: chỉ 40 chars gần nhất — evidence thật luôn sát
            # connector ("đạt 30.699 tỷ đồng nhờ..."). Số của câu trước ("Vốn hóa
            # 8.018 tỷ") cách xa hơn → không tính (strip tags làm mất dấu phân cách
            # câu </p>, nên không thể dựa vào dấu câu).
            pre = text[max(0, m.start() - 40):m.start()]
            has_evidence = bool(re.search(
                r"\d[\d.,]*\s*(tỷ|tỉ|triệu|x)|ref-\d|BCTC|vnstock|công bố|nghị quyết|"
                r"kiểm toán|báo cáo tài chính|filings",
                ctx, re.I
            )) or bool(re.search(
                r"\d[\d.,]*\s*(tỷ|tỉ|triệu|x)|ref-\d|BCTC|vnstock|công bố|nghị quyết|"
                r"kiểm toán|báo cáo tài chính|filings",
                pre, re.I
            ))
            if not has_evidence:
                issues.append(f"causal claim định lượng không evidence: ...{(pre + ctx).strip()[:120]}...")

    passed = len(issues) == 0 or found == 0
    return passed, {
        "causal_claims_found": found,
        "unverified": len(issues),
        "issues": issues[:5],
        "note": "bất kỳ causal chain không evidence → FAIL (FIX-10: spec/code thống nhất fail-closed; FIX-3c: window ±120, named evidence only)",
    }


def verify_vague_language(req, html):
    """REQ-055: Vague language — đếm hedging phrases, >15 → WARN."""
    if not html:
        return False, {"error": "no html"}
    text = _narrative_text(html)

    # FIX VN100 v4 (2026-08-02): tách 2 nhóm — trước đây gộp "hedging mơ hồ" với
    # "từ nhận định" (hấp dẫn/cơ hội/điểm sáng...) làm báo cáo nghiên cứu chuẩn
    # (vốn PHẢI có nhận định) bị đếm là vague → fail 71/71 mã (advisory).
    # Chỉ đếm hedging THẬT (không cam kết, mơ hồ); opinion words không bị phạt.
    hedging = [
        r"có thể", r"dự kiến", r"khoảng", r"ước tính", r"tiềm năng",
        r"trong tầm ngắm",
    ]
    opinion_words = [
        r"đáng chú ý", r"ấn tượng", r"khả quan", r"tích cực", r"hấp dẫn",
        r"đáng quan tâm", r"cơ hội", r"điểm sáng", r"nổi bật", r"hứa hẹn",
    ]

    count = 0
    for h in hedging:
        count += len(re.findall(h, text, re.I))
    opinion_count = 0
    for h in opinion_words:
        opinion_count += len(re.findall(h, text, re.I))

    # Batch-4 (nghiệm thu V4 Flash): bỏ hardcode return True — main() xử lý advisory.
    # VN100 v4 (2026-08-02): ngưỡng 15 → 25 — sau khi tách opinion words, 6 từ hedging
    # thật trên narrative VN ~4-5K ký tự thường 15-20 lần (đa số "ước tính" KÈM SỐ =
    # estimate hợp lệ, không phải lỏng lẻo). >25 mới là narrative mơ hồ thật sự.
    passed = count <= 25
    evidence = {
        "hedging_phrase_count": count,
        "opinion_word_count": opinion_count,
        "threshold": 25,
        "note": f"{'WARN: excessive vague language' if count > 25 else 'OK'} — advisory, main() WARN không block deploy; từ nhận định (hấp dẫn/cơ hội...) không tính là vague",
    }
    return passed, evidence


def verify_timeframe_consistency(req, html):
    """REQ-056: Timeframe consistency — không cherry-pick timeframe có lợi."""
    if not html:
        return False, {"error": "no html"}
    text = _narrative_text(html)

    short_term_positive = []
    issues = []
    for m in re.finditer(
        r"(?:tăng|tăng\s+trưởng)\s+(\d+(?:[.,]\d+)?)\s*%?\s*(?:so\s+với\s+)?(?:quý\s+trước|QoQ|so\s+với\s+tháng)",
        text, re.I
    ):
        val = float(m.group(1).replace(",", "."))
        if val > 0:
            ctx = text[max(0, m.start() - 300):m.end() + 100]
            has_long_term = bool(re.search(r"(?:YoY|cùng kỳ|so với năm|3 năm|5 năm)", ctx, re.I))
            if not has_long_term:
                short_term_positive.append({
                    "value": val,
                    "context": m.group(0)[:80],
                })

    if short_term_positive:
        issues.append(
            f"{len(short_term_positive)} short-term positive claims without long-term context — possible cherry-pick"
        )

    passed = len(issues) == 0
    return passed, {
        "short_term_positive_claims": len(short_term_positive),
        "missing_long_term_context": len(short_term_positive),
        "issues": issues,
        "note": "QoQ positive mà không có YoY context → WARN cherry-pick",
    }


def verify_dividend_claim(req, html):
    """REQ-057: Dividend claim — phải có nguồn nếu không có data."""
    if not html:
        return False, {"error": "no html"}
    text = _narrative_text(html)

    div_kws = [
        r"cổ tức", r"dividend", r"tỷ lệ chi trả", r"payout",
        r"cổ tức tiền mặt", r"cổ tức cổ phiếu",
    ]

    # Check if source pack has dividend data
    fin = _load_json_rel("data/financials.json")
    has_dividend_data = False
    if fin and isinstance(fin, dict):
        has_dividend_data = any(
            k in fin for k in ("dividend", "dividends", "payout_ratio", "dps")
        )

    issues = []
    found = 0
    for kw in div_kws:
        for m in re.finditer(kw, text, re.I):
            ctx = text[max(0, m.start() - 80):m.end() + 80]
            has_number = bool(re.search(r"\d[\d.,]*\s*%?", ctx))
            if not has_number:
                continue
            found += 1
            if not has_dividend_data:
                has_cite = bool(re.search(
                    r"ref-\d|BCTC|theo|công bố|ĐHCĐ|nghị quyết|CHƯA XÁC MINH|sponsor",
                    ctx, re.I
                ))
                if not has_cite:
                    issues.append(f"dividend claim không có data + không cite: ...{ctx.strip()[:100]}...")

    passed = len(issues) == 0
    return passed, {
        "dividend_claims_with_numbers": found,
        "has_dividend_data": has_dividend_data,
        "uncited": len(issues),
        "issues": issues[:5],
    }


def verify_support_resistance_method(req, html):
    """REQ-058: Support/Resistance method — S/R levels phải kèm method."""
    if not html:
        return False, {"error": "no html"}
    text = _narrative_text(html)

    method_kws = [
        r"swing", r"fibonacci", r"MA\d*", r"moving average", r"round number",
        r"pivot", r"volume profile", r"VAP", r"đỉnh", r"đáy",
        r"kháng cự.*đỉnh", r"hỗ trợ.*đáy", r"trendline", r"ngưỡng",
    ]

    issues = []
    found_sr = 0
    for m in re.finditer(r"(?:hỗ\s*trợ|kháng\s*cự|support|resistance)[^0-9]{0,50}?(\d[\d.,]*)", text, re.I):
        v = _normalize_number(m.group(1))
        # V5 fix: năm (2021) và số nhỏ (101, 8.3, 2.5...) không phải mức S/R giá cổ phiếu
        if v is None or v < 1000 or (1900 <= v <= 2100 and float(v).is_integer()):
            continue
        found_sr += 1
        ctx = text[max(0, m.start() - 200):m.end() + 50]
        has_method = any(re.search(mk, ctx, re.I) for mk in method_kws)
        if not has_method:
            issues.append(f"S/R level '{m.group(1)}' không có method: ...{ctx.strip()[:100]}...")

    passed = len(issues) < 2  # allow 1 S/R without method, ≥2 → FAIL
    return passed, {
        "sr_levels_found": found_sr,
        "without_method": len(issues),
        "issues": issues[:5],
        "note": "≥2 S/R levels không method → FAIL",
    }


def verify_period_integrity(req, html):
    """REQ-062: Period integrity — port từ v1.0.1 period_integrity_gate.py.

    Validates (period, value) pairs trong verified-dashboard-data.json khớp raw CSV.
    6 sub-checks: raw_periods_unique, values_length_match, period_order_detected,
    period_value_pairs_preserved, latest_matches, oldest_matches.
    Per-field cross-check: revenue, net_profit, eps, total_assets, total_equity, capex.
    """
    vdd = _load_json_rel("verified-dashboard-data.json")
    if not vdd or not isinstance(vdd, dict):
        return False, {"error": "thiếu verified-dashboard-data.json — period integrity không verify được (W4-4: không vacuous pass)"}

    fin = vdd.get("financials", {})
    if not fin:
        # P0-5 (Sol 2026-08-08): fail-closed — critical/high KHÔNG được PASS rỗng
        return False, {"error": "contract thiếu financials — fail-closed (không vacuous pass)"}

    years = fin.get("years", [])
    expected_count = 5
    sub_checks = {}
    failures = []

    # Sub-check 1: raw_periods_unique
    periods_unique = len(set(years)) == len(years) and len(years) == expected_count
    sub_checks["raw_periods_unique"] = periods_unique
    if not periods_unique:
        failures.append({"code": "PERIOD_DUPLICATE_OR_WRONG_COUNT",
                        "years": years, "expected": expected_count})

    # Sub-check 2: values_length_matches_periods
    field_keys = [
        ("revenue", "revenue"),
        ("net_profit", "netProfit"),
        ("eps", "eps"),
        ("total_assets", "totalAssets"),
        ("total_equity", "equity"),
        ("capex", "capex"),
    ]
    len_ok = True
    for field_name, arr_key in field_keys:
        arr = fin.get(arr_key)
        if arr and isinstance(arr, list) and len(arr) != len(years):
            len_ok = False
            failures.append({"code": "VALUES_LENGTH_MISMATCH",
                           "field": field_name, "arr_len": len(arr), "periods": len(years)})
    sub_checks["values_length_matches_periods"] = len_ok

    # Sub-checks 3-6: Try loading raw CSVs for cross-check
    work_dir = _work_dir()
    # G3 (review V4 Flash): trước đây chỉ tìm CSV ở work_dir ROOT — pipeline chuẩn
    # đặt CSV ở source-pack/ → corrupt CSV root không bao giờ chạy, vacuous PASS.
    # Mở rộng 3 path: root, source-pack/, data/.
    csv_candidates = [
        "income_statement_sponsor.csv", "balance_sheet_sponsor.csv", "cash_flow_sponsor.csv",
    ]

    import csv as _csv
    csv_data = {}
    stmt_map = {"income_statement_sponsor.csv": "income",
                "balance_sheet_sponsor.csv": "balance",
                "cash_flow_sponsor.csv": "cash"}
    for fname in csv_candidates:
        for sub in ("", "source-pack", "data"):
            path = os.path.join(work_dir, sub, fname)
            if os.path.exists(path):
                try:
                    with open(path) as f:
                        rows = list(_csv.DictReader(f))
                    rows = [r for r in rows if str(r.get("report_period", "")).strip().lower() == "year"] or rows
                    csv_data[stmt_map[fname]] = {"rows": rows, "path": os.path.join(sub, fname)}
                except Exception as e:
                    csv_data[stmt_map[fname]] = {"rows": [], "path": os.path.join(sub, fname), "error": str(e)[:50]}
                break

    if not csv_data:
        sub_checks["period_order_detected"] = False
        sub_checks["explicit_period_value_pairs_preserved"] = False
        sub_checks["latest_period_matches_source"] = False
        sub_checks["oldest_period_matches_source"] = False
        # G3: fail-closed — verified-dashboard-data tồn tại nhưng không có CSV nguồn
        # ở bất kỳ path nào → không verify được period integrity → FAIL (không vacuous)
        return False, {"note": "KHÔNG tìm thấy CSV nguồn ở work_dir / source-pack / data — "
                                "period integrity không đối chiếu được (fail-closed)",
                       "sub_checks": sub_checks,
                       "searched": csv_candidates}

    # Period order detection: years should be chronological
    try:
        years_int = [int(y) for y in years]
        is_ordered = years_int == sorted(years_int)
        sub_checks["period_order_detected"] = is_ordered
    except (ValueError, TypeError):
        is_ordered = False
        sub_checks["period_order_detected"] = False

    # Per-field cross-check against CSVs
    # P0-C (Sol checkpoint 2026-08-08): thêm cfo + inventory là field BẮT BUỘC; thêm
    # alias ngân hàng 'total operating income' cho revenue.
    field_csv_map = [
        ("revenue", "income", ["total operating income", "net sales", "net revenue", "sales", "revenue"], "revenue", 1e-9),
        ("net_profit", "income", ["attributable to parent company", "net profit", "profit after tax"], "netProfit", 1e-9),
        ("eps", "income", ["eps basic", "earnings per share"], "eps", 1.0),
        ("total_assets", "balance", ["total assets"], "totalAssets", 1e-9),
        ("total_equity", "balance", ["owner's equity", "owners' equity", "owners equity", "total equity"], "equity", 1e-9),
        ("capex", "cash", ["purchases of fixed assets", "capex"], "capex", 1e-9),
        ("cfo", "cash", ["net cash inflows/(outflows) from operating activities", "net cash from operating activities", "net cash.*operating"], "cfo", 1e-9),
        ("inventory", "balance", ["inventories, net", "net inventories", "inventories", "inventory", "hàng tồn kho"], "inventory_fin", 1e-9),
    ]
    # P0-C: field bắt buộc — bị skipped (thiếu cột/array/CSV) phải FAIL, không PASS ngầm
    REQUIRED_FIELDS = {"revenue", "net_profit", "eps", "total_assets", "total_equity", "cfo", "inventory"}

    pv_pairs_ok = True
    latest_ok = True
    oldest_ok = True
    per_field = {}

    if is_ordered and years_int:
        latest_period = str(years_int[-1])
        oldest_period = str(years_int[0])

        for canonical, stmt_key, aliases, arr_key, scale in field_csv_map:
            entry = csv_data.get(stmt_key)
            rows = entry["rows"] if isinstance(entry, dict) else (entry or [])
            if not rows:
                # P0-C: field bắt buộc mà thiếu CSV → FAIL (không skip ngầm)
                if canonical in REQUIRED_FIELDS:
                    pv_pairs_ok = False
                    failures.append({"code": "NO_CSV", "field": canonical, "detail": "không tìm thấy CSV nguồn"})
                per_field[canonical] = {"skipped": "no_csv", "path": entry.get("path") if isinstance(entry, dict) else None}
                continue

            # Find column — P0-C (Sol checkpoint 2026-08-08): chọn cột theo ĐỘ KHỚP
            # với contract (match-based), không chỉ theo alias dài nhất — tránh chọn
            # sai cột khi CSV có nhiều cột cùng dạng (vd bảo hiểm: "Net sales from
            # insurance business" vs "Net revenue of insurance premium").
            # Rule not_applicable: financial-statement schema (Total Operating
            # Income) does not carry industrial inventory. This covers banks and
            # non-bank lenders such as EVF without trusting a coarse sector label.
            sector_cfg = str(vdd.get("sector") or "")
            if canonical == "inventory":
                income_rows = (csv_data.get("income") or {}).get("rows", [])
                financial_schema = bool(income_rows and any(
                    str(h).strip().lower() == "total operating income"
                    for h in income_rows[0].keys()
                ))
                if "bank" in sector_cfg.lower() or financial_schema:
                    per_field[canonical] = {
                        "not_applicable": "financial-statement schema — không có hàng tồn kho",
                        "oracle": "source-pack income column Total Operating Income" if financial_schema else "sector=banking",
                    }
                    continue
            # P0 (Sol checkpoint 2): chọn cột theo ALIAS ƯU TIÊN CỐ ĐỊNH (thứ tự danh
            # sách, exact trước substring) — KHÔNG dùng contract làm oracle (tránh
            # oracle vòng tròn: contract tự chứng cho cột được chọn).
            col = None
            for a in aliases:
                col = next((h for h in rows[0].keys() if h.lower().strip() == a), None)
                if col:
                    break
                col = next((h for h in rows[0].keys() if a in h.lower()), None)
                if col:
                    break
            if not col:
                # P0-C: field bắt buộc mà không tìm thấy cột → FAIL
                if canonical in REQUIRED_FIELDS:
                    pv_pairs_ok = False
                    failures.append({"code": "NO_COLUMN", "field": canonical,
                                     "detail": f"không tìm thấy cột trong CSV {stmt_key}"})
                per_field[canonical] = {"skipped": "no_column"}
                continue

            arr = fin.get(arr_key, [])
            if not arr or not isinstance(arr, list):
                # P0-C: field bắt buộc mà contract thiếu array → FAIL
                if canonical in REQUIRED_FIELDS:
                    pv_pairs_ok = False
                    failures.append({"code": "NO_CONTRACT_ARRAY", "field": canonical, "detail": arr_key})
                per_field[canonical] = {"skipped": "no_contract_array"}
                continue

            per_year_results = {}
            for yi, y in enumerate(years_int):
                y_str = str(y)
                # P0 (Sol 2026-08-08): CSV rows có thể bắt đầu sớm hơn contract (vd 2018 vs
                # 2021) — PHẢI match theo cột năm, không lấy theo index (bug vacuous pass
                # trước đây che giấu: REQ-062 chưa từng chạy thật).
                row_y = next((r for r in rows if str(r.get("period", "")).strip() == y_str), None)
                if row_y is None:
                    continue
                raw_val = None
                try:
                    raw_val = float(row_y.get(col, 0))
                except (ValueError, TypeError):
                    pass

                # Normalize capex to absolute
                if canonical == "capex" and raw_val is not None:
                    raw_val = abs(raw_val)

                raw_scaled = raw_val * scale if raw_val is not None else None
                contract_val = arr[yi] if yi < len(arr) else None

                match = False
                if raw_scaled is not None and contract_val is not None:
                    # P0 (CB-2 2026-08-08): builder làm tròn contract 2 decimal — với giá trị
                    # NHỎ (<~0.5 tỷ) sai số làm tròn vượt 1% → false mismatch. Tolerance động:
                    # 1% theo magnitude HOẶC sai số làm tròn tuyệt đối 0.006 tỷ.
                    # Không chia cho contract=0: công thức cũ tạo tolerance 600%
                    # và để mutation 2,213.57→0 lọt.
                    magnitude = max(abs(raw_scaled), abs(contract_val))
                    allowed_abs = max(0.01 * magnitude, 0.006)
                    match = abs(raw_scaled - contract_val) <= allowed_abs

                per_year_results[y_str] = {
                    "raw_value": raw_val,
                    "raw_scaled": round(raw_scaled, 2) if raw_scaled is not None else None,
                    "contract_value": contract_val,
                    "match": match,
                }
                if not match:
                    pv_pairs_ok = False
                    failures.append({
                        "code": "PERIOD_VALUE_PAIR_MISMATCH",
                        "field": canonical, "period": y_str,
                        "raw_scaled": raw_scaled, "contract": contract_val,
                    })

            per_field[canonical] = {"per_year": per_year_results}

            # P0-C: field bắt buộc mà KHÔNG khớp được năm nào (rows thiếu năm contract) → FAIL
            if canonical in REQUIRED_FIELDS and not per_year_results:
                pv_pairs_ok = False
                failures.append({"code": "NO_YEAR_ROWS", "field": canonical,
                                 "detail": f"CSV không có dòng năm nào khớp contract years {years_int}"})
            # P0 (Sol checkpoint 2): thiếu riêng 1 năm raw → FAIL (không âm thầm bỏ qua)
            if canonical in REQUIRED_FIELDS and per_year_results and len(per_year_results) < len(years_int):
                pv_pairs_ok = False
                missing = [y for y in years_int if str(y) not in per_year_results]
                failures.append({"code": "MISSING_YEAR_IN_CSV", "field": canonical,
                                 "detail": f"CSV thiếu năm {missing} trong contract {years_int}"})

            # Check latest/oldest
            if latest_period in per_year_results and not per_year_results[latest_period].get("match"):
                latest_ok = False
            if oldest_period in per_year_results and not per_year_results[oldest_period].get("match"):
                oldest_ok = False

    sub_checks["explicit_period_value_pairs_preserved"] = pv_pairs_ok
    sub_checks["latest_period_matches_source"] = latest_ok
    sub_checks["oldest_period_matches_source"] = oldest_ok

    overall = all(sub_checks.values())
    return overall, {
        "sub_checks": sub_checks,
        "per_field": {k: {kk: vv for kk, vv in v.items() if kk != "per_year"}
                      for k, v in per_field.items()},
        "failures": failures[:10],
        "note": "v1.0.1 period integrity port — block deploy if period inversion detected",
    }


# ═══════════════════════════════════════════════════════════════
# v0.17.0 — V5 WAVE: các gap còn thiếu sau V3/V4 (REQ-059 → REQ-067)
# 059 data provenance (GIGO) · 060 internal identity (cross-footing)
# 061 derived metrics recompute · 063 valuation methods completeness
# 064 trend-sign consistency · 065 verdict-consistency · 066 API fallback log
# 067 fiscal-year alignment
# Tất cả method trả về (passed, evidence), không raise; tái dùng helper V4.
# ═══════════════════════════════════════════════════════════════

def _v5_year_ctx(text, pos, radius=60):
    """Tìm năm (20xx) trong ±radius chars quanh vị trí pos."""
    m = re.search(r"(20\d\d)", text[max(0, pos-radius):pos+radius])
    return m.group(1) if m else None

def verify_data_provenance(req, html):
    """REQ-059: data files phải có nguồn thật — spot-check revenue vs source-pack CSV
    hoặc API vnstock; price phải có fetched_at; task-state phải log data_source."""
    import csv as _csv
    fin = _load_json_rel("data/financials.json")
    if not fin:
        return False, {"error": "data/financials.json not found"}
    issues = []

    # W4-4 (Wave 4): cash_flow.json phải có dòng CFO — mutation "missing CFO" từng lọt,
    # REQ-059 không đọc cash_flow chi tiết. Chống data khuyết im lặng.
    cf = _load_json_rel("data/cash_flow.json")
    if not cf:
        issues.append("data/cash_flow.json không tìm thấy — không verify được CFO")
    else:
        cfo_rows = [k for k in cf.keys() if "operating" in str(k).lower()]
        if not cfo_rows:
            issues.append("cash_flow.json thiếu dòng CFO (operating activities) — phase 2/3 cần CFO")
        else:
            # P0-B (Sol checkpoint 2026-08-08): key tồn tại không đủ — nếu CFO toàn null
            # trong khi CSV nguồn CÓ giá trị thật → builder map sai cột → FAIL
            cfo_vals = []
            for k in cfo_rows:
                v = cf.get(k) or {}
                cfo_vals += [x for x in v.values() if isinstance(x, (int, float)) and x == x]
            if not any(x not in (None, 0) for x in cfo_vals):
                import os as _os, csv as _csv2
                wd = _work_dir()
                csv_path = None
                for sub in ("", "source-pack", "data"):
                    cand = _os.path.join(wd, sub, "cash_flow_sponsor.csv")
                    if _os.path.exists(cand):
                        csv_path = cand
                        break
                if csv_path:
                    with open(csv_path) as f:
                        rows = list(_csv2.DictReader(f))
                    rows = [r for r in rows if str(r.get("report_period", "")).strip().lower() == "year"] or rows
                    cfo_col = None
                    for cand in ("Net cash inflows/(outflows) from operating activities", "Net cash from operating activities"):
                        if rows and cand in rows[0].keys():
                            cfo_col = cand
                            break
                    if cfo_col is None and rows:
                        for k2 in rows[0].keys():
                            if "net cash" in str(k2).lower() and "operating" in str(k2).lower():
                                cfo_col = k2
                                break
                    if cfo_col:
                        raw_vals = []
                        for r in rows:
                            v2 = r.get(cfo_col)
                            if v2 not in (None, ""):
                                try:
                                    raw_vals.append(float(v2))
                                except ValueError:
                                    pass
                        if any(v2 != 0 for v2 in raw_vals):
                            issues.append(
                                f"CFO toàn null/0 trong cash_flow.json nhưng CSV nguồn có dữ liệu thật "
                                f"(cột '{cfo_col}') — builder map sai alias")
    spots = {}  # fin_key → (value, desc, tolerance_pct)

    # G1 (review V4 Flash): trước đây chỉ spot-check revenue → bịa NPAT/EPS/Total
    # assets ĐỒNG BỘ toàn stack (data files + report + DATA arrays) vẫn lọt 67/67.
    # Mở rộng sang 4 field; luôn ưu tiên fetch live khi API sống.
    # (fin_key, income_cols, balance_cols, divisor, tol%)
    _field_specs = [
        ("revenue_ty",  ("Net sales", "Sales", "Doanh thu", "Revenue", "Total operating income", "Operating income"), (), 1e9, 10),
        ("npatmi_ty",   ("Attributable to parent company", "Net profit", "Lợi nhuận sau thuế", "LNST"), (), 1e9, 10),
        ("Total Assets", (), ("Total assets", "Total Assets", "Tổng tài sản"), 1e9, 10),
        ("eps_vnd",     ("EPS basic", "EPS"), (), 1, 15),  # EPS basic, VND/share; tol 15% do diluted
    ]

    def _ground_truth_for(fin_key):
        if fin_key == "Total Assets":
            b = _load_json_rel("data/balance_sheet.json") or {}
            return _dict_get_ci(b, fin_key)
        return _dict_get_ci(fin, fin_key)

    def _ground_truth_years(fin_key):
        gt = _ground_truth_for(fin_key)
        return {int(y) for y in gt.keys() if str(y).isdigit()} if isinstance(gt, dict) else set()

    def _csv_last_annual(path, col, allowed_years=None):
        """Lấy giá trị annual mới nhất của cột trong CSV (dòng 'year'/'FY').
        Khớp cột case-insensitive (VCB: 'TOTAL ASSETS' thay cho 'Total assets').
        Chỉ chọn năm có trong artifact để không so API/CSV 2025 với report kết
        thúc ở 2024 (DVT cohort 2026-08-12)."""
        try:
            with open(path) as f:
                rows = list(_csv.reader(f))
            header = [h.strip() for h in rows[0]]
            ci = header.index(_ci_find(header, col)) if _ci_find(header, col) else None
            if ci is None:
                return None
            period_i = header.index(_ci_find(header, "period")) if _ci_find(header, "period") else None
            report_i = header.index(_ci_find(header, "report_period")) if _ci_find(header, "report_period") else None
            last = None
            for r in rows[1:]:
                if len(r) <= ci:
                    continue
                report_period = r[report_i].strip().lower() if report_i is not None and len(r) > report_i else ""
                period = r[period_i].strip() if period_i is not None and len(r) > period_i else r[0].strip()
                is_annual = report_period in ("year", "fy") or period.lower().startswith(("year", "fy"))
                if not is_annual:
                    continue
                m_year = re.search(r"(?:19|20)\d{2}", period)
                year = int(m_year.group(0)) if m_year else None
                if allowed_years and year not in allowed_years:
                    continue
                try:
                    value = float(r[ci])
                    if value == value and (last is None or year is None or last[1] is None or year >= last[1]):
                        last = (value, year)
                except Exception:
                    pass
            return last
        except Exception:
            return None

    income_csvs = ("source-pack/income_statement_sponsor.csv", "data/income_statement_sponsor.csv", "income_statement_sponsor.csv")
    balance_csvs = ("source-pack/balance_sheet_sponsor.csv", "data/balance_sheet_sponsor.csv", "balance_sheet_sponsor.csv")

    # 1a) Spot-check qua source-pack CSV (offline ground truth, phase 1 fetch)
    for fin_key, income_cols, balance_cols, divisor, tol in _field_specs:
        if fin_key in spots:
            continue
        csvs = income_csvs if income_cols else balance_csvs
        cols = income_cols or balance_cols
        for cand in csvs:
            full = os.path.join(_work_dir(), cand)
            if not os.path.exists(full):
                continue
            for col in cols:
                found = _csv_last_annual(full, col, _ground_truth_years(fin_key))
                if found is not None:
                    v, year = found
                    spots[fin_key] = (v / divisor, f"source-pack CSV ({os.path.basename(cand)}: {col} {year})", tol, year)
                    break
            if fin_key in spots:
                break

    # 1b) API vnstock live — G1-fix (nghiệm thu V4 Flash): luôn fetch live cả 4 field
    #     khi API sống (bỏ 'if fk in spots: continue' — trước đây API chỉ FILL field
    #     thiếu, không OVERRIDE field đã có spot từ CSV → bịa CẢ CSV vẫn lọt).
    #     API live là nguồn KHÔNG thể giả mạo — hàng rào cuối thật sự.
    #     2026-08-10: retry 1 lần khi import lỗi transient (nhiều tiến trình song song
    #     từng gây ModuleNotFoundError tạm thời → false positive REQ-059).
    api_spots = {}  # fin_key → (value, desc, tol, year) — chỉ từ API live
    import time as _time

    def _try_api_live():
        from vnstock_data import Fundamental
        fapi = Fundamental().equity(TICKER)
        # income statement → Net sales / Attributable to parent company / EPS basic
        annual = annual_rows(normalize_statement(
            fapi.income_statement(period='year', lang='en'), 'income'
        ))
        col_map = {
            "revenue_ty": ("Net sales", "Total Operating Income"),
            "npatmi_ty": ("Attributable to parent company", "Net profit/(loss) after tax"),
            "eps_vnd": ("EPS basic (VND)", "EPS basic"),
        }
        for fk, candidates in col_map.items():
            resolved = next((_ci_find(list(annual.columns), col) for col in candidates
                             if _ci_find(list(annual.columns), col) is not None), None)
            if resolved is None:
                continue
            allowed_years = _ground_truth_years(fk)
            best_yr, best_val = None, None
            for idx in annual.index:
                try:
                    yv = int(str(idx)[:4])
                except Exception:
                    continue
                if allowed_years and yv not in allowed_years:
                    continue
                v = float(annual.loc[idx, resolved])
                if best_yr is None or yv > best_yr:
                    best_yr, best_val = yv, v
            if best_val is not None:
                api_spots[fk] = (best_val / (1e9 if fk != "eps_vnd" else 1), f"API vnstock live ({resolved} {best_yr})", 10 if fk != "eps_vnd" else 15, best_yr)
        # balance sheet → Total assets
        bannual = annual_rows(normalize_statement(
            fapi.balance_sheet(period='year', lang='en'), 'balance'
        ))
        ta_col = _ci_find(list(bannual.columns), "Total assets")
        if ta_col is not None:
            allowed_years = _ground_truth_years("Total Assets")
            best_yr, best_val = None, None
            for idx in bannual.index:
                try:
                    yv = int(str(idx)[:4])
                except Exception:
                    continue
                if allowed_years and yv not in allowed_years:
                    continue
                v = float(bannual.loc[idx, ta_col])
                if best_yr is None or yv > best_yr:
                    best_yr, best_val = yv, v
            if best_val is not None:
                api_spots["Total Assets"] = (best_val / 1e9, f"API vnstock live ({ta_col} {best_yr})", 10, best_yr)
    try:
        _try_api_live()
    except Exception as _e1:
        try:
            _time.sleep(2)
            _try_api_live()
        except Exception as _e2:
            if not spots:
                issues.append(f"API spot-check lỗi: {str(_e2)[:60]}")

    # G1-fix: so chéo CSV-spot vs API-spot — lệch > tolerance → FAIL (CSV do agent
    # viết được; API live không thể giả mạo). API chết → CSV là nguồn cuối.
    for fk, (api_val, api_desc, api_tol, api_year) in api_spots.items():
        if fk in spots:
            csv_val, csv_desc, _, csv_year = spots[fk]
            if abs(csv_val - api_val) / max(abs(api_val), 0.001) * 100 > api_tol:
                issues.append(
                    f"{fk} CSV-vs-API CONFLICT: {csv_desc} = {csv_val:,.1f} ≠ API live = {api_val:,.1f} "
                    f"(lệch >{api_tol}%) — CSV có thể bị agent viết, nghi bịa nguồn"
                )
            else:
                spots[fk] = (api_val, api_desc, api_tol, api_year)  # tin API live hơn CSV
        else:
            spots[fk] = (api_val, api_desc, api_tol, api_year)

    # 1c) So sánh từng spot với data files (khoan dung 10%; EPS 15% do diluted)
    for fin_key, _i, _b, _d, _t in _field_specs:
        if fin_key not in spots:
            continue
        gt_val, desc, tol, spot_year = spots[fin_key]
        # ground truth từ financials.json (dict năm) hoặc balance_sheet.json ("Total Assets")
        gt = _ground_truth_for(fin_key)
        if not isinstance(gt, dict):
            issues.append(f"{fin_key}: spot-check có ({desc} = {gt_val:,.1f}) nhưng data file thiếu field — data không có nguồn đối chiếu")
            continue
        years = sorted(int(y) for y in gt.keys() if str(y).isdigit())
        candidates = [str(spot_year)] if spot_year in years else ([str(y) for y in years[-2:]] if years else [])
        matched = None
        for yr in candidates:
            if yr in gt and gt[yr] is not None:
                # Zero and negative values are both real observations. Earlier
                # code skipped zero, making exact 0-vs-0 source matches fail.
                # revenue/npatmi (financials.json) đã ở tỷ; "Total Assets" (balance_sheet.json) ở VND → chia 1e9
                gt_ty = float(gt[yr]) / 1e9 if fin_key == "Total Assets" else float(gt[yr])
                rel_limit = max(abs(gt_val), 0.001) * tol / 100
                # financials.json rounds revenue/NPATMI to 0.01 tỷ; allow only
                # half of that display unit in addition to the relative limit.
                abs_limit = 0.0050001 if fin_key in ("revenue_ty", "npatmi_ty") else 0.0
                if abs(gt_ty - gt_val) <= max(rel_limit, abs_limit):
                    matched = yr
                    break
        if matched is None:
            issues.append(f"{fin_key} spot-check FAIL: {desc} = {gt_val:,.1f} không khớp data {candidates} (±{tol}%)")

    if not spots:
        issues.append("KHÔNG spot-check được field nào (thiếu source-pack CSV và API không fetch được) — data không có nguồn đối chiếu")

    # 2) price_fetched_at phải tồn tại ở data level
    ov = fin.get("overview") or {}
    if ov.get("current_price"):
        ts = _load_json_rel(".task-state/task-state.json")
        has_ts = False
        if ts:
            p1 = (ts.get("phases", {}).get("phase1_data", {}) or {}).get("result") or {}
            has_ts = bool(p1.get("price_fetched_at") or ts.get("price_fetched_at"))
        ov_file = _load_json_rel("data/overview.json")
        has_ov = bool(ov_file and (ov_file.get("price_fetched_at") or ov_file.get("price_source")))
        has_fin = bool(ov.get("price_fetched_at") or ov.get("price_source"))
        if not (has_ts or has_ov or has_fin):
            issues.append("overview có current_price nhưng KHÔNG có price_fetched_at (data/overview.json | financials overview | task-state phase1) — nghi tự điền giá")

    # 3) task-state phase1 phải log data_source
    ts = _load_json_rel(".task-state/task-state.json")
    ds = None
    if ts:
        p1 = (ts.get("phases", {}).get("phase1_data", {}) or {}).get("result") or {}
        ds = p1.get("data_source")
    if not ds:
        issues.append("task-state phase1 chưa log data_source (sponsor|community)")

    # 4) peers.json phải có source
    peers = _load_json_rel("data/peers.json")
    if isinstance(peers, dict) and peers.get("peers") and not peers.get("source"):
        issues.append("peers.json thiếu field 'source' (phải ghi nguồn API)")

    # 5) contract phải có _provenance
    contract = _load_json_rel("verified-dashboard-data.json")
    if contract and not contract.get("_provenance"):
        issues.append("verified-dashboard-data.json thiếu _provenance (built_at/source)")

    passed = len(issues) == 0
    spot_summary = {k: f"{v[0]:,.1f} via {v[1]}" for k, v in spots.items()}
    return passed, {"issues": issues[:8],
                    "spot_check_fields": spot_summary,
                    "data_source": ds}


def verify_internal_identity(req, html):
    """REQ-060: cross-footing — PE×EPS≈price; PB×BVPS≈price; vốn hóa≈price×shares;
    EPS≈NPAT/shares; contract price≈financials price. Chống bịa số lẻ không khớp."""
    fin = _load_json_rel("data/financials.json")
    if not fin:
        return False, {"error": "data/financials.json not found"}
    tol = req["verification"].get("tolerance_pct", 5)
    eps_tol = req["verification"].get("eps_vs_npat_tolerance_pct", 15)  # EPS diluted/CP lưu hành bình quân
    issues = []
    ov = fin.get("overview") or {}
    price, shares = ov.get("current_price"), ov.get("issue_share")
    eps25 = (fin.get("eps_vnd") or {}).get("2025")
    eq25 = (fin.get("equity_ty") or {}).get("2025")
    np25 = (fin.get("npatmi_ty") or {}).get("2025")

    # 1) EPS ≈ NPAT / shares — P0-6 (Sol 2026-08-08): theo IAS 33, EPS reported dùng
    #    cổ phiếu BÌNH QUÂN (weighted-average) và earnings attributable — không được
    #    ép khớp bằng ending shares. Lệch chỉ là cảnh báo (note), KHÔNG fail; EPS bịa
    #    vẫn bị REQ-033 (cross-section narrative vs data) bắt.
    eps_note = ""
    if eps25 and np25 is not None and shares:
        eps_calc = float(np25) * 1e9 / float(shares)
        if abs(eps_calc - float(eps25)) / max(abs(float(eps25)), 0.001) * 100 > eps_tol:
            eps_note = f"EPS {eps25} ≠ NPAT/shares {eps_calc:,.0f} (lệch {abs(eps_calc-float(eps25))/max(abs(float(eps25)),0.001)*100:.0f}% > {eps_tol}% — EPS reported theo cổ phiếu bình quân, chấp nhận, không ép)"

    # 2) PE claim × EPS ≈ price
    val_text = " ".join(s for s in [extract_section_text(html, x) for x in
                                    ["sec-valuation", "sec-hero", "sec-exec"]] if s)
    if not val_text:
        val_text = _narrative_text(html)
    if price and eps25 and eps25 > 0:
        # FIX VN100 (HLT 2026-08-02): EPS ≤ 0 (công ty lỗ) → P/E âm — cross-footing
        # vô nghĩa (P/E âm × EPS âm = giá dương, verifier tính sai dấu → false positive)
        pe = _extract_primary_multiple(val_text, "P/?E", None, tol)
        if pe:
            pe_comp = float(price) / float(eps25)
            pe_abs_tol = max(abs(pe_comp) * tol / 100, 0.005)
            if abs(float(pe) - pe_comp) > pe_abs_tol:
                implied = float(pe) * float(eps25)
                issues.append(f"P/E {pe}× × EPS {eps25} = {implied:,.0f} ≠ giá {price} (tol multiple={pe_abs_tol:.3f})")

    # 3) PB claim × BVPS ≈ price
    if price and eq25 and shares and eq25 > 0:
        bvps = float(eq25) * 1e9 / float(shares)
        pb = _extract_primary_multiple(val_text, "P/?B", None, tol)
        if pb:
            pb_comp = float(price) / bvps
            pb_abs_tol = max(abs(pb_comp) * tol / 100, 0.005)
            if abs(float(pb) - pb_comp) > pb_abs_tol:
                implied = float(pb) * bvps
                issues.append(f"P/B {pb}× × BVPS {bvps:,.0f} = {implied:,.0f} ≠ giá {price} (tol multiple={pb_abs_tol:.3f})")

    # 4) vốn hóa claim ≈ price × shares
    if price and shares:
        mc_ty = float(price) * float(shares) / 1e9
        text = _narrative_text(html)
        for m in re.finditer(r"(?:vốn hóa|market cap)[^.\d]{0,30}?(\d[\d.,]*)\s*((?:nghìn\s*tỷ|tỷ|tỉ|triệu))?", text, re.I):
            # G7 (review V4 Flash): "vốn hóa TOÀN NGÀNH 500.000 tỷ" là quy mô ngành,
            # không phải vốn hóa của CTD → bỏ qua
            between = text[m.start():m.start(1)]
            if re.search(r"ngành|thị trường|industry|toàn", between, re.I):
                continue
            nval = _scale_to_tỷ(_normalize_number(m.group(1)), m.group(2) or "")
            if nval and abs(nval - mc_ty) > max(mc_ty * tol / 100, 0.5):
                issues.append(f"vốn hóa claim {m.group(1)}{m.group(2) or ''} ≈ {nval:,.0f} tỷ ≠ price×shares {mc_ty:,.0f} tỷ (lệch >{tol}%)")

    # 5) contract price vs financials price
    contract = _load_json_rel("verified-dashboard-data.json")
    if contract and contract.get("price") and price:
        if abs(float(contract["price"]) - float(price)) / float(price) * 100 > tol:
            issues.append(f"contract price {contract['price']} ≠ financials price {price} (lệch >{tol}%)")

    passed = len(issues) == 0
    return passed, {"issues": issues[:8], "price": price, "eps_2025": eps25,
                    "note": eps_note or ("no price/eps data to cross-foot" if not price or not eps25 else "")}


def verify_derived_metrics_recompute(req, html):
    """REQ-061: ROE/ROA/net margin/YoY growth/vốn hóa claims phải recompute từ
    financials.json (±5% tương đối hoặc ±1pp tuyệt đối). Chống 'ROE 24%' bịa."""
    fin = _load_json_rel("data/financials.json")
    if not fin:
        return False, {"error": "data/financials.json not found"}
    bs = _load_json_rel("data/balance_sheet.json")
    text = _narrative_text(html)
    issues = []
    checked = 0
    tol_rel = req["verification"].get("tolerance_pct", 5)
    tol_pp = 1.0

    years = sorted(int(y) for y in (fin.get("revenue_ty") or {}).keys() if str(y).isdigit())
    default_year = max(years) if years else 2025

    def _year_in(ctx, default):
        m = re.search(r"(20\d\d)", ctx)
        if m and m.group(1) in (fin.get("revenue_ty") or {}):
            return m.group(1)
        return str(default)

    def _chk(label, claimed, computed, ctx):
        nonlocal checked
        checked += 1
        if abs(computed - claimed) > tol_pp and abs(computed - claimed) / max(abs(computed), 0.001) * 100 > tol_rel:
            issues.append(f"{label} claim {claimed}% ≠ recompute {computed:.1f}% (năm {_year_in(ctx, default_year)})")

    # ROE = NPAT / equity
    # GAP-1 FIX (V4 Flash, đợt so sánh 31-vs-68): pattern cũ `[^.\d]{0,30}?` không cho
    # phép chữ số → kẹt khi có "(2025)" giữa "ROE" và số → "ROE (2025) 24%" vô hình.
    # Thêm optional year prefix (giống FIX-4b cho REQ-033): keyword → ... → (20xx)? → SỐ.
    for m in re.finditer(r"\bROE\b[^0-9]{0,60}?(?:20\d\d[^0-9]{0,60}?)?(-?\d[\d.,]*)\s*%", text, re.I):
        claimed = _normalize_number(m.group(1))
        if claimed is None:
            continue
        ctx = text[max(0, m.start()-80):m.end()+40]
        y = _year_in(ctx, default_year)
        np_ty, eq_ty = (fin.get("npatmi_ty") or {}).get(y), (fin.get("equity_ty") or {}).get(y)
        if np_ty is None or eq_ty is None or eq_ty == 0:
            continue
        _chk("ROE", claimed, float(np_ty) / float(eq_ty) * 100, ctx)

    # ROA = NPAT / total assets (balance_sheet.json, VND → tỷ)
    ta = {}
    if isinstance(bs, dict):
        d = _dict_get_ci(bs, "Total Assets")
        if isinstance(d, dict):
            ta = {str(k): v for k, v in d.items()}
    # GAP-1 FIX: same optional year prefix as ROE ("ROA (2025) X%")
    for m in re.finditer(r"\bROA\b[^0-9]{0,60}?(?:20\d\d[^0-9]{0,60}?)?(-?\d[\d.,]*)\s*%", text, re.I):
        claimed = _normalize_number(m.group(1))
        if claimed is None:
            continue
        ctx = text[max(0, m.start()-80):m.end()+40]
        y = _year_in(ctx, default_year)
        np_ty, ta_ty = (fin.get("npatmi_ty") or {}).get(y), ta.get(y)
        if np_ty is None or ta_ty is None:
            continue
        _chk("ROA", claimed, float(np_ty) / (float(ta_ty) / 1e9) * 100, ctx)

    # Net margin = NPAT / revenue
    # GAP-1 FIX: same optional year prefix as ROE ("Biên LNST (2025) X%")
    for m in re.finditer(r"(?:biên lợi nhuận ròng|net margin|biên lợi nhuận sau thuế|biên LNST)[^0-9]{0,60}?(?:20\d\d[^0-9]{0,60}?)?(-?\d[\d.,]*)\s*%", text, re.I):
        claimed = _normalize_number(m.group(1))
        if claimed is None:
            continue
        ctx = text[max(0, m.start()-80):m.end()+40]
        y = _year_in(ctx, default_year)
        np_ty, rev_ty = (fin.get("npatmi_ty") or {}).get(y), (fin.get("revenue_ty") or {}).get(y)
        if np_ty is None or rev_ty is None or rev_ty == 0:
            continue
        _chk("net margin", claimed, float(np_ty) / float(rev_ty) * 100, ctx)

    # YoY growth doanh thu
    # GAP-1 FIX: same optional year prefix as ROE ("doanh thu tăng năm 2025: 34%")
    for m in re.finditer(r"(?:tăng trưởng doanh thu|doanh thu (?:tăng|giảm)|revenue (?:grew|growth|declined))[^0-9]{0,60}?(?:20\d\d[^0-9]{0,60}?)?(-?\d[\d.,]*)\s*%", text, re.I):
        claimed = _normalize_number(m.group(1))
        if claimed is None:
            continue
        ctx = text[max(0, m.start()-100):m.end()+40]
        y = _year_in(ctx, default_year)
        rev = fin.get("revenue_ty") or {}
        yp = str(int(y) - 1)
        if y in rev and yp in rev and float(rev[yp]) != 0:
            _chk("YoY revenue", claimed, (float(rev[y]) / float(rev[yp]) - 1) * 100, ctx)

    # YoY growth lợi nhuận
    # GAP-1 FIX: same optional year prefix as ROE ("lợi nhuận tăng 2025: 110%")
    for m in re.finditer(r"(?:tăng trưởng lợi nhuận|lợi nhuận (?:tăng|giảm)|profit (?:grew|growth|declined)|npatmi (?:tăng|giảm))[^0-9]{0,60}?(?:20\d\d[^0-9]{0,60}?)?(-?\d[\d.,]*)\s*%", text, re.I):
        claimed = _normalize_number(m.group(1))
        if claimed is None:
            continue
        ctx = text[max(0, m.start()-100):m.end()+40]
        y = _year_in(ctx, default_year)
        npat = fin.get("npatmi_ty") or {}
        yp = str(int(y) - 1)
        if y in npat and yp in npat and float(npat[yp]) != 0:
            _chk("YoY NPAT", claimed, (float(npat[y]) / float(npat[yp]) - 1) * 100, ctx)

    # Market cap = price × shares
    ov = fin.get("overview") or {}
    if ov.get("current_price") and ov.get("issue_share"):
        mc_ty = float(ov["current_price"]) * float(ov["issue_share"]) / 1e9
        for m in re.finditer(r"(?:vốn hóa|market cap)[^.\d]{0,30}?(\d[\d.,]*)\s*((?:nghìn\s*tỷ|tỷ|tỉ|triệu))?", text, re.I):
            # G7 (review V4 Flash): "vốn hóa TOÀN NGÀNH" là quy mô ngành → bỏ qua
            between = text[m.start():m.start(1)]
            if re.search(r"ngành|thị trường|industry|toàn", between, re.I):
                continue
            nval = _scale_to_tỷ(_normalize_number(m.group(1)), m.group(2) or "")
            if nval is None or nval == 0:
                continue
            checked += 1
            # Report displays market cap as whole tỷ; accept half a display step.
            if abs(nval - mc_ty) > max(mc_ty * tol_rel / 100, 0.5):
                issues.append(f"vốn hóa claim {m.group(1)}{m.group(2) or ''} ≈ {nval:,.0f} tỷ ≠ price×shares {mc_ty:,.0f} tỷ")

    passed = len(issues) == 0
    return passed, {"issues": issues[:8], "checked": checked,
                    "note": "no derived-metric claims" if checked == 0 else ""}


def verify_valuation_methods(req, html):
    """REQ-063: 9 phương pháp định giá — method không có giá trị phải được nhắc
    với lý do N/A (ngân hàng, công ty lỗ...); Graham recompute ±5%."""
    ts = _load_json_rel(".task-state/task-state.json")
    src = src_name = None
    if ts:
        r = (ts.get("phases", {}).get("phase3_valuation", {}) or {}).get("result")
        if isinstance(r, dict):
            src, src_name = r, "task-state.phase3_valuation"
    if src is None:
        contract = _load_json_rel("verified-dashboard-data.json")
        if contract and isinstance(contract.get("valuation"), dict):
            src, src_name = contract["valuation"], "verified-dashboard-data.json.valuation"
    issues = []
    if src is None:
        return False, {"error": "thiếu nguồn valuation (task-state phase3 / contract.valuation)"}

    methods = req["verification"].get("methods", ["ev_ebitda", "ps", "pcf", "dcf_per_share", "graham_number"])
    labels_map = {
        "ev_ebitda": ["ev/ebitda", "ev ebitda"],
        "ps": ["p/s"],
        "pcf": ["p/cf", "pcf"],
        "dcf_per_share": ["dcf", "chiết khấu dòng tiền", "dòng tiền chiết khấu"],
        "graham_number": ["graham", "số graham"],
        "converge_median": ["converge", "median định giá"],
        "ddm": ["ddm", "cổ tức chiết khấu"],
        "reverse_dcf": ["reverse dcf", "dcf ngược"],
    }
    na_pat = r"(?:n/a|na\b|không áp dụng|không phù hợp|không có ý nghĩa|không tính|không dùng|không sử dụng|bỏ qua|vô nghĩa|không đáng tin|thiếu data|không có data|không khả thi)"
    text = _narrative_text(html)
    for meth in methods:
        val = src.get(meth)
        if val is not None and val != 0:
            continue
        labels = labels_map.get(meth, [meth])
        mentioned = False
        found_na = False
        for lbl in labels:
            # A ticker may itself equal a valuation acronym (for example DCF).
            # Do not interpret the entity token as a method claim; descriptive
            # aliases such as "chiết khấu dòng tiền" remain fully checked.
            if re.sub(r"[^a-z0-9]", "", lbl.lower()) == re.sub(r"[^a-z0-9]", "", TICKER.lower()):
                continue
            for m in re.finditer(re.escape(lbl), text, re.I):
                mentioned = True
                # Lý do N/A có thể đứng trước method trong cùng câu, ví dụ
                # "không dùng FCFF/WACC/Graham kiểu công nghiệp". Chỉ mở cửa
                # sổ trong cùng câu để một N/A ở câu trước không miễn nhầm method.
                prefix_start = max(0, m.start()-160)
                prefix = text[prefix_start:m.start()]
                left_seps = list(re.finditer(r"(?<!\d)[.!?](?!\d)", prefix))
                left_bound = (prefix_start + left_seps[-1].start()) if left_seps else prefix_start - 1
                suffix = text[m.end():m.end()+160]
                right_sep = re.search(r"(?<!\d)[.!?](?!\d)", suffix)
                right_bound = (m.end() + right_sep.end()) if right_sep else min(len(text), m.end()+160)
                sentence = text[left_bound+1:right_bound]
                if re.search(na_pat, sentence, re.I):
                    found_na = True
                    break
            if found_na:
                break
        if mentioned and not found_na:
            issues.append(f"method '{meth}' được nhắc trong narrative nhưng không có giá trị trong {src_name} và không đánh dấu N/A có lý do")

    # Graham recompute từ data
    fin = _load_json_rel("data/financials.json")
    g = src.get("graham_number")
    if g and fin:
        eps = (fin.get("eps_vnd") or {}).get("2025")
        eq = (fin.get("equity_ty") or {}).get("2025")
        ov = fin.get("overview") or {}
        if eps and eq and ov.get("issue_share"):
            bvps = float(eq) * 1e9 / float(ov["issue_share"])
            g_comp = (22.5 * float(eps) * bvps) ** 0.5
            if abs(g_comp - float(g)) / max(abs(g_comp), 0.001) * 100 > 5:
                issues.append(f"Graham recompute {g_comp:,.0f} ≠ report/nguồn {g:,.0f} (>5%)")

    passed = len(issues) == 0
    return passed, {"issues": issues[:8], "source": src_name, "methods": methods}


def verify_trend_consistency(req, html):
    """REQ-064: từ ngữ tăng/giảm gần metric phải cùng dấu với dữ liệu (overall hoặc
    theo năm). Chống narrative 'nghe có vẻ đúng' nhưng ngược dữ liệu."""
    fin = _load_json_rel("data/financials.json")
    if not fin:
        return False, {"error": "data/financials.json not found"}
    text = _narrative_text(html)
    # FIX V6 (HPG cohort 2026-08-01): cắt phần glossary/footer trước khi quét —
    # "CAGR — tốc độ tăng trưởng gộp hàng năm..." trong mục giải thích thuật ngữ
    # nằm trong cửa sổ 180 ký tự sau "lợi nhuận" → false positive trend.
    for marker in ("Giải thích thuật ngữ", "THUẬT NGỮ", "Glossary", "DISCLAIMER", "Disclaimer"):
        idx = text.find(marker)
        if idx > 0:
            text = text[:idx]
            break
    issues = []
    for metric, labels, series_key, display in [
        ("revenue", ["doanh thu", "revenue"], "revenue_ty", "doanh thu"),
        ("npatmi", ["lợi nhuận sau thuế", "lợi nhuận ròng", "lnst", "net profit", "lợi nhuận"], "npatmi_ty", "lợi nhuận"),
    ]:
        series = fin.get(series_key, {})
        yrs = sorted(int(y) for y in series.keys() if str(y).isdigit())
        if len(yrs) < 2:
            continue
        overall = 1 if float(series[str(yrs[-1])]) > float(series[str(yrs[0])]) else -1
        for lbl in labels:
            for m in re.finditer(lbl, text, re.I):
                pre = text[max(0, m.start()-30):m.end()+10]
                if re.search(r"biên lợi nhuận|margin|lợi nhuận gộp|gross", pre, re.I):
                    continue  # biên/gộp ≠ chuỗi dữ liệu ròng
                ctx = text[max(0, m.start()-30):m.end()+60]
                tm = re.search(r"(tăng trưởng|tăng đều|đi lên|phục hồi|tăng|giảm|sụt giảm|suy giảm|đi xuống|sụt|lao dốc|co lại)", ctx, re.I)
                if not tm:
                    continue
                # G6 (review V4 Flash): "chi phí tăng nhanh hơn doanh thu" — trend word
                # "tăng" thuộc về CHI PHÍ, không phải doanh thu → bỏ qua (tránh báo oan
                # khi revenue giảm). Check vùng ±60 quanh trend word.
                tm_zone = text[max(0, tm.start()-60):tm.end()+20]
                if re.search(r"chi phí|giá vốn|expense|cost", tm_zone, re.I):
                    continue
                neg_win = ctx[max(0, tm.start()-40):tm.end()+20]
                if re.search(r"không\s+(?:còn\s+)?(?:tăng|giảm)|không\s+tăng", neg_win, re.I):
                    continue
                word = tm.group(1).lower()
                claim_sign = 1 if any(w in word for w in ["tăng", "đi lên", "phục hồi"]) else -1
                # FIX V6.2 (HPG cohort 2026-08-01): claim đi kèm SỐ % cụ thể là YoY
                # (vd "LNST 15,453.3 tỷ (tăng 28.5%)" = 2025 vs 2024, ĐÚNG) — nếu khớp
                # YoY recompute năm cuối → hợp lệ; không so với overall 5 năm
                # (34,478 → 15,453 = giảm → false positive trước đây).
                pct_m = re.search(r"(-?\d[\d.,]*)\s*%", ctx)
                if pct_m and len(yrs) >= 2:
                    claimed_pct = _normalize_number(pct_m.group(1))
                    yoy_pct = (float(series[str(yrs[-1])]) / float(series[str(yrs[-2])]) - 1) * 100
                    if claimed_pct is not None and abs(claimed_pct - yoy_pct) <= 10:
                        continue  # claim YoY khớp → hợp lệ, bỏ qua
                ym = re.search(r"(20\d\d)", ctx)
                if ym and ym.group(1) in series:
                    y = int(ym.group(1))
                    sign = (1 if float(series[str(y)]) > float(series[str(y-1)]) else -1) if y > yrs[0] else overall
                else:
                    sign = overall
                if claim_sign != sign:
                    issues.append(f"'{display}' trend '{word}' ngược dữ liệu (data sign={sign}): ...{ctx.strip()[:90]}...")
    passed = len(issues) == 0
    return passed, {"issues": issues[:8], "note": "no trend claims found" if not issues else ""}


def verify_verdict_consistency(req, html):
    """REQ-065: tone kết luận (exec/thesis) phải cùng dấu với upside/downside từ
    valuation targets. Chống 'kết luận tích cực' trong khi mọi method ra giá thấp hơn."""
    import statistics
    fin = _load_json_rel("data/financials.json")
    price = (fin or {}).get("overview", {}).get("current_price") if fin else None
    ts = _load_json_rel(".task-state/task-state.json")
    targets = []
    if ts:
        r = (ts.get("phases", {}).get("phase3_valuation", {}) or {}).get("result")
        if isinstance(r, dict):
            t = r.get("targets")
            if isinstance(t, dict):
                targets = [v for v in t.values() if isinstance(v, (int, float)) and v > 0]
    if not targets and price:
        val = extract_section_text(html, "sec-valuation") or ""
        for m in re.finditer(r"(?:giá hợp lý|fair value|target price|giá mục tiêu|giá trị hợp lý)[^.\d]{0,40}?(\d[\d.,]*)\s*(nghìn)?", val, re.I):
            v = _normalize_number(m.group(1))
            if v and not (2000 <= v <= 2099):
                targets.append(v)
    if not targets or not price:
        return True, {"note": "không có targets/price để so upside — bỏ qua"}
    upside = statistics.median(targets) / float(price) - 1
    issues = []
    # GAP-3 FIX (V4 Flash, đợt so sánh 31-vs-68): claim "Upside X%" phải recompute được
    # từ targets vs price (±5pp). Trước đây chỉ check tone — report ghi "Upside 13.3%"
    # trong khi targets cho upside khác >5pp thì không REQ nào bắt.
    # Bắt 3 dạng: "upside ... X%", "X% ... upside", "(+X% so với giá hiện tại)".
    # Lưu ý: `issues` phải khai báo TRƯỚC block này (bản đầu để sau → crash khi có claim
    # lệch >5pp, chỉ sạch khi không có claim nào chạm ngưỡng).
    ntext = _narrative_text(html)
    up_claims = []
    for m in re.finditer(r"upside[^.%0-9]{0,30}?(-?\d[\d.,]*)\s*%", ntext, re.I):
        v = _normalize_number(m.group(1))
        if v is not None:
            up_claims.append(v)
    for m in re.finditer(r"(-?\d[\d.,]*)\s*%[^.%0-9]{0,30}?upside", ntext, re.I):
        v = _normalize_number(m.group(1))
        if v is not None:
            up_claims.append(v)
    for m in re.finditer(r"\(([+-]?\d[\d.,]*)\s*%\s*so\s*với\s*giá", ntext, re.I):
        v = _normalize_number(m.group(1))
        if v is not None:
            up_claims.append(v)
    up_pct = upside * 100
    for v in up_claims:
        if abs(v - up_pct) > 5.0:
            issues.append(f"upside claim {v}% ≠ recompute {up_pct:.1f}% (median targets vs price) — lệch >5pp")
    exec_text = (extract_section_text(html, "sec-exec") or "") + " " + (extract_section_text(html, "sec-thesis") or "")
    pos_words = ["tích cực", "khả quan", "lạc quan", "hấp dẫn", "cơ hội", "tăng trưởng", "phục hồi",
                 "mạnh mẽ", "ưu việt", "undervalued", "định giá rẻ", "triển vọng", "đáng chú ý"]
    neg_words = ["tiêu cực", "kém khả quan", "rủi ro", "suy giảm", "overvalued", "đắt", "cảnh báo",
                 "bất lợi", "yếu kém", "thiếu hấp dẫn", "thận trọng", "giảm giá"]
    # Nhãn "Tech Score ... tín hiệu tích cực/tiêu cực" mô tả tín hiệu
    # kỹ thuật, không phải tone của investment thesis. Loại riêng các
    # câu này trước khi đếm tone; các nhận định khác vẫn bị kiểm.
    tone_text = re.sub(r"[^.!?]*Tech\s*Score[^.!?]*[.!?]?", " ", exec_text, flags=re.I)
    low = tone_text.lower()
    pos_n = sum(low.count(w) for w in pos_words)
    neg_n = sum(low.count(w) for w in neg_words)
    if upside > 0.05 and neg_n > pos_n:
        issues.append(f"upside +{upside*100:.0f}% (từ targets) nhưng exec/thesis nghiêng tiêu cực ({neg_n} âm vs {pos_n} dương)")
    if upside < -0.05 and pos_n > neg_n:
        issues.append(f"upside {upside*100:.0f}% (âm) nhưng exec/thesis nghiêng tích cực ({pos_n} dương vs {neg_n} âm)")
    passed = len(issues) == 0
    return passed, {"issues": issues, "upside_pct": round(upside * 100, 1),
                    "upside_claims": [round(v, 1) for v in up_claims[:5]],
                    "pos_words": pos_n, "neg_words": neg_n}


def verify_api_fallback(req, html):
    """REQ-066: phase 0 phải log api_source + attempts; community tier phải được
    flag trong report (Lesson Learned #1 — pipeline chết vì 1 nguồn duy nhất)."""
    ts = _load_json_rel(".task-state/task-state.json")
    if not ts:
        return False, {"error": "task-state.json không có — không log được api_source"}
    r = (ts.get("phases", {}).get("phase0_sponsor", {}) or {}).get("result") or {}
    api_source = r.get("api_source")
    if not api_source:
        return False, {"error": "phase0 chưa log api_source — không biết data từ nguồn nào (phải log chuỗi fallback)"}
    issues = []
    if "community" in str(api_source).lower():
        text = _narrative_text(html)
        if not re.search(r"community|8\s*kỳ|dữ liệu giới hạn|data giới hạn|cảnh báo|bản free", text, re.I):
            issues.append("dùng community tier nhưng report không flag 'community/dữ liệu giới hạn'")
    passed = len(issues) == 0
    return passed, {"issues": issues, "api_source": api_source,
                    "tier": r.get("tier"), "sponsor_ok": r.get("sponsor_ok")}


def verify_fiscal_year(req, html):
    """REQ-067: fiscal_year_type phải log (Lesson Learned #5 — ngân hàng có thể
    dùng năm tài chính khác dương lịch); custom → narrative phải ghi rõ."""
    ts = _load_json_rel(".task-state/task-state.json")
    fyt = None
    if ts:
        fyt = ts.get("fiscal_year_type")
        if not fyt:
            p1 = (ts.get("phases", {}).get("phase1_data", {}) or {}).get("result") or {}
            fyt = p1.get("fiscal_year_type")
    if not fyt:
        return False, {"error": "task-state thiếu 'fiscal_year_type' (calendar|custom) — phase 1 phải log để khỏi giả định dương lịch"}
    if str(fyt).lower() not in ("calendar", "custom", "cal", "cus"):
        return False, {"error": f"fiscal_year_type không hợp lệ: '{fyt}' (kỳ vọng calendar|custom)"}
    issues = []
    if str(fyt).lower() in ("custom", "cus"):
        text = _narrative_text(html)
        if not re.search(r"năm tài chính|fiscal year|fiscal|niên độ", text, re.I):
            issues.append("fiscal_year_type=custom nhưng narrative không ghi rõ 'năm tài chính/niên độ'")
    passed = len(issues) == 0
    return passed, {"issues": issues, "fiscal_year_type": fyt}
def verify_runtime_render(req, html):
    """REQ-069: Runtime render readiness — chart JS phải khớp cấu trúc thật.

    Chống "chart chết im lặng" (V4 Flash, phiên chạy CTD 2026-08-01):
    lỗi runtime (DATA.<key> thiếu, dataset data sai shape, $ chưa khai báo)
    làm chart không render nhưng verifier cú pháp vẫn PASS — sản phẩm của cả
    V4 Flash (4/12 chart chết) lẫn fixture cũ (0/10, "$ is not defined") đều
    lọt qua 68 REQ. Check STATIC (không cần browser): canvas id, DATA keys,
    kiểu dataset data, biến trần.
    """
    if not html:
        return False, {"error": "no html"}
    issues = []
    checked = 0

    # 1. Canvas ids: duy nhất
    canvas_ids = re.findall(r'<canvas[^>]*\bid="([^"]+)"', html)
    dupes = sorted({c for c in canvas_ids if canvas_ids.count(c) > 1})
    if dupes:
        issues.append(f"canvas id trùng lặp: {dupes}")
    checked += 1

    # 2. new Chart($('id')) / $("id") refs -> canvas phải tồn tại
    # (a) $('chartX') refs: loại guard `if ($('x'))` và OR-chain `$('a') || $('b')`
    #     (chartBSDt2 || chartReturns, if ($('chartThesisRPO'))) — optional charts.
    chart_refs = re.findall(r'\$\s*\(\s*["\'](chart[\w]+)["\']\s*\)', html)
    or_chains = re.findall(r'\$\(\s*["\'](chart[\w]+)["\']\s*\)\s*\|\|\s*\$\(\s*["\'](chart[\w]+)["\']\s*\)', html)
    or_ok = set()
    for a, b2 in or_chains:
        if a in canvas_ids or b2 in canvas_ids:
            or_ok.add(a); or_ok.add(b2)
    guarded = set(re.findall(r'if\s*\(\s*\$\(\s*["\'](chart[\w]+)["\']\s*\)', html))
    # P0-F (Sol checkpoint 3): chart có GUARD DỮ LIỆU — `if (DATA.segMix && ...length) {`
    # chỉ vẽ khi có data thật; segMix rỗng → canvas không bắt buộc.
    data_guarded = set(re.findall(r'if\s*\(\s*DATA\.([\w]+)[^)]*\)\s*\{\s*new\s+Chart\s*\(\s*\$\s*\(\s*["\'](chart[\w]+)["\']\s*\)', html))
    for _dk, _ck in data_guarded:
        if re.search(r'["\']?' + _dk + r'["\']?\s*:\s*\[\s*\]', html):
            guarded.add(_ck)  # data rỗng → guard false → không cần canvas
    missing_canvas = sorted({r for r in chart_refs if r not in canvas_ids
                             and r not in or_ok and r not in guarded})
    if missing_canvas:
        issues.append(f"new Chart tham chiếu canvas không tồn tại: {missing_canvas}")

    # 3. const DATA = {...}: parse object thật, so DATA.<key> refs
    m = re.search(r"const\s+DATA\s*=\s*\{", html)
    if not m:
        issues.append("không tìm thấy const DATA = { — chart data không có nguồn")
    else:
        start = m.end() - 1
        depth = 0
        i = start
        while i < len(html):
            ch = html[i]
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    break
            i += 1
        try:
            raw_obj = html[start:i + 1]
            # Chấp nhận JS object với keys UNQUOTED (revenue: [...]) — chuẩn
            # builder tạo ra; JSON yêu cầu quoted keys (bug cohort V4: HPG)
            raw_obj = re.sub(r'([{,]\s*)([A-Za-z_$][A-Za-z0-9_$]*)(\s*:)', r'\1"\2"\3', raw_obj)
            data_obj = json.loads(raw_obj)
            refs = set(re.findall(r"DATA\.([A-Za-z_][A-Za-z0-9_]*)", html))
            missing_keys = sorted(k for k in refs if k not in data_obj)
            if missing_keys:
                issues.append(f"JS tham chiếu DATA keys không có trong object: {missing_keys}")
            # dataset data: DATA.<key> phải là ARRAY; DATA.<key>.<sub> thì check leaf
            for mm in re.finditer(r"data:\s*DATA\.([A-Za-z_][A-Za-z0-9_]*)(?:\.([A-Za-z_][A-Za-z0-9_]*))?", html):
                k = mm.group(1)
                sub = mm.group(2)
                v = data_obj.get(k)
                if v is None:
                    continue
                if sub:
                    sv = v.get(sub) if isinstance(v, dict) else None
                    if sv is not None and not isinstance(sv, list):
                        issues.append(f"dataset data: DATA.{k}.{sub} phải là array (hiện {type(sv).__name__})")
                elif not isinstance(v, list):
                    issues.append(f"dataset data: DATA.{k} phải là array (hiện {type(v).__name__})")
            checked += 1
        except Exception as e:
            issues.append(f"không parse được const DATA: {str(e)[:80]}")

    # 4. Biến trần (labels:/data:) phải khai báo hoặc global hợp lệ
    declared = set(re.findall(r"\b(?:const|let|var)\s+([A-Za-z_$][\w$]*)", html))
    declared |= set(re.findall(r"\bfunction\s+([A-Za-z_$][\w$]*)", html))
    globals_ok = {"DATA", "Chart", "window", "document", "Math", "JSON", "Object", "Array",
                  "String", "Number", "Date", "RegExp", "parseInt", "parseFloat", "isNaN",
                  "console", "setTimeout", "clearTimeout", "requestAnimationFrame", "fetch"}
    if "jquery" in html.lower():
        globals_ok.add("$")
    # (c) bare-var: chỉ quét trong script block chart; skip literals
    script_block = ""
    m_script = re.search(r"<script>(.*?)</script>", html, re.DOTALL)
    if m_script:
        script_block = m_script.group(1)
    literals = {"true", "false", "null", "undefined"}
    for mm in re.finditer(r"(?:labels|data):\s*([A-Za-z_$][\w$]*)", script_block):
        name = mm.group(1)
        if name in declared or name in globals_ok or name in literals:
            continue
        issues.append(f"chart dùng biến '{name}' (labels:/data:) nhưng không khai báo const/let/var/function")

    # 5. Dùng $() mà không khai báo $ (và không có jQuery) -> ReferenceError khi load
    if re.search(r"\$\s*\(", html) and "$" not in declared and "$" not in globals_ok:
        issues.append("dùng $() nhưng không khai báo $ và không có jQuery — ReferenceError khi load")

    passed = len(issues) == 0
    return passed, {"canvas_total": len(canvas_ids), "chart_refs": sorted(set(chart_refs)),
                    "issues": issues[:8],
                    "note": "static runtime-readiness: canvas id / DATA keys / dataset data shape / bare vars"}


def verify_no_internal_meta(req, html):
    """REQ-070 (V4 Flash, phiên chạy CTD 2026-08-01): narrative KHÔNG chứa meta
    nội bộ — tên phase (phase 3 / phase4a), tên file dữ liệu (financials.json,
    peers.json, price_daily, cash_flow...), tên nội bộ (task-state, news_digest...).
    Người đọc cuối chỉ thấy mô tả nguồn tiếng Việt. Danh sách nguồn cuối trang
    (li id="ref-N") và thẻ sup ẩn (citation) được miễn trừ.

    Gốc rễ: phase 6 chèn dấu vết kỹ thuật để verifier đọc được nguồn, nhưng chúng
    hiện ra cho người đọc → mâu thuẫn "nội bộ vs người đọc". Cách đúng: mô tả nguồn
    tiếng Việt (theo BCTC) + {SRC('ref-N')} (render sup ẩn CSS).
    """
    if not html:
        return False, {"error": "no html"}

    # Các section narrative chính (trùng danh sách REQ-033) — ref list cuối trang không nằm trong này
    CLAIM_SECTIONS = {
        "sec-hero", "sec-exec", "sec-biz", "sec-industry", "sec-history",
        "sec-segment", "sec-thesis", "sec-valuation", "sec-bs",
        "sec-risk", "sec-scenario", "sec-insight-1", "sec-insight-2", "sec-insight-3",
    }
    section_ids = set(re.findall(r'<section[^>]*id="(sec-[a-z0-9-]+)"', html)) & CLAIM_SECTIONS

    # Pattern meta nội bộ: phase/phase-N, tên file .json/.md, từ khoá nội bộ
    internal_pat = re.compile(
        r"phase\s*\d|phase\d|"
        r"[A-Za-z_][\w]*\.(?:json|md)|"
        r"task-state|investment_amount|technical_active|technical_profile|"
        r"news_digest|wacc_estimates|sector_insights|company_profile|"
        r"price_weekly|price_daily|cash_flow|balance_sheet|financials|peers\.json|"
        r"verified-dashboard-data|init_task_state|run_phase",
        re.I)

    issues = []
    for sid in sorted(section_ids):
        sec_text = extract_section_text(html, sid)
        if not sec_text:
            continue
        # Bỏ thẻ sup.cite (citation ẩn) khỏi text section để không tính chúng
        sec_wo_sup = re.sub(r"<sup[^>]*class=[\"']cite[\"'][^>]*>.*?</sup>", " ", sec_text, flags=re.DOTALL)
        for m in internal_pat.finditer(sec_wo_sup):
            ctx = sec_wo_sup[max(0, m.start()-40):m.end()+20].strip()
            issues.append(f"{sid}: chứa meta nội bộ '{m.group(0)}' — ctx: ...{ctx}...")
            if len(issues) >= 10:
                break
        if len(issues) >= 10:
            break

    passed = len(issues) == 0
    return passed, {"sections_scanned": len(section_ids), "issues": issues[:10],
                    "note": "narrative không chứa tên phase/file/từ nội bộ (ref list miễn trừ)"}




def verify_no_zero_datasets(req, html):
    """REQ-071 (V4 Flash, phiên CTD 2026-08-01): không dataset biểu đồ toàn 0.
    Chống "chart vẽ rỗng": data thiếu (balance_sheet chỉ 3 dòng tổng → inventory
    toàn 0) làm cột chart biến mất nhưng verifier cú pháp vẫn PASS. Check STATIC:
    mọi array numeric trong const DATA phải có ít nhất 1 phần tử khác 0.
    Null/nullable (chuỗi ngày, MA có null đầu) được bỏ qua; chỉ bắt array mà
    toàn bộ phần tử số = 0.
    """
    if not html:
        return False, {"error": "no html"}
    m = re.search(r"const DATA\s*=\s*(\{.*?\})\s*;", html, re.DOTALL)
    if not m:
        return False, {"error": "const DATA không tìm thấy"}
    try:
        data = json.loads(m.group(1))
    except Exception as e:
        return False, {"error": f"DATA parse lỗi: {e}"}

    issues = []
    checked = 0
    for key, val in data.items():
        if not isinstance(val, list) or not val:
            continue
        # chỉ xét array có phần tử số (bỏ qua dates/labels chuỗi)
        nums = [v for v in val if isinstance(v, (int, float)) and v is not None]
        if not nums:
            continue
        checked += 1
        if all(v == 0 for v in nums):
            issues.append(f"dataset '{key}' toàn 0 — chart vẽ rỗng (data thiếu hoặc key sai)")
            if len(issues) >= 10:
                break

    passed = len(issues) == 0
    return passed, {"datasets_checked": checked, "issues": issues[:10],
                    "note": "mọi dataset numeric phải có ≥1 giá trị khác 0 (chống chart vẽ rỗng)"}




def verify_realistic_sr(req, html):
    """REQ-072 (V4 Flash, phiên CTD 2026-08-01): mức Hỗ trợ/Kháng cự thực tế.
    Phiên CTD: "52W high 92,750" xếp làm kháng cự khi giá 61,000 (cách +52%) —
    phi thực tế cho giao dịch ngắn hạn. Check data/technical_active.json:
    kháng cự ∈ [giá, giá×1.30], hỗ trợ ∈ [giá×0.70, giá]; mức ngoài khoảng phải
    vào far_levels. Thiếu file/field → advisory (không FAIL).
    """
    if not html:
        return False, {"error": "no html"}
    ta = _load_json_rel("data/technical_active.json")
    if not ta or not isinstance(ta, dict):
        return True, {"note": "technical_active.json không có — bỏ qua (advisory)"}
    sr = ta.get("support_resistance")
    if not sr or not isinstance(sr, list):
        return True, {"note": "support_resistance không có trong technical_active.json — bỏ qua (advisory)"}
    last = ta.get("last_close")
    if not last:
        return True, {"note": "thiếu last_close — bỏ qua (advisory)"}

    issues = []
    for m in sr:
        lvl = m.get("level")
        typ = m.get("type")
        if lvl is None or typ not in ("support", "resistance"):
            continue
        if typ == "resistance":
            if lvl <= last:
                issues.append(f"kháng cự {lvl} ≤ giá hiện tại {last} — phân loại sai hướng")
            elif lvl > last * 1.30:
                issues.append(f"kháng cự {lvl} cách giá {last} >30% ({lvl/last*100-100:.0f}%) — phi thực tế, nên vào far_levels")
        else:  # support
            if lvl >= last:
                issues.append(f"hỗ trợ {lvl} ≥ giá hiện tại {last} — phân loại sai hướng")
            elif lvl < last * 0.70:
                issues.append(f"hỗ trợ {lvl} cách giá {last} >30% — phi thực tế, nên vào far_levels")
        if len(issues) >= 10:
            break

    passed = len(issues) == 0
    return passed, {"last_close": last, "sr_levels": len(sr), "issues": issues[:10],
                    "note": "S/R phải trong ±30% giá và đúng hướng; mức xa → far_levels"}




def verify_paragraph_structure(req, html):
    """REQ-073 (V4 Flash, phiên review UI CTD 2026-08-01): narrative không có
    "bức tường chữ" — đoạn <p> trực tiếp trong section quá dài (>300 ký tự text)
    mà không nằm trong ul/ol phải tách. Chỉ áp cho các section narrative chính.
    Ghi chú/ngoại lệ: ghi chú nhỏ (faint/meta-note) và thẻ p trong callout không tính.
    """
    if not html:
        return False, {"error": "no html"}
    CLAIM_SECTIONS = {
        "sec-hero", "sec-exec", "sec-biz", "sec-industry", "sec-history",
        "sec-segment", "sec-thesis", "sec-valuation", "sec-bs",
        "sec-risk", "sec-scenario", "sec-insight-1", "sec-insight-2", "sec-insight-3",
    }
    section_ids = set(re.findall(r'<section[^>]*id="(sec-[a-z0-9-]+)"', html)) & CLAIM_SECTIONS
    MAX_LEN = 300

    issues = []
    total_p = 0
    for sid in sorted(section_ids):
        m_sec = re.search(r'<section[^>]*id="' + sid + r'".*?</section>', html, re.DOTALL)
        if not m_sec:
            continue
        sec_html = m_sec.group(0)
        # Tách từng <p>...</p> không nằm trong ul/ol/table/callout (loại bỏ các block đó trước)
        sec_no_lists = re.sub(r'<ul>.*?</ul>|<ol>.*?</ol>|<table.*?</table>|'
                              r'<div class="callout[^"]*".*?</div>', ' ', sec_html, flags=re.DOTALL)
        for m in re.finditer(r'<p(?![^>]*class=[^>]*faint)[^>]*>(.*?)</p>', sec_no_lists, re.DOTALL):
            text = re.sub(r'<[^>]+>', ' ', m.group(1))
            text = re.sub(r'\s+', ' ', text).strip()
            total_p += 1
            if len(text) > MAX_LEN:
                issues.append(f"{sid}: đoạn {len(text)} ký tự (> {MAX_LEN}) — nên tách bullet/đoạn ngắn: {text[:60]}...")
                if len(issues) >= 10:
                    break
        if len(issues) >= 10:
            break

    passed = len(issues) == 0
    return passed, {"paragraphs_scanned": total_p, "issues": issues[:10],
                    "note": "đoạn narrative >300 ký tự → tách bullet (chống bức tường chữ)"}


def verify_phase_completion(req, html):
    """REQ-068 (P3 — review V4 Flash): mọi phase 0–6 phải status=completed + có
    result keys tối thiểu. Chống agent bỏ qua phase 2 (DuPont) hoặc 4b (profile)
    mà verifier không biết (verifier không đọc phase statuses trước đây).

    Vòng 2 (nghiệm thu Flash): ngoài status, còn check result keys tối thiểu —
    chống agent đánh dấu completed mà result rỗng (skip thực).
    """
    ts = _load_json_rel(".task-state/task-state.json")
    if not ts or not isinstance(ts, dict):
        return False, {"error": "task-state.json không tìm thấy — không verify được phase completion"}
    phases = ts.get("phases", {}) or {}
    # REQ-068 chỉ verify phase 0–6 (phase 7 = deploy, chạy sau verify)
    required_phases = ["phase0_sponsor", "phase1_data", "phase2_fundamental",
                       "phase3_valuation", "phase4a_tech_active",
                       "phase4b_tech_profile", "phase5_news", "phase6_dashboard"]
    # P1-02 (Wave 1): min result keys đọc từ task-state.schema.json (1 nguồn duy nhất —
    # không hardcode rải rác; schema và verifier không thể drift nhau)
    _schema_path = os.path.join(SKILL_DIR, "task-state.schema.json")
    _schema = None
    if os.path.exists(_schema_path):
        try:
            with open(_schema_path) as _f:
                _schema = json.load(_f)
        except Exception:
            _schema = None
    min_result_keys = {}
    nullable_result_keys = {}
    if isinstance(_schema, dict):
        min_result_keys = _schema.get("x_min_result_keys", {}) or {}
        nullable_result_keys = _schema.get("x_nullable_result_keys", {}) or {}
    if not min_result_keys:
        return False, {"error": "task-state.schema.json không đọc được x_min_result_keys — schema thiếu/hỏng"}
    issues = []
    phase_status = {}
    for pid in required_phases:
        ph = phases.get(pid, {})
        status = ph.get("status")
        phase_status[pid] = status
        if status != "completed":
            issues.append(f"{pid}: status='{status}' (cần 'completed') — agent có thể đã bỏ qua phase này")
            continue
        # vòng 2: check result keys tối thiểu
        result = ph.get("result") or {}
        if not isinstance(result, dict):
            result = {}
        # Some outputs are semantically N/A (negative EPS/BVPS or invalid CAGR),
        # but their keys must still exist.  Nullable keys live in the canonical
        # schema so verifier and task-state policy cannot drift.
        nullable = set(nullable_result_keys.get(pid, []))
        missing_keys = [k for k in min_result_keys.get(pid, [])
                        if k not in result
                        or (result[k] in (None, "", [], {}) and k not in nullable)]
        if missing_keys:
            issues.append(f"{pid}: status=completed NHƯNG result thiếu keys {missing_keys} — nghi skip thực (chỉ đánh dấu)")
    passed = len(issues) == 0
    return passed, {
        "phases_checked": len(required_phases),
        "phase_status": phase_status,
        "issues": issues[:8],
        "note": "P3 + vòng-2: status=completed AND result keys tối thiểu",
    }


def verify_pe_normalized(req, html):
    """REQ-074 — P/E chuẩn hóa cho cổ phiếu chu kỳ (HPG cohort V2 8/2026).

    Kích hoạt khi: CV(EPS 5 năm) > cv_threshold (EPS biến động mạnh) VÀ
    EPS hiện tại < peak_discount × max(EPS 5 năm) (đang trong pha đi xuống/
    hồi phục chưa hết của chu kỳ — HPG: EPS 2021 đỉnh, 2023 đáy, 2025 vẫn
    dưới đỉnh). Khi kích hoạt: P/E raw bị bóp méo bởi chu kỳ → report PHẢI
    trình bày cả P/E raw lẫn P/E chuẩn hóa (giá / median EPS 5 năm); verifier
    tự tính lại, lệch > tolerance_pct → FAIL.

    Không kích hoạt khi EPS đang ở gần đỉnh (tăng trưởng dốc, VD CTD) — median
    5 năm pha loãng tốc độ tăng trưởng, P/E chuẩn hóa sẽ vô nghĩa.
    """
    import json as _json, statistics as _stats
    work_dir = os.path.dirname(REPORT) if REPORT else "."
    fin_path = os.path.join(work_dir, "data/financials.json")
    if not os.path.exists(fin_path):
        return False, {"error": "financials.json not found"}
    with open(fin_path) as f:
        fin = _json.load(f)

    eps = fin.get("eps_vnd") or {}
    vals = [(str(k), float(v)) for k, v in sorted(eps.items())
            if str(k).isdigit() and v is not None]
    if len(vals) < 4:
        return True, {"status": "SKIP",
                      "reason": f"chỉ {len(vals)} năm EPS — chưa đủ 5 năm để xác định chu kỳ"}
    _, eps_vals = zip(*vals)
    if _stats.mean(eps_vals) <= 0:
        return True, {"status": "SKIP", "reason": "EPS trung bình ≤ 0 (công ty lỗ) — P/E chuẩn hóa không áp dụng"}
    median_eps = _stats.median(eps_vals)
    cv = _stats.stdev(eps_vals) / abs(_stats.mean(eps_vals))
    peak = max(eps_vals)
    last = eps_vals[-1]
    cv_th = float(req["verification"].get("cv_threshold", 0.30))
    peak_disc = float(req["verification"].get("peak_discount", 0.80))
    tol = float(req["verification"].get("tolerance_pct", 10))

    if cv <= cv_th:
        return True, {"status": "PASS_NOT_APPLICABLE",
                      "reason": f"EPS ổn định CV={cv:.2f} ≤ {cv_th:.2f} — P/E raw đại diện",
                      "cv": round(cv, 3)}
    if last >= peak_disc * peak:
        return True, {"status": "PASS_NOT_APPLICABLE",
                      "reason": (f"EPS đang ở gần đỉnh ({last:,.0f} ≥ {peak_disc:.0%} "
                                 f"đỉnh {peak:,.0f}) — pha tăng trưởng, không phải chu kỳ đi xuống"),
                      "cv": round(cv, 3)}

    # KÍCH HOẠT: bắt buộc cả 2 số
    price = (fin.get("overview") or {}).get("current_price")
    if not price:
        return False, {"error": "thiếu overview.current_price — không tính được P/E"}
    # P/E is undefined for a non-positive denominator. This must be rendered
    # explicitly as N/A rather than recomputed as a negative multiple.
    pe_raw = price / last if last > 0 else None
    pe_norm = price / median_eps if median_eps > 0 else None

    full_text = extract_all_text(html) if html else ""
    val_text_parts = []
    for sec_id in ["sec-valuation", "sec-hero", "sec-exec"]:
        st = extract_section_text(html, sec_id) if html else ""
        if st:
            val_text_parts.append(st)
    val_text = "\n".join(val_text_parts) if val_text_parts else full_text

    norm_found = norm_ok = raw_found = raw_ok = False
    raw_na = bool(re.search(r"P\s*[/／]\s*E\s*raw\s*(?:=|:)?\s*N\s*/?\s*A", val_text, re.I))
    norm_na = bool(re.search(
        r"P\s*[/／]\s*E\s*(?:chuẩn\s*h[oóòỏõọôốồổỗộơớờởỡợa]|normalized|điều\s*chỉnh)"
        r"[^\n.;]{0,35}?(?:=|:)?\s*N\s*/?\s*A",
        val_text,
        re.I,
    ))
    # Loại cụm năm trước khi trích số: "median 5 năm", "2021-2025" chứa số
    # làm regex bắt nhầm (vd "P/E chuẩn hóa theo median 5 năm = 11.0×" → bắt 5)
    scan_text = re.sub(r"\d{4}\s*-\s*\d{4}", "YEAR-RANGE", val_text)
    scan_text = re.sub(r"\d+\s*năm", "NY", scan_text)
    for m in re.finditer(r"(?:P\s*[/／]\s*E|P\s*E)\b[^0-9]{0,40}?(\d[\d.,]*)", scan_text, re.I):
        num = _normalize_number(m.group(1))
        if num is None:
            continue
        # Phân loại raw vs normalized bằng đoạn GIỮA từ khóa P/E và số
        # (không lấy context sau — "P/E 8.8 — ... P/E chuẩn hóa = 11.0" làm 8.8
        # dính từ khóa phía sau → phân loại nhầm, cohort V2 debug)
        # Strip dấu tiếng Việt trước khi khớp từ khóa — "chuẩn hóa"/"chuẩn hoá"
        # ("ẩ" U+1EA9 nằm ngoài [âa]) lọt regex Unicode (bug cohort V3)
        mid = m.group(0)
        pre = scan_text[max(0, m.start() - 40):m.start()]
        kw_text = _strip_vi_diacritics(mid + " " + pre)
        if re.search(r"chuan hoa|normalized|median|dieu chinh|adjusted", kw_text, re.I):
            norm_found = True
            norm_ok = pe_norm is not None and abs(num - pe_norm) / max(abs(pe_norm), 0.001) * 100 <= tol
        else:
            raw_found = True
            raw_ok = pe_raw is not None and abs(num - pe_raw) / max(abs(pe_raw), 0.001) * 100 <= tol

    issues = []
    if pe_norm is None:
        if not norm_na:
            issues.append("P/E chuẩn hóa phải là N/A khi median EPS không dương")
    elif not norm_found:
        issues.append(f"Thiếu P/E chuẩn hóa — EPS chu kỳ (CV={cv:.2f}, EPS {last:,.0f} < "
                      f"{peak_disc:.0%} đỉnh {peak:,.0f}), phải trình bày giá/median EPS = {pe_norm:.2f}× "
                      "bên cạnh P/E raw")
    elif not norm_ok:
        issues.append(f"P/E chuẩn hóa trong report ≠ recompute {pe_norm:.2f}× (±{tol:.0f}%)")
    if pe_raw is None:
        if not raw_na:
            issues.append("P/E raw phải là N/A khi EPS năm cuối không dương")
    elif not raw_found:
        issues.append("Thiếu P/E raw")
    elif not raw_ok:
        issues.append(f"P/E raw trong report ≠ recompute {pe_raw:.2f}× (±{tol:.0f}%)")

    if issues:
        return False, {"status": "FAIL", "issues": issues, "cv": round(cv, 3),
                       "pe_raw": round(pe_raw, 2) if pe_raw is not None else None,
                       "pe_norm": round(pe_norm, 2) if pe_norm is not None else None}
    return True, {"status": "PASS", "cv": round(cv, 3),
                  "pe_raw": round(pe_raw, 2) if pe_raw is not None else None,
                  "pe_norm": round(pe_norm, 2) if pe_norm is not None else None}


# ═══════════════════════════════════════════════════════════════
# DISPATCH TABLE (FIX-5 — review V4 Pro: thay elif-chain 54 nhánh + skip-list
# thủ công bằng dict duy nhất). Thêm verify method mới = thêm 1 entry ở đây.
# ═══════════════════════════════════════════════════════════════

def verify_data_scalar_accuracy(req, html):
    """REQ-076 (P1-1, Sol 2026-08-11): DATA JS scalar pe/pb oracle.

    Checks 3 surfaces simultaneously:
      1. verified-dashboard-data.json (sidecar) .pe / .pb
      2. const DATA in HTML .pe / .pb
      3. Source recompute: price / eps, price / bvps

    Mutation of ANY surface must FAIL. Missing field = fail-closed.
    N/A when EPS <= 0 (P/E) or BVPS <= 0 (P/B). Does NOT skip P/B for banking.
    """
    import json as _json
    import math as _math
    work_dir = os.path.dirname(REPORT) if REPORT else "."
    fin_path = os.path.join(work_dir, "data/financials.json")
    if not os.path.exists(fin_path):
        return False, {"error": "financials.json not found"}
    with open(fin_path) as f:
        fin = _json.load(f)

    if not html:
        return False, {"error": "no html"}

    # --- Load sidecar ---
    sidecar_path = os.path.join(work_dir, "verified-dashboard-data.json")
    sidecar = None
    load_issues = []
    if os.path.exists(sidecar_path):
        try:
            with open(sidecar_path) as f:
                sidecar = _json.load(f)
            if not isinstance(sidecar, dict):
                load_issues.append("sidecar must be a JSON object")
                sidecar = None
        except Exception as exc:
            load_issues.append(f"cannot parse sidecar: {type(exc).__name__}")
    else:
        load_issues.append("verified-dashboard-data.json missing")

    # --- Parse DATA JS object from HTML ---
    m_data = re.search(r"const\s+DATA\s*=\s*\{", html)
    data_obj = None
    if m_data:
        start = m_data.end() - 1
        depth = 0
        i = start
        while i < len(html):
            if html[i] == "{": depth += 1
            elif html[i] == "}":
                depth -= 1
                if depth == 0: break
            i += 1
        try:
            raw_obj = html[start:i + 1]
            raw_obj = re.sub(r'([{,]\s*)([A-Za-z_$][A-Za-z0-9_$]*)(\s*:)', r'\1"\2"\3', raw_obj)
            data_obj = _json.loads(raw_obj)
        except Exception as exc:
            load_issues.append(f"cannot parse const DATA: {type(exc).__name__}")
    else:
        load_issues.append("const DATA missing from HTML")
    if data_obj is not None and not isinstance(data_obj, dict):
        load_issues.append("const DATA must be an object")
        data_obj = None

    # --- Source recompute ---
    price = fin.get("overview", {}).get("current_price")
    eps_dict = fin.get("eps_vnd", {})
    eq_dict = fin.get("equity_ty", {})
    shares = fin.get("overview", {}).get("issue_share")

    # Dynamic last year (not hardcoded)
    eps_years = sorted([y for y in eps_dict.keys() if str(y).isdigit()], key=int)
    last_year = eps_years[-1] if eps_years else None
    def _finite_number(value):
        return (isinstance(value, (int, float)) and not isinstance(value, bool)
                and _math.isfinite(float(value)))

    source_issues = []
    if not _finite_number(price) or price <= 0:
        source_issues.append("overview.current_price missing/invalid")

    eps_raw = eps_dict.get(last_year) if last_year else None
    eps_val = float(eps_raw) if _finite_number(eps_raw) else None
    if eps_val is None:
        source_issues.append("latest eps_vnd missing/invalid")

    eq_years = sorted([y for y in eq_dict.keys() if str(y).isdigit()], key=int)
    eq_last_year = eq_years[-1] if eq_years else last_year
    eq_raw = eq_dict.get(eq_last_year) if eq_last_year else None
    eq_val = float(eq_raw) if _finite_number(eq_raw) else None
    if eq_val is None:
        source_issues.append("latest equity_ty missing/invalid")
    if not _finite_number(shares) or shares <= 0:
        source_issues.append("overview.issue_share missing/invalid")

    bvps = (eq_val * 1e9 / float(shares)) if (eq_val is not None and
            _finite_number(shares) and shares > 0) else None

    issues = load_issues + source_issues
    checked = {}

    surfaces = [("sidecar", sidecar), ("html_data", data_obj)]

    def _check_surface_scalar(surface_name, surface_obj, key, expected, is_na, na_reason):
        if surface_obj is None:
            return
        present = key in surface_obj
        value = surface_obj.get(key)
        if is_na:
            if not present or value is None or (value == 0 and not isinstance(value, bool)):
                checked[f"{surface_name}_{key}"] = f"N/A ({na_reason})"
            else:
                issues.append(
                    f"{surface_name}.{key}={value!r} but {na_reason} — "
                    "N/A accepts only missing/null/0"
                )
            return
        if not present or value is None:
            issues.append(f"{surface_name}.{key} missing — expected {expected:.2f}")
            return
        if not _finite_number(value) or value <= 0:
            issues.append(f"{surface_name}.{key}={value!r} is not a finite positive number")
            return
        abs_diff = abs(float(value) - expected)
        diff = abs_diff / expected * 100
        # Builder publishes PE/PB at 2 decimals. Accept either the semantic 2%
        # band or half one display unit (0.005), whichever is larger. This
        # prevents false failures for genuinely tiny multiples without allowing
        # a mutation to move by a full displayed cent.
        abs_tolerance = max(abs(expected) * 0.02, 0.0050000001)
        tolerance_pct = abs_tolerance / expected * 100
        checked[f"{surface_name}_{key}"] = {
            "data": value, "expected": round(expected, 6),
            "diff_pct": round(diff, 2), "tolerance_pct": round(tolerance_pct, 2),
            "abs_diff": round(abs_diff, 6), "abs_tolerance": round(abs_tolerance, 6),
        }
        if abs_diff > abs_tolerance:
            issues.append(
                f"{surface_name}.{key}={value} != recompute={expected:.2f} "
                f"(abs diff {abs_diff:.6f} > tolerance {abs_tolerance:.6f}; "
                f"{diff:.1f}% vs dynamic {tolerance_pct:.1f}%)"
            )

    # --- P/E check ---
    pe_na = eps_val is not None and eps_val <= 0
    expected_pe = (float(price) / eps_val) if (
        _finite_number(price) and price > 0 and eps_val is not None and eps_val > 0
    ) else None
    if pe_na or expected_pe is not None:
        for surface_name, surface_obj in surfaces:
            _check_surface_scalar(surface_name, surface_obj, "pe", expected_pe,
                                  pe_na, f"EPS={eps_val} <= 0")

    # --- P/B check ---
    pb_na = bvps is not None and bvps <= 0
    expected_pb = (float(price) / bvps) if (
        _finite_number(price) and price > 0 and bvps is not None and bvps > 0
    ) else None
    if pb_na or expected_pb is not None:
        for surface_name, surface_obj in surfaces:
            _check_surface_scalar(surface_name, surface_obj, "pb", expected_pb,
                                  pb_na, f"BVPS={bvps:.2f} <= 0")

    passed = len(issues) == 0
    return passed, {"checked": checked, "issues": issues[:5],
                    "eps_year": last_year, "equity_year": eq_last_year,
                    "source": {"price": price, "eps": eps_val,
                               "bvps": round(bvps, 2) if bvps is not None else None},
                    "note": "P1-1: 3-surface pe/pb oracle (sidecar + HTML DATA + source recompute)"}


METHODS = {
    "command": verify_command,
    "artifact_check": verify_artifact_check,
    "section_map_check": verify_section_map,
    "count_check": verify_count_check,
    "content_depth_check": verify_content_depth,
    "section_content_check": verify_section_content,
    "canvas_check": verify_canvas_check,
    "div_balance_check": verify_div_balance,
    "valuation_sanity_check": verify_valuation_sanity,
    "data_accuracy_check": verify_data_accuracy,
    "capex_accuracy_check": verify_capex_accuracy,
    "valuation_recompute_check": verify_valuation_recompute,
    "chart_data_accuracy_check": verify_chart_data_accuracy,
    "external_claim_flag_check": verify_external_claim_flag,
    "chart_runtime_check": verify_chart_runtime_check,
    "source_citation_check": verify_source_citation,
    "price_source_check": verify_price_source,
    "drawdown_source_check": verify_drawdown_source,
    "peer_provenance_check": verify_peer_provenance,
    "cross_section_consistency_check": verify_cross_section_consistency,
    "temporal_alignment_check": verify_temporal_alignment,
    "segment_check": verify_segment_check,
    "cagr_recompute_check": verify_cagr_recompute,
    "tech_recompute_check": verify_tech_recompute,
    "claim_basis_check": verify_claim_basis,
    "industry_claim_check": verify_industry_claim,
    "identity_check": verify_identity,
    "task_state_oracle_check": verify_task_state_oracle,
    "sponsor_period_check": verify_sponsor_period_check,
    "sponsor_import_check": verify_sponsor_import_check,
    "news_window_check": verify_news_window,
    "investment_amount_check": verify_investment_amount,
    "source_freshness_check": verify_source_freshness,
    "news_authenticity_check": verify_news_authenticity,
    "forecast_source_check": verify_forecast_source,
    "technical_indicator_verify": verify_technical_indicator,
    "macro_data_citation_check": verify_macro_data_citation,
    "management_claim_check": verify_management_claim,
    "historical_return_verify": verify_historical_return,
    "comparison_baseline_check": verify_comparison_baseline,
    "unit_consistency_check": verify_unit_consistency,
    "liquidity_check": verify_liquidity,
    "audit_opinion_check": verify_audit_opinion,
    "causal_chain_evidence_check": verify_causal_chain,
    "vague_language_check": verify_vague_language,
    "timeframe_consistency_check": verify_timeframe_consistency,
    "dividend_claim_check": verify_dividend_claim,
    "support_resistance_method_check": verify_support_resistance_method,
    "period_integrity_check": verify_period_integrity,
    "data_provenance_check": verify_data_provenance,
    "internal_identity_check": verify_internal_identity,
    "derived_metrics_recompute_check": verify_derived_metrics_recompute,
    "valuation_methods_check": verify_valuation_methods,
    "trend_consistency_check": verify_trend_consistency,
    "verdict_consistency_check": verify_verdict_consistency,
    "api_fallback_check": verify_api_fallback,
    "fiscal_year_check": verify_fiscal_year,
    "phase_completion_check": verify_phase_completion,
    "runtime_render_check": verify_runtime_render,
    "no_internal_meta_check": verify_no_internal_meta,
    "no_zero_dataset_check": verify_no_zero_datasets,
    "realistic_sr_check": verify_realistic_sr,
    "paragraph_structure_check": verify_paragraph_structure,
    "pe_normalized_check": verify_pe_normalized,
    "data_scalar_accuracy_check": verify_data_scalar_accuracy,
}


# ═══════════════════════════════════════════════════════════════
# MAIN VERIFIER
# ═══════════════════════════════════════════════════════════════

def main():
    if not os.path.exists(REQ_FILE):
        print(f"{RED}❌ requirements.yaml not found: {REQ_FILE}{NC}")
        sys.exit(2)

    with open(REQ_FILE) as f:
        req_data = yaml.safe_load(f)

    html = read_report()
    if not html and REPORT:
        print(f"{YELLOW}⚠️ Report not found: {REPORT} — running pre-build checks only{NC}")
    elif not REPORT:
        print(f"{YELLOW}⚠️ No report path — running pre-build checks only{NC}")

    # Evidence dir
    evidence_dir = os.path.join(os.path.dirname(REPORT or "."), ".task-state", "evidence")
    os.makedirs(evidence_dir, exist_ok=True)

    results = {"total": 0, "pass": 0, "fail": 0, "skip": 0, "details": []}
    fail_details = []

    print(f"\n{'='*60}")
    print(f"  INDEPENDENT VERIFIER — {TICKER}")
    print(f"  Report: {REPORT or '(pre-build)'}")
    print(f"  Requirements: {req_data['total']}")
    print(f"{'='*60}\n")

    for req in req_data["requirements"]:
        rid = req["id"]
        method = req["verification"]["method"]
        priority = req.get("priority", "medium")

        # Skip artifact checks if no report
        # FIX-5 (review V4 Pro): trước đây skip-list dài ~45 method strings maintain
        # bằng tay. Giờ derive từ METHODS dict — thêm method mới tự động được skip khi
        # không có artifact (mọi verify_* trừ verify_command đều cần html).
        if not html and method in METHODS and method != "command":
            results["skip"] += 1
            print(f"  ⏭️  {rid} [{priority:8}] SKIP (no artifact)")
            continue

        # Run verification
        detail = {"id": rid, "text": req["text"][:60], "priority": priority, "method": method}
        passed = False
        evidence = {}

        try:
            if method == "all_requirements_pass":
                # Special: checked at end
                results["skip"] += 1
                continue
            # FIX-5 (review V4 Pro): dispatch qua METHODS dict thay vì elif-chain
            # 54 nhánh. Thêm method mới chỉ cần 1 entry trong METHODS.
            handler = METHODS.get(method)
            if handler is not None:
                passed, evidence = handler(req, html)
            else:
                evidence = {"error": f"unknown method: {method}"}
        except Exception as e:
            evidence = {"error": str(e)}

        # Write evidence file
        evidence_file = os.path.join(evidence_dir, f"{rid}.json")
        evidence_data = {
            "requirement_id": rid,
            "text": req["text"],
            "priority": priority,
            "method": method,
            "status": "pass" if passed else "fail",
            "evidence": evidence,
            "verified_at": datetime.datetime.now().isoformat(),
            "artifact": REPORT,
        }
        with open(evidence_file, "w") as f:
            json.dump(evidence_data, f, indent=2, ensure_ascii=False)

        results["total"] += 1
        if passed:
            results["pass"] += 1
            status_color = GREEN + "✅ PASS" + NC
        elif priority == "advisory":
            # Advisory (batch-3, đề xuất V4 Flash): priority=advisory từ YAML là 1 nguồn
            # sự thật — check fail KHÔNG block deploy (WARN-only), không đếm vào fail
            results["skip"] += 1
            # Cosmetic (batch-5): một số advisory method dùng key 'warnings'/'note' thay
            # vì 'issues' → hiển thị số warning thật thay vì luôn "0 issue"
            warn_count = len(evidence.get("issues") or evidence.get("warnings") or [])
            status_color = YELLOW + f"⚠️ ADVISORY ({warn_count} issue)" + NC
        else:
            results["fail"] += 1
            status_color = RED + "❌ FAIL" + NC
            fail_details.append((rid, req["text"][:80], evidence))

        print(f"  {status_color} {rid} [{priority:8}] {req['text'][:55]}")

    # REQ-021: all requirements pass
    all_pass = results["fail"] == 0
    results["total"] += 1
    # PATCH P0-4: write REQ-021 evidence with provenance binding (was MISSING → mutation
    # harness couldn't confirm detection; also a state-binding risk if deploy could use stale
    # or cross-run evidence). Bind to current run, artifact hash, post-validation timestamp.
    req021_evidence = {
        "requirement_id": "REQ-021",
        "text": "KHÔNG deploy nếu bất kỳ REQ nào FAIL. Hook PreToolUse chặn vercel deploy.",
        "priority": "critical",
        "method": "all_requirements_pass",
        "status": "pass" if all_pass else "fail",
        "evidence": {
            "source_run_id": os.environ.get("EVAL_RUN_ID", f"verifier-{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}"),
            "source_artifact": REPORT,
            "source_artifact_sha256": hashlib.sha256(open(REPORT, "rb").read()).hexdigest()[:16] if REPORT and os.path.exists(REPORT) else None,
            "evidence_generated_after_validation": True,
            "unresolved_required_failures": results["fail"],
            "all_requirements_pass": all_pass,
            "requirement_state_at_eval": {rid: st for rid, st in [(d.get("requirement_id") or d.get("id"), d.get("status")) for d in [json.load(open(os.path.join(evidence_dir, f))) for f in os.listdir(evidence_dir) if f.startswith("REQ-") and f.endswith(".json")]] if st},
        },
    }
    with open(os.path.join(evidence_dir, "REQ-021.json"), "w") as f:
        json.dump(req021_evidence, f, indent=2, ensure_ascii=False)
    if all_pass:
        results["pass"] += 1
        print(f"\n  {GREEN}✅ PASS{NC} REQ-021 [critical] All requirements pass — deploy allowed")
    else:
        results["fail"] += 1
        print(f"\n  {RED}❌ FAIL{NC} REQ-021 [critical] {results['fail']} requirement(s) failed — BLOCKED deploy")

    # Summary
    recall = results["pass"] / results["total"] * 100 if results["total"] else 0
    print(f"\n{'='*60}")
    print(f"  VERDICT: {'PASS' if all_pass else 'FAIL'}")
    print(f"  Requirements: {results['pass']}/{results['total']} pass ({recall:.0f}% recall)")
    print(f"  Evidence: {evidence_dir}/")
    if fail_details:
        print(f"\n  {RED}FAILED REQUIREMENTS:{NC}")
        for rid, text, ev in fail_details:
            print(f"    {rid}: {text}")
            if ev:
                key_info = {k: v for k, v in ev.items() if k != "error" and v}
                if key_info:
                    print(f"      → {json.dumps(key_info, ensure_ascii=False)[:120]}")
    print(f"{'='*60}\n")

    # Write summary evidence
    summary_file = os.path.join(evidence_dir, "_summary.json")
    with open(summary_file, "w") as f:
        json.dump({
            "verified_at": datetime.datetime.now().isoformat(),
            "ticker": TICKER,
            "artifact": REPORT,
            "results": results,
            "requirement_recall_pct": round(recall, 1),
            "verdict": "PASS" if all_pass else "FAIL",
        }, f, indent=2, ensure_ascii=False)

    sys.exit(0 if all_pass else 1)


if __name__ == "__main__":
    main()
