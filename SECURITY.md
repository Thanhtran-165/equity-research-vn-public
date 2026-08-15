# Security policy

Không commit credential, cookie, API token, dữ liệu tài khoản vnstock hoặc output chứa đường dẫn/cấu hình cục bộ.

Nếu phát hiện lỗ hổng, hãy báo riêng cho maintainer trước khi công khai chi tiết. Không đưa dữ liệu tài chính chưa được phép phân phối vào issue hoặc pull request.

Repository áp dụng `scripts/check_public_repo.py` để chặn file sinh, file lớn, absolute path cá nhân và các mẫu credential phổ biến. Đây là lớp phòng vệ bổ sung, không thay thế secret scanner của nền tảng Git hosting.
