# Citation Registry (Wave 2 — W2-5)

Mỗi rule quan trọng trong skill phải nối tới **loại nguồn** — phân biệt chuẩn được chấp
nhận / heuristic nội bộ / giả định VN / kết quả thực nghiệm của dự án. KHÔNG thêm sách vở
suông; mỗi mục phải có rule tương ứng dùng nó.

## 1. Chuẩn & công thức được chấp nhận (accepted standard)

| Rule trong skill | Nguồn chuẩn | Ghi chú |
|---|---|---|
| DuPont decomposition (3 & 5 bước) | Ross/Westerfield/Jordan, Corporate Finance; Damodaran, Applied Corporate Finance | công thức chuẩn |
| FCFF/FCFE bridge | Damodaran, Valuation (ch. 6-7, 15) | P0-02 — cầu nối EV→equity |
| CAPM & WACC | Damodaran; Koller et al., Valuation (McKinsey) | kèm estimation protocol W2-4 |
| DCF terminal value g < r | Koller et al.; Damodaran | hard gate đã thêm |
| Graham Number | Graham, The Intelligent Investor | PE×PB ≤ 22.5 |
| DDM Gordon | Gordon 1959; tài liệu CFA | |
| Accrual ratio | Sloan 1996, "Do Stock Prices Fully Reflect Information in Accruals..."; Richardson et al. 2005 | W2-2 |
| Cash conversion (CFO/LNST) | Dechow 1994; Sloan 1996 | W2-2 |
| CCC (DSO/DIO/DPO) | tài liệu quản trị tài chính chuẩn (Richards & Laughlin 1980) | W2-2 |
| VaR/ES | tài liệu rủi ro chuẩn (Jorion, Value at Risk) | phase 4b |
| VAS/IFRS trình bày BCTC | VAS 21, 24; IFRS 9/15 | nền tảng dữ liệu |
| Shrinkage beta (Blume) | Blume 1971 | W2-4 |

## 2. Heuristic nội bộ (internal — phải ghi "internal heuristic")

| Rule | Ghi chú |
|---|---|
| Ngưỡng "ROE >15% tốt, >20% xuất sắc" | heuristic VN chung — cần phân tầng ngành (W2) |
| ERP VN 7–8% | giả định nội bộ — phải kèm ngày + cơ sở |
| Median P25–P75 hội tụ đa phương pháp | internal aggregation — chưa hiệu chuẩn (đang thay bằng applicability filter) |
| Sector method registry | internal — dựa trên thực hành ngành |
| Terminal growth 2–3% VN | giả định nội bộ — cần đối chiếu tăng trưởng GDP dài hạn |

## 3. Giả định thị trường VN (VN-specific)

- Giá nghìn đồng → quy đổi (vnstock); phí sàn, thuế 0.1% bán
- T+ settlement, biên độ giá theo sàn
- BCTC niên độ khác năm dương lịch (CTD 1/7–30/6) — REQ-067
- Thị trường mới nổi: thanh khoản mỏng, beta không ổn định

## 4. Kết quả thực nghiệm của dự án (phải có evidence file, không chỉ tài liệu)

| Kết quả | Evidence |
|---|---|
| Negative tests 8/8 bắt hành vi bịa | scripts/tests/test_v5_negative.py |
| Security: injection bị chặn, canary sạch | scripts/tests/test_security_injection.py |
| Golden E2E 73 REQ 0 hard fail | scripts/tests/test_golden_e2e.py |
| Deploy gate matrix 3 mode × 5 case | scripts/tests/test_predeploy_gate.py |
| Valuation units golden numbers | scripts/tests/test_valuation_units.py |
| Backtest walk-forward (khi chạy) | scripts/tests/backtest_technical.py |
| Sentiment calibration (khi chạy) | scripts/tests/sentiment_calibration.py |

## 5. Quy tắc sử dụng

- Rule thuộc nhóm 2/3: khi xuất hiện trong báo cáo phải ghi "ước tính/heuristic theo dự án"
  hoặc mô tả nguồn VN cụ thể — KHÔNG trình bày như chuẩn học thuật
- Nhóm 4: chỉ trích khi có file evidence thật chạy được
