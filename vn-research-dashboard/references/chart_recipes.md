# Chart Recipes — 7 loại chart cho dashboard

Mỗi recipe: dùng cho section nào → code template → tùy chọn.

## Mục lục
1. [Bar + Line Combo (Doanh thu & LNST)](#1)
2. [Line with Gradient Fill (Biên LN)](#2)
3. [Dual-axis Line (PE & PB)](#3)
4. [Bar + Line (Giá vs BVPS)](#4)
5. [Stacked Bar (DuPont)](#5)
6. [Bar with Color Threshold (Summary định giá)](#6)
7. [Bar + Line Forecast (Dự phóng)](#7)

---

## 1. Bar + Line Combo <a name="1"></a>

**Dùng cho:** Doanh thu (bar) + LNST (line) trên cùng chart, 2 y-axis.

```javascript
new Chart(document.getElementById('chartRevNP'), {
  type: 'bar',
  data: {
    labels: years,
    datasets: [
      { label: 'Doanh thu (tỷ)', data: data.revenue,
        backgroundColor: (c) => grad(c, 'rgba(168,85,247,0.9)', 'rgba(168,85,247,0.25)'),
        borderRadius: 8, yAxisID: 'y', order: 2 },
      { label: 'LNST (tỷ)', data: data.netProfit, type: 'line',
        borderColor: '#ec4899', backgroundColor: '#ec4899',
        borderWidth: 3, tension: 0.4, pointRadius: 5,
        pointBackgroundColor: '#ec4899', pointBorderColor: '#fff', pointBorderWidth: 2,
        yAxisID: 'y1', order: 1 }
    ]
  },
  options: {
    responsive: true, maintainAspectRatio: false,
    plugins: { legend: { position: 'top', align: 'end',
      labels: { usePointStyle: true, boxWidth: 8 } } },
    scales: {
      y:  { position: 'left',  grid: { color: 'rgba(139,92,246,0.06)' },
            ticks: { callback: v => (v/1000) + 'K' } },
      y1: { position: 'right', grid: { display: false },
            ticks: { callback: v => (v/1000).toFixed(0) + 'K' } }
    }
  }
});

// Helper grad
const grad = (ctx, c1, c2) => {
  const g = ctx.chart.ctx.createLinearGradient(0, 0, 0, 280);
  g.addColorStop(0, c1); g.addColorStop(1, c2); return g;
};
```

---

## 2. Line with Gradient Fill <a name="2"></a>

**Dùng cho:** Biên LN (ROS) với area fill + ROE dashed line.

```javascript
new Chart(document.getElementById('chartMargin'), {
  type: 'line',
  data: { labels: years, datasets: [
    { label: 'ROS (Biên LNST)', data: data.ros,
      borderColor: '#ec4899',
      backgroundColor: (c) => grad(c, 'rgba(236,72,153,0.35)', 'transparent'),
      borderWidth: 3, tension: 0.4, pointRadius: 5, fill: true,
      pointBackgroundColor: '#ec4899', pointBorderColor: '#fff', pointBorderWidth: 2 },
    { label: 'ROE', data: data.roe,
      borderColor: '#06b6d4', backgroundColor: 'transparent',
      borderWidth: 3, tension: 0.4, pointRadius: 5, borderDash: [6, 4],
      pointBackgroundColor: '#06b6d4', pointBorderColor: '#fff', pointBorderWidth: 2 }
  ]},
  options: {
    responsive: true, maintainAspectRatio: false,
    plugins: { legend: { position: 'top', align: 'end',
      labels: { usePointStyle: true, boxWidth: 8 } } },
    scales: { y: { ticks: { callback: v => v + '%' } } }
  }
});
```

---

## 3. Dual-axis Line <a name="3"></a>

**Dùng cho:** PE & PB với 2 y-axis riêng (scale khác nhau).

```javascript
new Chart(document.getElementById('chartPEPB'), {
  type: 'line',
  data: { labels: years, datasets: [
    { label: 'P/E', data: data.pe, borderColor: '#a855f7',
      borderWidth: 3, tension: 0.4, pointRadius: 5, yAxisID: 'y',
      pointBackgroundColor: '#a855f7', pointBorderColor: '#fff', pointBorderWidth: 2 },
    { label: 'P/B', data: data.pb, borderColor: '#10d98a',
      borderWidth: 3, tension: 0.4, pointRadius: 5, yAxisID: 'y1',
      pointBackgroundColor: '#10d98a', pointBorderColor: '#fff', pointBorderWidth: 2 }
  ]},
  options: {
    responsive: true, maintainAspectRatio: false,
    plugins: { legend: { position: 'top', align: 'end',
      labels: { usePointStyle: true, boxWidth: 8 } } },
    scales: {
      y:  { position: 'left',  title: { display: true, text: 'P/E (x)', color: '#a855f7' },
            ticks: { color: '#a855f7' } },
      y1: { position: 'right', title: { display: true, text: 'P/B (x)', color: '#10d98a' },
            ticks: { color: '#10d98a' }, grid: { display: false } }
    }
  }
});
```

---

## 4. Bar + Line (Giá vs BVPS) <a name="4"></a>

```javascript
new Chart(document.getElementById('chartPriceBV'), {
  type: 'bar',
  data: { labels: years, datasets: [
    { label: 'Giá (K đ)', data: data.price, type: 'line',
      borderColor: '#ec4899', borderWidth: 3, tension: 0.4, pointRadius: 6, order: 1,
      pointBackgroundColor: '#ec4899', pointBorderColor: '#fff', pointBorderWidth: 2 },
    { label: 'BVPS (K đ)', data: data.bvps.map(v => v/1000),
      backgroundColor: (c) => grad(c, 'rgba(6,182,212,0.7)', 'rgba(6,182,212,0.2)'),
      borderRadius: 8, order: 2 }
  ]},
  options: {
    responsive: true, maintainAspectRatio: false,
    plugins: { legend: { position: 'top', align: 'end',
      labels: { usePointStyle: true, boxWidth: 8 } } },
    scales: { y: { ticks: { callback: v => v + 'K' } } }
  }
});
```

---

## 5. Stacked Bar (DuPont) <a name="5"></a>

**Lưu ý:** Stack 3 thành phần với `stack: 'a'` để biểu diễn tổng ROE. Chia ×100 cho asset turn & leverage để scale đẹp.

```javascript
new Chart(document.getElementById('chartDuPont'), {
  type: 'bar',
  data: { labels: years, datasets: [
    { label: 'Biên LN (%)', data: data.dupMargin,
      backgroundColor: 'rgba(168,85,247,0.8)', borderRadius: 6, stack: 'a' },
    { label: 'Vòng quay TS (÷100)', data: data.dupTurn,
      backgroundColor: 'rgba(236,72,153,0.8)', borderRadius: 6, stack: 'a' },
    { label: 'Đòn bẩy (÷100)', data: data.dupLev,
      backgroundColor: 'rgba(6,182,212,0.8)', borderRadius: 6, stack: 'a' }
  ]},
  options: {
    responsive: true, maintainAspectRatio: false,
    plugins: {
      legend: { position: 'top', align: 'end',
        labels: { usePointStyle: true, boxWidth: 8, font: { size: 10 } } },
      tooltip: { callbacks: {
        label: (c) => {
          const lbl = c.dataset.label; const v = c.parsed.y;
          if (lbl.includes('Biên')) return `Biên LN: ${v}%`;
          if (lbl.includes('Vòng')) return `Vòng quay: ${(v/100).toFixed(2)}x`;
          return `Đòn bẩy: ${(v/100).toFixed(2)}x`;
        }
      }}
    },
    scales: {
      x: { stacked: true, grid: { display: false } },
      y: { stacked: true, ticks: { display: false },
           grid: { color: 'rgba(139,92,246,0.06)' } }
    }
  }
});
```

⚠️ **Bẫy cấu trúc:** `tooltip` phải ở cùng level với `legend` trong `plugins`, **không lồng vào legend**.

---

## 6. Bar with Color Threshold + Annotation <a name="6"></a>

**Dùng cho:** Summary 9 phương pháp định giá. Color theo giá trị so với giá hiện tại + đường vàng = giá hiện tại.

Cần plugin: `chartjs-plugin-annotation`.

```javascript
new Chart(document.getElementById('chartSummary'), {
  type: 'bar',
  data: {
    labels: ['DDM', 'PB 1.0x', 'PB median', ...],
    datasets: [{
      data: [14.9, 18.9, 24.0, ...],
      backgroundColor: (ctx) => {
        const v = ctx.parsed.y;
        if (v < priceCurrent) return 'rgba(255,77,109,0.7)';   // đỏ = dưới giá
        if (v > priceCurrent * 1.5) return 'rgba(16,217,138,0.7)'; // xanh = trên giá nhiều
        return 'rgba(168,85,247,0.7)';                          // tím = quanh giá
      },
      borderRadius: 8
    }]
  },
  options: {
    plugins: {
      legend: { display: false },
      tooltip: { callbacks: { label: c => c.parsed.y.toFixed(1) + 'K đ/cp' } },
      annotation: {
        annotations: {
          priceLine: {
            type: 'line', yMin: priceCurrent, yMax: priceCurrent,
            borderColor: '#fbbf24', borderWidth: 2, borderDash: [6, 4],
            label: { content: 'Giá ' + priceCurrent + 'K', display: true,
                     position: 'end', backgroundColor: 'rgba(251,191,36,0.9)',
                     color: '#000', font: { weight: '700', size: 10 },
                     padding: { x: 6, y: 3 }, borderRadius: 4 }
          }
        }
      }
    },
    scales: {
      y: { ticks: { callback: v => v + 'K' },
           grid: { color: 'rgba(139,92,246,0.06)' } },
      x: { ticks: { font: { size: 10 }, maxRotation: 0, minRotation: 0 } }
    }
  }
});
```

⚠️ Cần load plugin trước Chart init:
```html
<script src="https://cdn.jsdelivr.net/npm/chartjs-plugin-annotation@3.0.1/dist/chartjs-plugin-annotation.min.js"></script>
```

---

## 7. Bar + Line Forecast <a name="7"></a>

**Dùng cho:** Sản lượng (bar) + LNST dự phóng (line) 3 năm tới.

```javascript
new Chart(document.getElementById('chartForecast'), {
  type: 'bar',
  data: { labels: forecastYears, datasets: [
    { label: 'Sản lượng (tr.tấn)', data: forecastVol,
      backgroundColor: (c) => grad(c, 'rgba(168,85,247,0.9)', 'rgba(168,85,247,0.3)'),
      borderRadius: 8, yAxisID: 'y' },
    { label: 'LNST dự phóng (tỷ)', data: forecastNP, type: 'line',
      borderColor: '#10d98a', borderWidth: 3, tension: 0.4, pointRadius: 5, yAxisID: 'y1',
      pointBackgroundColor: '#10d98a', pointBorderColor: '#fff', pointBorderWidth: 2 }
  ]},
  options: {
    responsive: true, maintainAspectRatio: false,
    plugins: { legend: { position: 'top', align: 'end',
      labels: { usePointStyle: true, boxWidth: 8 } } },
    scales: {
      y:  { position: 'left',  title: { display: true, text: 'Triệu tấn' },
            grid: { color: 'rgba(139,92,246,0.06)' } },
      y1: { position: 'right', title: { display: true, text: 'Tỷ VNĐ' },
            ticks: { callback: v => (v/1000) + 'K' }, grid: { display: false } }
    }
  }
});
```

---

## Chart.js defaults (set 1 lần đầu script)

```javascript
Chart.defaults.color = '#8b8ba7';
Chart.defaults.font.family = "'Inter', sans-serif";
Chart.defaults.borderColor = 'rgba(139,92,246,0.08)';
```
