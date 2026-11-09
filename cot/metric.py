"""指标：计算四项占比与历史分位。"""


def compute_ratios(oi, long, short):
    """由 OI/多头/空头 计算四项占比（单位 %）。返回 {long_pct, short_pct, net_pct, gross_pct}。"""
    if not oi or oi <= 0:
        return {'long_pct': None, 'short_pct': None, 'net_pct': None, 'gross_pct': None}
    return {
        'long_pct': long / oi * 100,
        'short_pct': short / oi * 100,
        'net_pct': (long - short) / oi * 100,
        'gross_pct': (long + short) / oi * 100,
    }


def percentile_rank(values, current):
    """当前值在历史序列中的百分位（0~100）。

    第 X 百分位 = 高于 X% 的历史值。values 不含 current 自身。
    """
    if not values:
        return None
    below = sum(1 for v in values if v < current)
    return below / len(values) * 100
