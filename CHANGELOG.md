# Changelog

所有 notable 变更都记录在这个文件。

格式基于 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.0.0/)，版本号遵循 [Semantic Versioning](https://semver.org/lang/zh-CN/)。

## [未发布] - 2026-09-21（归档修复）

**项目已归档，停止功能更新**（能力由 tradex-hub 取代）。

### Changed
- 修复 `data_router.py` 的数据源导入断链：astock_signals 路径由已失效的 `trader-finance-hub/src` 更新为 `tradex-hub/tradex/src`（多候选路径探测 + 清晰报错）。此前依赖 astock_signals 的 9 个命令（fundflow/northbound/dragon/concept/industry/etf/cb/tickstore/board）全部报 `No module named 'astock_signals'`。
- 修复 SKILL.md 与 README.md 中旧名 `trader-finance-hub` 的残留引用。
- README 重写：标明项目已归档、如实列出数据源可用性注意（东财 push2 风控所致 RemoteDisconnected、Wind 订阅等）。

## [3.7.0] - 2026-08-06

### Added
- 新增 `board` 命令（涨停板速报）：涨停池 / 炸板池 / 跌停池 / 昨日涨停池 / 涨停揭秘 / 打板情绪速算，调用 `astock_signals.limit_up_board`。
- Router 命令总数扩展至 18 个。

### Changed
- `data_router.py` 头部版本号更新为 `v3.7.0`。

## [3.6.0] - 2026-06-24

### Added
- 新增 3 个 CLI 命令：`etf`（ETF 数据）、`cb`/`bond`/`convertible`（可转债数据）、`tickstore`（逐笔成交存储）。
- Router 命令总数扩展至 17 个。

### Changed
- `data_router.py` 头部版本号更新为 `v3.6.0`。

## [3.5.0] - 2026-06-24

### Added
- 补齐 5 个薄壳 CLI 命令（fundflow / northbound / dragon / concept / industry 等），Router 命令数从 9 扩展到 14。

### Changed
- `data_router.py` 头部版本号更新为 `v3.5.0`。

## [3.4.0] - 2026-06-17

### Added
- 新增 `EltdxAdapter` 适配器，接入 eltdx 通达信私有协议数据源。
- 新增 5 个 CLI 命令：
  - `kline` — 历史K线（日/周/月）
  - `minute` — 当日分时数据
  - `auction` — 集合竞价序列（早盘/尾盘）
  - `tick` — 逐笔成交数据
  - `f10` — 公司资料/题材归因/财务诊断
- `health` 命令加入 eltdx 数据源检测，当前 4 个数据源（腾讯/Wind/ftshare/eltdx）全部可评分。
- 新增 `.gitignore`，忽略 `__pycache__`。

### Changed
- `data_router.py` 头部版本号更新为 `v3.4.0`。
- README.md 描述改实事求是：去掉"多源智能路由""零依赖""毫秒级"等夸大表述，明确当前实际数据源和命令能力。

### Fixed
- 修复 FTShare 公告路径查找逻辑：原路径 `~/.workbuddy/.workbuddy/skills/ftshare-announcement-data` 重复了 `.workbuddy` 目录，改为 `~/.workbuddy/skills/ftshare-announcement-data`。

## [3.3.1] - 2026-05-22

### Fixed
- 若干数据源探测超时问题修复。

## [3.3.0] - 2026-05-22

### Added
- 发布 trader-data-router 独立 Skill 形态。
- `health` / `quote` / `watchlist` / `compare` 4 个核心命令。

## [3.1.0] - 2026-06-01

### Changed
- 项目更名 `trader-data-router`。
- 东财适配器重构（datacenter 端点，4/4 可用）。
- 集成全市场分析引擎（NewsFetcher + THSDataFetcher + MarketModels）。
- 联动 trader-finance-hub 开源项目。

## [3.0.0] - 2026-05-22

### Added
- 新增 `data_router.py` 多源数据路由脚本。

## [2.0.0] - 2026-05-22

### Added
- 整合 Wind 万得金融 8 大能力。

## [1.0.0] - 2026-05-20

### Added
- 初始版本：腾讯 + ftshare + AkShare 体系。
