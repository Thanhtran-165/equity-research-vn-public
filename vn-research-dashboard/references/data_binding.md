# Data Binding — Placeholder schema cho dashboard

Danh sách toàn bộ điểm cần fill trong template. Theo thứ tự xuất hiện trong HTML.

## ⚠️ Template đã được tokenize (refactor 2026-06)

Template `dashboard_template.html` giờ dùng **placeholder `{{UPPER_TOKEN}}`** (trước đây hard-code HPG → phải edit tay mỗi lần chạy → nguồn gốc của các bug "placeholder không replace"). Pattern fill = `str.replace` thuần (KHÔNG f-string/.format — xung đột brace với JS).

**Composite blocks** (KPI strip, fin table, val cards, insights, DCF/Graham, disclaimer, footer) = 1 token chứa nguyên khối HTML (`{{KPI_STRIP}}`, `{{FIN_TABLE_HTML}}`, `{{VAL_CARDS_HTML}}`, ...). Cách fill: build HTML string trong Python rồi inject.

**Token danh sách đầy đủ** (xem `references/data_binding_tokens.md` cho bảng map đầy đủ):
- Identity: `{{TICKER}}`, `{{COMPANY_NAME}}`, `{{TICKER_BADGE}}`, `{{COMPANY_SUB}}`, `{{PRICE_DISPLAY}}`, `{{PRICE_META}}`, `{{YEAR_RANGE}}`, `{{LATEST_YEAR}}`
- Composite HTML: `{{KPI_STRIP}}`, `{{FIN_TABLE_HTML}}`, `{{FIN_TABLE_FOOTNOTE}}`, `{{VAL_CARDS_HTML}}`, `{{MULTIPLES_GRID_HTML}}`, `{{DCF_GRAHAM_HTML}}`, `{{DUPONT_INTERPRETATION_HTML}}`, `{{SUMMARY_STATS_HTML}}`, `{{INSIGHTS_GRID_HTML}}`, `{{RATING_HTML}}`, `{{DISCLAIMER_HTML}}`, `{{FOOTER_HTML}}`
- Chart subs (text): `{{CHART_REVNP_SUB}}`, `{{CHART_MARGIN_SUB}}`, `{{CHART_PEPB_SUB}}`, `{{CHART_PRICEBV_SUB}}`, `{{TABLE5Y_SUB}}`, `{{SECTION01_NOTE}}`, `{{SUMMARY_CHART_SUB}}`, `{{INSIGHTS_TITLE}}`, `{{FORECAST_YEARS}}`, `{{FORECAST_SUB}}`
- Gauge: `{{FAIR_VALUE}}`, `{{GAUGE_VERDICT}}`, `{{GAUGE_DIFF_NOTE}}`
- Chart data (JSON/raw JS): `{{YEARS}}`, `{{CHART_DATA}}`, `{{SUMMARY_CHART_DATA}}`, `{{SUMMARY_ANNOTATION}}`

⚠️ **Token mà chứa JS function** (vd `backgroundColor:(ctx)=>{...}` trong `{{SUMMARY_CHART_DATA}}`) — KHÔNG JSON-stringify được. Phải emit raw JS object literal (xem `render_hpg_sample.py` trong project mẫu).

⚠️ **VIZ_CSS / VIZ_JS**: đây là design-time placeholder, **inject.py** (từ `_viz-shared/`) đã fill trước khi template đến tay LLM. Đừng đụng tới khi fill data.

## Verify contract

```python
import re
remaining = sorted(set(re.findall(r"\{\{[A-Z_0-9]+\}\}", html)))
assert not remaining, f"unreplaced tokens: {remaining}"
```

---

## {{DISCLAIMER_HTML}} — content template (v2.2.0, học từ us-equity-research)

Block disclaimer đã có CSS trong template (line 651) + placeholder `{{DISCLAIMER_HTML}}` ở line 826. **Fill content dưới đây** vào token — chống "ảo giác model" cho nhà đầu tư đọc:

```html
<div class="disclaimer-title">⚠️ Lưu ý cho nhà đầu tư</div>
<p>Báo cáo này do AI tổng hợp từ nhiều nguồn công khai (vnstock, CafeF, Vietstock, BCTC DN). Mặc dù mỗi con số quan trọng đều có nguồn, <strong>AI có thể sai</strong> — nguồn lỗi, dữ liệu cũ, hoặc hiểu sai đặc thù thị trường VN.</p>
<div class="disclaimer-title sub">3 kỷ luật khi đọc</div>
<ol>
  <li><strong>Đếm nguồn.</strong> Mỗi số quan trọng (LNST, EPS, PE, PB, VCSH) nên có ít nhất 2 nguồn độc lập khớp nhau (vnstock + CafeF/BCTC). Chỉ 1 nguồn = chưa chắc.</li>
  <li><strong>Số bất thường = dừng.</strong> PE 3× hoặc 50× nghe bất thường → verify qua BCTC gốc. Có thể là split-adjustment chưa adjust (Bẫy 5B).</li>
  <li><strong>Nếu là tiền của tôi.</strong> Trước khi quyết định, hỏi: "Tôi có dám đặt số tiền này dựa trên con số AI đưa ra không?" Nếu chưa dám → verify BCTC kiểm toán.</li>
</ol>
<div class="disclaimer-title sub">Nhãn chất lượng dữ liệu</div>
<ul class="qlist">
  <li><span class="qbadge qbadge-HIGHQ">HIGHQ</span> BCTC kiểm toán + vnstock khớp nhau</li>
  <li><span class="qbadge qbadge-MEDQ">MEDQ</span> 1-2 nguồn (vnstock hoặc CafeF), cần đối chiếu thêm</li>
  <li><span class="qbadge qbadge-LOWQ">LOWQ</span> phỏng đoán / WebSearch / chưa verify BCTC</li>
</ul>
<p class="disclaimer-foot">AI không thay thế phán đoán của bạn. Bạn là người ra quyết định cuối cùng với tiền của mình. Báo cáo này KHÔNG phải khuyến nghị mua/bán.</p>
```

**CSS cần có** (đã có trong template, verify không bị thiếu): `.disclaimer`, `.disclaimer-title`, `.qlist`, `.qbadge-HIGHQ/MEDQ/LOWQ`. Nếu thiếu → thêm từ `_viz-shared/components.css`.

---

## Sidebar TOC sticky (v2.2.0 — layout 2 cột, học từ us-equity-research)

**CSS** đã thêm vào `_viz-shared/components.css` (v2.2.0): `.layout-main`, `.layout-content`, `.toc-sidebar`, `.toc-sidebar-item`...

**Cách áp dụng vào template** — bọc section content trong layout-main + thêm aside:

```html
<!-- Sau hero section, bọc剩余 sections trong layout-main -->
<div class="layout-main">
  <div class="layout-content">
    <!-- Section 2 (TL;DR) đến Section 11 (independent view) ở đây -->
  </div>

  <!-- TOC sidebar sticky bên phải -->
  <aside class="toc-sidebar" id="tocSidebar">
    <div class="toc-sidebar-head">📑 Mục lục</div>
    <div class="toc-sidebar-hint">{{N_SECTIONS}} phần · click để nhảy đến</div>
    <ul class="toc-sidebar-list">
      {{TOC_SIDEBAR_ITEMS}}
    </ul>
  </aside>
</div><!-- /layout-main -->

<!-- Disclaimer + footer OUTSIDE layout-main (full width) -->
```

**Token mới** `{{TOC_SIDEBAR_ITEMS}}` — generate tự động:
```python
# Scan section ids → build list items
sections = re.findall(r'<section id="(sec-[^"]+)"[^>]*>.*?<h[12][^>]*>(?:<span[^>]*>\d+</span>)?\s*([^<]+)', html, re.DOTALL)
toc_items = "\n".join(
    f'    <li><a class="toc-sidebar-item" href="#{sid}">'
    f'<span class="toc-sidebar-num">{i+1}</span>'
    f'<span class="toc-sidebar-label">{title.strip()[:40]}</span></a></li>'
    for i, (sid, title) in enumerate(sections)
)
html = html.replace("{{TOC_SIDEBAR_ITEMS}}", toc_items)
```

**Responsive**: desktop ≥1100px = 2 cột (sidebar phải sticky); tablet/mobile = 1 cột (ẩn sidebar, dùng topnav trên cùng). Đã có `@media (max-width: 1100px)` trong components.css.

---

## Danh sách chi tiết (theo thứ tự HTML)

## Hero section

```html
<!-- Tên công ty -->
<div class="ticker-badge">⚡ HOSE:[EXCHANGE] · [SECTOR]</div>
<div class="company-name">[COMPANY_NAME]</div>
<div class="company-sub">[LEGAL_NAME] · Ngành: [SECTOR_VI] · [BIZ_MODEL]</div>

<!-- Giá hiện tại -->
<div class="price-now mono"><span class="ccy">₫</span>[PRICE_CURRENT]<span class="price-unit"> /cp</span></div>
<div class="price-meta">Capitalization ≈ <strong class="mono pos">[MARKET_CAP formatted]</strong> (~$[MARKET_CAP_USD]B USD) · Cập nhật [DATE]</div>
```

⚠️ **Market Cap format rule (BẮT BUỘC):**
- Fetch từ vnstock: `Company(symbol, source='VCI').overview()['market_cap']` → trả về VND tuyệt đối (1.99e14)
- Quy đổi: `/1e9` → tỷ VNĐ (199,254), `/25.5e3` → tỷ USD (~7.8)
- **Format chuẩn hiển thị:**
  - ✅ ĐÚNG: `₫199.3K tỷ` hoặc `199,254 tỷ VNĐ` hoặc `~$7.8B USD`
  - ❌ SAI: `₫136.5B tỷ` (trùng B + tỷ), `136.5B` (thiếu đơn vị), `136,500 tỷ` (sai số vì dùng CP cũ)
- **KHÔNG tự tính** `price × shares_cũ` — phải dùng số CP **hiện tại** (sau cổ tức CP gần nhất) hoặc fetch `market_cap` trực tiếp từ vnstock

## KPI cards (6 cards)

```html
<div class="kpi">
  <div class="kpi-label">[LABEL]</div>            <!-- VD: "P/E (2025)" -->
  <div class="kpi-value mono [pos/neu]">[VALUE]<span>x</span></div>
  <div class="kpi-delta [pos/neg/neu]">[DELTA_TEXT]</div>
</div>
```

6 cards gợi ý:
1. P/E (năm gần nhất)
2. P/B (năm gần nhất)
3. ROE (năm gần nhất)
4. BVPS (năm gần nhất)
5. LNST (năm gần nhất, YoY change)
6. Metric đặc thù ngành (sản lượng thép / SSSG bán lẻ / NAV BĐS...)

## Bảng tài chính 5 năm

Mỗi hàng là 1 chỉ số. **Cross-check số liệu trước khi fill** (xem skill `vn-financial-data-collector/references/data_pitfalls.md`).

Hàng bắt buộc:
- Doanh thu thuần, LNST, Vốn chủ sở hữu, Tổng tài sản, LCFD HĐKD (CFO)
- Số CP lưu hành (từng năm, **KHÔNG cố định**)
- EPS (đồng), BVPS (đồng) — dòng highlight
- ROE, ROA, Biên LNST (ROS)
- Giá cuối năm (đồng)

## Charts (Chart.js data array)

Tất cả array phải có **5 phần tử** (5 năm):

```javascript
const years = [2021, 2022, 2023, 2024, 2025];
const data = {
  revenue:   [150865, 142771, 118953, 140191, 158332],   // tỷ
  netProfit: [34521, 8444, 6835, 12021, 15515],          // tỷ
  eps:       [5937, 1319, 1068, 1878, 2019],             // đồng
  bvps:      [17713, 15313, 17031, 20313, 18867],        // đồng
  price:     [32.8, 19.5, 25.2, 25.0, 23.65],            // nghìn đồng (cho chart)
  pe:        [5.5, 14.8, 23.6, 13.3, 11.7],              // x
  pb:        [1.85, 1.27, 1.48, 1.23, 1.25],             // x
  roe:       [33.5, 8.6, 6.3, 9.2, 10.7],                // %
  ros:       [22.9, 5.9, 5.7, 8.6, 9.8],                 // %
  // DuPont: ÷100 cho asset turn và leverage để chart đẹp
  dupMargin: [22.9, 5.9, 5.7, 8.6, 9.8],                 // %
  dupTurn:   [91, 88, 67, 62, 66],                       // ×100
  dupLev:    [160, 165, 163, 173, 166],                  // ×100
};
```

⚠️ **Đơn vị `price` trong chart = nghìn đồng** (vì scale nhỏ hơn revenue). **Đơn vị `price_current` ở Hero = đồng** (23,650). **Phải consistent trong code.**

## Valuation scenarios (5 cards)

```html
<div class="val-card">
  <div class="name">[METHOD_NAME]</div>      <!-- "PB median 5N" -->
  <div class="price mono [pos/neu/neg]">[VALUE]K</div>
  <div class="upside [pos/neg]">[UPSIDE_PCT]%</div>
  <div class="bar-track"><div class="bar-fill" style="width:[PCT]%"></div></div>
  <div>[FORMULA_NOTE]</div>                   <!-- "BVPS'25 × PB 1.27x" -->
</div>
```

`bar-fill width`: scale theo `VALUE / MAX_VALUE × 100`, max = giá trị kịch bản cao nhất.

## Gauge (giá hợp lý trung tâm)

```html
<div class="gauge-num mono">₫[FAIR_VALUE]K</div>
<div class="gauge-verdict" style="background:[COLOR]">[VERDICT]</div>
<div>Giá hiện <strong>[PRICE_CURRENT]K</strong> → rẻ/đắt hơn ~[DIFF_PCT]%</div>
```

- `VERDICT`: "🟢 UNDERVALUED" (green) / "⚖️ FAIRLY VALUED" (amber) / "🔴 OVERVALUED" (red)

## Khuyến nghị cuối cùng

```html
<div class="kpi-label">Khuyến nghị (9 PP hội tụ)</div>
<div class="[neu/pos/neg]">[RECOMMENDATION]</div>      <!-- "⬆ ACCUMULATE" -->
<div>Dải mục tiêu: [TARGET_LOW] - [TARGET_HIGH] ([UPSIDE_RANGE])</div>
```

Recommendation mapping (từ `vn-valuation-engine`):
- STRONG BUY (>+30%), BUY/ACCUMULATE (+10% to +30%), HOLD (-10% to +10%), REDUCE (-30% to -10%), SELL (<-30%)

## Sources footer

```html
<div>Nguồn: <a href="[VIETSTOCK_URL]">Vietstock</a> ·
  <a href="[CAFEF_URL]">CafeF</a> ·
  <a href="[IR_URL]">BCTC [COMPANY]</a>
</div>
```

## Validation checklist trước khi "Done"

- [ ] Tất cả section có data — **grep raw placeholders** phải trả 0:
  ```bash
  grep -o "{{[A-Z_]*}}" BSR_Complete_Report.html | sort -u
  # Must return empty. If not → inject script bug
  ```
- [ ] Số liệu cross-check với ít nhất 2 nguồn
- [ ] **Market Cap đúng**: fetch từ vnstock `Company.overview()['market_cap']`, KHÔNG tự tính bằng CP cũ
- [ ] **Market Cap format đúng**: "₫199.3K tỷ" hoặc "199,254 tỷ VNĐ" — KHÔNG "₫XB tỷ" (trùng đơn vị)
- [ ] **Số CP nhất quán**: nếu có cổ tức CP gần → dùng số CP mới nhất cho market cap, nhưng dùng số CP **từng năm** cho EPS/BVPS
- [ ] **Split-adjustment check (BẮT BUỘC):** Nếu công ty có split/dividend-stock → verify PE/PB cross-year dùng cùng base (xem `data_pitfalls.md` Bẫy 5B). Back-calc `CP = LNST/EPS` từng năm → nếu CP mismatch > 5% → cần adjust
- [ ] Chart syntax OK (`node --check /tmp/dash.js` returns ✅)
- [ ] `Canvas count` = `new Chart count` (+ 1 nếu có custom canvas candlestick)
- [ ] Mở file local → tất cả charts hiển thị
- [ ] Disclaimer ở footer có cảnh báo "không phải lời khuyên đầu tư"
- [ ] **Rà soát toàn cục**: grep file cho các pattern sai phổ biến (`₫\d+\.?\d*[BMK]\s*tỷ` = trùng đơn vị, số CP cố định xuyên năm)

## ⚠️ Template + inject pattern (lessons learned case BSR 2026)

**Vấn đề:** Dùng f-string Python để generate HTML chứa JavaScript → xung đột brace `{{...}}` (Python f-string escape) với JS object literal `{...}` → JS syntax error khó debug.

**Pattern ĐÚNG (đã verify):**

1. **Tách template HTML tĩnh** (file `.html`) với placeholder `{{TOKEN_NAME}}`
2. **Python script inject** đọc template + replace placeholder bằng string replacement ĐƠN GIẢN (không f-string):
   ```python
   with open('dashboard_template.html') as f: tpl = f.read()
   html = tpl
   simple_tokens = {
       '{{PRICE_NOW}}': f"{price_now:,.0f}",
       '{{FINAL_REC}}': V['final_recommendation'],
       # ... tất cả tokens
   }
   for k, v in simple_tokens.items():
       html = html.replace(k, str(v))
   ```

3. **Token replacement order CRITICAL (bug đã mắc):** Vòng lặp `for k,v in simple_tokens.items()` phải chạy **SAU KHI tất cả token đã được add vào dict**. Nếu add token mới (VD oil correlation) sau vòng lặp → các token đó không được replace → raw `{{TOKEN}}` hiển thị trong dashboard.

   ```python
   # ✅ ĐÚNG: Define tất cả tokens TRƯỚC, replace SAU
   simple_tokens = {...}
   simple_tokens['{{NEW_TOKEN}}'] = value  # OK, thêm trước loop
   for k, v in simple_tokens.items():
       html = html.replace(k, str(v))

   # ❌ SAI: Replace trước, add token sau
   for k, v in simple_tokens.items():
       html = html.replace(k, str(v))
   simple_tokens['{{NEW_TOKEN}}'] = value  # BUG! Không bao giờ được replace
   ```

4. **JSON data injection** cho array/object lớn (chart data, news cards): Dùng pattern `/*TOKEN*/.../**/` trong template + regex replace:
   ```javascript
   // Trong template:
   const DATA_JSON = /*DATA*/{}/**/;
   // Trong Python:
   pattern = r'/\*DATA\*/.*?/\*\*/'
   repl = f'/*DATA*/{json.dumps(value)}/**/'
   html = re.sub(pattern, repl, html, count=1, flags=re.DOTALL)
   ```

5. **Verify cuối cùng (BẮT BUỘC):**
   ```python
   import re
   remaining = set(re.findall(r'{{[A-Z_]+}}', html))
   if remaining:
       print(f"⚠️ WARNING: {len(remaining)} placeholders unreplaced: {remaining}")
   else:
       print("✅ All placeholders replaced")
   ```

6. **JS chart syntax check** — Charts với nested options dễ thiếu/thừa `}`. Auto-fix script:
   ```bash
   node 22_fix_and_verify.js  # tự balance braces cho từng Chart block
   node --check /tmp/dash.js  # verify syntax
   ```

7. **Chart.js arrow function** trong tooltip/scales callback — dùng `function(v){return ...}` thay vì `v => ...` để tránh parser issue trong một số edge cases.

---

## Xref cross-reference links (BẮT BUỘC — v2.2.6 học từ CTD test 7/2026)

> Mỗi section trong text có reference nội bộ ("xem Section N") PHẢI là link clickable.
> ORCL benchmark có 31 xref links. CTD ban đầu có 0 → gap navigation rõ.

### Pattern

```html
<!-- CSS (đã có trong template): -->
a.xref{color:var(--blue);text-decoration:none;border-bottom:1px dotted var(--blue);font-weight:500}
a.xref:hover{background:var(--blue-soft);border-bottom-style:solid}

<!-- HTML usage: -->
<a href="#sec-valuation" class="xref">Section 8</a>
<a href="#sec-risk" class="xref">Section 11</a>
<a href="#sec-bs" class="xref">Section 10</a>
```

### Section number → id mapping

| # | id | # | id | # | id |
|---|---|---|---|---|---|
| 1 | sec-hero | 8 | sec-valuation | 15 | sec-insight |
| 2 | sec-exec | 9 | sec-peer | 16 | sec-moat |
| 3 | sec-biz | 10 | sec-bs | 17 | sec-supply |
| 4 | sec-industry | 11 | sec-risk | 18 | sec-tech |
| 5 | sec-history | 12 | sec-33k | 19 | sec-tech-profile |
| 6 | sec-segment | 13 | sec-scenario | 20 | sec-analyst |
| 7 | sec-thesis | 14 | sec-checklist | 21 | sec-glossary / 22 sec-source |

### Verify trước deploy

```bash
XREF_COUNT=$(grep -c 'class="xref"' [output].html)
[ "$XREF_COUNT" -ge 10 ] || echo "❌ FAIL: chỉ $XREF_COUNT xref links (minimum 10)"
```

### Chỗ BẮT BUỘC có xref

- Exec Summary → reference sections chi tiết (history, BS, valuation)
- Risk Matrix → reference scenario analysis
- Thesis KPI → reference checklist
- Valuation → reference analyst targets
- Technical → reference valuation (divergence)
- Disclaimer → reference data quality
- Glossary → reference source appendix
- Mỗi insight → reference risk matrix
