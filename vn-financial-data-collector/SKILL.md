---
name: vn-financial-data-collector
description: Thu thập và xác minh số liệu báo cáo tài chính doanh nghiệp niêm yết Việt Nam (HOSE/HNX/UPCOM) từ nhiều nguồn chính thức. Use when phân tích cơ bản/định giá cổ phiếu VN, khi cần data doanh thu/LNST/VCSH/EPS/BVPS/PE/PB 5 năm, hoặc khi user yêu cầu phân tích mã cổ phiếu cụ thể (HPG, VCB, VNM, FPT, MWG...). Cốt lõi = workflow cross-check 3 nguồn (Vietstock + CafeF + trang QHCD doanh nghiệp) + các bẫy dữ liệu đặc thù thị trường VN.
---

# VN Financial Data Collector

Thu thập số liệu tài chính doanh nghiệp niêm yết Việt Nam — **đặc thù cần cross-check nhiều nguồn vì mỗi nguồn có độ trễ/sai số khác nhau**.

## Workflow 4 bước

### Bước 1: Xác định năm phân tích (RẤT QUAN TRỌNG)

**Luôn kiểm tra ngày hiện tại** trước khi thu thập. Quy tắc "5 năm gần nhất":
- Nếu tháng hiện tại **≥ 4** (sau Q1): kỳ năm gần nhất = **N-1 đã có BCTC kiểm toán** (công bố ~tháng 3-4). Ví dụ tháng 6/2026 → kỳ 5 năm = **2021-2025**.
- Nếu tháng hiện tại **< 4**: kỳ gần nhất = N-2 (BCTC N-1 chưa ra). Ví dụ tháng 2/2026 → kỳ 5 năm = **2020-2024**.

### Bước 2: Fetch data từ vnstock API (NGUỒN #1 — BẮT BUỘC)

**Luôn dùng vnstock API trước**, KHÔNG web scraping. Tham khảo `references/vnstock_api.md` cho code đầy đủ.

**⚠️ 2 cách import (vnstock 4.0 — học từ CTD test 7/2026):**

**Cách A — Sponsor Gold (ưu tiên nếu có):**
```python
# Sponsor venv Python (check ~/.vnstock/auth_state.json tier=golden)
# Path: [SPONSOR_VENV_PATH]bin/python
from vnstock_data import Finance, Company, Quote
# → fetch 40+ kỳ (10+ năm), cột tiếng Anh HOA
```

**Cách B — Community (fallback):**
```python
# Python system, không cần config
from vnstock.api.financial import Finance
from vnstock.api.company import Company
from vnstock.api.quote import Quote
# → chỉ 8 kỳ (~2 năm), cột 'item'/'item_en'/'item_id'
# Cần WebFetch CafeF/Vietstock bổ sung 12 kỳ cũ
```

**Cấu trúc data khác nhau** (quan trọng khi parse):
- Sponsor: `inc.columns` = `['report_period', 'ticker', 'Net sales', 'Attributable to parent company', 'EPS basic (VND)', 'Total Assets', "Owner's Equity", ...]`, filter `report_period == 'year'` cho annual
- Community: `inc.columns` = `['item', 'item_en', 'item_id', '2026-Q1', '2025-Q4', ...]`, mỗi row = 1 metric

→ Code fetch phải detect format + extract LNST/EPS/VCSH theo đúng key. Tham khảo `scripts/preflight.py` cho pattern handle cả 2.

 Tóm tắt:

```python
from vnstock.api.financial import Finance
from vnstock.api.company import Company
from vnstock.api.quote import Quote

f = Finance(symbol='HPG', source='VCI')
# BCTC đầy đủ 2018Q1-2026Q1:
income = f.income_statement()      # Doanh thu, LNST, EPS...
balance = f.balance_sheet()        # VCSH, Tổng TS, Nợ...
cashflow = f.cash_flow()           # CFO, CapEx...
# ⚠️ KHÔNG DÙNG f.ratio() làm nguồn chính — đã từng stale (BSR case).
# Tự tính EPS/BVPS/ROE/PE/PB từ income + balance + giá hiện tại.
# f.ratio() CHỈ dùng để cross-check (verify) — nếu chênh >5%, dùng số tự tính.

c = Company(symbol='HPG', source='VCI')
overview = c.overview()             # market_cap, issue_share, target_price
events = c.events()                 # công bố thông tin, cổ tức
```

**⚠️ QUY TẮC MỚI (v2.2.0 — học từ case BSR)**: KHÔNG dùng `f.ratio()` làm nguồn chính. Tự tính từ `income_statement` + `balance_sheet`:
- EPS = LNST_CĐ_mẹ / số CP lưu hành (lấy từ `overview['issue_share']`)
- BVPS = VCSH / số CP
- ROE = LNST / VCSH
- PE = giá hiện tại / EPS (tự tính, không tin ratio())
- PB = giá hiện tại / BVPS

`f.ratio()` **chỉ dùng để cross-check** — nếu chênh >5% với số tự tính → dùng số tự tính, flag ratio() có thể stale.

**Chỉ dùng web scraping khi vnstock thiếu:**
- BCTC kiểm toán PDF chính thức → trang QHCD DN
- Tin tức > 50 bài → CafeF, VnExpress
- Báo cáo thường niên → trang QHCD DN

### Bước 3: Cross-check & áp dụng 6 bẫy dữ liệu

**Cross-check 3 chỉ số chính** (LNST, VCSH, EPS) giữa:
1. vnstock Finance (nguồn #1)
2. CafeF BCTC page (nguồn #2)
3. BCTC kiểm toán PDF từ trang QHCD (nguồn #3 — gold standard)

Nếu chênh > 5%, dùng giá trị từ BCTC kiểm toán.

Xem chi tiết `references/data_pitfalls.md` + `references/vnstock_api.md`. Tóm tắt 6 bẫy:

1. **Số CP lưu hành thay đổi** — vnstock `Finance.ratio()` có sẵn 'Số CP lưu hành (triệu)' từng quý. **KHÔNG dùng số CP cố định.**

2. **Đơn vị tính** — vnstock giá = nghìn đồng (19.38 = 19,380 đ). VCSH (tỷ) / CP (tỷ) = đồng/cp. **Cross-check BVPS với ratios có sẵn.**

3. **LNST vs LN trước thuế** — vnstock income_statement có rõ 'Lợi nhuận của Cổ đông của Công ty mẹ' + 'Lãi cơ bản trên cổ phiếu (VND)'. Dùng dòng này cho EPS.

4. **Data cũ trong search results** — vnstock luôn cập nhật (Q+1). Web search có thể index BCTN cũ.

5. **Quy đổi split-adjusted price** — vnstock `Quote.history()` trả giá raw (chưa adjust). PE/PB dùng giá + EPS cùng năm thì không cần adjust.

6. **Vốn hóa sai** — Dùng `Company.overview()['market_cap']` (chính xác). KHÔNG tự tính bằng CP cũ.

6. **Vốn hóa (Market Cap) sai** — Dùng số CP cũ hoặc sai format (VD "₫136.5B tỷ"). **Luôn fetch `market_cap` từ vnstock `Company.overview()`** thay vì tự tính. Format chuẩn: "199,254 tỷ VNĐ" hoặc "₫199.3K tỷ" — KHÔNG "₫XB tỷ" (trùng đơn vị).

### Bước 4: Output structured

Trả về JSON theo schema (đơn vị `_b_vnd` = tỷ VNĐ, `_vnd` = đồng VNĐ):

```json
{
  "ticker": "HPG",
  "company": "CTCP Tập đoàn Hòa Phát",
  "exchange": "HOSE",
  "sector": "Thép",
  "data_years": [2021, 2022, 2023, 2024, 2025],
  "shares_outstanding_b": [5.81, 6.40, 6.40, 6.40, 7.69],
  "income_statement": {
    "revenue_b_vnd": [150865, 142771, 118953, 140191, 158332],
    "net_profit_b_vnd": [34521, 8444, 6835, 12021, 15515]
  },
  "balance_sheet": {
    "equity_b_vnd": [103000, 98000, 109000, 130000, 145000],
    "total_assets_b_vnd": [165000, 162000, 178000, 224489, 240000]
  },
  "cash_flow": { "cfo_b_vnd": [42000, 18000, 25000, 28000, 35000] },
  "market": {
    "price_year_end_vnd": [32800, 19500, 25200, 25000, 23650],
    "price_current_vnd": 23600,
    "date_current": "2026-06-21",
    "market_cap_b_vnd": 199254,
    "market_cap_usd_b": 7.8,
    "shares_current_b": 8.44
  },
  "dividends": { "stock_div_pct": [30, 25, 0, 20, 10], "cash_div_vnd": [] },
  "sources_verified": ["vnstock API", "CafeF", "BCTC HPG"]
}
```

## Phân công cho skill tiếp theo

- **Phân tích cơ bản** (ROE/ROA/ROS/CAGR/DuPont): dùng skill `vn-fundamental-analysis`
- **Định giá** (DCF/PE/PB/EV-EBITDA/Graham/DDM): dùng skill `vn-valuation-engine`
- **Dashboard HTML**: dùng skill `vn-research-dashboard`

## Tham khảo

- **`references/vnstock_api.md`** — ⭐ NGUỒN #1: Code Python fetch BCTC/ratios/news/events qua vnstock API
- `references/data_sources.md` — URL pattern web sources (backup khi vnstock thiếu)
- `references/data_pitfalls.md` — 6 bẫy dữ liệu đặc thù VN + cách phát hiện/sửa
- `references/sector_insights.md` — Đặc thù theo ngành
