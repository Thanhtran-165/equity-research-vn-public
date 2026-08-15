---
name: vn-fundamental-analysis
description: Phân tích cơ bản doanh nghiệp niêm yết VN từ dữ liệu BCTC 5 năm — tính ROE/ROA/ROS/CAGR, DuPont decomposition (3 thành phần), phân tích xu hướng và chất lượng lợi nhuận. Use when đã thu thập data qua skill vn-financial-data-collector và cần phân tích sức khỏe tài chính, hiệu quả kinh doanh, hoặc khi user hỏi "phân tích cơ bản", "đánh giá tài chính", "chất lượng ROE", "DuPont" cho mã CP VN cụ thể.
---

# VN Fundamental Analysis

Phân tích cơ bản từ BCTC 5 năm — tập trung vào **chất lượng** lợi nhuận (không chỉ con số).

## Điều kiện tiên quyết

Cần JSON data từ skill `vn-financial-data-collector` với schema:
```json
{
  "data_years": [2021..2025],
  "shares_outstanding_b": [...],
  "income_statement": { "revenue_b_vnd": [...], "net_profit_b_vnd": [...] },
  "balance_sheet": { "equity_b_vnd": [...], "total_assets_b_vnd": [...] },
  "cash_flow": { "cfo_b_vnd": [...] }
}
```

## Workflow 3 bước

### Bước 1: Tính 5 chỉ số chính (cho mỗi năm)

| Chỉ số | Công thức | Đơn vị | Benchmark tốt (VN) |
|---|---|---|---|
| **EPS** | `LNST[tỷ] / số CP[tỷ]` | đồng/cp | tăng dần |
| **BVPS** | `VCSH[tỷ] / số CP[tỷ]` | đồng/cp | tăng dần |
| **ROE** | `LNST / VCSH × 100` | % | > 15% tốt, > 20% xuất sắc |
| **ROA** | `LNST / Tổng TS × 100` | % | > 8% tốt |
| **ROS** | `LNST / Doanh thu × 100` | % | tùy ngành (xem sector_insights) |

⚠️ **Kiểm tra đơn vị:** `tỷ / tỷ = đơn vị cơ bản`, KHÔNG nhân thêm ×1000. BVPS hợp lý cho CP VN: 5,000-50,000 đồng. Nếu BVPS > 1,000,000 đ → sai đơn vị.

### Bước 2: DuPont Decomposition (chất lượng ROE)

Tách ROE thành 3 phần để hiểu **nguồn gốc** thay vì chỉ con số cuối:

```
ROE = Biên LN × Vòng quay TS × Đòn bẩy
    = (LNST/Doanh thu) × (Doanh thu/Tổng TS) × (Tổng TS/VCSH)
```

**Diễn giải nhanh:**
- **Biên LN giảm nhưng ROE ổn** → công ty hy sinh biên để tăng quy mô (đúng cho giai đoạn mở rộng)
- **ROE tăng chỉ nhờ đòn bẩy** → cảnh báo chất lượng kém, rủi ro cao
- **Biên LN giảm mạnh** (VD: 23% → 6%) → chu kỳ ngành hoặc mất lợi thế cạnh tranh
- **3 thành phần ổn định, biên LN là driver chính** → ROE chất lượng cao

Tham khảo `references/dupont_interpretation.md` cho template diễn giải từng pattern.

### Bước 3: Phân tích xu hướng & CAGR

```
CAGR = (Giá trị cuối / Giá trị đầu)^(1/số năm) - 1
```

**Bẫy CAGR với cổ phiếu chu kỳ:** Năm đáy chu kỳ làm CAGR âm hoặc phình. Ví dụ HPG LNST 2021-2025: 34,521 → 8,444 → 6,835 → 12,021 → 15,515. CAGR 2021-2025 = -18% (sai ý), nhưng CAGR phục hồi 2022-2025 = +22% (đúng ý).

**Quy tắc:**
- Cổ phiếu chu kỳ (thép, dầu khí, BĐS): tính CAGR **từ đỉnh đến đỉnh** hoặc **từ đáy đến đáy**, không đầu-cuối
- Cổ phiếu tăng trưởng (công nghệ, bán lẻ): CAGR đầu-cuối OK
- Luôn show cả 2: CAGR full 5 năm + CAGR giai đoạn phục hồi

## Output

Trả về JSON + diễn giải text:

```json
{
  "ratios_by_year": [
    {"year": 2025, "eps": 2019, "bvps": 18867, "roe": 10.7, "roa": 6.5, "ros": 9.8}
  ],
  "dupont_2025": {
    "ni_margin": 0.098, "asset_turn": 0.66, "leverage": 1.66, "roe": 0.107,
    "interpretation": "ROE thấp hơn đỉnh vì biên LN chưa phục hồi + vòng quay TS giảm (DQ2). Chất lượng tốt — không bơm nợ."
  },
  "cagr": {
    "revenue_5y": 0.012, "net_profit_5y": -0.18,
    "note": "CAGR LNST bị méo do đáy chu kỳ 2022-2023. CAGR phục hồi 2022→2025 = +22.4%"
  },
  "quality_verdict": "TÀI CHÍNH KHỎE / CẦN THEO DÕI / NGUY HIỂM"
}
```

## Phân công cho skill tiếp theo

- **Định giá** (giá hợp lý từ ratios): dùng skill `vn-valuation-engine`
- **Dashboard HTML**: dùng skill `vn-research-dashboard`

## Tham khảo

- `references/dupont_interpretation.md` — Template diễn giải 6 pattern DuPont phổ biến (chất lượng ROE tốt/xấu/đang xấu đi)
