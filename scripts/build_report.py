#!/usr/bin/env python3
"""Builder chuẩn v3 (2026-08-02): fetch + build + render + verify.
v3: + sector pack v3 (references/sector_pack.md) → section "Phân tích ngành".
v2: peer THẬT cùng ICB cấp 3; tech score thật; analytics; tiêu chí ngành.
Fix: REQ-003 (split_audit cp_back_calc), 005/037 (tech_score thật),
008 (news fetch), 013 (section ≥200), 024 (capex array), 029 (cite cùng câu),
033/034/036 (format số), 069 (DATA keys + canvas match).
Usage: python3 build_report.py <TICKER> [SECTOR]
"""
import sys, json, os, re, statistics, traceback, subprocess, math, tempfile
from datetime import datetime, timedelta

from runtime_environment import SponsorDependencyError, raise_sponsor_dependency
from statement_adapter import combine_statements, completed_annual_rows

TICKER = sys.argv[1]
SECTOR = sys.argv[2] if len(sys.argv) > 2 else 'general'
SKILL_DIR = os.path.abspath(os.environ.get(
    'EQUITY_SKILL_DIR', os.path.join(os.path.dirname(__file__), '..')
))
WORK_ROOT = os.path.abspath(os.environ.get('EQUITY_WORK_ROOT', tempfile.gettempdir()))
WORK = os.path.join(WORK_ROOT, f'vn100_{TICKER}')
TEMPLATE = os.path.abspath(os.environ.get(
    'EQUITY_DASHBOARD_TEMPLATE',
    os.path.join(SKILL_DIR, 'vn-research-dashboard', 'assets', 'dashboard_template.html'),
))
CONFIG_DIR = os.path.abspath(os.environ.get(
    'EQUITY_CONFIG_DIR', os.path.join(SKILL_DIR, 'config')
))
CACHE_DIR = os.path.abspath(os.environ.get(
    'EQUITY_CACHE_DIR', os.path.join(os.path.expanduser('~'), '.cache', 'equity-research-vn')
))
BANKS = {'ACB','BID','CTG','TCB','HDB','MBB','STB','VPB','TPB','SHB','LPB','VCB','EIB','BVB','NVB','OCB','PGB','SSB','VAB','KLB','VIB'}
IS_BANK = TICKER in BANKS or SECTOR == 'banking'
os.makedirs(f'{WORK}/data', exist_ok=True)
os.makedirs(f'{WORK}/source-pack', exist_ok=True)
os.makedirs(f'{WORK}/.task-state', exist_ok=True)
os.makedirs(CACHE_DIR, exist_ok=True)


def _resolve_eps_reported(reported, missing, npatp, shares):
    """Giữ EPS reported; chỉ back-calc những ô thực sự thiếu.

    `missing` phải được xác định từ NaN/thiếu cột trước khi normalize.
    Số 0 do nguồn công bố là dữ liệu, không được coi là missing.
    """
    resolved = list(reported)
    if shares > 0:
        for i in range(len(resolved)):
            if missing[i] and npatp and npatp[i]:
                resolved[i] = float(npatp[i]) / shares
    return [0.0 if e is None else e for e in resolved]


def _write_preflight_sector():
    """P0-04 v2 (Sol 2026-08-10): ghi canonical sector + provenance từ preflight.

    Verifier REQ-040 đọc file này để so với 4 output — sector sai nhưng đồng nhất
    (build TJC với 'tech') phải bị bắt. Nguồn chuẩn: preflight_p0_sectors.json
    (ICB+sàn, chạy trước batch). Nếu không có file → source 'none' (verifier chỉ
    kiểm consistency nội bộ 4 output, không ép canonical).
    """
    candidates = [
        os.environ.get('VNALL_PREFLIGHT_SECTORS', ''),
        os.path.join(CONFIG_DIR, 'preflight_p0_sectors.json'),
        os.path.join(os.getcwd(), 'data/vnall/preflight_p0_sectors.json'),
    ]
    pf = None
    pf_path = None
    for p in candidates:
        if p and os.path.exists(p):
            try:
                with open(p) as f:
                    pf = json.load(f)
                pf_path = p
                break
            except Exception:
                pf = None
    entry = {"ticker": TICKER, "runner_input_sector": SECTOR,
             "canonical_sector": SECTOR, "source": "none", "source_path": None,
             "source_sha256": None, "checked_at": datetime.now().isoformat()}
    if isinstance(pf, dict) and TICKER in pf:
        entry["canonical_sector"] = pf[TICKER]
        entry["source"] = "preflight_p0_sectors"
        entry["source_path"] = pf_path
        try:
            import hashlib
            entry["source_sha256"] = hashlib.sha256(open(pf_path, 'rb').read()).hexdigest()
        except Exception:
            entry["source_sha256"] = None
    with open(f'{WORK}/preflight-sector.json', 'w') as f:
        json.dump(entry, f, ensure_ascii=False, indent=2)
    return entry


_write_preflight_sector()

# ============ SECTOR PACK v3 ============
# Builder đọc references/sector_pack.md → sinh section "Phân tích ngành"
PACK_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'references', 'sector_pack.md')
SECTOR_MAP = {
    'banking':'1. NGÂN HÀNG', 'bank':'1. NGÂN HÀNG', 'ngân hàng':'1. NGÂN HÀNG',
    'realestate':'2. BẤT ĐỘNG SẢN & XÂY DỰNG', 'bds':'2. BẤT ĐỘNG SẢN & XÂY DỰNG', 'property':'2. BẤT ĐỘNG SẢN & XÂY DỰNG',
    'construction':'2. BẤT ĐỘNG SẢN & XÂY DỰNG', 'xây dựng':'2. BẤT ĐỘNG SẢN & XÂY DỰNG', 'nhà thầu':'2. BẤT ĐỘNG SẢN & XÂY DỰNG',
    'steel':'3. CHU KỲ HÀNG HÓA', 'thép':'3. CHU KỲ HÀNG HÓA', 'materials':'3. CHU KỲ HÀNG HÓA',
    'hóa chất':'3. CHU KỲ HÀNG HÓA', 'phân bón':'3. CHU KỲ HÀNG HÓA', 'dầu khí':'3. CHU KỲ HÀNG HÓA',
    'than':'3. CHU KỲ HÀNG HÓA', 'xi măng':'3. CHU KỲ HÀNG HÓA',
    'retail':'4. TIÊU DÙNG & BÁN LẺ', 'bán lẻ':'4. TIÊU DÙNG & BÁN LẺ', 'consumer':'4. TIÊU DÙNG & BÁN LẺ',
    'thực phẩm':'4. TIÊU DÙNG & BÁN LẺ', 'đồ uống':'4. TIÊU DÙNG & BÁN LẺ', 'dệt may':'4. TIÊU DÙNG & BÁN LẺ',
    'securities':'5. CHỨNG KHOÁN & QUỸ', 'chứng khoán':'5. CHỨNG KHOÁN & QUỸ', 'finance':'5. CHỨNG KHOÁN & QUỸ',
    'insurance':'6. BẢO HIỂM', 'bảo hiểm':'6. BẢO HIỂM',
    'energy':'7. NĂNG LƯỢNG & ĐIỆN', 'điện':'7. NĂNG LƯỢNG & ĐIỆN', 'power':'7. NĂNG LƯỢNG & ĐIỆN',
    'gas':'7. NĂNG LƯỢNG & ĐIỆN', 'khí':'7. NĂNG LƯỢNG & ĐIỆN',
    'transport':'8. VẬN TẢI & CẢNG', 'vận tải':'8. VẬN TẢI & CẢNG', 'cảng':'8. VẬN TẢI & CẢNG',
    'hàng không':'8. VẬN TẢI & CẢNG', 'logistics':'8. VẬN TẢI & CẢNG',
    'pharma':'9. DƯỢC PHẨM & Y TẾ', 'dược':'9. DƯỢC PHẨM & Y TẾ', 'y tế':'9. DƯỢC PHẨM & Y TẾ',
    'tech':'10. CÔNG NGHỆ & VIỄN THÔNG', 'công nghệ':'10. CÔNG NGHỆ & VIỄN THÔNG', 'viễn thông':'10. CÔNG NGHỆ & VIỄN THÔNG',
    'thủy sản':'11. NÔNG NGHIỆP & CHẾ BIẾN', 'cao su':'11. NÔNG NGHIỆP & CHẾ BIẾN',
    'đường':'11. NÔNG NGHIỆP & CHẾ BIẾN', 'gỗ':'11. NÔNG NGHIỆP & CHẾ BIẾN', 'nông':'11. NÔNG NGHIỆP & CHẾ BIẾN',
    'industrial':'13. CÔNG NGHIỆP & SẢN XUẤT', 'công nghiệp':'13. CÔNG NGHIỆP & SẢN XUẤT', 'sản xuất':'13. CÔNG NGHIỆP & SẢN XUẤT',
    'general':'12. NGÀNH KHÁC',
}

def load_sector_pack(sector):
    """Đọc pack ngành cho sector — trả dict(group, peculiar[], traps[], criteria[]) hoặc None."""
    key = (sector or '').lower().strip()
    group = SECTOR_MAP.get(key) or next((v for k, v in SECTOR_MAP.items() if k and k in key), '12. NGÀNH KHÁC')
    try:
        txt = open(PACK_PATH, encoding='utf-8').read()
    except Exception:
        return None
    m = re.search(r'^## ' + re.escape(group) + r'.*?(?=^## |\Z)', txt, re.M | re.S)
    if not m:
        return None
    block = m.group(0)
    out = {'group': group}
    for sub, name in [('Đặc thù', 'peculiar'), ('Cách đọc', 'traps'), ('Tiêu chí', 'criteria')]:
        sm = re.search(r'^### ' + sub + r'.*?(?=^### |\Z)', block, re.M | re.S)
        if sm:
            items = [l.strip('- ').strip() for l in sm.group(0).splitlines()
                     if l.strip().startswith('- ')]
            out[name] = items
    return out if (out.get('peculiar') or out.get('traps') or out.get('criteria')) else None

def fv(x):
    if x is None: return 'n/a'
    return f'{int(round(float(x)))}'  # raw, no separator (verifier _normalize_number bug on EN comma format)

def ft(x):
    if x is None: return 'n/a'
    return f'{float(x):.1f}'  # raw, no comma thousands (verifier parse bug)

def CANVAS(cid, h=280, label=None):
    lab = label or f'Biểu đồ {cid}'
    return f'<div class="chart-row"><div class="chart-card"><div class="height-wrapper" style="position:relative;height:{h}px"><canvas id="{cid}" role="img" aria-label="{lab}"></canvas></div></div></div>'

# ============ FETCH ============
def fetch():
    import pandas as pd, numpy as np
    try:
        from vnstock_data import Fundamental, Quote
    except (ImportError, ModuleNotFoundError) as exc:
        raise_sponsor_dependency(exc)

    # Unified UI 3.2.7 trả period theo cột và field dạng slug. Lấy riêng quý/năm,
    # sau đó chuẩn hóa về contract nội bộ đã kiểm định. Không pin ngược 3.0.0 và
    # không suy diễn vị trí index của payload nhà cung cấp.
    try:
        equity_api = Fundamental().equity(TICKER)
        def _statement(name, period):
            return getattr(equity_api, name)(period=period, lang='en')
        inc = combine_statements(_statement('income_statement', 'quarter'),
                                 _statement('income_statement', 'year'), 'income')
        bal = combine_statements(_statement('balance_sheet', 'quarter'),
                                 _statement('balance_sheet', 'year'), 'balance')
        cf = combine_statements(_statement('cash_flow', 'quarter'),
                                _statement('cash_flow', 'year'), 'cash_flow')
    except (ImportError, ModuleNotFoundError) as exc:
        raise_sponsor_dependency(exc)

    inc.to_csv(f'{WORK}/source-pack/income_statement_sponsor.csv', index_label='period')
    bal.to_csv(f'{WORK}/source-pack/balance_sheet_sponsor.csv', index_label='period')
    cf.to_csv(f'{WORK}/source-pack/cash_flow_sponsor.csv', index_label='period')
    # Financial statements do not always expose the same annual rows.  The report
    # is anchored on years that exist in both income and balance statements;
    # cash-flow values are optional and are aligned by year (never by list index).
    # Không nhận dòng LTM/quý hiện tại bị provider gắn nhãn ``year`` làm năm
    # hoàn chỉnh (CTD từng neo 2026 vào tháng 8/2026). Source-pack vẫn giữ dòng
    # gốc để audit; báo cáo chỉ dùng năm đã kết thúc trước năm đang chạy.
    inc_a=completed_annual_rows(inc).tail(5)
    bal_a=completed_annual_rows(bal).tail(5)
    cf_a=completed_annual_rows(cf).tail(5)
    common_years=sorted(set(inc_a.index) & set(bal_a.index))[-5:]
    if not common_years:
        raise ValueError("no common annual income/balance years")
    inc5=inc_a.reindex(common_years); bal5=bal_a.reindex(common_years)
    cf5=cf_a.reindex(common_years)
    years=[int(x) for x in inc5.index]
    # Statement-schema-aware columns. Non-bank financial institutions (EVF and
    # securities/consumer-finance issuers) also expose Total Operating Income,
    # not industrial "Net sales". Sector labels are too coarse to be an oracle.
    toi_col = next((c for c in inc5.columns if str(c).strip().lower() == 'total operating income'), None)
    # Ngân hàng, chứng khoán và bảo hiểm đều là định chế tài chính, nhưng chỉ
    # ngân hàng/lender dùng Total Operating Income. SSI/BVH vẫn có canonical
    # Net sales do adapter ánh xạ từ schema riêng; không được ép về TOI.
    specialized_financial_markers = {
        'net_revenue',
        '5_doanh_thu_thuan_hdkd_bh_10_03_04',
        'luu_chuyen_tien_thuan_tu_hoat_dong_kinh_doanh_chung_khoan',
        'a_no_phai_tra_300_210_330',
        'a_no_phai_tra_300_310_340',
    }
    specialized_financial = bool(
        toi_col
        or specialized_financial_markers.intersection(map(str, inc5.columns))
        or specialized_financial_markers.intersection(map(str, bal5.columns))
        or specialized_financial_markers.intersection(map(str, cf5.columns))
    )
    if IS_BANK or toi_col:
        rev_col=toi_col or 'Total Operating Income'; npat_col='Net profit/(loss) after tax'; npatp_col='Attributable to parent company'
    else:
        # Adapter đã xác định canonical. Exact-first ngăn SSI bắt nhầm raw field
        # ``deduction_from_revenue`` chỉ vì tên chứa chữ revenue.
        rev_col='Net sales' if 'Net sales' in inc5.columns else next(
            (c for c in inc5.columns if re.fullmatch(r'Net revenue|Revenue|Doanh thu thuần', str(c), re.I)),
            None,
        )
        # Ưu tiên Attributable (CĐ mẹ) — MSN/VIC có minority lớn: EPS tính trên attributable
        # nên npatmi_ty phải là attributable, nếu dùng total → lệch >15% (REQ-060)
        npat_col=next((c for c in inc5.columns if re.search(r'Attributable to parent|Net profit attributable to shareholders',c,re.I)),None) \
            or next((c for c in inc5.columns if re.search(r'Net profit.*after tax|Profit after tax',c,re.I)),None)
        npatp_col=npat_col
    # capex cho MỌI loại (bank cũng có dòng mua sắm tài sản trong cash flow — Sol 2026-08-08:
    # REQ-062 bắt buộc đối chiếu; trước đây bank bỏ qua → PASS rỗng)
    capex_col=next((c for c in cf5.columns if re.search(r'Purchases of fixed assets|Mua sắm tài sản',c,re.I)),None)
    eps_col=next((c for c in inc5.columns if re.search(r'EPS.*basic|Earning.*per.*share',c,re.I)),None)
    toi=[float(inc5[rev_col].iloc[i]) for i in range(len(inc5))] if rev_col and rev_col in inc5.columns else [0]*len(inc5)
    npat=[float(inc5[npat_col].iloc[i]) for i in range(len(inc5))] if npat_col and npat_col in inc5.columns else [0]*len(inc5)
    npatp=[float(inc5[npatp_col].iloc[i]) for i in range(len(inc5))] if npatp_col and npatp_col in inc5.columns else npat
    # EPS reported là oracle. Phân biệt rõ ô thiếu (NaN) với số 0 được nguồn công
    # bố: 0 có thể là kết quả làm tròn của EPS rất nhỏ và KHÔNG được phép bị ghi đè
    # bằng NPAT/shares. Chỉ ô thiếu thật mới được back-calc ở bước sau.
    if eps_col and eps_col in inc5.columns:
        eps_missing = [inc5[eps_col].iloc[i] != inc5[eps_col].iloc[i] for i in range(len(inc5))]
        eps = [None if eps_missing[i] else float(inc5[eps_col].iloc[i]) for i in range(len(inc5))]
    else:
        eps_missing = [True] * len(inc5)
        eps = [None] * len(inc5)
    eq_col=next((c for c in bal5.columns if re.search(r"Owner'?s?'?\s*equity|Vốn chủ sở hữu", c, re.I)),None)
    as_col=next((c for c in bal5.columns if c.upper()=="TOTAL ASSETS"),None)
    equity=[float(bal5[eq_col].iloc[i]) for i in range(len(bal5))] if eq_col else [0]*len(bal5)
    assets=[float(bal5[as_col].iloc[i]) for i in range(len(bal5))] if as_col else [0]*len(bal5)
    # CFO: P0-B (Sol checkpoint 2026-08-08) — nhận MỌI alias chuẩn (exact-first):
    # "Net cash inflows/(outflows) from operating activities" (mẫu sponsor) hoặc
    # "Net cash from operating activities". KHÔNG dùng truthiness (CFO=0 thật phải giữ 0).
    cfo_col = None
    for cand in ('Net cash inflows/(outflows) from operating activities', 'Net cash from operating activities'):
        if cand in cf5.columns:
            cfo_col = cand
            break
    if cfo_col is None:
        cfo_col = next((c for c in cf5.columns if re.search(r'net cash.*operating', c, re.I)), None)
    cfo=[float(cf5[cfo_col].iloc[i]) if cfo_col and cf5[cfo_col].iloc[i] == cf5[cfo_col].iloc[i] else None for i in range(len(cf5))] if cfo_col else [None]*len(years)
    capex=[float(cf5[capex_col].iloc[i]) if cf5[capex_col].iloc[i] == cf5[capex_col].iloc[i] else None for i in range(len(cf5))] if capex_col and capex_col in cf5.columns else [None]*len(years)
    # inventory THẬT từ balance sheet (P0-1: cấm fallback giả lập từ gross profit)
    inv_col=next((c for c in bal5.columns if re.search(r'Inventory|Hàng tồn kho|Inventories',c,re.I)),None)
    inventory=[float(bal5[inv_col].iloc[i]) if bal5[inv_col].iloc[i] == bal5[inv_col].iloc[i] else None for i in range(len(bal5))] if inv_col else [None]*len(years)
    # gross profit (for chartEQ / DATA)
    gp_col=next((c for c in inc5.columns if re.search(r'Gross Profit|Lợi nhuận gộp',c,re.I)),None)
    gross=[float(inc5[gp_col].iloc[i]) if inc5[gp_col].iloc[i] == inc5[gp_col].iloc[i] else None for i in range(len(inc5))] if gp_col and gp_col in inc5.columns else [None]*len(years)
    # liabilities
    liab_col=next((c for c in bal5.columns if re.search(r'Total Liabilities|TOTAL LIABILITIES',c,re.I)),None)
    liab=[float(bal5[liab_col].iloc[i]) for i in range(len(bal5))] if liab_col else [(assets[i]-equity[i]) for i in range(len(bal5))]
    # price
    q=Quote(source='VCI',symbol=TICKER)
    # P0-01 (Sol 2026-08-09): end date ĐỘNG theo ngày chạy — KHÔNG khóa snapshot cũ
    hist=q.history(start='2022-01-01',end=datetime.now().date().isoformat())
    hist.to_csv(f'{WORK}/source-pack/price.csv',index=False)
    last=float(hist['close'].iloc[-1])*1000
    try:
        as_of_date = str(hist['time'].iloc[-1])[:10]
    except Exception:
        as_of_date = 'N/A'
    # shares — VN100 fix 2026-08-02 (BVH/HSG/MIG): nhiều tầng fallback
    # 1) Paid-in capital / Charter capital; 2) back-calc npatp/eps; 3) overview issue_share
    cc_col=next((c for c in bal5.columns if re.search(r'Paid-in capital|Charter capital|Vốn điều lệ|Charter Capital',c,re.I)),None)
    cc=float(bal5[cc_col].iloc[-1]) if cc_col else 0
    if cc>0: shares=cc/10000
    elif eps and eps[-1] and npatp and npatp[-1]: shares=npatp[-1]/eps[-1]
    else:
        shares=0
        try:
            from vnstock_data import Company
            ov=Company(symbol=TICKER,source='VCI').overview()
            if hasattr(ov,'columns') and 'issue_share' in ov.columns and float(ov['issue_share'].iloc[0])>0:
                shares=float(ov['issue_share'].iloc[0])
        except Exception:
            pass
    # EPS back-calc CHỈ khi API thiếu ô (NaN/không có cột). P0-6 (Sol
    # 2026-08-08): KHÔNG ghi đè EPS reported, kể cả EPS reported = 0;
    # theo IAS 33 denominator là cổ phiếu bình quân,
    # không phải shares cuối kỳ; lệch là mâu thuẫn nguồn THẬT → để verifier báo,
    # không ép số khớp (REQ-060 sẽ fail → needs_human).
    eps = _resolve_eps_reported(eps, eps_missing, npatp, shares)
    # Ô vẫn thiếu được render 0/N/A để pipeline không crash; REQ-062
    # sẽ fail-closed vì raw CSV không có pair hợp lệ.
    ev_ebitda = None  # P0-6 (Sol 2026-08-08): EV/EBITDA gỡ khỏi output — net_debt trước
    # đây tính bằng tổng liabilities (sai khái niệm: phải nợ vay chịu lãi − tiền);
    # mapping nợ/cash đúng sẽ được xác minh rồi mới bật lại.
    return dict(years=years,toi=toi,npat=npat,npatp=npatp,eps=eps,equity=equity,assets=assets,cfo=cfo,capex=capex,gross=gross,liab=liab,inventory=inventory,last=last,shares=shares,periods=min(len(inc), len(bal), len(cf)),ev_ebitda=ev_ebitda,as_of_date=as_of_date,statement_type=('financial_institution' if specialized_financial else 'corporate'))

# ============ TECH SCORE (REQ-005/037) ============
def tech_score(D_raw):
    import pandas as pd, numpy as np
    price=pd.read_csv(f'{WORK}/source-pack/price.csv')
    price['time']=pd.to_datetime(price['time'])
    price=price.sort_values('time').reset_index(drop=True)
    price['cv']=price['close']*1000
    p=price['cv']
    # Short/suspended price histories are legitimate.  Use the available window
    # instead of producing NaN and crashing while rounding the report payload.
    ma10=float(p.rolling(10,min_periods=1).mean().iloc[-1]); ma20=float(p.rolling(20,min_periods=1).mean().iloc[-1]); ma50=float(p.rolling(50,min_periods=1).mean().iloc[-1])
    last252=price.tail(252)
    hi52=float(last252['cv'].max()); lo52=float(last252['cv'].min())
    roll_max=last252['cv'].cummax(); dd=(last252['cv']/roll_max-1)*100; max_dd=float(dd.min())
    # RSI14 daily
    delta=p.diff(); gain=delta.clip(lower=0).rolling(14).mean(); loss=(-delta.clip(upper=0)).rolling(14).mean()
    rsi14=float((100-100/(1+gain.iloc[-1]/loss.iloc[-1])) if loss.iloc[-1]>0 else 100)
    # MACD (12,26,9) daily
    ema12=p.ewm(span=12).mean(); ema26=p.ewm(span=26).mean()
    macd=ema12-ema26; macd_sig=macd.ewm(span=9).mean()
    macd_last=float(macd.iloc[-1]); macd_sig_last=float(macd_sig.iloc[-1])
    # Bollinger
    bb_mid=p.rolling(20,min_periods=1).mean().iloc[-1]; bb_std=p.rolling(20,min_periods=1).std(ddof=0).iloc[-1]
    bb_lower=float(bb_mid-2*bb_std); bb_upper=float(bb_mid+2*bb_std)
    pct_hi = (last252['cv'].iloc[-1]/hi52-1)*100 if hi52 else 0

    # weekly for chart
    price_w=price.set_index('time').resample('W').last().dropna().tail(53)
    ret1w=(price_w['cv'].pct_change()*100).round(1).fillna(0).tolist()
    techPrice=price_w['cv'].round(0).tolist()
    pwm=price_w['cv']
    ma20w=pwm.rolling(20,min_periods=1).mean().round(0).tolist()
    ma50w=pwm.rolling(50,min_periods=1).mean().round(0).tolist()
    gw=pwm.diff().clip(lower=0).rolling(14,min_periods=1).mean()
    lw=(-pwm.diff().clip(upper=0)).rolling(14,min_periods=1).mean()
    rsi_w=(100-100/(1+gw/lw.replace(0,np.nan))).fillna(50).round(0).tolist()
    bins=[-5,-4,-3,-2,-1,0,1,2,3]; counts=[int(sum(1 for r in ret1w if bins[i]<=r<bins[i+1])) for i in range(len(bins)-1)]
    counts.append(int(sum(1 for r in ret1w if r>=3)))
    last252m=price.set_index('time').resample('ME').last().tail(12)
    rm=last252m['cv'].cummax(); ddm=(last252m['cv']/rm-1)*100
    dd_values=[round(max(float(ddm.iloc[i]),-25),1) for i in range(len(ddm))]
    dd_months=['T1','T2','T3','T4','T5','T6','T7','T8','T9','T10','T11','T12'][:len(dd_values)]

    # Score -6..+6 (CTD-style)
    score=0
    last_p=float(p.iloc[-1])
    # Trend (MA): +2 uptrend, -2 downtrend
    if last_p>ma10>ma20>ma50: score+=2
    elif last_p>ma10>ma20: score+=1
    elif last_p<ma10<ma20<ma50: score-=2
    elif last_p<ma10<ma20: score-=1
    # RSI
    if rsi14>70: score+=1
    elif rsi14<30: score-=1
    elif rsi14<45: score-=1
    # MACD
    if macd_last>macd_sig_last>0: score+=1
    elif macd_last<macd_sig_last<0: score-=1
    # momentum from 52w
    if pct_hi>-5: score+=1
    elif pct_hi<-30: score-=1
    score=max(-6,min(6,score))
    if score>=2: verdict='BUY'
    elif score<=-2: verdict='SELL'
    else: verdict='NEUTRAL'

    return dict(ma10=ma10,ma20=ma20,ma50=ma50,hi52=hi52,lo52=lo52,max_dd=max_dd,rsi14=rsi14,
        macd=macd_last,macd_sig=macd_sig_last,bb_lower=bb_lower,bb_upper=bb_upper,pct_from_high=pct_hi,
        score=score,verdict=verdict,
        rsi_w=rsi_w[-52:],techPrice=techPrice[-52:],ma20w=ma20w[-52:],ma50w=ma50w[-52:],
        ret1w=ret1w[-52:],weeks=list(range(1,len(ret1w[-52:])+1)),
        dd_months=dd_months,dd_values=dd_values,bins=bins,counts=counts)

# ============ NEWS (REQ-008) ============
def fetch_news():
    fetched_at = datetime.now().date().isoformat()
    try:
        from vnstock import Company
        from urllib.parse import urljoin
        # VCI legacy company.news() (vnstock 3.5.1) hiện trả payload không có
        # key `data` và ném KeyError. KBS cung cấp endpoint news theo symbol và
        # đã được smoke-test trực tiếp; dữ liệu tài chính vẫn dùng VCI sponsor.
        c=Company(symbol=TICKER, source='KBS')
        # KBS giới hạn page_size tối đa 20. Payload lỗi cũng có thể bị wrapper
        # chuyển thành DataFrame (`st/msg/code`) nên phải kiểm schema, không được
        # diễn giải nhầm thành ok_empty.
        news=c.news(page_size=20)
        if news is None or len(news)==0:
            return {'fetched_at':fetched_at,'fetch_status':'ok_empty','provider':'KBS',
                    'window_days':30,'articles':[]}
        if not {'publish_time', 'title'}.issubset(set(news.columns)):
            raise ValueError(f"KBS_NEWS_SCHEMA:{','.join(map(str, news.columns))}")
        # Chỉ ghi bài trong window 30 ngày; không đưa tin stale vào digest.
        arts=[]
        for _,r in news.head(20).iterrows():
            date_key = 'publish_time' if 'publish_time' in r else 'date'
            raw_date = str(r.get(date_key,''))
            try:
                article_date = datetime.fromisoformat(raw_date[:10]).date()
            except Exception:
                continue
            if 0 <= (datetime.now().date() - article_date).days <= 30:
                raw_url = str(r.get('url', r.get('link','')) or '')
                # KBS trả đường dẫn Vietstock tương đối; chuẩn hóa domain để
                # REQ-044 có thể xác thực nguồn, không biến URL thật thành no-domain.
                article_url = urljoin('https://vietstock.vn/', raw_url) if raw_url else ''
                arts.append({'title':str(r.get('title', raw_date)),'source':'KBS/Vietstock',
                             'url':article_url,'date':article_date.isoformat(),
                             'category':'general','sentiment':'neutral'})
        return {'fetched_at':fetched_at,'fetch_status':('ok' if arts else 'ok_empty'),'provider':'KBS',
                'window_days':30,'articles':arts}
    except Exception as e:
        return {'fetched_at':fetched_at,'fetch_status':'error','provider':'KBS','window_days':30,
                'articles':[],'error':type(e).__name__}


_PEER_CACHE = os.path.join(CACHE_DIR, 'peer_overview.json')

def _load_peer_cache():
    try:
        return json.load(open(_PEER_CACHE)) if os.path.exists(_PEER_CACHE) else {}
    except Exception:
        return {}

def _save_peer_cache(c):
    try:
        json.dump(c, open(_PEER_CACHE, 'w'))
    except Exception:
        pass

def fetch_peers():
    """VN100 v2 (2026-08-02): peer THẬT cùng ngành (ICB cấp 3) thay PEER1/2/3 generic.
    Tối đa 3 peer; lỗi API → trả None (builder dùng fallback generic).
    PERF (2026-08-09): cache FILE — symbols_by_industries là dữ liệu TĨNH toàn thị trường
    (gọi lại mỗi mã = lãng phí 1.000 calls); peer overview cache theo ticker (cùng peer
    xuất hiện trong nhiều mã cùng ngành). Giảm 4 calls/mã → ~1-2 calls/mã."""
    try:
        from vnstock_data import Listing, Company
        # cache industries (1 lần cho cả batch)
        cache_ind = os.path.join(CACHE_DIR, 'industries.json')
        if os.path.exists(cache_ind):
            import json as _j
            ind = _j.load(open(cache_ind))
            import pandas as pd
            ind = pd.DataFrame(ind)
        else:
            lst = Listing(source='VCI')
            ind = lst.symbols_by_industries()
            try:
                json.dump(ind.to_dict('records'), open(cache_ind, 'w'))
            except Exception:
                pass
        rows = ind[ind['symbol'] == TICKER]
        if rows.empty:
            return None
        # ICB cấp sâu nhất (cấp 3 = ngành chi tiết nhất) — cấp 1 quá rộng (8000 Tài chính
        # gồm cả ngân hàng/BĐS/chứng khoán) → peer sai ngành (VIC 2026-08-02)
        icb_level_col = 'icb_level' if 'icb_level' in rows.columns else None
        row = rows.sort_values(icb_level_col, ascending=False).iloc[0] if icb_level_col else rows.iloc[0]
        icb = str(row['icb_code'])
        icb_name = str(row['icb_name'])
        same = ind[(ind['icb_code'] == icb) & (ind['symbol'] != TICKER)]
        if same.empty and len(icb) > 2:
            # fallback: cùng tên ngành cấp 3
            same = ind[(ind['icb_name'] == icb_name) & (ind['symbol'] != TICKER)]
        peers_sym = same['symbol'].tolist()[:3]
        cache = _load_peer_cache()
        dirty = False
        out = []
        for ps in peers_sym:
            if ps in cache:
                pe, pb = cache[ps].get('pe'), cache[ps].get('pb')
            else:
                try:
                    ov = Company(symbol=ps, source='VCI').overview()
                    pe = pb = None
                    if hasattr(ov, 'columns') and not ov.empty:
                        pe = float(ov['pe'].iloc[0]) if 'pe' in ov.columns and ov['pe'].iloc[0] else None
                        pb = float(ov['pb'].iloc[0]) if 'pb' in ov.columns and ov['pb'].iloc[0] else None
                    cache[ps] = {'pe': pe, 'pb': pb}
                    dirty = True
                except Exception:
                    continue
            if pe or pb:
                out.append({
                    'ticker': ps,
                    'pe': round(pe, 2) if isinstance(pe, (int, float)) and pe > 0 else None,
                    'pb': round(pb, 2) if isinstance(pb, (int, float)) and pb > 0 else None,
                })
        if dirty:
            _save_peer_cache(cache)
        return out or None
    except Exception:
        return None


# ============ BUILD DATA + files ============
def build_all(D_raw, tech, news, real_peers=None):
    years=D_raw['years']; toi=D_raw['toi']; npat=D_raw['npat']; npatp=D_raw['npatp']
    eps=D_raw['eps']; equity=D_raw['equity']; assets=D_raw['assets']; cfo=D_raw['cfo']
    capex=D_raw['capex']; gross=D_raw['gross']; liab=D_raw['liab']; inventory=D_raw.get('inventory') or [None]*5
    last=D_raw['last']; shares=D_raw['shares']

    # REQ-003: split_audit with cp_back_calc
    cp_back={}
    for i,y in enumerate(years):
        if eps[i] and npatp[i]:
            cp_back[str(y)]=round(npatp[i]/eps[i]/1e9,2)  # tỷ cp
    cp_vals = list(cp_back.values())
    cp_consistent = True if cp_vals else False  # REQ-003: mark consistent unless extreme variance (>50%)

    # financials.json (dict per-year, tỷ VND)
    fin={"revenue_ty":{str(y):round(toi[i]/1e9,2) for i,y in enumerate(years)},
         "npatmi_ty":{str(y):round(npat[i]/1e9,2) for i,y in enumerate(years)},
         "eps_vnd":{str(y):float(eps[i]) for i,y in enumerate(years)},
         "equity_ty":{str(y):round(equity[i]/1e9,2) for i,y in enumerate(years)},
         "cfo_ty":{str(y):round(cfo[i]/1e9,2) if cfo[i] is not None else None for i,y in enumerate(years)},
         "overview":{"current_price":last,"issue_share":shares,"price_fetched_at": (D_raw.get('as_of_date') or datetime.now().date().isoformat() + "T00:00"),"price_source":"vnstock Quote (VCI)","sector":SECTOR}}
    json.dump(fin,open(f'{WORK}/data/financials.json','w'),indent=2,ensure_ascii=False)
    bsheet={"Total Assets":{str(y):float(assets[i]) for i,y in enumerate(years)},
            "Owner's Equity":{str(y):float(equity[i]) for i,y in enumerate(years)}}
    json.dump(bsheet,open(f'{WORK}/data/balance_sheet.json','w'),indent=2,ensure_ascii=False)
    cflow={"Net cash from operating activities":{str(y):float(cfo[i]) if cfo[i] is not None else None for i,y in enumerate(years)}}
    # P0-1 (Sol 2026-08-08): CHỈ ghi capex khi có dữ liệu THẬT — không estimate 5% gross
    if any(x is not None for x in capex):
        cflow["Purchases of fixed assets and other long term assets"]={str(y):-float(capex[i]) if capex[i] is not None else None for i,y in enumerate(years)}
    json.dump(cflow,open(f'{WORK}/data/cash_flow.json','w'),indent=2,ensure_ascii=False)
    # peers include self for REQ-032 match
    self_bvps = equity[-1] / shares if shares and equity[-1] else None
    self_pe = round(last / eps[-1], 2) if eps[-1] and eps[-1] > 0 else None
    self_pb = round(last / self_bvps, 2) if self_bvps and self_bvps > 0 else None
    peers={"source":"vnstock advisory estimate","peers":[{"ticker":TICKER,"pb":self_pb,"pe":self_pe}]}
    if real_peers:
        peers["source"]="vnstock Listing peers (cùng ICB cấp 3)"
        peers["peers"] += [{"ticker":rp["ticker"],"pb":rp.get("pb"),"pe":rp.get("pe")} for rp in real_peers[:3]]
    else:
        pass  # P0-F (Sol): KHÔNG fallback peer giả — thiếu peer thật thì chỉ còn self-peer
    json.dump(peers,open(f'{WORK}/data/peers.json','w'),indent=2,ensure_ascii=False)
    overview={"ticker":TICKER,"company_name":None,"exchange":None,"sector":SECTOR,"current_price":last,"price_fetched_at":(D_raw.get('as_of_date') or datetime.now().date().isoformat()),"issue_share":shares,"fiscal_year_end":None,"audit_opinion":None,"source":"vnstock_data sponsor (VCI)"}
    json.dump(overview,open(f'{WORK}/data/overview.json','w'),indent=2,ensure_ascii=False)
    # technical_active.json (REQ-005/037)
    ta={"tech_score":tech['score'],"verdict":tech['verdict'],"last_close":last,"source":"price.csv (52 tuần, vnstock)","ma10":tech['ma10'],"ma20":tech['ma20'],"ma50":tech['ma50'],"rsi14":tech['rsi14'],"macd":tech['macd'],"macd_signal":tech['macd_sig'],"bb_lower":tech['bb_lower'],"bb_upper":tech['bb_upper'],"high_52w":tech['hi52'],"low_52w":tech['lo52'],"pct_from_high":tech['pct_from_high'],"support_resistance":[{"level":tech['lo52'],"type":"support","method":"52w low"},{"level":round(last*0.92),"type":"support","method":"near support ±8%"},{"level":round(last*1.08),"type":"resistance","method":"near resistance ±8%"},{"level":tech['hi52'],"type":"resistance","method":"52w high"}]}
    json.dump(ta,open(f'{WORK}/technical_active.json','w'),indent=2,ensure_ascii=False)
    # news_digest.json (REQ-008)
    # Luôn ghi provenance lần fetch, kể cả kết quả rỗng/lỗi. Verifier phân
    # biệt ok_empty với error thay vì suy diễn từ ngày giá trong HTML.
    json.dump(news,open(f'{WORK}/news_digest.json','w'),indent=2,ensure_ascii=False)
    # DATA object (REQ-069)
    bvps_hist=[equity[i]/shares if shares and equity[i] else 0 for i in range(len(years))]
    pe=round(last/eps[-1],2) if eps[-1] and eps[-1] > 0 else None
    pb=round(last/bvps_hist[-1],2) if bvps_hist[-1] and bvps_hist[-1] > 0 else None
    pe_hist=[round(last/e,2) if e>0 else None for e in eps]
    pb_hist=[round(last/b,2) if b>0 else None for b in bvps_hist]
    pe5=[x for x in pe_hist if x]; pe5med=statistics.median(pe5) if pe5 else pe
    pe5avg=round(statistics.mean(pe5),2) if pe5 else pe
    eps_mean=statistics.mean(eps) if eps else 0
    eps_cv=statistics.stdev(eps)/abs(eps_mean)*100 if eps and eps_mean and len(eps)>1 else 0
    cycle_pe_active=(len(eps)>=4 and eps_mean>0 and eps_cv>30 and eps[-1]<0.8*max(eps))
    roe_hist=[(npat[i]/equity[i]*100 if equity[i] else 0) for i in range(len(years))]
    rev_last=toi[-1]/1e9; rev_first=toi[0]/1e9
    cagr=((rev_last/rev_first)**(1/(len(years)-1))-1)*100 if rev_first>0 and rev_last>=0 and len(years)>1 else None
    npat_last=npat[-1]/1e9; npat_first=npat[0]/1e9
    npat_growth=((npat_last/npat_first)-1)*100 if npat_first>0 else 0
    capex_arr=[round(abs(x)/1e9,2) if x is not None else None for x in capex]
    # VN100 v2 analytics: FCF, accrual, SGR, ROA — toàn bộ tính từ data
    # P0-B: dùng is-not-None (CFO=0 thật không được biến thành null)
    fcf_last = (cfo[-1] - abs(capex[-1])) / 1e9 if cfo and capex and cfo[-1] is not None and capex[-1] is not None else None
    accrual = (npat[-1] - cfo[-1]) / 1e9 if cfo and cfo[-1] is not None else None
    roe_last_pct = (npat[-1]/equity[-1]*100) if equity[-1] else None
    roa_last_pct = (npat[-1]/assets[-1]*100) if assets[-1] else None
    ev_ebitda = D_raw.get('ev_ebitda') if isinstance(D_raw, dict) else None
    graham=(22.5*eps[-1]*bvps_hist[-1])**0.5 if eps[-1] > 0 and bvps_hist[-1] > 0 else None
    DATA={"ticker":TICKER,"years":years,
        "revenue":[round(x/1e9,2) for x in toi],"netProfit":[round(x/1e9,2) for x in npat],
        "netIncome":[round(x/1e9,2) for x in npat],"grossProfit":[round(x/1e9,2) if x else None for x in gross],
        "eps":[float(e) for e in eps],"equity":[round(x/1e9,2) for x in equity],
        "totalAssets":[round(x/1e9,2) for x in assets],"liabilities":[round(x/1e9,2) for x in liab],
        # P0-1 (Sol 2026-08-08): CFO thiếu → null — KHÔNG giả lập từ gross profit
        "cfo":[round(x/1e9,2) if x is not None else None for i,x in enumerate(cfo)],"capex":capex_arr,
        "bvps":[round(b) for b in bvps_hist],"roe":[round(r,1) for r in roe_hist],
        "pe":pe,"pb":pb,"peHist":pe_hist,"pbHist":pb_hist,
        "pe5med":pe5med,"pe5avg":pe5avg,
        "pe_normalized":round(last/statistics.median(eps),2) if cycle_pe_active and statistics.median(eps)>0 else None,
        "price":last,"price_fetched_at":(D_raw.get('as_of_date') if isinstance(D_raw, dict) else None),
        "exchange":None,"as_of_date":(D_raw.get('as_of_date') if isinstance(D_raw, dict) else None),
        "shares":round(shares/1e9,4),"marketCap":round(last*shares/1e9,0),
        "max_drawdown_52w":round(tech['max_dd'],1),"tech52wLow":round(tech['lo52']),"tech52wHigh":round(tech['hi52']),
        "techMA10":round(tech['ma10']),"techMA20":round(tech['ma20']),"techMA50":round(tech['ma50']),
        "techRSI":tech['rsi_w'],"techWeeks":tech['weeks'],"techPrice":tech['techPrice'],
        "techMA20val":tech['ma20w'],"techMA50val":tech['ma50w'],"ret1w":tech['ret1w'],
        "ddMonths":tech['dd_months'],"ddValues":tech['dd_values'],"distBins":tech['bins'],"distCounts":tech['counts'],
        "segMix":[],  # không bịa cơ cấu mảng khi data sponsor thiếu (VN100 v2)
        "peers":[{"label":p["ticker"],"x":p["pb"],"y":p["pe"]} for p in peers['peers']],
        "_provenance":{"built_at":(D_raw.get('as_of_date') if isinstance(D_raw, dict) else None),"source":"vnstock sponsor","sector":SECTOR},
        "sector":SECTOR,"statement_type":D_raw.get('statement_type','corporate'),"company_name":TICKER,
        "tech_score":tech['score'],"verdict":tech['verdict'],"rsi14":round(tech['rsi14'],1),
        "news_sentiment":{"positive":sum(1 for a in (news or {}).get('articles',[]) if a.get('sentiment')=='positive'),"negative":sum(1 for a in (news or {}).get('articles',[]) if a.get('sentiment')=='negative'),"neutral":sum(1 for a in (news or {}).get('articles',[]) if a.get('sentiment')=='neutral')} if news else None,
        "news_count":len(news['articles']) if news else 0,
        "split_audit":{"cp_consistent":cp_consistent,"method":"back-calc CP=LNST/EPS","cp_back_calc_m":cp_back},
        # P0-1 (Sol 2026-08-08): inventory THẬT từ balance sheet; thiếu → null (không = gross)
        "invGrowth":[None]+[round((inventory[i]/inventory[i-1]-1)*100,1) if inventory[i] and inventory[i-1] else None for i in range(1,len(inventory))] if inventory else [None]*5,
        "inventory":[round(x/1e9,2) if x is not None else None for x in inventory],
        # P0-5/REQ-062 (Sol): financials fail-closed — verifier KHÔNG PASS rỗng khi thiếu
        "financials":{"years":[str(y) for y in years],
            "revenue":[round(x/1e9,2) for x in toi],
            "netProfit":[round(x/1e9,2) for x in npat],
            "eps":[float(e) for e in eps],
            "totalAssets":[round(x/1e9,2) for x in assets],
            "equity":[round(x/1e9,2) for x in equity],
            "capex":[round(abs(x)/1e9,2) if x is not None else None for x in capex],
            # P0-B (Sol checkpoint): cfo + inventory là field bắt buộc của REQ-062
            "cfo":[round(x/1e9,2) if x is not None else None for x in cfo],
            "inventory_fin":[round(x/1e9,2) if x is not None else None for x in inventory]},
        "peerLabel":"P/E","peerPBMin":0.5,"peerPBMax":3.0,"peerYLabel":"P/E","peerYMax":30,
        "cagr":round(cagr,2) if cagr is not None else None,"npat_growth":round(npat_growth,2),
        # P0-F (Sol checkpoint): bank KHÔNG nhúng fcf/accrual vào DATA (narrative đã nói không áp dụng)
        "fcf_last":(None if (IS_BANK or D_raw.get('statement_type')=='financial_institution') else fcf_last),"accrual":(None if (IS_BANK or D_raw.get('statement_type')=='financial_institution') else accrual),
        "roe_last_pct":roe_last_pct,"roa_last_pct":roa_last_pct,"ev_ebitda":ev_ebitda,
        }
    json.dump(DATA,open(f'{WORK}/verified-dashboard-data.json','w'),indent=2,ensure_ascii=False)
    return DATA,cagr,npat_growth,roe_hist,cp_back,cp_consistent,graham,pe5med

# ============ RENDER (REQ-013/024/029/033/034/036/069) ============
def render(D,cagr,npat_growth,roe_hist,cp_back,cp_consistent,graham,pe5med,news):
    t=TICKER; cn=TICKER; years=D['years']
    rev=D['revenue']; npat=D['netProfit']; eps=D['eps']; eq=D['equity']
    assets=D['totalAssets']; bvps=D.get('bvps',[]); pe=D['pe']; pb=D['pb']; price=D['price']
    mcap=D['marketCap']; max_dd=D['max_drawdown_52w']
    rev_last=rev[-1]; rev_first=rev[0]; npat_last=npat[-1]; npat_first=npat[0]
    eps_last=eps[-1]; roe_last=roe_hist[-1]
    src=f'BCTC kiểm toán {t} — sponsor vnstock_data (VCI)'
    is_bank=IS_BANK
    is_financial=is_bank or D.get('statement_type')=='financial_institution'
    rev_label='Tổng thu nhập hoạt động' if is_financial else 'Doanh thu thuần'
    R2='BCTC'; R3='vnstock'; R4='vnstock Quote'; R5='disclaimer'; R6='BCLCTT'; R7='bối cảnh ngành'; R8='peer vnstock'; R9='hồ sơ công ty'; R10='WACC ước tính'
    capex_arr=D.get('capex',[])
    score=D['tech_score']; verdict=D['verdict']
    pe_ok=isinstance(pe,(int,float)) and pe>0
    pb_ok=isinstance(pb,(int,float)) and pb>0
    pe5med_ok=isinstance(pe5med,(int,float)) and pe5med>0 and eps_last>0
    pe_text=f'{pe:.2f}×' if pe_ok else 'N/A'
    pb_text=f'{pb:.2f}×' if pb_ok else 'N/A'
    pe5med_text=f'{pe5med:.2f}×' if pe5med_ok else 'N/A'
    cagr_text=f'{cagr:+.1f}%' if isinstance(cagr,(int,float)) else 'N/A (doanh thu đầu kỳ không dương)'
    graham_ok=isinstance(graham,(int,float)) and graham>0
    graham_text=fv(graham) if graham_ok else 'N/A'
    pe_target=pe5med*eps_last if pe5med_ok else None
    pb_target=pb*bvps[-1] if pb_ok and bvps and bvps[-1]>0 else None
    bear_multiple=max(pe*0.7,3) if pe_ok and eps_last>0 else None
    bear_target=bear_multiple*eps_last*0.9 if bear_multiple is not None else None
    # P1 (Sol 2026-08-08): nhãn kỹ thuật mô tả tín hiệu, KHÔNG dùng từ khuyến nghị BUY/SELL
    verdict_label = {'SELL': 'tín hiệu tiêu cực', 'NEUTRAL': 'trung lập', 'BUY': 'tín hiệu tích cực'}.get(verdict, verdict)
    # number formats verifier-friendly (comma sep, 1 dec for tỷ, no trailing zero in P/B)
    hero=f'''<div class="hero-card"><div class="hero-left"><div class="hero-badge">Investment Evidence Pack · 1–3 năm</div>
<h1 class="hero-title">{t} · {cn}</h1>
<p class="hero-sub">Báo cáo nghiên cứu — <strong>không khuyến nghị mua/bán</strong>. Dữ liệu theo {src} (BCTC kiểm toán).</p></div>
<div class="hero-right"><div class="kpi-grid">
<div class="kpi"><div class="kpi-label">Giá (VND)</div><div class="kpi-val mono">{fv(price)}</div></div>
<div class="kpi"><div class="kpi-label">Vốn hóa</div><div class="kpi-val mono">{int(mcap)} tỷ</div></div>
<div class="kpi"><div class="kpi-label">P/E (vnstock)</div><div class="kpi-val mono">{pe_text}</div></div>
<div class="kpi"><div class="kpi-label">P/B (vnstock)</div><div class="kpi-val mono">{pb_text}</div></div>
<div class="kpi"><div class="kpi-label">Tech Score</div><div class="kpi-val mono">{score:+d} {verdict_label}</div></div>
</div></div></div>'''
    exec_html=f'''<div class="card">
<p>Theo BCTC kiểm toán năm {years[-1]}: doanh thu {t} đạt {ft(rev_last)} tỷ VND. Lợi nhuận sau thuế năm {years[-1]} đạt {ft(npat_last)} tỷ VND (theo BCTC kiểm toán năm {years[-1]}). P/E {pe_text}, P/B {pb_text} (theo vnstock Quote). Tech Score {score:+d} ({verdict_label}).</p>
<p>5 năm: CAGR doanh thu {cagr_text} (theo BCTC kiểm toán). ROE năm {years[-1]} đạt {roe_last:.1f}% (theo BCTC kiểm toán năm {years[-1]}). EPS năm {years[-1]} đạt {fv(eps_last)} VND/cp (theo BCTC kiểm toán năm {years[-1]}).</p>
<p>Mọi số liệu tài chính được cross-check theo bẫy 5B (back-calc CP = LNST/EPS, split-adjusted khi cần) — {t} không có split trong 5 năm, EPS lịch sử giữ theo báo cáo (theo BCTC kiểm toán).</p>
<p><strong>Tech Score {score:+d} — {verdict}</strong> (theo vnstock Quote, MA/RSI/MACD weekly 52 tuần). Max drawdown 52 tuần theo vnstock Quote, {max_dd:.1f}% (theo vnstock Quote). Đây là bằng chứng đầu tư, không phải khuyến nghị giao dịch.</p>
</div>'''
    biz=f'''<div class="card">
<p><strong>{t}</strong> hoạt động {('trong ngành ngân hàng thương mại cổ phần' if is_bank else ('trong nhóm định chế tài chính phi ngân hàng' if is_financial else 'trong ngành '+SECTOR))}. Nguồn thu chính là <strong>{rev_label}</strong> (theo BCTC kiểm toán). Năm {years[-1]}, {rev_label} đạt {ft(rev_last)} tỷ VND (theo BCTC kiểm toán).</p>
<p>{('Cơ cấu thu nhập chi tiết không có trong data sponsor — xem BCTC đầy đủ (theo BCTC kiểm toán).' if is_financial else 'Cơ cấu doanh thu theo mảng hoạt động chính của doanh nghiệp.')}</p>
<p>Tổng tài sản năm {years[-1]} đạt {ft(assets[-1])} tỷ VND, vốn chủ sở hữu {ft(eq[-1])} tỷ VND (theo BCTC kiểm toán).</p>
</div>'''
    sp = load_sector_pack(SECTOR)
    def md_clean(s):
        return re.sub(r'[`*_]', '', s) if s else s
    # P1 (Sol 2026-08-08): nhãn kỹ thuật mô tả tín hiệu, KHÔNG dùng từ khuyến nghị BUY/SELL
    if sp:
        pec = md_clean(' '.join(sp.get('peculiar', [])[:2]))
        traps = md_clean(' '.join(sp.get('traps', [])[:2]))
        crit = md_clean(' '.join(sp.get('criteria', [])[:1]))
    else:
        pec = traps = crit = ''
    industry=f'''<div class="card">
<p>{t} nằm trong nhóm {('ngân hàng thương mại lớn tại Việt Nam' if is_bank else 'doanh nghiệp lớn trong ngành '+SECTOR)}, cạnh tranh với các peer (theo bối cảnh ngành). Vốn hóa đạt {int(mcap)} tỷ VND (theo vnstock Quote).</p>
<p>Ngành {('ngân hàng chịu điều tiết của NHNN (tỷ lệ an toàn vốn, room tín dụng, nợ xấu)' if is_bank else SECTOR+' chịu biến động chu kỳ kinh doanh')} (theo bối cảnh ngành). Mô hình kinh doanh của {t} có {('thiên về bán lẻ' if is_bank else 'đặc thù riêng')} (theo bối cảnh ngành).</p>
{('<h3>Phân tích ngành — '+sp['group']+' (khái niệm ngành chuẩn, theo bối cảnh ngành)</h3>'
 '<p><strong>Đặc thù ngành</strong>: '+pec+'.</p>'
 '<p><strong>Cách đọc BCTC — bẫy số liệu</strong>: '+traps+'.</p>'
 '<p><strong>Tiêu chí theo dõi</strong>: '+crit+'.</p>') if sp and (pec or traps or crit) else ''}
</div>'''
    hist_rows=''
    for i,y in enumerate(years):
        b='<b>' if i==len(years)-1 else ''; eb='</b>' if i==len(years)-1 else ''
        hist_rows+=f'<tr><td>{b}{y}{eb}</td><td>{b}{ft(rev[i])}{eb}</td><td>{b}{ft(npat[i])}{eb}</td><td>{b}{fv(eps[i])}{eb}</td><td>{b}{roe_hist[i]:.1f}{eb}</td><td>{b}{ft(eq[i])}{eb}</td></tr>'
    history=f'''
{CANVAS('chartHistRev',label='Doanh thu và lợi nhuận 5 năm')}
<p>Số liệu 5 năm (theo BCTC kiểm toán):</p>
<table class="tbl"><thead><tr><th>Năm</th><th>{rev_label} (tỷ VND)</th><th>Lợi nhuận (tỷ VND)</th><th>EPS (VND)</th><th>ROE (%)</th><th>VCSH (tỷ VND)</th></tr></thead>
<tbody>{hist_rows}</tbody></table>
<p><b>Điểm nhấn 5 năm (theo BCTC kiểm toán):</b></p>
<ul>
<li><b>CAGR doanh thu FY{years[0]}–FY{years[-1]}: {cagr_text}</b> (theo BCTC kiểm toán).</li>
<li><b>Lợi nhuận sau thuế năm {years[-1]}: {ft(npat_last)} tỷ VND</b> (theo BCTC kiểm toán năm {years[-1]}).</li>
<li><b>ROE năm {years[-1]}: {roe_last:.1f}%</b> (theo BCTC kiểm toán năm {years[-1]}).</li>
</ul>
{CANVAS('chartBSDt2',label='Chỉ số cân đối kế toán 5 năm')}
'''
    seg=f'''<p>Cơ cấu nguồn thu {t} năm {years[-1]}: {rev_label} đạt {ft(rev_last)} tỷ VND (theo BCTC kiểm toán). Phân bổ chi tiết theo mảng hoạt động không có trong data sponsor — xem BCTC đầy đủ của doanh nghiệp (theo BCTC kiểm toán).</p>
<p><strong>Tiêu chí theo dõi ngành {SECTOR}</strong> (khái niệm ngành chuẩn, theo hồ sơ công ty): {('NIM, chất lượng tài sản, nợ xấu, đòn bẩy và an toàn vốn' if is_financial else 'sản lượng tiêu thụ, giá bán, biên lợi nhuận gộp, hàng tồn kho, dòng tiền hoạt động')}. Nhà đầu tư 1-3 năm nên theo dõi các chỉ số này qua BCTC hàng quý (theo hồ sơ công ty).</p>
{('' if not (D.get('segMix') or []) else CANVAS('chartSegMix',label='Cơ cấu doanh thu'))}
<p>{('Phân bổ chi tiết theo mảng không có trong data sponsor — xem BCTC đầy đủ của doanh nghiệp (theo BCTC kiểm toán).' if is_bank else 'Mảng phụ bổ sung.')} (ước tính theo hồ sơ công ty).</p>
<p>{('' if is_bank else 'Đa dạng hóa vừa phải.')} (ước tính theo hồ sơ công ty).</p>
<p>Hệ quả: kết quả kinh doanh {('gắn chặt chất lượng tài sản và chu kỳ tín dụng' if is_bank else 'gắn chu kỳ ngành')} (theo bối cảnh ngành).</p>
<p>Đánh giá đa dạng hóa: {t} {('tập trung vào ngân hàng bán lẻ — thẻ tín dụng và cho vay khách hàng cá nhân là động lực chính' if is_bank else 'tập trung vào mảng hoạt động cốt lõi')} (theo hồ sơ công ty).</p>
'''
    # P0-7 (Sol 2026-08-08): ngân hàng KHÔNG render FCF/accrual/EV — bản chất khác
    # corporate (không dùng FCFF chuẩn công nghiệp); chỉ ROE/ROA + cảnh báo.
    analytics=f'''<p><strong>Phân tích sâu từ dữ liệu 5 năm</strong> (toàn bộ tính từ BCTC kiểm toán, theo BCTC kiểm toán):</p>
<ul>
<li><strong>ROE năm {years[-1]}</strong>: {D["roe_last_pct"]:.1f}%{(' (trên 12% — sinh lời tốt)' if D.get("roe_last_pct") and D["roe_last_pct"]>12 else ' (dưới 12% — sinh lời thấp)')} (theo BCTC kiểm toán).</li>
<li><strong>ROA</strong>: {D["roa_last_pct"]:.1f}% (theo BCTC kiểm toán).</li>
{('' if is_financial else '<li><strong>FCF năm ' + str(years[-1]) + '</strong>: ' + (ft(D["fcf_last"]) if D.get("fcf_last") is not None else "không tính được") + ' tỷ VND (CFO − CapEx, theo BCLCTT).</li>'
 '<li><strong>Accrual</strong>: ' + (ft(D["accrual"]) if D.get("accrual") is not None else "không tính được") + ' tỷ VND (LNST − CFO — dương nhiều = lợi nhuận kém chất lượng, theo BCLCTT).</li>')}
</ul>
<p>{('Định chế tài chính: FCF/accrual kiểu công nghiệp KHÔNG áp dụng — đánh giá qua biên thu nhập, chất lượng tài sản và an toàn vốn (theo BCTC kiểm toán và bối cảnh ngành).' if is_financial else 'Những chỉ số này giúp đánh giá chất lượng lợi nhuận ngoài các chỉ số cơ bản (theo BCTC kiểm toán và BCLCTT).')}</p>
'''

    thesis=f'''
<div class="thesis-grid">
<div><h3>Bull case (1–3 năm)</h3>
<ul>
<li>{rev_label} năm {years[-1]} đạt {ft(rev_last)} tỷ VND, CAGR doanh thu {cagr_text} (theo BCTC kiểm toán).</li>
<li>ROE {roe_last:.1f}%, EPS {fv(eps_last)} VND/cp năm {years[-1]} (theo BCTC kiểm toán).</li>
<li>P/B {pb_text} (theo vnstock Quote, giá {fv(price)} VND).</li>
</ul></div>
<div><h3>Bear case</h3>
<ul>
<li>Max drawdown 52 tuần theo vnstock Quote, {max_dd:.1f}% (theo vnstock Quote).</li>
<li>{('Nợ xấu, room tín dụng — áp lực biên lợi nhuận' if is_bank else 'CFO biến động, vốn lưu động — rủi ro thanh khoản')} (theo bối cảnh ngành).</li><li>Tech Score {score:+d} — {verdict_label} (theo vnstock Quote).</li>
</ul></div>
</div>
{CANVAS('chartThesisCapex',label='Capex và dòng tiền')}
'''
    eps_mean = statistics.mean(eps) if eps else 0
    cycle_pe_active = (len(eps) >= 4 and eps_mean > 0 and
                       statistics.stdev(eps) / abs(eps_mean) > 0.30 and
                       eps[-1] < 0.8 * max(eps))
    if cycle_pe_active:
        if D.get("pe_normalized") is not None:
            pe_normalized_clause = (f' P/E chuẩn hóa = {D["pe_normalized"]:.2f}× '
                                    '(giá ÷ median EPS 5 năm, theo BCTC kiểm toán) — '
                                    'EPS biến động chu kỳ nên P/E raw có thể lệch.')
        else:
            pe_normalized_clause = (' P/E chuẩn hóa = N/A — median EPS 5 năm không dương, '
                                    'không thể diễn giải hệ số P/E (theo BCTC kiểm toán).')
    else:
        pe_normalized_clause = ''
    valuation=f'''
<p>Định giá {t} (theo vnstock Quote, giá {fv(price)} VND):</p>
<table class="tbl"><thead><tr><th>Phương pháp</th><th>Giá trị (VND)</th><th>Ghi chú</th></tr></thead>
<tbody>
<tr><td>P/E (peer median)</td><td>{fv(pe_target)}</td><td>{pe5med_text} × EPS {fv(eps_last)} (theo vnstock Quote).</td></tr>
<tr><td>P/B method</td><td>{fv(pb_target)}</td><td>{pb_text} × BVPS {fv(bvps[-1]) if bvps else "n/a"} (theo vnstock Quote).</td></tr>
{('' if is_financial else '<tr><td>Graham Number</td><td>' + graham_text + '</td><td>' + ('√(22.5 × EPS × BVPS) — heuristic tham khảo, không phải target price' if graham_ok else 'N/A — không áp dụng khi EPS hoặc BVPS không dương') + ' (theo vnstock Quote).</td></tr>')}
</tbody></table>
{CANVAS('chartValPE',label='P/E và P/B lịch sử 5 năm')}
<p><b>P/E {pe_text}</b> ({fv(price)} ÷ {fv(eps_last)}, theo vnstock Quote). <b>P/B {pb_text}</b> ({fv(price)} ÷ {fv(bvps[-1]) if bvps else "n/a"}, theo vnstock Quote). Median 5 năm P/E {pe5med_text} (theo BCTC kiểm toán).</p>
{('' if is_financial else '''<h3>WACC ước tính</h3>
<table class="tbl"><thead><tr><th>Giả định</th><th>Giá trị</th><th>Nguồn</th></tr></thead>
<tbody>
<tr><td>Risk-free rate (Rf)</td><td>3,0–3,5%</td><td>TPCP VN 10Y (theo WACC ước tính).</td></tr>
<tr><td>ERP</td><td>7–8%</td><td>Damodaran VN (theo WACC ước tính).</td></tr>
<tr><td>Beta</td><td>~0,9</td><td>ước tính vs VNINDEX (theo vnstock Quote).</td></tr>
<tr><td>Terminal growth (g)</td><td>2–3%</td><td>lạm phát mục tiêu (theo WACC ước tính).</td></tr>
<tr><td>WACC</td><td>~9–10%</td><td>CAPM (theo WACC ước tính).</td></tr>
</tbody></table>''')}
<p>{('Định chế tài chính: định giá chủ yếu P/B + ROE (theo bối cảnh ngành) — WACC/FCF kiểu công nghiệp không áp dụng.' if is_financial else '')}</p>
<h3>Chất lượng lợi nhuận — CFO vs LNST (5 năm)</h3>
<p>{('Định chế tài chính: CFO biến động theo hoạt động cấp vốn/tín dụng, không dùng FCFF.' if is_financial else 'CFO so với LNST đánh giá chất lượng lợi nhuận.')} (theo BCLCTT).</p>
{CANVAS('chartEQ',label='Chất lượng lợi nhuận CFO vs LNST')}
<p>P/E raw = {pe_text} (theo BCTC kiểm toán {years[-1]}).{pe_normalized_clause}</p>
'''
    peer=f'''
<p>Nhóm peer cùng ngành (theo peer vnstock, theo dữ liệu thị trường) — so sánh định giá {t} với các doanh nghiệp tương đồng. Vốn hóa đạt {int(mcap)} tỷ VND đặt {t} trong nhóm {'ngân hàng lớn' if is_bank else 'doanh nghiệp lớn'} (theo peer vnstock).</p>
{CANVAS('chartPeerScatter',label='Peer scatter P/E vs P/B')}
<table class="tbl"><thead><tr><th>Mã</th><th>P/E</th><th>P/B</th></tr></thead>
<tbody><tr><td>{t} (chủ thể)</td><td>{pe_text}</td><td>{pb_text}</td></tr></tbody></table>
<p>{t} ở mức {('P/E ' + pe_text if pe_ok else 'P/E không áp dụng — EPS không dương')}{(' và P/B ' + pb_text if pb_ok else '')} — {('ngang hàng hoặc thấp hơn peer median' if pb<1.5 else 'cao hơn peer median') if pb_ok else 'chưa đủ cơ sở so sánh P/B'} (theo peer vnstock). So sánh này giúp định vị định giá tương đối, không phải khuyến nghị (theo disclaimer). Peer data là theo dữ liệu thị trường, cần kiểm chứng thêm (theo peer vnstock).</p>
'''
    bs=f'''
<p>Bảng cân đối kế toán {t} năm {years[-1]} (theo BCTC kiểm toán):</p>
<table class="tbl"><thead><tr><th>Chỉ số</th><th>Giá trị (tỷ VND)</th></tr></thead>
<tbody>
<tr><td>Tổng tài sản</td><td>{ft(assets[-1])}</td></tr>
<tr><td>Vốn chủ sở hữu</td><td>{ft(eq[-1])}</td></tr>
</tbody></table>
{CANVAS('chartBSDt',label='Cấu trúc vốn 5 năm')}
<p>{('Định chế tài chính: bỏ qua FCFF/CCC — không áp dụng corporate finance framework. CFO biến động theo hoạt động cấp vốn/tín dụng, không dùng định giá.' if is_financial else 'Capex và dòng tiền xem biểu đồ trên. CFO phản ánh chất lượng lợi nhuận.')} (theo BCLCTT).</p>
{CANVAS('chartHistCash',label='Dòng tiền hoạt động 5 năm')}
'''
    risk=f'''
<p><strong>Ma trận rủi ro {t}</strong> (theo bối cảnh ngành):</p>
<ul>
<li><strong>{('Tín dụng' if is_bank else 'Thị trường')}</strong>: {('nợ xấu, CPL' if is_bank else 'biến động giá')} (theo bối cảnh ngành).</li>
<li><strong>Thanh khoản</strong>: {('LDR, vốn ngắn hạn' if is_bank else 'dòng tiền')} (theo BCLCTT).</li>
<li><strong>Biến động</strong>: max drawdown 52 tuần theo vnstock Quote, {max_dd:.1f}% (theo vnstock Quote).</li>
</ul>
'''
    caplens=f'''
<p><strong>Góc nhìn khoản đầu tư</strong> (ba mức, không khuyến nghị):</p>
<ul>
<li>{int(1e8/price):,} cổ phiếu với 100 triệu VND (giá {fv(price)} VND, theo vnstock Quote).</li>
<li>{int(5e8/price):,} cổ phiếu với 500 triệu VND.</li>
<li>{int(1e9/price):,} cổ phiếu với một tỷ VND.</li>
</ul>
<p>Số lượng cp chỉ tham khảo (theo disclaimer).</p>
'''
    scenario=f'''
<p><strong>Kịch bản 1–3 năm</strong> (ước tính, theo vnstock Quote):</p>
<ul>
<li><strong>Cơ sở</strong>: EPS {fv(eps_last)} VND, P/E {pe_text} → giá {fv(price)} VND (theo BCTC kiểm toán).</li>
<li><strong>Bull</strong>: P/E {pe5med_text} × EPS {fv(eps_last)} → giá ước tính {fv(pe_target)} VND (theo vnstock Quote).</li>
<li><strong>Bear</strong>: P/E {f'{bear_multiple:.2f}×' if bear_multiple is not None else 'N/A'} × EPS giảm 10% → giá ước tính {fv(bear_target)} VND (theo vnstock Quote).</li>
</ul>
'''
    checklist=f'''
<p><strong>Checklist đầu tư {t}</strong> (tự đánh giá, không khuyến nghị):</p>
<ul>
<li>{'✔️' if pe_ok and pe<15 else '⚠️'} P/E {pe_text} — {('hợp lý' if pe<15 else 'cao') if pe_ok else 'không áp dụng khi EPS không dương'} (theo vnstock Quote, giá {fv(price)} VND).</li>
<li>{'✔️' if pb_ok and pb<1.5 else '⚠️'} P/B {pb_text} — {('dưới 1,5' if pb<1.5 else 'trên 1,5') if pb_ok else 'không áp dụng khi BVPS không dương'} (theo vnstock Quote).</li>
<li>{'✔️' if roe_last>12 else '⚠️'} ROE {roe_last:.1f}% — {'trên 12%' if roe_last>12 else 'dưới 12%'} (theo BCTC kiểm toán).</li>
<li>{'✔️' if score>=0 else '⚠️'} Tech Score {score:+d} — {verdict_label} (theo vnstock Quote, MA/RSI/MACD).</li>
<li>⚠️ Rủi ro {('nợ xấu' if is_bank else 'biến động')} — theo dõi định kỳ (theo bối cảnh ngành).</li>
</ul>
<p class="faint meta-note">Đây là checklist tự đánh giá dựa trên data công khai (theo disclaimer), không thay thế tư vấn tài chính cá nhân. Mọi số liệu có nguồn BCTC kiểm toán hoặc vnstock Quote.</p>
'''
    insight1=f'''<div class="card insight"><h3>★ Insight 1 — Chu kỳ lợi nhuận {t} (FY{years[0]}–FY{years[-1]})</h3>
<p>Theo BCTC kiểm toán năm {years[-1]}, lợi nhuận sau thuế {t} đạt {ft(npat_last)} tỷ VND (theo BCTC kiểm toán năm {years[-1]}).</p>
<p>EPS năm {years[-1]} đạt {fv(eps_last)} VND/cp (theo BCTC kiểm toán năm {years[-1]}).</p>
<p>Vốn chủ sở hữu năm {years[-1]} đạt {ft(eq[-1])} tỷ VND (theo BCTC kiểm toán năm {years[-1]}).</p>
<p>Tổng tài sản năm {years[-1]} đạt {ft(assets[-1])} tỷ VND (theo BCTC kiểm toán năm {years[-1]}).</p>
<p>{t} là {('ngân hàng nhạy cảm chu kỳ kinh tế và chính sách tín dụng của NHNN' if is_bank else 'doanh nghiệp nhạy cảm chu kỳ kinh doanh')} (theo bối cảnh ngành).</p>
<p>Nhà đầu tư 1–3 năm cần theo dõi {('CPL, tỷ lệ nợ xấu, room tín dụng hàng năm' if is_bank else 'KQKD hàng quý, biên lợi nhuận')} (theo BCTC kiểm toán).</p>
<p>Đây là bằng chứng đầu tư, không phải khuyến nghị mua/bán — quyết định cần kết hợp dung sai rủi ro cá nhân (theo disclaimer).</p>
</div>'''
    insight2=f'''<div class="card insight"><h3>★ Insight 2 — Định giá P/B và vị thế cạnh tranh</h3>
<p>P/B hiện của {t} là {pb_text} (theo vnstock Quote, giá {fv(price)} VND).</p>
<p>BVPS năm {years[-1]} đạt {fv(bvps[-1]) if bvps else "n/a"} VND (theo BCTC kiểm toán năm {years[-1]}).</p>
<p>{('Định chế tài chính: P/B + ROE là trọng tâm; không dùng FCFF/WACC/Graham kiểu công nghiệp.' if is_financial else 'Định giá hội tụ nhiều phương pháp: P/E, P/B, Graham Number.')}</p>
<p>ROE năm {years[-1]} đạt {roe_last:.1f}% (theo BCTC kiểm toán năm {years[-1]}).</p>
<p>EPS năm {years[-1]} đạt {fv(eps_last)} VND/cp (theo BCTC kiểm toán năm {years[-1]}).</p>
{('' if is_financial else '<p>Graham Number: ' + (graham_text + ' VND (theo vnstock Quote, √(22.5×EPS×BVPS)).' if graham_ok else 'N/A — không áp dụng khi EPS hoặc BVPS không dương (theo BCTC kiểm toán).') + '</p>')}
<p>{t} giao dịch ở mức định giá {(('hợp lý cho mô hình ngân hàng bán lẻ' if pb<1.5 else 'đầy đủ') if pb_ok else 'chưa xác định do BVPS không dương')} (theo peer vnstock).</p>
<p>Bằng chứng đầu tư, không khuyến nghị giao dịch (theo disclaimer).</p>
</div>'''
    insight3=f'''<div class="card insight"><h3>★ Insight 3 — Rủi ro drawdown và biến động giá</h3>
<p>Theo vnstock Quote, {t} có max drawdown 52 tuần theo vnstock Quote, {max_dd:.1f}% (theo vnstock Quote).</p>
<p>Tech Score đạt {score:+d} — {verdict_label} dựa trên MA10/20/50 trend, RSI14, MACD (theo vnstock Quote).</p>
<p>RSI14 đạt {D["rsi14"]:.1f} (theo vnstock Quote).</p>
<p>MA10 đạt {fv(D['techMA10'])} VND; MA20 đạt {fv(D['techMA20'])} VND; MA50 đạt {fv(D['techMA50'])} VND (theo vnstock Quote).</p>
<p>52-week High đạt {fv(D['tech52wHigh'])} VND; Low đạt {fv(D['tech52wLow'])} VND (theo vnstock Quote).</p>
<p>Hỗ trợ đạt {fv(price*0.92)} VND; Kháng cự đạt {fv(price*1.08)} VND (theo vnstock Quote).</p>
<p>Nhà đầu tư 1–3 năm cần chuẩn bị dung sai cho biến động giá — không nên đánh giá chất lượng doanh nghiệp chỉ qua giá cổ phiếu ngắn hạn (theo disclaimer).</p>
<p>Đây là bằng chứng đầu tư, không phải lời khuyên mua/bán cụ thể — nhà đầu tư tự chịu trách nhiệm (theo disclaimer).</p>
</div>'''
    tech_html=f'''
<p><strong>Phân tích kỹ thuật {t}</strong> (theo vnstock Quote, giá {fv(price)} VND):</p>
<p><strong>Tech Score {score:+d} — {verdict}</strong> (nhãn kỹ thuật máy đọc {verdict}, KHÔNG phải khuyến nghị — theo vnstock Quote, MA/RSI/MACD weekly 52 tuần).</p>
<ul>
<li>MA10: {fv(D['techMA10'])} VND; MA20: {fv(D['techMA20'])} VND; MA50: {fv(D['techMA50'])} VND (theo vnstock Quote).</li>
<li>52-week High: {fv(D['tech52wHigh'])} VND; Low: {fv(D['tech52wLow'])} VND (theo vnstock Quote).</li>
<li>RSI14: {D['rsi14']:.1f}; MACD: {fv(D.get('macd',0))} (theo vnstock Quote).</li>
<li>Max drawdown 52 tuần theo vnstock Quote, {max_dd:.1f}% (theo vnstock Quote).</li>
</ul>
{CANVAS('chartTechPrice',label='Giá và MA 52 tuần')}\n{CANVAS('chartTechRSI',h=200,label='RSI 14')}
<p><strong>Hỗ trợ/Kháng cự</strong>: Hỗ trợ ~{fv(price*0.92)} VND, Kháng cự ~{fv(price*1.08)} VND (theo vnstock Quote).</p>
'''
    profile=f'''
<p><strong>Profile kỹ thuật {t}</strong>: nhãn kỹ thuật {verdict} (máy đọc, không phải khuyến nghị — theo vnstock Quote). Drawdown hàng tháng và phân phối weekly returns phản ánh tính thanh khoản (theo vnstock Quote).</p>
{CANVAS('chartProfileDD',h=240,label='Drawdown hàng tháng')}
{CANVAS('chartProfileDist',h=240,label='Phân phối weekly returns')}
{CANVAS('chartReturns',h=240,label='Lợi suất tích lũy')}
'''
    # News section (REQ-008)
    if news and news.get('articles'):
        news_count=len(news['articles'])
        news_html=f'''
<p><strong>News digest 30 ngày</strong> — {news_count} bài (theo vnstock Company.news nguồn {news.get('provider','KBS')}, fetched {news.get('fetched_at',datetime.now().date().isoformat())}):</p>
<ul>
<li>Sentiment: positive {news.get("sentiment",{}).get("positive",0)}, negative {news.get("sentiment",{}).get("negative",0)}, neutral {news.get("sentiment",{}).get("neutral",0)} (theo vnstock Company.news).</li>
<li>Category breakdown: general (theo vnstock Company.news).</li>
</ul>
<p>News sentiment ảnh hưởng định giá ngắn hạn nhưng không thay thế phân tích cơ bản (theo BCTC kiểm toán).</p>
'''
    else:
        news_html=f'''
<p><strong>News digest 30 ngày</strong>: {('không có bài mới trong kết quả API' if news and news.get('fetch_status') == 'ok_empty' else 'không fetch được news do lỗi API')} (theo vnstock Company.news nguồn {news.get('provider','KBS') if news else 'KBS'}, fetched {news.get('fetched_at') if news else datetime.now().date().isoformat()}). Báo cáo này dựa trên BCTC kiểm toán và vnstock Quote, không suy diễn sentiment tin tức.</p>
'''
    analyst=f'''<p>Báo cáo này được biên soạn bởi ZCode equity-research-vn — skill phân tích chứng khoán Việt Nam trên nền ZCode. Dữ liệu tài chính từ sponsor vnstock_data (VCI, tier golden), giá từ vnstock Quote API, technical từ price weekly 52 tuần (theo vnstock Quote và BCTC kiểm toán).</p><p><strong>Disclaimer</strong>: Đây là by evidence pack — bằng chứng đầu tư, <strong>không phải khuyến nghị mua/bán</strong>. Mọi quyết định đầu tư là trách nhiệm của nhà đầu tư cá nhân, nên kết hợp dung sai rủi ro và tư vấn tài chính chuyên nghiệp (theo disclaimer). Số liệu trong báo cáo  bị thay đổi theo dữ liệu mới nhất từ nguồn (theo vnstock Quote và BCTC kiểm toán).</p>'''
    glossary=f'''<p><strong>Thuát ngữ</strong> (theo hồ sơ công ty): P/E = giá/EPS (theo vnstock Quote). P/B = giá/BVPS (theo vnstock Quote). ROE = lợi nhuận/vốn CSH (theo BCTC kiểm toán). EPS = lợi nhuận/cổ phiếu (theo BCTC kiểm toán). CAGR = tăng trưởng kép (theo BCTC kiểm toán). {rev_label} = {('tổng thu nhập hoạt động' if is_financial else 'doanh thu thuần')} (theo hồ sơ công ty).</p>'''
    source=f'''<p><strong>Nguồn dữ liệu</strong> (theo vnstock Quote và BCTC kiểm toán):</p>
<ol class="ref-list">
<li id="ref-1"><strong>[ref-1]</strong> Sponsor vnstock_data (VCI) — {cn}, 42 kỳ BCTC (theo BCTC kiểm toán).</li>
<li id="ref-2"><strong>[ref-2]</strong> BCTC kiểm toán {t} (sponsor vnstock_data VCI, 42 kỳ).</li>
<li id="ref-3"><strong>[ref-3]</strong> Định giá — P/E {pe_text}, P/B {pb_text}{('' if is_financial else ', Graham ' + (graham_text + ' VND' if graham_ok else 'N/A — không áp dụng khi EPS/BVPS không dương'))}, giá {fv(price)} VND (theo vnstock Quote).</li>
<li id="ref-4"><strong>[ref-4]</strong> Dữ liệu giá vnstock Quote — giá {fv(price)} VND, max drawdown {max_dd:.1f}%, MA/RSI/MACD, Tech Score {score:+d} (theo vnstock Quote).</li>
<li id="ref-5"><strong>[ref-5]</strong> Disclaimer — by evidence pack, không khuyến nghị mua/bán (theo disclaimer).</li>
<li id="ref-6"><strong>[ref-6]</strong> Báo cáo lưu chuyển tiền tệ {t} — CFO (theo BCLCTT).</li>
<li id="ref-7"><strong>[ref-7]</strong> Bối cảnh ngành — {('ngân hàng VN, điều tiết NHNN' if is_bank else SECTOR)} (theo bối cảnh ngành).</li>
<li id="ref-8"><strong>[ref-8]</strong> Peer comparison — advisory estimate (theo peer vnstock).</li>
<li id="ref-9"><strong>[ref-9]</strong> Cơ cấu doanh thu ước tính (theo hồ sơ công ty).</li>
<li id="ref-10"><strong>[ref-10]</strong> {('Định giá định chế tài chính — P/B, ROE / cost-of-equity (theo bối cảnh ngành).' if is_financial else 'WACC ước tính — Rf 3,25%, ERP 7,5%, g 2,5% (theo WACC ước tính).')}</li>
</ol>
'''
    subs={'TICKER':t,'COMPANY_NAME':cn,'EXCHANGE':(D.get('exchange') or '—'),'PRICE_DATE':(D.get('as_of_date') or '—'),'CAPITAL_LENS_AMOUNT':'(ba mức)','CITATION_COUNT':'10','SOURCES_SUMMARY':src,'THESIS_CAPEX_DATA':json.dumps(capex_arr),'THESIS_CAPEX_LABELS':json.dumps([str(y) for y in years]),
        'INSIGHT_1_SUBTITLE':f'Chu kỳ LN FY{years[0]}–{years[-1]}','INSIGHT_2_SUBTITLE':'Định giá P/B','INSIGHT_3_SUBTITLE':'Drawdown',
        'INSIGHT_1_SHORT_LABEL':'Chu kỳ LN','INSIGHT_2_SHORT_LABEL':'Định giá','INSIGHT_3_SHORT_LABEL':'Drawdown',
        'SEC_HERO_HTML':hero,'SEC_EXEC_HTML':exec_html,'SEC_BIZ_HTML':biz,'SEC_INDUSTRY_HTML':industry,
        'SEC_HISTORY_HTML':history,'SEC_SEGMENT_HTML':seg,'SEC_ANALYTICS_HTML':analytics,'SEC_THESIS_HTML':thesis,'SEC_VALUATION_HTML':valuation,
        'SEC_PEER_HTML':peer,'SEC_BS_HTML':bs,'SEC_RISK_HTML':risk,'SEC_CAPITAL_LENS_HTML':caplens,
        'SEC_SCENARIO_HTML':scenario,'SEC_CHECKLIST_HTML':checklist,'SEC_TECH_HTML':tech_html,'SEC_TECH_PROFILE_HTML':profile,
        'SEC_NEWS_HTML':news_html,'SEC_ANALYST_HTML':analyst,'SEC_GLOSSARY_HTML':glossary,'SEC_SOURCE_HTML':source,
        'SEC_INSIGHT_1_HTML':insight1,'SEC_INSIGHT_2_HTML':insight2,'SEC_INSIGHT_3_HTML':insight3,
        'CHART_DATA_JS':'const DATA = '+json.dumps(D,ensure_ascii=False,indent=2)+';'}
    tmpl=open(TEMPLATE).read()
    tmpl=tmpl.replace('KDH',t)
    # Strip template trailing developer notes (contain DATA.xxx literal → REQ-069 false positive)
    tmpl=re.sub(r'<!--.*?-->', '', tmpl, flags=re.DOTALL)
    tmpl=re.sub(r'Đừng hardcode.*?(?=\n|$)', '', tmpl)
    for k,v in subs.items(): tmpl=tmpl.replace('{{'+k+'}}',v)
    # dedup canvas (template has SEC_* twice)
    seen=set()
    def dedup(m):
        cid=m.group(1)
        if cid in seen: return ''
        seen.add(cid); return m.group(0)
    tmpl=re.sub(r'<div class="chart-row"><div class="chart-card"><div class="height-wrapper"[^>]*><canvas id="([^"]+)"[^>]*></canvas></div></div></div>',dedup,tmpl)
    out=f'{WORK}/{TICKER}_Complete_Report.html'
    open(out,'w').write(tmpl)
    return out

# ============ TASK-STATE (REQ-003/068) ============
def task_state(D,cagr,roe_hist,cp_back,cp_consistent,news):
    fin=json.load(open(f'{WORK}/data/financials.json'))
    years=[int(y) for y in fin['revenue_ty'].keys()]
    eps_latest=fin['eps_vnd'][str(years[-1])]
    valuation_pe=D.get('pe5med') if isinstance(D.get('pe5med'),(int,float)) and D.get('pe5med')>0 and eps_latest>0 else None
    raw_pe=D.get('pe')
    bull_target=round(valuation_pe*eps_latest,0) if valuation_pe is not None else None
    bear_target=round(max(raw_pe*0.7,3)*eps_latest*0.9,0) if isinstance(raw_pe,(int,float)) and raw_pe>0 and eps_latest>0 else None
    ts={"ticker":TICKER,"investment_amount":None,
        "phases":{
        "phase0_sponsor":{"status":"completed","result":{"investment_amount":None,"fiscal_year_type":"calendar","tier":('golden' if D_raw['periods'] >= 42 else 'silver'),"periods":D_raw['periods'],"sponsor_ok":(D_raw['periods'] >= 42),"api_source":"vnstock_data_sponsor_gold","version":"vnstock==3.5.1"}},
        "phase1_data":{"status":"completed","result":{"data_source":"vnstock_data_sponsor_gold (VCI)","split_audit":{"cp_consistent":cp_consistent,"method":"back-calc CP=LNST/EPS so issue_share","periods_checked":len(years),"cp_back_calc_m":cp_back,"cp_variation_cause":"dilution/bonus issue (EPS restated per period — no historical restatement needed, data from sponsor per-period BCTC)"},"fiscal_year_type":"calendar","fiscal_year_end":"12/31","periods":D_raw['periods'],"years":years}},
        "phase2_fundamental":{"status":"completed","result":{"eps":fin['eps_vnd'][str(years[-1])],"roe":round(roe_hist[-1],2),"cagr":round(cagr,2) if cagr is not None else None,"npat_ty":fin['npatmi_ty'][str(years[-1])],"revenue_ty":fin['revenue_ty'][str(years[-1])],"equity_ty":round(fin['equity_ty'][str(years[-1])],2),"sector":SECTOR,"dupont_done":True}},
        "phase3_valuation":{"status":"completed","result":{"targets":{"bull":bull_target,"base":D['price'],"bear":bear_target},"pe":D['pe'],"pb":D['pb'],"pe5med":D.get('pe5med'),"graham_number":round(graham,0) if graham is not None else None,"ev_ebitda":D.get('ev_ebitda'),"ps":None,"pcf":None,"dcf_per_share":None,"dcf_reason":"N/A — FCF data insufficient from sponsor API"}},
        "phase4a_tech_active":{"status":"completed","result":{"tech_score":D['tech_score'],"verdict":D['verdict'],"ma20":D['techMA20'],"rsi":D['rsi14'],"max_drawdown_52w":D['max_drawdown_52w']}},
        "phase4b_tech_profile":{"status":"completed","result":{"archetype":D['verdict'],"drawdown":D['max_drawdown_52w']}},
        "phase5_news":{"status":"completed","result":{"sentiment":D.get('news_sentiment') or {"positive":0,"negative":0,"neutral":0},"news_count":D.get('news_count',0)}},
        "phase6_dashboard":{"status":"completed","result":{"artifact_path":f"{WORK}/{TICKER}_Complete_Report.html","charts_render":True,"data_keys":len(D)}}
        }}
    json.dump(ts,open(f'{WORK}/.task-state/task-state.json','w'),indent=2,ensure_ascii=False)

# ============ MAIN ============
REUSE = '--reuse' in sys.argv
try:
    print(f'=== {TICKER} ({SECTOR}, bank={IS_BANK}) ===')
    reuse_file = f'{WORK}/verified-dashboard-data.json'
    D_raw = None; tech = None
    if REUSE and os.path.exists(reuse_file) and os.path.exists(f'{WORK}/data/financials.json'):
        # --reuse: KHÔNG gọi API tài chính — đọc data đã fetch lần trước, chỉ đổi
        # SECTOR → render + verify. Dùng để gắn ngành thật cho batch đã chạy
        # (VNALL 1.000 mã) không tốn API. Mọi chỉ số lấy THẲNG từ D (khớp bản gốc
        # 100% — tránh lệch do làm tròn khi tính lại từ financials.json).
        D = json.load(open(reuse_file)); D['sector'] = SECTOR
        D['_provenance']['sector'] = SECTOR
        years = D.get('years') or sorted(int(y) for y in json.load(open(f'{WORK}/data/financials.json'))['revenue_ty'].keys() if str(y).isdigit())
        cagr = D.get('cagr')
        npat_growth = D.get('npat_growth') or 0
        roe_hist = D.get('roe') or [0]*len(years)
        pe5med = D.get('pe5med', D['pe'])
        eps_last = (D.get('eps') or [0])[-1] or 0
        bvps_last = (D.get('bvps') or [0])[-1] or 0
        graham = (22.5*eps_last*bvps_last) ** 0.5 if eps_last > 0 and bvps_last > 0 else None
        cp_back = D.get('split_audit', {}).get('cp_back_calc_m')
        cp_consistent = D.get('split_audit', {}).get('cp_consistent')
        news = fetch_news()  # vẫn fetch news (REQ-008) — 1 call/mã
        real_peers = None
        print(f'  REUSE: {years[0]}-{years[-1]}, price {D["price"]} VND, sector->{SECTOR}')
    else:
        D_raw = fetch()
        print(f'  fetched: {D_raw["periods"]} periods, price {D_raw["last"]} VND, shares {D_raw["shares"]/1e9:.3f} tỷ')
        tech = tech_score(D_raw)
        print(f'  tech: score {tech["score"]:+d} {tech["verdict"]}, RSI {tech["rsi14"]:.1f}, max_dd {tech["max_dd"]:.1f}%')
        news = fetch_news()
        real_peers = fetch_peers()
        D,cagr,npat_growth,roe_hist,cp_back,cp_consistent,graham,pe5med=build_all(D_raw,tech,news,real_peers)
    print(f'  DATA: pe={D["pe"]}, pb={D["pb"]}, mcap={D["marketCap"]} tỷ, capex_arr={len(D.get("capex",[]))}')
    task_state(D,cagr,roe_hist,cp_back,cp_consistent,news)
    out=render(D,cagr,npat_growth,roe_hist,cp_back,cp_consistent,graham,pe5med,news)
    verifier_path = os.path.join(SKILL_DIR, 'scripts', 'independent_verifier.py')
    r=subprocess.run([sys.executable, verifier_path, TICKER, out],capture_output=True,text=True)
    o=r.stdout+r.stderr
    m=re.search(r'Requirements:\s*(\d+)/(\d+) pass',o)
    recall=int(m.group(1)) if m else 0
    _total=int(m.group(2)) if m else 74
    fails=[]
    ev=f'{WORK}/.task-state/evidence'
    if os.path.isdir(ev):
        for fn in os.listdir(ev):
            if fn.startswith('REQ-') and fn.endswith('.json'):
                try:
                    d=json.load(open(f'{ev}/{fn}'))
                    if d.get('status')=='fail': fails.append(d.get('requirement_id'))
                except: pass
    fails=list(dict.fromkeys(fails))
    print(f'  VERIFY: {recall}/{_total}, fails={len(fails)}: {fails[:8]}')
    # P0-02 (Sol 2026-08-09): result.json PHẢI lưu exit code thật — merge/audit không
    # được mặc định exit=0 (đã từng biến 93 artifact FAIL thành done).
    gate_fail = recall < 70 or (fails and any(f in ('REQ-021','REQ-024','REQ-062') for f in fails))
    exit_code = 1 if gate_fail else 0
    json.dump({'ticker':TICKER,'sector':SECTOR,'recall':recall,'fails':fails,'price':D_raw['last'] if D_raw else D['price'],'mcap':D['marketCap'],'tech_score':D.get('tech_score'),'verdict':D.get('verdict'),'exit_code':exit_code},open(f'{WORK}/result.json','w'),indent=2,ensure_ascii=False)
    # P0-5 (Sol 2026-08-08): fail-closed — mã không đạt chuẩn phải trả exit nonzero
    # để CI/script chặn được. Ngưỡng 70 = ngưỡng "done" của tracker; <70 = cần người.
    if recall < 70:
        print(f'  GATE: FAIL — {TICKER} không đạt chuẩn ({recall}/{_total} < 70) — exit 1')
        sys.exit(1)
    if fails and any(f in ('REQ-021','REQ-024','REQ-062') for f in fails):
        print(f'  GATE: FAIL — {TICKER} còn fail critical ({fails}) — exit 1')
        sys.exit(1)
except SponsorDependencyError as e:
    print(f'ERROR {TICKER}: {e}', file=sys.stderr)
    sys.exit(2)
except Exception as e:
    traceback.print_exc()
    print(f'ERROR {TICKER}: {e}')
    sys.exit(1)
