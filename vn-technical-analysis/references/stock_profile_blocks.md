# Stock Profile Blocks — Methodology 15 block cốt lõi

> Reference cho **mode PROFILE**. Methodology từ dashboard phân tích thị trường nội bộ (đã port sang Python).
>
> Triết lý: **"What I See"** — mô tả lịch sử giá-khối lượng. MỌI block kèm `interpretation_guardrail` cảnh báo đây là quan sát quá khứ, KHÔNG phải tín hiệu/dự báo/khuyến nghị.
>
> Input chung cho mọi block: `rows` = list daily OHLCV (mỗi row có `date, open, high, low, close, volume, value, range_pct`). Từ vnstock: `value = close * volume * 1000` (giá vnstock = nghìn đồng, ×1000 ra đồng).

## Mục lục
1. [Helpers dùng chung](#helpers) — mean/std/skew/kurtosis/quantile/percentile/returns/drawdown
2. [price_behavior_profile](#b1)
3. [volatility_profile](#b2)
4. [drawdown_profile](#b3)
5. [liquidity_profile](#b4)
6. [return_distribution_profile](#b5)
7. [tail_risk_profile](#b6)
8. [liquidity_risk_profile](#b7)
9. [relative_strength + dynamic_beta + correlation](#b8)
10. [regime_profile](#b9)
11. [volume_price_profile](#b10)
12. [volume_price_confirmation (VPCI)](#b11)
13. [money_flow (OBV/VPT/CMF)](#b12)
14. [effort_result (Wyckoff)](#b13)
15. [high_volume_behavior](#b14)
16. [pvi_nvi_participation](#b15)
17. [volume_at_price](#b16)
18. [industry_peer_profile](#b17)

---

## Helpers dùng chung <a name="helpers"></a>

Methodology nền cho mọi block (helpers chuẩn hóa OHLCV + thống kê).

```python
import math

def finite(v):
    try:
        x = float(v)
    except (TypeError, ValueError):
        return None
    return x if math.isfinite(x) else None

def round_(v, d=2):
    return None if not finite(v) else round(float(v), d)

def mean(values=[]):
    nums = [v for v in values if finite(v)]
    return sum(nums)/len(nums) if nums else None

def std_dev(values=[]):
    nums = [v for v in values if finite(v)]
    if len(nums) < 2:
        return None
    avg = mean(nums)
    return math.sqrt(sum((v-avg)**2 for v in nums) / (len(nums)-1))

def skewness(values=[]):
    nums = [v for v in values if finite(v)]
    if len(nums) < 3:
        return None
    avg, sd = mean(nums), std_dev(nums)
    if not sd:
        return None
    n = len(nums)
    return (n / ((n-1)*(n-2))) * sum(((v-avg)/sd)**3 for v in nums)

def excess_kurtosis(values=[]):
    nums = [v for v in values if finite(v)]
    if len(nums) < 4:
        return None
    avg, sd = mean(nums), std_dev(nums)
    if not sd:
        return None
    n = len(nums)
    z4 = sum(((v-avg)/sd)**4 for v in nums)
    return ((n*(n+1)) / ((n-1)*(n-2)*(n-3))) * z4 - (3*(n-1)**2)/((n-2)*(n-3))

def quantile(values, q):
    """q trong [0,1]. Dùng linear interpolation (giống stock_history_calculations.mjs)."""
    nums = sorted(v for v in values if finite(v))
    if not nums:
        return None
    if len(nums) == 1:
        return nums[0]
    pos = q * (len(nums) - 1)
    lo = math.floor(pos); hi = math.ceil(pos)
    if lo == hi:
        return nums[lo]
    return nums[lo] + (nums[hi] - nums[lo]) * (pos - lo)

def median(values=[]):
    return quantile(values, 0.5)

def percentile_of_value(values, value):
    """Vị trí percentile của `value` trong `values` (0-100). Dùng floor counting (giống source)."""
    nums = [v for v in values if finite(v)]
    if not nums or not finite(value):
        return None
    return round_(sum(1 for v in nums if v <= value) / len(nums) * 100)

def log_returns(rows=[]):
    out = []
    for i in range(1, len(rows)):
        p, c = rows[i-1].get("close"), rows[i].get("close")
        if p and c and p > 0 and c > 0:
            out.append(math.log(c/p))
    return out

def daily_returns_pct(rows=[]):
    """Return % (không phải decimal). Dùng cho distribution/drawdown."""
    out = []
    for i in range(1, len(rows)):
        p, c = rows[i-1].get("close"), rows[i].get("close")
        if p and c and p > 0 and c > 0:
            out.append((c/p - 1) * 100)
    return out

def drawdown_series(rows=[]):
    """Series drawdown (decimal, âm) theo running peak."""
    peak = None
    out = []
    for row in rows:
        c = finite(row.get("close"))
        if c is None:
            out.append(None); continue
        peak = c if peak is None else max(peak, c)
        out.append(c/peak - 1 if peak else None)
    return out

def realized_vol(rows, window):
    """HV annualized %, dùng log returns."""
    values = log_returns(rows)[-window:]
    if len(values) < max(5, window // 3):
        return None
    return round_(std_dev(values) * math.sqrt(252) * 100)

def realized_vol_history(rows, window):
    """Toàn bộ history HV để tính percentile."""
    returns = log_returns(rows)
    min_count = max(5, window // 3)
    values = []
    for i in range(min_count, len(returns) + 1):
        sample = returns[max(0, i-window):i]
        v = round_(std_dev(sample) * math.sqrt(252) * 100) if len(sample) >= min_count else None
        if finite(v):
            values.append(v)
    return values

def pct_change(rows, window):
    """Return % của window phiên gần nhất."""
    if len(rows) <= window:
        return None
    start = rows[-1-window].get("close")
    end = rows[-1].get("close")
    if not (start and end and start > 0 and end > 0):
        return None
    return round_((end/start - 1) * 100)

def line_change_pct(points, window):
    """% change của field `value` trong list of dict, cách `window` ngày."""
    if len(points) <= window:
        return None
    a = points[-1-window].get("value")
    b = points[-1].get("value")
    if not (finite(a) and finite(b)) or a == 0:
        return None
    return round_((b/a - 1) * 100)
```

### Helpers phụ trợ (moving average tại index, drawdown episodes)

```python
def sma_at(rows, index, field, window):
    """SMA của `field` kết thúc tại index (inclusive)."""
    if index < window - 1:
        return None
    slice_ = rows[index-window+1:index+1]
    vals = [finite(r.get(field)) for r in slice_]
    vals = [v for v in vals if v is not None]
    return sum(vals)/len(vals) if len(vals) == window else None

def vwma_at(rows, index, field, window):
    """VWMA = sum(close*volume)/sum(volume) trên window."""
    if index < window - 1:
        return None
    slice_ = rows[index-window+1:index+1]
    num = 0.0; den = 0.0; ok = True
    for r in slice_:
        px = finite(r.get(field)); vol = finite(r.get("volume"))
        if px is None or vol is None:
            ok = False; break
        num += px * vol; den += vol
    return (num/den) if ok and den > 0 else None

def moving_average_before(rows, index, field, window):
    """Trailing MA kết thúc TRƯỚC index (cho effort-result, dùng dữ liệu quá khứ)."""
    return sma_at(rows, index-1, field, window)

def average_value(rows, window):
    slice_ = rows[-window:]
    vals = [finite(r.get("value")) for r in slice_]
    vals = [v for v in vals if v is not None]
    return sum(vals)/len(vals) if vals else None

def drawdown_episodes(rows):
    """Tách episodes: mỗi episode = từ peak đến recovery (về lại peak).
    Trả list of {trough_date, depth_pct, recovery_days, ...}. Sort theo depth tăng dần."""
    peak = None; peak_date = None
    episodes = []
    in_dd = False; trough_idx = None; trough_close = None
    for i, row in enumerate(rows):
        c = finite(row.get("close"))
        if c is None:
            continue
        if peak is None or c > peak:
            peak = c; peak_date = row.get("date")
            if in_dd:
                # recovered
                eps_depth = (trough_close/peak_at_start - 1)*100 if peak_at_start else None
                episodes.append({
                    "peak_date": peak_at_start_date, "trough_date": rows[trough_idx]["date"],
                    "depth_pct": round_(eps_depth), "recovery_days": i - trough_idx,
                })
                in_dd = False
        else:
            if not in_dd:
                in_dd = True; peak_at_start = peak; peak_at_start_date = peak_date
                trough_idx = i; trough_close = c
            elif c < trough_close:
                trough_idx = i; trough_close = c
    if in_dd:
        eps_depth = (trough_close/peak_at_start - 1)*100 if peak_at_start else None
        episodes.append({
            "peak_date": peak_at_start_date, "trough_date": rows[trough_idx]["date"],
            "depth_pct": round_(eps_depth), "recovery_days": None,  # chưa recover
        })
    episodes.sort(key=lambda e: e["depth_pct"] or 0)
    return episodes
```

> **Lưu ý đơn vị:** vnstock trả `close` = nghìn đồng. Khi tính `value` cho block liquidity/effort-result: `value = close * volume * 1000` (ra đồng). Giữ nhất quán trong toàn bộ rows trước khi gọi các block.

---

## B1. price_behavior_profile <a name="b1"></a>



```python
def price_behavior_profile(rows):
    latest = rows[-1] if rows else {}
    closes_252 = [r["close"] for r in rows[-252:] if finite(r.get("close"))]
    high_52w = max(closes_252) if closes_252 else None
    low_52w = min(closes_252) if closes_252 else None
    latest_close = latest.get("close")
    returns = daily_returns_pct(rows)
    rolling = [rolling_return_profile(rows, w) for w in (21, 63, 126, 252)]
    return {
        "latest_close": latest_close,
        "latest_date": latest.get("date"),
        "return_1m_pct": pct_change(rows, 21),
        "return_3m_pct": pct_change(rows, 63),
        "return_6m_pct": pct_change(rows, 126),
        "return_1y_pct": pct_change(rows, 252),
        "high_52w": high_52w,
        "low_52w": low_52w,
        "distance_from_52w_high_pct": round_((latest_close/high_52w - 1)*100)
            if finite(high_52w) and finite(latest_close) and high_52w > 0 else None,
        "distance_from_52w_low_pct": round_((latest_close/low_52w - 1)*100)
            if finite(low_52w) and finite(latest_close) and low_52w > 0 else None,
        "rolling_returns": rolling,  # 4 windows, xem helper dưới
        "daily_return_distribution": {
            "observations": len(returns),
            "median_pct": round_(median(returns)),
            "p10_pct": round_(quantile(returns, 0.1)),
            "p90_pct": round_(quantile(returns, 0.9)),
            **threshold_counts(returns),
        },
        "interpretation_guardrail": "Hành vi giá là quan sát lịch sử; không phải dự báo xu hướng tương lai.",
    }

def rolling_return_profile(rows, window):
    """Trả {window, current_return_pct, percentile, median, p10, p90, observations}."""
    series = rolling_return_series(rows, window)  # list of value
    values = [v for v in series if finite(v)]
    current = values[-1] if values else None
    return {
        "window": window,
        "current_return_pct": current,
        "percentile": percentile_of_value(values, current),
        "median_return_pct": round_(median(values)),
        "p10_return_pct": round_(quantile(values, 0.1)),
        "p90_return_pct": round_(quantile(values, 0.9)),
        "observations": len(values),
    }

def rolling_return_series(rows, window):
    """Slide window qua toàn bộ history, mỗi bước = return % của window đó."""
    out = []
    for i in range(window, len(rows)):
        a = rows[i-window].get("close"); b = rows[i].get("close")
        if a and b and a > 0 and b > 0:
            out.append((b/a - 1) * 100)
    return out

def threshold_counts(values):
    nums = [v for v in values if finite(v)]
    return {
        "observations": len(nums),
        "up_5_pct": sum(1 for v in nums if v >= 5),
        "down_5_pct": sum(1 for v in nums if v <= -5),
        "up_10_pct": sum(1 for v in nums if v >= 10),
        "down_10_pct": sum(1 for v in nums if v <= -10),
    }
```

---

## B2. volatility_profile <a name="b2"></a>



```python
def volatility_profile(rows):
    vol20_hist = realized_vol_history(rows, 20)
    vol60_hist = realized_vol_history(rows, 60)
    current_vol20 = realized_vol(rows, 20)
    current_vol60 = realized_vol(rows, 60)
    range_63 = [finite(r.get("range_pct")) for r in rows[-63:]]
    range_63 = [v for v in range_63 if v is not None]
    return {
        "hv20_pct": current_vol20,
        "hv60_pct": current_vol60,
        "hv120_pct": realized_vol(rows, 120),
        "hv252_pct": realized_vol(rows, 252),
        "hv20_percentile_1y": percentile_of_value(vol20_hist[-252:], current_vol20),
        "hv60_percentile_1y": percentile_of_value(vol60_hist[-252:], current_vol60),
        "range_pct_median_63d": round_(median(range_63)),
        "range_pct_p90_63d": round_(quantile(range_63, 0.9)),
        "interpretation_guardrail": "Biến động là độ phân tán lịch sử; không phải dải giá kỳ vọng hay dự báo biến động tương lai.",
    }
```

---

## B3. drawdown_profile <a name="b3"></a>

+ `drawdownEpisodeProfile`.

```python
def drawdown_profile(rows):
    dd_series = drawdown_series(rows)
    finite_dd = [v for v in dd_series if finite(v)]
    current = finite_dd[-1] if finite_dd else None
    max_depth = min(finite_dd) if finite_dd else None
    # underwater days = số phiên liên tiếp gần nhất price < peak
    underwater = 0
    for v in reversed(dd_series):
        if finite(v) and v < 0:
            underwater += 1
        else:
            break
    episodes = drawdown_episodes(rows)
    recovery_days = [e.get("recovery_days") for e in episodes if finite(e.get("recovery_days"))]
    return {
        "current_drawdown_pct": round_(current*100) if finite(current) else None,
        "current_underwater_days": underwater,
        "max_drawdown_pct": round_(max_depth*100) if finite(max_depth) else None,
        "episode_count": len(episodes),
        "deep_drawdown_count_10_pct": sum(1 for e in episodes if (e.get("depth_pct") or 0) <= -10),
        "deep_drawdown_count_20_pct": sum(1 for e in episodes if (e.get("depth_pct") or 0) <= -20),
        "deep_drawdown_count_30_pct": sum(1 for e in episodes if (e.get("depth_pct") or 0) <= -30),
        "median_recovery_days": round_(median(recovery_days), 0) if recovery_days else None,
        "worst_episodes": episodes[:5],
        "max_runup": max_runup_profile(rows),
        "interpretation_guardrail": "Mức giảm từ đỉnh nhạy với cửa sổ và dữ liệu chưa điều chỉnh sự kiện vốn; không phải dự báo đáy/đỉnh.",
    }

def max_runup_profile(rows):
    if not rows:
        return None
    low_idx = 0
    best = {"value_pct": None, "low_date": rows[0].get("date"), "high_date": rows[0].get("date")}
    for i, row in enumerate(rows):
        if row.get("close") < rows[low_idx].get("close"):
            low_idx = i
        low = rows[low_idx].get("close")
        if low and low > 0:
            v = (row.get("close")/low - 1) * 100
            if not finite(best["value_pct"]) or v > best["value_pct"]:
                best = {"value_pct": round_(v), "low_date": rows[low_idx].get("date"), "high_date": row.get("date")}
    return best
```

---

## B4. liquidity_profile <a name="b4"></a>



```python
def liquidity_profile(rows):
    latest = rows[-1] if rows else {}
    values_252 = [finite(r.get("value")) for r in rows[-252:]]
    values_252 = [v for v in values_252 if v is not None]
    avg20 = average_value(rows, 20)
    avg60 = average_value(rows, 60)
    latest_value = finite(latest.get("value"))
    # volume spike days = volume > 2x avg20
    spike_days = 0
    for i in range(max(0, len(rows)-252), len(rows)):
        vol = finite(rows[i].get("volume"))
        avg20_at = sma_at(rows, i-1, "volume", 20)
        if vol and avg20_at and avg20_at > 0 and vol >= 2*avg20_at:
            spike_days += 1
    return {
        "latest_volume": latest.get("volume"),
        "latest_value": latest_value,
        "avg_value_20d": avg20,
        "avg_value_60d": avg60,
        "latest_value_percentile_1y": percentile_of_value(values_252, latest_value),
        "liquidity_stability": round_(std_dev(values_252)/mean(values_252) * 100)
            if values_252 and mean(values_252) else None,  # CV%
        "volume_spike_days_1y": spike_days,
        "interpretation_guardrail": "Thanh khoản tính từ giá đóng cửa × khối lượng; không phản ánh block trade, sổ lệnh hay dữ liệu intraday.",
    }
```

---

## B5. return_distribution_profile <a name="b5"></a>



```python
def return_distribution_profile(rows):
    daily = daily_returns_pct(rows)
    one_year = daily[-252:]
    histogram_bins = [
        ("<= -10%", float("-inf"), -10), ("-10% đến -5%", -10, -5),
        ("-5% đến -2%", -5, -2), ("-2% đến 0%", -2, 0),
        ("0% đến 2%", 0, 2), ("2% đến 5%", 2, 5),
        ("5% đến 10%", 5, 10), ("> 10%", 10, float("inf")),
    ]
    def stats(sample):
        return {
            "observations": len(sample),
            "mean_pct": round_(mean(sample), 4),
            "median_pct": round_(median(sample), 4),
            "std_pct": round_(std_dev(sample), 4),
            "p01_pct": round_(quantile(sample, 0.01), 4),
            "p05_pct": round_(quantile(sample, 0.05), 4),
            "p25_pct": round_(quantile(sample, 0.25), 4),
            "p75_pct": round_(quantile(sample, 0.75), 4),
            "p95_pct": round_(quantile(sample, 0.95), 4),
            "p99_pct": round_(quantile(sample, 0.99), 4),
            "iqr_pct": round_(quantile(sample, 0.75) - quantile(sample, 0.25), 4),
            "skewness": round_(skewness(sample), 4),
            "excess_kurtosis": round_(excess_kurtosis(sample), 4),
            "positive_day_rate_pct": round_(sum(1 for v in sample if v > 0)/len(sample)*100) if sample else None,
        }
    return {
        "full_sample": stats(daily),
        "one_year": stats(one_year),
        "one_year_histogram": [
            {"label": lbl, "count": sum(1 for v in one_year if mn < v <= mx)}
            for lbl, mn, mx in histogram_bins
        ],
        "interpretation_guardrail": "Phân phối lợi suất là thống kê mô tả quá khứ; không giả định phân phối chuẩn và không dự báo lợi suất tương lai.",
    }
```

---

## B6. tail_risk_profile <a name="b6"></a>

Historical VaR/ES (không phải mô hình).

```python
def tail_risk_profile(rows):
    daily = daily_returns_pct(rows)
    tail = daily[-252:]
    q05 = quantile(tail, 0.05)
    q01 = quantile(tail, 0.01)
    es05 = mean([v for v in tail if v <= q05]) if finite(q05) else None
    es01 = mean([v for v in tail if v <= q01]) if finite(q01) else None
    rolling21 = [v for v in rolling_return_series(rows, 21) if finite(v)]
    rolling63 = [v for v in rolling_return_series(rows, 63) if finite(v)]
    return {
        "observations_1y": len(tail),
        "historical_var_95_1d_pct": round_(abs(q05), 4) if finite(q05) else None,
        "historical_var_99_1d_pct": round_(abs(q01), 4) if finite(q01) else None,
        "expected_shortfall_95_1d_pct": round_(abs(es05), 4) if finite(es05) else None,
        "expected_shortfall_99_1d_pct": round_(abs(es01), 4) if finite(es01) else None,
        "down_5pct_days_1y": sum(1 for v in tail if v <= -5),
        "down_10pct_days_1y": sum(1 for v in tail if v <= -10),
        "rolling_21d_p05_pct": round_(quantile(rolling21, 0.05)),
        "rolling_63d_p05_pct": round_(quantile(rolling63, 0.05)),
        "interpretation_guardrail": "Tail risk dùng lịch sử đã quan sát; VaR/ES ở đây là mô tả historical, không phải mô hình rủi ro giao dịch.",
    }
```

---

## B7. liquidity_risk_profile <a name="b7"></a>

Stress test theo value lịch sử.

```python
def liquidity_risk_profile(rows):
    tail = rows[-252:]
    values = [finite(r.get("value")) for r in tail]
    values = [v for v in values if v is not None and v >= 0]
    latest = rows[-1] if rows else {}
    avg20 = average_value(rows, 20)
    avg60 = average_value(rows, 60)
    med252 = median(values)
    drought_thr = med252 * 0.5 if finite(med252) else None
    severe_thr = med252 * 0.2 if finite(med252) else None
    capacity20 = avg20 * 0.1 if finite(avg20) else None
    capacity60 = avg60 * 0.1 if finite(avg60) else None
    def days_to_trade(notional):
        return {
            "notional": notional,
            "at_10pct_adv20_days": round_(notional/capacity20, 2) if capacity20 else None,
            "at_10pct_adv60_days": round_(notional/capacity60, 2) if capacity60 else None,
        }
    zero_vol = sum(1 for r in tail if (r.get("volume") or 0) <= 0)
    thin_days = sum(1 for r in tail if finite(r.get("value")) and r["value"] <= severe_thr) if severe_thr else 0
    drought_days = sum(1 for r in tail if finite(r.get("value")) and r["value"] <= drought_thr) if drought_thr else 0
    label = "trung bình"
    if zero_vol > 5 or thin_days >= 40 or (finite(avg20) and finite(med252) and avg20 < med252*0.4):
        label = "cao"
    if zero_vol == 0 and thin_days < 10 and finite(avg20) and finite(med252) and avg20 >= med252*0.8:
        label = "thấp"
    return {
        "observations_1y": len(tail),
        "latest_value": latest.get("value"),
        "median_value_1y": round_(med252, 0) if finite(med252) else None,
        "avg_value_20d": avg20,
        "avg_value_60d": avg60,
        "latest_value_percentile_1y": percentile_of_value(values, latest.get("value")),
        "zero_volume_days_1y": zero_vol,
        "value_drought_days_1y": drought_days,
        "severe_thin_value_days_1y": thin_days,
        "trade_capacity_scenarios": [days_to_trade(n) for n in (1_000_000_000, 5_000_000_000, 10_000_000_000)],
        "liquidity_risk_label": label,
        "interpretation_guardrail": "Rủi ro thanh khoản chỉ là stress test theo giá trị giao dịch lịch sử; không phản ánh sổ lệnh thời gian thực hoặc chi phí trượt giá thực tế.",
    }
```

---

## B8. relative_strength + dynamic_beta + correlation <a name="b8"></a>

Cần benchmark (VNINDEX) series.

```python
def paired_rows(stock_rows, bench_rows):
    """Pair theo date (inner join), trả list of {date, stock:{close}, benchmark:{close}}."""
    bench_by_date = {r.get("date"): r for r in bench_rows}
    out = []
    for r in stock_rows:
        b = bench_by_date.get(r.get("date"))
        if b and finite(r.get("close")) and finite(b.get("close")):
            out.append({"date": r.get("date"), "stock": r, "benchmark": b})
    return out

def benchmark_metrics(paired, window=252):
    """Trả {window, observations, stock_return_pct, benchmark_return_pct, relative_return_pct,
    correlation, beta, r2, hit_rate_pct, stock_max_drawdown_pct, benchmark_max_drawdown_pct,
    drawdown_similarity}."""
    pairs = paired[-(window+1):]
    if len(pairs) < max(5, window // 2):
        return None
    # returns dạng decimal
    stock_rets, bench_rets = [], []
    for i in range(1, len(pairs)):
        sp, sc = pairs[i-1]["stock"]["close"], pairs[i]["stock"]["close"]
        bp, bc = pairs[i-1]["benchmark"]["close"], pairs[i]["benchmark"]["close"]
        if sp > 0 and bp > 0:
            stock_rets.append(sc/sp - 1); bench_rets.append(bc/bp - 1)
    if len(stock_rets) < max(5, window // 2):
        return None
    stock_cum = 1.0; bench_cum = 1.0
    for s, b in zip(stock_rets, bench_rets):
        stock_cum *= (1+s); bench_cum *= (1+b)
    stock_ret = stock_cum - 1; bench_ret = bench_cum - 1
    # correlation & beta
    ms = sum(stock_rets)/len(stock_rets)
    mb = sum(bench_rets)/len(bench_rets)
    cs = [s-ms for s in stock_rets]; cb = [b-mb for b in bench_rets]
    cov = sum(x*y for x, y in zip(cs, cb)) / (len(stock_rets) - 1)
    var = sum(x*x for x in cb) / (len(bench_rets) - 1)
    beta = cov/var if var else None
    den_corr = (sum(x*x for x in cs)**0.5) * (sum(y*y for y in cb)**0.5)
    corr = sum(x*y for x, y in zip(cs, cb))/den_corr if den_corr else None
    r2 = corr*corr if finite(corr) else None
    hit_rate = sum(1 for s, b in zip(stock_rets, bench_rets) if s > b) / len(stock_rets) * 100
    # drawdown similarity
    stock_dd = drawdown_series([p["stock"] for p in pairs])
    bench_dd = drawdown_series([p["benchmark"] for p in pairs])
    dd_pairs = [(s, b) for s, b in zip(stock_dd, bench_dd) if finite(s) and finite(b)]
    if dd_pairs:
        ds = [x[0] for x in dd_pairs]; db = [x[1] for x in dd_pairs]
        ms2 = sum(ds)/len(ds); mb2 = sum(db)/len(db)
        cs2 = [x-ms2 for x in ds]; cb2 = [x-mb2 for x in db]
        den2 = (sum(x*x for x in cs2)**0.5) * (sum(y*y for y in cb2)**0.5)
        dd_sim = sum(x*y for x, y in zip(cs2, cb2))/den2 if den2 else None
    else:
        dd_sim = None
    return {
        "window": window,
        "observations": len(stock_rets),
        "stock_return_pct": round_(stock_ret*100),
        "benchmark_return_pct": round_(bench_ret*100),
        "relative_return_pct": round_((stock_ret - bench_ret)*100),
        "correlation": round_(corr, 4),
        "beta": round_(beta, 4),
        "r2": round_(r2, 4) if finite(r2) else None,
        "hit_rate_pct": round_(hit_rate),
        "stock_max_drawdown_pct": round_(min(ds for ds in stock_dd if finite(ds))*100) if any(finite(x) for x in stock_dd) else None,
        "benchmark_max_drawdown_pct": round_(min(db for db in bench_dd if finite(db))*100) if any(finite(x) for x in bench_dd) else None,
        "drawdown_similarity": round_(dd_sim, 4) if finite(dd_sim) else None,
    }

def relative_strength_profile(stock_rows, bench_rows, benchmarks=("VNINDEX", "VN30")):
    """Tính metrics cho nhiều benchmark + best-fit + dynamic_beta + correlation.
    `benchmarks` = dict {id: rows}. Trả 3 sub-profile."""
    # Sử dụng cho từng benchmark
    comparisons = []
    for bid, brows in benchmarks.items():
        paired = paired_rows(stock_rows, brows)
        metrics = {str(w): benchmark_metrics(paired, w) for w in (60, 120, 252)}
        comparisons.append({"benchmark": bid, "metrics": metrics})
    best_fit = None
    for c in comparisons:
        r2_252 = c["metrics"].get("252", {}).get("r2") if c["metrics"].get("252") else None
        if finite(r2_252) and (best_fit is None or r2_252 > best_fit["r2_252"]):
            best_fit = {"benchmark": c["benchmark"], "r2_252": r2_252}
    vnindex = next((c for c in comparisons if c["benchmark"] == "VNINDEX"), None)
    vni_252 = vnindex["metrics"]["252"] if vnindex and vnindex["metrics"].get("252") else {}
    return {
        "relative_strength_profile": {
            "best_fit_benchmark": best_fit,
            "comparisons": comparisons,
            "interpretation_guardrail": "So sánh benchmark là mô tả lịch sử theo dữ liệu hiện có, không phải tín hiệu dự báo.",
        },
        "dynamic_beta_profile": {
            "primary_benchmark": "VNINDEX",
            "beta_60": vnindex["metrics"]["60"]["beta"] if vnindex and vnindex["metrics"].get("60") else None,
            "beta_120": vnindex["metrics"]["120"]["beta"] if vnindex and vnindex["metrics"].get("120") else None,
            "beta_252": vni_252.get("beta"),
        },
        "correlation_profile": {
            "primary_benchmark": "VNINDEX",
            "corr_60": vnindex["metrics"]["60"]["correlation"] if vnindex and vnindex["metrics"].get("60") else None,
            "corr_252": vni_252.get("correlation"),
            "r2_252": vni_252.get("r2"),
            "drawdown_similarity_252": vni_252.get("drawdown_similarity"),
        },
    }
```

**Ngưỡng R² (từ `ANALYTICS_STANDARD.md:62-71`):**
- `R² < 0.40` → **low** (beta không đáng đọc sâu)
- `0.40 ≤ R² ≤ 0.70` → **medium**
- `R² > 0.70` → **high** (beta đáng tin)

---

## B9. regime_profile <a name="b9"></a>

Phân loại trạng thái thị trường theo VNINDEX.

```python
def classify_regime(r60, r120, drawdown, vol_rank):
    """Trả {id, label, r60, r120, drawdown_pct, vol_rank}.
    r60/r120/drawdown dạng decimal. vol_rank = percentile 0-100."""
    if not all(finite(x) for x in (r60, r120, drawdown)):
        return {"id": "unknown", "label": "chưa đủ dữ liệu"}
    if drawdown <= -0.18 or (r60 <= -0.12 and (vol_rank or 0) >= 75):
        rid = "stress"; label = "stress"
    elif r60 > 0.06 and r120 > 0.08 and drawdown > -0.08:
        rid = "uptrend"; label = "uptrend"
    elif r60 > 0.04 and r120 <= 0.08 and drawdown > -0.14:
        rid = "recovery"; label = "phục hồi"
    else:
        rid = "sideways"; label = "sideways"
    return {"id": rid, "label": label,
            "r60": round_(r60*100), "r120": round_(r120*100),
            "drawdown_pct": round_(drawdown*100), "vol_rank": vol_rank}

def regime_profile(stock_rows, vnindex_rows):
    """current_market_regime + behavior_by_market_regime (stock avg ret per regime)."""
    # Tính regime cho mỗi ngày VNINDEX
    rows = vnindex_rows
    regimes_by_date = {}
    for i, row in enumerate(rows):
        if i < 120:
            continue
        r60 = (row["close"]/rows[i-60]["close"] - 1) if rows[i-60].get("close") else None
        r120 = (row["close"]/rows[i-120]["close"] - 1) if rows[i-120].get("close") else None
        dd = drawdown_series(rows[:i+1])[-1]
        # vol rank = percentile của HV20 tại i
        vol_hist = realized_vol_history(rows[:i+1], 20)
        vol_now = vol_hist[-1] if vol_hist else None
        vol_rank = percentile_of_value(vol_hist, vol_now) if finite(vol_now) else None
        regimes_by_date[row["date"]] = classify_regime(r60, r120, dd, vol_rank)
    # Current regime
    current = regimes_by_date.get(rows[-1]["date"]) if rows else None
    # Behavior by regime: group stock returns theo regime
    paired = paired_rows(stock_rows, vnindex_rows)
    groups = {}
    for i in range(1, len(paired)):
        sp, sc = paired[i-1]["stock"]["close"], paired[i]["stock"]["close"]
        bp, bc = paired[i-1]["benchmark"]["close"], paired[i]["benchmark"]["close"]
        regime = regimes_by_date.get(paired[i]["date"])
        if not regime or regime["id"] == "unknown" or not (sp > 0 and bp > 0):
            continue
        rid = regime["id"]
        g = groups.setdefault(rid, {"regime_id": rid, "regime_label": regime["label"],
                                     "stock_returns": [], "bench_returns": []})
        g["stock_returns"].append(sc/sp - 1)
        g["bench_returns"].append(bc/bp - 1)
    behavior = []
    for g in groups.values():
        srs, brs = g["stock_returns"], g["bench_returns"]
        if not srs:
            continue
        behavior.append({
            "regime_id": g["regime_id"], "regime_label": g["regime_label"],
            "observations": len(srs),
            "stock_avg_daily_return_pct": round_(mean(srs)*100, 4),
            "benchmark_avg_daily_return_pct": round_(mean(brs)*100, 4),
            "relative_avg_daily_return_pct": round_((mean(srs) - mean(brs))*100, 4),
            "hit_rate_pct": round_(sum(1 for s, b in zip(srs, brs) if s > b)/len(srs)*100),
        })
    behavior.sort(key=lambda x: x["regime_id"])
    return {
        "primary_benchmark": "VNINDEX",
        "current_market_regime": current,
        "behavior_by_market_regime": behavior,
        "regime_guardrail": "Regime dùng trạng thái benchmark hiện có; không thay thế lịch sử thành phần point-in-time.",
    }
```

---

## B10. volume_price_profile <a name="b10"></a>

(compact). Đo up/down value & correlation.

```python
def volume_price_profile(rows):
    tail = rows[-252:]
    up_value = [finite(r.get("value")) for i, r in enumerate(tail) if i > 0 and finite(r.get("value"))
                and finite(tail[i-1].get("close")) and r.get("close") > tail[i-1].get("close")]
    down_value = [finite(r.get("value")) for i, r in enumerate(tail) if i > 0 and finite(r.get("value"))
                  and finite(tail[i-1].get("close")) and r.get("close") < tail[i-1].get("close")]
    up_value = [v for v in up_value if v is not None]
    down_value = [v for v in down_value if v is not None]
    avg_up = mean(up_value); avg_down = mean(down_value)
    # correlation giữa abs(return) và value
    pairs = []
    for i in range(1, len(tail)):
        ret = finite(tail[i].get("close")) and finite(tail[i-1].get("close"))
        if ret and tail[i-1]["close"] > 0 and finite(tail[i].get("value")):
            pairs.append((abs(tail[i]["close"]/tail[i-1]["close"] - 1), tail[i]["value"]))
    if len(pairs) >= 5:
        xs = [p[0] for p in pairs]; ys = [p[1] for p in pairs]
        mx, my = mean(xs), mean(ys)
        cx = [x-mx for x in xs]; cy = [y-my for y in ys]
        den = (sum(x*x for x in cx)**0.5) * (sum(y*y for y in cy)**0.5)
        ret_value_corr = round_(sum(x*y for x, y in zip(cx, cy))/den, 4) if den else None
    else:
        ret_value_corr = None
    return {
        "observations_1y": len(tail),
        "avg_value_up_days": round_(avg_up) if avg_up else None,
        "avg_value_down_days": round_(avg_down) if avg_down else None,
        "up_down_value_ratio_1y": round_(avg_up/avg_down, 4) if avg_up and avg_down else None,
        "abs_return_value_correlation_1y": ret_value_corr,
        "interpretation_guardrail": "Quan hệ giá-khối lượng là đồng biến hay nghịch biến trong quá khứ; không kết luận dòng tiền tương lai.",
    }
```

---

## B11. volume_price_confirmation_profile (VPCI) <a name="b11"></a>

VPCI = VPC × VPR × VM.

```python
def vpci_profile(rows, short_window=20, long_window=100):
    series = []
    for i, row in enumerate(rows):
        sma_s = sma_at(rows, i, "close", short_window)
        sma_l = sma_at(rows, i, "close", long_window)
        vwma_s = vwma_at(rows, i, "close", short_window)
        vwma_l = vwma_at(rows, i, "close", long_window)
        avg_vol_s = sma_at(rows, i, "volume", short_window)
        avg_vol_l = sma_at(rows, i, "volume", long_window)
        vpc = (vwma_l - sma_l) if (finite(vwma_l) and finite(sma_l)) else None
        vpr = (vwma_s / sma_s) if (finite(vwma_s) and finite(sma_s) and sma_s) else None
        vm = (avg_vol_s / avg_vol_l) if (finite(avg_vol_s) and finite(avg_vol_l) and avg_vol_l > 0) else None
        vpci = (vpc * vpr * vm) if all(finite(x) for x in (vpc, vpr, vm)) else None
        series.append({"date": row.get("date"), "value": vpci,
                       "sma_short": sma_s, "sma_long": sma_l,
                       "volume_ratio_short_long": vm})
    valid = [s for s in series if finite(s.get("value"))]
    latest = series[-1] if series else {}
    latest_valid = valid[-1] if valid else {}
    latest_close = rows[-1].get("close") if rows else None
    price_vs_sma_long = (round_((latest_close/latest["sma_long"] - 1)*100)
                         if finite(latest_close) and finite(latest.get("sma_long")) and latest["sma_long"]
                         else None)
    vpci_change_20d = line_change_pct(valid, 20)
    label = confirmation_label(latest_valid.get("value"), vpci_change_20d,
                                price_vs_sma_long, latest.get("volume_ratio_short_long"))
    return {
        "methodology": "VPCI/VWMA/SMA daily OHLCV, fixed windows 20/100",
        "short_window": short_window, "long_window": long_window,
        "observations": len(rows), "valid_observations": len(valid),
        "sma_20": latest.get("sma_short"), "sma_100": latest.get("sma_long"),
        "price_vs_sma100_pct": price_vs_sma_long,
        "vpci_latest": latest_valid.get("value"),
        "vpci_20d_change_pct": vpci_change_20d,
        "vpci_percentile_1y": percentile_of_value([v["value"] for v in valid[-252:]], latest_valid.get("value")),
        "confirmation_label": label,
        "interpretation_guardrail": "VPCI/VWMA/SMA mô tả mức đồng thuận giữa giá và volume; không phải tín hiệu giao dịch hay dự báo giá.",
    }

def confirmation_label(vpci_latest, vpci_change_20d, price_vs_sma_long, volume_ratio):
    known = [v for v in (vpci_latest, price_vs_sma_long, volume_ratio) if finite(v)]
    if len(known) < 2:
        return "chưa đủ dữ liệu"
    vc = vpci_change_20d or 0
    if finite(vpci_latest) and vpci_latest > 0 and vc >= 0 and (price_vs_sma_long or 0) >= 0 and (volume_ratio or 0) >= 0.8:
        return "giá-volume cùng xác nhận"
    if finite(vpci_latest) and vpci_latest < 0 and vc <= 0 and (price_vs_sma_long or 0) <= 0 and (volume_ratio or 0) >= 0.8:
        return "giá-volume cùng suy yếu"
    if (price_vs_sma_long or 0) >= 0 and (finite(vpci_latest) and vpci_latest <= 0):
        return "giá đi trước volume"
    if (price_vs_sma_long or 0) <= 0 and (finite(vpci_latest) and vpci_latest >= 0):
        return "volume không cùng chiều giá"
    return "hỗn hợp"
```

---

## B12. money_flow_pressure_profile (OBV/VPT/CMF) <a name="b12"></a>



```python
def money_flow_profile(rows):
    # OBV + VPT cumulative
    cum = []; obv = 0; vpt = 0
    for i in range(1, len(rows)):
        p, r = rows[i-1], rows[i]
        if not (p.get("close", 0) > 0 and r.get("close", 0) > 0) or not finite(r.get("volume")):
            continue
        ret = r["close"]/p["close"] - 1
        if r["close"] > p["close"]:
            obv += r["volume"]
        elif r["close"] < p["close"]:
            obv -= r["volume"]
        vpt += r["volume"] * ret
        cum.append({"date": r.get("date"), "obv": obv, "vpt": vpt,
                    "ret_pct": ret*100, "volume": r["volume"]})
    # CMF 20 & 60
    cmf20 = cmf_at(rows, len(rows)-1, 20)
    cmf60 = cmf_at(rows, len(rows)-1, 60)
    latest = cum[-1] if cum else {}
    vpt_chg = line_change_pct([{"value": c["vpt"]} for c in cum], 20)
    obv_chg = line_change_pct([{"value": c["obv"]} for c in cum], 20)
    label = money_flow_label(cmf20, cmf60, vpt_chg, obv_chg)
    tail = cum[-252:]
    return {
        "methodology": "OBV, VPT, CMF daily OHLCV, fixed windows 20/60",
        "observations": len(rows), "valid_observations": len(cum),
        "latest_date": latest.get("date"),
        "obv_latest": round_(latest.get("obv"), 0) if latest.get("obv") is not None else None,
        "vpt_latest": round_(latest.get("vpt"), 4) if latest.get("vpt") is not None else None,
        "obv_20d_change_pct": vpt_chg,  # lưu ý: source dùng line_change_pct
        "vpt_20d_change_pct": vpt_chg,
        "cmf_20d": round_(cmf20, 4) if finite(cmf20) else None,
        "cmf_60d": round_(cmf60, 4) if finite(cmf60) else None,
        "positive_flow_days_1y": sum(1 for c in tail if c["ret_pct"] > 0 and c.get("volume", 0) > 0),
        "negative_flow_days_1y": sum(1 for c in tail if c["ret_pct"] < 0 and c.get("volume", 0) > 0),
        "money_flow_label": label,
        "interpretation_guardrail": "Money flow mô tả áp lực từ OHLCV ngày; không thay thế dữ liệu intraday, block trade, sổ lệnh hoặc khuyến nghị giao dịch.",
    }

def cmf_at(rows, index, window=20):
    sample = rows[max(0, index-window+1):index+1]
    sample = [r for r in sample if all(finite(r.get(f)) for f in ("high", "low", "close", "volume")) and r["volume"] > 0]
    if len(sample) < max(5, window // 2):
        return None
    vol_sum = sum(r["volume"] for r in sample)
    if not vol_sum:
        return None
    flow = 0
    for r in sample:
        rng = r["high"] - r["low"]
        if not rng:
            continue
        mult = ((r["close"] - r["low"]) - (r["high"] - r["close"])) / rng
        flow += mult * r["volume"]
    return flow / vol_sum

def money_flow_label(cmf20, cmf60, vpt_chg, obv_chg):
    vals = [v for v in (cmf20, cmf60, vpt_chg, obv_chg) if finite(v)]
    pos = sum(1 for v in vals if v > 0); neg = sum(1 for v in vals if v < 0)
    if pos + neg < 2:
        return "chưa đủ dữ liệu"
    if pos >= 3 and (cmf20 or 0) > 0.03 and (cmf60 or 0) >= 0:
        return "áp lực tiền dương"
    if neg >= 3 and (cmf20 or 0) < -0.03 and (cmf60 or 0) <= 0:
        return "áp lực tiền âm"
    if pos >= 3 and (not finite(cmf20) or cmf20 >= 0) and (not finite(cmf60) or cmf60 >= -0.03):
        return "nghiêng dương nhưng yếu"
    if neg >= 3 and (not finite(cmf20) or cmf20 <= 0) and (not finite(cmf60) or cmf60 <= 0.03):
        return "nghiêng âm nhưng yếu"
    return "hỗn hợp"
```

---

## B13. effort_result_profile (Wyckoff) <a name="b13"></a>


- **Effort** = mean(normalized_volume_20d, normalized_value_20d) — mức nỗ lực giao dịch so trung bình.
- **Result** = max(|return|, intraday range) — kết quả giá.

```python
def effort_result_profile(rows):
    obs = []
    for i in range(1, len(rows)):
        p, r = rows[i-1], rows[i]
        if not (p.get("close", 0) > 0 and r.get("close", 0) > 0):
            continue
        vol_avg20 = moving_average_before(rows, i, "volume", 20)
        val_avg20 = moving_average_before(rows, i, "value", 20)
        ret = (r["close"]/p["close"] - 1) * 100
        rng = (finite(r.get("range_pct")) and r["range_pct"]
               or (r["high"]-r["low"])/p["close"]*100 if (finite(r.get("high")) and finite(r.get("low"))) else None)
        vol_ratio = (r["volume"]/vol_avg20) if (finite(r.get("volume")) and finite(vol_avg20) and vol_avg20 > 0) else None
        val_ratio = (r["value"]/val_avg20) if (finite(r.get("value")) and finite(val_avg20) and val_avg20 > 0) else None
        effort = mean([v for v in (vol_ratio, val_ratio) if finite(v)])
        result = max(abs(ret) if finite(ret) else 0, rng if finite(rng) else 0)
        obs.append({"date": r.get("date"), "ret_pct": ret, "abs_ret_pct": abs(ret),
                    "range_pct": rng, "effort_ratio": effort, "result_pct": result,
                    "result_per_effort": (result/effort) if (finite(effort) and effort > 0) else None})
    tail = obs[-252:]
    result_vals = [o["result_pct"] for o in tail if finite(o.get("result_pct"))]
    rpe_vals = [o["result_per_effort"] for o in tail if finite(o.get("result_per_effort"))]
    result_median = median(result_vals); result_p75 = quantile(result_vals, 0.75)
    rpe_median = median(rpe_vals)
    high_effort = [o for o in tail if finite(o.get("effort_ratio")) and o["effort_ratio"] >= 2]
    low_rhe = [o for o in high_effort if finite(o.get("result_pct")) and finite(result_median) and o["result_pct"] <= result_median]
    high_rhe = [o for o in high_effort if finite(o.get("result_pct")) and finite(result_p75) and o["result_pct"] >= result_p75]
    latest = obs[-1] if obs else {}
    label = effort_result_label(len(low_rhe), len(high_rhe), len(high_effort),
                                 latest.get("effort_ratio"), latest.get("result_per_effort"), rpe_median)
    return {
        "methodology": "Effort = avg(normalized volume 20D, normalized value 20D); Result = max(abs return, intraday range)",
        "observations_1y": len(tail),
        "high_effort_days_1y": len(high_effort),
        "low_result_high_effort_days_1y": len(low_rhe),
        "high_result_high_effort_days_1y": len(high_rhe),
        "low_result_high_effort_share_pct": round_(len(low_rhe)/len(high_effort)*100) if high_effort else None,
        "high_result_high_effort_share_pct": round_(len(high_rhe)/len(high_effort)*100) if high_effort else None,
        "median_result_pct_1y": round_(result_median, 4) if finite(result_median) else None,
        "median_result_per_effort_1y": round_(rpe_median, 4) if finite(rpe_median) else None,
        "latest_effort_ratio": latest.get("effort_ratio"),
        "latest_result_pct": latest.get("result_pct"),
        "effort_result_label": label,
        "interpretation_guardrail": "Effort-result đo từ dữ liệu ngày để nhận diện phiên nhiều giao dịch nhưng biến động tương ứng thấp/cao; không kết luận hấp thụ/cạn cung theo nghĩa tín hiệu.",
    }

def effort_result_label(low_cnt, high_cnt, he_cnt, latest_effort, latest_rpe, median_rpe):
    if not he_cnt:
        return "chưa đủ high-effort events"
    low_share = low_cnt / he_cnt; high_share = high_cnt / he_cnt
    if (finite(latest_effort) and latest_effort >= 2 and finite(latest_rpe) and finite(median_rpe)
            and latest_rpe <= median_rpe * 0.7):
        return "effort cao, result thấp"
    if low_share >= 0.45:
        return "thường có effort cao nhưng result thấp"
    if high_share >= 0.45:
        return "effort cao thường đi cùng result lớn"
    return "effort-result hỗn hợp"
```

---

## B14. high_volume_behavior_profile <a name="b14"></a>

Event study: forward returns sau volume ≥ 2x avg20.

```python
def high_volume_behavior_profile(rows, threshold=2):
    events = []
    for i in range(1, len(rows)):
        r, p = rows[i], rows[i-1]
        avg20 = moving_average_before(rows, i, "volume", 20)
        if not (finite(r.get("volume")) and finite(avg20) and avg20 > 0
                and p.get("close", 0) > 0 and r.get("close", 0) > 0):
            continue
        norm_vol = r["volume"] / avg20
        if norm_vol < threshold:
            continue
        events.append({
            "date": r.get("date"), "close": r["close"], "volume": r["volume"],
            "normalized_volume_20d": round_(norm_vol, 4),
            "same_day_return_pct": round_((r["close"]/p["close"] - 1)*100, 4),
            "forward_return_5d_pct": round_(forward_return(rows, i, 5), 4),
            "forward_return_20d_pct": round_(forward_return(rows, i, 20), 4),
            "forward_return_60d_pct": round_(forward_return(rows, i, 60), 4),
        })
    events_1y = events[-252:]  # xấp xỉ 1 năm
    stats20 = forward_window_stats(events, "forward_return_20d_pct")
    label = high_volume_behavior_label(stats20, len(events))
    return {
        "methodology": "High-volume event = volume >= 2x trailing 20D average; forward returns measured after event close",
        "threshold_normalized_volume_20d": threshold,
        "observations": len(rows),
        "event_count_full_sample": len(events),
        "event_count_1y": len(events_1y),
        "forward_5d": forward_window_stats(events, "forward_return_5d_pct"),
        "forward_20d": stats20,
        "forward_60d": forward_window_stats(events, "forward_return_60d_pct"),
        "post_high_volume_label": label,
        "latest_high_volume_event": events[-1] if events else None,
        "recent_high_volume_events": events[-12:],
        "interpretation_guardrail": "Event study mô tả điều đã xảy ra sau các phiên volume cao; không dùng để dự báo phiên kế tiếp hoặc sinh tín hiệu mua bán.",
    }

def forward_return(rows, index, window):
    if index + window >= len(rows):
        return None
    start = rows[index].get("close"); end = rows[index+window].get("close")
    if not (start and end and start > 0 and end > 0):
        return None
    return (end/start - 1) * 100

def forward_window_stats(events, key):
    matured = [e for e in events if finite(e.get(key))]
    vals = [e[key] for e in matured]
    return {
        "matured_events": len(matured),
        "median_pct": round_(median(vals), 4),
        "p25_pct": round_(quantile(vals, 0.25), 4),
        "p75_pct": round_(quantile(vals, 0.75), 4),
        "positive_rate_pct": round_(sum(1 for v in vals if v > 0)/len(vals)*100) if vals else None,
    }

def high_volume_behavior_label(stats20, event_count):
    if event_count < 5 or stats20.get("matured_events", 0) < 5:
        return "chưa đủ high-volume events"
    if (stats20.get("positive_rate_pct") or 0) >= 60 and (stats20.get("median_pct") or 0) > 0:
        return "sau volume cao thường giữ giá tốt hơn"
    if (stats20.get("positive_rate_pct") or 100) <= 40 and (stats20.get("median_pct") or 0) < 0:
        return "sau volume cao thường suy yếu"
    return "hành vi sau volume cao hỗn hợp"
```

---

## B15. pvi_nvi_participation_profile <a name="b15"></a>

PVI cập nhật phiên volume tăng; NVI phiên volume giảm; base=1000.

```python
def pvi_nvi_profile(rows):
    series = []; pvi = 1000.0; nvi = 1000.0
    for i in range(1, len(rows)):
        p, r = rows[i-1], rows[i]
        if not (p.get("close", 0) > 0 and r.get("close", 0) > 0) or not finite(p.get("volume")) or not finite(r.get("volume")):
            continue
        ret = r["close"]/p["close"] - 1
        if r["volume"] > p["volume"]:
            pvi *= (1 + ret)
        if r["volume"] < p["volume"]:
            nvi *= (1 + ret)
        direction = "higher_volume" if r["volume"] > p["volume"] else ("lower_volume" if r["volume"] < p["volume"] else "same_volume")
        series.append({"date": r.get("date"), "volume": r["volume"], "ret_pct": round_(ret*100, 4),
                       "pvi": round_(pvi, 4), "nvi": round_(nvi, 4), "volume_direction": direction})
    latest = series[-1] if series else {}
    pvi_chg20 = line_change_pct([{"value": s["pvi"]} for s in series], 20)
    nvi_chg20 = line_change_pct([{"value": s["nvi"]} for s in series], 20)
    pvi_chg60 = line_change_pct([{"value": s["pvi"]} for s in series], 60)
    nvi_chg60 = line_change_pct([{"value": s["nvi"]} for s in series], 60)
    pvi_nvi_ratio = (latest["pvi"]/latest["nvi"]) if (finite(latest.get("pvi")) and finite(latest.get("nvi")) and latest.get("nvi")) else None
    tail = series[-252:]
    label = pvi_nvi_label(pvi_chg20, nvi_chg20, pvi_nvi_ratio)
    return {
        "methodology": "PVI updates on higher-volume days; NVI updates on lower-volume days; base=1000",
        "observations": len(series),
        "latest_date": latest.get("date"),
        "pvi_latest": latest.get("pvi"), "nvi_latest": latest.get("nvi"),
        "pvi_nvi_ratio": round_(pvi_nvi_ratio, 4) if finite(pvi_nvi_ratio) else None,
        "pvi_20d_change_pct": pvi_chg20, "nvi_20d_change_pct": nvi_chg20,
        "pvi_60d_change_pct": pvi_chg60, "nvi_60d_change_pct": nvi_chg60,
        "pvi_percentile_1y": percentile_of_value([s["pvi"] for s in tail], latest.get("pvi")),
        "nvi_percentile_1y": percentile_of_value([s["nvi"] for s in tail], latest.get("nvi")),
        "higher_volume_days_1y": sum(1 for s in tail if s["volume_direction"] == "higher_volume"),
        "lower_volume_days_1y": sum(1 for s in tail if s["volume_direction"] == "lower_volume"),
        "participation_regime_label": label,
        "interpretation_guardrail": "PVI/NVI mô tả price change xảy ra nhiều hơn ở phiên volume tăng hay giảm; không phải tín hiệu giao dịch.",
    }

def pvi_nvi_label(pvi_chg20, nvi_chg20, pvi_nvi_ratio):
    known = [v for v in (pvi_chg20, nvi_chg20, pvi_nvi_ratio) if finite(v)]
    if len(known) < 2:
        return "chưa đủ dữ liệu"
    if (pvi_chg20 or 0) > 0 and (nvi_chg20 or 0) <= 0:
        return "high-volume participation nổi bật hơn"
    if (nvi_chg20 or 0) > 0 and (pvi_chg20 or 0) <= 0:
        return "low-volume participation nổi bật hơn"
    if (pvi_chg20 or 0) > 0 and (nvi_chg20 or 0) > 0:
        return "participation cùng chiều"
    if (pvi_chg20 or 0) < 0 and (nvi_chg20 or 0) < 0:
        return "participation cùng suy yếu"
    return "participation hỗn hợp"
```

---

## B16. volume_at_price_profile <a name="b16"></a>

Xấp xỉ VAP: gán volume/value vào bin theo typical-price, 12 bins trên 252 phiên.

```python
def volume_at_price_profile(rows, window=252, bin_count=12):
    tail = []
    for r in rows[-window:]:
        tp = typical_price(r)
        if finite(tp) and finite(r.get("volume")) and r["volume"] >= 0:
            tail.append({**r, "typical_price": tp})
    prices = [t["typical_price"] for t in tail]
    if not prices:
        return {"acceptance_label": "chưa đủ dữ liệu"}
    min_p, max_p = min(prices), max(prices)
    span = max(max_p - min_p, 0); step = span/bin_count if span > 0 else None
    bins = [{"bin_index": i, "days": 0, "volume": 0.0, "value": 0.0} for i in range(bin_count)]
    for t in tail:
        if not step:
            continue
        idx = max(0, min(bin_count-1, int((t["typical_price"] - min_p)/step)))
        bins[idx]["days"] += 1
        bins[idx]["volume"] += t.get("volume") or 0
        bins[idx]["value"] += t.get("value") or 0
    total_vol = sum(b["volume"] for b in bins) or 0
    total_val = sum(b["value"] for b in bins) or 0
    for b in bins:
        b["volume_share_pct"] = round_(b["volume"]/total_vol*100, 2) if total_vol else None
        b["value_share_pct"] = round_(b["value"]/total_val*100, 2) if total_val else None
    poc = sorted(bins, key=lambda b: b["volume"], reverse=True)[0] if bins else None
    top3 = sorted(bins, key=lambda b: b["volume"], reverse=True)[:3]
    conc = sum(b.get("volume_share_pct") or 0 for b in top3)
    latest_close = rows[-1].get("close") if rows else None
    if latest_close and step:
        cur_bin = bins[max(0, min(bin_count-1, int((latest_close - min_p)/step)))]
    else:
        cur_bin = None
    label = "chưa đủ dữ liệu"
    if len(tail) >= 60 and poc:
        if cur_bin and cur_bin["bin_index"] == poc["bin_index"]:
            label = "giá hiện tại nằm trong vùng volume lớn nhất"
        elif latest_close and latest_close > min_p + step*poc["bin_index"]:
            label = "giá hiện tại nằm trên vùng volume lớn nhất"
        elif latest_close:
            label = "giá hiện tại nằm dưới vùng volume lớn nhất"
        else:
            label = "volume-at-price hỗn hợp"
    return {
        "methodology": "Daily volume-at-price approximation: assigns each day volume/value to typical-price bins over trailing 252 sessions",
        "window": window, "bin_count": bin_count, "observations": len(tail),
        "price_min": round_(min_p, 4), "price_max": round_(max_p, 4),
        "point_of_control_bin_index": poc["bin_index"] if poc else None,
        "current_price_bin_index": cur_bin["bin_index"] if cur_bin else None,
        "volume_concentration_top3_pct": round_(conc, 2),
        "acceptance_label": label,
        "interpretation_guardrail": "VAP là xấp xỉ từ dữ liệu ngày; không thay thế volume profile intraday, order book hoặc phân bổ khớp lệnh thực tế trong phiên.",
    }

def typical_price(row):
    vals = [finite(row.get(f)) for f in ("high", "low", "close")]
    vals = [v for v in vals if v is not None]
    if len(vals) >= 3:
        return mean(vals)
    return finite(row.get("close"))
```

---

## B17. industry_peer_profile <a name="b17"></a>

Cần data ngành. **Guardrail**: peer theo phân loại hiện tại, KHÔNG point-in-time.

```python
def industry_peer_profile(symbol, symbol_metrics, peer_metrics_list):
    """symbol_metrics = {return_60d_pct, hv60_pct, avg_value_60d, ...}
    peer_metrics_list = list of cùng dict cho các mã cùng industry_group."""
    if not peer_metrics_list:
        return {
            "peer_count": 0,
            "industry_peer_guardrail": "Chưa có dữ liệu peer ngành; so sánh ngành chỉ là tham chiếu theo phân ngành hiện tại.",
        }
    def percentile_in(metric):
        vals = [p.get(metric) for p in peer_metrics_list + [symbol_metrics]]
        vals = [v for v in vals if finite(v)]
        return percentile_of_value(vals, symbol_metrics.get(metric))
    peer_returns = [p.get("return_60d_pct") for p in peer_metrics_list]
    peer_returns = [v for v in peer_returns if finite(v)]
    peer_vols = [p.get("hv60_pct") for p in peer_metrics_list]
    peer_vols = [v for v in peer_vols if finite(v)]
    peer_liq = [p.get("avg_value_60d") for p in peer_metrics_list]
    peer_liq = [v for v in peer_liq if finite(v)]
    return {
        "peer_count": len(peer_metrics_list),
        "peer_median_return_60d_pct": round_(median(peer_returns)) if peer_returns else None,
        "peer_median_hv60_pct": round_(median(peer_vols)) if peer_vols else None,
        "peer_median_value_60d": round_(median(peer_liq)) if peer_liq else None,
        "symbol_return_percentile_in_peer": percentile_in("return_60d_pct"),
        "symbol_volatility_percentile_in_peer": percentile_in("hv60_pct"),
        "symbol_liquidity_percentile_in_peer": percentile_in("avg_value_60d"),
        "interpretation_guardrail": "Peer theo phân loại hiện tại, không phải point-in-time; chỉ đọc như tham chiếu tương đối.",
    }
```

> Nếu không có data ngành từ vnstock → bỏ qua block này hoặc trả `peer_count: 0` với guardrail.

---

## Tổng hợp: orchestrator mẫu

```python
def build_stock_profile(symbol, stock_rows, vnindex_rows=None, vn30_rows=None):
    """Orchestrator cho mode PROFILE. Trả dict schema JSON.
    `*_rows` = list daily OHLCV đã normalize (có 'value' = close*volume*1000)."""
    if len(stock_rows) < 60:
        return {"error": "Không đủ dữ liệu (cần ≥60 phiên)", "symbol": symbol}
    benchmarks = {}
    if vnindex_rows:
        benchmarks["VNINDEX"] = vnindex_rows
    if vn30_rows:
        benchmarks["VN30"] = vn30_rows
    payload = {
        "schema": "vn-technical-profile-v1",
        "generated_at": "<iso>",
        "language_policy": "neutral_descriptive_non_advice",
        "symbol": symbol,
        "stock_identity": {"symbol": symbol, "sample_size": len(stock_rows)},
        "price_behavior_profile": price_behavior_profile(stock_rows),
        "volatility_profile": volatility_profile(stock_rows),
        "drawdown_profile": drawdown_profile(stock_rows),
        "liquidity_profile": liquidity_profile(stock_rows),
        "return_distribution_profile": return_distribution_profile(stock_rows),
        "tail_risk_profile": tail_risk_profile(stock_rows),
        "liquidity_risk_profile": liquidity_risk_profile(stock_rows),
        "volume_price_profile": volume_price_profile(stock_rows),
        "volume_price_confirmation_profile": vpci_profile(stock_rows),
        "money_flow_pressure_profile": money_flow_profile(stock_rows),
        "effort_result_profile": effort_result_profile(stock_rows),
        "high_volume_behavior_profile": high_volume_behavior_profile(stock_rows),
        "pvi_nvi_participation_profile": pvi_nvi_profile(stock_rows),
        "volume_at_price_profile": volume_at_price_profile(stock_rows),
    }
    if benchmarks:
        rs = relative_strength_profile(stock_rows, vnindex_rows, benchmarks)
        payload.update(rs)
        if vnindex_rows:
            payload["regime_profile"] = regime_profile(stock_rows, vnindex_rows)
    # Anti-conclusion panel (bắt buộc mode profile)
    payload["non_conclusion"] = [
        "Không kết luận đây là khuyến nghị hoặc lời gọi giao dịch.",
        "Tỷ lệ trong quá khứ không đảm bảo lặp lại trong tương lai.",
        "Các cửa sổ quan sát chồng lấp, không phải quan sát độc lập.",
        "Dữ liệu giá chưa điều chỉnh corporate actions được kiểm chứng đầy đủ.",
    ]
    return payload
```

**Kiểm tra readiness** (subset của `profileReadinessProfile` ở source line 1162-1204): đảm bảo mỗi block có field label chính (`confirmation_label`, `money_flow_label`, `effort_result_label`, `post_high_volume_label`, `participation_regime_label`, `acceptance_label`, `liquidity_risk_label`) trước khi render narrative.
