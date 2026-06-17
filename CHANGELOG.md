# Changelog

所有 notable 变更都记录在这个文件。

格式基于 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.0.0/)，版本号遵循 [Semantic Versioning](https://semver.org/lang/zh-CN/)。

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
