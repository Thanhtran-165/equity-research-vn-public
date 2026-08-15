#!/usr/bin/env python3
"""Test REQ-024 khi CAPEX THIẾU (P0-A / §8.7 Sol): output phải null/N/A, không 0/estimate.

Chạy: python3 scripts/tests/test_capex_missing.py
"""
import json, os, sys, tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import independent_verifier as iv

def make_staging(capex_value, html_capex):
    """Tạo staging giả: cash_flow.json + report HTML với capex theo tham số."""
    work = tempfile.mkdtemp(prefix="capex_missing_")
    cf = {"Purchases of fixed assets and other long term assets": capex_value}
    with open(os.path.join(work, "cash_flow.json"), "w") as f:
        json.dump(cf, f)
    html = f"<html><body>test report <script>const DATA = {{years: [2021, 2022, 2023, 2024, 2025], capex: {html_capex}}};</script></body></html>"
    report = os.path.join(work, "TST_Complete_Report.html")
    with open(report, "w") as f:
        f.write(html)
    return work, report

def req_for():
    return {"verification": {"data_file": "cash_flow.json",
                             "capex_key": "Purchases of fixed assets and other long term assets",
                             "tolerance_pct": 10}}

def main():
    fails = []
    req = req_for()

    # Case 1: ground truth toàn None + report cũng null → phải FAIL fail-closed (không PASS giả)
    work1, report1 = make_staging({y: None for y in "2021 2022 2023 2024 2025".split()},
                                  "[null, null, null, null, null]")
    iv.REPORT = report1  # hàm đọc work_dir từ biến global REPORT
    ok1, detail1 = iv.verify_capex_accuracy(req, open(report1).read())
    print(f"[Case 1] GT null + report null → result={ok1} detail={detail1}")
    if ok1:
        fails.append("Case 1: capex null-toàn-bộ bị PASS (phải FAIL fail-closed)")

    # Case 2: ground truth thiếu hẳn key → FAIL rõ ràng
    work2 = tempfile.mkdtemp(prefix="capex_missing2_")
    with open(os.path.join(work2, "cash_flow.json"), "w") as f:
        json.dump({}, f)  # không có capex key
    html2 = "<html><body>report</body></html>"
    report2 = os.path.join(work2, "TST_Complete_Report.html")
    with open(report2, "w") as f:
        f.write(html2)
    iv.REPORT = report2
    ok2, detail2 = iv.verify_capex_accuracy(req, html2)
    print(f"[Case 2] thiếu hẳn capex key → result={ok2} detail={detail2}")
    if ok2:
        fails.append("Case 2: thiếu capex key bị PASS (phải FAIL fail-closed)")

    # Case 3 (đối chứng): GT đầy đủ + report khớp → PASS (chứng minh test có khả năng phân biệt)
    work3, report3 = make_staging({"2021": 100e9, "2022": 120e9, "2023": 110e9, "2024": 130e9, "2025": 140e9},
                                  "[100.0, 120.0, 110.0, 130.0, 140.0]")
    iv.REPORT = report3
    ok3, detail3 = iv.verify_capex_accuracy(req, open(report3).read())
    print(f"[Case 3] GT đầy đủ + report khớp (tỷ) → result={ok3} detail={detail3}")
    if not ok3:
        fails.append(f"Case 3: dữ liệu đầy đủ bị FAIL oan — test không phân biệt được: {detail3}")

    print()
    if fails:
        print("❌ FAIL:", *fails, sep="\n  - ")
        sys.exit(1)
    print("✅ PASS — capex thiếu → null/fail-closed, đầy đủ → so sánh được. Không có 0/estimate.")

if __name__ == "__main__":
    main()
