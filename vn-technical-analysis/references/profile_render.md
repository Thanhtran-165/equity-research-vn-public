# Profile Render — Recipe map profile JSON → dashboard HTML

> Reference cho **mode PROFILE Bước 5**. Map mỗi block trong profile JSON → component/chart trong `assets/profile_template.html`. Kèm format chart data + QA checklist.
>
> Pattern hấp thụ từ `longform/chart_recipes.md` (Chart.js recipe) + `longform/components.md` (component) + đồng nhất visual với `technical_template.html` (mode ACTIVE).

## Mục lục
1. [Workflow render](#workflow)
2. [Token fill map](#tokens) — JSON field → `{{TOKEN}}`
3. [Chart data format](#charts) — 4 chart object
4. [Non-advice language check](#lang)
5. [QA checklist](#qa)

---

## Workflow render <a name="workflow"></a>

> **Nguyên tắc ngôn ngữ**: dashboard dùng tiếng Việt đời thường cho người đọc phổ thông. Thuật ngữ kỹ thuật (VaR/ES/CMF/VPCI/HV...) chỉ xuất hiện trong ngoặc hoặc tooltip — KHÔNG làm label chính. Token name trong code GIỮ NGUYÊN (vd `{{VAR_95}}`) vì AI đọc, chỉ đổi **label hiển thị** trong template. Bảng tra đổi ngôn ngữ ở cuối file ([mục Ngôn ngữ](#lang-map)).

```python
# Input: profile JSON (từ Bước 2-3) + rows OHLCV + benchmark rows
# 1. Copy template
import shutil
shutil.copy("assets/profile_template.html", f"{output_dir}/{symbol}_profile.html")

# 2. Đọc template, fill token
html = open(f"{output_dir}/{symbol}_profile.html").read()
# string replace đơn giản (KHÔNG f-string — ký tự {} trong JS sẽ vỡ)
for token, value in TOKEN_MAP.items():
    html = html.replace("{{" + token + "}}", str(value))

# 3. Ghi ra
open(f"{output_dir}/{symbol}_profile.html", "w").write(html)
```

⚠️ **Quan trọng**: dùng `str.replace`, KHÔNG dùng f-string hay `.format()` — vì template có nhiều `{` `}` trong JS (object literal, Chart.js config) sẽ bị hiểu nhầm.

---

## Token fill map <a name="tokens"></a>

Bảng mapping từ profile JSON field → `{{TOKEN}}`. Mỗi token = 1 chuỗi đã format sẵn (KHÔNG raw number).

### Identity + hero
| Token | Nguồn JSON | Format ví dụ |
|---|---|---|
| `{{TICKER}}` | `symbol` | `HPG` |
| `{{COMPANY_NAME}}` | (từ vnstock overview) | `Hòa Phát Group` |
| `{{EXCHANGE_INDUSTRY}}` | (overview) | `HOSE · Sản xuất thép` |
| `{{LATEST_CLOSE_DISPLAY}}` | `price_behavior.latest_close × 1000` | `23,450` (đồng, có dấu phẩy) |
| `{{LATEST_DATE}}` | `price_behavior.latest_date` | `24/06/2026` |
| `{{SAMPLE_SIZE}}` | `stock_identity.sample_size` | `585` |
| `{{SAMPLE_PERIOD}}` | `sample_start → sample_end` | `19/02/2024 → 24/06/2026` |
| `{{GENERATED_AT}}` | `generated_at` | `2026-06-24T06:25Z` |
| `{{HERO_GRADIENT}}` | theo archetype (xem bảng dưới) | `linear-gradient(135deg,rgba(139,92,246,0.12),rgba(6,182,212,0.08))` |

### Hero gradient theo archetype
| Archetype | HERO_GRADIENT |
|---|---|
| trend_following | `linear-gradient(135deg,rgba(6,182,212,0.15),rgba(139,92,246,0.08))` (cyan) |
| accumulation_breakout | `linear-gradient(135deg,rgba(139,92,246,0.12),rgba(236,72,153,0.08))` (purple, mặc định) |
| trap_prone | `linear-gradient(135deg,rgba(255,77,109,0.1),rgba(251,191,24,0.06))` (red+amber) |
| mixed / no_current_setup | `linear-gradient(135deg,rgba(168,85,247,0.1),rgba(251,191,24,0.06))` (neutral) |

### KPI strip (6 ô)
| Token | Nguồn | Helper class |
|---|---|---|
| `{{KPI_RETURN_1M}}` | `return_1m_pct` | `.pos` nếu >0, `.neg` nếu <0 |
| `{{KPI_RETURN_3M}}` | `return_3m_pct` | tương tự |
| `{{KPI_RETURN_1Y}}` | `return_1y_pct` | tương tự |
| `{{KPI_RETURN_1M_CLASS}}` / `_3M_` / `_1Y_` | — | `pos` / `neg` |
| `{{KPI_HV60}}` | `volatility.hv60_pct` | `29.7%` |
| `{{KPI_HV60_PERCENTILE}}` | `hv60_percentile_1y` | `12` |
| `{{KPI_DRAWDOWN}}` | `drawdown.current_drawdown_pct` | `-13.4%` |
| `{{KPI_UNDERWATER}}` | `current_underwater_days` | `192` |
| `{{KPI_BETA}}` | `benchmark_vs_vnindex_252d.beta` | `0.76` |
| `{{KPI_R2}}` | `r2` | `0.29` |
| `{{KPI_R2_LABEL}}` | R² <0.40→`low`, 0.40-0.70→`medium`, >0.70→`high` | `low` |

### Profile read card (archetype)
| Token | Nguồn | Format |
|---|---|---|
| `{{ARCHETYPE_PRIMARY}}` | `archetype.primary` | `accumulation_breakout` |
| `{{ARCHETYPE_PRIMARY_VI}}` | map → Việt | `Tích lũy - thoát nền` |
| `{{ARCHETYPE_NOTE}}` | `archetype.reader_note` | nguyên văn |
| `{{ARCHETYPE_ICON}}` | theo archetype | `📐` / `🧱` / `⚠️` / `🔀` / `❓` |

Map archetype → icon + tên Việt:
| primary | icon | primary_vi |
|---|---|---|
| trend_following | 📈 | Tiếp diễn |
| accumulation_breakout | 🧱 | Tích lũy - thoát nền |
| trap_prone | ⚠️ | Dễ bẫy |
| mixed | 🔀 | Pha trộn |
| no_current_setup | ❓ | Chưa rõ |

### Section: Biểu đồ nến & khối lượng (mới, ở đầu — sau profile read card)
| Token | Nguồn | Format |
|---|---|---|
| `{{CANDLESTICK_DATA}}` | JSON array `{d,o,h,l,c,v}` — **~120 phiên gần nhất** (KHÔNG lấy hết 585, chart sẽ quá dày). Giá = nghìn đồng (như vnstock), `v` = triệu cổ phiếu (`volume/1e6`). | `[{"d":"2026-01-02","o":23.1,"h":23.5,"l":22.9,"c":23.4,"v":7.5},...]` |
| `{{MA20_DATA}}` | array MA20 cùng độ dài candles, `null` cho 19 phiên đầu (chưa đủ) | `[null,...,null,22.8,22.9,...]` |
| `{{MA50_DATA}}` | array MA50, `null` cho 49 phiên đầu | `[null,...]` |
| `{{HIGH52W_PRICE}}` | `price_behavior.high_52w` (nghìn đồng, KHÔNG ×1000) | `27.09` |
| `{{LOW52W_PRICE}}` | `low_52w` | `19.97` |
| `{{CHART_MONTHS}}` | JSON array label tháng cho trục X (~6-8 label) | `["1/26","2/26","3/26","4/26","5/26","6/26"]` |
| `{{SAMPLE_LAST_N}}` | số phiên hiển thị (120 hoặc tùy) | `120` |

```python
def build_candlestick_data(rows, n=120):
    """Lấy n phiên gần nhất, tính MA20/MA50, trả candles + ma20 + ma50."""
    recent = rows[-n:]
    closes = [r["close"] for r in rows]
    candles = []
    for r in recent:
        candles.append({"d": r["date"], "o": round(r["open"],2), "h": round(r["high"],2),
                        "l": round(r["low"],2), "c": round(r["close"],2),
                        "v": round(r["volume"]/1e6, 2)})  # triệu CP
    # MA20/MA50 trên TOÀBỘ rows rồi cắt n cuối (để MA đầu recent không null nhiều)
    def sma(arr, w):
        out = []
        for i in range(len(arr)):
            if i < w-1: out.append(None)
            else: out.append(round(sum(arr[i-w+1:i+1])/w, 2))
        return out
    ma20 = sma(closes, 20)[-n:]
    ma50 = sma(closes, 50)[-n:]
    # Months labels
    months = []
    seen = set()
    for r in recent:
        m = r["date"][:7]
        if m not in seen:
            seen.add(m)
            months.append(f"{m[5:]}/{m[2:4]}")
    return candles, ma20, ma50, months[-8:] if len(months) > 8 else months
```

⚠️ **Quan trọng**: candlestick vẽ bằng **custom Canvas 2D** (KHÔNG phải Chart.js) — port từ `technical_template.html`. Vì vậy **canvas count ≠ new Chart count** nữa: Check 2 QA phải điều chỉnh (xem [QA](#qa)).

### Section 1: Vị trí giá
| Token | Nguồn | Format |
|---|---|---|
| `{{PRICE_DIST_HIGH}}` | `distance_from_52w_high_pct` | `-13.4%` |
| `{{PRICE_DIST_LOW}}` | `distance_from_52w_low_pct` | `+17.4%` |
| `{{HV20}}` / `{{HV60_DETAIL}}` / `{{HV120}}` / `{{HV252}}` | volatility | `25.1%` |
| `{{RANGE_MEDIAN_63D}}` | `range_pct_median_63d` | `1.51%` |

### Section 2: Mức giảm & rủi ro
| Token | Nguồn |
|---|---|
| `{{DRAWDOWN_CURRENT}}` | `drawdown.current_drawdown_pct` |
| `{{DRAWDOWN_MAX}}` | `max_drawdown_pct` |
| `{{UNDERWATER_DAYS}}` | `current_underwater_days` |
| `{{VAR_95}}` / `{{VAR_99}}` / `{{ES_95}}` | `tail_risk` |
| `{{DOWN_5PCT_DAYS}}` | `down_5pct_days_1y` |

### Section 3: Dòng tiền
| Token | Nguồn |
|---|---|
| `{{VPCI_VALUE}}` | `vpci_latest` (3 số thập phân) |
| `{{VPCI_PERCENTILE}}` | `vpci_percentile_1y` |
| `{{CONFIRMATION_LABEL}}` | `confirmation_label` |
| `{{CMF_20}}` / `{{CMF_60}}` | `cmf_20d` / `cmf_60d` |
| `{{CMF_CLASS}}` | `.neg` nếu <0, `.pos` nếu >0 |
| `{{CMF_COLOR_TOKEN}}` | `red` / `green` |
| `{{MONEY_FLOW_LABEL}}` | `money_flow_label` |
| `{{HVB_COUNT}}` | `high_volume_behavior.event_count_1y` |
| `{{HVB_MEDIAN}}` | `median_forward_20d_pct` |
| `{{HVB_LABEL}}` | `post_high_volume_label` |

### Section 4: So VNINDEX
| Token | Nguồn |
|---|---|
| `{{BENCH_TABLE_ROWS}}` | build `<tr><td>60D</td><td>0.40</td><td>0.31</td><td class="neg">0.10</td></tr>...` 3 dòng (60/252) |
| `{{STOCK_RETURN_252}}` | `benchmark_vs_vnindex_252d.stock_return_pct` |
| `{{BENCH_RETURN_252}}` | `benchmark_return_pct` |
| `{{REL_RETURN_252}}` | `relative_return_pct` |
| `{{REL_RETURN_CLASS}}` | `neg` nếu <0, `pos` nếu >0 |

### Section 5: Volume-at-price
| Token | Nguồn |
|---|---|
| `{{POC_BIN}}` | bin index có volume cao nhất |
| `{{CURRENT_BIN}}` | bin chứa giá hiện tại |
| `{{VAP_CONCENTRATION}}` | tổng share% top-3 bins |
| `{{ACCEPTANCE_LABEL}}` | `acceptance_label` |

### Section 6: Mẫu hình
| Token | Nguồn |
|---|---|
| `{{SETUPS_TABLE_ROWS}}` | build rows từ `setups[]` (xem helper) |
| `{{SETUPS_EMPTY_NOTE}}` | nếu không có setup → `<div class="callout">Không có setup chiều tăng rõ.</div>`, ngược lại rỗng |
| `{{SETUPS_READER_NOTE}}` | reader_note của setup top-1, hoặc note archetype |

```python
def build_setups_rows(setups):
    if not setups:
        return ""
    rows = ""
    for s in setups[:6]:
        color = "neg" if s["completion_score"] >= 78 else ("neu" if s["completion_score"] >= 62 else "")
        rows += f"""<tr><td><strong>{s['pattern_name']}</strong></td>
        <td>{s['completion_score']:.0f}</td>
        <td class="{color}">{s['setup_status']}</td>
        <td>{s['watch_zone']['low']:.2f} – {s['watch_zone']['high']:.2f}</td>
        <td>+{s['distance_to_confirmation_pct']:.1f}%</td></tr>"""
    return rows
```

### Section 7: Non-conclusion
| Token | Nguồn |
|---|---|
| `{{NON_CONCLUSION_LIST}}` | build `<li>` từ `non_conclusion[]` |

```python
def build_non_conclusion(items):
    return "".join(f"<li>{t}</li>" for t in items)
```

---

## Chart data format <a name="charts"></a>

4 chart cần fill data object (JSON, inline trong `<script>`). Mỗi object = 1 `{{TOKEN}}`.

### `{{ROLLING_DATA}}` — Chart 1 (rolling percentile)
```json
{
  "labels": ["21D", "63D", "126D", "252D"],
  "percentiles": [25, 54, 39, 44],
  "returns": [-3.3, 1.2, -1.6, 17.2],
  "colors": ["rgba(255,77,109,0.6)","rgba(16,217,138,0.6)","rgba(255,77,109,0.6)","rgba(251,191,24,0.6)"]
}
```
Color rule: percentile <30 = red, >70 = green, 30-70 = amber.

### `{{DIST_DATA}}` — Chart 2 (distribution histogram)
```json
{
  "labels": ["≤-10%", "-10→-5%", "-5→-2%", "-2→0%", "0→2%", "2→5%", "5→10%", ">10%"],
  "counts": [0, 3, 45, 102, 110, 38, 6, 0],
  "colors": ["rgba(255,77,109,0.7)","rgba(255,77,109,0.5)","rgba(255,77,109,0.3)","rgba(251,191,24,0.2)","rgba(16,217,138,0.2)","rgba(16,217,138,0.3)","rgba(16,217,138,0.5)","rgba(16,217,138,0.7)"]
}
```
Color rule: bins âm = red gradient (đậm dần về trái), bins dương = green gradient (đậm dần về phải), bin quanh 0 = amber nhẹ. Source: `return_distribution.one_year_histogram`.

### `{{VAP_DATA}}` — Chart 3 (horizontal bar)
```json
{
  "labels": ["19.97-20.45", "20.45-20.93", "...", "26.65-27.09"],
  "values": [3.2, 5.1, "...", 2.1],
  "colors": ["rgba(139,92,246,0.4)","..."]
}
```
Color rule: bin chứa point_of_control = purple đậm (`rgba(168,85,247,0.8)`), các bin khác = purple mờ (`rgba(139,92,246,0.3)`). Labels = price range mỗi bin (typical_price).

### `{{BENCH_DATA}}` — Chart 4 (multi-line base-100)
```json
{
  "labels": ["02/2024", "03/2024", "...", "06/2026"],
  "stock": [100, 102, "...", 117.2],
  "bench": [100, 105, "...", 138.5]
}
```
Base-100: chuỗi đầu tiên = 100, các điểm sau = `100 × (1 + cumulative_return)`. Lấy ~12-24 điểm (monthly) để chart gọn, KHÔNG dùng daily 540 điểm. Labels = tháng/năm.

---

## Non-advice language check <a name="lang"></a>

Sau khi fill token, **grep** output HTML kiểm tra KHÔNG lọt từ bị cấm (xem `metric_guardrails.md` forbidden list). **Quan trọng**: phải loại trừ các cảnh báo phủ định ("không phải tín hiệu", "KHÔNG BUY/SELL") — đây là *đúng methodology*, không phải vi phạm.

```bash
# Bước 1: Tìm mọi hit thô (chỉ trong text hiển thị, không trong <script>/comment)
grep -inE "bullish|bearish|strong buy|strong sell|mua mạnh|bán mạnh|tín hiệu|khuyến nghị|nên mua|nên bán|overbought|oversold|verdict" {output}.html | grep -v "<script>" | grep -v "^[0-9]*:.*//"

# Bước 2: Lọc bỏ PHỦ ĐỊNH (cảnh báo) — chỉ giữ KHẲNG ĐỊNH (vi phạm thật)
# Hit VI PHẠM = từ KHÔNG đi kèm phủ định. Ví dụ vi phạm:
#   "Tín hiệu: MUA HPG" / "Verdict: STRONG BUY" / "Khuyến nghị: tích lũy"
# Hit HỢP LỆ = từ đi kèm phủ định. Ví dụ đúng methodology:
#   "không phải tín hiệu" / "KHÔNG BUY/SELL" / "không phải khuyến nghị"
```

**Quy tắc phân biệt:**
- ✅ **Hợp lệ** (cảnh báo): "không phải tín hiệu giao dịch", "KHÔNG phải khuyến nghị", "không thay thế dữ liệu intraday", "mô tả lịch sử, không phải tín hiệu dự báo".
- ❌ **Vi phạm** (dùng như khuyến nghị): "Tín hiệu: MUA", "Verdict: STRONG BUY", "Khuyến nghị: tích lũy cổ phiếu", "bullish rõ ràng".

Nếu Bước 2 chỉ còn hit phủ định → **PASS**. Nếu còn hit khẳng định → **FAIL, sửa**.

**Cho phép** trong mode PROFILE: "đang hình thành", "áp lực tiền âm", "volume không cùng chiều giá", "suy yếu", "thận trọng", "hỗn hợp" — đây là mô tả, không phải khuyến nghị.

---

## QA checklist <a name="qa"></a>

Hấp thụ từ `longform` Bước 6, đơn giản hóa cho dashboard. Chạy SAU khi fill token, TRƯỚC khi done.

```bash
OUTPUT="{project}/{symbol}_profile.html"

# Check 1: KHÔNG còn token placeholder
grep -oE "{{[A-Z_0-9]+}}" "$OUTPUT" | sort -u
# Phải trả EMPTY.

# Check 2: canvas + Chart.js count
echo "canvas: $(grep -c '<canvas' "$OUTPUT")"
echo "new Chart: $(grep -c 'new Chart' "$OUTPUT")"
# candlestick là custom canvas (KHÔNG new Chart) nên: canvas = new Chart + 1
# = 4 Chart.js + 1 candlestick = 5 canvas, 4 new Chart.

# Check 3: JS syntax check — extract <script> ra file tạm, node --check
python3 -c "
import re,sys,tempfile
html=open('$OUTPUT').read()
scripts=re.findall(r'<script>(.*?)</script>', html, re.DOTALL)
with tempfile.NamedTemporaryFile(mode='w', suffix='.js', delete=False) as f:
    f.write('\n'.join(scripts)); print(f.name)
" | xargs node --check
# Exit 0 = no syntax error.

# Check 4: non-advice language — chỉ flag KHẲNG ĐỊNH (xem section lang phía trên)
grep -inE "bullish|bearish|strong buy|strong sell|tín hiệu|khuyến nghị|nên mua|nên bán|verdict" "$OUTPUT" | grep -v "<script>" | grep -vE "không phải|KHÔNG|không thay thế|không phải tín hiệu"
# Phải trả EMPTY (các hit còn lại sau khi lọc phủ định = vi phạm thật).

# Check 5: có 7 section id
for id in read price risk flow bench vap setup notes; do
  grep -q "id=\"$id\"" "$OUTPUT" || echo "MISSING section #$id"
done
```

Exit: tất cả PASS = sẵn sàng. Nếu Check 1/2/3 fail → sửa trước khi done. Check 4 (non-advice) là **cứng** — mode PROFILE không bao giờ lọt từ khuyến nghị.

---

## Pitfalls thực tế

### Pitfall 1 — Token `{{...}}` sót trong JS object
❌ Fill `{{ROLLING_DATA}}` bằng string thay vì valid JSON → JS syntax error, toàn bộ chart vỡ.
✅ Khi fill chart data, dùng `json.dumps(obj, ensure_ascii=False)` để đảm bảo valid JSON. Test `node --check` bắt được lỗi này.

### Pitfall 2 — f-string `.format()` phá JS `{}`
❌ Dùng `html.format(**tokens)` → Python hiểu `{}` trong Chart.js config là placeholder → KeyError.
✅ Dùng `html.replace("{{TOKEN}}", value)` từng token. Không bao giờ `.format()`.

### Pitfall 3 — Chart data daily quá dày (BENCH_DATA)
❌ Fill BENCH_DATA với 540 điểm daily → line chart rối, label overlap, tooltip chậm.
✅ Resample xuống ~24 điểm monthly (mỗi ~22 phiên lấy 1 điểm) cho chart gọn readable.

### Pitfall 4 — Giá nghìn đồng vs đồng
❌ Hiển thị `{{LATEST_CLOSE_DISPLAY}}` = `23.45` (nghìn đồng) → user tưởng 23 đ.
✅ Luôn ×1000 khi display: `latest_close * 1000` rồi format có dấu phẩy → `23,450`. Note rõ "đồng" trong `.price-unit`.

### Pitfall 5 — Archetype pill class sai
❌ `{{ARCHETYPE_PRIMARY}}` = `accumulation_breakout` nhưng CSS chỉ có `.pill.trend_following` → pill không có màu.
✅ Map đầy đủ 5 class CSS: `.trend_following`, `.accumulation_breakout`, `.trap_prone`, `.mixed`, `.no_current_setup` (đã có sẵn trong template `:root` + `.pill` block).

### Pitfall 6 — Candlestick quá dày / đơn vị volume sai
❌ Fill CANDLESTICK_DATA với cả 585 phiên → nến chít chò, candleW < 3px, không đọc được. Hoặc volume để đơn vị gốc (triệu CP thô = 7,486,700) → cột volume đỉnh số khổng lồ.
✅ (1) Lấy **~120 phiên gần nhất** (n=120) — đủ thấy trend 6 tháng mà readable. (2) Volume chia 1e6 → triệu CP (`7.49`) khớp label `+ maxVol.toFixed(1)+'M'`. (3) Giá candlestick để **nghìn đồng** (23.45) — KHÔNG ×1000, vì grid label hiện `p.toFixed(1)` dạng `23.5`. (4) MA20/MA50 tính trên TOÀN BỘ rows rồi cắt 120 cuối, để MA đầu recent chỉ null ít.

### Pitfall 7 — Candlestick là custom canvas, KHÔNG phải Chart.js
❌ Đếm `new Chart` kỳ vọng = `canvas count` → fail vì candlestick là IIFE Canvas 2D riêng.
✅ QA Check 2: `canvas count = new Chart count + 1` (4 Chart.js + 1 candlestick custom = 5 canvas). Candlestick port từ `technical_template.html` (mode ACTIVE), KHÔNG dùng Chart.js.

---

## Ngôn ngữ: thuật ngữ kỹ thuật → đời thường <a name="lang-map"></a>

Dashboard dùng tiếng Việt đời thường cho người đọc phổ thông. **Token name giữ nguyên** trong code (`{{VAR_95}}`), chỉ đổi **label hiển thị** trong template. Khi fill token, dùng giá trị số như cũ — chỉ label HTML thay đổi.

| Label cũ (kỹ thuật) | Label mới (đời thường) | Token (giữ nguyên) |
|---|---|---|
| Rủi ro đuôi (historical) | Những phiên giảm mạnh nhất | (section title) |
| Hist. VaR 95 (1D) | Ngày giảm tồi tệ — 95% thời gian không vượt (VaR 95) | `{{VAR_95}}` |
| Hist. VaR 99 (1D) | Ngày giảm tồi tệ — 99% thời gian không vượt (VaR 99) | `{{VAR_99}}` |
| Expected Shortfall 95 | Mức giảm TB những ngày tồi tệ (ES 95) | `{{ES_95}}` |
| Số phiên underwater | Chưa lấy lại đỉnh sau bao nhiêu phiên | `{{UNDERWATER_DAYS}}` |
| Mức giảm tối đa (mẫu) | Sụt giảm sâu nhất từng ghi nhận | `{{DRAWDOWN_MAX}}` |
| HV20 / HV60 / HV120 / HV252 | Biến động 20/60/120 phiên (HV20...) / Biến động 1 năm (HV252) | `{{HV20}}` ... |
| Point of Control | Mức giá được giao dịch nhiều nhất | `{{POC_BIN}}` |
| Tập trung top-3 bins | Tập trung ở 3 mức giá giao dịch nhiều nhất | `{{VAP_CONCENTRATION}}` |
| Bin giá hiện tại | Mức giá hiện tại đang ở khoảng nào | `{{CURRENT_BIN}}` |
| Volume-at-price | Khối lượng giao dịch theo từng mức giá | (section title) |
| Corr | Tương quan (đi cùng thị trường) | (th header) |
| R² | Độ khớp (đáng tin cậy) | (th header) |
| Cửa sổ | Khung thời gian | (th header) |
| Score | Điểm sạch (0-100) | (th header) |
| Vùng xác nhận | Vùng cần vượt để xác nhận | (th header) |
| VPCI | Giá và khối lượng có cùng chiều? (VPCI) | (card title) |
| CMF | Dòng tiền vào hay ra? (CMF) | (card title) |
| Hành vi sau volume cao | Sau phiên giao dịch lớn | (card title) |
| Guardrail — [topic] | Lưu ý khi đọc — [topic] | (callout h4) |
| percentile N/100 | đang ở mức N/100 so với năm qua | (kpi-delta) |
| events/năm · median fwd 20D | lần/năm · mức tăng TB 20 phiên sau | (kpi-delta) |
| Return (TICKER) (252D) | Hiệu suất (TICKER) (1 năm) | (bench note) |
| Chênh mốc | Chênh so thị trường | (bench note) |
| Phân phối lợi suất ngày | Các phiên tăng giảm phân bố thế nào | (card title) |
| Phân vị lợi nhuận lăn | Hiệu suất hiện tại đang ở đâu so với lịch sử | (card title) |

**Quy tắc khi viết label mới:**
- Luôn bắt đầu bằng câu hỏi hoặc mô tả hành động ("Giá và khối lượng có cùng chiều?", "Dòng tiền vào hay ra?").
- Thuật ngữ kỹ thuật giữ trong ngoặc đơn sau câu đời thường ("... (VaR 95)", "... (CMF)", "... (HV60)").
- Tránh viết tắt (HV, VPCI, CMF, ES) làm label chính — chỉ trong ngoặc.
- "Guardrail" → "Lưu ý khi đọc" (người Việt không hiểu "guardrail").
- "percentile N/100" → "đang ở mức N/100 so với năm qua" (giải thích rõ so với gì).

⚠️ **Non-advice vẫn phải giữ**: ngôn ngữ đời thường KHÔNG đồng nghĩa với khuyến nghị. "Dòng tiền vào" = mô tả CMF dương, KHÔNG phải "nên mua". Cấm list trong `metric_guardrails.md` vẫn áp dụng đầy đủ.
