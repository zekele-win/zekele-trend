"""解析：从 TFF 报告 HTML 提取 5 个美股指数期货的 Leveraged Funds 持仓。"""
import re
import html
from datetime import datetime

# code → 市场名开头前缀（兼容 CFTC 历年命名变化）
# ES: "E-MINI S&P 500 -"（近期）→ "E-MINI S&P 500 STOCK INDEX"（2021 前）
# RTY: "RUSSELL E-MINI"（近期）→ "MINI RUSSELL 2000 INDEX"（2021 前）
MARKETS = {
    'ES': ['E-MINI S&P 500'],
    'NQ': ['NASDAQ-100 Consolidated'],
    'RTY': ['RUSSELL E-MINI', 'E-MINI RUSSELL 2000'],
    'VIX_FUT': ['VIX FUTURES'],
    'YM': ['DJIA Consolidated'],
}


def _match_code(name):
    """按前缀匹配市场名 → 代码（排除 MICRO 等衍生合约）。"""
    name = name.strip()
    for code, prefixes in MARKETS.items():
        for p in prefixes:
            if name.startswith(p):
                return code
    return None

# 代码 → 显示名
NAMES = {
    'ES': 'E-MINI S&P 500',
    'NQ': 'NASDAQ-100',
    'RTY': 'Russell 2000',
    'VIX_FUT': 'VIX 期货',
    'YM': '道指 DJIA',
}

_BLOCK = re.compile(
    r'([^\n]{3,90}?)\s*\n\s*CFTC Code[^\n]*?Open Interest is\s+([\d,]+)\s*\n\s*Positions\s*\n\s*([\d, ]+)')
_AS_OF = re.compile(r'Positions as of\s+([A-Za-z]+)\s+(\d{1,2}),\s+(\d{4})')


def parse_tff(text):
    """解析 TFF 报告文本。

    返回 {as_of: 'YYYY-MM-DD' 或 None, markets: {code: {oi, long, short, spreading}}}
    其中 long/short/spreading 是 Leveraged Funds（杠杆基金）分类的持仓。
    """
    txt = html.unescape(re.sub(r'<[^>]+>', ' ', text))

    as_of = None
    m = _AS_OF.search(txt)
    if m:
        try:
            as_of = datetime.strptime('{} {} {}'.format(m.group(1), m.group(2), m.group(3)), '%B %d %Y').strftime('%Y-%m-%d')
        except ValueError:
            as_of = None

    markets = {}
    for mm in _BLOCK.finditer(txt):
        name = mm.group(1).strip()
        code = _match_code(name)
        if not code or code in markets:
            continue
        oi = int(mm.group(2).replace(',', ''))
        nums = [int(x.replace(',', '')) for x in re.findall(r'[\d,]+', mm.group(3))]
        if len(nums) < 11:
            continue
        # 5 个分类各 3 列（Long/Short/Spreading），Leveraged Funds 是第 4 个 → idx 6/7/8
        markets[code] = {
            'oi': oi,
            'long': nums[6],
            'short': nums[7],
            'spreading': nums[8],
        }
    return {'as_of': as_of, 'markets': markets}
