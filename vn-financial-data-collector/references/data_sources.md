# Nguồn dữ liệu tài chính VN — URL & cách truy cập

## Mục lục
1. [Vietstock](#vietstock)
2. [CafeF](#cafef)
3. [cophieu68](#cophieu68)
4. [Trang QHCD doanh nghiệp](#trang-qhcd)
5. [VSDC](#vsdc)
6. [Nguồn quốc tế phụ trợ](#quoc-te)

---

## Vietstock <a name="vietstock"></a>

**Dùng cho:** Giá realtime, EPS/BVPS/P/E/P/B cập nhật, số CP lưu hành, lịch sử giá.

| Dữ liệu | URL pattern |
|---|---|
| Trang tổng quan | `finance.vietstock.vn/[MÃ]-ten-cong-ty.htm` |
| Tài chính (KQKD/CDKT) | `finance.vietstock.vn/[MÃ]/tai-chinh.htm` |
| Tài liệu BCTC (PDF) | `finance.vietstock.vn/[MÃ]/tai-tai-lieu.htm` |
| Lịch sử giá | `finance.vietstock.vn/[MÃ]/lich-su-gia.htm` |

**Tips:**
- Trang tổng quan hiển thị **ngày cập nhật** ở góc trên — kiểm tra độ mới
- Ô "BVPS", "EPS", "P/E", "P/B" thường hiển thị sẵn ở trang tổng quan — **cross-check với tự tính**
- Lịch sử giá theo ngày — dùng cho giá cuối năm

---

## CafeF <a name="cafef"></a>

**Dùng cho:** Chuỗi BCTC theo năm (KQKD/CDKT/LCTT), tin tức kết quả kinh doanh.

| Dữ liệu | URL pattern |
|---|---|
| Trang cổ phiếu | `cafef.vn/du-lieu/hose/[mã]-ten-cong-ty.chn` |
| BCTC theo năm | `cafef.vn/du-lieu/bao-cao-tai-chinh/[mã].chn` |
| Lịch sử giá | `cafef.vn/du-lieu/hose/[mã].chn` (tab Lịch sử) |

**Tips:**
- Trang cổ phiếu hiển thị **số CP lưu hành hiện tại** ở sidebar — dùng để verify
- Tin tức kết quả kinh doanh công bố ~cuối tháng 1 năm sau → search "[tên DN] kết quả kinh doanh năm [N]" với `search_recency_filter=oneMonth`

---

## cophieu68 <a name="cophieu68"></a>

**Dùng cho:** Lịch sử chia tách cổ phiếu, sự kiện cổ đông.

| Dữ liệu | URL pattern |
|---|---|
| Sự kiện (chia tách, cổ tức) | `cophieu68.vn/quote/event.php?id=[mã]` |
| Tóm tắt tài chính | `cophieu68.vn/quote/summary.php?id=[mã]` |
| BCTC chi tiết | `cophieu68.vn/quote/financial.php?id=[mã]` |

**Tips:**
- Trang `event.php` liệt kê **lịch sử phát hành CP trả cổ tức + chia tách** — nguồn tốt nhất cho `shares_outstanding_b` qua các năm
- Mỗi dòng có "Cổ phiếu sau phát hành: X,XXX,XXX,XXX" — đọc số này để xây chuỗi

---

## Trang QHCD doanh nghiệp <a name="trang-qhcd"></a>

**Dùng cho:** BCTC kiểm toán chính thức (PDF), báo cáo thường niên.

URL trang QHCD thay đổi theo DN. Pattern tìm:
```
Google: "site:[domain-dn] báo cáo tài chính" → vào trang /quan-he-co-dong/bao-cao-tai-chinh
```

| DN tiêu biểu | Trang QHCD |
|---|---|
| Hòa Phát (HPG) | `hoaphat.com.vn/quan-he-co-dong/bao-cao-tai-chinh` |
| Vinamilk (VNM) | `vinamilk.com.vn/quan-he-co-dong/bao-cao-tai-chinh` |
| Vingroup (VIC) | `vingroup.net/quan-he-co-dong` |
| Vietcombank (VCB) | `vietcombank.com.vn/quan-he-co-dong` |

**Tips:**
- BCTC kiểm toán cho niên độ 31/12/N thường công bố **27-31/03/N+1** — kiểm tra ngày trên file
- File PDF có cả tiếng Việt lẫn tiếng Anh (HPG: `/investor-relations/financial-report`)
- Báo cáo thường niên (BCTN) có phần tóm tắt + BCTC đầy đủ + phân tích MD&A

---

## VSDC <a name="vsdc"></a>

**Dùng cho:** Báo cáo phát hành CP trả cổ tức (số CP chính thức).

URL: `vsd.vn/vi/ad/[mã-số-đợt]` — mỗi đợt phát hành có mã riêng.

**Tips:**
- Tìm: Google `"site:vsd.vn [mã CP] phát hành cổ phiếu trả cổ tức"`
- Có thông tin chính thức: tỷ lệ chia, ngày giao dịch không hưởng quyền, số CP phát hành thêm

---

## Nguồn quốc tế phụ trợ <a name="quoc-te"></a>

| Nguồn | URL | Dùng cho |
|---|---|---|
| Investing.com | `investing.com/equities/[tên-dn]-jsc-ratios` | Financial ratios 5 năm |
| Investing.com | `investing.com/equities/[tên-dn]-jsc-historical-data-splits` | Lịch sử chia tách CP |
| Yahoo Finance | `finance.yahoo.com/quote/[MÃ].VN/` | Lịch sử giá, dividend |
| Finbox | `finbox.com/HOSE:[MÃ]/explorer/pe_ltm/` | P/E chart 5 năm |
| WSJ | `wsj.com/market-data/quotes/VN/XSTC/[MÃ]/financials` | Balance sheet tổng quát |

**Lưu ý:** Dữ liệu quốc tế thường **trễ hơn nguồn VN** 1-2 quý và có thể **chưa adjust split kịp** → luôn verify với nguồn VN.
