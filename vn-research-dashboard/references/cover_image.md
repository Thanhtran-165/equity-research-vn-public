# Cover Image Generation — Optional hero image cho dashboard

Học từ pattern `imagegen` skill: dùng built-in `image_gen` tool để tạo cover image premium cho dashboard.

## Khi nào generate

**Optional** — user có thể thêm `--with-cover` vào slash command:
```
/equity-research-vn VCB --with-cover
```

Mặc định KHÔNG generate (giữ dashboard lightweight, không phụ thuộc external assets).

## Prompt template theo sector

Dùng built-in `image_gen` tool với prompt structure từ `imagegen` skill:

### Ngân hàng
```
Use case: infographic-diagram
Primary request: premium financial cover for Vietnam bank equity research report
Scene/backdrop: abstract dark navy gradient with subtle geometric pattern
Subject: stylized bank building silhouette with growth arrow, shield icon for stability
Style/medium: clean vector illustration, glassmorphism, purple-pink gradient accents
Composition/framing: 16:9 hero banner, focal center-right
Text (verbatim): "VCB", "Equity Research", "2026"
Constraints: readable short labels, no real logos, no watermark, premium fintech aesthetic
```

### Thép / công nghiệp
```
Use case: infographic-diagram
Primary request: premium financial cover for Vietnam steel company equity research
Scene/backdrop: dark industrial gradient with molten metal orange accents
Subject: stylized steel mill / blast furnace silhouette with production volume chart
Style/medium: clean vector illustration, industrial aesthetic, purple-orange gradient
Composition/framing: 16:9 hero banner
Text (verbatim): "HPG", "Steel Cycle Research", "2026"
Constraints: readable labels, no real logos, no watermark
```

### Công nghệ
```
Use case: infographic-diagram
Primary request: premium financial cover for Vietnam tech company equity research
Scene/backdrop: dark tech gradient with circuit board pattern
Subject: stylized data center / chip / network nodes with growth trajectory
Style/medium: clean vector illustration, cyberpunk-lite, cyan-purple gradient
Composition/framing: 16:9 hero banner
Text (verbatim): "FPT", "Tech Growth Research", "2026"
Constraints: readable labels, no real logos, no watermark
```

### Bất động sản
```
Use case: infographic-diagram
Primary request: premium financial cover for Vietnam real estate equity research
Scene/backdrop: dark premium gradient with city skyline silhouette
Subject: stylized skyscraper / development project with NAV breakdown
Style/medium: clean vector illustration, luxury aesthetic, gold-purple gradient
Composition/framing: 16:9 hero banner
Text (verbatim): "VHM", "Real Estate Research", "2026"
Constraints: readable labels, no real logos, no watermark
```

### Generic (mặc định)
```
Use case: infographic-diagram
Primary request: premium financial cover for Vietnam equity research report
Scene/backdrop: dark gradient with abstract financial chart lines
Subject: stylized bull/bear silhouette with candlestick chart background
Style/medium: clean vector illustration, fintech aesthetic, purple-pink gradient
Composition/framing: 16:9 hero banner
Text (verbatim): "[TICKER]", "Equity Research", "2026"
Constraints: readable labels, no real logos, no watermark
```

## Workflow

1. **Detect sector** từ `Company.overview()['sector']`
2. **Chọn prompt template** phù hợp (hoặc generic)
3. **Replace placeholders**: `[TICKER]`, company name
4. **Call `image_gen` tool** với prompt
5. **Save image** vào `[TICKER]_cover.png` cùng thư mục dashboard
6. **Embed vào HTML hero** — thay gradient background bằng image:
```html
<div class="hero" style="background:linear-gradient(135deg,rgba(10,10,20,0.85),rgba(168,85,247,0.4)),url('[TICKER]_cover.png') center/cover">
```

## Lưu ý

- `image_gen` tool save mặc định ở `$CODEX_HOME/*` — cần copy vào project dir
- Cover image tăng file size dashboard (thêm ~200-500KB) → optional
- Nếu deploy Vercel → cần upload cover image cùng (embed base64 hoặc deploy cùng folder)
- **Text trong image thường bị méo** — giữ text tối thiểu (chỉ ticker + "Equity Research")
- Nếu user muốn text chính xác → dùng HTML overlay thay vì text trong image

## Aspect ratio

- Hero banner: **16:9** (1480×832px) — fit với max-width container
- Square cover: **1:1** — cho social media share
- Story format: **9:16** — cho Instagram/Stories (nếu user yêu cầu)
