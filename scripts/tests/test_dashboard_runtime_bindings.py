#!/usr/bin/env python3
"""Regression tĩnh cho các binding dashboard dễ chết im lặng.

Không gọi mạng. Các kiểm tra này khóa bốn lỗi đã từng xuất hiện trên bản FPT:
canvas CFO không được khởi tạo, peer chỉ có chủ thể, MA truyền scalar thay vì
series và Risk Matrix bị hạ thành danh sách văn bản.
"""
import ast
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
BUILDER = (ROOT / "scripts" / "build_report.py").read_text()
TEMPLATE = (ROOT / "vn-research-dashboard" / "assets" / "dashboard_template.html").read_text()


def _visible_template():
    """Bỏ phần TOKENS TO FILL/comment hướng dẫn khỏi contract runtime."""
    return re.sub(r"<!--.*?-->", "", TEMPLATE, flags=re.DOTALL)


def _canvas_ids(text):
    return set(re.findall(r"CANVAS\(['\"]([^'\"]+)", text))


def _chart_init_ids():
    # Hỗ trợ cả new Chart($('id')) và biểu thức fallback id1 || id2.
    ids = set(re.findall(r"new Chart\([^\n]*?\$\('([^']+)'", TEMPLATE))
    if "$('chartBSDt2') || $('chartReturns')" in TEMPLATE:
        ids.add("chartReturns")
    return ids


def _data_block():
    start = BUILDER.index("DATA={")
    end = BUILDER.index("json.dump(DATA", start)
    return BUILDER[start:end]


def _subs_keys():
    # subs literal trong render; chỉ lấy key đứng trước dấu ':' để tránh token
    # xuất hiện trong các chuỗi nội dung.
    m = re.search(r"\bsubs\s*=\s*\{(.*?)\n\s*tmpl", BUILDER, re.DOTALL)
    assert m, "render() phải có bảng thay token subs"
    return set(re.findall(r"['\"]([A-Z][A-Z0-9_]+)['\"]\s*:", m.group(1)))


def test_profit_quality_chart_is_bound():
    assert "new Chart($('chartEQ')" in TEMPLATE
    assert "data:DATA.cfo" in TEMPLATE
    assert "data:DATA.netIncome" in TEMPLATE


def test_technical_chart_uses_series_not_scalar():
    for key in ("techMA10Series", "techMA20Series", "techMA50Series"):
        assert key in BUILDER
        assert f"DATA.{key}" in TEMPLATE
    assert "yMin:DATA.techMA50, yMax:DATA.techMA50" in TEMPLATE
    assert "yMin:DATA.techMA50val" not in TEMPLATE


def test_peer_fetch_uses_fundamental_ratios_and_multi_candidate_pool():
    assert "Fundamental().equity(ps).ratio" in BUILDER
    assert "RT_VALUE_PE" in BUILDER and "RT_VALUE_PB" in BUILDER
    assert "tolist()[:12]" in BUILDER
    assert "if len(out) == 3" in BUILDER
    assert "if len(valid_peers) >= 2" in BUILDER


def test_risk_section_is_a_real_matrix():
    assert '<table class="risk-table">' in BUILDER
    assert "Nhóm rủi ro" in BUILDER
    assert "Chất lượng dòng tiền" in BUILDER
    assert "pill pill-" in BUILDER


def test_placeholder_producer_consumer_parity():
    """Mọi placeholder visible phải có producer; không để token chết trong HTML."""
    consumers = set(re.findall(r"\{\{([A-Z][A-Z0-9_]+)\}\}", _visible_template()))
    producers = _subs_keys()
    assert consumers <= producers, sorted(consumers - producers)
    # News từng được producer nhưng không có section consumer.
    assert "SEC_NEWS_HTML" in producers
    assert "{{SEC_NEWS_HTML}}" in _visible_template()


def test_canvas_has_exactly_one_runtime_binding_with_conditional_guard():
    """Canvas tùy chọn có guard; canvas bắt buộc phải có đúng một init Chart."""
    canvas = _canvas_ids(BUILDER)
    init = _chart_init_ids()
    assert canvas <= init, f"canvas không có Chart init: {sorted(canvas - init)}"
    # Không tạo hai Chart instance cho cùng canvas; fallback chartBSDt2/chartReturns
    # được tính là một binding hợp lệ.
    counts = {cid: len(re.findall(rf"new Chart\([^\n]*\$\('{re.escape(cid)}'", TEMPLATE)) for cid in canvas}
    assert all(n == 1 for n in counts.values()), counts


def test_data_contract_declares_required_keys_and_series_shapes():
    required = {
        "years", "revenue", "netIncome", "cfo", "eps", "roe", "equity", "liabilities",
        "peers", "techWeeks", "techPrice", "techRSI",
        "techMA10Series", "techMA20Series", "techMA50Series",
        "returnIndex", "macd", "macd_signal", "bb_lower", "bb_upper", "segMix",
        "ddMonths", "ddValues", "distBins", "distCounts",
    }
    data_keys = set(re.findall(
        r"(?:['\"]([A-Za-z][A-Za-z0-9_]*)['\"]|\b([A-Za-z][A-Za-z0-9_]*))\s*:",
        _data_block(),
    ))
    data_keys = {a or b for a, b in data_keys}
    assert required <= data_keys, sorted(required - data_keys)
    for key in ("years", "netIncome", "cfo", "liabilities", "techWeeks", "techPrice", "techRSI",
                "techMA10Series", "techMA20Series", "techMA50Series", "returnIndex"):
        m = re.search(rf"['\"]?{key}['\"]?\s*:\s*([^,\n]+)", _data_block())
        assert m, key
        # Series may be a named list or a list comprehension, never a scalar.
        expr = m.group(1).strip()
        assert expr.startswith(("[", "years", "tech[")), (key, expr)
    # Numeric daily MA fields are scalar display metrics only, never chart series.
    assert not re.search(r"data\s*:\s*DATA\.techMA(?:10|20|50)(?:\b|[,}])", TEMPLATE)


def test_render_does_not_hide_missing_numeric_data_with_zero_fallback():
    body = BUILDER[BUILDER.index("def render("):]
    body = body[:body.index("\ndef ", 1)] if "\ndef " in body[1:] else body
    assert not re.search(r"D\.get\([^\n)]*,\s*0\s*\)", body)


def test_canvas_labels_and_units_are_semantic():
    assert "aria-label" in BUILDER
    assert "Chất lượng lợi nhuận CFO vs LNST" in BUILDER
    assert "So sánh P/E và P/B cùng ngành" in BUILDER
    assert "Giá và MA 52 tuần" in BUILDER
    assert "tỷ VND" in TEMPLATE
    assert "P/B (×)" in TEMPLATE


def test_year_and_capital_tokens_are_dynamic():
    visible = _visible_template()
    assert "{{CAPITAL_LENS_AMOUNT}}" in visible
    assert "{{PRICE_DATE}}" in visible
    assert "years[-1]" in BUILDER
    # Không đóng đinh năm hiện tại trong các tiêu đề/nhãn 5 năm.
    assert not re.search(r"(?:5 năm|năm)\s+2025", visible, re.IGNORECASE)


def test_reader_copy_has_no_internal_controller_labels():
    visible = _visible_template()
    for internal in ("Mode ACTIVE", "Mode PROFILE", "TIMING/VERDICT", "NON-ADVICE",
                     "Investment Evidence Pack", "Balance Sheet, Capex & Free Cash Flow"):
        assert internal not in visible
    assert "{{BS_SECTION_TITLE}}" in visible
    assert "Tín hiệu dữ liệu" in visible


def test_builder_generated_reader_copy_has_no_internal_product_labels():
    # Regression vòng 6: chỉ soi template đã bỏ lọt hero/meta do builder sinh.
    render_body = BUILDER[BUILDER.index("def render("):]
    forbidden = (
        "Investment Evidence Pack", "investment evidence pack", "Evidence Pack",
        "Mode ACTIVE", "Mode PROFILE", "TIMING/VERDICT", "NON-ADVICE",
        "by evidence pack",
    )
    for label in forbidden:
        assert label not in render_body
    for controller in ("cross-check theo bẫy", "nhãn kỹ thuật máy đọc",
                       "Profile kỹ thuật", "Max drawdown", "weekly returns",
                       "Sắc thái máy đọc", "52-week High"):
        assert controller not in render_body


def test_typography_uses_one_offline_safe_family_in_html_and_charts():
    assert "'Inter'" not in TEMPLATE
    assert "'JetBrains Mono'" not in TEMPLATE
    assert "--font-mono:var(--font-sans)" in TEMPLATE
    assert "Chart.defaults.font.family = getComputedStyle(document.body).fontFamily" in TEMPLATE
    assert "font-variant-numeric:tabular-nums" in TEMPLATE


def test_insight_sections_use_the_same_typography_component():
    assert ".insight h3{font-family:inherit" in TEMPLATE
    assert ".insight p{font-family:inherit" in TEMPLATE
    for number in (15, 16, 17):
        assert f'<span class="num">{number}</span>' in TEMPLATE
    assert "★ Insight" not in TEMPLATE
    assert "★ Insight" not in BUILDER


def test_news_has_a_visible_section_and_chart_semantics_are_not_stale():
    visible = _visible_template()
    assert 'id="sec-news"' in visible
    assert "{{SEC_NEWS_HTML}}" in visible
    assert "Dòng tiền hoạt động (tỷ VND)" in TEMPLATE
    assert "Nợ phải trả" in TEMPLATE
    assert "EPS (VND/cp)" in TEMPLATE
    assert "Lợi suất tích lũy" in TEMPLATE
    for stale in ("Project Value", "Debt vs Cash", "Dividend + Buyback"):
        assert stale not in visible


def test_section_21_is_real_two_sided_synthesis_not_product_metadata():
    assert '<div class="thesis-grid">' in BUILDER
    assert "Yếu tố hỗ trợ" in BUILDER
    assert "Yếu tố cần thận trọng" in BUILDER
    assert "Kết luận cân bằng" in BUILDER
    analyst_match = re.search(r"analyst\s*=f'''(.*?)'''", BUILDER, re.DOTALL)
    assert analyst_match
    analyst = analyst_match.group(1)
    for metric in ("rev_last", "npat_last", "roe_last", "max_dd", "verdict_label"):
        assert metric in analyst
    assert "Báo cáo được biên soạn bởi ZCode" not in analyst


def test_template_has_landmarks_keyboard_focus_and_reduced_motion():
    visible = _visible_template()
    assert 'class="skip-link" href="#main-content"' in visible
    assert '<main class="container" id="main-content">' in visible
    assert re.search(r'<nav\b[^>]*class="topnav"[^>]*aria-label=', visible)
    assert 'aria-labelledby="toc-heading"' in visible
    assert ':focus-visible' in TEMPLATE
    assert '@media (prefers-reduced-motion: reduce)' in TEMPLATE
    assert "REDUCED_MOTION" in TEMPLATE


def test_template_does_not_regrow_dead_ui_skeletons_or_duplicate_disclaimer():
    # Các skeleton này từng tồn tại nhưng không có producer trong builder.
    for dead_class in (
        "vc-layer", "barrier-table", "dep-matrix", "tech-score-card",
        "signal-grid", "analyst-table", "consensus-grid", "candlestick",
    ):
        assert dead_class not in TEMPLATE
    assert TEMPLATE.count(".disclaimer{") == 1
    assert ".footer-disclaimer{" in TEMPLATE
    assert ".thesis-grid>:is(div,article)" in TEMPLATE


def test_builder_centralizes_provenance_and_adds_table_semantics():
    assert "def clean_reader_provenance" in BUILDER
    assert "tmpl=clean_reader_provenance(tmpl)" in BUILDER
    assert 'scope="col"' in BUILDER
    assert 'aria-label="Bảng dữ liệu phân tích"' in BUILDER
    # Không quay lại cơ chế rải nhãn nguồn ẩn cạnh từng con số.
    assert "source_labels =" not in BUILDER


def test_provenance_cleaner_never_rewrites_css_selectors_or_pseudo_elements():
    tree = ast.parse(BUILDER)
    fn = next(node for node in tree.body
              if isinstance(node, ast.FunctionDef) and node.name == "clean_reader_provenance")
    namespace = {"re": re}
    exec(compile(ast.Module(body=[fn], type_ignores=[]), "<cleaner>", "exec"), namespace)
    sample = '''<style>.section-title .num{color:red}.x::before{content:"."}</style>
<body><p>Theo BCTC kiểm toán năm 2025: doanh thu 10 tỷ.</p>
<p>Trạng thái (không phải khuyến nghị — theo vnstock Quote).</p>
<section id="sec-source"><p>Nguồn VCI</p></section></body>'''
    cleaned = namespace["clean_reader_provenance"](sample)
    assert ".section-title .num" in cleaned
    assert ".x::before" in cleaned
    assert ".section-title.num" not in cleaned
    assert ".x:before" not in cleaned
    assert "theo vnstock Quote" not in cleaned.split('<section id="sec-source"')[0]
    assert "Nguồn VCI" in cleaned


def test_runtime_verifier_checks_rendered_news_peer_and_dom_contract():
    verifier = (ROOT / "scripts" / "independent_verifier.py").read_text()
    runtime = verifier[verifier.index("def verify_runtime_render"):]
    runtime = runtime[:runtime.index("\ndef ", 1)]
    for contract in (
        'news_digest.json', 'sec-news', 'chartPeerScatter',
        'main-content', 'skip-link', "scope='col'", 'placeholder chưa render',
        '.section-title .num', '.topnav-inner::-webkit-scrollbar',
        'CSS selector bị minify sai',
    ):
        assert contract in runtime


def test_req029_describes_centralized_provenance_not_inline_labels():
    requirements = (ROOT / "requirements.yaml").read_text()
    req029 = requirements[requirements.index("- id: REQ-029"):]
    req029 = req029[:req029.index("\n- id: REQ-030")]
    assert "Provenance tập trung" in req029
    assert "Không rải nhãn nguồn/controller" in req029
    assert "sec-source" in req029


def test_dynamic_empty_states_exist_for_optional_data():
    assert "Chưa đủ ít nhất hai doanh nghiệp" in BUILDER
    assert "Không có tin mới trong 30 ngày" in BUILDER
    assert "Chưa có dữ liệu tin tức khả dụng" in BUILDER
    assert "không suy diễn sắc thái tin khi thiếu dữ liệu" in BUILDER
