# SECTOR PACK v3 — Phân tích ngành khách quan (2026-08-02)

> **Định vị**: khái niệm ngành + cách đọc từ BCTC + tiêu chí theo dõi — KHÔNG khuyến
> nghị mua/bán (xem `DISCLAIMER.md`). Không chứa số liệu thị phần/công ty cụ thể —
> mọi số phải từ data đã verify.
>
> **Cách dùng**: `scripts/build_report.py` đọc pack theo ngành của ticker → sinh section
> "Phân tích ngành" (đặc thù + cách đọc + tiêu chí theo dõi). Pack là nguồn KHÁI NIỆM —
> builder chỉ trích phần phù hợp, không chép nguyên văn.

---

## 1. NGÂN HÀNG

### Đặc thù
- Kinh doanh "hàng hóa" là tiền — doanh thu chính = thu nhập lãi thuần (NII) + thu nhập ngoài lãi (phí, ngoại hối, đầu tư)
- Không có "net sales" — không áp dụng CCC/FCFF/WACC corporate; định giá chủ yếu P/B + DDM
- Lợi nhuận nhạy cảm: biên lãi thuần (NIM), chất lượng tài sản (nợ xấu), đòn bẩy vốn (CAR), chi phí vốn (CASA)

### Cách đọc từ BCTC (bẫy)
- Revenue = **Total Operating Income** (không tìm "Net sales")
- Cột balance sheet IN HOA (`TOTAL ASSETS`, `"OWNER'S EQUITY"`) — khớp case-insensitive
- CFO thường âm/biến động do bản chất hoạt động tín dụng — KHÔNG phải dấu hiệu xấu, không dùng FCFF
- ROE/PB là chỉ số chính; EPS ngân hàng có thể bị pha loãng bởi phát hành tăng vốn

### Tiêu chí theo dõi
- NIM (biên lãi thuần), CASA (tiền gửi không kỳ hạn / tổng tiền gửi), NPL (nợ xấu), CAR (an toàn vốn), room tín dụng NHNN — từ BCTC hàng quý + công bố NHNN

---

## 2. BẤT ĐỘNG SẢN & XÂY DỰNG

### Đặc thù
- Chu kỳ dài, phụ thuộc: pháp lý dự án, lãi suất, dòng vốn tín dụng BĐS, cung-cầu khu vực
- Doanh thu nhận theo tiến độ (construction) hoặc bàn giao (developer) — lợi nhuận 1 năm có thể không đại diện
- Dòng tiền: presales (khách ứng trước) tạo CFO dương giả tạo khi bán hàng mạnh; CFO âm khi mở rộng (nhà thầu: backlog, ứng trước)

### Cách đọc từ BCTC (bẫy)
- P/E thấp chưa chắc "rẻ" — EPS bóp méo bởi ghi nhận doanh thu theo dự án (một dự án lãi lớn đẩy EPS 1-2 năm)
- Xem: vòng quay hàng tồn kho (dở dang), khách ứng trước (presales), dòng tiền hoạt động dài hạn thay vì 1 năm
- Nhà thầu: backlog (khối lượng đơn hàng) là chỉ số dẫn — xem thuyết minh BCTC

### Tiêu chí theo dõi
- BĐS: presales, dở dang, tiến độ pháp lý dự án, tồn kho/doanh thu
- Xây dựng: backlog, biên gộp hợp đồng, ứng trước khách hàng, chu kỳ thanh toán

---

## 3. CHU KỲ HÀNG HÓA (thép, phân bón, hóa chất, dầu khí, than, xi măng)

### Đặc thù
- Lợi nhuận theo chu kỳ giá hàng hóa (đỉnh-đáy): giá thép/quặng/phân bón/dầu thay đổi theo cung cầu toàn cầu
- EPS đỉnh chu kỳ rất cao (P/E thấp giả tạo), EPS đáy có thể âm — **P/E raw dễ đánh lừa**

### Cách đọc từ BCTC (bẫy)
- **Luôn dùng P/E chuẩn hóa** (giá ÷ median EPS 5 năm) bên cạnh P/E raw (REQ-074 bắt buộc khi chu kỳ)
- CAGR đỉnh-đáy thấp/âm — so sánh đỉnh-đỉnh hoặc đáy-đáy mới có nghĩa
- So sánh định giá theo chu kỳ; kiểm biên gộp khi giá đổi chiều
- Đòn bẩy: công ty chu kỳ vay nặng khi mở rộng — xem nợ/EBITDA qua chu kỳ

### Tiêu chí theo dõi
- Giá hàng hóa quốc tế (thép HRC, quặng sắt, urê, dầu Brent) — nguồn vĩ mô, sản lượng tiêu thụ, biên gộp, tồn kho

---

## 4. TIÊU DÙNG & BÁN LẺ

### Đặc thù
- Doanh thu phụ thuộc sức mua nội địa (GDP tiêu dùng) — nhu cầu tương đối ổn định nhưng cạnh tranh cao
- Bán lẻ: chuỗi cửa hàng (diện tích, SSSG), tồn kho, vòng quay vốn lưu động
- FMCG: thương hiệu, phân phối, chi phí bán hàng cao

### Cách đọc từ BCTC (bẫy)
- CCC (DIO+DSO−DPO) quan trọng — bán lẻ tồn kho lớn, vòng quay nhanh là tốt
- Biên gộp theo mặt hàng; chi phí bán hàng & quản lý (SG&A) / doanh thu — mở rộng chuỗi làm chi phí quản lý đội lên trước khi doanh thu kịp theo
- Mở rộng nhanh → CFO có thể âm (vốn lưu động) dù lợi nhuận tốt

### Tiêu chí theo dõi
- SSSG (doanh thu cùng cửa hàng), số cửa hàng mới, tồn kho/doanh thu, biên gộp, SG&A/doanh thu

---

## 5. CHỨNG KHOÁN & QUỸ

### Đặc thù
- Doanh thu phụ thuộc thanh khoản thị trường: môi giới (KLGD), tự doanh (mark-to-market), cho vay margin, lãi từ tài sản tài chính
- Lợi nhuận biến động mạnh theo chu kỳ thị trường chứng khoán (khối lượng giao dịch)

### Cách đọc từ BCTC (bẫy)
- Doanh thu = doanh thu hoạt động (môi giới + tự doanh + lãi tài sản tài chính) — không có "net sales" kiểu sản xuất
- Lợi nhuận tự doanh phụ thuộc giá cổ phiếu tự có — xem cơ cấu tài sản tài chính (trading book)
- CCC không áp dụng; dùng P/B (tài sản ròng) + ROE qua chu kỳ thị trường

### Tiêu chí theo dõi
- KLGD trung bình thị trường (HOSE/HNX), dư nợ margin toàn ngành, market share môi giới, giá trị tài sản tài chính

---

## 6. BẢO HIỂM

### Đặc thù
- Kinh doanh rủi ro: doanh thu phí bảo hiểm + thu nhập đầu tư từ dự phòng phí
- Lợi nhuận trễ: nhận phí trước, chi trả bồi thường sau — dòng tiền âm khi mở rộng nhanh là bình thường
- Yêu cầu vốn theo quy định (vốn khả dụng, biên khả năng thanh toán)

### Cách đọc từ BCTC (bẫy)
- "Net revenue of insurance premium" / "Net sales from insurance business" là doanh thu (đã có trong headers.py alias)
- Shares: bảo hiểm thường KHÔNG có "Charter capital" → dùng back-calc hoặc overview issue_share
- EPS nhỏ so với vốn hóa (tài sản đầu tư lớn) — P/B + tỷ lệ kết hợp (combined ratio) quan trọng hơn P/E

### Tiêu chí theo dõi
- Tỷ lệ kết hợp (combined ratio = chi phí bồi thường + chi phí khai thác / phí), tăng trưởng phí, lợi suất đầu tư, biên khả năng thanh toán

---

## 7. NĂNG LƯỢNG & ĐIỆN

### Đặc thù
- Điện: doanh thu ổn định (hợp đồng PPA), phụ thuộc thủy văn (thủy điện), giá nhiên liệu (nhiệt điện), phụ tải
- Dầu khí thượng nguồn: giá dầu, sản lượng, chi phí khai thác
- Khí/LPG: sản lượng tiêu thụ, giá bán, tồn kho

### Cách đọc từ BCTC (bẫy)
- Thủy điện: so sánh sản lượng với trung bình nhiều năm (năm hạn/mưa lệch lớn)
- Nhiệt điện: biên theo giá than/khí — xem cơ chế giá điện (điều chỉnh giá)
- Đòn bẩy cao đặc trưng (tài sản lớn, vay dài hạn) — dùng DSCR (khả năng trả nợ), tỷ lệ nợ

### Tiêu chí theo dõi
- Giá dầu/khí/than, sản lượng, giá điện điều chỉnh (EVN), thủy văn, tồn kho khí/LPG

---

## 8. VẬN TẢI & CẢNG BIỂN / HÀNG KHÔNG

### Đặc thù
- Cảng: doanh thu theo lượng hàng (container/TEU, tấn), giá dịch vụ cảng, vị thế vùng
- Hàng không: doanh thu vận tải hành khách + hàng hóa; lợi nhuận nhạy cảm giá nhiên liệu + tỷ giá (thuê máy bay ngoại tệ)
- Vận tải đường bộ/logistics: biên mỏng, phụ thuộc giá nhiên liệu

### Cách đọc từ BCTC (bẫy)
- Hàng không: chi phí nhiên liệu + chi phí thuê/bảo dưỡng máy bay ngoại tệ → lợi nhuận dễ lỗ khi giá nhiên liệu leo thang, tỷ giá bất lợi
- Cảng: tài sản cố định lớn, khấu hao cao — EBIT/EBITDA chứ không chỉ LNST
- CCC: cảng/logistics vốn lưu động lớn

### Tiêu chí theo dõi
- Sản lượng hàng hóa cảng, giá cước, giá nhiên liệu, tỷ giá, hệ số tải (hàng không)

---

## 9. DƯỢC PHẨM & Y TẾ

### Đặc thù
- Doanh thu ổn định (nhu cầu y tế ít co giãn), phụ thuộc: danh mục thuốc, đấu thầu, giá thuốc quản lý
- Kênh phân phối: bệnh viện (đấu thầu), nhà thuốc (OTC)
- Nghiên cứu phát triển (R&D) tạo moat nhưng chi phí cao

### Cách đọc từ BCTC (bẫy)
- Tăng trưởng phụ thuộc danh mục sản phẩm mới + vị thế đấu thầu — xem thuyết minh cơ cấu doanh thu theo kênh
- Tồn kho dược: hạn dùng — vòng quay quan trọng
- CCC + biên gộp là chỉ số chính; ROE ổn định cao là điểm tích cực

### Tiêu chí theo dõi
- Doanh thu theo kênh, biên gộp, vòng quay tồn kho, chính sách giá/đấu thầu

---

## 10. CÔNG NGHỆ & VIỄN THÔNG

### Đặc thù
- Doanh thu phần mềm/dịch vụ (hợp đồng dài hạn), viễn thông (thuê bao, cước)
- Tăng trưởng phụ thuộc đầu tư công nghệ (chuyển đổi số), nhân sự chất lượng cao
- Biên gộp phần mềm cao; chi phí nhân sự chiếm tỷ trọng lớn

### Cách đọc từ BCTC (bẫy)
- Doanh thu dịch vụ thường ghi nhận theo tiến độ — kiểm hợp đồng dài hạn (backlog số hóa)
- CCC: ít tồn kho, phải thu lớn (B2B, chính phủ) — DSO quan trọng
- Định giá: PEG (P/E theo mức mở rộng) cho phần mềm, EBITDA-based cho viễn thông (khấu hao mạng lưới lớn)

### Tiêu chí theo dõi
- Doanh thu dịch vụ, DSO, tỷ lệ hợp đồng định kỳ (recurring revenue), đầu tư R&D

---

## 11. NÔNG NGHIỆP & CHẾ BIẾN (thủy sản, cao su, đường, gỗ, lương thực)

### Đặc thù
- Phụ thuộc: giá nguyên liệu, thời tiết, xuất khẩu (tỷ giá, thuế quan), chu kỳ sinh học (cao su 7-10 năm)
- Thủy sản: nuôi trồng rủi ro dịch bệnh, giá cả thị trường

### Cách đọc từ BCTC (bẫy)
- Tồn kho sinh học (cao su, thủy sản) — đánh giá lại có thể bóp méo lợi nhuận
- Biên gộp theo giá nguyên liệu — xem xu hướng, không chỉ 1 năm
- Đầu tư dài hạn vào vườn cây (cao su) — khấu hao + chi phí chăm sóc trước khi thu hoạch

### Tiêu chí theo dõi
- Giá hàng hóa nông sản, sản lượng, diện tích vườn cây, tồn kho, tỷ giá, thuế quan xuất khẩu

---

## 12. NGÀNH KHÁC (generic)

### Đặc thù
- Ngành không nằm trong 11 nhóm trên: áp dụng khung chung — mô hình kinh doanh, chu kỳ, cạnh tranh

### Cách đọc từ BCTC (bẫy)
- Luôn kiểm: doanh thu = gì (hàng hóa/dịch vụ/tài chính), CCC có áp dụng không, P/E có ý nghĩa không (lỗ/chu kỳ)
- Cảnh giác P/E âm hoặc EPS biến động mạnh → P/E chuẩn hóa thay thế

### Tiêu chí theo dõi
- Doanh thu, biên gộp, ROE, dòng tiền hoạt động — xu hướng 5 năm

---

## 13. CÔNG NGHIỆP & SẢN XUẤT

### Đặc thù
- Sản xuất & gia công (cơ khí, nhựa, bao bì, linh kiện, điện tử gia dụng) — biên gộp theo giá nguyên liệu + hiệu suất nhà máy
- Khách hàng chủ yếu doanh nghiệp (B2B/OEM) — đơn hàng theo hợp đồng, phụ thuộc chu kỳ công nghiệp

### Cách đọc từ BCTC (bẫy)
- CCC quan trọng: tồn kho + phải thu lớn (B2B) — so vòng quay theo thời gian
- Biên gộp theo giá nguyên liệu đầu vào (nhựa, thép, giấy, hóa chất) — xem xu hướng, không chỉ 1 năm
- Nhà máy mới: khấu hao cao giai đoạn đầu — lợi nhuận thấp là đặc trưng, chưa phải dấu hiệu kém

### Tiêu chí theo dõi
- Giá nguyên liệu đầu vào, đơn hàng/backlog, tồn kho, biên gộp, công suất nhà máy

---

## MAP NGÀNH → PACK (builder dùng)

| Sector (từ tracker/vnstock) | Nhóm pack |
|---|---|
| banking, bank | 1. NGÂN HÀNG |
| realestate, bds, property | 2. BĐS & XÂY DỰNG |
| construction, xây dựng, nhà thầu | 2. BĐS & XÂY DỰNG |
| steel, thép, materials, hóa chất, phân bón, dầu khí, than, xi măng | 3. CHU KỲ HÀNG HÓA |
| retail, bán lẻ, consumer, thực phẩm, đồ uống, dệt may | 4. TIÊU DÙNG & BÁN LẺ |
| securities, chứng khoán | 5. CHỨNG KHOÁN |
| insurance, bảo hiểm | 6. BẢO HIỂM |
| energy, điện, power, gas, khí | 7. NĂNG LƯỢNG & ĐIỆN |
| transport, vận tải, cảng, hàng không, logistics | 8. VẬN TẢI & CẢNG |
| pharma, dược, y tế | 9. DƯỢC PHẨM |
| tech, công nghệ, viễn thông | 10. CÔNG NGHỆ |
| thủy sản, cao su, đường, gỗ, nông | 11. NÔNG NGHIỆP |
| industrial, công nghiệp, sản xuất, cơ khí, nhựa, bao bì | 13. CÔNG NGHIỆP & SẢN XUẤT |
| *(khác)* | 12. NGÀNH KHÁC |
