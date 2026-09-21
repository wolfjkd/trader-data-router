# trader-data-router

> **⚠️ 已归档（2026-09-21）**：本项目已由 **tradex-hub**（A股数据中台）功能取代，**不再持续维护/更新**。本仓库作为 A股数据获取的历史 CLI 方案保留存档。新项目请使用 tradex-hub 或 `tradex-add-datasource` 项目级 skill。

<p align="center">
  <strong>A股轻量级多源数据获取 CLI</strong><br>
  <i>腾讯直连 · eltdx 通达信协议 · 数据源健康评分</i>
</p>

---

## 这是什么？

**trader-data-router** 是一个面向 A股交易员的轻量数据获取命令行工具，提供：
- 通过**腾讯直连接口**快速获取实时行情（毫秒级）
- 通过 **eltdx 通达信协议**获取 K线/分时/集合竞价/逐笔/F10
- 通过 **tradex-hub 的 astock_signals** 复用资金流、龙虎榜、行业、可转债、涨停板等深度数据
- **数据源健康检测与评分**，异常时自动标注并降级

> **定位说明**：本项目是多源直连模式的 CLI 轻量方案。**tradex-hub**（同一作者出品的数据中台）提供了更完整的 SmartRouter 多源融合、自动健康分、限流防护、REST/MCP 双端点能力，且已包含本项目绝大部分数据能力。**除非你需要一个不依赖中台进程的裸 CLI，否则建议直接使用 tradex-hub。**

## 快速开始

```bash
git clone https://github.com/wolfjkd/trader-data-router.git
cd trader-data-router

# 健康检测（自动探测可用数据源并评分）
python data_router.py health

# 实时行情（腾讯直连）
python data_router.py quote --codes sh000001,sz399001,sz399006
python data_router.py quote --codes sh600519 --json   # JSON 输出供脚本调用

# 自选股（编辑 WATCHLIST 后）
python data_router.py watchlist

# 多源对比
python data_router.py compare --code 600519.SH --type quote
```

## 依赖说明

| 依赖 | 必需 | 说明 |
|------|------|------|
| Python 3.10+ | 必装 | 核心脚本运行环境 |
| 腾讯财经接口 | 无需安装 | 国内直连 `qt.gtimg.cn` |
| **eltdx**（可选但推荐） | `pip install eltdx` | 通达信私有协议 K线/分时/逐笔/F10 |
| **tradex-hub**（可选，推荐装） | 见下 | 提供 astsignals 深度命令行（资金流/龙虎榜/行业/概念/ETF/可转债/涨停板） |

> **astock_signals 数据来源**：`fundflow`/`northbound`/`dragon`/`concept`/`industry`/`etf`/`cb`/`tickstore`/`board` 这些命令复用 tradex-hub 的 `astock_signals` 模块。需安装 tradex-hub 或将 `tradex-hub/tradex/src` 加入 `PYTHONPATH`；若未安装，这些命令会报 `未找到 astock_signals`。详见 [SKILL.md](./SKILL.md)。

## 数据源覆盖矩阵

| 数据类型 | 免费源 | 付费/增强源 |
|---------|--------|-----------|
| 实时行情快照 | ✅ 腾讯接口 | Wind / eltdx |
| 历史K线 | ✅ eltdx 通达信协议 | Wind |
| 分时数据 | ✅ eltdx 通达信协议 | - |
| 集合竞价 | ✅ eltdx 通达信协议 | - |
| 逐笔成交 | ✅ eltdx 通达信协议 | - |
| F10 公司资料 | ✅ eltdx 通达信协议 | Wind |
| A股公告 | ✅ ftshare (结构化) | Wind RAG |
| 财经新闻 | WebSearch | Wind RAG |
| 财务报表/ROE | - | ✅ Wind |
| 技术指标(MACD) | - | ✅ Wind |
| 资金流/龙虎榜/行业/概念 | ✅ astock_signals（需 tradex-hub） | Wind |
| 涨停板速报 | ✅ astock_signals | - |
| 大宗商品 | ✅ 腾讯接口 | - |
| 美股指数 | ✅ 腾讯接口 | Wind global_stock |

### 已知的数据源可用性注意

- **东财 push2 系列接口**（fundflow/board 的部分上游）存在被限风险，实际运行时可能返回 `RemoteDisconnected`（远端关闭连接）。这是东方财富风控所致，并非本项目 bug，且本项目对该类命令会稳定地降级返回空/提示。
- **Wind** 需独立订阅 API Key，且单工具单标的、有日调用额度，省着用。
- **北向资金** 自 2024-08-19 起官方停止实时披露，相关命令可能只有历史缓存数据，属上游停更。

## 进阶配置

- Wind / ftshare / Wind RAG 的安装与 API Key 配置，详见 [SKILL.md](./SKILL.md)。
- 本 skill 已集成到 WorkBuddy skill 体系：`~/.workbuddy/skills/trader-data-router/`，可直接被 AI Agent 调用。

## 使用场景

### 场景1：轻量实时行情脚本

```bash
python data_router.py quote --codes sh000001,sh600519 --json
```

### 场景2：程序化接入

```python
import subprocess, json
r = subprocess.run(
    ['python', 'data_router.py', 'quote', '--codes', 'sh600519', '--json'],
    capture_output=True, text=True
)
data = json.loads(r.stdout)
print(data['best_source'], data['data'])
```

### 场景3：数据源健康巡检

```bash
python data_router.py health
```

## 文件说明

| 文件 | 用途 |
|------|------|
| `data_router.py` | 多源获取 CLI（核心执行文件） |
| `SKILL.md` | 完整文档：数据源配置、API 速查、部署步骤、故障排除 |
| `README.md` | 本文件，项目介绍与快速上手 |

## 版本历史

| 版本 | 日期 | 变更 |
|------|------|------|
| v3.7.0 | 2026-08-06 | 新增 `board` 命令（涨停板速报），Router 扩展至 18 个命令 |
| v3.6.0 | 2026-06-24 | 新增 `etf` / `cb` / `tickstore` 命令，Router 扩展至 17 个 |
| v3.5.0 | 2026-06-24 | 补齐 5 个薄壳 CLI 命令（fundflow/northbound/dragon/concept/industry），9→14 命令 |
| v3.4.0 | 2026-06-17 | 集成 eltdx 通达信数据源；新增 kline/minute/auction/tick/f10 |
| v3.1 | 2026-06-01 | 更名 trader-data-router；东财适配器重构；集成全市场分析引擎 |
| v3.0 | 2026-05-22 | 新增 data_router.py 多源智能路由 |
| v2.0 | 2026-05-22 | 整合 Wind 万得金融 8 大能力 |
| v1.0 | 2026-05-20 | 初始版：腾讯+ftshare+AkShare 数据源体系 |

## License

MIT License — 自由使用、修改、分发。

## 致谢

- [腾讯财经](https://qt.gtimg.cn/) — 免费实时行情接口
- [Wind万得金融](https://www.wind.com.cn/) — 专业金融数据
- [AkShare](https://akshare.akfamily.xyz/) — Python 财经数据接口库
- [eltdx](https://pypi.org/project/eltdx/) — 通达信私有协议客户端
- **tradex-hub** — 本项目最重要的数据依赖（astock_signals 深度数据）

---

<p align="center">
  <sub>Made with trading discipline by wolfjkd · 已归档</sub>
</p>