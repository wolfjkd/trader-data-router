# trader-data-router

<p align="center">
  <strong>A股数据获取体系 + 数据源检测</strong><br>
  <i>多源数据 · 健康评分 · 择优输出</i>
</p>

---

## ✨ 这是什么？

**trader-data-router** 是一个面向 A股交易员的数据获取 CLI 工具，提供统一入口查询多个数据源，并对数据源做健康检测和评分。

| 能力 | 说明 |
|------|------|
| 📊 **多数据源** | 腾讯实时行情、Wind 深度数据、ftshare 公告、eltdx 通达信协议 |
| 🔄 **数据源检测** | `data_router.py health` 自动探测数据源可用性并评分 |
| ⚡ **并行探测** | 多线程同时请求多个数据源 |
| 🛡️ **故障降级** | 某个源异常时，报告会标注状态并给出可用备选 |

### 核心架构

```
请求 → 并行探测(腾讯 + Wind + ftshare + eltdx) → 评分排序 → 输出结果
                                              ↓
                                    某源异常？标注状态并继续
```

## 🚀 快速开始（3步）

### 1. 下载

```bash
git clone https://github.com/wolfjkd/trader-data-router.git
cd trader-data-router
```

### 2. 健康检测

```bash
python data_router.py health
```

预期输出：
```
====================================================================
    数据源健康检测  2026-05-22 10:30:00
====================================================================

[1/3] 检测腾讯行情接口...
  [+] [TENCENT] 评分: 100.0/100 (A级)
     响应时间: 196ms
     可用性: 100 | 及时性: 100 | 质量: 100

[2/3] 检测Wind万得...
  [!] Wind未安装（路径不存在: ...）

[3/3] 检测FTShare公告...
  [+] [FTSHARE] 评分: 88.0/100 (B级)
     响应时间: 1800ms
     ...

====================================================================
    汇总
====================================================================
数据源       状态      评分      响应       等级
--------------------------------------------------------------------
tencent        OK    100.0     196ms       A
wind           FAIL    0.0      N/A        D  
ftshare        OK     88.0   1800ms       B  

[*] 最佳数据源: tencent（评分 100.0, 等级 A）
```

### 3. 查行情

```bash
# 三大指数
python data_router.py quote --codes sh000001,sz399001,sz399006

# 自选股（修改WATCHLIST后）
python data_router.py watchlist

# JSON输出（供脚本调用）
python data_router.py quote --codes sh600519 --json

# 多源对比
python data_router.py compare --code 600519.SH --type quote

# eltdx 通达信数据源（K线/分时/集合竞价/逐笔/F10）
python data_router.py kline --code 601868 --period day --count 100
python data_router.py minute --code 601868
python data_router.py auction --code 601868
python data_router.py tick --code 601868 --date 20260617 --count 1000
python data_router.py f10 --code 601868
```

## 📁 文件说明

| 文件 | 用途 |
|------|------|
| `SKILL.md` | 完整文档：数据源配置、API速查表、部署步骤、故障排除 |
| `data_router.py` | 多源数据路由脚本（核心执行文件） |
| `README.md` | 本文件，项目介绍和快速上手 |

## ⚙️ 配置你的自选股

编辑 `data_router.py` 中的 `WATCHLIST` 列表：

```python
WATCHLIST = [
    ("sh600519", "贵州茅台"),
    ("sz000001", "平安银行"),
    # 添加你关注的股票...
]
```

格式：`("sh" + 6位代码, "名称")` — 上海以`sh`开头，深圳以`sz`开头。

## 📊 数据源覆盖矩阵

| 数据类型 | 免费源 | 付费增强源 |
|---------|--------|-----------|
| 实时行情快照 | ✅ 腾讯接口 | Wind (字段更丰富) / eltdx |
| 历史K线 | ✅ eltdx 通达信协议 | Wind (质量更高) |
| 分时数据 | ✅ eltdx 通达信协议 | - |
| 集合竞价 | ✅ eltdx 通达信协议 | - |
| 逐笔成交 | ✅ eltdx 通达信协议 | - |
| F10 公司资料 | ✅ eltdx 通达信协议 | Wind |
| A股公告 | ✅ ftshare (结构化) | Wind RAG (语义搜索) |
| 财经新闻 | WebSearch | Wind RAG |
| 财务报表/ROE | - | ✅ Wind |
| 技术指标(MACD等) | - | ✅ Wind |
| 板块涨跌/资金流 | WebSearch | ✅ Wind index_data |
| 宏观指标(CPI等) | WebSearch | ✅ Wind economic_data |
| 大宗商品(金/银/油) | ✅ 腾讯接口 | - |
| 美股指数 | ✅ 腾讯接口 | Wind global_stock |

> 💡 **免费模式**：腾讯 + ftshare + eltdx 已覆盖日常行情、公告、K线、分时、竞价、逐笔需求。Wind 是可选增强。

## 🔄 数据源评分模型

每次查询都会对数据源进行三维打分：

| 维度 | 权重 | 说明 |
|------|------|------|
| 可用性 | 40% | 连通且有有效数据 = 100分 |
| 及时性 | 25-30% | 腾讯<500ms满分，Wind<1.5s满分，eltdx<500ms满分 |
| 质量 | 30-35% | 数据完整度 + 数值合理性 |

**等级**：A≥85 / B≥70 / C≥50 / D<50（D级视为不可用）

## 🔧 进阶配置

### 安装Wind（可选，需要API Key）

详见 [SKILL.md](./SKILL.md) 第5节。

```bash
# 安装Skill
npx skills add https://gitee.com/wind_info/wind-skills.git --skill wind-mcp-skill -g -y

# 配置Key
node <WIND_SKILL_DIR>/scripts/cli.mjs open-portal
node <WIND_SKILL_DIR>/scripts/cli.mjs setup-key <YOUR_KEY> --scope global
```

### 安装ftshare公告（推荐）

```bash
npx openclaw skills install shawn92/ftshare-announcement-data
```

### 集成到WorkBuddy Skill系统

将整个目录放到你的skills文件夹：

```bash
cp -r trader-data-router ~/.workbuddy/skills/
# 或
cp -r trader-data-router ~/.openclaw/workspace/skills/
```

## 使用场景

### 场景1：AI Agent定时报告

结合 WorkBuddy Automation 定时生成晚间财经报告：

```bash
#!/bin/bash
# evening_report.sh
echo "=== 数据源健康 ==="
python data_router.py health
echo ""
echo "=== 行情快照 ==="
python data_router.py quote --json
echo ""
echo "=== 自选股 ==="
python data_router.py watchlist --json
```

### 场景2：交易盯盘辅助

```bash
# 每30秒刷新自选股
watch -n 30 'python data_router.py watchlist'
```

### 场景3：程序化接入

```python
import subprocess, json

# 获取JSON格式行情
result = subprocess.run(
    ['python', 'data_router.py', 'quote', '--codes', 'sh600519,sz000001', '--json'],
    capture_output=True, text=True
)
data = json.loads(result.stdout)

print(f"最佳数据源: {data['best_source']}")
for stock in data['data']:
    print(f"{stock['name']}: {stock['price']} ({stock['change_pct']}%)")
```

## 已知限制

| 限制 | 影响 | 解决方案 |
|------|------|---------|
| akshare东方财富被拒 | 板块数据不可用 | Wind替代或WebSearch |
| Wind日额度限制 | 不能无限调用 | 优先腾讯做实时快照 |
| 单工具单标的(Wind) | 批量需循环 | for循环逐只查询 |
| 无本地缓存 | 每次都实时探测 | 后续版本加入 |

## 版本历史

| 版本 | 日期 | 变更 |
|------|------|------|
| v3.4.0 | 2026-06-17 | 集成 eltdx 通达信数据源；新增 5 个 CLI 命令：`kline`/`minute`/`auction`/`tick`/`f10`；health 检测加入 eltdx；FTShare 路径 bug 修复 |
| v3.1 | 2026-06-01 | 更名 trader-data-router；东财适配器重构（datacenter端点，4/4可用）；集成全市场分析引擎（NewsFetcher+THSDataFetcher+MarketModels）；联动 trader-finance-hub 开源项目 |
| v3.0 | 2026-05-22 | 新增 data_router.py 多源智能路由 |
| v2.0 | 2026-05-22 | 整合Wind万得金融8大能力 |
| v1.0 | 2026-05-20 | 初始版：腾讯+ftshare+AkShare体系 |

## License

MIT License — 自由使用、修改、分发。

## 致谢

- [腾讯财经](https://qt.gtimg.cn/) — 免费实时行情接口
- [Wind万得金融](https://www.wind.com.cn/) — 专业金融数据
- [ftshare-announcement-data](https://clawhub.ai) — A股公告数据
- [AkShare](https://akshare.akfamily.xyz/) — Python财经数据接口库
- [eltdx](https://github.com/electkismet/eltdx) — 通达信私有协议 Python 客户端

---

<p align="center">
  <sub>Made with trading discipline by <a href="https://github.com/wolfjkd">wolfjkd</a></sub>
</p>
