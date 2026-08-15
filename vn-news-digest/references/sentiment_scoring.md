# Sentiment Scoring — Hệ thống tính điểm

Tin tức tài chính VN cần phân tích định tính vì sentiment thường mơ hồ. Bảng dưới giúp chuẩn hóa.

## Bước 1: Gán sentiment cho từng tin

| Sentiment | Ký hiệu | Tiêu chí |
|---|---|---|
| **bullish** | ▲ | Tin tăng lợi nhuận / tăng sản lượng / dự án tốt / giá ngành tăng / khối ngoại mua / CTCK khuyến nghị MUA |
| **bearish** | ▼ | Tin giảm lợi nhuận / giá ngành giảm / khối ngoại bán / đối thủ cạnh tranh mạnh / CTCK hạ khuyến nghị |
| **neutral** | ◆ | Cổ tức (trung tính), thay đổi nhân sự (chưa rõ), công bố thông tin quy trình |

⚠️ **Quan trọng:** Dùng đồng nhất giá trị `bullish` / `bearish` / `neutral` (tiếng Anh lowercase) cho cả `sentiment` field và `sentiment_breakdown`. Không dùng `positive`/`negative` để tránh bug khi render.

**Mẹo phân biệt:**
- "LNST tăng X%" → bullish (dù X nhỏ, vẫn tăng)
- "LNST giảm Y%" → bearish
- "Cổ tức tỷ lệ Z%" → neutral (cổ tức luôn được công bố)
- "Tăng trưởng thấp hơn cùng kỳ" → bearish (âm arguably, nhưng dù dương mà thấp hơn kỳ vọng → nhẹ bearish)

## Bước 2: Gán impact weight

| Impact | Weight | Tiêu chí |
|---|---|---|
| **Rất cao** | 2.0 | Sự kiện 1 lần lớn: dự án lò cao mới, M&A, thay đổi CEO, KQ quý vượt/kém kỳ vọng > 50% |
| **Cao** | 1.5 | Tin ảnh hưởng định giá dài hạn: sản lượng +20%+ YoY, biên LN ±3 điểm %, giá ngành ±10% |
| **Trung bình** | 1.0 | Tin giao dịch (khối ngoại mua/bán), cổ tức, tin kinh doanh thông thường |
| **Thấp** | 0.5 | Tin quy trình: thông báo cuộc họp, sửa điều lệ, thay đổi đại diện |

**Quy tắc heuristic:**
- Nếu tin xuất hiện trên **3+ nguồn** → bump impact lên 1 cấp (tín hiệu thị trường quan tâm)
- Nếu tin về **catalyst dài hạn** (Dung Quất 2, HRC new line) → impact Rất cao/Cao
- Nếu tin về **ngành/vĩ mô** → impact Cao (ảnh hưởng tất cả công ty ngành)

## Bước 3: Tính sentiment score

```javascript
const news = [...];  // mảng tin đã gán sentiment + impact

const sentimentValue = { bullish: 1, neutral: 0, bearish: -1 };
const impactWeight = { 'Rất cao': 2.0, 'Cao': 1.5, 'Trung bình': 1.0, 'Thấp': 0.5 };

let rawSum = 0, maxPossible = 0;
news.forEach(n => {
  const w = impactWeight[n.impact];
  rawSum += sentimentValue[n.sentiment] * w;
  maxPossible += w;
});
const score = Math.round((rawSum / maxPossible) * 100);  // -100 → +100
```

## Bước 4: Verdict theo threshold

| Score | Verdict | Màu | Khuyến nghị ngắn hạn |
|---|---|---|---|
| +60 đến +100 | 🟢 **STRONG BULLISH** | Green | Tích lũy mạnh |
| +30 đến +59 | 🟢 **BULLISH** | Green | Tích lũy |
| -29 đến +29 | 🟡 **NEUTRAL** | Amber | Quan sát |
| -59 đến -30 | 🔴 **BEARISH** | Red | Hạn chế/Giảm |
| -100 đến -60 | 🔴 **STRONG BEARISH** | Red | Tránh |

## Bước 5: Category breakdown (tùy chọn)

Tính score riêng cho từng category (biz/sector/macro/disclosure). Hiểu sâu hơn — VD:
- Score biz cao + sector thấp → công ty tốt nhưng ngành yếu (cơ hội mua khi ngành phục hồi)
- Score macro thấp + biz cao → rủi ro ngắn hạn nhưng dài hạn OK

## Ví dụ tính (case HPG 22/05-21/06/2026)

```
14 tin:
- 9 bullish: 4×Cao(1.5) + 3×Rất cao(2.0) + 2×Trung bình(1.0) = 6+6+2 = 14
- 3 neutral: 3×Trung bình(1.0) = 3 → 0×3 = 0
- 2 bearish: 1×Trung bình(1.0) + 1×Cao(1.5) = -1-1.5 = -2.5

rawSum = 14 + 0 - 2.5 = 11.5
maxPossible = 14 + 3 + 2.5 = 19.5
score = (11.5/19.5) × 100 = 59 → bump vì 3 tin xuất hiện trên nhiều nguồn → 62
verdict = BULLISH (+30 đến +59 → gần +60, bump lên)
```

## Bẫy sentiment scoring

1. **Đừng đếm số tin thuần túy** — 1 tin Rất cao có thể nặng hơn 5 tin Thấp
2. **Cẩn thận tin "trung tính báo chí"** — đôi khi giấu sentiment thật (VD: "DN báo lãi" nhưng thực tế thấp hơn kỳ vọng)
3. **Tách sentiment ngắn hạn vs dài hạn** — tin Q1 tốt không nhất thiết bullish dài hạn nếu chu kỳ sắp đỉnh
4. **Cross-check với giá CP** — nếu sentiment bullish nhưng giá giảm mạnh → có thể đã priced-in hoặc thị trường thấy điều khác
5. **Dedup tin trùng** — nếu cùng 1 chủ đề xuất hiện trên 3+ nguồn → chỉ lấy 1 item (nguồn #1 ưu tiên). Nếu cùng chủ đề kéo dài nhiều phiên (VD: khối ngoại bán ròng 3 ngày liên tiếp) → gom thành 1 item với ngày đại diện = ngày có giá trị giao dịch lớn nhất. Impact của item gom = max impact của các phiên.
6. **Analyst recommendation = bullish nhưng cẩn thận** — CTCK hay "MUA" với target cao → bullish, nhưng cần check xem recommendation này có xuất hiện định kỳ (mỗi quý) hay không. Nếu định kỳ → impact `Trung bình`; nếu upgrade/downgrade mới → impact `Cao`.
