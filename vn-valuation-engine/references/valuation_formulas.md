# Valuation Formulas — Công thức + code template

Mỗi phương pháp: công thức → khi nào dùng → code Node.js template → bẫy.

## Mục lục
1. [PE / PB Median](#pepb)
2. [EV/EBITDA](#evebitda)
3. [P/CF và P/S](#pcfps)
4. [PEG](#peg)
5. [DCF (FCFF)](#dcf)
6. [Reverse DCF](#reverse-dcf)
7. [DDM (Gordon)](#ddm)
8. [Graham Number](#graham)
9. [Sensitivity Analysis](#sensitivity)

---

## PE / PB Median <a name="pepb"></a>

**Khi dùng:** Cổ phiếu phi chu kỳ (bán lẻ, tiêu dùng, công nghệ ổn định).

```javascript
const eps = netProfit_tỷ / shares_tỷ;        // đồng/cp
const bvps = equity_tỷ / shares_tỷ;           // đồng/cp
const pe_history = years.map((_,i) => price[i] / eps_history[i]);
const pb_history = years.map((_,i) => price[i] / bvps_history[i]);
const medianPE = [...pe_history].sort((a,b)=>a-b)[2];  // 5 năm → index 2 = median
const medianPB = [...pb_history].sort((a,b)=>a-b)[2];

const fairPrice_PE = eps_current * medianPE;
const fairPrice_PB = bvps_current * medianPB;
```

**Bẫy:** Với cổ phiếu chu kỳ (thép), năm đáy chu kỳ có LNST thấp → PE phình lên 30-50x. **Loại bỏ năm đáy** hoặc dùng PE normalised.

---

## EV/EBITDA <a name="evebitda"></a>

**Khi dùng:** Ngành tư bản lớn (thép, dầu khí, BĐS), vì loại trừ khấu hao & cấu trúc vốn.

```javascript
const ebitda = ebit + depreciation_amortization;       // EBIT = LT trước thuế + lãi vay
const netDebt = total_debt - cash;
const marketCap = price * shares_tỷ / 10;              // tỷ (price đồng × tỷ CP / 10)
const ev = marketCap + netDebt + minority_interest;    // thường bỏ minority nếu nhỏ
const evEbitda = ev / ebitda;

// Định giá từ EV
const fairEV = ebitda_current * evEbitda_median_5y;
const fairMarketCap = fairEV - netDebt;
const fairPrice = fairMarketCap * 10 / shares_tỷ;      // đồng/cp
```

**Bẫy:** EBITDA không có sẵn trong BCTC VN — phải tính thủ công: `LTST + chi phí lãi vay + khấu hao`.

---

## P/CF và P/S <a name="pcfps"></a>

**Khi dùng:** P/CF khi LNST bị nghi ngờ (xào nấu) — dòng tiền khó giả mạo. P/S khi LNST âm hoặc chu kỳ.

```javascript
const pCF = marketCap / cfo_tỷ;
const pS = marketCap / revenue_tỷ;
const fairPrice_PCF = (cfo_current * pCF_median_5y) * 10 / shares_tỷ;
const fairPrice_PS  = (revenue_current * pS_median_5y) * 10 / shares_tỷ;
```

---

## PEG <a name="peg"></a>

**Khi dùng:** Cổ phiếu tăng trưởng (công nghệ, bán lẻ). `PE / EPS growth rate`.

```javascript
const epsGrowth = (Math.pow(EPS_recent / EPS_5y_ago, 1/4) - 1) * 100;
const peg = pe_current / Math.max(epsGrowth, 1);  // tránh chia 0
// PEG < 1.0 = undervalued; PEG 1-2 = fair; PEG > 2 = overvalued
```

**Bẫy:** Không dùng cho cổ phiếu chu kỳ (growth rate âm hoặc cực biến động).

---

## DCF (FCFF) <a name="dcf"></a>

**Khi dùng:** Mọi ngành, nhưng đặc biệt hữu ích cho công ty có dự án lớn sắp ramp-up (Dung Quất 2 cho HPG).

```javascript
// FCFF = CFO - CapEx  (đơn vị tỷ)
// Forecast FCFF 5 năm tới (dựa trên kế hoạch DN + dự phóng CK)
const fcff_forecast = [10000, 14000, 20000, 24000, 28000];  // 5 năm tới
const wacc = 0.105;      // Tham chiếu references/wacc_estimates.md
const g_terminal = 0.03;

let pv_explicit = 0;
fcff_forecast.forEach((f, i) => {
  pv_explicit += f / Math.pow(1 + wacc, i + 1);
});
const terminalValue = fcff_forecast[4] * (1 + g_terminal) / (wacc - g_terminal);
const pv_terminal = terminalValue / Math.pow(1 + wacc, 5);
const enterpriseValue = pv_explicit + pv_terminal;
const equityValue = enterpriseValue - netDebt;
const fairPrice = equityValue / shares_tỷ / 1000;  // chia 1000 ra nghìn? tuỳ đơn vị
```

**3 kịch bản:**
- **Bi quan:** FCFF phục hồi chậm, WACC +1%, g -1%
- **Base:** FCFF theo kế hoạch DN
- **Tích cực:** FCFF ramp-up mạnh (DQ2 vận hành tối đa), WACC -0.5%

**Bẫy:** DCF cực nhạy — kịch bản tích cực có thể gấp 3x bi quan. Luôn trình bày cả 3 kịch bản, không chỉ base.

---

## Reverse DCF <a name="reverse-dcf"></a>

**Khi dùng:** Để biết thị trường đang ngụ ý tăng trưởng gì tại giá hiện tại.

```javascript
// Binary search g sao cho PV(FCFF, g, wacc) = EV hiện tại
function calcEV(g, baseFCFF, wacc) {
  let pv = 0;
  for (let i = 1; i <= 5; i++) pv += baseFCFF * Math.pow(1+g, i) / Math.pow(1+wacc, i);
  const tv = baseFCFF * Math.pow(1+g, 5) * 1.03 / (wacc - 0.03);
  pv += tv / Math.pow(1+wacc, 5);
  return pv;
}
let lo = 0.01, hi = 0.30;
for (let k = 0; k < 50; k++) {
  const m = (lo + hi) / 2;
  if (calcEV(m, baseFCFF, wacc) < currentEV) lo = m; else hi = m;
}
const impliedGrowth = (lo + hi) / 2;
// Nếu impliedGrowth < growth industry → undervalued
```

---

## DDM (Gordon) <a name="ddm"></a>

**Khi dùng:** Công ty trả cổ tức tiền mặt đều đặn (utilities, ngân hàng truyền thống).

```javascript
const dps_current = 1000;  // đ/cp
const ke = 0.11;            // cost of equity
const g = 0.04;             // growth dài hạn
const fairPrice = dps_current * (1 + g) / (ke - g);
```

**Bẫy:** KHÔNG dùng cho công ty trả cổ tức cổ phiếu (HPG, VNM) — DDM sẽ cho giá thấp bất thường vì DPS tiền mặt thấp. DDM cho HPG = 14.9K vs giá thực 23.6K → sai hoàn toàn.

---

## Graham Number <a name="graham"></a>

**Khi dùng:** Sanity check cổ điển, đặc biệt cho cổ phiếu giá trị.

```javascript
const graham = Math.sqrt(22.5 * eps * bvps);
// Điều kiện: eps > 0 và bvps > 0
// Nếu giá < Graham → undervalued (theo tiêu chuẩn Graham)
```

**Công thức gốc:** Graham đề xuất mua khi `PE × PB ≤ 22.5` (tương đương PE ≤ 15 và PB ≤ 1.5).

---

## Sensitivity Analysis <a name="sensitivity"></a>

Luôn tính bảng nhạy cảm cho DCF:

```
WACC \ g    2%      3%      4%
  10%      52.3K   58.1K   66.0K
  10.5%    47.8K   52.5K   58.7K    ← Base
  11%      44.0K   47.8K   52.7K
  12%      37.9K   40.6K   43.9K
```

```javascript
const waccs = [0.10, 0.105, 0.11, 0.12];
const gs = [0.02, 0.03, 0.04];
const sensitivityTable = waccs.map(w => gs.map(g => calcDCF(fcff_forecast, w, g)));
```

Trình bày bảng này trong output để user thấy DCF nhạy thế nào với giả định.
