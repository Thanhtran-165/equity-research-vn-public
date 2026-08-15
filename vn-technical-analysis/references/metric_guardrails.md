# Metric Dictionary & Non-Advice Guardrails

> Reference cho **mode PROFILE** — ngôn ngữ `neutral_descriptive_non_advice`. Methodology từ dashboard phân tích thị trường nội bộ (đã port sang Python, self-contained).
>
> **Quy tắc tối thượng:** Mọi output mode profile là MÔ TẢ quá khứ, không phải tín hiệu/dự báo/khuyến nghị.

## Mục lục
1. [15 Metric dictionary](#dict) — định nghĩa + guardrail từng metric
2. [Ngưỡng đánh giá](#thresholds)
3. [CONSUMER_LABELS](#labels) — map status kỹ thuật → Việt
4. [scrubCopy rules](#scrub) — làm sạch text trước khi xuất
5. [4 Điểm non-conclusion](#nonconclusion) — BẮT BUỘC xuất cuối report
6. [Bảng dịch thuật ép buộc](#translate)
7. [Cấm list ngôn ngữ](#forbidden)
8. [Glossary thuật ngữ](#glossary)

---

## 15 Metric dictionary <a name="dict"></a>

Methodology: 13 metric với 4 trường mỗi metric (label_vi + formula + meaning + guardrail). **Bắt buộc** đọc cùng guardrail khi trình bày.

```python
def metric_dictionary():
    return {
        "return": {
            "label_vi": "Hiệu suất",
            "formula": "close_t / close_{t-window} - 1",
            "meaning": "Mức tăng giảm trong kỳ đang chọn.",
            "guardrail": "Không phải dự báo; chỉ mô tả phần đã xảy ra.",
        },
        "relative_return": {
            "label_vi": "So mốc",
            "formula": "return_object - return_benchmark",
            "meaning": "Khoảng cách tăng giảm so với VNINDEX, ngành hoặc rổ hiện tại.",
            "guardrail": "Số dương không có nghĩa độc lập với mốc; chỉ là đi tốt hơn trong kỳ.",
        },
        "moving_average_distance": {
            "label_vi": "Cách đường trung bình",
            "formula": "close_t / moving_average_n - 1",
            "meaning": "Giá hiện tại nằm trên hoặc dưới mặt bằng giá gần đây bao nhiêu.",
            "guardrail": "Không phải tín hiệu mua bán.",
        },
        "breadth": {
            "label_vi": "Bề rộng",
            "formula": "count(condition_true) / eligible_count",
            "meaning": "Tỷ lệ mã cùng tham gia tăng hoặc cùng đứng trên đường trung bình.",
            "guardrail": "Đây là số lượng mã, không đo độ lớn tăng giảm.",
        },
        "dispersion": {
            "label_vi": "Mức phân hóa",
            "formula": "std(cross_section_returns)",
            "meaning": "Độ chênh lệch hiệu suất giữa các mã trong cùng nhóm.",
            "guardrail": "Cao hoặc thấp không tự nói tốt/xấu; cần đọc cùng bề rộng.",
        },
        "liquidity": {
            "label_vi": "Thanh khoản",
            "formula": "close * volume; ratio = volume_t / average_volume_window",
            "meaning": "Mức hoạt động giao dịch theo giá trị hoặc khối lượng so trung bình.",
            "guardrail": "Giá trị giao dịch là ước tính từ giá đóng cửa nhân khối lượng.",
        },
        "correlation": {
            "label_vi": "Đi cùng",
            "formula": "corr(return_a, return_b)",
            "meaning": "Hai chuỗi tăng giảm cùng nhịp ở mức nào.",
            "guardrail": "Không nói chuỗi nào dẫn trước và không chứng minh quan hệ nhân quả.",
        },
        "beta_r2": {
            "label_vi": "Mức phản ứng / độ khớp",
            "formula": "beta = cov(stock, benchmark) / var(benchmark); r2 = regression_fit",
            "meaning": "Mã phản ứng mạnh hay nhẹ hơn mốc, kèm độ đáng đọc của phép so sánh.",
            "guardrail": "Beta thấp không đồng nghĩa ít rủi ro; R² thấp thì không đọc beta quá sâu.",
        },
        "drawdown": {
            "label_vi": "Mức giảm từ đỉnh",
            "formula": "close_t / rolling_peak - 1",
            "meaning": "Giá đang thấp hơn đỉnh gần nhất bao nhiêu.",
            "guardrail": "Nhạy với cửa sổ quan sát và dữ liệu chưa điều chỉnh sự kiện vốn.",
        },
        "rolling_return": {
            "label_vi": "Lợi nhuận lăn",
            "formula": "close_t / close_{t-window} - 1 across all historical windows",
            "meaning": "Phân phối các cửa sổ tăng giảm cùng độ dài đã xảy ra trong lịch sử.",
            "guardrail": "Các cửa sổ chồng lấp không phải quan sát độc lập và không phải xác suất tương lai.",
        },
        "historical_episode": {
            "label_vi": "Đợt lịch sử",
            "formula": "peak/trough/recovery dates from observed close path",
            "meaning": "Các đợt đi xuống, hồi phục hoặc tăng từ đáy lên đỉnh trong mẫu đang có.",
            "guardrail": "Rất nhạy với ngày bắt đầu mẫu và trạng thái điều chỉnh dữ liệu.",
        },
        "data_adjustment": {
            "label_vi": "Điều chỉnh dữ liệu",
            "formula": "raw price vs adjusted price governance",
            "meaning": "Cho biết dữ liệu giá đã được xác nhận điều chỉnh corporate actions hay chưa.",
            "guardrail": "Khi chưa xác nhận điều chỉnh, các metric dài hạn chỉ nên đọc như quan sát tham khảo.",
        },
        "data_confidence": {
            "label_vi": "Độ tin cậy dữ liệu",
            "formula": "coverage, zero-volume ratio, membership basis, relationship fit",
            "meaning": "Cho biết metric nên đọc chắc hay chỉ đọc tham khảo.",
            "guardrail": "Không che giấu bất định; luôn đọc cùng kỳ và nền dữ liệu.",
        },
        "classification_history": {
            "label_vi": "Lịch sử phân ngành",
            "formula": "ticker + sector/industry/subindustry + effective_from/effective_to",
            "meaning": "Cho biết ngành của cổ phiếu được đọc theo snapshot hiện tại hay theo ngày hiệu lực.",
            "guardrail": "Nếu chưa có lịch sử phân ngành, so sánh ngành quá khứ chỉ là tham chiếu theo phân ngành hiện tại.",
        },
    }
```

---

## Ngưỡng đánh giá <a name="thresholds"></a>

### Ngưỡng R² (độ khớp benchmark)
Từ `ANALYTICS_STANDARD.md:62-71`. Đây là **ngưỡng đánh giá duy nhất** được định nghĩa bằng số.

| R² | Mức | Hành vi đọc |
|---|---|---|
| `< 0.40` | **low** (thấp) | Beta không đáng đọc sâu |
| `0.40 – 0.70` | **medium** (trung bình) | Đọc vừa phải |
| `> 0.70` | **high** (cao) | Beta đáng tin |

Quy tắc bổ sung: lead-lag/cluster phải đi kèm coverage/liquidity quality trước khi lên UI nổi bật.

### Cửa sổ thời gian (4 cửa cố định)
Từ `ANALYTICS_STANDARD.md:24-36`.

| Label | Sessions | Vai trò |
|---|---|---|
| `20D` | 20 | Tactical state, noisy |
| `60D` | 60 | **Default operating window** (mặc định) |
| `120D` | 120 | Structure / relationship context |
| `252D` | 252 | Annual baseline |

> Internal field giữ `20d/60d/120d/252d`. UI có thể hiển thị nhãn Việt.

---

## CONSUMER_LABELS <a name="labels"></a>

Port từ `web/stock_profile_foundation_module.js:11-90`. Map status kỹ thuật → tiếng Việt dễ đọc. Dùng khi render narrative.

```python
CONSUMER_LABELS = {
    # Data confidence status
    "usable": "đủ để đọc",
    "thin_sample": "mẫu mỏng",
    "guardrailed": "cần lưu ý",
    "verified": "đã kiểm chứng",
    "missing": "thiếu dữ liệu",
    "point_in_time_ready": "đủ lịch sử",
    "snapshot_only": "chỉ snapshot hiện tại",
    # Regime
    "bull": "tăng mạnh",
    "bear": "giảm mạnh",
    "uptrend": "tăng",
    "recovery": "phục hồi",
    "stress": "áp lực",
    "sideways": "đi ngang",
    "unknown": "chưa đủ dữ liệu",
    # Sample label
    "khá dày": "khá dày",
    "đủ tham khảo": "đủ tham khảo",
    "ít dữ liệu": "ít dữ liệu",
    "mẫu mỏng": "mẫu mỏng",
    # Behavior / outcome labels
    "đi tiếp khá sạch": "đi tiếp khá sạch",
    "hay kéo ngược": "hay kéo ngược",
    "hay thất bại": "hay thất bại",
    "nhiễu vừa phải": "nhiễu vừa phải",
    "đã đạt mục tiêu": "đã đạt mục tiêu",
    "từng đi ngược đáng kể": "từng đi ngược đáng kể",
    "tham khảo/đang theo dõi": "tham khảo / đang hình thành",
    "mạnh hơn lịch sử của chính mã": "mạnh hơn lịch sử của chính mã",
    "cần thận trọng": "cần thận trọng",
    "trung tính": "trung tính",
    "không có mẫu hình hiện tại": "không có mẫu hình hiện tại",
}

def consumer_label(value):
    """Tra CONSUMER_LABELS, fallback scrub Anh→Vi."""
    if value in CONSUMER_LABELS:
        return CONSUMER_LABELS[value]
    # Fallback scrub (subset)
    if value is None:
        return "chưa đủ dữ liệu"
    s = str(value)
    for en, vi in [
        ("volume", "khối lượng"), ("value", "giá trị giao dịch"),
        ("confirmation", "xác nhận"), ("regime", "trạng thái"),
        ("usable", "đủ để đọc"), ("verified", "đã kiểm chứng"),
    ]:
        s = s.replace(en, vi)
    return s
```

---

## scrubCopy rules <a name="scrub"></a>

Port từ `web/stock_history_pattern_module.js:6-17`. Làm sạch text "control-room" rò rỉ từ generated data trước khi xuất.

```python
import re

def scrub_copy(text):
    """Khử ngôn ngữ kỹ thuật/internal trước khi trình bày."""
    if not text:
        return text
    replacements = [
        (r"cửa sổ theo dõi", "khung 20/60/120 phiên"),
        (r"đang theo dõi\b", "đang hình thành"),
        (r"theo dõi chiều tăng", "chiều tăng"),
        (r"nên đọc như", ""),  # xóa cụm khẳng định
        (r"control[- ]?room", "ghi chú"),
    ]
    out = text
    for pattern, repl in replacements:
        out = re.sub(pattern, repl, out, flags=re.IGNORECASE)
    return out.strip()
```

---

## 4 Điểm non-conclusion <a name="nonconclusion"></a>

Port từ `web/stock_history_academic_module.js:148-163`. **BẮT BUỘC** xuất ở cuối mọi report mode profile (rendered trong `non_conclusion` field của JSON schema).

```python
NON_CONCLUSION_POINTS = [
    "Không kết luận đây là khuyến nghị hoặc lời gọi giao dịch.",
    "Tỷ lệ trong quá khứ không đảm bảo lặp lại trong tương lai.",
    "Không đọc so sánh rổ/ngành như lịch sử đầy đủ nếu chỉ snapshot hiện tại.",
    "Không dùng kết quả dài hạn nếu chưa kiểm chứng corporate actions.",
]

def non_conclusion_panel():
    """Trả list 4 điểm. Phải hiện cuối report."""
    return list(NON_CONCLUSION_POINTS)
```

Điểm 3, 4 có thể bỏ nếu profile không có benchmark comparison / corporate action data — nhưng điểm 1, 2 luôn có.

---

## Bảng dịch thuật ép buộc <a name="translate"></a>

Port từ `FRONTEND_V2_STYLE_GUIDE.md:39-43`. Khi xuất narrative Việt, dùng cột phải.

| Thuật ngữ Anh | Bắt buộc dùng |
|---|---|
| Drawdown | **Mức giảm** (từ đỉnh) |
| Volume | **Khối lượng** |
| Value | **Giá trị giao dịch** (hoặc **GTGT**) |
| Volatility | **Biến động** / **Mức dao động** |
| Range | **Biên dao động** |
| Regime | **Trạng thái** (thị trường) |
| Outperform / Underperform | **Đi tốt hơn / Đi kém hơn** (mốc) |
| Hit rate | **Tỷ lệ vượt mốc** |
| Confirmation | **Xác nhận** |
| Setup | **Cấu trúc đang hình thành** |
| Pattern | **Mẫu hình** |

---

## Cấm list ngôn ngữ <a name="forbidden"></a>

Port từ `ANALYTICS_STANDARD.md:83-87`. **Mode PROFILE KHÔNG** dùng các từ này (chỉ mode ACTIVE mới dùng):

| ❌ Cấm (mode profile) | ✅ Dùng thay thế |
|---|---|
| bullish / bearish | "đang tăng" / "đang giảm" (mô tả) |
| leader mạnh | "đi tốt hơn nhóm" |
| nên chú ý | "đáng quan sát" / "cần đọc cùng guardrail" |
| tín hiệu | "cấu trúc" / "quan sát" |
| dự báo | (không dùng — luôn "mô tả quá khứ") |
| khuyến nghị mua/bán | (không dùng) |
| target price | "mức tham chiếu lịch sử" |
| breakout sắp xảy ra | "đang ở gần vùng xác nhận" |
| overbought / oversold | (không dùng — chỉ mode active) |
| strong buy / strong sell | (không dùng — chỉ mode active) |

> **Lưu ý:** Mode ACTIVE (MA/RSI/MACD/Tech Score/Verdict) vẫn dùng ngôn ngữ này — đó là use-case khác, xem SKILL.md chính.

---

## Glossary thuật ngữ <a name="glossary"></a>

Port subset từ `web/help_module.js:26-164` (HELP_TEXT ~140 term). Đây là ~30 term chính skill dùng trong narrative.

| Thuật ngữ | Giải thích ngắn |
|---|---|
| **Giá trị giao dịch** | Ước tính = giá đóng cửa × khối lượng (chưa phải giá trị khớp lệnh thực) |
| **Mức giảm (từ đỉnh)** | Giá đang thấp hơn đỉnh gần nhất bao nhiêu % |
| **Lợi nhuận lăn** | Phân phối return của mọi cửa sổ cùng độ dài trong lịch sử |
| **Vị trí lịch sử** | Vị trí metric hiện tại so với toàn bộ mẫu quá khứ (percentile) |
| **Đi cùng (correlation)** | Hai chuỗi tăng giảm cùng nhịp ở mức nào (−1 đến +1) |
| **Mức phản ứng (beta)** | Mã dao động mạnh hay nhẹ hơn mốc |
| **Độ khớp (R²)** | Độ đáng đọc của beta; <0.40 = thấp, >0.70 = cao |
| **Đi tốt hơn mốc** | Return mã > return benchmark trong kỳ |
| **Vượt trung vị nhóm** | Return mã > median return các mã cùng ngành |
| **Trên/Dưới TB20/50/200** | Giá hiện tại trên/dưới đường trung bình 20/50/200 phiên |
| **Mức phân hóa** | Độ chênh lệch return giữa các mã trong nhóm (cross-sectional std) |
| **Bề rộng** | Số lượng mã tham gia tăng/giảm (không đo độ lớn) |
| **Mức dao động (biến động)** | Độ phân tán return lịch sử (HV), annualized |
| **Biên dao động 14 phiên** | (high − low) / close trung bình 14 phiên |
| **Phiên liên tiếp (streak)** | Số phiên tăng/giảm liên tiếp |
| **Đỉnh/Đáy 52 tuần** | Giá cao/thấp nhất trong 252 phiên |
| **Độ tin cậy dữ liệu** | Cho biết metric đọc chắc hay chỉ tham khảo |
| **Cửa sổ quan sát** | Số phiên dùng tính metric (20/60/120/252) |
| **Snapshot hiện tại** | Rổ thành viên/phân ngành theo thời điểm hiện tại, không lịch sử |
| **Point-in-time** | Lịch sử theo ngày hiệu lực (data limitation, chưa có) |
| **Cấu trúc đang hình thành (setup)** | Mẫu chưa xác nhận, cần chờ giá đóng cửa vượt mốc |
| **Vùng xác nhận** | Mức giá cần vượt để mẫu được tính "xác nhận" |
| **Completion score** | Điểm sạch của setup (0-100, <55 = bỏ) |
| **Mẫu mỏng** | Cỡ mẫu < 5 events → chỉ đọc như ghi chú |
| **Hành vi sau volume cao** | Return trung bình 5d/20d/60d sau phiên volume ≥ 2x avg20 |
| **Effort-result** | Effort = giao dịch so trung bình; Result = biến động giá |
| **PVI / NVI** | Price index cập nhật phiên volume tăng / giảm (base=1000) |
| **VAP (volume-at-price)** | Phân bổ volume theo mức giá (xấp xỉ từ daily) |
| **VPCI** | Volume Price Confirmation Indicator — mức đồng thuận giá-volume |
| **Money flow (OBV/VPT/CMF)** | 3 chỉ báo áp lực dòng tiền từ OHLCV |

---

## Quy trình áp dụng khi render narrative

Khi xuất narrative mode PROFILE, theo thứ tự:

1. **Tra `metric_dictionary()`** cho mỗi metric dùng → lấy `label_vi` + `guardrail`. Nếu trình bày số liệu, kèm guardrail tương ứng.
2. **Tra `CONSUMER_LABELS`** cho mọi status kỹ thuật (regime, sample_label, behavior_label...) → dùng tiếng Việt.
3. **Áp `scrub_copy()`** cho mọi text sinh từ data template (đặc biệt pattern/setup narrative).
4. **Kiểm `forbidden` list** — không để lọt "bullish/bearish/tín hiệu/khuyến nghị".
5. **Dịch thuật** theo bảng ép buộc (Drawdown→Mức giảm...).
6. **Cuối report** thêm `non_conclusion_panel()` (4 điểm, ít nhất điểm 1+2).

```python
def render_profile_narrative(profile_json):
    """Template narrative mode PROFILE. Trả markdown Việt."""
    md = []
    md.append(f"# Hồ sơ cổ phiếu {profile_json['symbol']}\n")
    md.append("*Mô tả hành vi giá-khối lượng lịch sử. Không phải khuyến nghị giao dịch.*\n")
    # ... render từng block dùng CONSUMER_LABELS + scrub_copy ...
    # Cuối: non-conclusion
    md.append("\n## Lưu ý khi đọc\n")
    for point in non_conclusion_panel():
        md.append(f"- {point}")
    return "\n".join(md)
```
