# zekele-trend 方案定稿

## 定位
追踪杠杆基金（对冲基金）在美股指数期货的多空杠杆与净杠杆走势，辅以 VIX 情绪对照。

## 数据源
| 数据 | 来源 | 频率 | 发布时刻（美东） | 端点 |
|---|---|---|---|---|
| 主数据 | CFTC COT — TFF 报告，Leveraged Funds 分类 | 周度（周二截止） | 周五 15:30 ET | 最新 `cftc.gov/dea/futures/financial_lf.htm`；历史 `cftc.gov/sites/default/files/files/dea/cotarchives/YYYY/futures/financial_lfMMDDYY.htm` |
| 辅助 | VIX 现货（每日收盘） | 每日 | 收盘后更新 | FRED `VIXCLS` |

## 市场（TFF 报告内确切命名）
- E-MINI S&P 500 → ES
- NASDAQ-100 Consolidated → NQ
- RUSSELL E-MINI → RTY
- VIX FUTURES → VIX 期货
- DJIA Consolidated → YM（道指）

## 指标
取 Leveraged Funds 分类的 Long / Short / Spreading 三字段，Open Interest（OI）做分母：
- 多头占比 = Long / OI
- 空头占比 = Short / OI
- 净多占比 = (Long − Short) / OI  ← 主线，多空偏向
- 总押注占比 = (Long + Short) / OI  ← 总规模
- 各算历史分位，窗口 5 年
- Spreading 存原始数据，不参与指标（跨期套利，非方向性）
- VIX 不计算占比，直接存指数值本身 + 5 年历史分位

## 呈现
- 每个指数一卡：净多占比主线 + 多头/空头剪刀差副线 + 分位标注
- VIX 现货全局一张（跨市场，市场级情绪对照）
- 顶部状态栏：数据截至日期 + COT 下一期发布倒计时 + 加载状态/重试

## 架构：数据与功能解耦
- **数据更新**（每周/每日）≠ **构建**（生成 html）。两者彻底解耦。
- 数据更新：定时任务全量抓 → 重新生成数据 json → 部署（html 一字不动）
- 功能更新（改样式/图表逻辑）：才动 html → 构建 → 部署
- 数据文件用**固定文件名**（cot.json / vix.json，不带哈希），缓存靠 max-age，不靠改文件名

## 数据流
```
定时任务（本机 cron）
  → 全量抓 CFTC（2021.1 起）+ VIX 全历史
  → 解析 + 计算指标
  → 生成 cot.json / vix.json（覆盖，固定名）
  → 部署到 Cloudflare Pages（html 不动）

浏览器（手机/桌面同）
  → fetch cot.json / vix.json（强缓存期内零网络请求）
  → 渲染图表
```

## 抓取模式：全量，非增量
- 每次定时任务全量抓（从 2021.1 起），不维护「抓到哪天」的状态
- 收益：无状态、幂等、自愈（CFTC 修正历史数据自动生效）、漏跑自动补全

## 缓存策略：强缓存（非协商缓存）
| 文件 | Cache-Control | 说明 |
|---|---|---|
| cot.json | max-age=86400（24h） | 周度数据，24h 延迟可见可接受 |
| vix.json | max-age=28800（8h） | 每日数据，8h 延迟可见可接受 |

- 强缓存期内刷新**零网络交互**（不发起任何请求，直接读本地缓存）
- 用 max-age，不用 ETag/304（304 仍是一次网络往返）
- 浏览器不存 localStorage：数据在 CDN + git 双备份，浏览器只读不存

## 调度（北京时间 CST UTC+8）
| 数据 | cron | 时机 |
|---|---|---|
| COT | `0 6 * * 6`（周六 06:00）+ `0 6 * * 0`（周日 06:00 兜底） | 周五 15:30 ET 发布 = 周六 03:30~04:30 北京，06:00 留 1.5~2.5h 余量 |
| VIX | `0 8 * * *`（每日 08:00） | 收盘后 FRED 更新到次日 04:00~05:00 北京，08:00 留 3~4h 余量 |

- 对准数据发布时刻，不用固定间隔轮询（不空跑）
- 全量抓 + 幂等，cron 漏跑自动自愈，不需严格「一次都不能漏」

## 历史回填与数据规模
- 起点：2021.1（5 年），COT 与 VIX 对齐（时间轴一致，分位窗口一致）
- 规模：5 市场 × 8 字段 × 260 周 ≈ 1 万点，json 几百 KB（gzip 后几十~100KB），10 年才 ~1MB

## 目录
```
cot/      数据侧：采集 + 解析 + 指标 + 历史 json（真相源，git 追踪）
site/     展示侧：看板页面 + 生成脚本 + 部署产物（cot.json / vix.json / html）
jobs/     调度声明
```

## 数据托管
- 不用 CF D1/cron：免费计划 Cron Trigger 仅 10ms CPU，跑不动「下载+解析+入库」
- 备选（本机无法 7×24 在线时）：GitHub Actions schedule（免费 2000 分钟/月），能力等价、不依赖本机开机
