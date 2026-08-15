# Phase 1: Data Collection

Bạn là subagent Phase 1. Context tách biệt.

## Input
- `task-state.json` → `ticker` + `phases.phase0_sponsor.result` (tier, sponsor_ok)
- Sub-skill: `vn-financial-data-collector/SKILL.md` + `references/`

## Nhiệm vụ
1. **AUDIT SPLIT (Bẫy 5B) BẮT BUỘC ĐẦU TIÊN** (REQ-003 — G13: phải log vào task-state):
   - Back-calc `CP = LNST/EPS` từng năm
   - Nếu CP mismatch >5% → adjust EPS/BVPS về cùng base với giá
   - Verify: PE_pre-split = PE_post-split
   - **LOG BẮT BUỘC vào task-state** (G13 — verifier giờ đọc từ đây, không tin chữ trong report):
     ```json
     "phases": {"phase1_data": {"result": {"split_audit": {
       "cp_consistent": true, "method": "back-calc CP=LNST/EPS, so issue_share",
       "periods_checked": 5
     }}}}
     ```
   - Report mention "split-adjusted/Bẫy 5B/cross-check" là điều kiện phụ — nhưng chỉ log mới là nguồn sự thật
2. **SECTOR DETECT — BANK GATE (Lesson cohort 8/2026 — VCB)**:
   - Phát hiện sớm từ phase 1, TRƯỚC khi tính bất kỳ chỉ số nào:
     - Tín hiệu 1: income statement KHÔNG có `Net sales`/`Revenue` nhưng có **`Total Operating Income`** (NII + thu nhập khác) → bank
     - Tín hiệu 2: sector từ company_profile ∈ {Ngân hàng, Banks, Financial Services - Banks}
   - **Column names ngân hàng (sponsor) thường IN HOA** (`TOTAL ASSETS`, `"OWNER'S EQUITY"`) và kèm đơn vị (`Total Assets (VND)`) — LUÔN chuẩn hóa qua `vn-financial-data-collector/implementation/normalization/headers.py` (resolve_field: case-insensitive + bỏ token đơn vị) thay vì so chuỗi trực tiếp
   - Nếu detect bank → **LOG BẮT BUỘC** vào task-state phase1 result:
     ```json
     "sector_applicability": {
       "sector": "bank",
       "reason": "Total Operating Income thay cho Net sales (hoặc sector=Ngân hàng)",
       "skipped_metrics": ["ccc", "accrual_cfo", "fcff", "wacc_corporate"],
       "use_metrics": ["cost_of_equity_capm", "pb", "ddm"]
     }
     ```
   - Hệ quả: revenue = `Total Operating Income`; KHÔNG tính CCC (ngân hàng không có inventory), KHÔNG dùng accrual CFO-based; phase 3 dùng cost of equity + P/B + DDM (xem `sector_method_registry.md`)
3. Fetch BCTC 5 năm qua `vnstock_data` (sponsor, 40+ kỳ):
   - Income statement, Balance sheet, Cash flow
   - **CFO 3 TÊN CỘT KHÁC NHAU THEO NGÀNH (Lesson cohort V2 8/2026)** — thử lần lượt:
     `'Cash flows from operating activities'` (công ty thường) →
     `'Net cash from operating activities'` (ngân hàng VCB) →
     `'Net cash inflows/(outflows) from operating activities'` (thép HPG)
     — cột nào có data thì dùng; lưu tên cột thật vào `raw_field_name`
   - **BALANCE SHEET CHI TIẾT (Lesson #16 — phiên CTD chỉ lưu 3 dòng tổng → chart tồn kho
     toàn 0, không vẽ được nợ vay/tiền mặt)**: ngoài `Total Assets` / `Owner's Equity` /
     `Liabilities`, BẮT BUỘC lưu thêm vào `data/balance_sheet.json`:
     `Inventories, Net` (hoặc `Inventories`), `Cash and cash equivalents` (hoặc `Cash`),
     `Short-term borrowings`, `Long-term borrowings`, `Accounts receivable`
     — cùng cấu trúc `{"<tên dòng>": {"<năm>": <giá trị VND>}}`
   - Nếu API thiếu dòng nào → ghi `null` cho dòng đó (KHÔNG ghi 0 — 0 là số thật khác null)
3. Fetch giá: weekly 52 tuần + daily ~2 năm (cho Phase 4). **PRICE REAL-TIME (Lesson Learned #6)**:
   - Giá hiện tại PHẢI fetch từ API (vnstock_data or vnstock)
   - **KHÔNG ĐƯỢC** tự điền giá tay vào overview.json
   - Nếu API giá down → ghi `price: null` + FAIL rõ ràng
   - Lưu timestamp fetch: `"price_fetched_at": "2026-07-31T11:00:00"`
4. Cross-check EPS: back-calc vs reported
5. **MAX DRAWDOWN (Lesson Learned #9)**:
   - Tính max drawdown từ data giá weekly 52 tuần
   - Lưu vào verified-dashboard-data.json: `"max_drawdown_52w": -28.5` (ví dụ)
   - Phase 6 sẽ cite số này thay vì "ước tính 30-50%"
5. **PEER DATA FETCH (Lesson Learned #4) — BẮT BUỘC**:
   - Xác định 4-5 peer cùng ngành (dựa trên industry từ company_profile.json, **cùng ICB cấp 3**)
   - Fetch P/B, PE, revenue CAGR, market_cap cho mỗi peer qua `vnstock_data`
   - **Peer selection criteria**: cùng ngành ICB cấp 3, ≥4 peers, còn niêm yết (không ticker đã hủy)
   - Lưu vào `[WORK_DIR]/data/peers.json` với schema:
   ```json
   {
     "source": "vnstock_data_sponsor_gold",
     "peers": [
       {"ticker": "HBC", "pb": 0.8, "pe": 15.2, "cagr_3y": -15.0, "market_cap_b": 1200},
       {"ticker": "C4G", "pb": 1.2, "pe": 8.5, "cagr_3y": 10.0, "market_cap_b": 800}
     ],
     "notes": "Peer data fetched cùng lúc với ticker chính, từ cùng API"
   }
   ```
   - **KHÔNG ĐƯỢC** tự ghi peer data từ bộ nhớ — phải có API call
   - Nếu API không có peer data → ghi `peers.json` với `"status": "unavailable"` → Phase 6 sẽ BỎ scatter chart
6. **LIQUIDITY DATA (REQ-052)**: fetch KLGD trung bình 10 phiên, GTGD trung bình, free float % nếu có
   - Lưu vào `data/liquidity.json` hoặc `overview.json`
7. **FISCAL YEAR DETECT (REQ-067 — G8 fix: trước ghi nhầm REQ-051)**: đọc `fiscal_year_type` từ company_profile; nếu custom → log cảnh báo
8. **PRE-CHECK SOURCE PACK (Lesson Learned #2)**:
   - Nếu chạy từ source pack (không phải fetch trực tiếp): verify đủ fields
   - Required: revenue, net_profit, **equity**, total_assets, cost_of_sales cho mỗi năm
   - Nếu thiếu → BÁO LỖI, không chạy tiếp

## Data pitfall (9 bẫy) — đọc `vn-financial-data-collector/references/data_pitfalls.md`
Áp dụng TẤT CẢ 9 bẫi. Đặc biệt:
- Bẫy 5B: split-adjustment consistency (giá split-adjusted, EPS phải cùng base)
- Đơn vị: vnstock giá = nghìn đồng → ×1000 ra VND
- LNST thuộc CĐ mẹ (không phải total)

## Output — ghi vào task-state.json + data file
```json
{
  "phases": {
    "phase1_data": {
      "status": "completed",
      "result": {
        "data_source": "sponsor",
        "periods": 41,
        "years": [2021, 2022, 2023, 2024, 2025],
        "split_audit": {"adjustment_needed": false, "cp_consistent": true},
        "files": {
          "financials": "[WORK_DIR]/data/financials.json",
          "price_weekly": "[WORK_DIR]/data/price_weekly.json",
          "price_daily": "[WORK_DIR]/data/price_daily.json"
        }
      }
    }
  }
}
```

## Requirements
- REQ-003: Split audit performed
- REQ-004: Data thật từ vnstock (KHÔNG mô phỏng)

## KHÔNG được
- Mô phỏng data giá nếu fetch fail → nói thẳng "không có data"
- Bỏ qua split audit → PE/PB sẽ sai hoàn toàn
- Dùng community tier (8 kỳ) nếu sponsor OK từ Phase 0
- **TỰ BỊA peer data từ bộ nhớ** (Lesson Learned #4) — phải fetch từ API
- **Bỏ qua equity=0 hoặc null** trong source pack (Lesson Learned #2) — báo lỗi
