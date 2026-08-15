# Authoring Pitfalls — đúc kết từ phiên chạy thật (V4 Flash, CTD 2026-08-01)

> Đọc TRƯỚC khi viết narrative/dashboard. Mỗi mục là 1 lỗi thật đã tốn 1 vòng sửa
> (47 → 67/68 REQ). Tránh được là đỡ 5 vòng lặp.

## 1. Số gần keyword bị gán sai ngữ cảnh (REQ-033/034/036/061)

Verifier quét số trong cửa sổ 60–80 ký tự quanh keyword (doanh thu/LNST/EPS/ROE…).
- "dư nợ ~5.900 tỷ" cách "doanh thu" ~70 ký tự → bị coi là doanh thu năm 2025 → FAIL.
- "vượt mốc 1.000 tỷ" sau "doanh thu kỷ lục" → claim doanh thu 1.000 → FAIL.
- **Luật**: số KHÔNG liên quan metric (nợ, tiền gửi, KLGD, tỷ lệ trong tin tức…) phải
  cách keyword ≥80 ký tự, hoặc không đặt cạnh keyword.
- Tin tức: tránh "doanh thu/lợi nhuận/LNST + số" trong cùng câu.

## 2. Bảng tài chính kiểu năm-ở-header bị REQ-033 đánh FAIL

`| Doanh thu | 9,078 | 14,537 | ... |` → số đầu cột bị gán năm SAI (năm gần nhất trong
±60 ký tự = 2025) → "revenue/2025: 9,078" → FAIL.
- **Thay bằng dạng**: "Doanh thu (tỷ VND): 2021: 9,078 · 2022: 14,537 · 2023: 16,528 · 2024: 22,906 · 2025: 30,699 (theo BCTC)".
- Mỗi giá trị đi kèm năm NGAY CẠNH nó.

## 3. CAGR: 2 claim cùng loại phải cách nhau >160 ký tự (REQ-036)

Context ±80 ký tự quanh claim CAGR; `_claim_metric` đọc keyword TRONG context:
- "CAGR doanh thu … 35.6%. CAGR lợi nhuận … 138.8%" → claim 138.8% dính "doanh thu"
  trong cửa sổ → so với CAGR doanh thu → FAIL.
- **Luật**: 1 metric 1 nơi; hoặc tách section; hoặc context của claim chỉ chứa đúng
  keyword metric của nó.
- Glossary KHÔNG được chứa "CAGR/tăng trưởng kép" + số (sinh claim ảo; "52 tuần"
  trong cửa sổ bị bắt làm giá trị).

## 4. Key metrics cần DIRECT source trong CÙNG CÂU (REQ-029 FIX-3b)

P/E, P/B, CAGR, ROE, ROA, EPS → source phải là tên cụ thể:
`bctc|vnstock|ref-|sponsor|kiểm toán|công bố|hose|filings|báo cáo tài chính|cafef|vietstock|finance|api`.
- "tính từ financials.json" KHÔNG đủ ("finance" phải nằm TRƯỚC dấu chấm câu).
- **Bẫy dấu chấm**: "financials.**json**" — dấu "." cắt câu → source phía sau không tính.
  Viết "financials" (bỏ .json) hoặc đặt [ref-N] trước dấu chấm.

## 5. P/B trong REQ-025: pattern cần "P/B <số>x" ≤30 ký tự không có chữ số xen giữa

- "P/B (2025) 0.74x" → "(2025)" chặn pattern → report value = null → FAIL.
- **Luật**: viết "P/B 0.74x" (năm để chỗ khác); dùng marker "hiện tại" nếu có nhiều
  candidate ("P/B hiện tại 0.74x").

## 6. Peer claims (REQ-032): ticker có chữ số + keyword P/E gần ticker = bẫy

- "P/E của FCN/C4G cao" → pattern bắt "4" trong "C4G" thành giá trị peer → FAIL.
- "P/E của C4G và FCN" → "C4G" không phải ticker 3-chữ-cái → vẫn dính qua pattern 2.
- **Luật**: không đặt "P/E|P/B" trong vòng 10 ký tự trước một số; viết
  "một số peer (C4G, FCN) có P/E cao" — "P/E cao" không kèm số.
- Giá trị peer hiển thị phải TRÙNG peers.json (REQ-032 ±10%).

## 7. ROE/ROA: năm gán sai vì `_year_in` lấy 20xx ĐẦU TIÊN trong ±80 ký tự

- "đáy 2021–2022 …, 2023–2025 phục hồi … ROE (0.29% → 8.32%)" → claim 0.29% gán năm
  2023, claim 8.32% gán năm 2021 → cả hai FAIL.
- **Luật**: câu claim ROE chỉ chứa ĐÚNG năm của nó trong ±80 ký tự; tách năm khác
  ra câu/xa hơn; viết "ROE 2025 đạt 8.32% (theo BCTC)".

## 8. REQ-062 period integrity: cần CSV nguồn + `financials.years` array

- `verified-dashboard-data.json.financials` phải có `years: [2021…2025]` + các array
  (revenue, netProfit, eps, totalAssets, equity, capex) — KHÔNG phải dict theo năm.
- Phải có `source-pack/income_statement_sponsor.csv` (+ balance/cash) với cột
  `report_period` = "year".

## 9. Runtime render: DATA keys và shape (REQ-069 — không cần browser vẫn check được)

- `data: DATA.peers` cần ARRAY trực tiếp `[{label,x,y,r,own}]` — KHÔNG bọc `{data:[…]}`.
- Template JS đọc thêm: `techWeeks/techPrice/techMA10/20/50/ddMonths/ddValues/distBins/distCounts` —
  thiếu 1 key = chart chết im lặng (lỗi runtime không bị REQ cú pháp bắt).
- Chart chết theo chuỗi: 1 lỗi trong DOMContentLoaded handler → mọi chart sau đó chết.

## 10. Lặt vặt

- "CFO" bị REQ-048 coi là management claim → phải có nguồn cạnh ("theo cash_flow.json").
- News: "Giải ngân 56%…" → macro claim (REQ-047) → thêm "theo VietnamFinance".
- "biên LNST 2.55% (781.3 tỷ LNST / 30,699 tỷ doanh thu)" → REQ-051 profit range FAIL.
  Viết "biên LNST 2.55% (theo BCTC)".
- Vốn hóa: "Tỷ trọng vốn hóa | 100 triệu…" → claim vốn hóa 100 triệu → FAIL (REQ-060/061).
  Viết "Tỷ trọng so vốn hóa (6,954 tỷ)" để pattern khớp recompute.

## 11. Meta nội bộ lộ ra cho người đọc (REQ-070 — phiên review thẩm mỹ 2026-08-01)

Vấn đề gốc: phase 6 chèn dấu vết kỹ thuật để verifier đọc nguồn, nhưng chúng HIỂN THỊ
cho người đọc cuối — mâu thuẫn "nội bộ vs người đọc". Tất cả đều phải ẩn/viết lại:

- Tên phase: "phase 3", "phase4a" trong narrative → bỏ hẳn.
- Tên file: "theo financials.json", "(nguồn: peers.json…)", "(theo cash_flow)",
  "(theo price_weekly)", "(theo technical_active.json)" → mô tả tiếng Việt:
  "(theo dữ liệu tài chính)", "(theo báo cáo lưu chuyển tiền tệ)", "(theo giá tuần)".
- `[ref-N]` viết THẲNG trong text → phải qua `{SRC('ref-N')}` (sup ẩn CSS). Kiểm tra:
  mọi `[ref-` trong HTML phải đứng sau `<sup class='cite'>`.
- Dòng "Ghi chú: …", "Nguồn: …" cạnh bảng → class `meta-note` (CSS display:none),
  giữ trong DOM để verifier còn đọc nguồn bảng.
- Tiêu đề trùng: template có h2 (section-title) → KHÔNG thêm h3 cùng nội dung.
- REQ-070 quét narrative các section chính, ref list cuối trang được miễn trừ.

## 12. Template 2 nguồn — sửa nhầm chỗ (quy trình, phiên CTD)

- Builder đọc template từ bản COPY (`/tmp/tpl_clean.html`), không phải template gốc skill.
- Sửa CSS vào template gốc mà không đồng bộ bản copy → fix "bay hơi" (bảng mất style,
  sup không ẩn) → phát hiện muộn sau 2 lượt review.
- **Luật**: khi sửa template/chart/JS — sửa CẢ template gốc lẫn bản copy builder dùng,
  rồi grep xác nhận chuỗi mới có trong file build.

## 13. Data thiếu → chart vẽ toàn 0 (phiên CTD)

- `balance_sheet.json` chỉ có 3 dòng tổng (Total Assets / Owner's Equity / Liabilities) —
  không có chi tiết tồn kho → `inventory = [0,0,0,0,0]` → 2 chart vẽ cột toàn 0, trông cụt.
- **Luật**: trước khi vẽ chart với 1 data key, kiểm tra key khác 0; nếu thiếu data →
  vẽ key khác có thật (ví dụ: nợ phải trả = tổng tài sản − vốn chủ sở hữu) hoặc bỏ chart.
- Fallback id cũ trong template (`$('chartBSDt2') || $('chartReturns')`) có thể đổ chart
  nhầm section khi canvas không tồn tại → dùng guard `if ($('id'))` cho canvas tùy chọn.
- **Annotation tĩnh trong template** (chartjs-plugin-annotation với yMin/yMax hardcode —
  ví dụ 'Hỗ trợ ~21,000' còn sót từ mã KDH cũ) → vẽ đường S/R sai hoàn toàn cho ticker mới.
  Luật: annotation PHẢI dùng DATA.<key> (tech52wLow, techMA50val), không hardcode số.

## 14. Thẩm mỹ khối text (phiên review UI 2026-08-01)

- CSS thiếu cho bảng (`.tbl`) / danh sách (`.section ul/li`) / tin tức (`.news-item`) →
  khối text trần trụi. Template phải có đủ: `.tbl`, `.section p/ul/li`, `.news-list/.news-item/.news-tag`,
  `sup.cite{display:none}`, `.meta-note{display:none}`, `.faint` có font-size nhỏ hơn body.
- Đoạn văn >250 ký tự → tách bullet (`<ul>`) hoặc đánh số (`<ol>`); mỗi ý 1 dòng, số liệu `<b>`.
- Class chữ phụ `.faint` chỉ đổi màu → phải kèm font-size (12px) — nếu không chữ phụ
  to bằng chữ chính, phá thứ bậc thông tin.

## 15. Residual dữ liệu mã khác khi copy báo cáo (cohort V5 2026-08-01)

- Copy HTML báo cáo ticker khác (vd CTD) rồi thay số → **số cũ còn sót ở context khác**
  (CSS, chart label, narrative, insight, risk table): HPG chứa PE 7.9 / ROE 8.3% /
  CAGR -18.2% / upside 35% / "114M cp" / "Coteccons" của CTD → fail 9 REQ (63/74).
- Mỗi lần `replace` 1 số tạo residual mới: thay 7.9→11.0 ở chỗ này, số 7.9 vẫn còn ở
  chỗ kia (verifier vẫn tìm thấy → REQ-060/061 fail dai dẳng).
- **Luật:** KHÔNG bao giờ dùng báo cáo mã khác làm template — build từ
  `dashboard_template.html` TRẮNG + fill data đúng ticker (phase6-dashboard.md mục
  "CẤM COPY BÁO CÁO MÃ KHÁC"). Sau build, grep ticker cũ + số đặc trưng của nó.
- Residual nguy hiểm nhất khi **trùng số ngẫu nhiên** (2 mã cùng PE ~7.9) → verifier
  không bắt được → dữ liệu sai lẫn mà vẫn PASS. Phòng bằng quy trình, không dựa vào verifier.
