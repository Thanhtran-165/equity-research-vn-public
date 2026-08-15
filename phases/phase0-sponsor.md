# Phase 0: Sponsor Package Detection

Bạn là subagent Phase 0. Context tách biệt — chỉ làm việc này.

## Input
- Đọc `[WORK_DIR]/.task-state/task-state.json` → field `ticker`

## Nhiệm vụ
1. Check `~/.vnstock/auth_state.json` → xác nhận tier (golden/platinum)
2. Test import sponsor gold: `python3 -c "from vnstock_data import Finance; print('OK')"`
3. Nếu ImportError (`_GROUP_CODE` hoặc `_INDEX_MAPPING`): fix bằng `pip3 install 'vnstock==3.5.1' --break-system-packages`
4. Verify sponsor data ≥20 kỳ. **API FALLBACK BẮT BUỘC** — thử theo thứ tự:

```python
# API FALLBACK (Lesson Learned #1)
api_source = None
api_error = None

# Thử 1: vnstock_data sponsor gold (ưu tiên — ổn định nhất)
try:
    from vnstock_data import Finance
    f = Finance(source='VCI', symbol='[TICKER]')
    periods = len(f.income_statement())  # KHÔNG có param 'lang'
    if periods >= 20:
        api_source = 'vnstock_data_sponsor_gold'
except Exception as e:
    api_error = f'sponsor_gold: {e}'

# Thử 2: Vnstock community (fallback)
if api_source is None:
    try:
        from vnstock import Vnstock
        vs = Vnstock().stock(symbol='[TICKER]', source='VCI')
        inc = vs.finance.income_statement(period='year', lang='en')
        if len(inc) >= 5:
            api_source = 'vnstock_community'
    except Exception as e:
        api_error = f'{api_error}; community: {e}'

# Nếu cả 2 fail → KHÔNG bịa data, báo lỗi rõ ràng
if api_source is None:
    print(f'FAIL: cả 2 API đều lỗi — {api_error}')
    sys.exit(1)

print(f'OK: api_source={api_source}, periods={periods}')
```

5. **INPUT: Quy mô vốn** (Lesson Learned #3) — hỏi user:
   - "Anh/chị muốn xem góc nhìn khoản đầu tư với quy mô vốn bao nhiêu VND?"
   - Nếu user không trả lời hoặc chạy non-interactive → default: `investment_amount` = null
   - Lưu vào task-state.json field `investment_amount`

6. **AUDIT OPINION CHECK (REQ-053)** — kiểm tra ý kiến kiểm toán:
   - Đọc audit_opinion từ company_profile hoặc sponsor metadata
   - Nếu "ngoại trừ" / "không chấp nhận" / "từ chối" / "qualified" / "adverse" → lưu vào task-state
   - Phase 6 sẽ cần disclaimer trong dashboard

7. **FISCAL YEAR DETECTION (REQ-067)** — phát hiện năm tài chính (Pro review Wave 4: trước ghi nhầm REQ-051 — REQ-051 là unit consistency):
   - Đọc fiscal_year_end từ company_profile
   - Nếu không phải 31/12 → lưu `fiscal_year_type: "custom"` + `fiscal_year_end: "MM/DD"`
   - Cảnh báo nếu so sánh với peer khác FY

## Output — cập nhật task-state.json
```json
{
  "investment_amount": null,
  "phases": {
    "phase0_sponsor": {
      "status": "completed",
      "result": {"tier": "golden", "periods": 41, "sponsor_ok": true, "api_source": "vnstock_data_sponsor_gold", "version": "vnstock==3.5.1"}
    }
  }
}
```

## Requirements (REQ cho phase này)
- REQ-001: Sponsor import OK (KHÔNG fallback community)
- REQ-002: Sponsor data ≥20 kỳ

## KHÔNG được
- Fallback community tier (8 kỳ) — data sẽ sai 3-4×
- Skip nếu fail — phải fix sponsor trước khi qua Phase 1

## Không cần biết (không phải việc của phase này)
- Dashboard template, section map, canvas — Phase 6 lo
- Valuation method — Phase 3 lo
- News sentiment — Phase 5 lo
