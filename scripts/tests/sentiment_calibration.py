#!/usr/bin/env python3
"""Sentiment consistency + event dedupe (W3-2 — Wave 3).

1. EVENT DEDUPE: cùng 1 sự kiện được nhiều báo đăng → gom 1 event trước khi tính điểm
   (tránh thưởng điểm nhiều lần cho 1 bằng chứng).
2. THRESHOLD CONSISTENCY: verdict phải khớp bảng quy đổi score (không để score 62 → BULLISH
   khi bảng nói ≥60 → STRONG BULLISH).
3. SURPRISE vs EXPECTATION: "LNST tăng" không tự động bullish nếu thấp hơn kỳ vọng.
Chạy: python3 scripts/tests/sentiment_calibration.py
"""
import sys

# Bảng quy đổi chuẩn (tham chiếu sentiment_scoring.md)
THRESHOLDS = [
    (60, 100, "STRONG BULLISH"),
    (20, 59, "BULLISH"),
    (-19, 19, "NEUTRAL"),
    (-59, -20, "BEARISH"),
    (-100, -60, "STRONG BEARISH"),
]

def verdict_for(score):
    for lo, hi, label in THRESHOLDS:
        if lo <= score <= hi:
            return label
    return "UNKNOWN"

def event_dedupe(articles):
    """articles: [{title, source, published_at, event_key?}] — gom theo event_key nếu có,
    else normalize title (bỏ nguồn/ngày) làm khóa."""
    events = {}
    for a in articles:
        key = a.get("event_key") or _norm_title(a["title"])
        events.setdefault(key, []).append(a)
    return events

def _norm_title(t):
    import re
    t = re.sub(r"[—–\-].*$", "", t)          # bỏ phần sau dấu gạch (thường là nguồn/chi tiết)
    t = re.sub(r"\(.*?\)", "", t)
    return re.sub(r"\s+", " ", t).strip().lower()

def surprise_adjust(base_score, actual_growth, expected_growth, tolerance=0.02):
    """Nếu thực tế thấp hơn kỳ vọng (dù vẫn tăng) → không tính là tin tích cực."""
    if actual_growth is None or expected_growth is None:
        return base_score, "no_expectation_data"
    if actual_growth < expected_growth - tolerance:
        return max(base_score - 40, -100), f"thấp hơn kỳ vọng {expected_growth*100:.0f}% (thực {actual_growth*100:.0f}%)"
    return base_score, "dat_or_exceed_expectation"

def run():
    fails = []

    # 1. Event dedupe: (a) cùng tựa → gom; (b) khác tựa nhưng cùng sự kiện → cần event_key
    arts = [
        {"title": "Coteccons công bố KQKD niên độ 2026 kỷ lục — CafeF", "source": "CafeF"},
        {"title": "Coteccons công bố KQKD niên độ 2026 kỷ lục — MarketTimes", "source": "MarketTimes"},
        {"title": "CTD KQKD niên độ 2026: LNTT vượt nghìn tỷ — VietnamFinance", "source": "VietnamFinance", "event_key": "kqkd-2026"},
        {"title": "Thưởng nhân viên 3,5 tháng lương — MarketTimes", "source": "MarketTimes"},
    ]
    events = event_dedupe(arts)
    # (a) không event_key: cùng tựa gom → 3 events (KQKD cùng tựa + LNTT + thưởng)
    if len(events) != 3:
        fails.append(f"event dedupe (title-only) sai: {len(events)} events (kỳ vọng 3)")
    # (b) có event_key (sau clustering): 3 báo KQKD gán cùng key → 2 events
    arts2 = [{"title": t["title"], "source": t["source"],
              "event_key": t.get("event_key", "kqkd-2026" if "KQKD" in t["title"] else None)} for t in arts]
    events2 = event_dedupe(arts2)
    if len(events2) != 2:
        fails.append(f"event dedupe (event_key) sai: {len(events2)} events (kỳ vọng 2 — KQKD gom 3 báo)")
    if max(len(v) for v in events2.values()) != 3:
        fails.append("event KQKD phải gom đủ 3 báo khi có event_key")

    # 2. Threshold consistency: score 62 → STRONG BULLISH; 62 → BULLISH là mâu thuẫn
    if verdict_for(62) != "STRONG BULLISH":
        fails.append(f"threshold: score 62 → {verdict_for(62)} (kỳ vọng STRONG BULLISH)")
    if verdict_for(10) != "NEUTRAL":
        fails.append(f"threshold: score 10 → {verdict_for(10)} (kỳ vọng NEUTRAL)")

    # 3. Surprise: LNST +25% nhưng kỳ vọng +40% → hạ điểm
    s1, note1 = surprise_adjust(50, 0.25, 0.40)
    if s1 != 10 or "thấp hơn kỳ vọng" not in note1:
        fails.append(f"surprise: {s1} ({note1}) — kỳ vọng 10 với note thấp hơn kỳ vọng")
    s2, note2 = surprise_adjust(50, 0.45, 0.40)
    if s2 != 50:
        fails.append(f"surprise: đạt kỳ vọng phải giữ điểm — {s2}")

    if fails:
        print("❌ SENTIMENT CALIBRATION FAIL:")
        for f in fails:
            print("  -", f)
        sys.exit(1)
    print("✅ SENTIMENT CALIBRATION OK:")
    print("   - Event dedupe: cùng tựa gom ✓; khác tựa cần event_key (3 báo KQKD → 1) ✓")
    print("   - Threshold: 62 → STRONG BULLISH (hết mâu thuẫn BULLISH) ✓")
    print("   - Surprise: +25% thực vs +40% kỳ vọng → hạ điểm (không tự bullish) ✓")

if __name__ == "__main__":
    run()
