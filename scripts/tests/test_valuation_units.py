#!/usr/bin/env python3
"""Unit tests cho UNIT CONTRACT + FCFF/FCFE (P0-01, P0-02 — Wave 1).

Golden numbers tính tay — oracle độc lập với bất kỳ implementation nào.
Chạy: python3 scripts/tests/test_valuation_units.py
"""
import sys

def market_cap(price_vnd, shares_billion):
    """P0-01: market cap = price(VND/cp) × shares(tỷ cp) → tỷ VND. KHÔNG hệ số 10."""
    return price_vnd * shares_billion

def fair_price(fair_market_cap_billion, shares_billion):
    """P0-01: fair price = fairMarketCap(tỷ VND) / shares(tỷ cp) → VND/cp."""
    return fair_market_cap_billion / shares_billion

def dcf_price(fcff_forecast, wacc, g_terminal, net_debt, shares_billion):
    """P0-01/P0-02: DCF FCFF → EV → equity → price (tỷ VND / tỷ cp = VND/cp).
    Hard gate: g_terminal PHẢI < wacc (terminal value vô nghĩa nếu g ≥ r)."""
    if g_terminal >= wacc:
        raise ValueError(f"g_terminal ({g_terminal}) phải < wacc ({wacc})")
    pv = sum(f / (1 + wacc) ** (i + 1) for i, f in enumerate(fcff_forecast))
    tv = fcff_forecast[-1] * (1 + g_terminal) / (wacc - g_terminal)
    ev = pv + tv / (1 + wacc) ** len(fcff_forecast)
    equity = ev - net_debt
    return equity / shares_billion

def fcfe_price(fcfe_forecast, ke, g_terminal, shares_billion):
    """P0-02: FCFE chiết khấu cost of equity → equity trực tiếp (không trừ nợ)."""
    pv = sum(f / (1 + ke) ** (i + 1) for i, f in enumerate(fcfe_forecast))
    tv = fcfe_forecast[-1] * (1 + g_terminal) / (ke - g_terminal)
    return (pv + tv / (1 + ke) ** len(fcfe_forecast)) / shares_billion

def run():
    fails = []

    # P0-01: golden example (tính tay)
    mc = market_cap(20000, 1.5)
    if mc != 30000:
        fails.append(f"market cap golden: {mc} (kỳ vọng 30,000 tỷ VND — lỗi /10 cũ cho 3,000)")
    fp = fair_price(30000, 1.5)
    if fp != 20000:
        fails.append(f"fair price golden: {fp} (kỳ vọng 20,000 VND/cp — lỗi *10 cũ cho 200,000)")
    # round-trip
    rt = market_cap(fair_price(30000, 1.5), 1.5)
    if abs(rt - 30000) > 1:
        fails.append(f"round-trip lệch: {rt} (kỳ vọng ≈30,000)")

    # P0-02: FCFF bridge → equity value
    # Giả định nhất quán: net_debt=4,000 tỷ; DCF FCFF 5 năm [1000..1400]
    p_fcff = dcf_price([1000, 1100, 1200, 1300, 1400], 0.10, 0.03, 4000, 1.0)
    # FCFE tương đương: FCFE = FCFF − lãi vay×(1−T) + vay ròng (giả sử lãi 400/năm, T=0.2,
    # vay ròng 0 → FCFE ≈ FCFF − 400×0.8 = FCFF − 320)
    fcfe_series = [f - 320 for f in [1000, 1100, 1200, 1300, 1400]]
    # cost of equity gần wacc khi nợ thấp: ke = 0.115 (beta cao hơn do đòn bẩy)
    p_fcfe = fcfe_price(fcfe_series, 0.115, 0.03, 1.0)
    if not (0.8 * p_fcff <= p_fcfe <= 1.3 * p_fcff):
        fails.append(f"FCFF/FCFE không reconcile: FCFF→{p_fcff:.0f} vs FCFE→{p_fcfe:.0f} (lệch ngoài tolerance)")

    # P0-02: g >= wacc phải bị chặn (hard gate)
    try:
        dcf_price([1000] * 5, 0.10, 0.12, 0, 1.0)
        fails.append("g > wacc không bị chặn (terminal value chia âm)")
    except ValueError:
        pass

    # P0-01: DCF price đơn vị — equity 10,000 tỷ / 1 tỷ cp = 10,000 VND/cp (không /1000 → 10)
    p = dcf_price([2000, 2000, 2000, 2000, 2000], 0.10, 0.03, 0, 1.0)
    if not (15000 <= p <= 30000):
        fails.append(f"DCF price ngoài khoảng hợp lý: {p:.0f} (nghi lỗi đơn vị /1000 cũ)")

    # Pro review: identity chặt — nợ=0 + không lãi vay → FCFF (chiết khấu wacc) PHẢI ≈ FCFE (chiết khấu ke=wacc)
    identity = dcf_price([2000, 2100, 2200, 2300, 2400], 0.10, 0.03, 0, 1.0)
    identity2 = fcfe_price([2000, 2100, 2200, 2300, 2400], 0.10, 0.03, 1.0)
    if abs(identity - identity2) / identity > 0.02:
        fails.append(f"FCFF/FCFE identity (nợ=0) lệch >2%: {identity:.1f} vs {identity2:.1f}")

    if fails:
        print("❌ VALUATION UNITS FAIL:")
        for f in fails:
            print("  -", f)
        sys.exit(1)
    print("✅ VALUATION UNITS OK:")
    print("   - market cap golden 30,000 tỷ ✓ (lỗi /10 cũ cho 3,000)")
    print("   - fair price round-trip ✓")
    print("   - FCFF/FCFE reconcile trong tolerance ✓ (bridge EV→equity)")
    print("   - g < wacc gate ✓, DCF đơn vị VND/cp ✓")

if __name__ == "__main__":
    run()
