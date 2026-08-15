# Sector oracle

`preflight_p0_sectors.json` là mapping `{ticker: canonical_sector}` dùng để ràng buộc REQ-040. File được tạo từ listing/ICB công khai và được pin bằng SHA-256 trong verifier.

Có thể thay thế bằng file khác qua biến `VNALL_PREFLIGHT_SECTORS`, nhưng verifier fail-closed nếu hash không khớp freeze. Khi tái tạo mapping chính thức, phải cập nhật đồng thời file, `PINNED_PREFLIGHT_SHA`, regression tests và `.verifier-hash`.
