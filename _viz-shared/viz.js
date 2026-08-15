/* =========================================================================
   VIZ.JS — Chart component registry + Candlestick renderer + Navigation
   Pattern cốt lõi (học từ Metabase): "chart as plugin".
   Trước đây: mỗi template có 7+ lệnh `new Chart(...)` riêng, lặp đi lặp lại
   các config legend/grid/dualAxis. Giờ: registry với base config merge.

   API:
     viz.chart(canvasId, { type, datasets, scales?, plugins? })
     viz.renderCandlestick(canvasEl, { candles, volumes, ma20, ma50, high52w, low52w, months })
     viz.setupNav({ linksSelector, sections?, progressId?, backTopId? })
     viz.gradient(ctx, c1, c2)              // helper tiện ích
     viz.neon(c1, c2)                        // helper gradient cho bar fill
   ========================================================================= */
(function (global) {
  'use strict';

  const viz = {};

  /* ---------------------------------------------------------------------
     Chart.defaults — setup một lần (trước đây lặp 5 lần trong 5 templates)
     Lấy màu từ CSS custom properties → tự đổi theo data-theme.
     --------------------------------------------------------------------- */
  function cssVar(name) {
    return getComputedStyle(document.documentElement).getPropertyValue(name).trim();
  }
  function readChartColors() {
    const styles = getComputedStyle(document.documentElement);
    return {
      primary:   cssVar('--chart-primary')   || '#a855f7',
      secondary: cssVar('--chart-secondary') || '#ec4899',
      tertiary:  cssVar('--chart-tertiary')  || '#06b6d4',
      pos:       cssVar('--chart-pos')       || '#10d98a',
      neg:       cssVar('--chart-neg')       || '#ff4d6d',
      neutral:   cssVar('--chart-neutral')   || '#fbbf24',
      grid:      cssVar('--chart-grid')      || 'rgba(139,92,246,0.06)',
      text:      cssVar('--chart-text')      || '#8b8ba7',
      fontFamily: cssVar('--font-sans')      || 'Inter, sans-serif',
    };
  }
  let CHART_COLORS = readChartColors();
  function applyChartDefaults() {
    if (!global.Chart) return;
    CHART_COLORS = readChartColors();
    Chart.defaults.color = CHART_COLORS.text;
    Chart.defaults.font.family = CHART_COLORS.fontFamily;
    Chart.defaults.borderColor = CHART_COLORS.grid;
  }
  applyChartDefaults();
  // Re-apply khi theme đổi (nếu user swap data-theme sau render)
  viz.refreshTheme = applyChartDefaults;

  /* ---------------------------------------------------------------------
     Gradient helper (trước đây lặp ở mỗi template)
     --------------------------------------------------------------------- */
  viz.gradient = function (ctx, c1, c2) {
    const chartArea = ctx.chart.chartArea;
    const top = chartArea ? chartArea.top : 0;
    const bottom = chartArea ? chartArea.bottom : 280;
    const g = ctx.chart.ctx.createLinearGradient(0, top, 0, bottom);
    g.addColorStop(0, c1);
    g.addColorStop(1, c2);
    return g;
  };

  /* ---------------------------------------------------------------------
     CHART REGISTRY — "chart as plugin" pattern
     Base options hợp nhất tự động → không còn lặp legend/grid/dualAxis.
     --------------------------------------------------------------------- */
  const SCALE_BASE = { grid: { color: CHART_COLORS.grid } };
  const LEGEND_BASE = {
    position: 'top', align: 'end',
    labels: { usePointStyle: true, boxWidth: 8, font: { size: 11 } },
  };

  function deepMerge(base, override) {
    // Shallow-ish merge đủ cho config Chart.js (2 cấp).
    const out = Array.isArray(base) ? base.slice() : Object.assign({}, base);
    if (!override) return out;
    for (const k of Object.keys(override)) {
      const bv = base[k], ov = override[k];
      if (bv && typeof bv === 'object' && !Array.isArray(bv) && ov && typeof ov === 'object') {
        out[k] = Object.assign({}, bv, ov);
      } else {
        out[k] = ov;
      }
    }
    return out;
  }

  /**
   * Vẽ một chart từ registry. Base options (responsive, legend, grid) tự thêm.
   * @param {string} canvasId - id thẻ <canvas>
   * @param {object} spec - { type, data, options?, plugins? }
   */
  viz.chart = function (canvasId, spec) {
    if (!global.Chart) { console.warn('Chart.js chưa load'); return null; }
    const canvas = document.getElementById(canvasId);
    if (!canvas) { console.warn('canvas không tìm thấy:', canvasId); return null; }

    const baseOptions = {
      responsive: true,
      maintainAspectRatio: false,
      plugins: { legend: LEGEND_BASE },
    };

    const opts = deepMerge(baseOptions, spec.options || {});
    // Đảm bảo scales có grid color mặc định nếu user không override
    if (opts.scales) {
      for (const k of Object.keys(opts.scales)) {
        opts.scales[k] = deepMerge({ grid: { color: CHART_COLORS.grid } }, opts.scales[k]);
      }
    }

    return new Chart(canvas, {
      type: spec.type,
      data: spec.data,
      options: opts,
      plugins: spec.plugins || [],
    });
  };

  /* ---------------------------------------------------------------------
     CANDLESTICK RENDERER — custom Canvas 2D
     Trước đây: ~100 dòng này lặp 2 lần (technical + profile templates).
     Giờ: 1 hàm tái dùng. DPR-aware, resize-aware.
     @param {HTMLCanvasElement} canvas
     @param {object} data:
       candles: [{o,h,l,c}]      (giá nghìn đồng)
       volumes: number[]          (triệu CP)  — optional
       ma20: number[]             (null cho warmup)
       ma50: number[]
       high52w: number
       low52w: number
       months: string[]           (nhãn trục X, vd ['7/25','8/25',...])
       priceUnit?: 'K' | ''       (mặc định 'K' → chia 1000 khi hiển thị)
     --------------------------------------------------------------------- */
  viz.renderCandlestick = function (canvas, data) {
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    const candles = data.candles || [];
    if (!candles.length) return;
    const volumes = data.volumes || [];
    const ma20 = data.ma20 || [];
    const ma50 = data.ma50 || [];
    const high52w = data.high52w;
    const low52w = data.low52w;
    const months = data.months || [];
    const unit = data.priceUnit || 'K'; // 'K' → giá nghìn đồng hiển thị /1000
    const div = unit === 'K' ? 1000 : 1;

    function draw() {
      const dpr = window.devicePixelRatio || 1;
      const rect = canvas.getBoundingClientRect();
      const W = Math.max(100, rect.width);
      const H = Math.max(100, rect.height);
      canvas.width = W * dpr; canvas.height = H * dpr;
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      ctx.clearRect(0, 0, W, H);

      const priceH = H * 0.65, volH = volumes.length ? H * 0.25 : 0, gap = H * 0.05;
      const volY = priceH + gap;
      const padLeft = 50, padRight = 20, padTop = 10, padBot = 20;
      const chartW = W - padLeft - padRight;
      const priceTop = padTop, priceBot = priceH - padBot;
      const volTop = volY + 10, volBot = volY + volH;

      let pMin = Infinity, pMax = -Infinity;
      candles.forEach(c => { pMin = Math.min(pMin, c.l); pMax = Math.max(pMax, c.h); });
      const pPad = (pMax - pMin) * 0.05;
      pMin -= pPad; pMax += pPad;
      const priceToY = p => priceTop + (priceBot - priceTop) * (pMax - p) / (pMax - pMin);

      const n = candles.length;
      const candleW = Math.max(3, chartW / n * 0.7);
      const xStep = chartW / n;
      const idxToX = i => padLeft + xStep * (i + 0.5);

      // Grid + Y labels
      ctx.strokeStyle = 'rgba(139,92,246,0.08)'; ctx.lineWidth = 1;
      ctx.fillStyle = '#5a5a72'; ctx.font = '10px JetBrains Mono'; ctx.textAlign = 'right';
      for (let g = 0; g <= 5; g++) {
        const p = pMin + (pMax - pMin) * g / 5;
        const y = priceToY(p);
        ctx.beginPath(); ctx.moveTo(padLeft, y); ctx.lineTo(W - padRight, y); ctx.stroke();
        ctx.fillText(unit === 'K' ? (p / 1000).toFixed(1) + 'K' : p.toFixed(1), padLeft - 5, y + 3);
      }

      // MA20 (vàng)
      if (ma20.length) {
        ctx.strokeStyle = '#fbbf24'; ctx.lineWidth = 1.5; ctx.beginPath();
        let started = false;
        ma20.forEach((v, i) => {
          if (v === null || v === undefined) return;
          const x = idxToX(i), y = priceToY(v);
          if (!started) { ctx.moveTo(x, y); started = true; } else ctx.lineTo(x, y);
        });
        ctx.stroke();
      }
      // MA50 (cyan)
      if (ma50.length) {
        ctx.strokeStyle = '#06b6d4'; ctx.beginPath(); started = false;
        ma50.forEach((v, i) => {
          if (v === null || v === undefined) return;
          const x = idxToX(i), y = priceToY(v);
          if (!started) { ctx.moveTo(x, y); started = true; } else ctx.lineTo(x, y);
        });
        ctx.stroke();
      }

      // Resistance = đỉnh 52 tuần
      if (high52w != null) {
        ctx.strokeStyle = 'rgba(255,77,109,0.5)'; ctx.setLineDash([4, 4]); ctx.lineWidth = 1;
        const resY = priceToY(high52w);
        ctx.beginPath(); ctx.moveTo(padLeft, resY); ctx.lineTo(W - padRight, resY); ctx.stroke();
        ctx.fillStyle = 'rgba(255,77,109,0.8)'; ctx.textAlign = 'left'; ctx.font = '9px Inter';
        ctx.fillText('R ' + (high52w / div).toFixed(unit === 'K' ? 1 : 0) + (unit === 'K' ? 'K' : '') + ' (đỉnh 52W)', padLeft + 4, resY - 5);
      }
      // Support = đáy 52 tuần
      if (low52w != null) {
        ctx.strokeStyle = 'rgba(16,217,138,0.5)';
        const supY = priceToY(low52w);
        ctx.beginPath(); ctx.moveTo(padLeft, supY); ctx.lineTo(W - padRight, supY); ctx.stroke();
        ctx.fillStyle = 'rgba(16,217,138,0.8)';
        ctx.fillText('S ' + (low52w / div).toFixed(unit === 'K' ? 1 : 0) + (unit === 'K' ? 'K' : '') + ' (đáy 52W)', padLeft + 4, supY + 12);
        ctx.setLineDash([]);
      }

      // Candles
      candles.forEach((c, i) => {
        const x = idxToX(i);
        const isUp = c.c >= c.o;
        const color = isUp ? '#10d98a' : '#ff4d6d';
        const yHigh = priceToY(c.h), yLow = priceToY(c.l);
        const yOpen = priceToY(c.o), yClose = priceToY(c.c);
        const bodyTop = Math.min(yOpen, yClose);
        const bodyH = Math.max(1, Math.abs(yClose - yOpen));
        ctx.strokeStyle = color; ctx.lineWidth = 1;
        ctx.beginPath(); ctx.moveTo(x, yHigh); ctx.lineTo(x, yLow); ctx.stroke();
        ctx.fillStyle = color; ctx.fillRect(x - candleW / 2, bodyTop, candleW, bodyH);
      });

      // Volume sub-panel
      if (volumes.length) {
        const maxVol = Math.max(...volumes.filter(v => v > 0));
        const volToY = v => volBot - (volBot - volTop) * v / maxVol;
        ctx.fillStyle = '#5a5a72'; ctx.font = '10px JetBrains Mono'; ctx.textAlign = 'right';
        ctx.fillText(maxVol.toFixed(1) + 'M', padLeft - 5, volTop + 3);
        ctx.fillText('0', padLeft - 5, volBot);
        ctx.strokeStyle = 'rgba(139,92,246,0.08)';
        ctx.beginPath(); ctx.moveTo(padLeft, volBot); ctx.lineTo(W - padRight, volBot); ctx.stroke();
        candles.forEach((c, i) => {
          const x = idxToX(i);
          const isUp = c.c >= c.o;
          const v = volumes[i];
          if (v <= 0) return;
          const y = volToY(v);
          ctx.fillStyle = isUp ? 'rgba(16,217,138,0.5)' : 'rgba(255,77,109,0.5)';
          ctx.fillRect(x - candleW / 2, y, candleW, volBot - y);
        });
      }

      // X labels (tháng)
      if (months.length) {
        ctx.fillStyle = '#5a5a72'; ctx.font = '9px Inter'; ctx.textAlign = 'center';
        const monthStep = Math.ceil(n / months.length);
        months.forEach((m, i) => {
          const idx = i * monthStep + 2;
          if (idx < n) ctx.fillText(m, idxToX(idx), H - 5);
        });
      }
    }

    draw();
    let resizeTimer;
    window.addEventListener('resize', () => {
      clearTimeout(resizeTimer);
      resizeTimer = setTimeout(draw, 100);
    });
  };

  /* ---------------------------------------------------------------------
     NAVIGATION — scrollspy + progress bar + back-to-top
     Trước đây: lặp 2 lần (technical + profile). Giờ: 1 hàm.
     Tự phát hiện links vs fallback. Tương thích cả `data-target` (dashboard)
     và `href="#id"` (profile).
     --------------------------------------------------------------------- */
  viz.setupNav = function (opts) {
    opts = opts || {};
    const links = Array.from(document.querySelectorAll(opts.linksSelector || '.topnav-link, nav a[href^="#"]'));
    if (!links.length) return;

    const progress = opts.progressId ? document.getElementById(opts.progressId) : document.getElementById('progressBar');
    const backTop = opts.backTopId ? document.getElementById(opts.backTopId) : document.getElementById('backTop');
    // Giải section target cho mỗi link (data-target hoặc href)
    const sections = links.map(link => {
      const sel = link.dataset.target ? '#' + link.dataset.target : link.getAttribute('href');
      return { link: link, el: sel ? document.querySelector(sel) : null };
    }).filter(s => s.el);

    function onScroll() {
      const sc = window.scrollY + 120;
      const docH = document.documentElement.scrollHeight - window.innerHeight;
      if (progress) progress.style.width = (docH > 0 ? (window.scrollY / docH) * 100 : 0) + '%';
      if (backTop) backTop.classList.toggle('visible', window.scrollY > 600);

      let current = sections[0];
      for (let i = sections.length - 1; i >= 0; i--) {
        if (sections[i].el.getBoundingClientRect().top + window.scrollY - 120 <= sc) {
          current = sections[i]; break;
        }
      }
      links.forEach(l => l.classList.remove('active'));
      if (current) {
        current.link.classList.add('active');
        // Scroll nav để link active vào view
        const navInner = current.link.closest('.topnav-inner');
        if (navInner) {
          const linkRect = current.link.getBoundingClientRect();
          const navRect = navInner.getBoundingClientRect();
          if (linkRect.left < navRect.left + 50 || linkRect.right > navRect.right - 50) {
            navInner.scrollTo({
              left: current.link.offsetLeft - navInner.offsetWidth / 2 + current.link.offsetWidth / 2,
              behavior: 'smooth',
            });
          }
        }
      }
    }

    links.forEach(link => {
      link.addEventListener('click', e => {
        e.preventDefault();
        const sel = link.dataset.target ? '#' + link.dataset.target : link.getAttribute('href');
        const target = sel ? document.querySelector(sel) : null;
        if (target) {
          const navH = (document.querySelector('.topnav') || {}).offsetHeight || 0;
          const top = target.getBoundingClientRect().top + window.scrollY - navH - 8;
          window.scrollTo({ top: top, behavior: 'smooth' });
        }
      });
    });

    if (backTop) {
      backTop.addEventListener('click', () => window.scrollTo({ top: 0, behavior: 'smooth' }));
    }
    window.addEventListener('scroll', onScroll, { passive: true });
    onScroll();
  };

  global.viz = viz;
})(typeof window !== 'undefined' ? window : this);
