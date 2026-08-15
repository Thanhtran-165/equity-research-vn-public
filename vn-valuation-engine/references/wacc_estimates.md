# WACC tham chiếu theo ngành — thị trường VN

WACC (Weighted Average Cost of Capital) = chi phí vốn bình quân. Cốt lõi cho DCF.

## Công thức WACC

```
WACC = (E/V) × Re + (D/V) × Rd × (1 - tax)
```

- E = Vốn hóa thị trường (market cap)
- D = Nợ vay thị trường
- V = E + D
- Re = Cost of equity (dùng CAPM)
- Rd = Cost of debt (lãi suất vay thực tế)
- Tax = 20% (VN corporate tax rate)

## Ước tính Cost of Equity (Re) bằng CAPM

```
Re = Rf + β × (Rm - Rf)
```

- **Rf (Risk-free rate)**: Lãi suất trái phiếu Chính phủ VN 10 năm ≈ **3.0-3.5%**
- **Rm - Rf (Equity risk premium)**: VN ≈ **7-8%** (cao hơn Mỹ 5% do rủi ro thị trường mới nổi)
- **β (Beta)**: theo từng cổ phiếu (xem bảng dưới)

## WACC tham chiếu theo ngành (VN, 2025-2026)

| Ngành | Beta điển hình | Cost of Equity | Cost of Debt (sau thuế) | WACC tham chiếu |
|---|---|---|---|---|
| **Ngân hàng** | 0.9-1.1 | 9.5-11% | N/A (huy động) | **9-11%** |
| **Thép/công nghiệp nặng** | 1.2-1.4 | 11.5-13.5% | 5-6% | **10-12%** |
| **Bất động sản** | 1.3-1.5 | 12-14% | 6-8% | **11-13%** |
| **Bán lẻ/tiêu dùng** | 0.7-0.9 | 8.5-10.5% | 5-6% | **8-10%** |
| **Công nghệ/viễn thông** | 0.8-1.0 | 9-11% | 4-5% | **8-10%** |
| **Dầu khí/hóa chất** | 1.1-1.3 | 10.5-12.5% | 5-7% | **9-11%** |
| **Hàng không/vận tải** | 1.4-1.6 | 12.5-14.5% | 6-8% | **10-12%** |

## Beta cụ thể cho blue-chip VN (xấp xỉ)

| Cổ phiếu | Beta 5 năm (ước) | Ghi chú |
|---|---|---|
| VCB | 0.85 | Ngân hàng phòng thủ |
| VNM | 0.65 | Hàng thiết yếu, beta thấp |
| HPG | 1.30 | Chu kỳ thép |
| FPT | 0.95 | Công nghệ, ổn định |
| MWG | 1.20 | Bán lẻ, biến động cao |
| VIC/VHM | 1.40 | BĐS, beta cao |
| GAS | 0.80 | Độc quyền, phòng thủ |

## Cách dùng trong DCF

**Quy tắc:** Chọn WACC theo ngành, sau đó tinh chỉnh theo beta của cổ phiếu cụ thể.

```javascript
const wacc_base = 0.105;  // Thép = 10-12%, lấy giữa
const wacc_adjusted = wacc_base + (stock_beta - 1.2) * 0.02;  // mỗi 0.1 beta = 0.2% WACC
```

## Lưu ý đặc thù VN

1. **Lãi suất vay VN cao** (8-12%) so với quốc tế (3-5%) → cost of debt cao → WACC VN cao hơn Mỹ 2-4%
2. **Rủi ro tiền tệ** (VND/USD volatile) → thêm 1-2% risk premium cho công ty vay USD
3. **Small cap premium** (công ty vốn hóa < $200M) → cộng thêm 1-2%
4. **State-owned discount/premium** — công ty NN (VCB, BSR, GAS) có thể chấp nhận WACC thấp hơn vì bảo hộ nhà nước

## Quick estimate formula (rule of thumb)

Nếu không có thời gian tính chi tiết, dùng:
```
WACC ≈ 10% + (beta - 1.0) × 2%
```

Ví dụ HPG (beta 1.30): WACC ≈ 10% + 0.6% = **10.6%** (làm tròn 10.5%)
