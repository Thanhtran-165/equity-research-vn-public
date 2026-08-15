---
name: vn-news-digest
description: Tổng hợp bản tin 30 ngày cho cổ phiếu VN — thu thập tin tức từ CafeF/Vietstock/VietnamBiz/VnExpress/Tuổi Trẻ, phân loại 4 nhóm (kinh doanh/ngành/vĩ mô/công bố), tính sentiment score, và render HTML news digest. Use khi user yêu cầu "bản tin", "tin tức gần đây", "news digest", "what's happening with [ticker]", "cập nhật [mã CP] tháng này", hoặc khi cần bổ sung góc nhìn thời sự cho dashboard phân tích cơ bản.
---

# VN News Digest

Bản tin tổng hợp 30 ngày cho cổ phiếu VN — bổ sung góc nhìn **thời sự** (dashboard fundamental chỉ có data BCTC quý/năm).

## Workflow 4 bước

### Bước 1: Thu thập tin tức — ưu tiên vnstock API

**Nguồn #1 (BẮT BUỘC thử trước):** vnstock `Company.news()` — 50 tin gần nhất, có sẵn title, content ngắn, source, public_date:

```python
from vnstock.api.company import Company
c = Company(symbol='HPG', source='VCI')
news_df = c.news()
# Columns: news_title, news_short_content, news_source, public_date,
#          news_source_link, news_keyword
# Lọc theo public_date trong window 30 ngày
recent = news_df[news_df['public_date'] >= '2026-05-22']
```

**Nguồn #1 bổ sung:** vnstock `Company.events()` — 50 sự kiện (công bố thông tin, cổ tức, giao dịch nội bộ):
```python
events_df = c.events()
# Columns: event_title_vi, public_date, action_type_vi, category,
#          record_date, exercise_ratio, value_per_share
```

**Nguồn #2 (bổ sung khi cần tin ngành/vĩ mô):** WebSearch với `search_recency_filter=oneMonth`:
1. **Ngành**: `"[ngành] [sản phẩm chính] tháng [m] năm [y]"` → VietnamBiz/VSA
2. **Vĩ mô**: `"giá [hàng hóa] thế giới tháng [m] năm [y]"` → Asemconnect
3. **Analyst**: `"[mã CP] khuyến nghị giá mục tiêu [mã CK]"` → VietstockFinance

⚠️ **`search_recency_filter=oneMonth` không tin cậy cho VN** — thường trả tin cũ. Phải lọc thủ công theo ngày trong window.

**Tham khảo `references/news_sources.md`** cho URL pattern + `vn-financial-data-collector/references/vnstock_api.md` cho code vnstock.

### Bước 2: Phân loại 5 nhóm

Mỗi tin gắn 1 tag:

| Tag | Mô tả | Ví dụ |
|---|---|---|
| **biz** (Kinh doanh) | KQKD, sản lượng, doanh thu, biên LN | "Q1/2026 LNST +170%" |
| **sector** (Ngành) | Dự án mới, đối thủ, giá nguyên liệu | "Dung Quất 2 hoàn thành" |
| **macro** (Vĩ mô) | Giá hàng hóa thế giới, thuế AD, lãi suất | "Giá HRC TQ đảo chiều giảm" |
| **disclosure** (Công bố) | Cổ tức, phát hành CP, thay đổi Ban GĐ | "Chốt quyền cổ tức 10%" |
| **analyst** (Phân tích) | Báo cáo CTCK, giá mục tiêu, khuyến nghị | "ASEANSC TP 91,800 đ (+23%)" |

**Quy tắc dedup:** Nếu cùng 1 chủ đề kéo dài nhiều phiên (VD: khối ngoại bán ròng liên tục 3 ngày), gom thành **1 item duy nhất** với ngày đại diện = ngày có giá trị giao dịch lớn nhất. Tránh duplicate tin cùng nội dung trên nhiều nguồn — chỉ lấy nguồn #1 (xem `references/news_sources.md`).

### Bước 3: Sentiment + tác động

Cho mỗi tin gán:
- **Sentiment**: `bullish` ▲ / `bearish` ▼ / `neutral` ◆
- **Impact**: `Rất cao` / `Cao` / `Trung bình` / `Thấp`

Tính **sentiment score tổng hợp** (thang -100 → +100):
```
sentiment: bullish = +1, neutral = 0, bearish = -1
impact_weight: Rất cao=2, Cao=1.5, Trung bình=1, Thấp=0.5
raw_sum = Σ(sentiment × impact_weight)
max_possible = Σ(impact_weight)  # nếu tất cả bullish
score = (raw_sum / max_possible) × 100
```

Tham khảo `references/sentiment_scoring.md` cho bảng quy đổi + decision thresholds.

**Category breakdown BẮT BUỘC (không optional):** Tính score riêng cho từng category (biz/sector/macro/disclosure/analyst). Phân kỳ category thường là insight giá trị nhất — VD: "biz=100 nhưng macro=-41 → rủi ro ngắn hạn nhưng dài hạn OK". Đưa divergence lên `key_takeaways` #1.

### Bước 4: Render HTML (optional — output tối thiểu là JSON)

Copy template `assets/news_template.html` và fill data.

**Cấu trúc template (6 section):**
1. **Hero** — Ticker, khoảng thời gian 30 ngày, giá hiện tại + change
2. **Stats strip** — Tổng tin, số tin +/-
3. **Executive Summary (TL;DR)** — ⭐ BẮT BUỘC. 1 đoạn tóm tắt chính (~3-4 câu) + 4 highlight boxes (số liệu nổi bật). Người đọc lướt nhanh chỉ cần đọc phần này để hiểu toàn cảnh. Format:
   - Title 1 câu chốt (VD: "HPG 30 ngày: Cơ bản bùng nổ, giá bị áp lực — divergence rõ rệt")
   - Body 3-4 câu nêu: số tin +/−, tin nổi bật nhất, biến động giá, verdict cuối
   - 4 metric boxes (3 tích cực + 1 trung tính/tiêu cực hoặc mix tùy thực tế)
4. **Sentiment Meter** — Score -100→+100, breakdown theo 5 nhóm, verdict (BULLISH/NEUTRAL/BEARISH)
5. **News Grid** — Cards tin tức (2 cột). Mỗi card **phải có 5 phần đầy đủ** (xem chi tiết dưới)
6. **Timeline** — Dòng sự kiện theo ngày (timeline dọc với dot màu)
7. **Key Takeaways** — 3-5 điểm chính tổng hợp

### News card — 5 phần bắt buộc (để card "dày" và có giá trị)

Mỗi card không chỉ là title + summary ngắn. **Phải có đủ 5 phần**:

```
┌─────────────────────────────────────────┐
│ [CATEGORY TAG]            [DATE · SOURCE]│  ← head
│ Tiêu đề tin (đậm, rõ ràng)              │  ← title
│ Tóm tắt 2-3 câu với số liệu cụ thể      │  ← summary
│ ┌──────┐ ┌──────┐ ┌──────┐              │
│ │METRIC│ │METRIC│ │METRIC│              │  ← metrics (2-3 số liệu nổi bật)
│ └──────┘ └──────┘ └──────┘              │
│ 💡 Vì sao quan trọng: [implication cho  │  ← why it matters (QUAN TRỌNG)
│    định giá/ra quyết định]              │
│ [▲ Bullish]    Tác động: Cao · ↗ Đọc    │  ← impact + sentiment + link
└─────────────────────────────────────────┘
```

**Quy tắc viết "Vì sao quan trọng":**
- Liên kết tin với **định giá** (VD: "Mỗi $10/t HRC ≈ 1 điểm % biên LN")
- Liên kết với **catalyst dài hạn** (VD: "Củng cố dự phóng LNST 2026 = 21.9K tỷ")
- Liên kết với **tin khác** (VD: "Đối lập với tin #4 — rủi ro H2/2026")
- Không lặp lại summary — thêm góc nhìn phân tích

**Metrics box format:**
- Label: 1-2 từ viết hoa (VD: "LNST YoY", "Sản lượng", "Giá HRC")
- Value: số cụ thể + dấu mũi tên màu (xanh/đỏ/vàng)

**Style đồng bộ** với `vn-research-dashboard` (cùng palette tím-hồng, glassmorphism). Đảm bảo cùng phong cách khi dùng kèm dashboard.

## Output

Quy ước key (đồng nhất trên toàn skill):
- `sentiment` field: dùng giá trị tiếng Anh lowercase `bullish` / `bearish` / `neutral`
- `impact` field: dùng giá trị tiếng Việt `Rất cao` / `Cao` / `Trung bình` / `Thấp` (match key trong `impactWeight` map)
- `sentiment_breakdown`: dùng `bullish` / `neutral` / `bearish` (đồng nhất với item, không dùng positive/negative)

```json
{
  "ticker": "HPG",
  "company_name": "Hòa Phát Group",
  "period": "22/05/2026 - 21/06/2026",
  "news_count": 14,
  "sentiment_breakdown": { "bullish": 9, "neutral": 3, "bearish": 2 },
  "sentiment_score": 62,
  "verdict": "BULLISH",
  "category_scores": { "biz": 85, "sector": 70, "macro": 45, "disclosure": 50, "analyst": 70 },
  "category_divergence_note": "biz=85 (tăng trưởng mạnh) vs macro=45 (giá thép TQ giảm) → rủi ro ngắn hạn nhưng dài hạn OK",
  "news_items": [
    {
      "category": "biz", "date": "15/06/2026",
      "source": "Tuổi Trẻ",
      "url": "https://...",
      "title": "Q1/2026: Lợi nhuận tăng 170% YoY",
      "summary": "Tóm tắt 2-3 câu với số liệu cụ thể (KHÔNG mơ hồ)",
      "key_metrics": [
        {"label": "LNST YoY", "value": "+170%", "tone": "pos"},
        {"label": "Biên gộp", "value": "+2.8đ%", "tone": "pos"},
        {"label": "Sản lượng", "value": "+22%", "tone": "pos"}
      ],
      "why_it_matters": "Liên kết với định giá/catalyst — VD: 'Vietcap dự phóng LNST 2026 = 21.9K tỷ, Q1 đã hoàn thành phần lớn mục tiêu'",
      "sentiment": "bullish", "impact": "Cao"
    }
  ],
  "key_takeaways": [
    "Chu kỳ phục hồi mạnh — tin kinh doanh áp đảo",
    "Dung Quất 2 catalyst chính 2026-2027",
    "Rủi ro: giá thép TQ giảm tháng 6"
  ]
}
```

## Phối hợp với dashboard

News digest bổ sung cho `vn-research-dashboard` — cùng link nhưng nội dung khác:
- **Dashboard** = data BCTC 5 năm (cơ bản, định giá)
- **News Digest** = thời sự 30 ngày (catalyst, rủi ro ngắn hạn)

User thường yêu cầu cả 2 cùng lúc → tạo 2 file HTML liên kết nhau.

## Tham khảo

- `references/news_sources.md` — URL pattern + cách filter 7 nguồn (CafeF/Vietstock/VietnamBiz/VSA/VnExpress/Tuổi Trẻ/Báo Mới)
- `references/sentiment_scoring.md` — Bảng quy đổi sentiment × impact → score, decision thresholds
- `assets/news_template.html` — Template HTML (cùng style với research-dashboard)
