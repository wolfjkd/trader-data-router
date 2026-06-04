# A股数据获取体系 - 快速部署指南
> **Skill名称**：trader-data-router
> **当前版本**：**v3.3.1**（2026-06-04）

> 本skill记录A股T0日内交易员数据获取的完整解决方案
> **创建时间**：2026-05-20
> **适用场景**：新机器部署、重新配置、定时任务搭建

---

## 📊 数据获取架构

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                           A股数据获取体系 (v3.3.1)                               │
├──────────────┬──────────────┬──────────────┬──────────────┬─────────┬───────────┤
│   行情数据    │    公告数据   │    新闻数据   │   大宗商品   │ 深度数据 │ 独有数据   │
├──────────────┼──────────────┼──────────────┼──────────────┼─────────┼───────────┤
│  腾讯接口 ✅  │ ftshare ✅   │ WebSearch ✅ │ 腾讯接口 ✅  │ Wind ✅  │ eltdx ✅  │
│  (毫秒级)    │  (无需Key)   │  (兜底)     │  (无需Key)   │(需API Key)│(通达信协议)│
│  实时快照    │  A股公告     │  财经资讯    │  黄金银油    │财务/资金/ │集合竞价    │
│  【主力源】  │             │             │             │板块/宏观/ │逐笔成交    │
│             │             │             │             │公告RAG/  │F10资料     │
│             │             │             │             │技术指标   │分时/K线    │
└──────────────┴──────────────┴──────────────┴──────────────┴─────────┴───────────┘
```

---

## 🎯 数据类型与数据源

### 1. 行情数据（腾讯接口，开箱即用）

| 数据类型 | 接口地址 | 示例 |
|---------|---------|------|
| A股指数 | `https://qt.gtimg.cn/q=sh000001,sz399001,sz399006` | 上证/深证/创业板 |
| 自选股 | `https://qt.gtimg.cn/q=sh600170,sh603077,sh601868,sh601390,sz000061,sz000560` | 6只自选股 |
| 美股指数 | `https://qt.gtimg.cn/q=usINDU,usIXIC,usINX` | 道指/纳斯达克/标普 |
| 大宗商品 | `https://qt.gtimg.cn/q=hf_GC,hf_SI,hf_CL` | 黄金/白银/原油 |
| 数字货币 | `https://qt.gtimg.cn/q=gb_BTCJPY` | 比特币等 |

**获取方式**：
```bash
# 获取数据（Python）
import subprocess
result = subprocess.run(['curl', '-s', 'https://qt.gtimg.cn/q=sh000001'], capture_output=True, text=True)
```

### 2. 公告数据（ftshare-announcement-data，首选）

**安装**：
```bash
npx openclaw skills install shawn92/ftshare-announcement-data
# 或移动到workbuddy目录
mv ~/.openclaw/workspace/skills/ftshare-announcement-data ~/.workbuddy/skills/
```

**使用**：
```bash
# 单只股票公告历史
python ~/.workbuddy/skills/ftshare-announcement-data/run.py \
  stock-announcements-single-stock-all-periods \
  --stock-code 600170.SH \
  --page 1 --page-size 10

# 全市场某日公告
python ~/.workbuddy/skills/ftshare-announcement-data/run.py \
  stock-announcements-all-stocks-specific-date \
  --start-date 20260520 \
  --page 1 --page-size 20
```

**股票代码格式**：
- 上海：`600170.SH`
- 深圳：`000061.SZ`
- 创业板：`300xxx.SZ`
- 科创板：`688xxx.SH`

### 3. 新闻数据（WebSearch，兜底方案）

```bash
# 公告搜索
"上海建工 600170 公告 今天"
"和邦生物 603077 公告 最新"

# 新闻搜索
"XX股票 最新消息 今天"
"今日财经新闻 20260520"
"AI 科技 最新"
```

### 4. 板块/资金数据（WebSearch备选）

⚠️ akshare东方财富接口被拒，暂无稳定数据源

```bash
# 搜索关键词
"A股涨幅前5板块"
"北上资金 净流入"
"今日市场异动"
```

---
### 5. 东方财富MCP（cn-financial-mcp，v3.1新增，v3.1.1更新）

> **定位**：特色金融数据专用源——提供腾讯接口不覆盖的龙虎榜、北向资金、涨停池等
>
> **项目位置**：`C:\Users\wolfj\WorkBuddy\Claw\trader-finance-hub\cn-financial-mcp\`
>
> **GitHub**：https://github.com/wolfjkd/trader-finance-hub

#### 5.1 可用端点（2026-06-01实测）

| 端点 | AKShare函数 | 状态 | 响应时间 | 说明 |
|------|-----------|------|---------|------|
| 龙虎榜 | `stock_lhb_detail_em` | ✅ 可用 | ~600ms | datacenter.eastmoney.com |
| 北向资金 | `stock_hsgt_hist_em` | ✅ 可用 | ~1000ms | HSGT历史数据 |
| 涨停池 | `stock_zt_pool_em` | ✅ 可用 | ~150ms | 当日涨停板 |
| 行情Sina日线 | `stock_zh_a_daily` | ✅ 可用 | ~400ms | 非实时，收盘后更新 |

| 端点 | 状态 | 原因 |
|------|------|------|
| push2实时行情 | ❌ 被拒 | `stock_zh_a_spot_em` → ConnectionError |
| EM历史K线 | ❌ 被拒 | `stock_zh_a_hist` → ConnectionError |
| EM指数行情 | ❌ 被拒 | `stock_zh_index_spot_em` → ConnectionError |
| EM资金流向 | ❌ 被拒 | `stock_individual_fund_flow` → ConnectionError |
| EM概念板块 | ❌ 被拒 | `stock_board_concept_name_em` → ConnectionError |
| 新浪全量 | ❌ 失效 | `stock_zh_a_spot` → JSONDecodeError(返回HTML) |

#### 5.2 data_router.py 集成（v3.1.1）

```bash
# 健康检测（4端点综合评分）
python data_router.py health
# → eastmoney: 82.0/100 (B级) — 4/4端点可用

# 特色数据查询
python data_router.py northbound    # 北向资金流向
python data_router.py dragontiger   # 龙虎榜（近10天）
python data_router.py limitpool     # 涨停板池

# JSON输出（供脚本调用）
python data_router.py northbound --json
python data_router.py dragontiger --json
```

#### 5.3 架构说明

- **行情主力**：腾讯接口（100分/A级，200ms）——东财不参与实时行情路由
- **东财定位**：B级特色数据源（82分）——龙虎榜/北向资金/涨停池
- **评分逻辑**：可用性40% + 及时性30% + 质量30%，Sina日线天然低及时性（固定20分）
- 基于AKShare（开源），无需API Key

---

### 5.5 同花顺板块数据（v3.2新增）

> THS MCP因Tushare积分不足不可用，改用AKShare内置THS函数。

| 端点 | 函数 | 数据 | 状态 |
|------|------|------|------|
| 概念/行业列表 | stock_board_concept_name_ths | 362概念+90行业 | OK |
| 板块K线 | stock_board_concept_index_ths | 日线OHLCV | OK |
| 板块摘要 | stock_board_concept_summary_ths | 驱动事件/龙头股 | OK |
| 持续新高/新低 | stock_rank_cxg_ths | 技术形态选股 | OK |
| 热门排名 | stock_hot_rank_em | 热门100只 | OK |

### 5.6 全市场综合分析引擎（v3.2新增）

> 模块: trader-finance-hub/src/market_analyzer.py (618行)

| 子模块 | 功能 |
|------|------|
| NewsFetcher | 4源新闻聚合+情感检测+影响度评分 |
| THSDataFetcher | 同花顺板块AKShare后端+批量行情 |
| MarketModels | 四象限(涨幅x共识)+信息熵+情绪时钟 |

CLI: python data_router.py [news|sector|sentiment|report]

---

### 6. Wind深度数据（万得金融，核心补充）

> **定位**：填补腾讯接口无法覆盖的**财务报表、资金流向、板块行情、技术指标、宏观指标**等深度数据空白
>
> **Skill位置**：`C:\Users\wolfj\.workbuddy\skills\wind-mcp-skill\SKILL.md`
>
> **API Key配置文件**：`C:\Users\wolfj\.wind-aifinmarket\config`

#### 5.1 调用方式

```bash
# 基本格式（必须在wind-mcp-skill目录下执行）
WIND_SKILL_DIR="C:/Users/wolfj/.workbuddy/skills/wind-mcp-skill"
node "$WIND_SKILL_DIR/scripts/cli.mjs call <server_type> <tool_name> '<params_json>'
```

**Shell转义注意**：
- **Bash/Git Bash**：外层单引号包裹，内部双引号无需转义
- **PowerShell**：外层单引号 + 内部每个双引号前加 `\` 转义

#### 5.2 核心Server类型（8个）

| server_type | 能力覆盖 | 适用场景 |
|-------------|---------|---------|
| `stock_data` | A股行情+基本面+技术指标+风险 | **主力**：个股深度分析 |
| `global_stock_data` | 港股/美股同上 | 关注但不交易的海外标的 |
| `fund_data` | ETF/基金全维数据 | ETF套利/折溢价监控 |
| `index_data` | 指数/板块行情+PE/PB分位+技术 | 大盘/板块分析 |
| `bond_data` | 债券档案+估值+主体财务 | 宏观对冲参考 |
| `financial_docs` | 公告RAG+财经新闻RAG | **公告/新闻的Wind替代源** |
| `economic_data` | EDB宏观/行业经济指标 | GDP/CPI/PMI等宏观数据 |
| `analytics_data` | NL通用入口(兜底) | 跨域综合查询 |

#### 5.3 常用查询速查表（A股T0交易员高频场景）

**📈 行情快照（结构化字段）**
```bash
# 个股最新价+涨跌幅+成交量
node "$WIND_SKILL_DIR/scripts/cli.mjs" call stock_data get_stock_price_indicators \
  '{"windcode":"600519.SH","indexes":"中文简称,最新成交价,涨跌幅,成交量,换手率,市盈率(TTM),市净率"}'

# 自选股批量 → 需逐只调用（单工具单标的限制）
for code in 600170.SH 603077.SH 601868.SH 601390.SH 000061.SZ 000560.SZ; do
  node "$WIND_SKILL_DIR/scripts/cli.mjs" call stock_data get_stock_price_indicators \
    "{\"windcode\":\"$code\",\"indexes\":\"中文简称,最新成交价,涨跌幅,成交量\"}"
done
```

**📊 K线历史**
```bash
# 日K线（近30个交易日）
node "$WIND_SKILL_DIR/scripts/cli.mjs" call stock_data get_stock_kline \
  '{"windcode":"600170.SH","begin_date":"20260418","end_date":"20260522","count":30}'

# 分钟线（当日逐分钟走势）
node "$WIND_SKILL_DIR/scripts/cli.mjs" call stock_data get_stock_quote \
  '{"windcode":"600170.SH"}'
```

**💰 财务基本面（NL自然语言）**
```bash
# ROE+净利润增速
node "$WIND_SKILL_DIR/scripts/cli.mjs" call stock_data get_stock_fundamentals \
  '{"question":"贵州茅台2024年ROE和净利润增速"}'

# 前十大股东
node "$WIND_SKILL_DIR/scripts/cli.mjs" call stock_data get_stock_equity_holders \
  '{"question":"上海建工600170前十大股东"}'

# 公司基本档案
node "$WIND_SKILL_DIR/scripts/cli.mjs" call stock_data get_stock_basicinfo \
  '{"question":"和邦生物603077公司基本资料、所属行业"}'
```

**📐 技术指标**
```bash
# MACD/KDJ/RSI/BOLL
node "$WIND_SKILL_DIR/scripts/cli.mjs" call stock_data get_stock_technicals \
  '{"question":"中国中铁601390近60日MACD和RSI走势"}'
```

**🏭 板块/指数**
```bash
# 指数PE/PB历史分位
node "$WIND_SKILL_DIR/scripts/cli.mjs" call index_data get_index_fundamentals \
  '{"question":"沪深300指数PE/PB历史分位"}'
```

**📰 公告RAG（ftshare的增强替代）**
```bash
# 个股公告搜索
node "$WIND_SKILL_DIR/scripts/cli.mjs" call financial_docs get_company_announcements \
  '{"query":"上海建工600170最新公告","top_k":5}'

# 财经新闻
node "$WIND_SKILL_DIR/scripts/cli.mjs" call financial_docs get_financial_news \
  '{"query":"A股今日市场热点","top_k":10}'
```

**🌍 宏观指标**
```bash
# 中国CPI/PPI
node "$WIND_SKILL_DIR/scripts/cli.mjs" call economic_data get_economic_data \
  '{"metricIdsStr":"中国CPI同比","freq":"月","beginDate":"20250101","endDate":"20260522"}'
```

#### 5.4 Wind vs 现有数据源分工

| 数据需求 | 首选 | 备选 | 说明 |
|---------|------|------|------|
| 实时价格快照 | **腾讯接口** | Wind `stock_data` | 腾讯毫秒级，Wind有延迟但字段更丰富 |
| 历史K线 | **Wind** | AkShare腾讯K线 | Wind数据质量更高 |
| A股公告 | **ftshare** | **Wind RAG** | ftshare按日期列表，Wind按内容语义搜索 |
| 财经新闻 | WebSearch | **Wind RAG** | Wind新闻RAG质量高 |
| 财务报表/ROE/盈利 | **Wind** | 无 | 只有Wind能取到 |
| 技术指标(MACD/RSI) | **Wind** | 无 | 只有Wind能取到 |
| 板块涨跌/资金流向 | **Wind** `index_data` | WebSearch | Wind可取板块行情+PE分位 |
| 北上资金/资金流 | **Wind** NL | WebSearch | 用analytics_data或NL工具尝试 |
| 宏观指标(GDP/CPI) | **Wind** | WebSearch | Wind EDB数据库 |
| 港股/美股行情 | **Wind** | 腾讯接口 | Wind global_stock_data |

#### 5.5 Wind注意事项

- ⚠️ **有日调用额度**：不要在循环中无节制调用，优先腾讯接口做实时快照
- ⚠️ **单工具单标的**：批量查询需循环调用，不要传逗号分隔多代码
- ⚠️ **命令必须在skill目录下执行**：CLI用相对路径加载资源
- ⚠️ **结果标注合规要求**：使用Wind数据时必须标注「数据来源于万得Wind金融数据服务」
- ✅ **indexes字段只接中文名**：从 `wind-mcp-skill/references/indicators.md` 复制
- ✅ **NL question/query禁止空格**：用标点符号或直接连接替代空格

---

### 6. eltdx通达信行情协议（v3.3新增，独有数据源）

> **定位**：提供腾讯接口无法覆盖的**独有数据**——集合竞价、逐笔成交、F10资料
>
> **项目来源**：https://github.com/electkismet/eltdx/
>
> **许可**：MIT License（免费开源）
>
> **集成文件**：`C:\Users\wolfj\WorkBuddy\Claw\eltdx_integration.py`

#### 6.1 核心优势

| 特性 | eltdx | 腾讯接口 | 说明 |
|------|-------|---------|------|
| 集合竞价数据 | ✅ 有 | ❌ 无 | 开盘前竞价撮合详情 |
| 逐笔成交数据 | ✅ 有 | ❌ 无 | 每笔成交明细（时间/价格/量） |
| F10资料数据 | ✅ 有 | ❌ 无 | 公司基本面/行业/题材 |
| 分时数据 | ✅ 有 | ✅ 有 | 互补：eltdx本地更快 |
| 行情快照 | ✅ 有 | ✅ 有 | 竞争：腾讯是主力源 |

#### 6.2 延迟对比

| 数据源 | 行情快照 | 集合竞价 | 逐笔成交 |
|--------|---------|---------|---------|
| 腾讯接口 | ~200ms | N/A | N/A |
| eltdx | ~130ms | ~115ms | ~150ms |

> eltdx使用通达信私有协议，本地TCP连接，延迟更低

#### 6.3 安装与使用

```bash
# 安装eltdx
pip install eltdx

# 通过data_router.py使用（推荐）
cd C:\Users\wolfj\.workbuddy\skills\trader-data-router

# 集合竞价数据（独有功能）
python data_router.py auction --codes sz000001,sh600000

# 逐笔成交数据（独有功能）
python data_router.py tick --code sz000001 --date 20260604

# F10资料数据（独有功能）
python data_router.py f10 --code 000001

# 分时数据（与腾讯互补）
python data_router.py minute --code sz000001
```

#### 6.4 路由策略（v3.3.1修复）

**竞争性数据类型（quote/index/commodity）**：
- 腾讯作为**主力源**，当得分差≤15分时优先选择腾讯
- 确保行情快照始终使用最稳定的数据源

**独有数据类型（auction/tick/f10）**：
- 仅eltdx提供，无竞争，固定高分（含+10独有加成）

**互补数据类型（minute/k线）**：
- 按评分选择，eltdx本地协议延迟更低有优势

#### 6.5 健康检测

```bash
python data_router.py health
# 输出示例：
# [4/5] 检测eltdx通达信行情协议...
#   [eltdx] 综合评分: 92.5/100
#     - 行情快照: 可用 (134ms)
#     - 集合竞价(独有): 可用 (114ms)
#     - 分时数据: 可用 (126ms)
```

---

## 📚 AkShare可用接口（v1.18.63实测）

> ⚠️ 注意：东方财富接口（push2.eastmoney.com）被拒，但部分腾讯/新浪接口可用

### ✅ 可用接口

| 接口 | 数据类型 | 代码示例 |
|------|---------|---------|
| `stock_zh_a_hist_tx` | 腾讯历史K线 | 见下方 |
| `stock_news_em` | 财经早餐新闻 | 见下方 |

```python
import akshare as ak

# 1. 腾讯历史K线（推荐，无需代理）
df = ak.stock_zh_a_hist_tx(
    symbol='sz000001',      # 股票代码（sz/sz000001格式）
    start_date='20260518',
    end_date='20260520',
    adjust=''               # ''不复权, 'qfq'前复权
)
# 返回字段: date, open, close, high, low, amount

# 2. 财经早餐新闻
df = ak.stock_news_em()
# 返回: 发布时间, 新闻标题, 新闻内容

# 3. 巨潮资讯个股公告
df = ak.stock_zodiac_em(symbol='000001')
```

### ❌ 不可用接口（东方财富被拒）

| 接口 | 原因 | 替代方案 |
|------|------|---------|
| `stock_zh_a_spot_em` | 东方财富被拒 | 腾讯接口curl |
| `stock_zh_index_spot_em` | 东方财富被拒 | 腾讯接口curl |
| `stock_hsgt_*` | 北上资金接口 | WebSearch |

### 🔧 AkShare安装命令

```bash
# 使用阿里云镜像（推荐）
pip install akshare -i http://mirrors.aliyun.com/pypi/simple/ --trusted-host=mirrors.aliyun.com --upgrade
```

---

## 🔄 多源数据智能路由（data_router.py）

> **定位**：自动检测数据源健康状态，评分择优，解决免费接口临时失效问题
>
> **脚本位置**：`C:\Users\wolfj\.workbuddy\skills\trader-data-router\data_router.py`
>
> **依赖**：Python 3.x 标准库（无需额外安装）

### 6.1 核心架构

```
请求 → probe_sources(数据类型)
    │
    ├── ThreadPoolExecutor 并行探测（最多5线程）
    │     ├── TencentAdapter  (行情/指数/大宗商品) 【主力源】
    │     ├── WindAdapter      (深度数据/个股)
    │     ├── FtShareAdapter   (公告)
    │     ├── EastMoneyAdapter (龙虎榜/北向/涨停池)
    │     └── EltdxAdapter     (竞价/逐笔/F10) 【独有源】
    │
    ↓ 每个适配器独立返回 DataSourceResult
    │
    select_best(results, data_type) → 竞争性类型优先主力源，独有类型固定高分
```

### 6.2 评分模型

| 维度 | 权重 | 腾讯标准 | Wind标准 | ftshare标准 | eltdx标准 |
|------|------|---------|---------|------------|----------|
| 可用性 | 40% | 连通且有数据=100 | 连通=100 | 连通=100 | 连通=100 |
| 及时性 | 25~30% | <500ms=100, >5s=10 | <1.5s=100, >10s=10 | <2s=100, >15s=20 | <200ms=100, >5s=20 |
| 质量 | 30~35% | 数据完整度+数值合理 | 有内容且无error=95 | 返回条数≥5=95 | 独有数据=95, 互补=90 |

**等级**：A级≥85 / B级≥70 / C级≥50 / D级<50

**特殊规则**：
- **独有数据源加成**：eltdx的竞价/逐笔/F10功能固定+10分加成（无竞争）
- **主力源优先**：竞争性数据类型（quote/index/commodity），腾讯得分差≤15分时优先选择

### 6.3 CLI命令

```bash
cd C:\Users\wolfj\.workbuddy\skills\trader-data-router

# 健康检测（5个数据源）
python data_router.py health

# 行情数据（自动选最优源，腾讯优先）
python data_router.py quote --codes sh000001 --json        # 行情(JSON)
python data_router.py watchlist --json                     # 自选股(JSON)
python data_router.py compare --code 600170.SH --type quote # 多源对比

# eltdx独有数据（v3.3新增）
python data_router.py auction --codes sz000001,sh600000    # 集合竞价
python data_router.py tick --code sz000001 --date 20260604 # 逐笔成交
python data_router.py f10 --code 000001                    # F10资料
python data_router.py minute --code sz000001               # 分时数据

# 东方财富特色数据
python data_router.py northbound                           # 北向资金
python data_router.py dragontiger                          # 龙虎榜
python data_router.py limitpool                            # 涨停池

# 全市场综合分析
python data_router.py news                                 # 财经要闻
python data_router.py sector                               # 板块四象限
python data_router.py sentiment                            # 情绪时钟
python data_router.py report                               # 综合报告JSON
```

### 6.4 定时任务集成

晚间报告推荐流程：
1. `python data_router.py health` — 确认哪些源活着
2. `python data_router.py quote --json` — 行情JSON
3. `python data_router.py watchlist --json` — 自选股JSON
4. 公告/新闻根据health结果选源，报告标注来源和评分

### 6.5 已知限制

| 限制 | 状态 | 改进方向 |
|------|------|---------|
| Wind一致性检查嵌套JSON | 解析不完美 | 优化envelope提取 |
| 无缓存机制 | 每次实时探测 | 加短时间缓存 |
| eltdx F10资料部分字段为空 | 数据源限制 | 等待eltdx库更新 |
| 东方财富push2接口被拒 | 网络限制 | 仅用datacenter接口 |

---

## 🔄 备用方案（容错策略）

| 数据类型 | 首选 | 备用1 | 备用2 |
|---------|------|-------|-------|
| 行情快照 | **腾讯接口**【主力】 | Wind stock_data | eltdx |
| 集合竞价 | **eltdx**【独有】 | 无 | - |
| 逐笔成交 | **eltdx**【独有】 | 无 | - |
| F10资料 | **eltdx**【独有】 | 无 | - |
| 分时数据 | 腾讯接口 | eltdx | - |
| 历史K线 | **Wind** stock_data | AkShare腾讯K线 | - |
| 公告 | ftshare | Wind financial_docs RAG | WebSearch |
| 新闻 | WebSearch | Wind financial_docs RAG | - |
| 财务/技术指标 | **Wind** | 无 | - |
| 板块/资金/宏观 | **Wind** (index_data/economic_data) | WebSearch | - |
| 龙虎榜/北向/涨停 | **东方财富MCP** | WebSearch | - |

**自动切换逻辑**（两种模式）：

**模式1：智能路由（推荐，使用data_router.py）**
```
并行探测所有候选源 → 评分排序 → 竞争性类型优先主力源 → 独有类型固定高分
命令: python data_router.py health / quote / watchlist / auction / tick / f10 / minute
```

**模式2：链式降级（手动/脚本）**

---

## 📁 配置路径

| 类型 | 路径 |
|------|------|
| Skills目录 | `C:\Users\wolfj\.workbuddy\skills\` |
| Wind MCP Skill | `C:\Users\wolfj\.workbuddy\skills\wind-mcp-skill\` |
| Wind API Key | `C:\Users\wolfj\.wind-aifinmarket\config` |
| Tushare配置（备用） | `C:\Users\wolfj\.workbuddy\config\tushare.json` |
| eltdx集成模块 | `C:\Users\wolfj\WorkBuddy\Claw\eltdx_integration.py` |
| data_router脚本 | `C:\Users\wolfj\.workbuddy\skills\trader-data-router\data_router.py` |
| 定时任务 | WorkBuddy自动化系统 |

---

## 🚀 快速部署步骤

### 新机器部署清单

1. **安装基础依赖**
```bash
pip install akshare
pip install eltdx  # 通达信行情协议（独有数据源）
```

2. **安装核心Skills**
```bash
# ftshare公告（来自clawhub.ai）
npx openclaw skills install shawn92/ftshare-announcement-data

# Wind万得金融（Gitee源，推荐国内）
npx skills add https://gitee.com/wind_info/wind-skills.git --skill wind-mcp-skill -g -y
npx skills add https://gitee.com/wind_info/wind-skills.git --skill wind-find-finance-skill -g -y

# 其他推荐Skills（按需）
npx openclaw skills install openclaw/skills/tencent-finance
npx openclaw skills install sugarforever/01coder-agent-skills/china-stock-analysis
```

3. **配置Wind API Key**
```bash
# 执行open-portal打开开发者中心获取Key
node ~/.workbuddy/skills/wind-mcp-skill/scripts/cli.mjs open-portal
# 拿到Key后配置
node ~/.workbuddy/skills/wind-mcp-skill/scripts/cli.mjs setup-key <YOUR_KEY> --scope global
```

4. **测试数据源**
```bash
# 测试腾讯接口
curl -s "https://qt.gtimg.cn/q=sh000001"

# 测试ftshare
python ~/.workbuddy/skills/ftshare-announcement-data/run.py \
  stock-announcements-single-stock-all-periods \
  --stock-code 600170.SH --page 1 --page-size 1

# 测试Wind（贵州茅台最新价）
node ~/.workbuddy/skills/wind-mcp-skill/scripts/cli.mjs call stock_data get_stock_price_indicators \
  '{"windcode":"600519.SH","indexes":"中文简称,最新成交价,涨跌幅"}'

# 测试eltdx（通达信行情协议）
python -c "import eltdx; print('eltdx安装成功')"

# 测试完整路由系统
cd C:\Users\wolfj\.workbuddy\skills\trader-data-router
python data_router.py health  # 检测所有5个数据源
```

---

## 📝 自选股列表

| 股票名称 | 代码 | 市场 |
|---------|------|------|
| 上海建工 | 600170.SH | 上海 |
| 和邦生物 | 603077.SH | 上海 |
| 中国能建 | 601868.SH | 上海 |
| 中国中铁 | 601390.SH | 上海 |
| 农产品 | 000061.SZ | 深圳 |
| 我爱我家 | 000560.SZ | 深圳 |

---

## ⚠️ 已知限制

| 限制项 | 说明 | 解决方案 |
|-------|------|---------|
| akshare东方财富 | 连接被拒 | 腾讯接口/Wind替代 |
| Tushare积分 | 仅2分，权限低 | 提升积分或Wind替代 |
| 北上资金/板块涨跌 | ~~无稳定接口~~ | **Wind已覆盖**（index_data/economic_data/analytics_data） |
| Wind日调用额度 | 有上限，省着用 | 实时快照优先腾讯接口，深度分析才用Wind |
| Wind单工具单标的 | 批量需循环 | 写for循环逐只调用 |
| 港股/美股数据 | 腾讯接口字段有限 | **Wind global_stock_data已覆盖** |
| eltdx F10资料 | 部分字段为空 | 等待eltdx库更新，或用Wind替代 |
| 东方财富push2接口 | 被拒 | 仅用datacenter接口（龙虎榜/北向/涨停池） |

---

## 🔧 故障排除

### 腾讯接口失败
- 检查网络连接
- 可能是临时故障，5分钟后重试

### ftshare返回空
- 检查日期格式（YYYYMMDD）
- 确认股票代码格式正确（600170.SH）
- 切换Wind financial_docs RAG或WebSearch备用方案

### WebSearch无结果
- 换用不同关键词
- 检查日期是否正确（今天是工作日？）
- 尝试英文关键词

### Wind调用失败
- **KEY_MISSING**：执行 `node ~/.workbuddy/skills/wind-mcp-skill/scripts/cli.mjs open-portal` 重新配置
- **RATE_LIMIT_DAILY**：日额度用完，切换腾讯接口/WebSearch
- **INVALID_PARAMS_JSON**：检查shell转义（Bash单引号/PowerShell反斜杠）
- **NETWORK_ERROR**：等3-5秒后重试
- 确认命令在wind-mcp-skill目录下执行
- 详细错误码处理见 `C:\Users\wolfj\.workbuddy\skills\wind-mcp-skill\SKILL.md` 第7节

---

## 📋 版本变更日志

| 版本 | 日期 | 变更内容 |
|------|------|---------|
| **v3.2** | 2026-06-01 | 全市场综合分析引擎：新增market_analyzer.py（新闻采集/THS板块/四象限/情绪时钟/信息熵）；data_router新增news/sector/sentiment/report命令；MarketAnalyzerAdapter集成 |：新增northbound/dragontiger/limitpool CLI命令；4端点健康探测（行情Sina日线/北向/龙虎/涨停）；评分从D级3分提升至B级82分；SKILL.md第5节实测端点可用性表 |
| **v3.1** | 2026-06-01 | 新增东方财富MCP（cn-financial-mcp）集成（第5节）；data_router.py新增EastMoneyAdapter；WorkBuddy MCP配置更新；GitHub trader-finance-hub项目初始化 |
| **v3.0** | 2026-05-22 | 新增 `data_router.py` 多源智能路由（783行）；SKILL.md新增第6节；容错策略升级为智能路由模式 |
| **v2.0** | 2026-05-22 | 整合Wind万得金融能力（第5节，~130行）：8个server_type、速查表、分工对照表；架构从4列扩展为5列 |
| **v1.0** | 2026-05-20 | 初始版本：腾讯接口+ftshare公告+WebSearch+AakShare数据源体系（262行） |

---

*本skill由WorkBuddy生成并维护，当前版本：**v3.0***
