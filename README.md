# equity-research-vn

Skill ZCode tạo evidence pack phân tích cổ phiếu Việt Nam từ dữ liệu công khai và kiểm tra đầu ra bằng verifier độc lập gồm 76 yêu cầu.

## Phạm vi

- Pipeline 9 phase: sponsor, dữ liệu, cơ bản, định giá, kỹ thuật, hồ sơ kỹ thuật, tin tức, dashboard và verify/deploy.
- Mỗi phase giao tiếp qua `.task-state/task-state.json`.
- Mỗi yêu cầu tạo evidence riêng trong `.task-state/evidence/`.
- Báo cáo là tài liệu phân tích khách quan, không phải khuyến nghị mua hoặc bán.

## Cài đặt cho ZCode

```bash
git clone https://github.com/Thanhtran-165/equity-research-vn-public.git ~/.zcode/skills/equity-research-vn
python3 -m venv ~/.venv/equity-research-vn
source ~/.venv/equity-research-vn/bin/activate
python3 -m pip install -r ~/.zcode/skills/equity-research-vn/requirements-runtime.txt
```

### Cài đặt Sponsor

Full builder sử dụng hệ sinh thái vnstock Sponsor (`vnstock_data`, `vnstock`, `vnstock_ta`) và cố ý không fallback sang community tier. Cài trình cài đặt chính thức trong virtualenv:

```bash
python3 -m pip install --extra-index-url https://vnstocks.com/api/simple vnstock_installer
vnstock-installer
```

Đăng nhập/cấp quyền theo giao diện vnstock, rồi xác nhận trong đúng virtualenv:

```bash
python3 -c "from vnstock_data import Fundamental; print('Sponsor OK')"
```

Nếu full builder báo thiếu dependency Sponsor, quay lại mục này. Không cài package vào Python hệ thống và không chép credential vào repository.

### Compatibility Gate vnstock_data

Public builder hiện hỗ trợ các cặp đã kiểm định `distribution vnstock_data 3.2.7`
hoặc `3.2.8`, cùng `module.__version__ 3.2.2`. Với 3.2.7 builder giữ lời gọi
legacy; với 3.2.8 builder yêu cầu `format=time_series` và ánh xạ các VAS ID
chuẩn về contract nội bộ. Registry
machine-readable nằm tại `config/vnstock_compat_registry.json`; gate kiểm tra
version exact, API surface bắt buộc và schema DataFrame trước khi render. Schema
không nhận dạng, thiếu canonical field hoặc version/API chưa được kiểm định đều
fail-closed với hướng xử lý tiếng Việt. Gate dùng đúng interpreter đang chạy
builder và ghi `schema-fingerprint.json` vào work directory (artifact này không
thuộc repository public).
Các đơn vị trong fingerprint chỉ là assumptions của builder và luôn ghi
`not_verified`; compatibility gate không tuyên bố đã kiểm định đơn vị nguồn.

Khi nâng version, không sửa alias theo suy đoán: tạo đợt kiểm định riêng, cập
nhật registry với cặp version exact và capability, bổ sung fake DataFrame cho shape
mới cùng fingerprint/units, chạy toàn bộ regression và public guard, sau đó mới
đổi `tested_version`. Giữ cặp version cũ trong registry chỉ khi cả hai
đã có fixture và được kiểm định; nếu chưa, gate phải chặn.

## Chạy

```bash
python3 scripts/init_task_state.py FPT /tmp/equity-fpt
python3 scripts/build_report.py FPT tech
python3 scripts/independent_verifier.py FPT /tmp/vn100_FPT/FPT_Complete_Report.html
```

Có thể đặt các biến môi trường sau khi cần:

- `EQUITY_SKILL_DIR`: root của skill; mặc định tự suy ra từ vị trí script.
- `EQUITY_WORK_ROOT`: nơi ghi work directory; mặc định là thư mục tạm của hệ điều hành.
- `EQUITY_CACHE_DIR`: cache API; mặc định `~/.cache/equity-research-vn`.
- `VNALL_PREFLIGHT_SECTORS`: file sector oracle thay cho `config/preflight_p0_sectors.json`.

## Kiểm tra

```bash
python3 scripts/tests/requirements-lint.py
python3 scripts/check_public_repo.py
```

Các test trong `scripts/tests/` là source test có thể tái lập. Runtime output, tracker VN-ALL, log, screenshot, dữ liệu doanh nghiệp và evidence sinh ra không thuộc repository public.

## Nguồn phát hành

Bản public được tách bằng allowlist từ code freeze nội bộ `c8a3f6f2edfe8254f9b91ad8243fbb9a001d3ff1`, sau đó chỉ sửa portability và repo hygiene. Lịch sử kiểm định nội bộ và dữ liệu stress test không được đưa vào lịch sử Git public.

## Giấy phép và miễn trừ

MIT License. Xem [LICENSE](LICENSE) và [DISCLAIMER.md](DISCLAIMER.md).
