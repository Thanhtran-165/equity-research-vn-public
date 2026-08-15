# Technical Indicators — Công thức + code

Code JavaScript (dùng trong HTML) và Python (dùng khi fetch data).

## Mục lục
1. [Moving Averages (SMA/EMA)](#ma)
2. [RSI(14)](#rsi)
3. [MACD](#macd)
4. [Bollinger Bands](#bb)
5. [Beta & Correlation](#beta)
6. [Performance metrics](#perf)

---

## Moving Averages <a name="ma"></a>

**SMA (Simple Moving Average):**
```javascript
function SMA(data, period) {
  const out = [];
  for (let i = 0; i < data.length; i++) {
    if (i < period - 1) { out.push(null); continue; }
    const slice = data.slice(i - period + 1, i + 1);
    out.push(slice.reduce((a,b)=>a+b,0) / period);
  }
  return out;
}
```

**EMA (Exponential Moving Average):**
```javascript
function EMA(data, period) {
  const k = 2 / (period + 1);
  const out = [data[0]];
  for (let i = 1; i < data.length; i++) {
    out.push(data[i] * k + out[i-1] * (1 - k));
  }
  return out;
}
```

**Python:**
```python
def SMA(d, p):
    out = [None] * (p - 1)
    for i in range(p-1, len(d)):
        out.append(sum(d[i-p+1:i+1]) / p)
    return out

def EMA(d, p):
    k = 2 / (p + 1)
    o = [d[0]]
    for i in range(1, len(d)):
        o.append(d[i]*k + o[i-1]*(1-k))
    return o
```

**Diễn giải:**
- Giá trên MA10 = xu hướng tăng ngắn hạn
- Giá trên MA20 = xu hướng tăng trung hạn
- Giá trên MA50 = xu hướng tăng dài hạn
- MA50 cắt lên MA200 = **Golden Cross** (bullish mạnh)
- MA50 cắt xuống MA200 = **Death Cross** (bearish mạnh)

---

## RSI(14) <a name="rsi"></a>

**JavaScript:**
```javascript
function RSI(data, period = 14) {
  const rs = new Array(data.length).fill(null);
  if (data.length <= period) return rs;
  let avgGain = 0, avgLoss = 0;
  for (let i = 1; i <= period; i++) {
    const ch = data[i] - data[i-1];
    if (ch > 0) avgGain += ch; else avgLoss += Math.abs(ch);
  }
  avgGain /= period; avgLoss /= period;
  rs[period] = avgLoss === 0 ? 100 : 100 - 100/(1 + avgGain/avgLoss);
  for (let i = period + 1; i < data.length; i++) {
    const ch = data[i] - data[i-1];
    avgGain = (avgGain*(period-1) + (ch > 0 ? ch : 0)) / period;
    avgLoss = (avgLoss*(period-1) + (ch < 0 ? Math.abs(ch) : 0)) / period;
    rs[i] = avgLoss === 0 ? 100 : 100 - 100/(1 + avgGain/avgLoss);
  }
  return rs;
}
```

**Diễn giải:**
- RSI < 30 → **Quá bán** (oversold, cơ hội mua)
- RSI > 70 → **Quá mua** (overbought, cảnh báo bán)
- RSI 30-70 → Trung tính

⚠️ **Bẫy cổ phiếu chu kỳ:** RSI thấp không phải lúc nào cũng = mua. Trong downtrend mạnh, RSI có thể ở vùng 20-30 lâu. Kết hợp với MA và MACD.

---

## MACD <a name="macd"></a>

```javascript
const ema12 = EMA(closes, 12);
const ema26 = EMA(closes, 26);
const macdLine = closes.map((_, i) => ema12[i] - ema26[i]);
const signalLine = EMA(macdLine, 9);
const histogram = macdLine.map((m, i) => m - signalLine[i]);
```

**Diễn giải:**
- MACD > Signal → **Bullish** (crossover lên = tín hiệu mua)
- MACD < Signal → **Bearish** (crossover xuống = tín hiệu bán)
- Histogram > 0 và tăng → momentum bullish mạnh
- Histogram < 0 và giảm → momentum bearish mạnh

---

## Bollinger Bands <a name="bb"></a>

```javascript
function Bollinger(data, period = 20, mult = 2) {
  const sma = SMA(data, period);
  return data.map((_, i) => {
    if (i < period - 1) return { upper: null, middle: null, lower: null };
    const slice = data.slice(i - period + 1, i + 1);
    const mean = sma[i];
    const variance = slice.reduce((s, v) => s + (v - mean)**2, 0) / period;
    const sd = Math.sqrt(variance);
    return { upper: mean + mult * sd, middle: mean, lower: mean - mult * sd };
  });
}
```

**BB Position (current price trong dải):**
```javascript
const bbPos = (price - lower) / (upper - lower) * 100;
// < 20% = gần dải dưới (oversold)
// > 80% = gần dải trên (overbought)
```

---

## Beta & Correlation <a name="beta"></a>

```python
def weekly_returns(closes):
    return [(closes[i]/closes[i-1]-1)*100 for i in range(1, len(closes))]

def corr(a, b):
    ma, mb = sum(a)/len(a), sum(b)/len(b)
    ca = [x-ma for x in a]
    cb = [x-mb for x in b]
    num = sum(x*y for x, y in zip(ca, cb))
    den = (sum(x*x for x in ca)**0.5) * (sum(y*y for y in cb)**0.5)
    return num/den if den else 0

def beta(stock, market):
    ms, mm = sum(stock)/len(stock), sum(market)/len(market)
    cs = [x-ms for x in stock]
    cm = [x-mm for x in market]
    cov = sum(x*y for x, y in zip(cs, cm)) / len(stock)
    var = sum(x*x for x in cm) / len(market)
    return cov/var if var else 0
```

**Diễn giải:**
- Beta > 1: cổ phiếu biến động mạnh hơn thị trường (aggressive)
- Beta = 1: biến động bằng thị trường
- Beta < 1: biến động ít hơn (defensive)
- Beta < 0: di chuyển ngược thị trường (hiếm)

**Alpha = stock_perf - beta × market_perf**
- Alpha > 0: outperform thị trường
- Alpha < 0: underperform thị trường

---

## Performance metrics <a name="perf"></a>

```javascript
const perf1y = (closes[closes.length-1] / closes[0] - 1) * 100;
const perfFrom52wHigh = (current / Math.max(...closes) - 1) * 100;
const perfFrom52wLow = (current / Math.min(...closes) - 1) * 100;

// Volatility (annualized)
const returns = [];
for (let i = 1; i < closes.length; i++) {
  returns.push(closes[i]/closes[i-1] - 1);
}
const meanRet = returns.reduce((a,b)=>a+b,0) / returns.length;
const variance = returns.reduce((s,v)=>s+(v-meanRet)**2,0) / returns.length;
const weeklyVol = Math.sqrt(variance) * 100;
const annualVol = weeklyVol * Math.sqrt(52);  // tuần → năm
```

**Benchmark volatility VN:**
- < 15%: thấp (phòng thủ — VNM, VCB)
- 15-25%: trung bình (HPG, FPT)
- 25-40%: cao (MWG, VIC)
- > 40%: rất cao (cổ phiếu nhỏ, penny)
