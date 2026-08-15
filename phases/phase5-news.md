# Phase 5: News Digest 30 ngày

Bạn là subagent Phase 5. Context tách biệt.

## Input
- `task-state.json` → `ticker`
- Sub-skill: `vn-news-digest/SKILL.md` + `references/sentiment_scoring.md` + `news_sources.md`

## Nhiệm vụ
1. Fetch tin qua `Company.news()` (50 tin) + `Company.events()` (50 sự kiện)
2. WebSearch bổ sung tin ngành/vĩ mô (chỉ nếu vnstock thiếu)
3. Phân loại 5 nhóm: biz, sector, macro, disclosure, analyst
4. Sentiment score (-100 → +100) + category breakdown
5. **Thesis alignment (BẮT BUỘC)**: mỗi tin top-10 đánh dấu supports/threatens/neutral
   so với luận điểm đầu tư (bull/bear từ phase 2/3)
6. **Catalyst detection (BẮT BUỘC)**: 3-5 sự kiện 30-90 ngày tới kèm ngày + tác động kỳ vọng
   + lý do (nguồn: Company.events + tin kế hoạch); không có → ghi [] không bịa
7. Timeline + key takeaways

## Yêu cầu bắt buộc (REQ-044)
- **Mỗi article phải có URL gốc** (field `url`) hoặc `source_name` (tên báo)
- **KHÔNG** được paraphrase tự do — phải trích nguyên văn tiêu đề hoặc tóm tắt có cite rõ nguồn
- ≥50% article phải có URL hoặc source_name xác định được

## Output — ghi vào task-state.json
```json
{
  "phases": {
    "phase5_news": {
      "status": "completed",
      "result": {
        "total_news": 50,
        "sentiment": {"positive": 13, "negative": 4, "neutral": 33},
        "sentiment_score": 18,
        "categories": {"biz": 9, "sector": 3, "macro": 0, "disclosure": 16, "analyst": 3},
        "top_headlines": [...]
      }
    }
  }
}
```

## Requirements
- REQ-008: News sentiment score + category breakdown

## KHÔNG được
- Bỏ qua sentiment scoring (BẮT BUỘC)
- Fake news — chỉ dùng tin thật từ vnstock/WebSearch
