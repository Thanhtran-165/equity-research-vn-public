# Claim Taxonomy & Falsification (Wave 2 — W2-5)

Mọi khẳng định trong báo cáo phải phân loại — research-grade không có "câu chắc nịch" không phân loại.

## 1. Bảng phân loại claim

| Loại | Định nghĩa | Tối thiểu phải kèm |
|---|---|---|
| **Fact** | Số liệu công bố | nguồn, ngày, kỳ, đơn vị, as-of |
| **Derived metric** | Tính từ fact (ROE, CAGR...) | công thức, input IDs, rounding, recompute evidence |
| **Estimate** | Ước lượng (fair value, WACC) | model version, giả định, range/sensitivity |
| **Inference** | Suy luận (chất lượng ROE, rủi ro) | chuỗi lý luận, competing explanation, confidence |
| **Forecast** | Dự báo tương lai | horizon, base rate, xác suất kịch bản, **invalidation trigger** |
| **Recommendation-like** | Mua/bán/phân bổ | suitability guardrail, rủi ro/sức chứa, người duyệt — mặc định CẤM tự động |

## 2. Falsification trigger (điều gì làm thesis SAI)

Mỗi luận điểm đầu tư (bull/bear) phải kèm **điều kiện bác bỏ** — điều gì quan sát được
sẽ chứng minh luận điểm sai:

| Thesis | Trigger bác bỏ (ví dụ) |
|---|---|
| "Biên LNST cải thiện nhờ kỷ luật thầu" | Biên LNST 2 quý liên tiếp < 2% trong khi doanh thu vẫn tăng |
| "Định giá rẻ so lịch sử" | P/B phá vỡ dưới đáy 5 năm kèm CFO âm kéo dài 3 năm |
| "Tăng trưởng bền vững" | Doanh thu tăng > SGR 2 năm liên tiếp mà nợ vay tăng tương ứng (không pha loãng) |

Nếu không nghĩ ra trigger → luận điểm chưa đủ chặt để đưa vào verdict.

## 3. Sử dụng trong pipeline

- Phase 2/3/5: output thêm `claim_type` cho các kết luận chính + `invalidation_trigger` cho thesis
- Phase 6: narrative các câu inference/forecast bắt buộc có từ khóa phân loại
  (theo bảng trên) — tránh "khẳng định quá mức" (overclaim)
- REQ-065 (verdict consistency) đã check tone — mở rộng dần theo taxonomy này
