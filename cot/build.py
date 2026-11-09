"""数据侧主入口：全量抓取 COT + VIX → 解析 → 计算指标 + 分位 → 生成部署产物。

用法：python3 build.py
产物：
- cot/history/raw_cot.json  真相源（原始持仓 + 占比，按市场 → 日期）
- cot/history/vix.json      真相源（VIX 序列）
- site/cot.json             部署产物（前端 fetch，含分位）
- site/vix.json             部署产物（前端 fetch）
"""
import os
import sys
import json

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from fetch import fetch_latest_tff, fetch_tff_by_date_cached, fetch_vix_csv, tuesdays_since, BACKFILL_START
from parse import parse_tff, MARKETS, NAMES
from metric import compute_ratios, percentile_rank

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # 项目根
HISTORY_DIR = os.path.join(BASE, 'cot', 'history')
ARCHIVE_DIR = os.path.join(HISTORY_DIR, 'archive')
SITE_DIR = os.path.join(BASE, 'site')


def build_cot():
    """全量抓取 + 解析 COT，返回 {markets: {code: {date: {oi,long,short,spreading}}}, as_of}。"""
    data = {code: {} for code in MARKETS.keys()}
    # 1. 历史归档（5 年，本地缓存，已下载的跳过）
    for d in tuesdays_since(BACKFILL_START):
        htm = fetch_tff_by_date_cached(d, ARCHIVE_DIR)
        if not htm:
            continue
        parsed = parse_tff(htm)
        if not parsed['as_of'] or not parsed['markets']:
            continue
        for code, m in parsed['markets'].items():
            data[code][parsed['as_of']] = m
    # 2. 最新一期（每次重新下载，覆盖/补充）
    parsed = parse_tff(fetch_latest_tff())
    as_of = parsed['as_of']
    if as_of:
        for code, m in parsed['markets'].items():
            data[code][as_of] = m
    return {'markets': data, 'as_of': as_of}


def main():
    os.makedirs(HISTORY_DIR, exist_ok=True)
    os.makedirs(SITE_DIR, exist_ok=True)

    # ---- COT ----
    cot = build_cot()
    raw_cot = {}
    out_cot = {'as_of': cot['as_of'], 'markets': {}}
    for code in MARKETS.keys():
        series = cot['markets'][code]
        dates = sorted(series.keys())
        raw_cot[code] = {d: series[d] for d in dates}
        # 计算占比，构建完整序列
        out_series = []
        for d in dates:
            m = series[d]
            ratios = compute_ratios(m['oi'], m['long'], m['short'])
            out_series.append({'date': d, **m, **ratios})
        # 最新一期的分位（用此前全部历史做分布，不含最新自身）
        latest = out_series[-1] if out_series else None
        percentiles = {}
        if latest:
            hist = out_series[:-1]
            for key in ('long_pct', 'short_pct', 'net_pct', 'gross_pct'):
                vals = [r[key] for r in hist if r.get(key) is not None]
                percentiles[key] = percentile_rank(vals, latest.get(key))
        out_cot['markets'][code] = {
            'name': NAMES[code],
            'series': out_series,
            'latest': latest,
            'percentiles': percentiles,
        }
    with open(os.path.join(HISTORY_DIR, 'raw_cot.json'), 'w') as f:
        json.dump(raw_cot, f, ensure_ascii=False, indent=2)
    with open(os.path.join(SITE_DIR, 'cot.json'), 'w') as f:
        json.dump(out_cot, f, ensure_ascii=False, indent=2)

    # ---- VIX ----
    csv = fetch_vix_csv()
    vix_series = []
    for line in csv.splitlines()[1:]:  # 跳过表头 observation_date,VIXCLS
        parts = line.split(',')
        if len(parts) != 2 or parts[1] in ('.', ''):
            continue
        vix_series.append({'date': parts[0], 'value': float(parts[1])})
    # 只保留 5 年（与 COT 对齐起点）
    start_iso = BACKFILL_START.isoformat()
    vix_series = [p for p in vix_series if p['date'] >= start_iso]
    vix_pct = None
    if vix_series:
        vix_pct = percentile_rank([p['value'] for p in vix_series[:-1]], vix_series[-1]['value'])
    out_vix = {
        'as_of': vix_series[-1]['date'] if vix_series else None,
        'latest': vix_series[-1] if vix_series else None,
        'percentile': vix_pct,
        'series': vix_series,
    }
    with open(os.path.join(HISTORY_DIR, 'vix.json'), 'w') as f:
        json.dump(vix_series, f, ensure_ascii=False, indent=2)
    with open(os.path.join(SITE_DIR, 'vix.json'), 'w') as f:
        json.dump(out_vix, f, ensure_ascii=False, indent=2)

    # ---- 摘要 ----
    print('COT 截至 {}，市场 {} 个'.format(out_cot['as_of'], len(out_cot['markets'])))
    for code, mk in out_cot['markets'].items():
        latest = mk['latest']
        if latest:
            pct = mk['percentiles'].get('net_pct')
            pct_s = '{:.0f}'.format(pct) if pct is not None else '-'
            print('  {}: {} 期，最新 {} 净多 {:+.1f}%（分位 {}）'.format(
                code, len(mk['series']), latest['date'], latest['net_pct'], pct_s))
    if out_vix['latest']:
        vp = out_vix['percentile']
        print('VIX 截至 {}，最新 {:.2f}（分位 {}）'.format(
            out_vix['as_of'], out_vix['latest']['value'], '{:.0f}'.format(vp) if vp is not None else '-'))


if __name__ == '__main__':
    main()
