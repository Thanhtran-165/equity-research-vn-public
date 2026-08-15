# Dashboard Variants — Style + Layout Router

Học từ pattern `create-wildlife-infographics` Intent Router: chọn layout/style dựa trên **ngành + audience + output intent**.

## Layout Router (theo SECTOR)

Chọn **section nào được highlight/mở rộng** dựa trên ngành — không phải mọi ngành đều cần 10 sections như nhau:

| Ngành | Sections ưu tiên | Sections rút gọn | Chỉ số focus |
|---|---|---|---|
| **Ngân hàng** (VCB, BID, TCB) | P/B + ROE, DDM, NPL/CAR (sector insight) | DuPont (ít ý nghĩa), P/S (không dùng) | P/B, ROE, NPL, NIM, CAS |
| **Thép/công nghiệp** (HPG, HSG) | Tất cả 10 sections, DCF (FCFF lớn) | — | P/B, EV/EBITDA, ROE, giá HRC |
| **Bất động sản** (VIC, VHM, NLG) | NAV/P/B, RNAV, landbank | DuPont (ít ý nghĩa), EV/EBITDA | NAV, P/B, landbank, unrecognized rev |
| **Bán lẻ/tiêu dùng** (VNM, MWG, PNJ) | PE + PEG, SSSG, inventory days | DCF (FCFE thay FCFF) | PE, PEG, SSSG, gross margin |
| **Công nghệ** (FPT, CMG) | PE + PEG, revenue growth, R&D/rev | Graham (PE cao quá), P/B (TS vô hình) | PE, PEG, revenue growth, R&D |
| **Dầu khí/hóa chất** (GAS, PLX, BSR) | EV/EBITDA + P/CF, giá dầu | DuPont | EV/EBITDA, P/CF, giá dầu |

**Cách dùng:** Khi user request `/equity-research-vn VCB`, auto-detect sector từ `vnstock Company.overview()['sector']` → chọn layout variant.

## Audience Router

| Audience | Điều chỉnh | Phong cách đề xuất |
|---|---|---|
| **Analyst chuyên nghiệp** | Đầy đủ data tables, DCF sensitivity, ratios chi tiết | Bloomberg Terminal tối (compact, monospace) |
| **Retail investor** (mặc định) | KPI cards lớn, giải thích thuật ngữ, ít bảng | Fintech hiện đại (gradient, glassmorphism) |
| **Quỹ đầu tư / Institutional** | NAV, alpha vs benchmark, risk metrics, PDF export | Corporate sáng (navy, sạch) |
| **Giáo dục / Demo** | Annotations, tooltips, "why this matters" | Fintech hiện đại + giải thích thêm |

**Cách dùng:** User có thể thêm `--audience analyst` hoặc `--audience retail` vào slash command.

## Output Intent Router

| Intent | Format | Đặc điểm |
|---|---|---|
| **Interactive web** (mặc định) | HTML standalone | Charts tương tác, deploy Vercel |
| **PDF export** | HTML → in/PDF | Layout cố định, tránh animation, trang A4 |
| **Email attachment** | HTML nhẹ | Ít chart nặng, static images, < 1MB |
| **Mobile-first** | HTML responsive | Cards stack dọc, charts đơn giản, touch-friendly |

## Sparse Request Expansion

Khi user nói ngắn gọn (VD: "phân tích VCB"), tự động infer:
- **Sector**: Ngân hàng → P/B + ROE focus, bỏ DuPont/P/S
- **Audience**: Retail (mặc định) → Fintech style
- **Output**: Interactive web (mặc định) → full 10 sections
- **Period**: 5 năm gần nhất (mặc định)

Chỉ hỏi user khi:
- Sector không rõ (công ty đa ngành)
- User yêu cầu cụ thể (VD: "PDF cho báo cáo quý")

---

# Style Variants — 3 biến thể CSS

Template mặc định = **Fintech hiện đại** (dark + gradient). User có thể yêu cầu 2 biến thể khác.

## Variant 1: Fintech Hiện Đại (DEFAULT)

Dark background + neon gradient. Phù hợp dashboard trading.

```css
:root {
  /* Background */
  --bg-0: #0a0a14;
  --bg-1: #10101f;
  --card: rgba(28,28,48,0.55);

  /* Text */
  --text: #f0f0ff;
  --text-dim: #8b8ba7;
  --text-faint: #5a5a72;

  /* Accents (neon) */
  --purple: #a855f7;
  --pink: #ec4899;
  --cyan: #06b6d4;
  --green: #10d98a;
  --red: #ff4d6d;
  --amber: #fbbf24;

  /* Gradients */
  --grad-main: linear-gradient(135deg, #a855f7 0%, #ec4899 100%);
  --grad-cool: linear-gradient(135deg, #06b6d4 0%, #8b5cf6 100%);
  --grad-bg: radial-gradient(ellipse at 20% 0%, rgba(139,92,246,0.15) 0%, transparent 50%),
             radial-gradient(ellipse at 80% 100%, rgba(236,72,153,0.12) 0%, transparent 50%);
}

body {
  background: var(--bg-0);
  background-image: var(--grad-bg);
  background-attachment: fixed;
  color: var(--text);
  font-family: 'Inter', sans-serif;
}

.card {
  background: var(--card);
  border: 1px solid rgba(139,92,246,0.18);
  border-radius: 24px;
  backdrop-filter: blur(14px);  /* glassmorphism */
}
```

**Font:** Inter (sans) + JetBrains Mono (numbers)

---

## Variant 2: Bloomberg Terminal

Black background + amber/green terminal text. Phù hợp analyst chuyên nghiệp.

```css
:root {
  --bg-0: #000000;
  --bg-1: #0a0a0a;
  --card: rgba(20,20,20,0.85);

  --text: #ffaa00;          /* Bloomberg amber */
  --text-dim: #888888;
  --text-faint: #555555;

  /* Accents */
  --green: #00ff66;         /* terminal green */
  --red: #ff3333;
  --cyan: #00ccff;
  --amber: #ffcc00;

  --grad-main: linear-gradient(135deg, #ffaa00 0%, #ff6600 100%);
}

body {
  background: var(--bg-0);
  color: var(--text);
  font-family: 'Courier New', monospace;  /* monospace throughout */
}

.card {
  background: var(--card);
  border: 1px solid #333;
  border-radius: 4px;        /* sharper corners */
  backdrop-filter: none;
}

.kpi-value, .price-now { color: var(--green); }   /* numbers = green */
.kpi-label { color: var(--text); letter-spacing: 2px; }
```

**Đặc điểm:**
- Monospace font throughout (Courier New / JetBrains Mono)
- Sharp corners (border-radius: 4px)
- Số liệu luôn màu xanh (terminal convention)
- Header có ticker style `=== HPG · HOSE ===`
- No gradients (flat colors)
- Tốc độ/compactness > thẩm mỹ

---

## Variant 3: Corporate Sáng

White background + navy blue. Phù hợp báo cáo quỹ đầu tư, corporate deck.

```css
:root {
  --bg-0: #f8f9fc;
  --bg-1: #ffffff;
  --card: #ffffff;

  --text: #1a202c;
  --text-dim: #4a5568;
  --text-faint: #a0aec0;

  /* Accents */
  --navy: #1a365d;
  --blue: #2c5282;
  --teal: #2c7a7b;
  --green: #2f855a;
  --red: #c53030;
  --amber: #c05621;

  --grad-main: linear-gradient(135deg, #1a365d 0%, #2c5282 100%);
  --grad-bg: none;  /* no fancy gradients */
}

body {
  background: var(--bg-0);
  color: var(--text);
  font-family: 'Inter', sans-serif;
}

.card {
  background: var(--card);
  border: 1px solid #e2e8f0;
  border-radius: 12px;
  box-shadow: 0 1px 3px rgba(0,0,0,0.05);
  backdrop-filter: none;
}

.hero {
  background: linear-gradient(135deg, #1a365d 0%, #2c5282 100%);
  color: white;
  border-radius: 16px;
}
```

**Đặc điểm:**
- Light background, tối ưu in ấn
- Navy blue primary, cẩn trọng
- Box-shadow nhẹ thay vì glow
- Typography sạch, ít decoration
- Phù hợp PDF export / email attachment

---

## Cách apply variant

**Refactor 2026-06:** 3 variants giờ được định nghĩa trong `_viz-shared/tokens.css` dưới dạng `[data-theme="..."]` selectors. Apply = thêm 1 attribute lên thẻ `<html>`, KHÔNG cần rewrite `:root` nữa.

```html
<!-- Default (Fintech) — không cần attribute -->
<html lang="vi">

<!-- Bloomberg Terminal -->
<html lang="vi" data-theme="bloomberg">

<!-- Corporate sáng -->
<html lang="vi" data-theme="corporate">
```

Vì `_viz-shared/viz.js` đọc màu từ CSS custom properties (`--chart-primary`, `--chart-grid`...) và mỗi theme override các property này, **Chart.js tự đổi màu theo theme** — không cần mapping tay.

```python
# Trong render pipeline:
theme_attr = ' data-theme="bloomberg"' if user_style == 'bloomberg' else (' data-theme="corporate"' if user_style == 'corporate' else '')
html = html.replace('<html lang="vi">', f'<html lang="vi"{theme_attr}>')
```

> ⚠️ Chart colors đã render sẽ **không** tự đổi nếu swap theme *sau* khi chart vẽ xong. Swap theme phải xảy ra **trước** khi `viz.chart()` chạy (trang load). Để re-render runtime: gọi `viz.refreshTheme()` rồi `chart.update()` — nhưng không cần cho use case static export.

Chart.js colors cũng cần đổi theo variant. Quick mapping:
- Fintech: `#a855f7, #ec4899, #06b6d4` (neon)
- Bloomberg: `#ffaa00, #00ff66, #00ccff` (terminal)
- Corporate: `#1a365d, #2c5282, #2c7a7b` (muted)
