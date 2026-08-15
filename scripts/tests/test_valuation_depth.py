#!/usr/bin/env python3
"""Test tính tổng quát của Valuation Depth (sensitivity matrix + scenario EV).

Kiểm chứng: EV = Σ p×FV (tổng xác suất = 1), ma trận nhạy cảm tính đúng,
phát hiện lỗi phổ biến (xác suất không khớp 100%, EV tính sai, ma trận thiếu chiều).
Chạy: python3 scripts/tests/test_valuation_depth.py
"""
import sys

def expected_value(scenarios):
    """scenarios: list of {prob, fv}. Tổng prob phải ≈ 1.0."""
    total_p = sum(s["prob"] for s in scenarios)
    if abs(total_p - 1.0) > 0.001:
        raise ValueError(f"xác suất tổng {total_p} ≠ 1.0")
    return round(sum(s["prob"] * s["fv"] for s in scenarios))

def sensitivity_grid(base_val, delta_row, delta_col):
    """Ma trận 3×3: giá trị = base + delta_row[i] + delta_col[j]."""
    rows = ["Biến 1 thấp", "Biến 1 base", "Biến 1 cao"]
    cols = ["Biến 2 thấp", "Biến 2 base", "Biến 2 cao"]
    values = [[base_val + dr + dc for dc in delta_col] for dr in delta_row]
    return rows, cols, values

def most_sensitive(values):
    """Biến nhạy nhất: đi dọc 1 CỘT (cố định biến-cột, đổi biến-hàng) → biến thiên
    dọc cột đo ảnh hưởng của BIẾN HÀNG; đi ngang 1 HÀNG đo ảnh hưởng của BIẾN CỘT."""
    var1_row_range = max(max(values[r][c] for r in range(3)) - min(values[r][c] for r in range(3))
                         for c in range(3))
    var2_col_range = max(max(r) - min(r) for r in values)
    return ("biến-hàng" if var1_row_range >= var2_col_range else "biến-cột",
            var1_row_range, var2_col_range)

def run():
    fails = []

    # 1. EV đúng + tổng xác suất = 1
    ev = expected_value([{"prob": 0.25, "fv": 20000}, {"prob": 0.5, "fv": 26800}, {"prob": 0.25, "fv": 32000}])
    if ev != 26400:
        fails.append(f"EV sai: {ev} (kỳ vọng 26400)")
    try:
        expected_value([{"prob": 0.2, "fv": 20000}, {"prob": 0.5, "fv": 26800}, {"prob": 0.2, "fv": 32000}])
        fails.append("tổng xác suất 0.9 phải bị bắt (ValueError)")
    except ValueError:
        pass

    # 2. Sensitivity: ma trận đúng kích thước + giá trị đúng
    rows, cols, vals = sensitivity_grid(26000, [-3000, 0, 3000], [-2000, 0, 2000])
    if len(rows) != 3 or len(cols) != 3 or len(vals) != 3 or any(len(v) != 3 for v in vals):
        fails.append("ma trận nhạy cảm sai kích thước (phải 3×3)")
    if vals[2][2] != 31000 or vals[0][0] != 21000:
        fails.append(f"ma trận nhạy cảm sai giá trị: {vals}")

    # 3. Biến nhạy nhất phát hiện đúng (biến-hàng ±3000 → 6000 > biến-cột ±2000 → 4000)
    sens, r1, r2 = most_sensitive(vals)
    if sens != "biến-hàng" or r1 != 6000 or r2 != 4000:
        fails.append(f"phát hiện biến nhạy nhất sai: {sens} (biến-hàng {r1}, biến-cột {r2})")

    # 4. EV hợp lý nằm giữa các kịch bản
    if not (20000 <= ev <= 32000):
        fails.append(f"EV {ev} ngoài khoảng kịch bản [20000, 32000]")

    if fails:
        print("❌ FAIL:", *fails, sep="\n  - ")
        sys.exit(1)
    print("✅ VALUATION DEPTH OK:")
    print("   - EV = Σ p×FV = 26,400 ✓ (tổng xác suất phải = 1.0, sai bị bắt ✓)")
    print("   - Sensitivity 3×3 đúng giá trị ✓, phát hiện biến nhạy nhất ✓")
    print("   - EV nằm trong khoảng kịch bản ✓")

if __name__ == "__main__":
    run()
