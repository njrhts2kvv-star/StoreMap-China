"""
Use AMap reverse geocoding to fill missing province/city/district fields
for store master: 各品牌爬虫数据_Final/all_brands_offline_stores_cn_enriched_with_ba.csv

Fields filled when missing:
- province_name
- city_name (optional, if present)
- district_name
- province_code (from adcode)
- city_code (from adcode city part)
- district_code (adcode)
- city_id (same as city_code)

Requires: env var AMAP_WEB_KEY or VITE_AMAP_KEY.
Writes output to: 各品牌爬虫数据_Final/all_brands_offline_stores_cn_enriched_with_ba_amap.csv
Caches results in: tmp_amap_revgeo_cache.jsonl

Note: This will make many HTTP requests if run on all missing rows. Consider batching or
limiting. The script skips rows already in cache (by rounded lat,lng key).
"""
import os
import json
import time
from pathlib import Path
import pandas as pd
import requests
try:
    from tqdm import tqdm
except ImportError:
    def tqdm(x, *args, **kwargs):
        return x

BASE_DIR = Path(__file__).resolve().parent.parent
INPUT = BASE_DIR / '各品牌爬虫数据_Final/all_brands_offline_stores_cn_enriched_with_ba.csv'
OUTPUT = BASE_DIR / '各品牌爬虫数据_Final/all_brands_offline_stores_cn_enriched_with_ba_amap.csv'
CACHE = BASE_DIR / 'tmp_amap_revgeo_cache.jsonl'

API_KEY = os.getenv('AMAP_WEB_KEY') or os.getenv('VITE_AMAP_KEY')
if not API_KEY:
    raise SystemExit('Missing AMAP_WEB_KEY / VITE_AMAP_KEY')

print('Loading', INPUT)
df = pd.read_csv(OUTPUT if OUTPUT.exists() else INPUT, low_memory=False)
print('Loaded', len(df), 'rows from', 'OUTPUT' if OUTPUT.exists() else 'INPUT')
for col in ['province_name','city_name','district_name','province_code','city_code','district_code','city_id']:
    if col not in df.columns:
        df[col] = None
    df[col] = df[col].astype(object)

cache = {}
if CACHE.exists():
    with open(CACHE, 'r', encoding='utf-8') as f:
        for line in f:
            try:
                rec = json.loads(line)
                cache[rec['key']] = rec['data']
            except Exception:
                pass
print('Cache entries:', len(cache))

def is_placeholder(series):
    return (
        series.isna()
        | (
            series.astype(str)
            .str.strip()
            .isin(['', '[]', '[]00', 'nan', 'None', '未知'])
        )
    )

mask_missing = is_placeholder(df['district_name'])
candidates = df[mask_missing].copy()
print('Missing district_name rows:', len(candidates))

session = requests.Session()
session.verify = False


def round_key(lat, lng):
    return f"{round(float(lat),5)},{round(float(lng),5)}"


def revgeo(lat, lng):
    key = round_key(lat, lng)
    if key in cache:
        return cache[key]
    url = 'https://restapi.amap.com/v3/geocode/regeo'
    params = {
        'location': f"{lng},{lat}",
        'key': API_KEY,
        'radius': 1000,
        'extensions': 'base',
        'batch': 'false',
        'output': 'json',
    }
    for attempt in range(3):
        try:
            resp = session.get(url, params=params, timeout=8)
            resp.raise_for_status()
            data = resp.json()
            if data.get('status') != '1' or 'regeocode' not in data:
                continue
            addr = data['regeocode'].get('addressComponent', {})
            result = {
                'province_name': addr.get('province'),
                'city_name': addr.get('city') if addr.get('city') else addr.get('province'),
                'district_name': addr.get('district'),
                'district_code': addr.get('adcode'),
            }
            cache[key] = result
            with open(CACHE, 'a', encoding='utf-8') as f:
                f.write(json.dumps({'key': key, 'data': result}, ensure_ascii=False) + '\n')
            return result
        except Exception:
            if attempt == 2:
                return None
            time.sleep(0.5)

filled = 0
skipped = 0
for idx, row in tqdm(candidates.iterrows(), total=len(candidates), desc='revgeo', ncols=90):
    lat = row.get('lat_gcj02') or row.get('lat')
    lng = row.get('lng_gcj02') or row.get('lng')
    if pd.isna(lat) or pd.isna(lng):
        skipped += 1
        continue
    res = revgeo(lat, lng)
    if not res:
        skipped += 1
        continue
    # ensure cols
    for col in ['province_name','city_name','district_name','district_code','city_code','province_code','city_id']:
        if col not in df.columns:
            df[col] = None
    def is_empty(val):
        """Treat NaN, empty string, and placeholder strings as empty."""
        if pd.isna(val):
            return True
        sval = str(val).strip()
        return sval == '' or sval in {'[]', '[]00', 'nan', 'None', '未知'}
    if is_empty(df.at[idx, 'province_name']):
        df.at[idx, 'province_name'] = res.get('province_name')
    if 'city_name' in df.columns and is_empty(df.at[idx, 'city_name']):
        df.at[idx, 'city_name'] = res.get('city_name')
    if is_empty(df.at[idx, 'district_name']):
        df.at[idx, 'district_name'] = res.get('district_name')
    if is_empty(df.at[idx, 'district_code']):
        dc = res.get('district_code')
        if dc is not None:
            dc = str(dc).split('.')[0]
        df.at[idx, 'district_code'] = dc
    adcode = res.get('district_code')
    if adcode is not None:
        adcode = str(adcode).split('.')[0]
    citycode = adcode[:4] + '00' if adcode and len(adcode) >= 4 else None
    if is_empty(df.at[idx, 'city_id']) and citycode:
        df.at[idx, 'city_id'] = citycode
    if 'city_code' in df.columns and is_empty(df.at[idx, 'city_code']) and citycode:
        df.at[idx, 'city_code'] = citycode
    if 'province_code' in df.columns and is_empty(df.at[idx, 'province_code']) and adcode:
        df.at[idx, 'province_code'] = adcode[:2] + '0000'
    filled += 1
    if filled % 200 == 0:
        print(f'filled {filled}, cache {len(cache)}')
        df.to_csv(OUTPUT, index=False)
        time.sleep(0.2)

print('Filled rows:', filled, 'skipped:', skipped)
df.to_csv(OUTPUT, index=False)
print('Saved to', OUTPUT)
