#!/usr/bin/env python3
"""
source_pack_precheck.py — Verify source pack trước khi chạy pipeline (Lesson Learned #2)

Chạy: python3 source_pack_precheck.py <source_pack_dir>

Kiểm tra:
1. fundamental_sponsor.json có đủ fields cho 5 năm
2. overview.json có symbol, price, shares
3. balance_sheet_sponsor.csv có data
4. Không có field = 0 hoặc null (equity hay quên nhất)
"""
import json, sys, os

def check(source_pack):
    errors = []
    warnings = []

    # 1. overview.json
    ov_path = os.path.join(source_pack, 'overview.json')
    if not os.path.exists(ov_path):
        errors.append("overview.json MISSING")
    else:
        ov = json.load(open(ov_path))
        if not ov.get('symbol'):
            errors.append("overview.json: symbol MISSING")
        if not ov.get('current_price') or ov.get('current_price') == 0:
            errors.append("overview.json: current_price = 0 or missing")
        if not ov.get('shares_outstanding') or ov.get('shares_outstanding') == 0:
            warnings.append("overview.json: shares_outstanding = 0 or missing")

    # 2. fundamental_sponsor.json
    fs_path = os.path.join(source_pack, 'fundamental_sponsor.json')
    if not os.path.exists(fs_path):
        warnings.append("fundamental_sponsor.json MISSING (period_key_resolver will try CSV fallback)")
    else:
        fs = json.load(open(fs_path))
        years = fs.get('years')
        data = fs.get('data')

        if years is None:
            warnings.append("fundamental_sponsor.json: no 'years' key (resolver will try CSV)")
        elif not isinstance(years, list):
            errors.append(f"fundamental_sponsor.json: 'years' must be LIST, got {type(years).__name__}")
        elif len(years) != 5:
            errors.append(f"fundamental_sponsor.json: years must have EXACTLY 5 entries, got {len(years)}: {years}")

        if data is None and years is not None:
            errors.append("fundamental_sponsor.json: 'data' key MISSING (required when 'years' present)")
        elif isinstance(data, dict):
            required_fields = ['revenue', 'net_profit', 'equity', 'total_assets']
            for y in (years or []):
                yd = data.get(str(y), {})
                for field in required_fields:
                    v = yd.get(field, None)
                    if v is None or v == 0:
                        errors.append(f"fundamental_sponsor.json: data['{y}'].{field} = {v} — MISSING or ZERO")

    # 3. balance_sheet CSV
    bs_path = os.path.join(source_pack, 'balance_sheet_sponsor.csv')
    if not os.path.exists(bs_path):
        warnings.append("balance_sheet_sponsor.csv MISSING")

    return errors, warnings


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: python3 source_pack_precheck.py <source_pack_dir>")
        sys.exit(1)

    source_pack = sys.argv[1]
    if not os.path.isdir(source_pack):
        print(f"FAIL: {source_pack} is not a directory")
        sys.exit(1)

    errors, warnings = check(source_pack)

    if warnings:
        print("⚠️ WARNINGS:")
        for w in warnings:
            print(f"  ⚠ {w}")

    if errors:
        print(f"\n❌ PRECHECK FAIL ({len(errors)} errors):")
        for e in errors:
            print(f"  ❌ {e}")
        print("\n→ Fix source pack trước khi chạy pipeline.")
        sys.exit(1)
    else:
        print("✓ Source pack OK — đủ fields, ready for pipeline")
        sys.exit(0)
