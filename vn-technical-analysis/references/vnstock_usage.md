# vnstock Usage — Code fetch data giá VN

## Mục lục
1. [Cài đặt](#install)
2. [Fetch giá cổ phiếu](#stock)
3. [Fetch index (VNINDEX/VN30)](#index)
4. [Bẫy đơn vị](#unit)
5. [Xử lý NaN](#nan)

---

## Cài đặt <a name="install"></a>

```bash
pip install vnstock --upgrade
```

⚠️ **API breaking change (31/08/2025):** Lớp `Vnstock` cũ đã deprecated. Dùng `vnstock.api.quote.Quote` thay thế.

```python
# CŨ (deprecated)
from vnstock import Vnstock
stock = Vnstock().stock(symbol='HPG', source='VCI')

# MỚI (hiện tại)
from vnstock.api.quote import Quote
q = Quote(symbol='HPG', source='VCI')
```

---

## Fetch giá cổ phiếu <a name="stock"></a>

```python
from vnstock.api.quote import Quote

q = Quote(symbol='HPG', source='VCI')
df = q.history(
    start='2025-06-22',
    end='2026-06-21',
    interval='1W'  # '1D' daily, '1W' weekly
)
print(df.columns)  # ['time', 'open', 'high', 'low', 'close', 'volume']
print(df.head())
```

**Sources available:**
- `VCI` — Vietcombank Securities (ưu tiên #1, ổn định)
- `TCBS` — Techcombank Securities (backup)
- `DNSE` — DNSE Securities (backup)

---

## Fetch index (VNINDEX/VN30) <a name="index"></a>

Index dùng cùng class `Quote` với symbol là tên index:

```python
q_vni = Quote(symbol='VNINDEX', source='VCI')
df_vni = q_vni.history(start='2025-06-22', end='2026-06-21', interval='1W')

q_vn30 = Quote(symbol='VN30', source='VCI')
df_vn30 = q_vn30.history(start='2025-06-22', end='2026-06-21', interval='1W')
```

**Index symbols phổ biến:**
- `VNINDEX` — VN-Index (toàn thị trường HOSE)
- `VN30` — VN30 (30 cổ phiếu vốn hóa lớn)
- `HNXINDEX` — HNX-Index
- `UPCOMINDEX` — UPCOM-Index
- `HNX30` — HNX30

---

## Bẫy đơn vị <a name="unit"></a>

⚠️ **vnstock trả giá bằng NGHÌN đồng, KHÔNG phải đồng.**

```python
df = q.history(...)
print(df['close'].iloc[-1])  # 23.60 ← đây là 23,600 đ, KHÔNG phải 23.60 đ

# Quy đổi về đồng khi cần
df['close_vnd'] = df['close'] * 1000
df['open_vnd'] = df['open'] * 1000
# ...
```

**Lý do:** Format nghìn đồng giúp số gọn khi hiển thị, nhưng gây nhầm lẫn nếu không biết. Khi tính indicators (RSI, MACD), dùng raw values OK vì indicators dùng tỷ lệ (returns), không phụ thuộc đơn vị tuyệt đối. Nhưng khi hiển thị "giá hiện tại 23,600 đ" → phải ×1000.

---

## Xử lý NaN <a name="nan"></a>

Tuần cuối cùng thường có NaN (tuần chưa kết thúc). Bỏ trước khi tính:

```python
df = df.dropna(subset=['close'])
# Hoặc fill bằng close của tuần trước:
# df['close'] = df['close'].fillna(method='ffill')
```

**Kiểm tra data quality:**
```python
print(f"Rows: {len(df)}")
print(f"NaN count: {df[['open','high','low','close']].isna().sum().sum()}")
print(f"Date range: {df['time'].min()} → {df['time'].max()}")
```

---

## Export sang JSON để embed trong HTML

```python
import json
candles = []
for _, r in df.iterrows():
    candles.append({
        'date': r['time'].strftime('%Y-%m-%d'),
        'o': int(r['open'] * 1000),  # quy đổi đồng
        'h': int(r['high'] * 1000),
        'l': int(r['low'] * 1000),
        'c': int(r['close'] * 1000),
        'v': int(r['volume'])
    })
with open('hpg_data.json', 'w') as f:
    json.dump(candles, f)
```

---

## Troubleshooting

| Lỗi | Nguyên nhân | Sửa |
|---|---|---|
| `KeyError: 'data'` ở module Company | VCI API thay đổi | Upgrade: `pip install vnstock --upgrade` |
| `cannot convert float NaN to integer` | Tuần cuối NaN | `df.dropna(subset=['close'])` |
| `ImportError: cannot import name 'Index'` | Đã đổi API | Dùng `Quote(symbol='VNINDEX')` thay vì class Index |
| Authentication failed | Token hết hạn | Upgrade vnstock, sẽ tự re-auth |
