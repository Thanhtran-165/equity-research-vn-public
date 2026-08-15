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

Full builder sử dụng hệ sinh thái vnstock Sponsor (`vnstock_data`, `vnstock`, `vnstock_ta`). Hãy đăng nhập và cài các gói này theo tài liệu vnstock dành cho tài khoản của bạn.

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
