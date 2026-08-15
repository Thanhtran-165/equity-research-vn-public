#!/usr/bin/env python3
"""
inject.py — Design-time composition tool

Hợp nhất _viz-shared/ (tokens.css, components.css, viz.js) VÀO các template HTML,
thay thế các placeholder {{VIZ_CSS}} / {{VIZ_JS}}. Kết quả: các template tự chứa
(single-file) — không phụ thuộc vào các file bên ngoài lúc chạy.

QUAN TRỌNG:
  - Chỉ thay thế placeholder thiết kế ({{VIZ_CSS}}, {{VIZ_JS}}).
  - KHÔNG đụng tới data placeholders dạng {{TICKER}}, {{COMPANY_NAME}}, {{ROLLING_DATA}}...
    (đó là dữ liệu báo cáo, được điền ở bước report-time).
  - Trả về mã thoát khác 0 nếu phát hiện placeholder VIZ_* chưa được thay thế.

Usage:
  python3 inject.py                          # build tất cả templates
  python3 inject.py --check                  # chỉ kiểm tra, không ghi file
  python3 inject.py --file path/to/tpl.html  # build 1 file cụ thể
"""
import argparse
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SKILLS = HERE.parent  # thư mục cha chứa các skill (cùng cấp với _viz-shared/)

# Templates dùng design system này (path tương đối SKILLS)
TEMPLATE_PATHS = [
    "vn-research-dashboard/assets/dashboard_template.html",
    "vn-technical-analysis/assets/technical_template.html",
    "vn-technical-analysis/assets/profile_template.html",
    "vn-news-digest/assets/news_template.html",
    "longform-report/assets/article_template.html",
]

CSS_PLACEHOLDER = "{{VIZ_CSS}}"
JS_PLACEHOLDER = "{{VIZ_JS}}"

# Data tokens KHÔNG được đụng tới (chỉ để document; kiểm tra regex phía dưới bắt tất cả {{UPPER}})
DATA_TOKEN_WHITELIST_NOTE = (
    "Data tokens ({{TICKER}}, {{COMPANY_NAME}}, {{ROLLING_DATA}}...) được GIỮ NGUYÊN — "
    "chỉ LLM fill ở report-time. inject.py chỉ thay {{VIZ_CSS}}/{{VIZ_JS}}."
)


def load_shared() -> tuple[str, str]:
    """Đọc tokens.css + components.css → gộp thành 1 khối <style>; viz.js → <script>."""
    tokens = (HERE / "tokens.css").read_text(encoding="utf-8")
    components = (HERE / "components.css").read_text(encoding="utf-8")
    viz_js = (HERE / "viz.js").read_text(encoding="utf-8")
    css_block = (
        "<!-- ===== VIZ DESIGN TOKENS + COMPONENTS (inlined từ _viz-shared/ by inject.py) ===== -->\n"
        "<style>\n"
        f"{tokens}\n{components}\n"
        "</style>"
    )
    return css_block, viz_js


def build_template(tpl_path: Path, css_block: str, viz_js: str, write: bool = True) -> tuple[bool, list[str]]:
    """
    Trả về (ok, issues).
    ok=True nếu tất cả placeholder VIZ_* đã được xử lý.
    """
    if not tpl_path.exists():
        return False, [f"file không tồn tại: {tpl_path}"]

    html = tpl_path.read_text(encoding="utf-8")
    issues = []

    # Thay CSS nếu có placeholder, hoặc nếu template vẫn còn :root inline cũ (chưa migrate)
    has_css_ph = CSS_PLACEHOLDER in html
    has_js_ph = JS_PLACEHOLDER in html

    if not has_css_ph and not has_js_ph:
        issues.append("SKIP (chưa có placeholder {{VIZ_CSS}}/{{VIZ_JS}} — chưa migrate template này)")
        return True, issues

    if has_css_ph:
        html = html.replace(CSS_PLACEHOLDER, css_block)
    if has_js_ph:
        # Bọc viz.js trong <script> — đặt vào vị trí placeholder (giữ nguyên ngữ cảnh)
        js_block = (
            "<!-- ===== VIZ.JS (inlined từ _viz-shared/ by inject.py) ===== -->\n"
            "<script>\n"
            f"{viz_js}\n"
            "</script>"
        )
        html = html.replace(JS_PLACEHOLDER, js_block)

    # Kiểm tra: không được sót VIZ_* (đã thay nhưng có lặp → vẫn OK, replace xóa hết)
    leftover_viz = re.findall(r"\{\{VIZ_[A-Z]+\}\}", html)
    if leftover_viz:
        issues.append(f"placeholder VIZ_* còn sót: {sorted(set(leftover_viz))}")
        return False, issues

    if write:
        tpl_path.write_text(html, encoding="utf-8")

    return True, issues


def main():
    ap = argparse.ArgumentParser(description="Inject _viz-shared CSS/JS vào templates")
    ap.add_argument("--check", action="store_true", help="chỉ kiểm tra, không ghi file")
    ap.add_argument("--file", help="build 1 file cụ thể (path tuyệt đối hoặc tương đối skills/)")
    args = ap.parse_args()

    css_block, viz_js = load_shared()
    write = not args.check

    if args.file:
        f = Path(args.file)
        if not f.is_absolute():
            f = SKILLS / args.file
        paths = [f]
    else:
        paths = [SKILLS / p for p in TEMPLATE_PATHS]

    print(f"{'CHECK' if args.check else 'BUILD'} _viz-shared → {len(paths)} template(s)\n")
    all_ok = True
    for tpl in paths:
        ok, issues = build_template(tpl, css_block, viz_js, write=write)
        flag = "✓" if ok else "✗"
        print(f"  {flag} {tpl.relative_to(SKILLS)}")
        for msg in issues:
            print(f"      → {msg}")
        if not ok:
            all_ok = False

    print()
    if args.check:
        print("Check-only mode (không ghi file).")
    elif all_ok:
        print("✅ Build xong. Templates giờ self-contained (single-file).")
    else:
        print("❌ Có lỗi — xem issues trên.")
    sys.exit(0 if all_ok else 1)


if __name__ == "__main__":
    main()
