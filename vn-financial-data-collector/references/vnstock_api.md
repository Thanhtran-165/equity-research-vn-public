# vnstock API Reference — Nguồn data #1 cho mọi skill

vnstock là thư viện Python lấy data trực tiếp từ VCI/TCBS/KBS — **đáng tin hơn web scraping** vì:
- Data chính thức từ nguồn HOSE (qua VCI broker)
- Không bị block/bot detection như CafeF/Vietstock web
- Có sẵn BCTC, ratios, news, events — không cần parse HTML
- Đơn vị nhất quán (nghìn đồng cho giá)

## Mục lục
1. [Cài đặt](#install)
2. [Quote — Giá & lịch sử](#quote)
3. [Finance — BCTC & ratios](#finance)
4. [Company — News, Events, Cổ đông](#company)
5. [Listing — Danh mục CP](#listing)
6. [Sources](#sources)
7. [Quy hoạch nguồn: vnstock vs web](#priority)

---

## Cài đặt <a name="install"></a>

```bash
pip install vnstock --upgrade
```

⚠️ **API breaking change (31/08/2025):** Module `vnstock` cũ deprecated. Dùng `vnstock.api` submodule:
```python
from vnstock.api.quote import Quote
from vnstock.api.financial import Finance
from vnstock.api.company import Company
from vnstock.api.listing import Listing
```

---

## Quote — Giá & lịch sử <a name="quote"></a>

```python
from vnstock.api.quote import Quote
q = Quote(symbol='HPG', source='VCI')
df = q.history(start='2025-06-22', end='2026-06-21', interval='1W')
# Columns: time, open, high, low, close, volume
# ⚠️ Giá tính bằng NGHÌN đồng (19.38 = 19,380 đ)
# interval: '1D' daily, '1W' weekly
df = df.dropna(subset=['close'])  # bỏ tuần chưa hoàn thành
```

**Index (VNINDEX, VN30):**
```python
q_vni = Quote(symbol='VNINDEX', source='VCI')
df = q_vni.history(...)
```

**Dùng cho skills:** `vn-technical-analysis` (giá 52 tuần, indicators, Beta/Correlation)

---

## Finance — BCTC & ratios <a name="finance"></a>

```python
from vnstock.api.financial import Finance
f = Finance(symbol='HPG', source='VCI')

# Balance sheet (CDKT) — 122 items, 2018Q1-2026Q1
bs = f.balance_sheet()
# Items: TÀI SẢN NGẮN HẠN, Tiền, Hàng tồn kho, TÀI SẢN DÀI HẠN...
#         VỐN CHỦ SỞ HỮU, Nợ vay, Lợi nhuận sau thuế...

# Income statement (KQKD) — 25 items
inc = f.income_statement()
# Items: Doanh thu thuần, Lợi nhuận gộp, Chi phí lãi vay,
#         Lãi/(lỗ) trước thuế, Lợi nhuận của Cổ đông của Công ty mẹ,
#         Lãi cơ bản trên cổ phiếu (VND) ← EPS!

# Cash flow (LCTT) — 41 items
cf = f.cash_flow()
# Items: Lợi nhuận trước thuế, Khấu hao, Lợi nhuận HĐKD (CFO)...

# Ratios — 54 items (TÍNH SẮN!)
ratios = f.ratio()
# Items: Số CP lưu hành (triệu), Vốn hóa, P/E, P/B, P/S,
#         Giá/Dòng tiền, EV/EBITDA, ROE(%), ROA(%), Nợ/Vốn chủ...
```

⚠️ **CẢNH BÁO QUAN TRỌNG (case BSR 2026):** API `f.ratio()` có thể trả **data stale** — chỉ trả 2018-2019 cho BSR dù request năm 2021-2025. Có thể do pagination/limit. Test xem:
```python
rt = f.ratio()
print(f"Columns: {list(rt.columns)}")  # Nếu chỉ 4-7 cols vs years cũ → stale
print(f"Shape: {rt.shape}")  # Nếu shape (54, 7) thay vì (54, 30+) → stale
```
**Nếu stale:** KHÔNG dùng ratio() tính sẵn. Phải tự tính ROE/ROA/PE/PB từ `income_statement` + `balance_sheet` + giá. Verify cross-check với web sources (Vietstock, CafeF, báo cáo CTCK).

⚠️ **EPS từ vnstock có thể sai hoặc dùng weighted-average:** Case BSR — EPS 2021 vnstock = 2,073 đ nhưng BCTC kiểm toán gốc = 2,166 đ (MAS Securities, PHS confirmed). Luôn cross-check EPS bằng: `LNST(đồng) / số CP năm đó`. Back-calc `CP = LNST/EPS` rồi compare với `capital_history()`.

**Trích data cho fundamental analysis:**
```python
def get_yearly(df, item_name, years=['2021-Q4','2022-Q4','2023-Q4','2024-Q4','2025-Q4']):
    row = df[df['item'] == item_name]
    return [row[y].values[0] if not row.empty else None for y in years]

# Ví dụ lấy LNST 5 năm
lnst = get_yearly(f.income_statement(), 'Lợi nhuận của Cổ đông của Công ty mẹ')
revenue = get_yearly(f.income_statement(), 'Doanh thu thuần')
equity = get_yearly(f.balance_sheet(), 'VỐN CHỦ SỞ HỮU')
```

**Dùng cho skills:** `vn-financial-data-collector` (data 5 năm), `vn-fundamental-analysis` (ratios), `vn-valuation-engine` (PE/PB/EV-EBITDA có sẵn)

---

## Company — News, Events, Cổ đông <a name="company"></a>

```python
from vnstock.api.company import Company
c = Company(symbol='HPG', source='VCI')

# Overview — thông tin tổng hợp (vốn hóa, rating, target_price)
info = c.overview()
# Columns: symbol, current_price, market_cap, issue_share, rating,
#          target_price, highest_price1_year, lowest_price1_year,
#          foreigner_percentage, sector, company_profile...

# News — 50 tin gần nhất
news = c.news()
# Columns: news_title, news_short_content, news_source, public_date,
#          news_source_link, news_keyword

# Events — 50 sự kiện (công bố thông tin, cổ tức, giao dịch nội bộ)
events = c.events()
# Columns: event_title_vi, public_date, action_type_vi, category,
#          record_date, exercise_ratio, value_per_share, payout_date

# Shareholders — cổ đông lớn (source='KBS')
c = Company(symbol='HPG', source='KBS')
shareholders = c.shareholders()
# Columns: name, shares_owned, ownership_percentage

# Capital history — lịch sử vốn điều lệ (source='KBS')
cap = c.capital_history()
# Columns: date, charter_capital
```

**Dùng cho skills:** `vn-news-digest` (news 50 tin), `vn-financial-data-collector` (events = công bố thông tin), `vn-valuation-engine` (target_price analyst)

---

## Listing — Danh mục CP <a name="listing"></a>

```python
from vnstock.api.listing import Listing
lst = Listing(source='VCI')
all_symbols = lst.all_symbols()  # toàn bộ CP
# Columns: symbol, organ_name

# Theo ngành
by_industry = lst.symbols_by_industries()
```

---

## Sources <a name="sources"></a>

| Source | Tên | Hỗ trợ | Ưu tiên |
|---|---|---|---|
| `VCI` | Vietcombank Securities | Quote, Finance, Company (news/events/overview), Listing | **#1 — đầy đủ nhất** |
| `KBS` | KBS Securities (TCBS mới) | Company (capital_history, shareholders) | #2 — bổ sung VCI |
| `DNSE` | DNSE | Quote | #3 — backup |

---

## Quy hoạch nguồn: vnstock vs web <a name="priority"></a>

### Ưu tiên #1: vnstock API (luôn thử trước)

| Loại data | Method vnstock | Thay thế cho web nào |
|---|---|---|
| Giá lịch sử | `Quote.history()` | Investing.com, Yahoo Finance |
| BCTC (KQKD/CDKT/LCTT) | `Finance.balance_sheet/income_statement/cash_flow` | Vietstock, CafeF BCTC page |
| Ratios (PE/PB/ROE/EV-EBITDA) | `Finance.ratio()` | Vietstock ratios page |
| Vốn hóa, số CP | `Company.overview()` | Vietstock, CafeF sidebar |
| Tin tức | `Company.news()` (50 tin) | CafeF, VnExpress search |
| Công bố thông tin | `Company.events()` (50 sự kiện) | HOSE disclosure, VSD |
| Cổ đông lớn | `Company.shareholders()` (KBS) | BCTN, trang QHCD |
| Target price analyst | `Company.overview()['target_price']` | Báo cáo CTCK |
| Index (VNINDEX/VN30) | `Quote(symbol='VNINDEX')` | CafeF, VNDirect |

### Ưu tiên #2: Web scraping (chỉ khi vnstock thiếu)

| Loại data | Web nguồn | Lý do vnstock thiếu |
|---|---|---|
| BCTC kiểm toán PDF chính thức | Trang QHCD DN | vnstock chỉ có data, không có PDF |
| Báo cáo thường niên | Trang QHCD DN | Không có trong API |
| Tin tức > 50 bài gần nhất | CafeF, VnExpress | API chỉ trả 50 bài |
| Lịch sử chia tách chi tiết | cophieu68 `/quote/event.php` | vnstock events có nhưng hạn chế |
| Tin vĩ mô ngành | VietnamBiz, VSA | Không có trong API |

### Ưu tiên #3: WebSearch (chỉ cho verify/bổ sung)

Dùng `WebSearch` tool để:
- Verify số liệu quan trọng (LNST, VCSH) sau khi fetch vnstock
- Tìm data mới nhất chưa có trong API (BCTC năm vừa công bố)
- Bổ sung góc nhìn định tính (sentiment, news analysis)

---

## Code template: fetch toàn bộ data cho 1 CP

```python
from vnstock.api.quote import Quote
from vnstock.api.financial import Finance
from vnstock.api.company import Company

ticker = 'HPG'
source = 'VCI'

# 1. Giá 52 tuần
q = Quote(symbol=ticker, source=source)
prices = q.history(start='2025-06-22', end='2026-06-21', interval='1W').dropna(subset=['close'])

# 2. BCTC + Ratios
f = Finance(symbol=ticker, source=source)
income = f.income_statement()
balance = f.balance_sheet()
cashflow = f.cash_flow()
ratios = f.ratio()

# 3. Info + News + Events
c = Company(symbol=ticker, source=source)
overview = c.overview()
news = c.news()
events = c.events()

# 4. Index cho Beta
vni = Quote(symbol='VNINDEX', source=source).history(
    start='2025-06-22', end='2026-06-21', interval='1W').dropna(subset=['close'])

print(f"=== {ticker} DATA SUMMARY ===")
print(f"Giá hiện tại: {int(overview['current_price'].iloc[0]):,} đ")
print(f"Vốn hóa: {overview['market_cap'].iloc[0]/1e9:,.0f} tỷ VNĐ")
print(f"Số CP: {overview['issue_share'].iloc[0]/1e9:.2f} tỷ")
print(f"BCTC: income {income.shape}, balance {balance.shape}, cashflow {cashflow.shape}")
print(f"Tin tức: {len(news)} bài, Sự kiện: {len(events)}")
```

---

## Đặc thù schema theo ngành

⚠️ **Ngân hàng (VCB, BID, CTG, TCB...) dùng schema KQKD KHÁC công ty thường:**

| Công ty thường | Ngân hàng |
|---|---|
| Doanh thu thuần | **Thu nhập lãi thuần** + Tổng thu nhập hoạt động |
| Lợi nhuận của Cổ đông của Công ty mẹ | **Lợi nhuận sau thuế** (hoặc "Cổ đông của Công ty mẹ") |
| Giá vốn hàng bán | **Chi phí lãi** + Trích lập dự phòng |
| — | **Trích lập dự phòng tổn thất tín dụng** (đặc thù NH) |

**Code fetch LNST ngân hàng:**
```python
# Thay vì 'Lợi nhuận của Cổ đông của Công ty mẹ'
lnst = get_yearly(inc, 'Lợi nhuận sau thuế')  # cho NH
# HOẶC
lnst = get_yearly(inc, 'Cổ đông của Công ty mẹ')
```

**Code fetch "doanh thu" ngân hàng:**
```python
# Không có 'Doanh thu thuần' — dùng:
net_interest_income = get_yearly(inc, 'Thu nhập lãi thuần')  # NIM driver
total_income = get_yearly(inc, 'Tổng thu nhập hoạt động')     # tổng QT
```

---

## Troubleshooting

| Lỗi | Sửa |
|---|---|
| `KeyError: 'data'` ở Company | `pip install vnstock --upgrade` |
| `cannot convert float NaN to integer` | `.dropna(subset=['close'])` trước |
| `Vnstock class deprecated` | Dùng `vnstock.api.*` thay vì `vnstock.Vnstock` |
| `Source VCI does not support X` | Đổi source='KBS' hoặc 'DNSE' |
| RetryError NotImplementedError | Method chưa hỗ trợ source đó — đổi source |
| Auth failed | `pip install vnstock --upgrade` (tự re-auth) |

## Cập nhật vnstock

Kiểm tra version định kỳ:
```bash
pip show vnstock | grep Version
pip install vnstock --upgrade
```

vnstock update thường xuyên — API có thể thay đổi. Luôn check changelog tại https://vnstocks.com/docs/tai-lieu/lich-su-phien-ban
