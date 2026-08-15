# Pattern Scoring — 8 setup heuristic + family + archetype

> ✅ **PORTABLE — chạy 100% với vnstock thuần**
>
> File này chứa phần pattern scoring không cần dependency ngoài. Chỉ cần daily OHLCV từ vnstock là tính được toàn bộ.
>
> Methodology 8 setup heuristic (đã port sang Python, self-contained).
> Triết lý: **"Cấu trúc đang hình thành chỉ là cấu trúc cần quan sát, không phải tín hiệu mua bán."** (non_advice_boundary)

## Mục lục
1. [Helpers chung](#helpers)
2. [8 Setup detection heuristic (chiều tăng)](#setups)
3. [Setup status + reader_note](#status)
4. [5 Pattern family classification](#family)
5. [Stock archetype](#archetype)

---

## Helpers chung <a name="helpers"></a>

Helpers chuẩn (xử lý số + slope tuyến tính) dùng cho cả setups và pattern scoring.

```python
import math

def finite(v):
    try:
        x = float(v)
    except (TypeError, ValueError):
        return None
    return x if math.isfinite(x) else None

def pct(a, b):
    """(a/b - 1) * 100. b=0 → 0.0."""
    return (a/b - 1) * 100 if b else 0.0

def clamp(value, low=0.0, high=100.0):
    return max(low, min(high, value))

def slope(values):
    """Hệ số góc (linear regression) qua values."""
    if len(values) < 2:
        return 0.0
    n = len(values)
    x_mean = (n - 1) / 2
    y_mean = sum(values) / n
    denom = sum((i - x_mean) ** 2 for i in range(n)) or 1
    return sum((i - x_mean) * (value - y_mean) for i, value in enumerate(values)) / denom
```

---

## 8 Setup detection heuristic <a name="setups"></a>

**Chỉ phát hiện mẫu CHIỀU TĂNG**. Mỗi hàm trả dict qua `setup()` (xem [Status](#status)).

Yêu cầu input: `rows` = daily OHLCV, cần ≥75 phiên cho cup_with_handle, ≥65 cho các mẫu khác.

```python
def detect_bull_flag(rows):
    """Cờ tăng. Pole = 30 phiên trước, flag = 14 phiên gần nhất."""
    current = rows[-1]["close"]
    recent = rows[-14:]
    pole = rows[-44:-14]
    if len(pole) < 20:
        return None
    pole_move = pct(max(r["close"] for r in pole[-5:]), min(r["close"] for r in pole[:15]))
    recent_high = max(r["high"] for r in recent)
    recent_low = min(r["low"] for r in recent)
    recent_range = pct(recent_high, recent_low)
    pullback = pct(recent_high, current)
    compact = max(0, 25 - recent_range) * 2.2
    score = 30 + min(pole_move, 35) + compact - max(0, pullback - 8) * 2
    if pole_move < 10 or recent_range > 16:
        score -= 20
    return setup("bull_flags", "Cờ tăng", score, recent_high, recent_low, recent_high, current,
                 "Cần có nhịp dẫn trước rõ và phần nghỉ không quá rộng.")

def detect_bull_pennant(rows):
    """Cờ đuôi nheo tăng. Co biên dao động ở 12 phiên gần nhất."""
    current = rows[-1]["close"]
    recent = rows[-12:]
    prior = rows[-42:-12]
    if len(prior) < 20:
        return None
    prior_move = pct(max(r["close"] for r in prior[-5:]), min(r["close"] for r in prior[:15]))
    first_range = max(r["high"] for r in recent[:6]) - min(r["low"] for r in recent[:6])
    last_range = max(r["high"] for r in recent[-6:]) - min(r["low"] for r in recent[-6:])
    compression = 1 - (last_range / first_range) if first_range > 0 else 0
    recent_high = max(r["high"] for r in recent)
    recent_low = min(r["low"] for r in recent)
    score = 35 + min(prior_move, 30) + clamp(compression * 55, 0, 35) - max(0, pct(recent_high, recent_low) - 14) * 2
    if prior_move < 10:
        score -= 18
    return setup("bull_pennants", "Cờ đuôi nheo tăng", score, recent_high, recent_low, recent_high, current,
                 "Cần thấy biên dao động co lại thay vì chỉ đi ngang rộng.")

def detect_ascending_triangle(rows):
    """Tam giác tăng. Kháng cự phẳng + đáy dốc lên."""
    current = rows[-1]["close"]
    window = rows[-45:]
    highs = [r["high"] for r in window]
    lows = [r["low"] for r in window]
    resistance = sorted(highs)[int(len(highs) * 0.8)]
    high_spread = pct(max(highs[-25:]), min(highs[-25:]))
    low_rise = pct(min(lows[-10:]), min(lows[:15]))
    distance = max(0.0, pct(resistance, current))
    score = 45 + min(max(low_rise, 0), 18) * 1.8 + max(0, 8 - high_spread) * 3 - distance * 1.5
    return setup("triangles_ascending", "Tam giác tăng", score, resistance, min(lows[-20:]), resistance, current,
                 "Cần kháng cự đủ phẳng và đáy sau cao hơn đáy trước.")

def detect_falling_wedge(rows):
    """Nêm giảm. 2 biên cùng dốc xuống + thu hẹp."""
    current = rows[-1]["close"]
    window = rows[-40:]
    highs = [r["high"] for r in window]
    lows = [r["low"] for r in window]
    high_slope = slope(highs)
    low_slope = slope(lows)
    width_start = max(highs[:10]) - min(lows[:10])
    width_end = max(highs[-10:]) - min(lows[-10:])
    narrows = 1 - width_end / width_start if width_start > 0 else 0
    upper_now = highs[0] + high_slope * (len(highs) - 1)
    distance = max(0.0, pct(upper_now, current)) if upper_now > 0 else None
    score = 40 + clamp(narrows * 60, 0, 35) + (12 if high_slope < 0 and low_slope < 0 else -15) - (distance or 0) * 1.2
    return setup("wedges_falling", "Nêm giảm", score, upper_now, min(lows[-15:]), upper_now, current,
                 "Cần hai biên cùng dốc xuống và độ rộng thu hẹp.")

def detect_cup_with_handle(rows):
    """Cốc tay cầm. Cần ≥75 phiên. Độ sâu cốc ~25%, tay cầm nông."""
    if len(rows) < 75:
        return None
    current = rows[-1]["close"]
    window = rows[-90:]
    closes = [r["close"] for r in window]
    left_high = max(closes[:30])
    cup_low = min(closes[20:70])
    right_high = max(closes[55:])
    depth = pct(left_high, cup_low)
    recovery = pct(right_high, cup_low)
    handle = rows[-15:]
    handle_pullback = pct(max(r["high"] for r in handle), min(r["low"] for r in handle))
    confirmation = max(left_high, right_high)
    score = 35 + min(recovery, 35) + max(0, 35 - abs(depth - 25)) - max(0, handle_pullback - 16) * 2
    if depth < 12 or depth > 50:
        score -= 18
    return setup("cup_with_handle", "Cốc tay cầm", score, confirmation,
                 min(r["low"] for r in handle), confirmation, current,
                 "Mẫu dài, dễ nhiễu nếu tay cầm quá sâu hoặc hồi chưa đủ.")

def detect_rectangle_bottom(rows):
    """Chữ nhật đáy. Vùng đi ngang rõ sau nhịp giảm."""
    current = rows[-1]["close"]
    window = rows[-35:]
    prior = rows[-75:-35]
    high = max(r["high"] for r in window)
    low = min(r["low"] for r in window)
    range_pct = pct(high, low)
    prior_drop = pct(prior[0]["close"], min(r["close"] for r in prior)) if prior else 0
    distance = max(0.0, pct(high, current))
    score = 42 + max(0, 18 - abs(range_pct - 12)) * 2 + min(max(prior_drop, 0), 18) - distance
    return setup("rectangle_bottoms", "Chữ nhật đáy", score, high, low, high, current,
                 "Cần vùng đi ngang đủ rõ sau một nhịp giảm hoặc tích lũy.")

def detect_double_bottom(rows):
    """Hai đáy. Tách ≥12 phiên, lệch <8%."""
    current = rows[-1]["close"]
    window = rows[-65:]
    lows = [r["low"] for r in window]
    first_i = min(range(0, 32), key=lambda idx: lows[idx])
    second_i = min(range(32, len(lows)), key=lambda idx: lows[idx])
    first_low = lows[first_i]
    second_low = lows[second_i]
    low_gap = abs(pct(second_low, first_low))
    neckline = max(r["high"] for r in window[first_i:second_i + 1])
    distance = max(0.0, pct(neckline, current))
    separation = second_i - first_i
    score = 48 + max(0, 8 - low_gap) * 4 + min(separation, 30) * 0.5 - distance * 1.5
    if separation < 12:
        score -= 15
    return setup("double_bottoms", "Hai đáy", score, neckline, min(first_low, second_low), neckline, current,
                 "Hai đáy cần tách nhau đủ xa và không lệch quá mạnh.")

def detect_measured_move_up(rows):
    """Measured Move tăng. Nhịp đầu + pha điều chỉnh ~50%."""
    current = rows[-1]["close"]
    first = rows[-70:-35]
    pullback = rows[-35:-12]
    recent = rows[-12:]
    if not first or not pullback:
        return None
    leg_low = min(r["low"] for r in first)
    leg_high = max(r["high"] for r in first)
    leg_move = pct(leg_high, leg_low)
    pull_low = min(r["low"] for r in pullback)
    retrace = (leg_high - pull_low) / (leg_high - leg_low) * 100 if leg_high > leg_low else 100
    confirmation = max(r["high"] for r in recent)
    score = 38 + min(leg_move, 30) + max(0, 30 - abs(retrace - 50)) - max(0, pct(confirmation, current)) * 1.2
    if leg_move < 12 or retrace < 25 or retrace > 75:
        score -= 18
    return setup("measured_move_up", "Measured Move tăng", score, confirmation, pull_low, confirmation, current,
                 "Cần nhịp đầu rõ, pha điều chỉnh vừa phải và chưa bị rơi vào vùng răng cưa.")

DETECTORS = [detect_bull_flag, detect_bull_pennant, detect_ascending_triangle,
             detect_falling_wedge, detect_cup_with_handle, detect_rectangle_bottom,
             detect_double_bottom, detect_measured_move_up]

def scan_setups(rows):
    """Chạy tất cả detectors, sort theo score desc. Trả top 6."""
    candidates = [d(rows) for d in DETECTORS]
    candidates = [c for c in candidates if c]  # bỏ None
    candidates.sort(key=lambda c: (-float(c["completion_score"]),
                                    float(c.get("distance_to_confirmation_pct") or 999),
                                    c["pattern_name"]))
    return candidates[:6]
```

---

## Setup status + reader_note <a name="status"></a>



```python
def status_from_score(score, distance_pct, noisy=False):
    """Trả 1 trong: 'gần xác nhận' / 'đang hình thành' / 'chưa đủ sạch' / 'nhiễu'."""
    if noisy:
        return "nhiễu"
    if score >= 78 and distance_pct is not None and distance_pct <= 3:
        return "gần xác nhận"
    if score >= 62:
        return "đang hình thành"
    return "chưa đủ sạch"

def setup(pattern_id, pattern_name, score, confirmation_price, watch_low, watch_high,
          current_close, caution, status=None):
    """Wrap 1 setup candidate. Score <55 → None (bỏ)."""
    score = round(clamp(score), 2)
    if score < 55:
        return None
    distance = max(0.0, pct(confirmation_price, current_close)) if confirmation_price else None
    final_status = status or status_from_score(score, distance)
    return {
        "pattern_id": pattern_id,
        "pattern_name": pattern_name,
        "setup_status": final_status,
        "completion_score": score,
        "confirmation_price": round(confirmation_price, 4) if confirmation_price is not None else None,
        "watch_zone": {
            "low": round(watch_low, 4) if watch_low is not None else None,
            "high": round(watch_high, 4) if watch_high is not None else None,
        },
        "distance_to_confirmation_pct": round(distance, 2) if distance is not None else None,
        "caution_reason": caution,
        "reader_note": reader_note(pattern_name, final_status, distance),
    }

def reader_note(pattern_name, status, distance):
    """4 template narrative theo status."""
    if status == "gần xác nhận":
        return f"{pattern_name} đang ở gần vùng cần xác nhận; vẫn cần chờ giá đóng cửa vượt mốc quan sát."
    if status == "đang hình thành":
        return f"{pattern_name} có cấu trúc đáng quan sát nhưng chưa đủ điều kiện xác nhận."
    if status == "nhiễu":
        return f"{pattern_name} có vài nét giống mẫu nhưng đường giá còn nhiễu."
    suffix = f", còn cách vùng xác nhận khoảng {distance:.2f}%" if distance is not None else ""
    return f"{pattern_name} chưa đủ sạch để đọc mạnh{suffix}."
```

**Tóm tắt ngưỡng score:**
| Score | Status | Ý nghĩa |
|---|---|---|
| < 55 | (bỏ) | Không đủ để quan tâm |
| 55-61 | chưa đủ sạch | Cấu trúc yếu, còn xa vùng xác nhận |
| 62-77 | đang hình thành | Đáng quan sát, chưa confirm |
| ≥78 & dist≤3% | gần xác nhận | Gần vùng confirm, chờ breakout |

---

## 5 Pattern family classification <a name="family"></a>

Map pattern_id → family. **Portable** (chỉ dict lookup).

```python
CONTINUATION_PATTERNS = {
    "bull_flags", "bull_pennants", "high_tight_flags", "measured_move_up",
    "continuation_gaps", "rising_three_methods",
}
ACCUMULATION_PATTERNS = {
    "triangles_ascending", "triangles_symmetrical", "rectangle_bottoms",
    "cup_with_handle", "double_bottoms_adam_adam", "double_bottoms_adam_eve",
    "double_bottoms_eve_adam", "double_bottoms_eve_eve", "triple_bottoms",
    "pipe_bottoms", "rounding_bottoms",
}
DOWNSIDE_PATTERNS = {
    "bear_flags", "bear_pennants", "triangles_descending", "rectangle_tops",
    "head_and_shoulders_tops", "head_and_shoulders_tops_complex",
    "measured_move_down", "pipe_tops", "horn_tops", "diamond_tops",
    "three_falling_peaks", "triple_tops", "bump_and_run_reversal_tops",
    "falling_three_methods", "cup_with_handle_inverted",
}

def pattern_family(pattern_id):
    """Trả 1 trong 5: trend_following / accumulation_breakout / defensive_caution / reversal_or_recovery / mixed."""
    if pattern_id in CONTINUATION_PATTERNS:
        return "trend_following"
    if pattern_id in ACCUMULATION_PATTERNS:
        return "accumulation_breakout"
    if pattern_id in DOWNSIDE_PATTERNS:
        return "defensive_caution"
    if "bottom" in pattern_id or "valleys" in pattern_id:
        return "reversal_or_recovery"
    if "top" in pattern_id or "peaks" in pattern_id:
        return "defensive_caution"
    return "mixed"
```

---

## Stock archetype <a name="archetype"></a>

Phân loại cổ phiếu theo kiểu hành vi chủ đạo, suy ra từ setup hiện tại + high-volume behavior. Chỉ dùng dữ liệu OHLCV.

```python
def estimate_archetype(setups, high_volume_behavior):
    """Phân loại archetype từ setup hiện tại + high-volume behavior.
    `setups` = output scan_setups(); `high_volume_behavior` = block B14 từ stock_profile_blocks.md.
    Trả {primary, reader_note}."""
    families = [pattern_family(s["pattern_id"]) for s in setups]
    hv_label = high_volume_behavior.get("post_high_volume_label", "") if high_volume_behavior else ""
    if not setups:
        return {"primary": "no_current_setup",
                "reader_note": "Không có setup chiều tăng rõ trong các mẫu heuristic; đọc theo từng phiên."}
    if "trend_following" in families:
        return {"primary": "trend_following",
                "reader_note": "Setup hiện tại nghiêng tiếp diễn; đọc ưu tiên theo sức giữ xu hướng."}
    if "accumulation_breakout" in families:
        return {"primary": "accumulation_breakout",
                "reader_note": "Setup hiện tại nghiêng tích lũy; đọc kỹ ở phiên xác nhận thoát nền."}
    if "suy yếu" in hv_label:
        return {"primary": "trap_prone",
                "reader_note": "Hành vi sau volume cao suy yếu; thận trọng với phá vỡ giả."}
    return {"primary": "mixed",
            "reader_note": "Setup hiện tại pha trộn; đọc theo từng cấu trúc cụ thể."}
```

**Bảng 4 archetype:**
| Primary | Khi nào | Đọc như |
|---|---|---|
| `trend_following` | có setup thuộc family trend_following | Ưu tiên nhịp tiếp diễn, sức giữ xu hướng |
| `accumulation_breakout` | có setup thuộc family accumulation_breakout | Đọc nền tích lũy + phiên xác nhận thoát nền |
| `trap_prone` | hành vi sau volume cao suy yếu | Thận trọng phá vỡ giả |
| `mixed` | không khớp rule nào | Đọc theo từng cấu trúc cụ thể |
| `no_current_setup` | không có setup nào | Đọc theo từng phiên |

> **Guardrail**: archetype chỉ mô tả xu hướng hành vi lịch sử quan sát được; không phải dự báo hay nhãn phân loại cố định.
