# 9 bẫy dữ liệu đặc thù thị trường chứng khoán VN

Mỗi bẫy có: dấu hiệu nhận biết → cách phát hiện → cách sửa. Ví dụ thực từ case HPG (2026) và BSR (2026).

## Thứ tự ưu tiên (theo mức độ nghiêm)

| Mức | Bẫy | Tác động |
|---|---|---|
| 🔴 CRITICAL | **5B** Split-adjustment consistency | PE/PB sai hoàn toàn, kết luận định giá sai |
| 🟠 CAO | 1 Số CP lưu hành thay đổi | EPS/BVPS sai |
| 🟠 CAO | 3 LNST vs LN trước thuế | LNST sai, ROE sai |
| 🟡 TRUNG BÌNH | 2 Đơn vị tính | BVPS phình 1000x |
| 🟡 TRUNG BÌNH | 4 Data cũ | Phân tích sai kỳ |
| 🟡 TRUNG BÌNH | 5 Split-adjusted price | So sánh giá sai |
| 🟢 THẤP | 6 Vốn hóa sai format | Hiển thị sai |

## ⭐ Audit procedure ĐẦU TIÊN (chạy trước khi tính multiples)

```python
# Bước 0: Detect split + verify số CP trước khi tính EPS/PE/PB
from vnstock.api.company import Company
from vnstock.api.financial import Finance

# 1. Check events cho split/dividend-stock
events = Company(symbol=TICKER, source='VCI').events()
splits = [e for e in events.to_dict('records')
          if any(k in str(e.get('event_title_vi','')).lower()
                 for k in ['chia cổ phiếu','phát hành cổ phiếu','tăng vốn'])]
print(f"Splits found: {len(splits)}")

# 2. Check capital history
cap = Company(symbol=TICKER, source='KBS').capital_history()
print(f"Charter capital changes: {len(cap)}")

# 3. Back-calc CP từng năm: CP = LNST/EPS
inc = Finance(symbol=TICKER, source='VCI').income_statement(period='year')
for y in ['2021','2022','2023','2024','2025']:
    lnst = inc[inc['item']=='Lợi nhuận của Cổ đông của Công ty mẹ'][y].values[0] / 1e9  # tỷ
    eps = inc[inc['item']=='Lãi cơ bản trên cổ phiếu (VND)'][y].values[0]
    cp = lnst*1e9 / eps / 1e9  # tỷ CP
    print(f"  {y}: LNST={lnst:,.0f} tỷ, EPS={eps:,.0f} đ → CP back-calc = {cp:.3f} tỷ")

# 4. Nếu CP 2025 / CP 2024 > 1.2 → split đã xảy ra → áp dụng Bẫy 5B
```

---

## Bẫy 5B: Split-adjustment consistency — RỦI RO NGHIÊM TRỌNG (case BSR 2026)

**Dấu hiệu:** PE/PB history có values "đẹp bất thường" (VD: PE 1-2x cho năm lợi nhuận cao) → mismatch chuẩn giữa giá (split-adjusted) và EPS/BVPS (BCTC gốc).

**Ví dụ BSR (sai nghiêm trọng):** BSR chia tách 15/10/2025 — 31.5% cổ phiếu thưởng + 30% cổ tức cổ phiếu = **1.615x dilution** (3.10 tỷ → 5.007 tỷ CP). vnstock `Quote.history()` trả giá **SPLIT-ADJUSTED** (toàn bộ lịch sử scale về base 5.007 tỷ CP), nhưng BCTC gốc dùng base 3.10 tỷ CP cho 2021-2024.

**Lỗi cụ thể đã mắc:**
- EPS 2021 từ BCTC = 2,166 đ (base 3.10 tỷ)
- Year-end price 2021 từ vnstock = 13,210 đ (split-adjusted, base 5.007 tỷ)
- PE tính = 13,210 / 2,166 = **6.10x** ← SAI (mix 2 chuẩn)
- PE đúng = 13,210 / (2,166/1.615) = 13,210 / 1,341 = **9.85x**

**Bảng so sánh sai vs đúng (case BSR):**
| Năm | PE sai (mix chuẩn) | PE đúng (cùng base) |
|---|---|---|
| 2021 | 6.10x | 9.85x |
| 2022 | 1.62x | 2.62x |
| 2023 | 4.01x | 6.48x |
| 2024 | 69.22x | 111.78x |
| 2025 | 15.47x | 15.47x ✓ (cùng năm split) |

**Cách phát hiện (heuristic):**
1. Check `Company.events()` cho event `category='DIVIDEND'` với `action_type` chứa "chia cổ phiếu" / "phát hành cổ phiếu" / ratio > 0
2. Check `capital_history()` (KBS source) — nếu vốn điều lệ tăng đột biến → split
3. **Back-calc test**: Tính `CP = LNST/EPS` từng năm — nếu CP 2025 gấp ~1.6x CP 2024 → split gần đây
4. Check PE history — nếu PE đột nhiên "đẹp bất thường" cho các năm trước → có thể mix chuẩn

**Cách sửa (procedure chuẩn):**
```python
# 1. Detect split từ events
events = Company(symbol='BSR', source='VCI').events()
splits = [e for e in events.to_dict('records')
          if 'chia cổ phiếu' in str(e.get('event_title_vi','')).lower()
          or 'phát hành' in str(e.get('event_title_vi','')).lower()]
# Sum dilution ratio: VD 31.5% + 30% = 0.615 → multiplier 1.615
SPLIT_MULT = 1.0
for s in splits:
    ratio = float(s.get('exercise_ratio', 0) or 0)
    if ratio > 0:
        SPLIT_MULT *= (1 + ratio)

# 2. Adjust EPS/BVPS cho các năm TRƯỚC split date về base post-split
for year < split_year:
    eps_adjusted[year] = eps_original[year] / SPLIT_MULT
    bvps_adjusted[year] = bvps_original[year] / SPLIT_MULT
    shares_adjusted[year] = shares_original[year] * SPLIT_MULT
# Year của split và sau: giữ nguyên

# 3. PE/PB = price_adjusted / eps_adjusted (cùng base)
```

**Quy tắc vàng:** Nếu công ty có split/dividend-stock trong kỳ phân tích → **LUÔN adjust EPS/BVPS/shares về CÙNG base với giá** (thường là post-split) trước khi tính PE/PB/MC cross-year. Verify bằng cách: PE tính = PE pre-split (giá unadjusted / EPS pre-split) → phải bằng PE post-split (giá adjusted / EPS adjusted).

**Detect trước khi build dashboard:** Luôn chạy `audit_shares.py` (back-calc CP từ EPS/LNST) trước khi tính multiples. Nếu CP back-calc khác CP giả định > 5% → split đã xảy ra, cần adjust.

---


## Bẫy 6: Vốn hóa sai do số CP cũ hoặc sai format

**Dấu hiệu:** Vốn hóa hiển thị sai format (VD: "₫136.5B tỷ" — vừa trùng lặp đơn vị B+tỷ, vừa sai số) hoặc sai giá trị tuyệt đối > 20% so với nguồn chính thức.

**Ví dụ HPG (sai):** Dùng `₫136.5B tỷ` — sai 2 lỗi:
1. **Sai số:** Dùng số CP cũ (5.77 tỷ) × giá → 136.5K tỷ. Thực tế = 8.44 tỷ CP × 23,600 đ = **199,254 tỷ**
2. **Sai format:** "₫136.5B tỷ" — B (billion) và tỷ trùng lặp. Phải là "₫199.3K tỷ" hoặc "199,254 tỷ đồng"

**Cách phát hiện:** So sánh vốn hóa hiển thị với `market_cap` field từ vnstock:
```python
from vnstock.api.company import Company
info = Company(symbol='HPG', source='VCI').overview()
# info['market_cap'] = 1.99e14 = 199,254,000,000,000 đ = 199,254 tỷ
# info['issue_share'] = 8,442,965,000 = 8.44 tỷ CP
```

**Cách tính vốn hóa đúng:**
```
Market Cap = giá hiện tại × số CP lưu hành HIỆN TẠI (sau tất cả cổ tức CP)
         = 23,600 đ × 8,442,965,000 CP
         = 199,254,000,000,000 đ
         = 199,254 tỷ VNĐ
         ≈ $7.8B USD (chia ~25,500 VND/USD)
```

**Format chuẩn khi hiển thị:**
- ✅ Đúng: "199,254 tỷ VNĐ", "₫199.3K tỷ", "~$7.8B USD"
- ❌ Sai: "₫136.5B tỷ" (trùng B + tỷ), "136.5B" (thiếu đơn vị), "136,500 tỷ" (sai số)

**Quy tắc:** Luôn fetch `market_cap` từ vnstock `Company.overview()` thay vì tự tính. Nếu tự tính, dùng số CP **mới nhất** (sau cổ tức CP gần nhất), không phải số CP năm trước.

---

## Bẫy 1: Số CP lưu hành thay đổi qua các năm

**Dấu hiệu:** EPS/BVPS giảm liên tục dù LNST/VCSH tăng — vì mẫu số (số CP) tăng. HOẶC EPS tự tính ≠ EPS từ BCTC công bố.

**Ví dụ HPG (sai):** Dùng cố định 5.77 tỷ CP cho cả 2021-2025 → BVPS 2024 = 22,530 đ, 2025 = 25,130 đ (sai).

**Thực tế (đúng):** CP tăng qua các đợt cổ tức cổ phiếu:
| Năm | Số CP (tỷ) | Sự kiện |
|---|---|---|
| 2021 | 5.81 | sau cổ tức 2020 (35% CP) |
| 2022 | 6.40 | sau cổ tức 2021 (30% CP) |
| 2023 | 6.40 | không chia thêm |
| 2024 | 6.40 | không chia thêm |
| 2025 | 7.69 | sau cổ tức 2024 (20% CP, 26/06/2025) |

**BVPS đúng:** 145,000 / 7.69 = **18,867 đ** (khớp Vietstock 17,096 đ tại thời điểm tương ứng).

**Ví dụ BSR 2026 (back-calc):** Dùng `CP = LNST / EPS` để verify số CP:
| Năm | LNST (tỷ) | EPS (đ) | CP back-calc | CP giả định | Chênh |
|---|---|---|---|---|---|
| 2021 | 6,715.5 | 2,166 | 3.10 tỷ | 3.10 | 0% ✓ |
| 2022 | 14,725.8 | 4,750 | 3.10 tỷ | 3.10 | 0% ✓ |
| 2023 | 8,649.8 | 2,789 | 3.10 tỷ | 3.10 | 0% ✓ |
| 2024 | 631.1 | 204 | 3.10 tỷ | 3.10 | 0% ✓ |
| 2025 | 5,213.6 | 1,040 | **5.01 tỷ** | 5.007 | +0.6% ✓ |

→ Verify OK. Nhưng nếu EPS vnstock = 2,073 cho 2021 (sai) thì back-calc = 3.24 tỷ ≠ 3.10 → báo động.

**Cách phát hiện (3 method):**
1. **Back-calc verification**: Tính `CP = LNST(đồng) / EPS(đ/cp)` từng năm. Nếu CP back-calc khác `capital_history()` > 5% → có vấn đề
2. **Cross-check EPS**: Tính `EPS = LNST / CP` với CP giả định, so sánh với EPS trong income_statement ('Lãi cơ bản trên cổ phiếu'). Nếu chênh > 5% → số CP sai hoặc EPS công bố dùng weighted-average
3. **capital_history() audit**: Fetch `Company(symbol, source='KBS').capital_history()` → xem vốn điều lệ từng mốc thời gian

**Cách sửa:** Lấy lịch sử chia tách từ:
- `cophieu68.vn/quote/event.php?id=[mã]` (HTML)
- vnstock `Company.events()` filter `category='DIVIDEND'` + `action_type` chứa "chia cổ phiếu" / "phát hành"
- vnstock `Company.capital_history()` (KBS source)

---

## Bẫy 2: Đơn vị tính sai (BVPS phình 1000 lần)

**Dấu hiệu:** BVPS = hàng triệu đồng (thay vì hàng nghìn) — vô lý so với giá CP (~20,000-30,000 đ).

**Ví dụ (sai):** `VCSH(145 tỷ) / CP(7.69 tỷ) × 1000 = 18,866,697 đ` — BVPS phình 1000×.

**Công thức đúng:** `VCSH[tỷ đồng] / số CP[tỷ cp] = đồng/cp` (tỷ/tỷ = 1, không cần ×1000).
- VCSH 145,000 tỷ ÷ 7.69 tỷ CP = **18,867 đ/cp** ✓

**Cách phát hiện:** BVPS > 1,000,000 đ → chắc chắn sai đơn vị. BVPS hợp lý cho CP VN: 5,000-50,000 đ.

**Cách sửa:** Bỏ thừa `× 1000`. LNST[tỷ] / CP[tỷ] = đồng/cp cũng tương tự.

---

## Bẫy 3: LNST vs LN trước thuế vs LNST thuộc CĐ mẹ

**Dấu hiệu:** Cùng 1 năm, các nguồn cho 2 số "lợi nhuận" khác nhau (chênh ~30-70%).

**Ví dụ HPG 2023:**
- Báo cáo thường niên 2023: LN 2023 = ~6,800 tỷ (LNST hợp nhất thuộc CĐ mẹ) ✓
- Một số nguồn không kiểm toán: LN = 12,100 tỷ (có thể là LN trước thuế hoặc số liệu không chính thức) ❌

**Ba mức lợi nhuận trong BCTC:**
1. **LN trước thuế** (PBT) — lớn nhất
2. **LN sau thuế** (PAT/LNST) — = PBT × (1 - tax rate)
3. **LNST thuộc CĐ công ty mẹ** — nhỏ hơn LNST nếu có cổ đông không kiểm soát (NCI)

**Cách phát hiện:** ROS (LNST/Doanh thu) < 5% cho ngành phi tài chính + cổ phiếu phòng thủ → có thể đang dùng PBT. ROS hợp lý: 5-25% tùy ngành.

**Cách sửa:** Dùng **LNST hợp nhất thuộc CĐ công ty mẹ** (dòng cuối cùng của BCTC, dùng cho EPS). Verify với BCTC kiểm toán PDF từ trang QHCD.

---

## Bẫy 4: Data cũ trong search results

**Dấu hiệu:** Search "HPG BCTC 2025" trả về kết quả BCTN 2024 ở vị trí đầu — vì BCTN cũ được index mạnh hơn.

**Ví dụ (sai):** Tháng 6/2026, phân tích "5 năm gần nhất" nhưng dùng data 2020-2024 (BCTN 2024 nổi bật hơn BCTC 2025 chưa được index đầy đủ).

**Cách phát hiện:**
- Ngày hiện tại ≥ tháng 4 → kỳ gần nhất phải là **N-1** (BCTC đã công bố ~27/03)
- Search result hiển thị BCTN năm N-2 → data cũ

**Cách sửa:**
1. WebSearch với `search_recency_filter=oneMonth` hoặc `oneWeek`
2. Query: `"[tên DN] BCTC kiểm toán [năm N-1]"` + `"công bố 27/03"` hoặc `"30/01"`
3. Fetch trực tiếp trang QHCD DN — BCTC mới nhất luôn nằm đầu danh sách

---

## Bẫy 5: Split-adjusted price khi so sánh nhiều năm

**Dấu hiệu:** Giá CP năm 2021 (32,800 đ) và 2025 (23,650 đ) trông giảm mạnh, nhưng có thể do chia tách chứ không phải giảm giá thật.

**Ví dụ HPG:** CP tăng từ 5.81 tỷ (2021) → 7.69 tỷ (2025), tỷ lệ 1.32×. Giá "adjusted" 2021 = 32,800 / 1.32 = 24,850 đ → giảm thực ~5%, không phải -28%.

**Khi nào cần adjust:**
- So sánh giá tuyệt đối qua các năm (line chart giá 5 năm)
- Tính tỷ suất sinh lời dài hạn
- Reverse DCF với chuỗi giá lịch sử

**Khi nào KHÔNG cần adjust:**
- ROE/ROS/ROA (không phụ thuộc số CP)
- CAGR LNST/doanh thu/VCSH

**Cách adjust:** Tính tỷ lệ tích lũy = CP năm sau / CP năm trước. Giá adjusted = giá thực / tỷ lệ tích lũy.

**⚠️ QUAN TRỌNG — Xem thêm Bẫy 5B bên dưới:** Khi fetch giá từ vnstock `Quote.history()` (đã auto split-adjusted) NHƯNG đồng thời dùng EPS/BVPS từ BCTC gốc (chưa adjust) → mix 2 chuẩn → PE/PB SAI hoàn toàn. Đây là lỗi đã xảy ra với BSR 2026 (PE sai từ 6.10x → đúng 9.85x). Luôn adjust EPS/BVPS về cùng base với giá trước khi tính PE/PB cross-year.

---

## Bẫy 8 (v2.2.2 — học từ CTD test 7/2026): Subagent qualitative claims sai — tin blind

**Dấu hiệu:** Subagent research trả thông tin qualitative (sở hữu, governance, quan hệ công ty, event lịch sử) — LLM đưa thẳng vào báo cáo KHÔNG verify.

**Ví dụ CTD (7/2026):** Subagent claim "Ông Nguyễn Bá Dương là Chủ tịch đồng thời CTD + HBC + Ricons + Newtecons. Hệ sinh thái related-party." → **SAI HOÀN TOÀN**:
- Thực tế: ông Dương là **cựu Chủ tịch CTD** (rời 2020 khi Kusto tiếp quản)
- Hệ sinh thái ông sáng lập SAU khi rời CTD: Newtecons + Ricons + SOL E&C + BM Windows + Boho + DB
- HBC **độc lập** (ông Lê Viết Hải) — không liên quan

**Vì sao nguy hiểm:**
- Claims qualitative về **sở hữu/governance** dễ sai vì phức tạp (thay đổi qua thời gian, nhiều nguồn mâu thuẫn)
- Sai 1 claim → insight frame sai premise → kết luận sai → **misleading nhà đầu tư**
- Khó detect tự động (không phải số liệu, là narrative)

**Cách phòng tránh (BẮT BUỘC):**

1. **Verify mọi claim qualitative về sở hữu/quan hệ công ty** qua ≥2 nguồn độc lập trước khi đưa vào báo cáo:
   - WebSearch + webRead trực tiếp (không tin subagent blind)
   - Đặc biệt: "ông X là Chủ tịch công ty Y", "công ty A thuộc hệ sinh thái B", "sự kiện Z năm YYYY"

2. **Flag "VERIFY" cho mọi claim qualitative** trong draft báo cáo → confirm trước khi publish

3. **Cross-check với BCTC note "bên liên quan"** — nguồn chính thức nhất cho related-party transactions

4. **Khi subagent trả claim bất thường** (vd "Chủ tịch 4 công ty cùng lúc" — hiếm ở VN), **đặc biệt verify** — có thể sai

**Rule cốt lõi:** Subagent research = input, KHÔNG phải truth. Claims quantitative (số liệu) cần cross-check nguồn; claims qualitative (narrative) cần cross-check nhiều nguồn + verify trực tiếp. Đặc biệt governance/ownership — sai 1 chữ ("cựu" vs "hiện tại") = sai toàn bộ insight.

---

## Bẫy 9 (v2.2.4 — học từ CTD test 7/2026): Báo cáo thiếu biểu đồ — visual gap

**Dấu hiệu:** Báo cáo HTML có data tables + text NHƯNG không có charts/visualizations. So sánh với benchmark (ORCL report 13 charts) thấy gap rõ.

**Ví dụ CTD (7/2026):** Report ban đầu 0 charts (chỉ tables). ORCL benchmark có 13 charts (revenue/LNST, capex/FCF, segment mix, P/E history, peer scatter, price+MA, RSI, drawdown, distribution, valuation summary).

**Vì sao nguy hiểm:**
- Charts là cách **nhận ra pattern nhanh nhất** (red flag CFO âm + LNST dương → chart bar so sánh thấy ngay)
- Text tables dễ skip, charts "đánh vào mắt"
- Nhà đầu tư retail hiểu chart tốt hơn table
- Báo cáo "chuyên nghiệp" phải có charts, không chỉ text

**Cách phòng tránh (BẮT BUỘC):**

1. **Dashboard report PHẢI có tối thiểu 10 charts:**
   - Revenue + LNST 5 năm (bar + line dual axis)
   - CFO vs LNST (red flag visual — FCF âm)
   - Backlog growth (bar)
   - P/E + P/B history (line dual axis)
   - Valuation summary (bar — price vs fair value)
   - Debt vs Equity + D/E (bar + line)
   - Peer scatter (bubble — P/B vs growth)
   - Price + MA (line — technical)
   - RSI (line + overbought/oversold bands)
   - Drawdown (area — profile)
   - Return distribution (histogram — profile)
   - Segment mix (doughnut — nếu có)

2. **Verify trước deploy:** `grep -c 'new Chart\|viz.chart'` phải ≥ 10

3. **Chart data phải thật** — không simulate. Fetch từ vnstock_data (sponsor) cho price/financials.

4. **Mỗi chart trong card riêng** — có title + chart-wrap height rõ

**Rule cốt lõi:** Báo cáo equity research KHÔNG CHỈ là text + tables. Charts = phần visible nhất, bỏ sót = báo cáo "thiếu chuyên nghiệp" ngay lập tức.
