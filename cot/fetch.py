"""采集：下载 CFTC TFF 报告（最新 + 历史归档）与 FRED VIX 数据。

数据源：
- TFF 最新: https://www.cftc.gov/dea/futures/financial_lf.htm
- TFF 历史: https://www.cftc.gov/sites/default/files/files/dea/cotarchives/{year}/futures/financial_lf{mmddyy}.htm
- VIX:      https://fred.stlouisfed.org/graph/fredgraph.csv?id=VIXCLS（全历史 CSV，无需 key）
"""
import os
import time
import subprocess
import urllib.request
from datetime import date, timedelta

_UA = {'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko)'}

TFF_LATEST = 'https://www.cftc.gov/dea/futures/financial_lf.htm'
TFF_ARCHIVE = 'https://www.cftc.gov/sites/default/files/files/dea/cotarchives/{year}/futures/financial_lf{mmddyy}.htm'
FRED_VIX = 'https://fred.stlouisfed.org/graph/fredgraph.csv?id=VIXCLS'

# 回填起点（与 PLAN.md 一致：2021.1）
BACKFILL_START = date(2021, 1, 1)


def _get(url, retries=3):
    """GET 请求，带重试 + 退避（网络抖动/临时限流时自动重试）。返回解码后的文本。"""
    last_err = None
    for i in range(retries):
        try:
            req = urllib.request.Request(url, headers=_UA)
            with urllib.request.urlopen(req, timeout=30) as r:
                return r.read().decode('utf-8', errors='replace')
        except Exception as e:
            last_err = e
            time.sleep(2 * (i + 1))  # 退避 2s / 4s / 6s
    raise RuntimeError('GET 失败: {}'.format(url)) from last_err


def fetch_latest_tff():
    """下载最新一期 TFF 报告（HTML）。"""
    return _get(TFF_LATEST)


def fetch_tff_by_date(d):
    """按持仓截止日（周二）下载 TFF 报告归档。返回 HTML 或 None（当天无报告）。"""
    url = TFF_ARCHIVE.format(year=d.year, mmddyy=d.strftime('%m%d%y'))
    try:
        return _get(url)
    except Exception:
        return None


def fetch_tff_by_date_cached(d, cache_dir):
    """下载归档到本地缓存（归档不可变，已存在则跳过），返回 HTML 或 None。"""
    os.makedirs(cache_dir, exist_ok=True)
    fname = os.path.join(cache_dir, 'financial_lf{}.htm'.format(d.strftime('%m%d%y')))
    if os.path.exists(fname):
        with open(fname, encoding='utf-8', errors='replace') as f:
            return f.read()
    html = fetch_tff_by_date(d)
    if html:
        with open(fname, 'w', encoding='utf-8') as f:
            f.write(html)
    return html


def fetch_vix_csv():
    """下载 FRED VIXCLS 全历史 CSV（用 curl：FRED 会拦截 urllib 的 TLS 指纹）。"""
    out = subprocess.run(
        ['curl', '-s', '--max-time', '30', FRED_VIX],
        capture_output=True, text=True, timeout=45)
    if out.returncode != 0 or not out.stdout:
        raise RuntimeError('VIX 下载失败: curl rc={}'.format(out.returncode))
    return out.stdout


def tuesdays_since(start, end=None):
    """生成 [start, end] 区间内的所有周二（持仓截止日）。end 默认本周二。"""
    end = end or (date.today() - timedelta(days=(date.today().weekday() - 1) % 7))
    d = start
    while d.weekday() != 1:  # 1 = Tuesday
        d += timedelta(days=1)
    out = []
    while d <= end:
        out.append(d)
        d += timedelta(days=7)
    return out
