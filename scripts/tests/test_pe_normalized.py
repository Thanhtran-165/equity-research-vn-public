#!/usr/bin/env python3
"""test_pe_normalized.py — REQ-074: P/E chuẩn hóa cho cổ phiếu chu kỳ.

Chạy verifier trên work dir giả (financials.json + report HTML), đọc evidence
REQ-074. 9 case:
  1. HPG-like (kích hoạt) + narrative đầy đủ  → PASS
  2. HPG-like (kích hoạt) + thiếu P/E chuẩn hóa → FAIL
  3. HPG-like (kích hoạt) + số sai            → FAIL
  4. CTD-like (EPS đang đỉnh, tăng trưởng)   → PASS_NOT_APPLICABLE (không ép)
  5. EPS ổn định (CV thấp)                    → PASS_NOT_APPLICABLE
  6. Biến thể dấu tiếng Việt                  → PASS
  7. EPS hiện tại âm, median dương            → raw N/A + normalized PASS
  8. Median EPS âm                            → normalized N/A PASS
  9. P/E chuẩn hóa âm                         → FAIL
"""
import json, os, shutil, subprocess, sys, tempfile

VERIFIER = os.path.join(os.path.dirname(__file__), "..", "independent_verifier.py")

def run_case(name, eps, price, html):
    work = tempfile.mkdtemp(prefix=f"pe_norm_{name}_")
    os.makedirs(os.path.join(work, "data"), exist_ok=True)
    fin = {
        "eps_vnd": {str(2021 + i): v for i, v in enumerate(eps)},
        "overview": {"current_price": price},
    }
    with open(os.path.join(work, "data", "financials.json"), "w") as f:
        json.dump(fin, f)
    report = os.path.join(work, "REPORT.html")
    with open(report, "w") as f:
        f.write(html)
    subprocess.run([sys.executable, VERIFIER, "TEST", report],
                   capture_output=True, text=True, timeout=120)
    ev = os.path.join(work, ".task-state", "evidence", "REQ-074.json")
    existed = os.path.exists(ev)
    if existed:
        d = json.load(open(ev))
        status, det = d["status"], json.dumps(d.get("details") or {}, ensure_ascii=False)[:160]
    else:
        status, det = None, "không có evidence REQ-074"
    shutil.rmtree(work, ignore_errors=True)
    return status, det

def main():
    # Case 1: HPG-like — EPS đỉnh 2021 → đáy 2023 → hồi nhưng dưới đỉnh
    eps_hpg = [5000, 2000, 800, 1500, 2500]
    # median = 2000 → pe_norm = 22000/2000 = 11.0; pe_raw = 22000/2500 = 8.8
    html_ok = ("<section id='sec-valuation'>P/E hiện tại 8.8× — tuy nhiên EPS chu kỳ, "
               "P/E chuẩn hóa theo median 5 năm = 11.0× phản ánh đúng hơn.</section>")
    st, det = run_case("hpg_ok", eps_hpg, 22000, html_ok)
    assert st == "pass", f"Case 1 FAIL: status={st} {det}"
    print("✓ Case 1: HPG-like narrative đầy đủ → PASS")

    # Case 2: thiếu P/E chuẩn hóa → FAIL
    html_missing = ("<section id='sec-valuation'>P/E hiện tại 8.8× là mức hấp dẫn.</section>")
    st, det = run_case("hpg_missing", eps_hpg, 22000, html_missing)
    assert st == "fail", f"Case 2 FAIL: status={st} {det} (phải FAIL vì thiếu P/E chuẩn hóa)"
    print("✓ Case 2: HPG-like thiếu P/E chuẩn hóa → FAIL (bắt đúng)")

    # Case 3: số sai → FAIL
    html_wrong = ("<section id='sec-valuation'>P/E 8.8×, P/E chuẩn hóa = 5.0×.</section>")
    st, det = run_case("hpg_wrong", eps_hpg, 22000, html_wrong)
    assert st == "fail", f"Case 3 FAIL: status={st} {det} (số chuẩn hóa sai phải bị bắt)"
    print("✓ Case 3: HPG-like số P/E chuẩn hóa sai → FAIL (bắt đúng)")

    # Case 4: CTD-like — EPS tăng dốc, năm cuối = đỉnh → KHÔNG ép
    eps_ctd = [323, 280, 2267, 3729, 7736]
    st, det = run_case("ctd_like", eps_ctd, 61000, "<section id='sec-valuation'>P/E 7.9×</section>")
    assert st == "pass", f"Case 4 FAIL: status={st} {det} (CTD-like phải PASS_NOT_APPLICABLE → pass)"
    print("✓ Case 4: CTD-like (EPS đang đỉnh) → không ép P/E chuẩn hóa")

    # Case 5: EPS ổn định → KHÔNG ép
    eps_stable = [1000, 1100, 1050, 1200, 1150]
    st, det = run_case("stable", eps_stable, 20000, "<section id='sec-valuation'>P/E 17.4×</section>")
    assert st == "pass", f"Case 5 FAIL: status={st} {det} (EPS ổn định phải pass)"
    print("✓ Case 5: EPS ổn định (CV thấp) → không ép P/E chuẩn hóa")

    # Case 6: biến thể dấu tiếng Việt "chuẩn hoá" (bug regex Unicode cohort V3)
    html_variant = ("<section id='sec-valuation'>P/E 8.8×, P/E chuẩn hoá theo median 5 năm = 11.0×.</section>")
    st, det = run_case("hpg_unicode", eps_hpg, 22000, html_variant)
    assert st == "pass", f"Case 6 FAIL: status={st} {det} (phải nhận 'chuẩn hoá' với dấu khác)"
    print("✓ Case 6: biến thể 'chuẩn hoá' (dấu tiếng Việt khác) → vẫn nhận diện")

    # Case 7: current EPS âm, median dương → raw N/A, normalized vẫn có nghĩa
    eps_loss_now = [5000, 2000, 800, 1500, -500]
    html_loss_now = ("<section id='sec-valuation'>P/E raw = N/A; "
                     "P/E chuẩn hóa theo median 5 năm = 14.7×.</section>")
    st, det = run_case("loss_now", eps_loss_now, 22000, html_loss_now)
    assert st == "pass", f"Case 7 FAIL: status={st} {det}"
    print("✓ Case 7: EPS hiện tại âm → raw N/A, normalized dương → PASS")

    # Case 8: median EPS âm → normalized must be explicit N/A, never negative
    eps_bad_median = [5000, -1000, -800, -600, 400]
    html_bad_median = ("<section id='sec-valuation'>P/E raw = 55.0×; "
                       "P/E chuẩn hóa = N/A — median EPS không dương.</section>")
    st, det = run_case("bad_median", eps_bad_median, 22000, html_bad_median)
    assert st == "pass", f"Case 8 FAIL: status={st} {det}"
    print("✓ Case 8: median EPS âm → normalized N/A → PASS")

    html_negative = ("<section id='sec-valuation'>P/E raw = 55.0×; "
                     "P/E chuẩn hóa = -27.5×.</section>")
    st, det = run_case("negative_multiple", eps_bad_median, 22000, html_negative)
    assert st == "fail", f"Case 9 FAIL: status={st} {det} (P/E âm phải FAIL)"
    print("✓ Case 9: P/E chuẩn hóa âm → FAIL")

    print("\n✅ 9/9 REQ-074 tests PASS")

if __name__ == "__main__":
    main()
