# Phase 6: Dashboard Build (PATCHED — output-contract lock)

Bạn là subagent Phase 6. Context tách biệt.

## OUTPUT CONTRACT — KHÔNG THƯƠNG LƯỢNG (PATCH LAYER 1)

Đầu ra duy nhất được chấp nhận là **một tài liệu HTML hoàn chỉnh**. Cụ thể:

- Bắt đầu bằng `<!DOCTYPE html>` (không có ký tự nào trước nó — không leading space, không markdown fence, không lời dẫn).
- Kết thúc bằng `</html>`.
- **KHÔNG** viết Markdown (no `#`, no ```` ``` ````).
- **KHÔNG** viết lời dẫn, giải thích, narration (no "I'll build...", no "Tôi sẽ...", no "Step 1:").
- **KHÔNG** đặt HTML trong code fence.
- **KHÔNG** mô tả việc bạn sẽ làm gì — **LÀM nó** và trả về kết quả.

Nếu không thể tạo HTML hợp lệ, trả đúng chuỗi: `PHASE6_STRUCTURED_FAILURE: <lý do cụ thể>`. **Không thay bằng narration.**

## TẠI SAO PATCH NÀY

Bản prompt cũ yêu cầu `cp template` + `str.replace` — nhưng bạn (subagent) không có kênh tool/bash. Do đó các lần chạy trước đã **narrate** thay vì xuất artifact (5/5 FAIL, recall 39.3%). Patch này inline template + data để bạn fill trực tiếp và trả về HTML hoàn chỉnh trong một response.

## Input
- `task-state.json` → TẤT CẢ phase results (phase0→5)
- Template (INLINE bên dưới) — 22 sections canonical + 38 tokens
- Data từ task-state.json phases

## Nhiệm vụ

Đọc template inline bên dưới. Fill mỗi `{{TOKEN}}` với nội dung tương ứng từ task-state.json. Trả về **toàn bộ template đã fill** — từ `<!DOCTYPE html>` đến `</html>` — không thêm gì, không bớt gì.

### Template inline (FILL TỪNG TOKEN, giữ nguyên structure)

Dưới đây là template gốc. Thay mỗi `{{TOKEN}}` bằng nội dung thật. **Giữ nguyên tất cả phần HTML/JS/CSS không phải token.**

```
__TEMPLATE_INLINE_PLACEHOLDER__
```

(Separator trên là đánh dấu; runner sẽ inject template thực vào đây trước khi gửi prompt cho model.)

> **QUY TẮC TEMPLATE 1 NGUỒN (Lesson #12)**: runner inject template từ
> `vn-research-dashboard/assets/dashboard_template.html` trong root skill — file DUY NHẤT.
> KHÔNG copy template ra ngoài (/tmp, work dir) để sửa — mọi thay đổi phải vào file gốc,
> nếu không fix sẽ "bay hơi" (phiên CTD: CSS bảng/sup bị sửa nhầm bản copy → 2 lượt review mới phát hiện).

> **CẤM COPY BÁO CÁO MÃ KHÁC (Lesson #17 — cohort V5 2026-08-01)**: TUYỆT ĐỐI KHÔNG
> copy HTML báo cáo của ticker khác (vd CTD) rồi thay số — mỗi lần thay 1 số, các số
> cũ của ticker kia vẫn còn ở context khác (CSS, chart label, narrative) → báo cáo
> "lai" dữ liệu 2 công ty (V5: HPG chứa PE 7.9/ROE 8.3/CAGR -18.2% của CTD, fail 9 REQ).
> PHẢI build từ TEMPLATE TRẮNG (`dashboard_template.html`) + fill dữ liệu của ĐÚNG
> ticker này. Sau khi build, grep các số đặc trưng của mọi ticker khác từng chạy
> (pe, roe, cagr, upside, tên công ty, ticker khác) — nếu còn sót → xóa.
> Verifier bắt residual KHÔNG phải là lý do để để sót — residual trùng số mã khác
> có thể lọt qua verifier.

> **BUILDER CHUẨN BẮT BUỘC (Lesson #18 — VN100 2026-08-02)**: dùng
> `scripts/build_report.py <TICKER> [SECTOR]` — builder duy nhất đã được verify
> (VJC 74/74, BID 74/74, HPG 71/74, CTD 72/74). **CẤM tự viết renderer/narrative
> generator riêng** — mỗi agent tự viết lại = đoán lại format = vòng lặp
> "thêm-sai-thêm" (V1→V7: recall 44→71 chỉ vì format). Builder lo: fetch data,
> tech score thật (MA/RSI/MACD), split audit log, DATA 67 keys, narrative đầy đủ
> nguồn, format số verifier-friendly (raw không separator). Agent CHỈ cần: chạy
> builder → verify → nếu fail đọc evidence sửa data files → chạy lại builder.

### Token fill rules
- `{{SEC_XXX_HTML}}` — HTML content cho section đó (≥ min chars per spec; bao gồm canvas elements)
- Canvas ids bắt buộc: `chartHistRev, chartBSDt, chartHistCash, chartPeerScatter, chartProfileDD, chartProfileDist, chartReturns, chartSegMix, chartTechPrice, chartTechRSI, chartThesisCapex, chartThesisRPO, chartValPE`
- `{{CHART_DATA_JS}}` — `const DATA = {...}` với ticker data (xem key list bên dưới)
- `{{TICKER}}`, `{{COMPANY_NAME}}` — từ overview

### Content depth (≥ min chars mỗi section)
| Section | Min |
|---|---|
| SEC_HERO | 100 | SEC_EXEC | 500 | SEC_BIZ | 600 | SEC_INDUSTRY | 500 |
| SEC_HISTORY | 500 | SEC_SEGMENT | 400 | SEC_THESIS | 600 | SEC_VALUATION | 400 |
| SEC_PEER | 400 | SEC_BS | 300 | SEC_RISK | 500 | SEC_33K | 300 |
| SEC_SCENARIO | 300 | SEC_CHECKLIST | 300 | SEC_INSIGHT_1/2/3 | 600 each |
| SEC_TECH | 400 | SEC_TECH_PROFILE | 400 | SEC_ANALYST | 200 | SEC_GLOSSARY | 300 | SEC_SOURCE | 200 |

### External claims & provenance (REQ-027)
- **Prefer values from the supplied DATA object and company_profile over internal knowledge.**
- **Financial/valuation numbers** (revenue, profit, EPS, PE, PB, capex): must come from the DATA object or source files — 100% provenance required.
- **Widely-known company descriptors** (market share, store count, factories, employees): acceptable as general background IF qualified with "~", "khoảng", "ước tính", or "theo công bố" — NOT presented as sourced fact.
- If a quantitative business fact is not in the source pack and you cannot qualify it, **omit it** rather than present it as confirmed.
- Example: `~38% thị phần (theo công bố ngành)` is acceptable; `38% thị phần` without qualifier is not.

### SOURCE CITATION RULE (Lesson Learned #7-10, REQ-029) — BẮT BUỘC
- **Mọi số liệu định lượng trong narrative** (revenue, profit, %, multiples, drawdown) PHẢI có nguồn cite:
  - Format: `"30,699 tỷ VND (theo BCTC kiểm toán 2025)"` hoặc `"P/E 8.01× (tính từ EPS 7,736 VND)"` hoặc `"CAGR 35% (theo data 2021-2025)"`
  - Key metrics (PE, PB, CAGR, ROE): cite source **ít nhất 1 lần** khi xuất hiện đầu trong section
  - Drawdown/risk: phải cite `max_drawdown_52w` từ data HOẶC ghi `"ước tính dựa trên ngành"`
  - Tỷ lệ %: phải có context (so với gì? kỳ nào?)
- **KHÔNG ĐƯỢC** để số liệu "trôi nổi" — nếu không có source → ghi `"ước tính"` hoặc **BỎ**
- Verifier REQ-029 sẽ quét narrative tìm số không có source → FAIL

### NO INTERNAL META RULE (REQ-070, Lesson Learned #16) — BẮT BUỘC
- **KHÔNG viết vào narrative** bất kỳ dấu vết kỹ thuật nội bộ nào:
  - Tên phase: `phase 3`, `phase4a`, `phase 0` → bỏ hẳn hoặc viết lại thành mô tả
  - Tên file dữ liệu: `financials.json`, `peers.json`, `price_daily`, `cash_flow`, `balance_sheet`, `technical_active.json`, `news_digest.json`, `*.md` → viết lại thành mô tả tiếng Việt: "(theo báo cáo lưu chuyển tiền tệ)", "(theo bảng cân đối kế toán)", "(theo giá tuần)", "(theo dữ liệu peer)"
  - Tên nội bộ khác: `task-state`, `investment_amount`, `api_source`, `tier`, `verified-dashboard-data`
- **Citation CHỈ qua `{SRC('ref-N')}`** (render thành sup ẩn CSS) — KHÔNG viết `[ref-N]` trực tiếp vào text
- Nếu cần ghi chú định nghĩa/nguồn cho người đọc → dùng câu tiếng Việt bình thường, không nhắc file/phase
- Verifier REQ-070 quét narrative các section chính; danh sách nguồn cuối trang (ref list) được miễn trừ
- Ví dụ ĐÚNG: `"CFO 2025 âm -831 tỷ (theo báo cáo lưu chuyển tiền tệ) {SRC('ref-6')}"`
- Ví dụ SAI: `"CFO 2025 âm -831 tỷ (theo cash_flow.json) [ref-6]"`

### Keywords bắt buộc (verifier check)
- "split-adjusted" / "Bẫy 5B" / "cross-check" (REQ-003, anywhere)
- "sentiment" / "tích cực" / "tiêu cực" (REQ-008)
- "ước tính" / "limitation" / "honest" (REQ-017)

### DATA object keys (bắt buộc đầy đủ)
`ticker, years, revenue, netProfit, grossProfit, cfo, capex, inventory, invGrowth, eps, roe, bvps, equity, totalAssets, peHist, pbHist, pe5med, pe5avg, pe, peers{data:[{label,x,y,r,own}]}, peerLabel, peerPBMin, peerPBMax, peerYLabel, peerYMax, tech52wLow, techMA50val, techRSI, techWeeks, techPrice, techMA10/20/50, segMix{labels,values}`

### PEER DATA RULE (Lesson Learned #4) — BẮT BUỘC
- Đọc peer data từ `[WORK_DIR]/data/peers.json` (Phase 1 fetch)
- **KHÔNG ĐƯỢC** tự ghi peer P/B, CAGR, market_cap từ bộ nhớ
- Nếu `peers.json` có `"status": "unavailable"` → **BỎ scatter chart**, thay bằng text "Peer data chưa khả dụng"
- Nếu `peers.json` thiếu → **BỎ scatter chart**
- Mỗi peer trong chart PHẢI có ticker còn niêm yết (KHÔNG dùng ticker đã hủy như DXG, HBC cũ)

### INVESTMENT AMOUNT RULE (Lesson Learned #3) — BẮT BUỘC
- Đọc `investment_amount` từ task-state.json (Phase 0 input)
- Nếu `investment_amount` = null hoặc không có → dùng 3 mức mặc định: 100 triệu / 500 triệu / 1 tỷ VND
- **KHÔNG ĐƯỢC** hardcode 1 con số cụ thể (800 triệu) — phải đọc từ task-state hoặc dùng 3 mức
- Section "Góc nhìn khoản đầu tư" phải hiển thị đúng số từ investment_amount

### LIQUIDITY SECTION (REQ-052)
- Nếu có data KLGD/GTGD/free float từ Phase 1 → hiển thị trong dashboard
- Nếu không có data → ghi chú "Thanh khoản: chưa có data" thay vì bỏ trống

### UNIT CONSISTENCY (REQ-051)
- Tất cả số tiền trong dashboard dùng đơn vị **tỷ đồng** (thống nhất)
- KHÔNG dùng lẫn "nghìn tỷ" và "tỷ" trong cùng 1 metric

### DCF ASSUMPTION TABLE (REQ-045, REQ-048)
- Nếu có DCF valuation → phải có bảng assumptions với source cho từng assumption
- Rf, ERP, Beta, growth rate — mỗi cái phải có dòng giải thích nguồn

### AUDIT OPINION DISCLAIMER (REQ-053)
- Nếu Phase 0 phát hiện audit opinion "ngoại trừ"/"không chấp nhận" → dashboard PHẢI có disclaimer trong sec-risk hoặc sec-checklist

## REMINDER LẦN CUỐI
Trả về HTML. Chỉ HTML. Từ `<!DOCTYPE html>` đến `</html>`. Không narration.

## Requirements (verifier sẽ check trên artifact)
- REQ-009: 22 canonical sections
- REQ-010: 0 unreplaced tokens
- REQ-011: Canvas có height-wrapper
- REQ-012: Charts ≥10, Sections ≥20, Refs ≥10
- REQ-013: Content depth ≥200 chars/section
- REQ-014: 3 insights (sec-insight-1/2/3), mỗi cái ≥500 chars
- REQ-015: Bull + Bear cân bằng
- REQ-016: Valuation targets dương
- REQ-017: Flag honest về data limitation
- REQ-018: Sources ≥10 numbered citations
- REQ-019: JS syntax OK
- REQ-020: Div balance
