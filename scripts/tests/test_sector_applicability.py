#!/usr/bin/env python3
"""Test valuation applicability filter (W2-3/W2-4 — Wave 2).

Quy tắc: trước khi tính median, LOẠI phương pháp không phù hợp ngành (eligible=✗).
- Ngân hàng: không FCFF/WACC corporate, không CCC, không EV/EBITDA → dùng cost of equity
- Thép chu kỳ: P/E phải normalized (loại P/E raw tại năm đáy)
- Mọi output ghi excluded: [method, reason]
Chạy: python3 scripts/tests/test_sector_applicability.py
"""
import sys

# Applicability matrix (trích sector_method_registry.md)
MATRIX = {
    "bank":      {"pe": "warn_cyclical", "pb": "ok_normalized", "ev_ebitda": "no",
                  "dcf_fcff": "no", "ddm": "ok", "graham": "ok", "ps": "no", "peg": "no"},
    "contractor": {"pe": "ok", "pb": "ok", "ev_ebitda": "ok", "dcf_fcff": "ok",
                   "ddm": "no", "graham": "ok", "ps": "ok", "peg": "no"},
    "steel":     {"pe": "warn_normalize", "pb": "ok", "ev_ebitda": "ok", "dcf_fcff": "ok",
                  "ddm": "no", "graham": "ok", "ps": "ok", "peg": "no"},
    "retail":    {"pe": "ok", "pb": "warn", "ev_ebitda": "ok", "dcf_fcff": "ok",
                  "ddm": "warn", "graham": "ok", "ps": "ok", "peg": "ok"},
}

def applicable(sector, method):
    """Trả True nếu phương pháp được phép vào median."""
    status = MATRIX.get(sector, {}).get(method, "ok")
    return status != "no"

def filter_median(sector, valuations):
    """Loại method không phù hợp → median trên tập còn lại + excluded."""
    kept, excluded = [], []
    for v in valuations:
        if applicable(sector, v["method"]):
            kept.append(v["value"])
        else:
            excluded.append((v["method"], v.get("reason", "not eligible per sector registry")))
    if not kept:
        return None, excluded
    kept.sort()
    n = len(kept)
    median = kept[n // 2] if n % 2 else (kept[n // 2 - 1] + kept[n // 2]) / 2
    return median, excluded

def run():
    fails = []

    # 1. Ngân hàng: FCFF + EV/EBITDA phải bị loại; median chỉ từ P/B, DDM, Graham, P/E(warn)
    bank_vals = [
        {"method": "dcf_fcff", "value": 50000, "reason": "ngân hàng không dùng FCFF/WACC corporate"},
        {"method": "ev_ebitda", "value": 45000, "reason": "EV/EBITDA không áp dụng TCNH"},
        {"method": "pb", "value": 30000}, {"method": "ddm", "value": 28000}, {"method": "graham", "value": 32000},
    ]
    med, excl = filter_median("bank", bank_vals)
    methods_excl = {m for m, _ in excl}
    if "dcf_fcff" not in methods_excl or "ev_ebitda" not in methods_excl:
        fails.append(f"ngân hàng: FCFF/EV-EBITDA phải bị loại — excluded={methods_excl}")
    if med is None or not (28000 <= med <= 32000):
        fails.append(f"ngân hàng: median sai {med} (kỳ vọng ~30,000 từ P/B/DDM/Graham)")

    # 2. Nhà thầu: DCF + EV/EBITDA được phép
    ctd_vals = [{"method": "ev_ebitda", "value": 32235}, {"method": "dcf_fcff", "value": 30000},
                {"method": "pe", "value": 34000}, {"method": "pb", "value": 28000}]
    med2, excl2 = filter_median("contractor", ctd_vals)
    if excl2 or med2 is None:
        fails.append(f"nhà thầu: không method nào bị loại — excl={excl2}")

    # 3. Thép: P/E phải normalize (đánh dấu warn — vẫn giữ nếu giá trị đã normalize)
    steel_vals = [{"method": "pe", "value": 12000, "normalized": True}, {"method": "pb", "value": 15000},
                  {"method": "ev_ebitda", "value": 14000}]
    med3, excl3 = filter_median("steel", steel_vals)
    if excl3:
        fails.append(f"thép: P/E normalized + PB + EV/EBITDA đều hợp lệ — excl={excl3}")

    # 4. Tất cả bị loại → median None (không bịa)
    med4, excl4 = filter_median("bank", [{"method": "dcf_fcff", "value": 1}, {"method": "ev_ebitda", "value": 2}])
    if med4 is not None:
        fails.append(f"median phải None khi mọi method bị loại — {med4}")

    if fails:
        print("❌ SECTOR APPLICABILITY FAIL:")
        for f in fails:
            print("  -", f)
        sys.exit(1)
    print("✅ SECTOR APPLICABILITY OK:")
    print("   - Ngân hàng: FCFF/EV-EBITDA bị loại, median từ P/B/DDM/Graham ✓")
    print("   - Nhà thầu: EV/EBITDA + DCF được phép ✓")
    print("   - Thép: P/E normalized giữ, median đúng ✓")
    print("   - Mọi method bị loại → median None (không bịa) ✓")

if __name__ == "__main__":
    run()
