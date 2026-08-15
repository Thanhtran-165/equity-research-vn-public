# Phase 2: Fundamental Analysis

Bạn là subagent Phase 2. Context tách biệt.

## Input
- `task-state.json` → `phases.phase1_data.result.files` (đường dẫn data files)
- Đọc data JSON từ Phase 1 (financials.json)
- Sub-skill: `vn-fundamental-analysis/SKILL.md` + `references/dupont_interpretation.md`

## Nhiệm vụ
1. Tính từ raw financials (KHÔNG tin ratio() stale):
   - EPS, BVPS từng năm
   - ROE, ROA, ROS từng năm
   - Biên gộp (gross margin), biên ròng (net margin)
2. **DuPont decomposition** (3 thành phần, mọi trường hợp):
   - Biên LN (NPM) = NPAT / Revenue
   - Vòng quay TS (Asset Turnover) = Revenue / Total Assets
   - Đòn bẩy (Equity Multiplier) = Total Assets / Equity
   - ROE = NPM × Asset Turnover × Equity Multiplier
3. CAGR: revenue + NPAT (full period + recovery nếu chu kỳ)
4. **Chất lượng lợi nhuận (BẮT BUỘC — mọi ngành)**: cash conversion CFO/LNST từng năm
   → nhận định lợi nhuận có thành tiền không; đọc theo đặc thù ngành (nhà thầu mở rộng
   CFO âm là đặc trưng — xem chuỗi 5 năm, không chụp 1 năm)
5. **Chu kỳ vốn lưu động CCC (CÓ ĐIỀU KIỆN)**: DSO/DIO/DPO + CCC khi đủ data chi tiết
   (receivables/inventory/payables/COGS). Ngành không có tồn kho (ngân hàng/TCNH) hoặc
   thiếu data → ghi `ccc: null`, KHÔNG bịa
6. **DuPont 5 bước + SGR (CÓ ĐIỀU KIỆN)**: khi có EBIT/LNTT → tách gánh thuế/lãi vay/biên
   hoạt động; SGR = ROE × (1−payout) khi có data cổ tức. Thiếu → bỏ, không chặn

## Output — ghi vào task-state.json
```json
{
  "phases": {
    "phase2_fundamental": {
      "status": "completed",
      "result": {
        "eps": [...], "bvps": [...], "roe": [...], "roa": [...],
        "dupont": {"npm": ..., "asset_turnover": ..., "equity_multiplier": ..., "roe_check": ...},
        "cagr_revenue": ..., "cagr_npat": ...,
        "gross_margin": [...], "net_margin": [...],
        "cash_conversion": [CFO/LNST từng năm],
        "ccc": {"dso": ..., "dio": ..., "dpo": ..., "ccc_days": ...} | null,
        "dupont_5": {...} | null,
        "sgr": {...} | null
      }
    }
  }
}
```

## Requirements (cho phase này)
- DuPont 3 thành phần đầy đủ

## KHÔNG được
- Dùng ratio() từ vnstock (có thể stale — tự tính từ income + balance sheet)
- Skip DuPont (REQ-013 section depth sẽ check)

## Không cần biết
- Dashboard render — Phase 6
- Valuation target price — Phase 3
