---
name: vn-technical-analysis
description: Phân tích kỹ thuật cổ phiếu VN từ data giá THẬT (vnstock API) theo 2 mode. Mode ACTIVE — tính MA/RSI/MACD/Bollinger/Beta/Correlation, phát hiện candlestick & chart patterns thật, divergence check thành thật, render biểu đồ nến + volume, đưa Tech Score → Verdict BUY/SELL. Mode PROFILE — phân tích hồ sơ giá-khối lượng định lượng (28 block methodology từ market_stats: volatility, drawdown, VPCI/OBV/CMF, effort-result Wyckoff, volume-at-price, tail risk VaR/ES, pattern scoring, archetype), ngôn ngữ phi-tư-vấn (neutral_descriptive_non_advice). Use khi user hỏi "phân tích kỹ thuật", "có nên mua/bán giờ" (ACTIVE), "hồ sơ cổ phiếu / personality / hành vi giá-khối lượng" (PROFILE), "beta/correlation", "mô hình nến/giá". Cốt lõi = data từ vnstock (VCI source), KHÔNG BAO GIỜ ngụy tạo/mô phỏng data giá.
---

# VN Technical Analysis

Phân tích kỹ thuật từ **data giá thực vnstock** — trả lời câu hỏi "khi nào mua/bán" (timing, mode ACTIVE) hoặc "hồ sơ hành vi giá-khối lượng" (mode PROFILE) mà fundamental và news không trả lời được.

## Design system (refactor 2026-06)

Cả 2 template (`technical_template.html` mode ACTIVE, `profile_template.html` mode PROFILE) giờ dùng **`../_viz-shared/`** design system:
- CSS/JS shared đã `inject.py` inline sẵn (single-file, không phụ thuộc runtime)
- Cả 2 template đã **tokenize** (`{{TECH_CANDLES}}`, `{{TECH_RSI}}`, `{{ROLLING_DATA}}`, ...) — fill qua `str.replace` thuần, KHÔNG edit inline
- Candlestick chart qua `viz.renderCandlestick(canvas, {candles,volumes,ma20,ma50,high52w,low52w,months})` (trước đây ~100 dòng trùng lặp)
- Chart.js qua `viz.chart(id, spec)` registry; navigation qua `viz.setupNav()`
- Theme (Bloomberg/Corporate) = `data-theme="..."` attribute trên `<html>`

Sửa design chung: edit `../_viz-shared/*.{css,js}` → chạy `python3 ../_viz-shared/inject.py` → tái sinh templates.

## ⚠️ Nguyên tắc tối thượng: KHÔNG NGỤY TẠO DATA

**Tuyệt đối không** tự tạo chuỗi giá OHLC "mô phỏng" rồi trình bày như phân tích thật. Đây là lỗi nghiêm trọng đã từng xảy ra. Data giá PHẢI đến từ:

1. **vnstock (VCI source)** — nguồn chính, ưu tiên #1
2. **Yahoo Finance API** — backup (CORS issue khi gọi từ browser)
3. **TCBS API** — backup thứ cấp

Nếu không fetch được data → **nói thẳng "không có data"**, KHÔNG tự bổ sung bằng mô phỏng.

## 🎚️ Chọn mode (ACTIVE vs PROFILE)

Skill có 2 mode phân tích. **Mặc định = ACTIVE** (không phá hành vi cũ). Chuyển sang PROFILE khi user hỏi rõ "hồ sơ / personality / hành vi giá-khối lượng / mô tả" hoặc khi cần context phi-tư-vấn cho fundamental/valuation.

| | **Mode ACTIVE** (cũ) | **Mode PROFILE** (mới) |
|---|---|---|
| **Câu hỏi trả lời** | "Có nên mua/bán giờ? Timing?" | "Hồ sơ cổ phiếu này thế nào? Personality?" |
| **Ngôn ngữ** | Tech Score → Verdict BUY/SELL, "bullish/bearish", "tín hiệu" | `neutral_descriptive_non_advice` — mô tả, KHÔNG verdict |
| **Output** | HTML dashboard + JSON (tech_score, verdict) | Markdown narrative + JSON profile (28 block subset) |
| **Indicators** | MA/RSI/MACD/Bollinger | 15 block định lượng: volatility, drawdown, VPCI/OBV/CMF, effort-result, VAP, VaR/ES, PVI/NVI, regime |
| **Patterns** | Double Bottom, Channel, Candlestick, Divergence (thủ công) | 8 setup heuristic + archetype + behavior (scoring 0-100) |
| **So sánh** | Beta/Correlation vs VNINDEX/VN30 | + best-fit benchmark, regime, drawdown similarity, peer percentile |
| **Guardrail** | "Cổ phiếu chu kỳ" note | Bắt buộc 4 điểm non-conclusion + metric guardrail |
| **Reference** | `indicators.md`, `pattern_detection.md` | `stock_profile_blocks.md`, `pattern_scoring.md`, `metric_guardrails.md` |
| **Dependency** | Chỉ vnstock | Chỉ vnstock |

**Khi nào dùng mode nào:**
- **ACTIVE**: user hỏi "có nên mua/bán", "timing", "tín hiệu vào/ra lệnh", "overbought/oversold", "MACD/RSI". Cần verdict rõ ràng.
- **PROFILE**: user hỏi "hồ sơ", "personality", "hành vi giá", "đặc điểm cổ phiếu", "so với lịch sử của chính nó", "dòng tiền". Cần mô tả sâu, không khuyến nghị.
- **Không rõ**: hỏi lại user, hoặc dùng ACTIVE (mặc định).

> **Quan trọng:** KHÔNG trộn ngôn ngữ 2 mode. Mode PROFILE KHÔNG bao giờ xuất "BUY/SELL/bullish/tín hiệu". Mode ACTIVE KHÔNG xuất guardrail phi-tư-vấn dài dòng.

---

## Workflow mode ACTIVE (4 bước)

### Bước 1: Fetch data giá thực từ vnstock

Tham khảo `references/vnstock_usage.md` + `vn-financial-data-collector/references/vnstock_api.md` cho code đầy đủ. Tóm tắt:

```python
from vnstock.api.quote import Quote
from vnstock.api.company import Company
from vnstock.api.financial import Finance

# Giá 52 tuần
q = Quote(symbol='HPG', source='VCI')
df = q.history(start='YYYY-MM-DD', end='YYYY-MM-DD', interval='1W')
# ⚠️ Giá = NGHÌN đồng (19.38 = 19,380 đ)
df = df.dropna(subset=['close'])

# Overview — vốn hóa, số CP, target_price analyst (cho context)
c = Company(symbol='HPG', source='VCI')
info = c.overview()
# info['market_cap'], info['issue_share'], info['target_price'],
# info['highest_price1_year'], info['lowest_price1_year']

# Ratios — PE/PB/EV-EBITDA tính sẵn (verify vs tự tính)
f = Finance(symbol='HPG', source='VCI')
ratios = f.ratio()
# ratios có: 'P/E','P/B','P/S','EV/EBITDA','ROE (%)','ROA (%)',
#            'Số CP lưu hành (triệu)','Vốn hóa'
```

**Lấy luôn VNINDEX + VN30** để tính tương quan:
```python
q_vni = Quote(symbol='VNINDEX', source='VCI')
df_vni = q_vni.history(start=..., end=..., interval='1W')
```

⚠️ **Bẫy đơn vị:** vnstock trả giá bằng nghìn đồng (19.38), KHÔNG phải đồng (19,380). Phải ×1000 khi tính toán.

### Bước 2: Tính indicators thực

Tham khảo `references/indicators.md` cho công thức + code Node.js/Python. Tóm tắt indicators bắt buộc:

| Indicator | Công thức | Khi nào quan trọng |
|---|---|---|
| **MA10/20/50** | Trung bình động 10/20/50 tuần | Xu hướng ngắn/trung hạn |
| **RSI(14)** | Relative Strength Index | < 30 quá bán, > 70 quá mua |
| **MACD** | EMA12 - EMA26, Signal = EMA9 | Bullish/bearish crossover |
| **Bollinger Bands** | MA20 ± 2σ | Overbought/oversold + breakout |
| **Beta** | Cov(stock,market)/Var(market) | Độ rủi ro vs thị trường |
| **Correlation** | Pearson(stock, index) | Mức độ liên quan thị trường |

### Bước 3: Phát hiện patterns — CHỈ KHI CÓ EVIDENCE

Tham khảo `references/pattern_detection.md` cho code phát hiện tự động. **Quy tắc thành thật:**

- ✅ Double Bottom: 2 đáy cách nhau ≥5 tuần, chênh <3% → flag là "TIỀM NĂNG", cần confirm
- ✅ Descending/Ascending Channel: fit trendline qua swing highs/lows → flag nếu slope rõ
- ✅ Candlestick: Hammer, Marubozu, Doji, Engulfing → flag từng nến với điều kiện body/wick
- ✅ Divergence: check 2 đáy giá + 2 đáy RSI → CHỈ flag nếu giá giảm + RSI tăng (bullish) hoặc ngược lại
- ❌ **KHÔNG** claim pattern nếu data không show — nói thẳng "không có"

### Bước 4: Render HTML

Copy template `assets/technical_template.html` (cùng phong cách dashboard). Cấu trúc:

1. **Tech Verdict Card** — score -6→+6, verdict pill (STRONG SELL → STRONG BUY)
2. **Candlestick + Volume chart** — custom canvas (Chart.js không native candlestick)
3. **4 Indicator cards** — giá hiện tại, perf 1Y, RSI, MACD
4. **Price + MA chart** + **RSI chart** + **MACD chart** (Chart.js)
5. **Correlation section** — chart 3 đường (stock vs VNINDEX vs VN30) + Beta/Alpha cards
6. **Support/Resistance zones** — swing highs/lows thực
7. **Patterns section** — chỉ patterns có evidence (Double Bottom, Channel, Candlesticks)
8. **Divergence check card** — kết quả thành thật (có hoặc KHÔNG có)
9. **Trading Strategy Insight** — 3 kịch bản (tích cực/trung tính/tiêu cực)
10. **Minh bạch dữ liệu card** — ghi rõ nguồn vnstock + patterns đã detect

## Output JSON

```json
{
  "ticker": "HPG",
  "data_source": "vnstock (VCI)",
  "data_period": "2025-06-22 to 2026-06-21",
  "price_current": 23600,
  "performance_1y_pct": 21.8,
  "high_52w": 27540,
  "low_52w": 19120,
  "indicators": {
    "ma10": 24218, "ma20": 24170, "ma50": 24153,
    "rsi14": 47.8,
    "macd": -19, "signal": 135, "macd_trend": "bearish",
    "price_vs_ma10": "below", "price_vs_ma20": "below", "price_vs_ma50": "below"
  },
  "correlation": {
    "beta_vnindex": 0.83, "beta_vn30": 0.85,
    "corr_vnindex": 0.61, "corr_vn30": 0.65,
    "alpha_1y": -9.2, "outperform_market": false
  },
  "patterns_detected": [
    {"type": "double_bottom", "status": "potential", "neckline": 25710, "target": 28300},
    {"type": "descending_channel", "status": "active", "trend": "bearish"},
    {"type": "hammer", "date": "2026-05-10", "signal": "bullish_reversal_potential"},
    {"type": "marubozu_bearish", "date": "2026-06-07", "signal": "strong_bearish_momentum"}
  ],
  "divergence": {
    "has_divergence": false,
    "note": "RSI và giá cùng hướng ở 2 đáy gần nhất — không có divergence"
  },
  "tech_score": -4,
  "verdict": "SELL/REDUCE",
  "support_resistance": {
    "resistance": [{"level": "R1", "price": 27540, "note": "52W high"}, {"level": "R2", "price": 24153, "note": "MA50"}],
    "support": [{"level": "S1", "price": 24218, "note": "MA10"}, {"level": "S2", "price": 19120, "note": "52W low"}]
  }
}
```

## Tech Score decision table

Tính score từ 6 signals (mỗi signal ±1):

| Signal | +1 (bullish) | -1 (bearish) |
|---|---|---|
| Giá vs MA10 | Trên | Dưới |
| Giá vs MA20 | Trên | Dưới |
| Giá vs MA50 | Trên | Dưới |
| RSI | > 55 | < 45 |
| MACD vs Signal | Trên (bullish) | Dưới (bearish) |
| BB Position | > 50% | < 50% |

| Score | Verdict (TECHNICAL only — KHÔNG phải khuyến nghị giao dịch) |
|---|---|
| +4 đến +6 | TECHNICAL STRONG BULLISH |
| +1 đến +3 | TECHNICAL BULLISH |
| -1 đến 0 | TECHNICAL NEUTRAL |
| -3 đến -2 | TECHNICAL BEARISH |
| -6 đến -4 | TECHNICAL STRONG BEARISH |

**⚠️ GUARDRAIL BẮT BUỘC** (v2.2.0 — học từ us-equity-research):
- **KHÔNG dùng "STRONG BUY/BUY/SELL/STRONG SELL"** — đó là khuyến nghị giao dịch, technical alone không đủ.
- Dùng "TECHNICAL STRONG BULLISH/BEARISH" — mô tả trạng thái kỹ thuật, không phải lệnh.
- **Verdict technical phải kết hợp fundamental**: "Tech Score +5 NHƯNG valuation đắt → KHÔNG kết luận bullish cho đầu tư 3-5 năm."
- **Score bearish không tự động = "bán"**: Cổ phiếu chu kỳ ở đáy có thể là accumulation zone cho value investor. Kết hợp với fundamental (skill `vn-valuation-engine`) để decide.
- Technical = 1 input, không phải verdict cuối. Final verdict = fundamental + valuation + technical.

## Phối hợp với skills khác

- **Data fundamental**: `vn-financial-data-collector`
- **Định giá**: `vn-valuation-engine` (cơ bản vs kỹ thuật divergence)
- **Dashboard**: `vn-research-dashboard` (ghép technical vào report)
- **News**: `vn-news-digest`

> **Mode PROFILE** bổ sung context hành vi giá-khối lượng cho `vn-fundamental-analysis`/`vn-valuation-engine` **mà không đưa khuyến nghị** — profile trả lời "cổ phiếu này hành xử thế nào", fundamental/valuation trả lời "nó đáng bao nhiêu".

---

## Workflow mode PROFILE (5 bước)

Phân tích hồ sơ cổ phiếu định lượng theo methodology `market_stats` — **"What I See"**, mô tả lịch sử, KHÔNG verdict. Chi tiết công thức từng block xem `references/stock_profile_blocks.md`, pattern/archetype xem `references/pattern_scoring.md`, ngôn ngữ guardrail xem `references/metric_guardrails.md`.

### Bước 1: Fetch data thực từ vnstock (daily OHLCV)

```python
from vnstock.api.quote import Quote
import pandas as pd

# ⚠️ Cần DAILY (interval='1D'), KHÔNG phải weekly như mode active
# Lấy ~2 năm (≈500 phiên) để có đủ sample cho rolling 252 + percentile
q = Quote(symbol='HPG', source='VCI')
df = q.history(start='2024-01-01', end='2026-06-24', interval='1D')
df = df.dropna(subset=['close']).sort_values('time')

# ⚠️ Giá = NGHÌN đồng → value = close * volume * 1000 (ra đồng)
rows = []
for _, r in df.iterrows():
    rows.append({
        "date": str(r['time'])[:10],
        "open": float(r['open']), "high": float(r['high']),
        "low": float(r['low']), "close": float(r['close']),
        "volume": float(r['volume']),
        "value": float(r['close']) * float(r['volume']) * 1000,  # đồng
        "range_pct": (float(r['high']) - float(r['low'])) / float(r['close']) * 100,
    })

# VNINDEX + VN30 (cho benchmark/regime)
q_vni = Quote(symbol='VNINDEX', source='VCI')
vni_rows = [...]  # cùng format
q_vn30 = Quote(symbol='VN30', source='VCI')
vn30_rows = [...]
```

⚠️ **Bẫy**: nếu `< 60 phiên` → trả error "không đủ dữ liệu profile". Cần ≥252 phiên cho đầy đủ block 1-year.

### Bước 2: Tính 15 block profile

Import helpers + các block từ `references/stock_profile_blocks.md`. Mỗi block nhận `rows` (daily OHLCV đã có `value`). Tính theo thứ tự:

```python
# (code đầy đủ trong references/stock_profile_blocks.md)
profile = {
    "price_behavior_profile": price_behavior_profile(rows),
    "volatility_profile": volatility_profile(rows),
    "drawdown_profile": drawdown_profile(rows),
    "liquidity_profile": liquidity_profile(rows),
    "return_distribution_profile": return_distribution_profile(rows),
    "tail_risk_profile": tail_risk_profile(rows),
    "liquidity_risk_profile": liquidity_risk_profile(rows),
    "volume_price_profile": volume_price_profile(rows),
    "volume_price_confirmation_profile": vpci_profile(rows),
    "money_flow_pressure_profile": money_flow_profile(rows),
    "effort_result_profile": effort_result_profile(rows),
    "high_volume_behavior_profile": high_volume_behavior_profile(rows),
    "pvi_nvi_participation_profile": pvi_nvi_profile(rows),
    "volume_at_price_profile": volume_at_price_profile(rows),
}
# Benchmark blocks (cần VNINDEX + VN30)
rs = relative_strength_profile(rows, vni_rows, {"VNINDEX": vni_rows, "VN30": vn30_rows})
profile.update(rs)
profile["regime_profile"] = regime_profile(rows, vni_rows)
# industry_peer_profile (nếu có data ngành) — optional
```

### Bước 3: Pattern scoring + archetype

Xem `references/pattern_scoring.md`. Tính được:
- 8 setup heuristic chiều tăng (score 0-100, status, reader_note)
- 5 pattern family classification
- Stock archetype (4 loại: trend_following / accumulation_breakout / trap_prone / mixed)

```python
setups = scan_setups(rows)  # top 6, sort theo completion_score desc
archetype = estimate_archetype(setups, profile["high_volume_behavior_profile"])
```

### Bước 4: Sinh narrative non-advice

Tuân thủ NGHIÊM `references/metric_guardrails.md`:

1. Tra `metric_dictionary()` cho mỗi metric → dùng `label_vi` + kèm `guardrail`.
2. Tra `CONSUMER_LABELS` cho status kỹ thuật → Việt.
3. Áp `scrub_copy()` cho text template.
4. Kiểm `forbidden` list — không lọt "bullish/bearish/tín hiệu/khuyến nghị".
5. Dịch thuật ép buộc (Drawdown→Mức giảm...).
6. **Cuối report** thêm `non_conclusion_panel()` (4 điểm, ít nhất điểm 1+2 bắt buộc).

### Bước 5: Output — Dashboard HTML single-page + JSON

**Output chính: dashboard HTML** — dùng `assets/profile_template.html` (single-page, dark theme, Chart.js). Pattern hấp thụ từ skill `longform` (component + chart recipe). Xem `references/profile_render.md` cho:
- Bảng mapping đầy đủ profile JSON field → `{{TOKEN}}`
- Format 4 chart data object (rolling/dist/VAP/benchmark)
- Non-advice language check + QA checklist

```python
import shutil, json
# 1. Copy template
shutil.copy("assets/profile_template.html", f"{output_dir}/{symbol}_profile.html")
html = open(f"{output_dir}/{symbol}_profile.html").read()

# 2. Build token map từ profile JSON (Bước 2-3) + rows
TOKEN_MAP = {
    "TICKER": symbol,
    "COMPANY_NAME": company_name,  # từ vnstock overview
    "LATEST_CLOSE_DISPLAY": f"{latest_close*1000:,.0f}",  # nghìn→đồng
    # ... full map trong references/profile_render.md
    "ROLLING_DATA": json.dumps(rolling_obj, ensure_ascii=False),
    "DIST_DATA": json.dumps(dist_obj, ensure_ascii=False),
    "VAP_DATA": json.dumps(vap_obj, ensure_ascii=False),
    "BENCH_DATA": json.dumps(bench_obj, ensure_ascii=False),
}
# 3. String replace (KHÔNG f-string/.format — JS có {} sẽ vỡ)
for token, value in TOKEN_MAP.items():
    html = html.replace("{{" + token + "}}", str(value))
open(f"{output_dir}/{symbol}_profile.html", "w").write(html)
```

Cấu trúc dashboard (7 section, scroll single-page, không minimap/chapter):
1. **Hero** — ticker, giá, 6 KPI strip (return 1M/3M/1Y, HV60, mức giảm, Beta·R²)
2. **Đọc như** (profile read card) — archetype primary + reader_note + icon. **KHÔNG verdict BUY/SELL.**
3. **Vị trí giá & biến động** — rolling percentile chart + bảng HV20/60/120/252
4. **Mức giảm & rủi ro đuôi** — distribution histogram chart + VaR/ES table
5. **Dòng tiền & xác nhận** — VPCI/CMF/HVB cards + guardrail
6. **So VNINDEX** — base-100 line chart (resample monthly) + beta/corr/R² table
7. **Volume-at-price** — horizontal bar chart + POC/acceptance
8. **Mẫu hình & archetype** — setups table + reader_note
9. **Lưu ý khi đọc** — 4 điểm non-conclusion (callout warn) + minh bạch dữ liệu

**QA bắt buộc** (xem `references/profile_render.md`):
```bash
grep -oE "{{[A-Z_0-9]+}}" {output}.html | sort -u           # Check 1: trống (không sót token)
# canvas count == new Chart count (Check 2, =4)
# Check 3: JS syntax — extract <script> ra tempfile rồi node --check (xem profile_render.md QA)
grep -iE "bullish|bearish|tín hiệu|khuyến nghị|nên mua|nên bán" {output}.html | grep -v "<script>"  # Check 4: trống
```

**Output phụ: JSON** (schema `vn-technical-profile-v1`) — giữ lại cho pipeline downstream, schema như Bước 2-3 output. Markdown narrative ngắn có thể kèm nếu user muốn copy text.

**Output JSON** (schema `vn-technical-profile-v1`):
```json
{
  "schema": "vn-technical-profile-v1",
  "generated_at": "2026-06-24T...",
  "language_policy": "neutral_descriptive_non_advice",
  "symbol": "HPG",
  "stock_identity": {"symbol": "HPG", "sample_size": 480},
  "price_behavior_profile": {
    "latest_close": 23600, "return_1m_pct": 2.1, "return_1y_pct": 8.4,
    "high_52w": 27540, "low_52w": 19120,
    "distance_from_52w_high_pct": -14.2,
    "rolling_returns": [{"window": 63, "current_return_pct": 3.2, "percentile": 62, "...": "..."}],
    "interpretation_guardrail": "Hành vi giá là quan sát lịch sử; không phải dự báo xu hướng tương lai."
  },
  "volatility_profile": {"hv60_pct": 34.5, "hv60_percentile_1y": 45, "...": "..."},
  "drawdown_profile": {"current_drawdown_pct": -8.1, "max_drawdown_pct": -28.4, "...": "..."},
  "volume_price_confirmation_profile": {"vpci_latest": 0.012, "confirmation_label": "giá-volume cùng xác nhận", "...": "..."},
  "money_flow_pressure_profile": {"cmf_20d": 0.04, "money_flow_label": "áp lực tiền dương", "...": "..."},
  "setups": [{"pattern_id": "triangles_ascending", "pattern_name": "Tam giác tăng", "completion_score": 71, "setup_status": "đang hình thành", "...": "..."}],
  "non_conclusion": [
    "Không kết luận đây là khuyến nghị hoặc lời gọi giao dịch.",
    "Tỷ lệ trong quá khứ không đảm bảo lặp lại trong tương lai."
  ]
}
```

---

## Tham khảo

**Mode ACTIVE (cũ):**
- `references/vnstock_usage.md` — Code Python fetch giá + indicators (Quote, history, dropna, đơn vị nghìn đồng)
- `references/indicators.md` — Công thức + code Node.js/Python cho MA/RSI/MACD/Bollinger/Beta/Correlation
- `references/pattern_detection.md` — Code phát hiện Double Bottom, Channel, Candlestick, Divergence (với điều kiện evidence rõ)
- `assets/technical_template.html` — Template HTML (candlestick canvas + Chart.js + correlation)

**Mode PROFILE (mới):**
- `references/stock_profile_blocks.md` — 17 block profile cốt lõi (price_behavior, volatility, drawdown, VPCI/OBV/CMF, effort-result, VAP, VaR/ES, PVI/NVI, regime) + code Python (methodology từ dashboard phân tích nội bộ, đã port). **100% portable với vnstock.**
- `references/pattern_scoring.md` — 8 setup detection heuristic (chiều tăng) + 5 pattern family + 4 stock archetype. **100% portable với vnstock.**
- `references/metric_guardrails.md` — 13 metric dictionary (label_vi + guardrail) + CONSUMER_LABELS + scrubCopy rules + 4 điểm non-conclusion + bảng dịch thuật ép buộc + cấm list + glossary 30 term. **100% portable.**
- `assets/profile_template.html` — **Template dashboard HTML single-page** (mode PROFILE). Dark theme + Chart.js (4 chart: rolling/dist/VAP/benchmark). Dùng `{{TOKEN}}` placeholder. Đồng nhất visual với `technical_template.html`. Pattern hấp thụ từ skill `longform`.
- `references/profile_render.md` — Recipe map profile JSON → `{{TOKEN}}` + format 4 chart data + non-advice language check + QA checklist. **Bước 5 bắt buộc đọc.**
