# REQ Index (SINH TỰ ĐỘNG từ requirements.yaml — KHÔNG sửa tay)

> Tổng: 74 REQ · 9 phases · sinh bởi generate_registry_docs.py

## CRITICAL (16)

| REQ | Priority | Phases | Tóm tắt |
|---|---|---|---|
| REQ-001 | critical | phase0_sponsor | Sponsor package phải hoạt động (tier golden) |
| REQ-002 | critical | phase0_sponsor | Sponsor data phải trả ≥20 kỳ trên CẢ 3 báo cáo (income_statement + bal |
| REQ-004 | critical | phase1_data | Data giá THẬT từ vnstock |
| REQ-009 | critical | phase6_dashboard | Dashboard copy từ dashboard_template |
| REQ-021 | critical | phase7_deploy | KHÔNG deploy nếu bất kỳ REQ nào FAIL |
| REQ-022 | critical | phase6_dashboard | Revenue/NPATMI/EPS trong report KHỚP data files (±5%) |
| REQ-023 | critical | phase6_dashboard | Balance sheet metrics (Total Assets, Equity) khớp balance_sheet |
| REQ-024 | critical | phase6_dashboard | Capex trong chart/report KHỚP cash_flow |
| REQ-030 | critical | phase6_dashboard | Price freshness: giá hiện tại phải fetch real-time từ API, KHÔNG tự đi |
| REQ-032 | critical | phase1_data | Peer provenance: mọi số liệu peer trong narrative (tên DN cùng ngành + |
| REQ-033 | critical | phase6_dashboard | Cross-section consistency: cùng 1 số liệu key (revenue, NPAT, EPS, PE, |
| REQ-034 | critical | phase6_dashboard | Temporal alignment: số liệu theo năm phải khớp đúng năm |
| REQ-044 | critical | phase5_news | News authenticity: mỗi article phải có URL hoặc source_name |
| REQ-045 | critical | phase6_dashboard | Forecast source: mọi forward-looking claim (dự kiến, kế hoạch, dự phón |
| REQ-059 | critical | phase1_data | Data provenance: data files (financials |
| REQ-062 | critical | phase1_data | Period integrity: mọi (period, value) pair trong verified-dashboard-da |

## HIGH (40)

| REQ | Priority | Phases | Tóm tắt |
|---|---|---|---|
| REQ-003 | high | phase1_data | Audit split (Bẫy 5B) trước khi tính EPS/PE/PB |
| REQ-005 | high | phase4a_tech_active | Technical mode ACTIVE (weekly 52 tuần, Tech Score -6→+6, Verdict, MA/R |
| REQ-006 | high | phase4b_tech_profile | Technical mode PROFILE (daily ~2 năm, 15 block, archetype, NON-ADVICE) |
| REQ-007 | high | phase4b_tech_profile | Section PROFILE phải dùng ngôn ngữ neutral_descriptive_non_advice |
| REQ-010 | high | phase6_dashboard | Tất cả tokens {{ |
| REQ-011 | high | phase6_dashboard | Canvas elements phải có height-wrapper (chặn Chart |
| REQ-012 | high | phase6_dashboard | Charts ≥10, Sections ≥20, Refs ≥10 |
| REQ-013 | high | phase6_dashboard | Mỗi section phải có content depth ≥200 chars (không rỗng/mỏng) |
| REQ-014 | high | phase6_dashboard | 3 Special Insights riêng biệt (sec-insight-1/2/3), mỗi cái ≥500 chars |
| REQ-016 | high | phase3_valuation | Valuation targets phải hợp lý (dương, không âm vô lý) |
| REQ-019 | high | phase6_dashboard | JS syntax hợp lệ (node --check pass) |
| REQ-020 | high | phase6_dashboard | Div balance (open = close) |
| REQ-025 | high | phase3_valuation | Valuation multiples (PE, PB) recomputed từ data == report values (±2%) |
| REQ-026 | high | phase6_dashboard | Chart DATA JS object chứa values KHỚP data files (revenue, npatmi arra |
| REQ-028 | high | phase6_dashboard | Chart render-readiness: mỗi canvas ID referenced trong Chart() phải có |
| REQ-029 | high | phase6_dashboard | Source citation: mọi số liệu định lượng trong narrative (revenue, prof |
| REQ-031 | high | phase6_dashboard | Drawdown verification: mọi claim về drawdown (%) hoặc rủi ro giá phải  |
| REQ-035 | high | phase6_dashboard | Segment data: mọi segment breakdown (doanh thu theo mảng, % contributi |
| REQ-036 | high | phase6_dashboard | CAGR recompute: mọi claim CAGR (%) phải recompute được từ data files ( |
| REQ-037 | high | phase4a_tech_active | Technical recompute: Tech Score + Verdict phải recompute được từ price |
| REQ-038 | high | phase6_dashboard | Claim basis: mọi claim so sánh/đánh giá (tăng trưởng nhanh nhất, dẫn đ |
| REQ-039 | high | phase6_dashboard | Industry claim: mọi claim về ngành (thị phần ngành, tốc độ tăng trưởng |
| REQ-046 | high | phase4a_tech_active | Technical indicator verify: RSI, MACD, MA50/MA200 trong dashboard phải |
| REQ-047 | high | phase6_dashboard | Macro data citation: mọi số liệu vĩ mô/ngành (GDP, CPI, lãi suất, FDI, |
| REQ-048 | high | phase6_dashboard | Management claim: mọi claim về ban lãnh đạo, cổ đông lớn, sở hữu phải  |
| REQ-049 | high | phase6_dashboard | Historical return verify: mọi claim "tăng/giảm X% trong Y năm/tháng" p |
| REQ-053 | high | phase0_sponsor | Audit opinion: nếu BCTC có ý kiến kiểm toán "ngoại trừ" hoặc "không ch |
| REQ-054 | high | phase6_dashboard | Causal chain evidence: mọi chuỗi nhân quả (A nhờ B, A do B, A vì B) ph |
| REQ-056 | high | phase6_dashboard | Timeframe consistency: mọi comparison phải có baseline rõ ràng (YoY, Q |
| REQ-060 | high | phase3_valuation, phase6_dashboard | Internal identity (cross-footing): các số trong report phải tự khớp nh |
| REQ-061 | high | phase2_fundamental, phase6_dashboard | Derived metrics recompute: mọi claim ROE/ROA/net margin/tăng trưởng Yo |
| REQ-063 | high | phase3_valuation, phase6_dashboard | Valuation methods completeness: các phương pháp định giá (EV/EBITDA, P |
| REQ-064 | high | phase2_fundamental, phase6_dashboard | Trend consistency: từ ngữ tăng/giảm gần metric (doanh thu, lợi nhuận)  |
| REQ-066 | high | phase0_sponsor | API fallback log: phase 0 phải log api_source + tier vào task-state (L |
| REQ-068 | high | phase7_deploy | Phase completion: mọi phase 0–6 phải status=completed trong task-state |
| REQ-070 | high | phase6_dashboard | Narrative KHÔNG chứa meta nội bộ: không có tên phase (phase 3, phase4a |
| REQ-071 | high | phase6_dashboard | Không dataset biểu đồ toàn 0: mọi array số trong const DATA phải có ≥1 |
| REQ-072 | high | phase6_dashboard | Mức Hỗ trợ/Kháng cự thực tế (technical_active |
| REQ-069 | high | phase3_valuation, phase6_dashboard | Runtime render readiness: mọi tham chiếu chart JS phải khớp cấu trúc t |
| REQ-074 | high | phase6_dashboard | P/E chuẩn hóa cho cổ phiếu chu kỳ: khi EPS 5 năm biến động mạnh (CV >  |

## MEDIUM (18)

| REQ | Priority | Phases | Tóm tắt |
|---|---|---|---|
| REQ-008 | medium | phase5_news | News digest 30 ngày với sentiment score + category breakdown |
| REQ-015 | medium | phase6_dashboard | Bull + Bear case cân bằng (không chỉ bullish) |
| REQ-017 | medium | phase6_dashboard | Flag honest về data limitation (ước tính, stale, community tier) |
| REQ-018 | medium | phase6_dashboard | Sources & references ≥10 numbered citations |
| REQ-027 | medium | phase6_dashboard | Số liệuexternal (WCM LN, MCH DT, store count) phải flag 'ước tính' nếu |
| REQ-040 | medium | phase6_dashboard | Identity: ticker + company name trong report phải khớp target (CTD=Cot |
| REQ-041 | medium | phase5_news | News window: news digest phải fetch trong 30 ngày gần nhất, KHÔNG dùng |
| REQ-042 | medium | phase6_dashboard | Investment amount: investment_amount từ task-state phải được dùng tron |
| REQ-043 | medium | phase6_dashboard | Source freshness: references phải có date (ngày truy cập/năm), không " |
| REQ-051 | medium | phase6_dashboard | Unit consistency: tất cả số tiền trong dashboard phải thống nhất đơn v |
| REQ-057 | medium | phase6_dashboard | Dividend claim: mọi claim về cổ tức, dividend yield, payout ratio phải |
| REQ-058 | medium | phase4a_tech_active | Support/Resistance method: mỗi mức hỗ trợ/kháng cự trong dashboard phả |
| REQ-065 | medium | phase3_valuation, phase6_dashboard | Verdict consistency: tone kết luận (sec-exec/sec-thesis) phải cùng dấu |
| REQ-067 | medium | phase1_data | Fiscal year alignment: task-state phase1 phải log fiscal_year_type (ca |
| REQ-050 | medium | phase6_dashboard | Comparison baseline: mọi so sánh (cao hơn, thấp hơn, tốt hơn, cải thiệ |
| REQ-052 | medium | phase1_data | Liquidity: dashboard phải có thông tin thanh khoản (KLGD trung bình, G |
| REQ-055 | medium | phase6_dashboard | Vague language: hạn chế ngôn ngữ mơ hồ (có thể, dự kiến, tiềm năng, ấn |
| REQ-073 | medium | phase6_dashboard | Cấu trúc đoạn văn: narrative các section chính không được có đoạn <p>  |

## LOW (0)

| REQ | Priority | Phases | Tóm tắt |
|---|---|---|---|
