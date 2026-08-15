# Pattern Detection — Code phát hiện + quy tắc evidence

**Nguyên tắc cốt lõi:** Chỉ claim pattern khi data SHOW rõ. Không "tìm kiếm" pattern cho by nice-to-have — nếu không có, nói thẳng "không có".

## Mục lục
1. [Swing points](#swing)
2. [Double Bottom/Top](#double)
3. [Channel (Ascending/Descending)](#channel)
4. [Candlestick patterns](#candle)
5. [Divergence](#divergence)
6. [Bảng verdict patterns](#verdict)

---

## Swing points <a name="swing"></a>

Foundation cho mọi chart pattern detection:

```javascript
function findSwings(closes, lookback = 2) {
  const highs = [], lows = [];
  for (let i = lookback; i < closes.length - lookback; i++) {
    let isHigh = true, isLow = true;
    for (let j = 1; j <= lookback; j++) {
      if (closes[i] <= closes[i-j] || closes[i] <= closes[i+j]) isHigh = false;
      if (closes[i] >= closes[i-j] || closes[i] >= closes[i+j]) isLow = false;
    }
    if (isHigh) highs.push({ idx: i, price: closes[i] });
    if (isLow) lows.push({ idx: i, price: closes[i] });
  }
  return { highs, lows };
}
```

`lookback = 2` = swing point phải cao/thấp hơn 2 nến mỗi bên. Tăng `lookback` để lọc noise.

---

## Double Bottom/Top <a name="double"></a>

**Double Bottom** (bullish reversal):
- 2 đáy (swing lows) gần bằng nhau (chênh < 3%)
- Cách nhau ít nhất 5 tuần
- Neckline = swing high giữa 2 đáy

```javascript
function detectDoubleBottom(lows) {
  const patterns = [];
  for (let i = 0; i < lows.length - 1; i++) {
    for (let j = i + 1; j < lows.length; j++) {
      const l1 = lows[i], l2 = lows[j];
      const diff = Math.abs(l1.price - l2.price) / Math.min(l1.price, l2.price) * 100;
      const weeksApart = l2.idx - l1.idx;
      if (diff < 3 && weeksApart >= 5) {
        // Tìm neckline = high giữa 2 đáy
        const between = closes.slice(l1.idx, l2.idx + 1);
        const neckline = Math.max(...between);
        patterns.push({
          type: 'double_bottom',
          bottom1: l1, bottom2: l2,
          neckline: neckline,
          target: neckline + (neckline - Math.min(l1.price, l2.price)),
          status: 'potential', // chưa confirm cho đến khi breakout neckline
          weeks_apart: weeksApart
        });
      }
    }
  }
  return patterns;
}
```

**Quy tắc evidence:**
- Chênh 2 đáy < 3% → "TIỀM NĂNG" (chưa confirm)
- Chênh 2 đáy < 1% → "RÕ RÀNG" nhưng vẫn cần breakout
- Chênh > 3% → KHÔNG phải double bottom

**Status:**
- `potential`: 2 đáy đã hình thành, chưa breakout neckline
- `confirmed`: giá đã breakout trên neckline với volume
- `failed`: giá break xuống dưới đáy 2

---

## Channel (Ascending/Descending) <a name="channel"></a>

Fit 2 trendline qua swing highs và swing lows:

```javascript
function detectChannel(closes, lookback = 20) {
  const recent = closes.slice(-lookback);
  const recentHigh = Math.max(...recent);
  const recentLow = Math.min(...recent);
  const firstHigh = Math.max(...recent.slice(0, Math.floor(lookback/3)));
  const lastHigh = Math.max(...recent.slice(-Math.floor(lookback/3)));
  const firstLow = Math.min(...recent.slice(0, Math.floor(lookback/3)));
  const lastLow = Math.min(...recent.slice(-Math.floor(lookback/3)));

  const highSlope = lastHigh - firstHigh;
  const lowSlope = lastLow - firstLow;

  if (highSlope < -100 && lowSlope < -100) {
    return { type: 'descending_channel', trend: 'bearish', high_start: firstHigh, high_end: lastHigh, low_start: firstLow, low_end: lastLow };
  } else if (highSlope > 100 && lowSlope > 100) {
    return { type: 'ascending_channel', trend: 'bullish', high_start: firstHigh, high_end: lastHigh, low_start: firstLow, low_end: lastLow };
  }
  // Side: range-bound
  if (Math.abs(highSlope) < 100 && Math.abs(lowSlope) < 100) {
    return { type: 'trading_range', trend: 'neutral' };
  }
  return null;
}
```

**Quy tắc evidence:** Channel chỉ claim nếu slope rõ (high/low cùng hướng, đổi > 100 đ).

---

## Candlestick patterns <a name="candle"></a>

Phát hiện trên từng nến:

```javascript
function analyzeCandle(c) {
  const body = Math.abs(c.c - c.o);
  const upperWick = c.h - Math.max(c.c, c.o);
  const lowerWick = Math.min(c.c, c.o) - c.l;
  const range = c.h - c.l;
  const pctBody = range > 0 ? body / range * 100 : 0;
  const isUp = c.c >= c.o;

  const patterns = [];

  // Hammer (bullish reversal)
  if (lowerWick > body * 2 && pctBody < 35 && !isUp) {
    patterns.push({ name: 'hammer', signal: 'bullish_reversal' });
  }
  // Inverted Hammer
  if (lowerWick > body * 2 && pctBody < 35 && isUp) {
    patterns.push({ name: 'inverted_hammer', signal: 'bullish_reversal' });
  }
  // Shooting Star (bearish)
  if (upperWick > body * 2 && pctBody < 35) {
    patterns.push({ name: 'shooting_star', signal: 'bearish' });
  }
  // Marubozu (strong momentum)
  if (pctBody > 70) {
    patterns.push({ name: isUp ? 'marubozu_bullish' : 'marubozu_bearish', signal: isUp ? 'bullish_momentum' : 'bearish_momentum' });
  }
  // Doji (indecision)
  if (pctBody < 10) {
    patterns.push({ name: 'doji', signal: 'indecision' });
  }

  return patterns;
}
```

**Engulfing patterns (2 nến):**
```javascript
function detectEngulfing(candles) {
  const patterns = [];
  for (let i = 1; i < candles.length; i++) {
    const prev = candles[i-1], curr = candles[i];
    const prevUp = prev.c >= prev.o;
    const currUp = curr.c >= curr.o;
    // Bullish Engulfing
    if (!prevUp && currUp && curr.c > prev.o && curr.o < prev.c) {
      patterns.push({ idx: i, type: 'bullish_engulfing', signal: 'bullish_strong' });
    }
    // Bearish Engulfing
    if (prevUp && !currUp && curr.c < prev.o && curr.o > prev.c) {
      patterns.push({ idx: i, type: 'bearish_engulfing', signal: 'bearish_strong' });
    }
  }
  return patterns;
}
```

**Three Soldiers/Crows (3 nến):**
```javascript
function detectThreeSoldiers(candles) {
  const last3 = candles.slice(-3);
  const allGreen = last3.every(c => c.c >= c.o);
  const allRed = last3.every(c => c.c < c.o);
  const higherCloses = last3[0].c < last3[1].c && last3[1].c < last3[2].c;
  const lowerCloses = last3[0].c > last3[1].c && last3[1].c > last3[2].c;
  if (allGreen && higherCloses) return { type: 'three_white_soldiers', signal: 'bullish_reversal_strong' };
  if (allRed && lowerCloses) return { type: 'three_black_crows', signal: 'bearish_reversal_strong' };
  return null;
}
```

---

## Divergence <a name="divergence"></a>

**Quy tắc CỐT LÕI — chỉ claim khi THẬT SỰ có:**

```javascript
function checkDivergence(closes, rsi, swingLows) {
  if (swingLows.length < 2) return { has_divergence: false, note: 'Không đủ swing lows' };

  const l1 = swingLows[swingLows.length - 2];
  const l2 = swingLows[swingLows.length - 1];

  // Cần RSI tại 2 đáy — RSI array ngắn hơn closes 14 đơn vị
  const rsiOffset = 14;
  const rsi1Idx = l1.idx - rsiOffset;
  const rsi2Idx = l2.idx - rsiOffset;

  if (rsi1Idx < 0 || rsi2Idx < 0 || rsi1Idx >= rsi.length || rsi2Idx >= rsi.length) {
    return { has_divergence: false, note: 'Index ngoài range RSI' };
  }

  const priceChange = l1.price - l2.price; // dương = giá giảm từ l1 → l2
  const rsi1 = rsi[rsi1Idx], rsi2 = rsi[rsi2Idx];
  const rsiChange = rsi1 - rsi2; // dương = RSI giảm từ l1 → l2

  // Bullish divergence: giá giảm (priceChange > 0) nhưng RSI tăng (rsiChange < 0)
  if (priceChange > 0 && rsiChange < 0) {
    return {
      has_divergence: true,
      type: 'bullish',
      note: `Giá giảm ${l1.price} → ${l2.price} nhưng RSI tăng ${rsi1.toFixed(1)} → ${rsi2.toFixed(1)}`
    };
  }
  // Bearish divergence: giá tăng nhưng RSI giảm
  if (priceChange < 0 && rsiChange > 0) {
    return {
      has_divergence: true,
      type: 'bearish',
      note: `Giá tăng nhưng RSI giảm`
    };
  }

  // Không có divergence
  return {
    has_divergence: false,
    note: `Giá và RSI cùng hướng ở 2 đáy gần nhất (Δ giá: ${priceChange > 0 ? 'giảm' : 'tăng'}, Δ RSI: ${rsiChange > 0 ? 'giảm' : 'tăng'}) — không có divergence`
  };
}
```

⚠️ **Quan trọng:** Nếu `has_divergence: false` → **nói thẳng "KHÔNG có divergence"**, KHÔNG cố tình tìm divergence. Đây là pattern bị lạm dụng nhiều nhất trong technical analysis — nhiều analyst "phát hiện" divergence cho mọi cổ phiếu để có nội dung. Skill này cam kết thành thật.

---

## Bảng verdict patterns <a name="verdict"></a>

| Pattern | Signal | Strength | Confirm cần |
|---|---|---|---|
| Double Bottom (confirmed) | Bullish reversal | Rất mạnh | Breakout neckline + volume |
| Double Bottom (potential) | Bullish tiềm năng | Trung bình | Chờ breakout |
| Descending Channel | Bearish continuation | Mạnh | Break trên trendline trên |
| Ascending Channel | Bullish continuation | Mạnh | Hold cho đến khi break trendline dưới |
| Hammer | Bullish reversal | Trung bình | Confirm nến xanh tuần sau |
| Shooting Star | Bearish | Trung bình | Confirm nến đỏ tuần sau |
| Marubozu bullish | Bullish momentum | Mạnh | Volume tăng |
| Marubozu bearish | Bearish momentum | Mạnh | Volume tăng |
| Bullish Engulfing | Bullish mạnh | Mạnh | Volume tăng |
| Three White Soldiers | Bullish reversal mạnh | Rất mạnh | Volume tăng dần |
| RSI Bullish Divergence | Bullish reversal | Rất mạnh | Confirm bằng MACD divergence |
| RSI Bearish Divergence | Bearish reversal | Rất mạnh | Confirm bằng MACD divergence |

**Luôn kết hợp patterns với:**
1. Volume (volume tăng ở điểm关键 = confirm mạnh hơn)
2. Support/Resistance (pattern tại support/resistance = mạnh hơn)
3. Trend lớn (pattern ngược trend = cần evidence mạnh hơn)
4. Multiple timeframe (confirm trên weekly + daily)
