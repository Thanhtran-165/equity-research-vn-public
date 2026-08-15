# `_viz-shared/` — Hệ thống thiết kế trực quan hóa

Nguồn sự thật duy nhất cho CSS + JS được chia sẻ trên tất cả 5 mẫu bảng điều khiển (dashboard).
Trước đây, bảng màu (`:root`), các lớp thành phần và trình kết xuất biểu đồ nến (candlestick renderer)
được sao chép-dán vào từng mẫu — mỗi lần thay đổi bảng màu phải sửa 4–5 tệp, và trình kết xuất nến
~100 dòng bị trùng lặp tại 2 nơi. Thư mục này gom chúng lại thành **một** nguồn sự thật.

## Nội dung bên trong

| Tệp | Vai trò |
|---|---|
| `tokens.css` | Design tokens (`:root` variables) + 3 biến thể chủ đề (Fintech mặc định, Bloomberg, Corporate). Chuyển đổi chủ đề = thêm `data-theme="bloomberg"` vào `<html>`. |
| `components.css` | Các lớp thành phần giao diện dùng chung: `.hero`, `.card`, `.kpi`, `.fin-table`, `.section-title`, `.topnav`, `.news-card`, `.timeline`, `.exec-summary`, `.callout`, v.v. **Không bao giờ** mã hóa cứng màu — luôn tham chiếu đến các tokens. |
| `viz.js` | Đăng ký biểu đồ (`viz.chart`), trình kết xuất nến (`viz.renderCandlestick`), thanh điều hướng + scrollspy (`viz.setupNav`), các hàm hỗ trợ gradient. Trích xuất ~250 dòng JS bị trùng lặp từ các mẫu. |
| `inject.py` | Công cụ **thời gian thiết kế**: thay thế `{{VIZ_CSS}}` / `{{VIZ_JS}}` trong các mẫu bằng nội dung của thư viện dùng chung. Đầu ra là tệp tin tự đóng gói (single-file) (không phụ thuộc runtime). |
| `README.md` | Tài liệu này. |

## Hai cấp độ xử lý

```
THỜI GIAN THIẾT KẾ (hiếm — chỉ khi thay đổi thiết kế)
─────────────────────────────────────────────────────
  sửa tokens.css / components.css / viz.js
        │
        ▼
  python3 inject.py         ← hợp nhất vào 5 mẫu (tự đóng gói)
        │
        ▼
  mẫu đã được xây dựng lại (chứa CSS/JS inline, cộng với {{VIZ_*}} trống)

THỜI GIAN BÁO CÁO (mỗi lần chạy kỹ năng — không đổi)
────────────────────────────────────────────────────
  LLM sao chép mẫu đã xây dựng
        │
        ▼
  điền {{TICKER}}, {{REVENUE_DATA}}, {{KPI_*}}... qua str.replace
        │
        ▼
  HTML cuối cùng → triển khai lên Vercel
```

**inject.py chỉ đụng tới các placeholder `{{VIZ_*}}` thời gian thiết kế.**
Nó không bao giờ đụng tới các data token `{{TICKER}}` / `{{COMPANY_NAME}}` / `{{ROLLING_DATA}}` —
những token đó là dữ liệu báo cáo, chỉ được điền bởi LLM ở thời gian báo cáo.

## Cách sử dụng

### Sửa thiết kế (ví dụ: đổi bảng màu mặc định)

1. Sửa `tokens.css` (ví dụ: thay `--purple: #a855f7` thành giá trị khác).
2. Chạy `python3 inject.py`.
3. Tất cả 5 mẫu giờ đều phản ánh bảng màu mới — không cần sửa từng tệp thủ công.

### Thêm một biểu đồ mới vào một mẫu

Thay vì viết `new Chart(...)` thủ công với các tùy chọn nền tảng bị lặp lại,
hãy sử dụng registry:

```js
// Trước đây (trùng lặp): 7 khối new Chart trong 1 tệp, mỗi khối đều có legend/grid riêng.
new Chart(document.getElementById('chartRevNP'), {
  type: 'bar',
  data: { labels: years, datasets: [...] },
  options: { responsive: true, maintainAspectRatio: false,
    plugins: { legend: { position: 'top', align: 'end', labels: { usePointStyle: true, boxWidth: 8 } } },
    scales: { y: { grid: { color: 'rgba(139,92,246,0.06)' } } } }
});

// Sau khi có registry (DRY): tùy chọn nền tảng được hợp nhất tự động.
viz.chart('chartRevNP', {
  type: 'bar',
  data: { labels: years, datasets: [...] },
  options: { scales: { y: { ticks: { callback: v => (v/1000)+'K' } } } }  // chỉ phần cụ thể
});
```

### Sử dụng trình kết xuất nến (candlestick)

```js
viz.renderCandlestick(document.getElementById('chartCandlestick'), {
  candles: [{o,h,l,c}, ...],     // giá theo nghìn đồng
  volumes: [117.8, 162, ...],      // triệu CP
  ma20: [null, ..., 24170],        // null trong thời gian khởi động
  ma50: [null, ..., 24153],
  high52w: 27540,
  low52w: 19120,
  months: ['7/25', '8/25', ...],
});
```

### Gắn điều hướng (scrollspy + progress + back-to-top)

```js
viz.setupNav();  // tự động phát hiện .topnav-link hoặc nav a[href^="#"]
```

## Các mẫu sử dụng thư viện này

| Mẫu | `{{VIZ_CSS}}` | `{{VIZ_JS}}` | Ghi chú |
|---|:---:|:---:|---|
| `vn-research-dashboard/assets/dashboard_template.html` | ✓ | ✓ | Đầy đủ. Đã được tokenize (từng hard-code HPG). |
| `vn-technical-analysis/assets/technical_template.html` | ✓ | ✓ | Đầy đủ + đã được tokenize. Sử dụng `viz.renderCandlestick`. |
| `vn-technical-analysis/assets/profile_template.html` | ✓ | ✓ | Đầy đủ. Ghi đè theo từng mẫu: `.hero` gradient + `.topnav-inner` chiều rộng. |
| `vn-news-digest/assets/news_template.html` | ✓ | — | Chỉ CSS (không có canvas/Chart.js). Ghi đè theo từng mẫu: `.stats`, `.live-badge`. |
| `longform-report/assets/article_template.html` | — | ✓ | **Kế thừa một phần.** Bảng màu slate riêng biệt + hệ thống thiết kế (theo chủ đích — xem `themes.md`). Chỉ sử dụng registry `viz.chart()` (pattern DRY), KHÔNG sử dụng các tokens fintech. |

> Kế thừa một phần của longform là cố ý: đó là một design system khác biệt (giao diện slate, thanh điều hướng TOC, hero mood gradients) với `themes.md` riêng của nó. Ép buộc nó sử dụng tokens fintech sẽ xóa bỏ các AMBER/BLUE mood đã được tài liệu hóa của nó. Registry `viz.chart()` thì trung lập về bảng màu (đọc từ `--chart-*` tokens, có phương thức dự phòng), vì vậy nó là phần duy nhất của thư viện mà longform áp dụng một cách an toàn.

## Những thứ KHÔNG được phá vỡ

1. **Bộ chọn QA** (`qa_dashboard.js`): `.hero`, `.exec-summary`, `h2≥7`, `footer`, `.topnav`, `.topnav-link` / `nav a[href^="#"]`, ≥1 canvas không trống.
2. **grep QA của PROFILE**: 7 ID mục (`read/price/risk/flow/bench/vap/setup/notes`), bất biến `canvas = newChart + 1`.
3. **Hợp đồng `{{TOKEN}}` + str.replace** — không bao giờ dùng `.format()`/f-string (gây lỗi với `{}` của JS).
4. **Đầu ra tệp đơn** (triển khai Vercel + QA file:// + mở).
5. **Biến thể-1 (Fintech) = chủ đề mặc định.**
6. **ID canvas** (`chartRevNP`, v.v.) — để không làm hỏng `chart_recipes.md`.

## Các mẫu (mục đích học tập)

Thư viện này cụ thể hóa ba mẫu kiến trúc từ các BI tool dành cho production như Metabase:

1. **Design tokens** — bảng màu/độ bo tròn/kiểu chữ tách biệt vào `:root`. Thay đổi một biến
   cập nhật toàn bảng điều khiển. Chủ đề = các bộ ghi đè biến, kích hoạt qua `data-theme`.
2. **Chart as plugin** — đăng ký biểu đồ với các tùy chọn nền tảng hợp nhất. Thay vì mỗi biểu đồ
   khai báo lại `legend`/`grid` riêng, bạn chỉ ghi đè những gì là duy nhất cho biểu đồ đó.
3. **Build-time composition** — một thư viện dùng chung được hợp nhất vào nhiều mẫu tại thời điểm
   xây dựng, tạo ra các tệp tin tự đóng gói cho việc triển khai. Không phụ thuộc runtime, không có CDN,
   không có fetch. Đầu ra giống như các tệp được sao chép-dán thủ công về mặt chức năng, nhưng nguồn
   thì DRY (không lặp).
