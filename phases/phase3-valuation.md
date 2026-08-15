# Phase 3: Valuation

Bạn là subagent Phase 3. Context tách biệt.

## Input
- `task-state.json` → `phases.phase1_data.result` (financials) + `phases.phase2_fundamental.result` (EPS, BVPS, ROE)
- Sub-skill: `vn-valuation-engine/SKILL.md` + `references/valuation_formulas.md` + `wacc_estimates.md`

## Nhiệm vụ
1. Chọn PP định giá theo ngành (đọc `vn-financial-data-collector/references/sector_insights.md`)
2. Tính 9 PP:
   - PE/PB median 5 năm
   - EV/EBITDA
   - P/CF, P/S
   - DCF (3 kịch bản) — **SANITY CHECK: nếu FCF0 < 0 → flag + dùng EV/EBITDA-implied thay thế**
   - **DCF ASSUMPTIONS TABLE (REQ-045 forecast source + REQ-048 management claim)**: bắt buộc bảng assumptions với source cho mỗi assumption:
     - Risk-free rate (Rf): nguồn (TPCP 10Y, NHNN...)
     - Equity Risk Premium (ERP): nguồn (Damodaran, ước tính...)
     - Beta: tính từ 2 năm weekly returns vs VN-Index (G8: trước ghi REQ-050 — đó là comparison baseline, không phải beta; beta cần source tính toán)
     - Terminal growth rate: assumption + rationale
   - **REQ-063 valuation methods completeness**: mỗi method (DCF, PE, PB, EV/EBITDA, Graham) phải có giá trị hoặc N/A có lý do — không để trống
   - **REQ-060 internal identity**: PE×EPS≈giá, PB×BVPS≈giá (cross-footing)
   - **REQ-061 derived metrics**: ROE/ROA/margin recompute từ financials
   - **REQ-065 verdict consistency**: tone kết luận cùng dấu với upside từ targets
   - KHÔNG tự ý chọn assumption không có basis
   - DDM (nếu trả cổ tức)
   - Graham Number
   - Reverse DCF
3. Target price analyst từ `Company.overview()` — tham khảo
4. Hội tụ → median + dải P25-P75 → khuyến nghị
5. **Ma trận nhạy cảm**: 1 PP chủ đạo theo ngành × 2 biến quan trọng → bảng giá 3×3,
   xác định biến nhạy nhất (để tập trung kiểm chứng)
6. **Kịch bản xác suất**: bi quan/cơ sở/tích cực, mỗi kịch bản có FV + xác suất + điều kiện
   kích hoạt (tổng = 100%) → expected value; thiếu cơ sở → cơ sở 100% + ghi rõ
7. **Giải thích chiết khấu/phần bù**: 1-2 câu "vì sao rẻ/đắt" so median 5 năm + peer
   (dùng chất lượng lợi nhuận từ phase 2: cash conversion, CCC, đòn bẩy)

## SANITY CHECK BẮT BUỘC (học từ LC-005)
```
nếu FCF0 < 0:
    DCF trực tiếp = equity âm vô lý → KHÔNG hiển thị giá âm
    dùng EV/EBITDA-implied equity value thay thế
    flag "FCF<0 → DCF alternative method"
nếu valuation target < 0:
    FAIL → không hiển thị, dùng alternative
```

## Output — ghi vào task-state.json
```json
{
  "phases": {
    "phase3_valuation": {
      "status": "completed",
      "result": {
        "pe": ..., "pb": ..., "ev_ebitda": ..., "ps": ..., "pcf": ...,
        "dcf_per_share": ...,
        "dcf_note": "FCF<0, dùng EV/EBITDA-implied" | null,
        "graham_number": ...,
        "converge_median": ...,
        "verdict": "UNDERVALUED|FAIR|OVERVALUED",
        "targets": {"pe_method": ..., "pb_method": ..., "analyst": ..., "dcf_alt": ...}
      }
    }
  }
}
```

## Requirements
- REQ-016: Valuation targets hợp lý (dương, không âm vô lý). DCF với FCF<0 phải flag.

## KHÔNG được
- Hiển thị DCF âm (LC-005 failure) — phải dùng alternative
- Skip sanity check output

## UNIT CONTRACT + FCFF/FCFE (P0-01/P0-02 — Wave 1, BẮT BUỘC)
- MỌI công thức tuân theo `vn-valuation-engine/references/valuation_formulas.md` UNIT CONTRACT:
  marketCap = price × shares_tỷ (tỷ VND, KHÔNG hệ số 10); fairPrice = fairMarketCap / shares_tỷ.
- DCF: FCFF = EBIT×(1−T)+D&A−CapEx−ΔNWC; FCFE = CFO−CapEx+Net Borrowing. KHÔNG gọi CFO−CapEx là FCFF.
- Bridge EV→equity: EV − NetDebt = Equity Value. g_terminal phải < wacc (hard gate).
- Mỗi output ghi rõ: loại dòng tiền, discount rate, terminal model, đơn vị.

## APPLICABILITY FILTER (W2-3/W2-4 — Wave 2, BẮT BUỘC)
- Đọc `vn-valuation-engine/references/sector_method_registry.md` — lọc phương pháp theo ngành
  TRƯỚC khi tính median: method eligible=✗ → LOẠI + ghi `excluded: [method, reason]` trong output
- Ngân hàng/TCNH: KHÔNG dùng FCFF/WACC corporate, CCC, EV/EBITDA → cost of equity/residual income/DDM/P/B
- WACC/cost of equity theo `wacc_estimates.md` ESTIMATION PROTOCOL: mỗi input có ngày + nguồn,
  beta từ phase 4a (cửa sổ/index ghi rõ, có shrinkage Blume), ghi `as_of` trong output

## FORECAST-ERROR TRACKING (W3-3 — Wave 3)
- Mỗi target sinh ra phải ghi `target_as_of` (ngày quyết định) + `target_horizon` (tháng)
- Lưu vào task-state `valuation_forecasts: [{target_id, ticker, target_price, as_of, horizon}]`
  — để phiên sau đối chiếu với giá thực hiện (realized) và theo dõi error/bias theo ngành
- KHÔNG dùng dữ liệu công bố sau as_of để "làm khớp" target (point-in-time — data_dictionary.md PIT)
