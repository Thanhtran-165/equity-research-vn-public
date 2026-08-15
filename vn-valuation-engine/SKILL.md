---
name: vn-valuation-engine
description: Định giá cổ phiếu VN đa phương pháp — 9 phương pháp hội tụ (PE/PB/EV-EBITDA/P-CF/DCF/Reverse DCF/DDM/Graham/DuPont). Use when cần kết luận "rẻ hay đắt", giá hợp lý, target price, hoặc khi user hỏi "định giá", "giá mục tiêu", "có nên mua", "fair value" cho mã CP VN. Quyết định multip phương pháp ưu tiên theo ngành (xem sector_insights).
---

# VN Valuation Engine

Định giá đa phương pháp — kết luận từ **sự hội tụ** của nhiều góc nhìn, không tin 1 phương pháp duy nhất.

## Điều kiện tiên quyết

Cần output từ 2 skill trước:
- `vn-financial-data-collector` → data 5 năm + giá hiện tại
- `vn-fundamental-analysis` → EPS, BVPS, ROE, ROA (năm gần nhất)

## Workflow 3 bước

### Bước 1: Chọn phương pháp ưu tiên theo NGÀNH

Tham khảo `references/sector_insights.md` (từ data-collector). Quy tắc chọn:

| Ngành | Phương pháp CHÍNH | Phương pháp phụ |
|---|---|---|
| Ngân hàng | P/B + ROE | DDM (cổ tức) |
| Thép/Chu kỳ | P/B + EV/EBITDA | DCF (FCFF) |
| Bất động sản | P/B + NAV | RNAV |
| Bán lẻ/Tiêu dùng | PE + PEG | DCF (FCFE) |
| Công nghệ | PE + PEG | DCF (FCFF) |
| Dầu khí | EV/EBITDA + P/CF | DCF (FCFF) |

**Quy tắc:** PE/PB trung bình 5 năm **chỉ dùng cho cổ phiếu phi chu kỳ**. Cổ phiếu chu kỳ phải loại bỏ năm đáy chu kỳ hoặc dùng median.

### Bước 2: Tính tất cả phương pháp phù hợp

Tham khảo `references/valuation_formulas.md` cho công thức chi tiết + code template. Tóm tắt:

**Nhóm Multiples (áp hệ số trung bình 5N × số liệu năm gần nhất):**
- `PE median 5N × EPS` = giá hợp lý
- `PB median 5N × BVPS` = giá hợp lý
- `EV/EBITDA × EBITDA` = EV → trừ nợ ròng → Vốn hóa → giá/CP
- `P/CF × CFO` = giá hợp lý (tránh bị "xào nấu" LNST)
- `P/S × Doanh thu` = giá hợp lý

**Nhóm Intrinsic Value:**
- **DCF (FCFF)**: 3 kịch bản (Bi quan/Base/Tích cực) với WACC 10-12%, terminal growth 2-4%. Cần CFO, CapEx, nợ ròng.
- **Reverse DCF**: tính g ngụ ý tại giá hiện tại → nếu g thấp bất thường → undervalued
- **DDM (Gordon)**: `D1 / (ke - g)`. CHỈ dùng cho công ty trả cổ tức tiền mặt đều (HPG/VNM giữ lợi nhuận tái đầu tư → không hợp DDM)
- **Graham Number**: `√(22.5 × EPS × BVPS)`. Sanity check cổ điển, điều kiện EPS & BVPS > 0.

### Bước 3: Hội tụ → kết luận

Tính **median** và **trung bình** tất cả phương pháp. Dải hợp lý = P25-P75.

**Khuyến nghị decision table:**
| Upside median | Định giá | Khuyến nghị |
|---|---|---|
| > +30% | Deeply undervalued | STRONG BUY |
| +10% đến +30% | Undervalued | BUY / ACCUMULATE |
| -10% đến +10% | Fairly valued | HOLD |
| -30% đến -10% | Overvalued | REDUCE |
| < -30% | Deeply overvalued | SELL |

⚠️ **Luôn nhạy cảm với giả định:** DCF rất nhạy (kịch bản tích cực có thể gấp 3x bi quan). Median ổn định hơn trung bình vì kháng outlier.

## Output

```json
{
  "price_current": 23650,
  "valuations": [
    {"method": "PB median 5N", "fair_value": 24026, "upside_pct": 1.6, "confidence": "high"},
    {"method": "PE median 5N", "fair_value": 26869, "upside_pct": 13.6, "confidence": "medium"},
    {"method": "DCF Base", "fair_value": 47800, "upside_pct": 102, "confidence": "low"},
    {"method": "Graham", "fair_value": 29274, "upside_pct": 23.7, "confidence": "medium"}
  ],
  "median_fair_value": 26800,
  "mean_fair_value": 26500,
  "fair_range_p25_p75": [24000, 29000],
  "recommendation": "ACCUMULATE",
  "target_price_range": "26,000 - 29,000",
  "key_assumptions": {
    "wacc": 0.105, "terminal_growth": 0.03,
    "valuation_methods_weighted_by_confidence": true
  }
}
```

## Phân công cho skill tiếp theo

- **Dashboard HTML**: dùng skill `vn-research-dashboard`

## Tham khảo

- `references/valuation_formulas.md` — Công thức chi tiết + code Node.js/Python cho 9 phương pháp + sensitivity analysis template
- `references/wacc_estimates.md` — WACC tham chiếu theo ngành VN (thép 10-12%, ngân hàng 9-11%, BĐS 11-13%...)
