#!/usr/bin/env python3
"""
多源数据智能路由器 - A股T0交易数据获取
=========================================
版本: v3.3.1 (2026-06-04)
Skill: trader-data-router

五源数据路由(腾讯/Wind/ftshare/东财/eltdx) + 全市场综合分析引擎。

数据源:
  Primary:    腾讯接口(实时行情)       A级 100分
  Secondary:  Wind MCP(深度数据)       A级 94.5分
  Supplement: 东财MCP(特色数据)        B级 82分
  Specialist: ftshare(公告)           A级 91分
  Exclusive:  eltdx(独有数据)          A级 92.5分

路由策略(v3.3.1修复):
  - 行情快照/指数/商品：腾讯作为主力源，得分差≤15分时优先选择
  - 独有数据(竞价/逐笔/F10)：仅eltdx提供，无竞争
  - 互补数据(分时/K线)：按评分选择

eltdx独有数据(v3.3新增):
  - 集合竞价数据（腾讯接口无此功能）
  - 逐笔成交数据（腾讯接口无此功能）
  - F10资料数据（腾讯接口无此功能）
  - 分时数据（与腾讯接口互补）
  - K线数据（与腾讯接口互补）

分析引擎(v3.2):
  - NewsFetcher: 4源新闻聚合(EM/CCTV/全球/要闻)
  - THSDataFetcher: 同花顺板块数据(AKShare后端)
  - MarketModels: 四象限/情绪时钟/信息熵共识度

使用方式:
  # 检测所有数据源健康状态
  python data_router.py health

  # 获取实时行情（自动选最优源）
  python data_router.py quote --codes sh000001,sz399001

  # 获取自选股行情
  python data_router.py watchlist

  # 对比多个数据源的同一条数据
  python data_router.py compare --code 600170.SH --type quote

  # --- eltdx独有数据(v3.3) ---
  # 集合竞价/逐笔成交/F10资料/分时数据
  python data_router.py auction --codes sz000001,sh600000
  python data_router.py tick --code sz000001 --date 20260604
  python data_router.py f10 --code 000001
  python data_router.py minute --code sz000001

  # --- 其他数据(v3.2) ---
  # 北向资金/龙虎榜/涨停池
  python data_router.py northbound
  python data_router.py dragontiger
  python data_router.py limitpool

  # 全市场综合分析
  python data_router.py news          # 今日财经要闻
  python data_router.py sector        # 板块四象限分析
  python data_router.py sentiment     # 情绪时钟
  python data_router.py report        # 综合报告JSON
"""

import json
import sys
import time
import urllib.request
import urllib.error
import subprocess
from datetime import datetime
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed, TimeoutError

# Fix Windows console encoding for emoji
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

# ============================================================
# 配置区
# ============================================================

# 自选股列表
WATCHLIST = [
    ("sh600170", "上海建工"),
    ("sh603077", "和邦生物"),
    ("sh601868", "中国能建"),
    ("sh601390", "中国中铁"),
    ("sz000061", "农产品"),
    ("sz000560", "我爱我家"),
]

# A股主要指数
INDEXES = ["sh000001", "sz399001", "sz399006"]

# 美股指数
US_INDEXES = ["usINDU", "usIXIC", "usINX"]

# 大宗商品
COMMODITIES = ["hf_GC", "hf_SI", "hf_CL"]

# 数据源超时阈值（秒）
TIMEOUTS = {
    "tencent": 5,      # 腾讯接口快，5秒足够
    "wind": 10,        # Wind MCP需要CLI调用+网络
    "eastmoney": 8,    # 东方财富MCP，AKShare后端
    "ftshare": 15,     # ftshare Python脚本较慢
    "websearch": 20,   # WebSearch最慢（需AI处理）
}

# ============================================================
# 数据源适配器
# ============================================================

class DataSourceResult:
    """单次数据源探测结果"""
    def __init__(self, source: str, data_type: str):
        self.source = source
        self.data_type = data_type
        self.success = False
        self.response_time_ms = 0
        self.data = None           # 原始数据
        self.parsed = None         # 解析后的结构化数据
        self.error = None
        self.score = 0             # 综合评分 0-100
        self.availability_score = 0   # 可用性 0-100
        self.timeliness_score = 0     # 及时性 0-100
        self.quality_score = 0        # 质量 0-100
        self.timestamp = datetime.now().isoformat()

    def to_dict(self) -> dict:
        return {
            "source": self.source,
            "data_type": self.data_type,
            "success": self.success,
            "response_time_ms": self.response_time_ms,
            "score": round(self.score, 1),
            "availability_score": round(self.availability_score, 1),
            "timeliness_score": round(self.timeliness_score, 1),
            "quality_score": round(self.quality_score, 1),
            "error": self.error,
            "has_data": self.data is not None,
        }


class TencentAdapter:
    """腾讯行情接口适配器"""

    NAME = "tencent"
    DESCRIPTION = "腾讯实时行情接口（毫秒级，基础字段）"

    @staticmethod
    def fetch(codes: list[str], timeout: int = 5) -> DataSourceResult:
        result = DataSourceResult("tencent", "quote")
        start = time.time()

        try:
            url = f"https://qt.gtimg.cn/q={','.join(codes)}"
            req = urllib.request.Request(url, headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
            })
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                raw = resp.read().decode("gbk", errors="ignore")

            result.response_time_ms = round((time.time() - start) * 1000)
            result.data = raw
            result.success = True

            # 解析并评分
            parsed = TencentAdapter._parse(raw, codes)
            result.parsed = parsed
            result = TencentAdapter._score(result, codes)

        except urllib.error.URLError as e:
            result.response_time_ms = round((time.time() - start) * 1000)
            result.error = f"网络错误: {e.reason}"
            result.score = 0
        except Exception as e:
            result.response_time_ms = round((time.time() - start) * 1000)
            result.error = str(e)
            result.score = 0

        return result

    @staticmethod
    def _parse(raw: str, expected_codes: list) -> list[dict]:
        """解析腾讯接口返回数据为结构化列表"""
        records = []
        for line in raw.strip().split(";"):
            line = line.strip()
            if not line:
                continue
            # 格式: v_sh600170="1~上海建工~..."
            if "~" in line and "=" in line:
                try:
                    data_str = line.split("=", 1)[1].strip('"')
                    fields = data_str.split("~")
                    if len(fields) >= 45:  # 腾讯返回约50个字段
                        records.append({
                            "code": fields[2],       # 股票代码
                            "name": fields[1],        # 名称
                            "price": float(fields[3]) if fields[3] else None,       # 最新价
                            "prev_close": float(fields[4]) if fields[4] else None,   # 收盘价
                            "open": float(fields[5]) if fields[5] else None,         # 今开
                            "volume": int(float(fields[36])) if fields[36] else None, # 成交量(手)
                            "amount": float(fields[37]) if fields[37] else None,      # 成交额
                            "change_pct": float(fields[32]) if fields[32] else None, # 涨跌幅
                            "change_amt": float(fields[31]) if fields[31] else None, # 涨跌额
                            "high": float(fields[33]) if fields[33] else None,       # 最高
                            "low": float(fields[34]) if fields[34] else None,        # 最低
                            "turnover": float(fields[38]) if fields[38] else None,   # 换手率
                            "pe": fields[39],              # 市盈率
                            "market_cap": fields[44],      # 总市值
                            "timestamp": fields[30],       # 更新时间
                            "_source": "tencent",
                        })
                except (ValueError, IndexError):
                    continue
        return records

    @staticmethod
    def _score(result: DataSourceResult, expected_codes: list) -> DataSourceResult:
        """腾讯接口评分"""
        n_expected = len(expected_codes)
        n_got = len(result.parsed) if result.parsed else 0

        # 可用性 (40%): 连通且返回数据=满分
        result.availability_score = 100 if result.success and n_got > 0 else 0

        # 及时性 (30%): <500ms=100, <1s=90, <2s=70, <3s=50, <5s=30, >5s=10
        rt = result.response_time_ms
        if rt <= 500: result.timeliness_score = 100
        elif rt <= 1000: result.timeliness_score = 90
        elif rt <= 2000: result.timeliness_score = 70
        elif rt <= 3000: result.timeliness_score = 50
        elif rt <= 5000: result.timeliness_score = 30
        else: result.timeliness_score = 10

        # 质量 (30%): 数据完整度 + 数值合理性
        if n_got == 0:
            result.quality_score = 0
        elif n_got >= n_expected:
            # 全部返回，检查字段质量
            valid_count = sum(
                1 for r in result.parsed
                if r.get("price") is not None and r.get("price") > 0
            )
            ratio = valid_count / max(n_got, 1)
            result.quality_score = min(100, int(ratio * 100))
        else:
            # 部分返回
            result.quality_score = int((n_got / n_expected) * 70)

        # 加权总分
        result.score = (
            result.availability_score * 0.40 +
            result.timeliness_score * 0.30 +
            result.quality_score * 0.30
        )
        return result


class WindAdapter:
    """Wind MCP Skill适配器"""

    NAME = "wind"
    DESCRIPTION = "Wind万得金融（全维度数据，有日额度）"

    # Wind skill目录
    WIND_SKILL_DIR = Path.home() / ".workbuddy" / "skills" / "wind-mcp-skill"

    @classmethod
    def _is_available(cls) -> bool:
        """检查Wind CLI是否可用"""
        cli = cls.WIND_SKILL_DIR / "scripts" / "cli.mjs"
        return cli.exists()

    @classmethod
    def fetch(cls, code: str, indexes: str = "中文简称,最新成交价,涨跌幅,成交量",
              timeout: int = 10) -> DataSourceResult:
        """获取单个标的Wind行情快照"""
        result = DataSourceResult("wind", "quote")
        start = time.time()

        if not cls._is_available():
            result.error = "Wind CLI不存在，请先安装wind-mcp-skill"
            result.response_time_ms = round((time.time() - start) * 1000)
            result.score = 0
            return result

        try:
            cli = cls.WIND_SKILL_DIR / "scripts" / "cli.mjs"
            params_json = json.dumps({"windcode": code, "indexes": indexes}, ensure_ascii=False)
            cmd = ["node", str(cli), "call", "stock_data", "get_stock_price_indicators", params_json]

            proc = subprocess.run(
                cmd, capture_output=True, text=True, timeout=timeout,
                cwd=str(cls.WIND_SKILL_DIR)
            )

            result.response_time_ms = round((time.time() - start) * 1000)
            stdout = proc.stdout.strip()
            stderr = proc.stderr.strip()

            if proc.returncode == 0 and stdout:
                result.data = stdout
                result.success = True
                # 尝试解析JSON
                try:
                    result.parsed = json.loads(stdout) if stdout.startswith("{") or stdout.startswith("[") else {"raw": stdout}
                except json.JSONDecodeError:
                    result.parsed = {"raw": stdout}
            else:
                # 尝试从错误envelope提取信息
                result.error = stdout or stderr or f"退出码 {proc.returncode}"
                result.data = stdout

            result = cls._score(result)

        except subprocess.TimeoutExpired:
            result.response_time_ms = round((time.time() - start) * 1000)
            result.error = f"超时({timeout}s)"
            result.score = 0
        except Exception as e:
            result.response_time_ms = round((time.time() - start) * 1000)
            result.error = str(e)
            result.score = 0

        return result

    @classmethod
    def _score(cls, result: DataSourceResult) -> DataSourceResult:
        """Wind评分"""
        # 可用性
        result.availability_score = 100 if result.success else 0

        # 及时性: Wind需要CLI调用，标准放宽
        rt = result.response_time_ms
        if rt <= 1500: result.timeliness_score = 100
        elif rt <= 3000: result.timeliness_score = 85
        elif rt <= 5000: result.timeliness_score = 70
        elif rt <= 8000: result.timeliness_score = 50
        elif rt <= 10000: result.timeliness_score = 30
        else: result.timeliness_score = 10

        # 质量: Wind数据通常很全
        if result.success and result.data:
            data_str = str(result.data)
            # 有实际内容且不是错误
            if len(data_str) > 20 and "error" not in data_str.lower()[:200]:
                result.quality_score = 95  # Wind数据质量高
            elif len(data_str) > 5:
                result.quality_score = 70
            else:
                result.quality_score = 30
        else:
            result.quality_score = 0

        result.score = (
            result.availability_score * 0.40 +
            result.timeliness_score * 0.25 +
            result.quality_score * 0.35  # Wind质量权重稍高
        )
        return result


class FtShareAdapter:
    """ftshare公告数据适配器"""

    NAME = "ftshare"
    DESCRIPTION = "FTShare公告数据（A股公告结构化）"

    FTSHARE_DIR = Path.home() / ".workbuddy" / "skills" / "ftshare-announcement-data"

    @classmethod
    def _is_available(cls) -> bool:
        run_py = cls.FTSHARE_DIR / "run.py"
        return run_py.exists()

    @classmethod
    def fetch(cls, stock_code: str, page: int = 1, page_size: int = 10,
              timeout: int = 15) -> DataSourceResult:
        """获取个股公告"""
        result = DataSourceResult("ftshare", "announcement")
        start = time.time()

        if not cls._is_available():
            result.error = "ftshare run.py不存在"
            result.response_time_ms = round((time.time() - start) * 1000)
            result.score = 0
            return result

        try:
            cmd = [
                sys.executable, str(cls.FTSHARE_DIR / "run.py"),
                "stock-announcements-single-stock-all-periods",
                "--stock-code", stock_code,
                "--page", str(page),
                "--page-size", str(page_size)
            ]
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)

            result.response_time_ms = round((time.time() - start) * 1000)
            stdout = proc.stdout.strip()

            if proc.returncode == 0 and stdout:
                result.data = stdout
                result.success = True
                try:
                    result.parsed = json.loads(stdout)
                except json.JSONDecodeError:
                    result.parsed = {"raw": stdout}
            else:
                result.error = stdout or proc.stderr or f"退出码 {proc.returncode}"

            result = cls._score(result)

        except subprocess.TimeoutExpired:
            result.response_time_ms = round((time.time() - start) * 1000)
            result.error = f"超时({timeout}s)"
            result.score = 0
        except Exception as e:
            result.response_time_ms = round((time.time() - start) * 1000)
            result.error = str(e)
            result.score = 0

        return result

    @classmethod
    def _score(cls, result: DataSourceResult) -> DataSourceResult:
        result.availability_score = 100 if result.success else 0

        rt = result.response_time_ms
        if rt <= 2000: result.timeliness_score = 100
        elif rt <= 5000: result.timeliness_score = 80
        elif rt <= 10000: result.timeliness_score = 60
        elif rt <= 15000: result.timeliness_score = 40
        else: result.timeliness_score = 20

        if result.success and result.parsed:
            if isinstance(result.parsed, dict) and "data" in result.parsed:
                count = len(result.parsed["data"]) if isinstance(result.parsed["data"], list) else 0
            elif isinstance(result.parsed, list):
                count = len(result.parsed)
            else:
                count = 1 if len(str(result.parsed)) > 50 else 0

            if count >= 5: result.quality_score = 95
            elif count >= 1: result.quality_score = 75
            else: result.quality_score = 40
        else:
            result.quality_score = 0

        result.score = (
            result.availability_score * 0.40 +
            result.timeliness_score * 0.25 +
            result.quality_score * 0.35
        )
        return result


class EltdxAdapter:
    """
    eltdx通达信行情协议适配器 - 独有数据源
    
    独有功能（腾讯接口无）：
    - 集合竞价数据
    - 逐笔成交数据
    - F10资料数据
    - 代码表数据
    - 股本变迁数据
    
    互补功能：
    - 行情快照（与腾讯接口竞争）
    - 分时数据（与腾讯接口互补）
    - K线数据（与腾讯接口互补）
    """

    NAME = "eltdx"
    DESCRIPTION = "eltdx通达信行情协议（独有：集合竞价/逐笔成交/F10）"

    # eltdx集成模块路径
    ELTDX_INTEGRATION_PATH = Path.home() / "WorkBuddy" / "Claw"

    @classmethod
    def _is_available(cls) -> bool:
        """检查eltdx是否已安装"""
        try:
            import eltdx
            return True
        except ImportError:
            return False

    @classmethod
    def _get_integration(cls):
        """获取eltdx集成模块"""
        if str(cls.ELTDX_INTEGRATION_PATH) not in sys.path:
            sys.path.insert(0, str(cls.ELTDX_INTEGRATION_PATH))
        from eltdx_integration import EltdxIntegration
        return EltdxIntegration

    @staticmethod
    def fetch_quote(codes: list[str], timeout: int = 5) -> DataSourceResult:
        """获取行情快照（与腾讯接口竞争）"""
        result = DataSourceResult("eltdx", "quote")
        start = time.time()

        if not EltdxAdapter._is_available():
            result.error = "eltdx未安装，请先执行: pip install eltdx"
            result.response_time_ms = round((time.time() - start) * 1000)
            result.score = 0
            return result

        try:
            EltdxIntegration = EltdxAdapter._get_integration()
            with EltdxIntegration(timeout=timeout) as eltdx:
                quote_data = eltdx.get_quote_snapshot(codes)
                
            result.response_time_ms = round((time.time() - start) * 1000)
            
            if quote_data.get('status') == 'success':
                result.data = json.dumps(quote_data, ensure_ascii=False)
                result.parsed = quote_data.get('quotes', {})
                result.success = True
            else:
                result.error = quote_data.get('message', '获取行情失败')
            
            result = EltdxAdapter._score_quote(result, len(codes))

        except Exception as e:
            result.response_time_ms = round((time.time() - start) * 1000)
            result.error = str(e)[:150]
            result.score = 0

        return result

    @staticmethod
    def fetch_auction(codes: list[str], timeout: int = 5) -> DataSourceResult:
        """获取集合竞价数据（独有功能）"""
        result = DataSourceResult("eltdx", "auction")
        start = time.time()

        if not EltdxAdapter._is_available():
            result.error = "eltdx未安装"
            result.response_time_ms = round((time.time() - start) * 1000)
            result.score = 0
            return result

        try:
            EltdxIntegration = EltdxAdapter._get_integration()
            auction_results = {}
            
            with EltdxIntegration(timeout=timeout) as eltdx:
                for code in codes:
                    auction_data = eltdx.get_auction_data(code)
                    auction_results[code] = auction_data
            
            result.response_time_ms = round((time.time() - start) * 1000)
            result.data = json.dumps(auction_results, ensure_ascii=False)
            result.parsed = auction_results
            result.success = True
            
            # 独有数据源，固定高分
            result = EltdxAdapter._score_exclusive(result, len(codes))

        except Exception as e:
            result.response_time_ms = round((time.time() - start) * 1000)
            result.error = str(e)[:150]
            result.score = 0

        return result

    @staticmethod
    def fetch_tick(code: str, date: str, timeout: int = 10) -> DataSourceResult:
        """获取逐笔成交数据（独有功能）"""
        result = DataSourceResult("eltdx", "tick")
        start = time.time()

        if not EltdxAdapter._is_available():
            result.error = "eltdx未安装"
            result.response_time_ms = round((time.time() - start) * 1000)
            result.score = 0
            return result

        try:
            EltdxIntegration = EltdxAdapter._get_integration()
            
            with EltdxIntegration(timeout=timeout) as eltdx:
                tick_data = eltdx.get_tick_data(code, date)
            
            result.response_time_ms = round((time.time() - start) * 1000)
            result.data = json.dumps(tick_data, ensure_ascii=False)
            result.parsed = tick_data
            result.success = True
            
            # 独有数据源，固定高分
            result = EltdxAdapter._score_exclusive(result, 1)

        except Exception as e:
            result.response_time_ms = round((time.time() - start) * 1000)
            result.error = str(e)[:150]
            result.score = 0

        return result

    @staticmethod
    def fetch_f10(code: str, timeout: int = 10) -> DataSourceResult:
        """获取F10资料数据（独有功能）"""
        result = DataSourceResult("eltdx", "f10")
        start = time.time()

        if not EltdxAdapter._is_available():
            result.error = "eltdx未安装"
            result.response_time_ms = round((time.time() - start) * 1000)
            result.score = 0
            return result

        try:
            EltdxIntegration = EltdxAdapter._get_integration()
            
            with EltdxIntegration(timeout=timeout) as eltdx:
                f10_data = eltdx.get_f10_data(code)
            
            result.response_time_ms = round((time.time() - start) * 1000)
            result.data = json.dumps(f10_data, ensure_ascii=False)
            result.parsed = f10_data
            result.success = True
            
            # 独有数据源，固定高分
            result = EltdxAdapter._score_exclusive(result, 1)

        except Exception as e:
            result.response_time_ms = round((time.time() - start) * 1000)
            result.error = str(e)[:150]
            result.score = 0

        return result

    @staticmethod
    def fetch_minute(code: str, timeout: int = 5) -> DataSourceResult:
        """获取分时数据（与腾讯接口互补）"""
        result = DataSourceResult("eltdx", "minute")
        start = time.time()

        if not EltdxAdapter._is_available():
            result.error = "eltdx未安装"
            result.response_time_ms = round((time.time() - start) * 1000)
            result.score = 0
            return result

        try:
            EltdxIntegration = EltdxAdapter._get_integration()
            
            with EltdxIntegration(timeout=timeout) as eltdx:
                minute_data = eltdx.get_minute_data(code)
            
            result.response_time_ms = round((time.time() - start) * 1000)
            result.data = json.dumps(minute_data, ensure_ascii=False)
            result.parsed = minute_data
            result.success = True
            
            # 互补数据源，中等分数
            result = EltdxAdapter._score_complementary(result)

        except Exception as e:
            result.response_time_ms = round((time.time() - start) * 1000)
            result.error = str(e)[:150]
            result.score = 0

        return result

    @staticmethod
    def _score_quote(result: DataSourceResult, expected: int) -> DataSourceResult:
        """行情快照评分（与腾讯竞争，无独有数据源加成）"""
        result.availability_score = 100 if result.success else 0
        
        rt = result.response_time_ms
        if rt <= 200: result.timeliness_score = 100
        elif rt <= 500: result.timeliness_score = 90
        elif rt <= 1000: result.timeliness_score = 75
        elif rt <= 2000: result.timeliness_score = 60
        elif rt <= 5000: result.timeliness_score = 40
        else: result.timeliness_score = 20
        
        if result.success and result.parsed:
            got = len(result.parsed)
            if got >= expected:
                result.quality_score = 95
            elif got > 0:
                result.quality_score = int((got / expected) * 80)
            else:
                result.quality_score = 0
        else:
            result.quality_score = 0
        
        # 行情快照是竞争性数据源，不加独有数据源加成
        result.score = (
            result.availability_score * 0.40 +
            result.timeliness_score * 0.30 +
            result.quality_score * 0.30
        )
        return result

    @staticmethod
    def _score_exclusive(result: DataSourceResult, expected: int) -> DataSourceResult:
        """独有数据源评分（集合竞价/逐笔成交/F10）"""
        result.availability_score = 100 if result.success else 0
        
        rt = result.response_time_ms
        if rt <= 500: result.timeliness_score = 100
        elif rt <= 1000: result.timeliness_score = 90
        elif rt <= 2000: result.timeliness_score = 80
        elif rt <= 5000: result.timeliness_score = 60
        elif rt <= 10000: result.timeliness_score = 40
        else: result.timeliness_score = 20
        
        if result.success and result.parsed:
            # 独有数据源，只要有数据就给高分
            if isinstance(result.parsed, dict):
                status = result.parsed.get('status', '')
                if status == 'success':
                    result.quality_score = 95
                elif status == 'no_data':
                    result.quality_score = 50  # 无数据但连接正常
                else:
                    result.quality_score = 30
            else:
                result.quality_score = 80
        else:
            result.quality_score = 0
        
        # 独有数据源加成：没有竞争，固定高分
        base_score = (
            result.availability_score * 0.35 +
            result.timeliness_score * 0.25 +
            result.quality_score * 0.40
        )
        # 独有数据源加成 +10分
        result.score = min(100, base_score + 10)
        return result

    @staticmethod
    def _score_complementary(result: DataSourceResult) -> DataSourceResult:
        """互补数据源评分（分时/K线）"""
        result.availability_score = 100 if result.success else 0
        
        rt = result.response_time_ms
        if rt <= 200: result.timeliness_score = 100
        elif rt <= 500: result.timeliness_score = 90
        elif rt <= 1000: result.timeliness_score = 75
        elif rt <= 2000: result.timeliness_score = 60
        elif rt <= 5000: result.timeliness_score = 40
        else: result.timeliness_score = 20
        
        if result.success and result.parsed:
            if isinstance(result.parsed, dict):
                status = result.parsed.get('status', '')
                points = result.parsed.get('points', 0)
                if status == 'success' and points > 0:
                    result.quality_score = 90
                elif status == 'success':
                    result.quality_score = 70
                else:
                    result.quality_score = 40
            else:
                result.quality_score = 70
        else:
            result.quality_score = 0
        
        result.score = (
            result.availability_score * 0.40 +
            result.timeliness_score * 0.30 +
            result.quality_score * 0.30
        )
        return result


class EastMoneyAdapter:
    """
    东方财富MCP适配器 — 特色金融数据专用源

    定位：不再与腾讯争夺实时行情（腾讯是主力），而是提供腾讯不覆盖的
    特色数据：龙虎榜、北向资金、涨停池、概念板块等。

    已知限制（2026-06-01）：
    - push2.eastmoney.com 实时行情接口被拒 → stock_zh_a_spot_em 不可用
    - 新浪 stock_zh_a_spot 全量接口也失效（返回HTML）
    - datacenter.eastmoney.com 部分接口可用（hsgt/lhb/zt_pool）
    - Sina stock_zh_a_daily 单股日线可用（非实时）
    """

    NAME = "eastmoney"
    DESCRIPTION = "东方财富MCP（42工具：龙虎榜/北向资金/涨停池/行业/财务/宏观）"

    # 已验证可用的AKShare函数端点
    _WORKING_ENDPOINTS = {
        "northbound": "stock_hsgt_hist_em",       # 北向资金 ✅
        "dragontiger": "stock_lhb_detail_em",     # 龙虎榜 ✅
        "limitpool": "stock_zt_pool_em",          # 涨停池 ✅
        "sina_daily": "stock_zh_a_daily",         # 新浪单股日线 ✅ (兜底)
    }

    # 已知被拒但仍可尝试的（可能在个别网络环境恢复）
    _BLOCKED_ENDPOINTS = [
        "stock_zh_a_spot_em",           # push2 实时行情
        "stock_zh_a_hist",              # EM 历史K线
        "stock_zh_index_spot_em",       # EM 指数行情
        "stock_individual_info_em",     # EM 个股信息
        "stock_individual_fund_flow",   # EM 资金流向
        "stock_board_concept_name_em",  # EM 概念板块
    ]

    @classmethod
    def _is_available(cls) -> bool:
        """检查AKShare是否已安装"""
        try:
            import akshare  # noqa: F401
            return True
        except ImportError:
            return False

    @staticmethod
    def fetch(codes: list[str], timeout: int = 8, data_type: str = "quote") -> DataSourceResult:
        """
        获取数据（根据 data_type 路由到不同的AKShare端点）。

        data_type:
          - 'quote': 行情（Sina单股日线兜底，非实时）
          - 'northbound': 北向资金流向
          - 'dragontiger': 龙虎榜
          - 'limitpool': 涨停板池
          - 'health': 多功能健康探测
        """
        result = DataSourceResult("eastmoney", data_type)
        start = time.time()

        try:
            import akshare as ak
            import datetime as _dt

            if data_type in ("quote", "health"):
                # 行情尝试：Sina单股日线（唯一可用的行情兜底）
                target_codes = set()
                for code in codes:
                    norm = EastMoneyAdapter._normalize_code_ak(code)
                    if norm:
                        target_codes.add(norm)

                quotes = []
                sina_ok = 0
                for code in target_codes:
                    try:
                        ex_prefix = "sh" if code.startswith(("6", "9")) else "sz"
                        sym = f"{ex_prefix}{code}"
                        df = ak.stock_zh_a_daily(symbol=sym)
                        if df is not None and not df.empty:
                            sina_ok += 1
                            last = df.tail(1).iloc[0]
                            quotes.append(EastMoneyAdapter._parse_sina_row(code, last))
                    except Exception:
                        continue

                result.response_time_ms = round((time.time() - start) * 1000)

                if quotes:
                    result.data = json.dumps(quotes, ensure_ascii=False)
                    result.parsed = quotes
                    result.success = True
                    result.error = f"Sina单股日线(非实时): {sina_ok}/{len(target_codes)}支"
                else:
                    result.error = "行情接口均不可用(EM push2封禁+Sina全量失效)"

                result = EastMoneyAdapter._score_quote(result, len(target_codes), len(quotes), result.response_time_ms)

            elif data_type == "northbound":
                df = ak.stock_hsgt_hist_em(symbol="北向资金")
                result.response_time_ms = round((time.time() - start) * 1000)
                if df is not None and not df.empty:
                    latest = df.iloc[0].to_dict()
                    result.data = json.dumps(latest, ensure_ascii=False, default=str)
                    result.parsed = latest
                    result.success = True
                else:
                    result.error = "北向资金数据为空"
                result.score = 85 if result.success else 0

            elif data_type == "dragontiger":
                today = _dt.date.today()
                start_d = today - _dt.timedelta(days=10)
                df = ak.stock_lhb_detail_em(
                    start_date=start_d.strftime("%Y%m%d"),
                    end_date=today.strftime("%Y%m%d"),
                )
                result.response_time_ms = round((time.time() - start) * 1000)
                if df is not None and not df.empty:
                    result.data = json.dumps(df.head(20).to_dict(orient="records"), ensure_ascii=False, default=str)
                    result.parsed = df.head(10).to_dict(orient="records")
                    result.success = True
                else:
                    result.error = "龙虎榜数据为空"
                result.score = 85 if result.success else 0

            elif data_type == "limitpool":
                today = _dt.date.today().strftime("%Y%m%d")
                df = ak.stock_zt_pool_em(date=today)
                result.response_time_ms = round((time.time() - start) * 1000)
                if df is not None and not df.empty:
                    result.data = json.dumps(df.head(20).to_dict(orient="records"), ensure_ascii=False, default=str)
                    result.parsed = df.head(10).to_dict(orient="records")
                    result.success = True
                else:
                    result.error = "今日无涨停板数据（可能非交易日）"
                    result.success = True  # 空数据不等同于失败
                result.score = 85 if result.success else 0

            else:
                result.error = f"不支持的数据类型: {data_type}"
                result.score = 0

        except ImportError:
            result.response_time_ms = round((time.time() - start) * 1000)
            result.error = "AKShare未安装"
            result.score = 0
        except Exception as e:
            result.response_time_ms = round((time.time() - start) * 1000)
            result.error = str(e)[:150]
            result.score = 0

        return result

    @staticmethod
    def _normalize_code_ak(tencent_code: str) -> str | None:
        """腾讯格式 -> 纯数字: sh600170 -> 600170, sz000061 -> 000061"""
        tc = tencent_code.strip().lower()
        for prefix in ("sh", "sz", "bj"):
            if tc.startswith(prefix):
                return tc[len(prefix):]
        return tc

    @staticmethod
    def _parse_sina_row(code: str, row) -> dict:
        """将 Sina stock_zh_a_daily DataFrame 行标准化"""
        return {
            "code": code,
            "name": "",  # Sina daily 接口不含名称
            "date": str(row.get("date", "")),
            "price": _safe_float(row.get("close")),
            "open": _safe_float(row.get("open")),
            "high": _safe_float(row.get("high")),
            "low": _safe_float(row.get("low")),
            "volume": _safe_int(row.get("volume")),
            "amount": _safe_float(row.get("amount")),
            "turnover": _safe_float(row.get("turnover")),
            "_source": "eastmoney/sina-daily",
            "_note": "Sina日线数据(非实时)，当日收盘后更新",
        }

    @staticmethod
    def _score_quote(result: DataSourceResult, expected: int, got: int, rt: float) -> DataSourceResult:
        """东财行情评分（已知限制：Sina日线非实时，扣及时性分）"""
        result.availability_score = 100 if got > 0 else 0
        # Sina日线及时性天然低（非实时数据）
        result.timeliness_score = 20  # 非实时，固定低分
        result.quality_score = 90 if got >= expected else int((got / expected) * 80) if got > 0 else 0
        result.score = (
            result.availability_score * 0.40 +
            result.timeliness_score * 0.30 +
            result.quality_score * 0.30
        )
        return result


def _safe_float(val) -> float | None:
    """安全转换为float"""
    import math
    if val is None:
        return None
    try:
        f = float(val)
        return None if math.isnan(f) else f
    except (ValueError, TypeError):
        return None


def _safe_int(val) -> int | None:
    """安全转换为int"""
    import math
    if val is None:
        return None
    try:
        i = int(float(val))
        return None if math.isnan(float(val)) else i
    except (ValueError, TypeError):
        return None


# ============================================================
# 路由核心逻辑
# ============================================================

def probe_sources(data_type: str, **kwargs) -> list[DataSourceResult]:
    """
    并行探测所有候选数据源，返回按得分排序的结果列表。
    
    data_type: 'quote' | 'announcement' | 'index' | 'commodity' | 'auction' | 'tick' | 'f10' | 'minute'
    """
    results = []
    futures_map = {}

    with ThreadPoolExecutor(max_workers=5) as executor:
        if data_type in ("quote", "index", "commodity"):
            codes = kwargs.get("codes", INDEXES)
            # 腾讯接口
            fut = executor.submit(TencentAdapter.fetch, codes, TIMEOUTS["tencent"])
            futures_map[fut] = ("tencent", "primary")

            # Wind（如果请求的是个股）
            single_code = kwargs.get("single_code")
            if single_code and WindAdapter._is_available():
                fut_w = executor.submit(WindAdapter.fetch, single_code)
                futures_map[fut_w] = ("wind", "secondary")

            # 东方财富MCP（特色数据源：龙虎榜/北向资金/涨停池）
            # 注意：东财不参与实时行情路由（push2被拒），仅作为补充数据源
            if EastMoneyAdapter._is_available():
                fut_e = executor.submit(EastMoneyAdapter.fetch, codes, TIMEOUTS["eastmoney"], "quote")
                futures_map[fut_e] = ("eastmoney", "supplement")
            
            # eltdx（独有数据源：集合竞价/逐笔成交/F10）
            if EltdxAdapter._is_available():
                fut_el = executor.submit(EltdxAdapter.fetch_quote, codes, TIMEOUTS.get("eltdx", 5))
                futures_map[fut_el] = ("eltdx", "exclusive")

        elif data_type == "announcement":
            stock_code = kwargs.get("stock_code", "600170.SH")
            # ftshare
            if FtShareAdapter._is_available():
                fut_f = executor.submit(FtShareAdapter.fetch, stock_code)
                futures_map[fut_f] = ("ftshare", "primary")

        elif data_type == "auction":
            # 集合竞价：只有eltdx有此功能
            codes = kwargs.get("codes", [])
            if EltdxAdapter._is_available() and codes:
                fut_a = executor.submit(EltdxAdapter.fetch_auction, codes, TIMEOUTS.get("eltdx", 5))
                futures_map[fut_a] = ("eltdx", "exclusive")

        elif data_type == "tick":
            # 逐笔成交：只有eltdx有此功能
            code = kwargs.get("code", "")
            date = kwargs.get("date", datetime.now().strftime("%Y%m%d"))
            if EltdxAdapter._is_available() and code:
                fut_t = executor.submit(EltdxAdapter.fetch_tick, code, date, TIMEOUTS.get("eltdx", 10))
                futures_map[fut_t] = ("eltdx", "exclusive")

        elif data_type == "f10":
            # F10资料：只有eltdx有此功能
            code = kwargs.get("code", "")
            if EltdxAdapter._is_available() and code:
                fut_f10 = executor.submit(EltdxAdapter.fetch_f10, code, TIMEOUTS.get("eltdx", 10))
                futures_map[fut_f10] = ("eltdx", "exclusive")

        elif data_type == "minute":
            # 分时数据：eltdx提供
            code = kwargs.get("code", "")
            if EltdxAdapter._is_available() and code:
                fut_m = executor.submit(EltdxAdapter.fetch_minute, code, TIMEOUTS.get("eltdx", 5))
                futures_map[fut_m] = ("eltdx", "complementary")

        # 等待所有探测完成
        for future in as_completed(futures_map, timeout=max(TIMEOUTS.values()) + 5):
            src_name, role = futures_map[future]
            try:
                res = future.result(timeout=5)
                results.append(res)
            except TimeoutError:
                fallback = DataSourceResult(src_name, data_type)
                fallback.error = "探测超时"
                fallback.score = 0
                results.append(fallback)
            except Exception as e:
                fallback = DataSourceResult(src_name, data_type)
                fallback.error = str(e)
                fallback.score = 0
                results.append(fallback)

    # 按得分降序排列
    results.sort(key=lambda x: x.score, reverse=True)
    return results


def select_best(results: list[DataSourceResult], min_score: float = 50.0, data_type: str = "quote") -> tuple[DataSourceResult | None, str]:
    """
    从探测结果中选择最优源。
    
    竞争性数据类型（quote/index/commodity）的主力源优先策略：
    - 腾讯是行情快照的主力源，当得分差在15分以内时优先选择腾讯
    - 独有数据源（auction/tick/f10）不受此规则影响
    
    返回: (最佳结果, 决策理由)
    """
    if not results:
        return None, "无可用数据源"

    # 竞争性数据类型的主力源定义
    COMPETITIVE_TYPES = ("quote", "index", "commodity")
    PRIMARY_SOURCES = {"quote": "tencent", "index": "tencent", "commodity": "tencent"}
    
    # 按得分排序
    results_sorted = sorted(results, key=lambda x: x.score, reverse=True)
    
    best = results_sorted[0]
    runner_up = results_sorted[1] if len(results_sorted) > 1 else None

    if best.score < min_score:
        return None, f"所有数据源评分均低于{min_score}分阈值（最佳: {best.source}={best.score:.1f}）"

    # 竞争性数据类型：主力源优先策略
    if data_type in COMPETITIVE_TYPES and runner_up:
        primary_source = PRIMARY_SOURCES.get(data_type)
        
        # 检查是否有主力源参与竞争
        primary_result = next((r for r in results_sorted if r.source == primary_source), None)
        
        if primary_result and primary_result.score >= min_score:
            # 主力源与其他源得分差在15分以内时，优先选择主力源
            score_diff = best.score - primary_result.score
            
            if best.source != primary_source and score_diff <= 15:
                decision = (
                    f"{primary_source}胜出（主力源优先：{primary_source}={primary_result.score:.1f}分, "
                    f"{best.source}={best.score:.1f}分, 差距{score_diff:.1f}分在15分阈值内）"
                )
                return primary_result, decision
            
            # 主力源本身就是最高分，正常选择
            if best.source == primary_source:
                grade = _score_to_grade(best.score)
                decision = f"{best.source}胜出（评分:{best.score:.1f}/100, 等级:{grade}, 响应:{best.response_time_ms}ms）"
                return best, decision
    
    # 非竞争性数据类型或主力源不可用时：纯分数竞争
    # 多源得分接近时选最快的
    if runner_up and abs(best.score - runner_up.score) <= 10:
        if best.response_time_ms > runner_up.response_time_ms:
            decision = f"{runner_up.source}胜出（与{best.source}分数接近但更快：{runner_up.response_time_ms}ms vs {best.response_time_ms}ms）"
            return runner_up, decision

    grade = _score_to_grade(best.score)
    decision = f"{best.source}胜出（评分:{best.score:.1f}/100, 等级:{grade}, 响应:{best.response_time_ms}ms）"
    return best, decision


def _score_to_grade(score: float) -> str:
    """数值评分转为等级"""
    if score >= 85: return "A"
    if score >= 70: return "B"
    if score >= 50: return "C"
    return "D"


# ============================================================
# CLI命令
# ============================================================

def cmd_health():
    """检测所有数据源健康状态"""
    print("=" * 75)
    print(f"  [Health] 数据源健康检测  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 75)

    all_results = {}

    # 1. 检测腾讯接口
    print("\n[1/5] 检测腾讯行情接口...")
    tencent_result = TencentAdapter.fetch(INDEXES, TIMEOUTS["tencent"])
    all_results["tencent"] = tencent_result
    _print_source_result(tencent_result)

    # 2. 检测Wind
    print("\n[2/5] 检测Wind万得...")
    if WindAdapter._is_available():
        wind_result = WindAdapter.fetch("600519.SH", timeout=TIMEOUTS["wind"])
        all_results["wind"] = wind_result
        _print_source_result(wind_result)
    else:
        print(f"  ⚠️  Wind未安装（路径不存在: {WindAdapter.WIND_SKILL_DIR}）")
        dummy = DataSourceResult("wind", "quote")
        dummy.error = "未安装"
        dummy.score = 0
        all_results["wind"] = dummy

    # 3. 检测ftshare
    print("\n[3/5] 检测FTShare公告...")
    if FtShareAdapter._is_available():
        ft_result = FtShareAdapter.fetch("600170.SH", timeout=TIMEOUTS["ftshare"])
        all_results["ftshare"] = ft_result
        _print_source_result(ft_result)
    else:
        print(f"  ⚠️  FTShare未安装（路径不存在: {FtShareAdapter.FTSHARE_DIR}）")
        dummy = DataSourceResult("ftshare", "announcement")
        dummy.error = "未安装"
        dummy.score = 0
        all_results["ftshare"] = dummy

    # 4. 检测eltdx（独有数据源）
    print("\n[4/5] 检测eltdx通达信行情协议...")
    if EltdxAdapter._is_available():
        eltdx_scores = []
        eltdx_status = []
        
        # 4a. 行情快照
        try:
            eltdx_q = EltdxAdapter.fetch_quote(["sz000001"], timeout=5)
            eltdx_scores.append(eltdx_q.score)
            eltdx_status.append(f"行情快照: {'可用' if eltdx_q.success else '不可用'} ({eltdx_q.response_time_ms}ms)")
        except Exception as e:
            eltdx_status.append(f"行情快照: 异常({e})")
        
        # 4b. 集合竞价（独有）
        try:
            eltdx_a = EltdxAdapter.fetch_auction(["sz000001"], timeout=5)
            eltdx_scores.append(eltdx_a.score)
            eltdx_status.append(f"集合竞价(独有): {'可用' if eltdx_a.success else '不可用'} ({eltdx_a.response_time_ms}ms)")
        except Exception as e:
            eltdx_status.append(f"集合竞价: 异常({e})")
        
        # 4c. 分时数据
        try:
            eltdx_m = EltdxAdapter.fetch_minute("sz000001", timeout=5)
            eltdx_scores.append(eltdx_m.score)
            eltdx_status.append(f"分时数据: {'可用' if eltdx_m.success else '不可用'} ({eltdx_m.response_time_ms}ms)")
        except Exception as e:
            eltdx_status.append(f"分时数据: 异常({e})")
        
        # 综合评分
        avg_score = sum(eltdx_scores) / len(eltdx_scores) if eltdx_scores else 0
        eltdx_result = DataSourceResult("eltdx", "multi")
        eltdx_result.score = avg_score
        eltdx_result.success = any(s > 50 for s in eltdx_scores)
        eltdx_result.response_time_ms = 0
        eltdx_result.error = " | ".join(eltdx_status)
        all_results["eltdx"] = eltdx_result
        
        print(f"  [eltdx] 综合评分: {avg_score:.1f}/100")
        for status in eltdx_status:
            print(f"    - {status}")
    else:
        print("  [eltdx] 未安装（pip install eltdx）")
        dummy = DataSourceResult("eltdx", "quote")
        dummy.error = "未安装"
        dummy.score = 0
        all_results["eltdx"] = dummy

    # 5. 检测东方财富MCP特色数据（多端点探测）
    print("\n[5/5] 检测东方财富MCP特色数据...")
    if EastMoneyAdapter._is_available():
        # 得分 = 各端点探测结果综合
        em_scores = []
        endpoints_status = []

        # 5a. 行情端（Sina日线兜底）
        try:
            em_q = EastMoneyAdapter.fetch(["sh600170"], timeout=TIMEOUTS["eastmoney"], data_type="quote")
            em_scores.append(em_q.score)
            endpoints_status.append(f"行情(Sina日线): {'可用' if em_q.success else '不可用'} ({em_q.response_time_ms}ms)")
        except Exception as e:
            endpoints_status.append(f"行情: 异常({e})")

        # 5b. 北向资金
        try:
            em_nb = EastMoneyAdapter.fetch([], timeout=10, data_type="northbound")
            em_scores.append(em_nb.score if em_nb.success else 0)
            endpoints_status.append(f"北向资金: {'可用' if em_nb.success else '不可用'} ({em_nb.response_time_ms}ms)")
        except Exception as e:
            endpoints_status.append(f"北向资金: 异常({e})")

        # 5c. 龙虎榜
        try:
            em_dt = EastMoneyAdapter.fetch([], timeout=10, data_type="dragontiger")
            em_scores.append(em_dt.score if em_dt.success else 0)
            endpoints_status.append(f"龙虎榜: {'可用' if em_dt.success else '不可用'} ({em_dt.response_time_ms}ms)")
        except Exception as e:
            endpoints_status.append(f"龙虎榜: 异常({e})")

        # 5d. 涨停池
        try:
            em_lp = EastMoneyAdapter.fetch([], timeout=10, data_type="limitpool")
            em_scores.append(em_lp.score if em_lp.success else 0)
            endpoints_status.append(f"涨停池: {'可用' if em_lp.success else '不可用'} ({em_lp.response_time_ms}ms)")
        except Exception as e:
            endpoints_status.append(f"涨停池: 异常({e})")

        # 综合评分
        avg_score = sum(em_scores) / len(em_scores) if em_scores else 0
        em_result = DataSourceResult("eastmoney", "multi")
        em_result.score = avg_score
        em_result.success = any(s > 50 for s in em_scores)
        em_result.response_time_ms = 0
        em_result.error = " | ".join(endpoints_status)
        all_results["eastmoney"] = em_result

        print(f"  [eastmoney] 综合评分: {avg_score:.1f}/100")
        for status in endpoints_status:
            print(f"    - {status}")
    else:
        print("  [eastmoney] AKShare未安装")
        dummy = DataSourceResult("eastmoney", "quote")
        dummy.error = "AKShare未安装"
        dummy.score = 0
        all_results["eastmoney"] = dummy

    # 汇总
    print("\n" + "=" * 75)
    print("  📊 汇总")
    print("=" * 75)
    print(f"{'数据源':<12} {'状态':^6} {'评分':^8} {'响应':^10} {'等级':^6} {'特色'}")
    print("-" * 75)
    
    features = {
        "tencent": "行情/分时",
        "wind": "深度数据",
        "ftshare": "公告",
        "eltdx": "竞价/逐笔/F10",
        "eastmoney": "龙虎榜/北向"
    }
    
    for name, res in all_results.items():
        status = "✅ 正常" if res.success and res.score >= 50 else "⚠️ 异常" if res.score >= 20 else "❌ 不可用"
        grade = _score_to_grade(res.score)
        rt_str = f"{res.response_time_ms}ms" if res.response_time_ms > 0 else "N/A"
        feat = features.get(name, "")
        print(f"{name:<12} {status:^6} {res.score:^8.1f} {rt_str:^10} {grade:^6} {feat}")

    best_name = max(all_results.keys(), key=lambda k: all_results[k].score)
    best = all_results[best_name]
    print(f"\n🏆 最佳数据源: {best_name}（评分 {best.score:.1f}, 等级 {_score_to_grade(best.score)}）")
    
    # 显示独有数据源状态
    eltdx_res = all_results.get("eltdx")
    if eltdx_res and eltdx_res.success:
        print(f"🎯 独有数据源: eltdx 已就绪（集合竞价/逐笔成交/F10资料）")


def cmd_quote(codes: list[str] | None = None, output_json: bool = False):
    """获取实时行情（自动选最优源）"""
    target_codes = codes or INDEXES

    # 并行探测
    results = probe_sources("quote", codes=target_codes)
    best, reason = select_best(results, data_type="quote")

    if output_json:
        output = {
            "timestamp": datetime.now().isoformat(),
            "best_source": best.source if best else None,
            "reason": reason,
            "all_probes": [r.to_dict() for r in results],
            "data": best.parsed if best and best.parsed else None,
        }
        print(json.dumps(output, ensure_ascii=False, indent=2))
        return

    if not best:
        print(f"❌ {reason}")
        return

    print(f"✅ 选择: {reason}\n")
    if best.source == "tencent" and best.parsed:
        _print_quote_table(best.parsed)
    elif best.source == "wind":
        print(best.data)


def cmd_watchlist(output_json: bool = False):
    """获取自选股行情"""
    codes = [item[0] for item in WATCHLIST]
    results = probe_sources("quote", codes=codes)
    best, reason = select_best(results, data_type="quote")

    if output_json:
        output = {
            "timestamp": datetime.now().isoformat(),
            "best_source": best.source if best else None,
            "reason": reason,
            "watchlist_data": best.parsed if best and best.parsed else None,
        }
        print(json.dumps(output, ensure_ascii=False, indent=2))
        return

    if not best:
        print(f"❌ {reason}")
        return

    print(f"📊 自选股行情 ({datetime.now().strftime('%H:%M:%S')}) | 来源: {best.source.upper()} ({_score_to_grade(best.score)}级)\n")
    print(f"{'名称':<8} {'代码':<10} {'最新价':>8} {'涨跌幅':>8} {'成交量':>12} {'响应':>8}")
    print("-" * 62)

    if best.source == "tencent" and best.parsed:
        watch_codes = set(item[0].replace("sh", "").replace("sz", "") for item in WATCHLIST)
        for rec in best.parsed:
            code_raw = rec.get("code", "")
            if any(code_raw.endswith(c) for c in watch_codes):
                price = f"{rec.get('price', '-'):.2f}" if rec.get("price") else "-"
                chg_pct = f"{rec.get('change_pct', '-')}%" if rec.get('change_pct') is not None else "-"
                vol = rec.get("volume")
                vol_str = f"{vol:,}" if vol else "-"
                name = rec.get("name", "-")[:6]
                print(f"{name:<8} {code_raw:<10} {price:>8} {chg_pct:>8} {vol_str:>12} {best.response_time_ms:>7}ms")
    else:
        print(best.data)


def cmd_compare(code: str, data_type: str = "quote"):
    """对比多个数据源的同一条数据"""
    print(f"⚖️  数据源对比: {code} ({data_type})\n")

    all_results = []

    # 腾讯
    print("🔵 探测腾讯接口...")
    # 转换Wind格式代码为腾讯格式（去掉.SH/.SZ前缀，加sh/sz前缀）
    tencent_code = code.replace(".SH", "").replace(".SZ", "")
    if not tencent_code.startswith(("sh", "sz", "us", "hk")):
        if tencent_code.startswith("6") or tencent_code.startswith("5"):
            tencent_code = "sh" + tencent_code
        elif tencent_code.startswith("0") or tencent_code.startswith("3"):
            tencent_code = "sz" + tencent_code
        else:
            tencent_code = "sh" + tencent_code
    t_res = TencentAdapter.fetch([tencent_code], TIMEOUTS["tencent"])
    all_results.append(t_res)
    _print_source_result(t_res)

    # Wind
    if data_type == "quote" and WindAdapter._is_available():
        print("🟢 探测Wind...")
        w_res = WindAdapter.fetch(code, timeout=TIMEOUTS["wind"])
        all_results.append(w_res)
        _print_source_result(w_res)

    # 东方财富MCP特色数据
    if data_type == "quote" and EastMoneyAdapter._is_available():
        print("🟡 探测东方财富MCP(行情Sina日线)...")
        tc = code.replace(".SH", "").replace(".SZ", "")
        px = "sh" if code.endswith(".SH") else "sz" if code.endswith(".SZ") else "sh"
        e_res = EastMoneyAdapter.fetch([px + tc], timeout=TIMEOUTS["eastmoney"], data_type="quote")
        all_results.append(e_res)
        _print_source_result(e_res)

    # 对比表
    print(f"\n{'='*55}")
    print(f"{'数据源':<10} {'评分':>6} {'可用性':>6} {'及时性':>6} {'质量':>6} {'响应ms':>8}")
    print("-" * 55)
    for r in sorted(all_results, key=lambda x: x.score, reverse=True):
        grade = _score_to_grade(r.score)
        print(f"{r.source:<10} {r.score:>5.1f}{grade:<1} {r.availability_score:>6.0f} "
              f"{r.timeliness_score:>6.0f} {r.quality_score:>6.0f} {r.response_time_ms:>8}")

    # 一致性检查（如果有两个以上源成功）
    successes = [r for r in all_results if r.success]
    if len(successes) >= 2:
        print(f"\n📋 一致性检查:")
        # 如果是腾讯和Wind都有价格数据，对比价格差异
        prices = {}
        for r in successes:
            if r.source == "tencent" and r.parsed:
                for item in r.parsed:
                    if item.get("price"):
                        prices[r.source] = item["price"]
            elif r.source == "wind" and r.data:
                # Wind原始数据中尝试找价格
                try:
                    d = json.loads(r.data) if isinstance(r.data, str) else r.data
                    if isinstance(d, dict):
                        for k, v in d.items():
                            if "价" in k and isinstance(v, (int, float)):
                                prices[r.source] = v
                                break
                except:
                    pass

        if len(prices) >= 2:
            sources_list = list(prices.keys())
            p1, p2 = prices[sources_list[0]], prices[sources_list[1]]
            diff_abs = abs(p1 - p2)
            diff_pct = (diff_abs / max(p1, p2)) * 100 if max(p1, p2) > 0 else 0
            status = "✅ 高度一致" if diff_pct < 0.5 else "⚠️ 有偏差" if diff_pct < 2 else "❌ 差异较大"
            print(f"  {sources_list[0]}: {p1} vs {sources_list[1]}: {p2} → 差异 {diff_abs:.2f} ({diff_pct:.2f}%) {status}")


def cmd_northbound(output_json: bool = False):
    """查询北向资金净流向（需要EastMoneyAdapter）"""
    if not EastMoneyAdapter._is_available():
        print("❌ AKShare未安装，无法查询北向资金")
        return

    print("🔍 查询北向资金流向...")
    result = EastMoneyAdapter.fetch([], timeout=10, data_type="northbound")

    if output_json:
        print(json.dumps({
            "timestamp": datetime.now().isoformat(),
            "source": "eastmoney",
            "success": result.success,
            "data": result.parsed,
            "error": result.error,
        }, ensure_ascii=False, indent=2, default=str))
        return

    if result.success:
        data = result.parsed
        print(f"\n📊 北向资金最新流向 ({datetime.now().strftime('%Y-%m-%d %H:%M')})")
        print(f"{'指标':<16} {'数值':>14}")
        print("-" * 34)
        key_map = {
            "当日成交净买额": "当日净买额(亿)",
            "买入成交额": "买入额(亿)",
            "卖出成交额": "卖出额(亿)",
            "当日资金流入": "资金流入(亿)",
            "持股市值": "持股市值(亿)",
            "领涨股": "领涨股",
            "领涨股-涨跌幅": "领涨股涨跌幅(%)",
            "领涨股-代码": "领涨股代码",
            "沪深300": "沪深300点位",
            "沪深300-涨跌幅": "沪深300涨跌幅(%)",
        }
        for orig_key, label in key_map.items():
            if orig_key in data:
                val = data[orig_key]
                if isinstance(val, float):
                    print(f"{label:<16} {val:>14.2f}")
                else:
                    print(f"{label:<16} {str(val):>14}")
    else:
        print(f"❌ 查询失败: {result.error}")


def cmd_dragontiger(output_json: bool = False):
    """查询龙虎榜（需要EastMoneyAdapter）"""
    if not EastMoneyAdapter._is_available():
        print("❌ AKShare未安装，无法查询龙虎榜")
        return

    print("🔍 查询龙虎榜（近10天）...")
    result = EastMoneyAdapter.fetch([], timeout=10, data_type="dragontiger")

    if output_json:
        print(json.dumps({
            "timestamp": datetime.now().isoformat(),
            "source": "eastmoney",
            "success": result.success,
            "count": len(result.parsed) if result.parsed else 0,
            "data": result.parsed,
            "error": result.error,
        }, ensure_ascii=False, indent=2, default=str))
        return

    if result.success and result.parsed:
        print(f"\n📊 龙虎榜 TOP10 ({datetime.now().strftime('%Y-%m-%d %H:%M')})")
        print(f"{'代码':<10} {'名称':<10} {'净买额(万)':>12} {'涨跌幅':>8} {'上榜原因':<16}")
        print("-" * 62)
        for row in result.parsed[:10]:
            code = str(row.get("代码", "") or "")
            name = (str(row.get("名称", "") or ""))[:9]
            net = _safe_float(row.get("龙虎榜净买额"))
            net_str = f"{net/10000:.0f}" if net else "-"
            pct = _safe_float(row.get("涨跌幅"))
            pct_str = f"{pct:+.2f}%" if pct is not None else "-"
            reason = (str(row.get("上榜原因", "") or ""))[:15]
            print(f"{code:<10} {name:<10} {net_str:>12} {pct_str:>8} {reason:<16}")
    else:
        print(f"  {result.error or '无数据'}")


def cmd_limitpool(output_json: bool = False):
    """查询涨停板池（需要EastMoneyAdapter）"""
    if not EastMoneyAdapter._is_available():
        print("❌ AKShare未安装，无法查询涨停池")
        return

    print("🔍 查询涨停板池...")
    result = EastMoneyAdapter.fetch([], timeout=10, data_type="limitpool")

    if output_json:
        print(json.dumps({
            "timestamp": datetime.now().isoformat(),
            "source": "eastmoney",
            "success": result.success,
            "count": len(result.parsed) if result.parsed else 0,
            "data": result.parsed,
            "error": result.error,
        }, ensure_ascii=False, indent=2, default=str))
        return

    if result.success and result.parsed:
        print(f"\n📊 涨停板池 TOP10 ({datetime.now().strftime('%Y-%m-%d %H:%M')})")
        print(f"{'代码':<10} {'名称':<10} {'涨跌幅':>8} {'封单额':>12} {'连板数':>6}")
        print("-" * 52)
        for row in result.parsed[:10]:
            code = str(row.get("代码", "") or "")
            name = (str(row.get("名称", "") or ""))[:9]
            pct = _safe_float(row.get("涨跌幅"))
            pct_str = f"{pct:.2f}%" if pct else "-"
            seal = _safe_float(row.get("封单额"))
            seal_str = f"{seal/1e8:.2f}亿" if seal else "-"
            board = row.get("连板数", "-")
            print(f"{code:<10} {name:<10} {pct_str:>8} {seal_str:>12} {str(board):>6}")
    else:
        print(f"  {result.error or '无数据'}")


# ============================================================
# MarketAnalyzerAdapter - 全市场综合分析引擎 (v3.2)
# ============================================================

class MarketAnalyzerAdapter:
    """
    全市场综合分析引擎适配器。

    封装 trader-finance-hub/src/market_analyzer.py 的核心能力，
    通过 data_router 统一入口调用。
    """

    NAME = "market_analyzer"

    @staticmethod
    def _import_analyzer():
        """动态导入 market_analyzer 模块"""
        # data_router.py 位置: ~/.workbuddy/skills/trader-data-router/data_router.py
        # market_analyzer 位置: ~/WorkBuddy/Claw/trader-finance-hub/src/market_analyzer.py
        hub_src = Path.home() / "WorkBuddy" / "Claw" / "trader-finance-hub" / "src"
        if str(hub_src) not in sys.path:
            sys.path.insert(0, str(hub_src))
        from market_analyzer import NewsFetcher, THSDataFetcher, MarketModels
        return NewsFetcher, THSDataFetcher, MarketModels

    @classmethod
    def fetch_news(cls, stock_code: str = "600170") -> dict:
        """获取头条新闻"""
        NewsFetcher, _, _ = cls._import_analyzer()
        headlines = NewsFetcher.fetch_headlines(stock_code)
        return {
            "count": len(headlines),
            "headlines": [
                {"title": h.title, "source": h.source, "sentiment": h.sentiment,
                 "impact": h.impact_score, "time": h.publish_time}
                for h in headlines
            ]
        }

    @classmethod
    def fetch_sector_analysis(cls, max_sectors: int = 40) -> dict:
        """板块四象限分析"""
        _, THSDataFetcher, MarketModels = cls._import_analyzer()
        sectors = THSDataFetcher.get_concept_batch_quotes([], max_names=max_sectors)
        if not sectors:
            return {"error": "无板块数据"}
        quad = MarketModels.four_quadrant(sectors)
        entropy = MarketModels.entropy_consensus(quad)
        return {
            "total_sectors": len(sectors),
            "entropy": entropy["entropy"],
            "consensus_level": entropy["consensus_level"],
            "distribution": entropy["distribution"],
            "quadrants": [
                {"name": q.name, "change_pct": q.change_pct, "quadrant": q.quadrant,
                 "consensus": q.consensus_strength, "volume_ratio": q.volume_ratio}
                for q in quad[:20]
            ]
        }

    @classmethod
    def fetch_sentiment_clock(cls, market_change: float = 0, up_down: float = 1,
                               lt_up: int = 0, lt_down: int = 0, nb_net: float = 0) -> dict:
        """情绪时钟"""
        _, _, MarketModels = cls._import_analyzer()
        return MarketModels.sentiment_clock(market_change, up_down, lt_up, lt_down, nb_net)

    @classmethod
    def fetch_full_report(cls) -> dict:
        """生成全市场综合分析报告"""
        try:
            hub_src = Path.home() / "WorkBuddy" / "Claw" / "trader-finance-hub" / "src"
            if str(hub_src) not in sys.path:
                sys.path.insert(0, str(hub_src))
            from market_analyzer import cmd_report
            return cmd_report()
        except Exception as e:
            return {"error": str(e), "timestamp": datetime.now().isoformat()}


# ============================================================
# 输出辅助
# ============================================================

def _print_source_result(res: DataSourceResult):
    """打印单个数据源检测结果"""
    grade = _score_to_grade(res.score)
    status_icon = "✅" if res.success and res.score >= 50 else "⚠️" if res.score >= 20 else "❌"
    print(f"  {status_icon} [{res.source.upper()}] 评分: {res.score:.1f}/100 ({grade}级)")
    print(f"     响应时间: {res.response_time_ms}ms")
    print(f"     可用性: {res.availability_score:.0f} | 及时性: {res.timeliness_score:.0f} | 质量: {res.quality_score:.0f}")
    if res.error:
        print(f"     错误: {res.error}")
    if res.success:
        preview = str(res.data)[:120] if res.data else "(空)"
        print(f"     数据预览: {preview}...")


def _print_quote_table(records: list[dict]):
    """打印行情表格"""
    print(f"{'名称':<8} {'代码':<10} {'最新价':>8} {'涨跌额':>8} {'涨跌幅':>8} {'成交量(手)':>12} {'成交额':>14}")
    print("-" * 74)
    for r in records:
        price = f"{r.get('price', '-'):.2f}" if r.get("price") is not None else "-"
        chg = f"{r.get('change_amt', '-'):+.2f}" if r.get("change_amt") is not None else "-"
        chg_pct = f"{r.get('change_pct', '-')}%" if r.get("change_pct") is not None else "-"
        vol = f"{r.get('volume', '-'):,}" if r.get("volume") is not None else "-"
        amt = f"{r.get('amount', '-'):,}" if r.get("amount") is not None else "-"
        name = (r.get("name", "-") or "-")[:7]
        code = r.get("code", "-") or "-"
        print(f"{name:<8} {code:<10} {price:>8} {chg:>8} {chg_pct:>8} {vol:>12} {amt:>14}")


# ============================================================
# 全市场综合分析命令 (v3.2)
# ============================================================

def cmd_market_news(output_json: bool = False):
    """全市场财经要闻"""
    print("[MarketAnalyzer] 采集多源财经要闻...")
    try:
        result = MarketAnalyzerAdapter.fetch_news()
        if output_json:
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return
        print(f"\n{'='*60}")
        print(f"  今日财经要闻 TOP{result['count']} ({datetime.now().strftime('%Y-%m-%d %H:%M')})")
        print(f"{'='*60}")
        for i, h in enumerate(result.get("headlines", []), 1):
            s = h.get("sentiment", "neutral")
            e = {"positive": "[+]", "negative": "[-]", "neutral": "[*]"}.get(s, "[*]")
            print(f"\n{i:2d}. {e} {h.get('title', '')}")
            print(f"    来源: {h.get('source', '')} | 影响度: {h.get('impact', 0):.0f} | {h.get('time', '')}")
    except Exception as e:
        print(f"[FAIL] {e}")


def cmd_market_sector(output_json: bool = False):
    """板块四象限分析"""
    print("[MarketAnalyzer] 获取板块数据并计算四象限（约需1-2分钟）...")
    try:
        result = MarketAnalyzerAdapter.fetch_sector_analysis()
        if output_json:
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return
        print(f"\n{'='*60}")
        print(f"  板块四象限分析 ({datetime.now().strftime('%Y-%m-%d %H:%M')})")
        print(f"  板块数: {result.get('total_sectors', 0)} | 信息熵: {result.get('entropy', '?')} -> {result.get('consensus_level', '?')}")
        print(f"{'='*60}")
        by_q = {}
        for q in result.get("quadrants", []):
            by_q.setdefault(q["quadrant"], []).append(q)
        labels = {"I": "强共识上涨", "II": "弱共识上涨", "III": "弱共识下跌", "IV": "强共识下跌"}
        for qk in ["I", "II", "III", "IV"]:
            items = by_q.get(qk, [])
            items.sort(key=lambda x: abs(x["change_pct"]), reverse=True)
            print(f"\n[象限{qk}] {labels.get(qk, '')}: {len(items)}个板块")
            print(f"{'板块':<16} {'涨跌幅':>8} {'共识':>6} {'量比':>5}")
            print("-" * 40)
            for item in items[:6]:
                print(f"{item['name']:<16} {item['change_pct']:>+7.2f}% {item['consensus']:>5.0f} {item['volume_ratio']:>4.2f}x")
    except Exception as e:
        print(f"[FAIL] {e}")


def cmd_market_sentiment(output_json: bool = False):
    """情绪时钟"""
    print("[MarketAnalyzer] 计算情绪时钟...")
    try:
        result = MarketAnalyzerAdapter.fetch_sentiment_clock()
        if output_json:
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return
        print(f"\n{'='*60}")
        print(f"  市场情绪时钟 ({datetime.now().strftime('%Y-%m-%d %H:%M')})")
        print(f"{'='*60}")
        print(f"  评分: {result['total_score']}/100 -> {result['phase']}")
        print(f"  {result['description']}")
        print(f"  建议: {result['action']}")
        print(f"\n  维度评分:")
        for dim, score in result.get("breakdown", {}).items():
            bar = "#" * int(score / 2.5) + "-" * (10 - int(score / 2.5))
            print(f"    {dim}: {bar} {score}/25")
    except Exception as e:
        print(f"[FAIL] {e}")


def cmd_market_report(output_json: bool = False):
    """生成全市场综合分析报告JSON"""
    print("[MarketAnalyzer] 生成全市场综合分析报告（约需2-3分钟）...")
    try:
        result = MarketAnalyzerAdapter.fetch_full_report()
        output_path = Path.home() / "WorkBuddy" / "Claw" / "reports" / f"market_report_{datetime.now().strftime('%Y%m%d_%H%M')}.json"
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2, default=str)
        print(f"\n报告已保存: {output_path}")
        modules = result.get("modules", {})
        nc = modules.get("news", {}).get("count", 0)
        ns = modules.get("sector_analysis", {}).get("total_sectors", 0)
        clk = modules.get("sentiment_clock", {}).get("phase", "?")
        ht = len(modules.get("hot_rank", {}).get("top30", []))
        print(f"摘要: 新闻{nc}条 | 板块{ns}个 | 情绪{clk} | 热门{ht}只")
    except Exception as e:
        print(f"[FAIL] {e}")


# ============================================================
# 入口
# ============================================================

def cmd_auction(codes: list[str], output_json: bool = False):
    """获取集合竞价数据（eltdx独有功能）"""
    if not EltdxAdapter._is_available():
        print("❌ eltdx未安装，请先执行: pip install eltdx")
        return
    
    print(f"🔍 查询集合竞价数据...")
    results = probe_sources("auction", codes=codes)
    
    if not results:
        print("❌ 无可用数据源")
        return
    
    best = results[0]
    
    if output_json:
        print(json.dumps({
            "timestamp": datetime.now().isoformat(),
            "source": best.source,
            "success": best.success,
            "data": best.parsed,
            "error": best.error,
        }, ensure_ascii=False, indent=2))
        return
    
    if best.success and best.parsed:
        print(f"\n📊 集合竞价数据 ({datetime.now().strftime('%Y-%m-%d %H:%M')})")
        print(f"数据源: eltdx (独有功能)")
        print("=" * 70)
        
        for code, data in best.parsed.items():
            if data.get('status') == 'success':
                print(f"\n📈 {code}")
                print(f"  ├─ 竞价点数: {data.get('points', 0)}")
                print(f"  ├─ 最新价格: {data.get('last_price', '-')} 元")
                print(f"  ├─ 匹配量: {data.get('last_matched_volume', '-')} 手")
                print(f"  ├─ 总成交额: {data.get('total_amount', 0):,.0f} 元")
                print(f"  └─ 最后时间: {data.get('last_time', '-')}")
            else:
                print(f"\n❌ {code}: {data.get('message', '无数据')}")
    else:
        print(f"❌ 获取失败: {best.error}")


def cmd_tick(code: str, date: str, output_json: bool = False):
    """获取逐笔成交数据（eltdx独有功能）"""
    if not EltdxAdapter._is_available():
        print("❌ eltdx未安装，请先执行: pip install eltdx")
        return
    
    print(f"🔍 查询逐笔成交数据...")
    results = probe_sources("tick", code=code, date=date)
    
    if not results:
        print("❌ 无可用数据源")
        return
    
    best = results[0]
    
    if output_json:
        print(json.dumps({
            "timestamp": datetime.now().isoformat(),
            "source": best.source,
            "success": best.success,
            "data": best.parsed,
            "error": best.error,
        }, ensure_ascii=False, indent=2))
        return
    
    if best.success and best.parsed:
        data = best.parsed
        print(f"\n📈 逐笔成交数据 ({date})")
        print(f"数据源: eltdx (独有功能)")
        print("=" * 70)
        
        if data.get('status') == 'success':
            buy_ratio = data['buy_count'] / data['ticks'] * 100 if data['ticks'] > 0 else 0
            
            print(f"\n📊 {code}")
            print(f"  ├─ 成交笔数: {data.get('ticks', 0)}")
            print(f"  ├─ 买入笔数: {data.get('buy_count', 0)} ({buy_ratio:.1f}%)")
            print(f"  ├─ 卖出笔数: {data.get('sell_count', 0)} ({100-buy_ratio:.1f}%)")
            print(f"  ├─ 总成交额: {data.get('total_amount', 0):,.0f} 元")
            
            last_tick = data.get('last_tick')
            if last_tick:
                print(f"  └─ 最新成交: {last_tick.get('time', '-')} {last_tick.get('price', '-')}元 {last_tick.get('volume', '-')}手")
            
            # 显示最后几笔成交
            details = data.get('details', [])
            if details:
                print(f"\n📋 最后{len(details)}笔成交:")
                print(f"{'时间':<10} {'价格':>8} {'数量':>8} {'金额':>12} {'方向':<6}")
                print("-" * 50)
                for tick in details[-10:]:
                    print(f"{tick.get('time', '-'):<10} {tick.get('price', '-'):>8} {tick.get('volume', '-'):>8} {tick.get('amount', 0):>12,.0f} {tick.get('buy_or_sell', '-'):<6}")
        else:
            print(f"❌ {code}: {data.get('message', '无数据')}")
    else:
        print(f"❌ 获取失败: {best.error}")


def cmd_f10(code: str, output_json: bool = False):
    """获取F10资料数据（eltdx独有功能）"""
    if not EltdxAdapter._is_available():
        print("❌ eltdx未安装，请先执行: pip install eltdx")
        return
    
    print(f"🔍 查询F10资料...")
    results = probe_sources("f10", code=code)
    
    if not results:
        print("❌ 无可用数据源")
        return
    
    best = results[0]
    
    if output_json:
        print(json.dumps({
            "timestamp": datetime.now().isoformat(),
            "source": best.source,
            "success": best.success,
            "data": best.parsed,
            "error": best.error,
        }, ensure_ascii=False, indent=2))
        return
    
    if best.success and best.parsed:
        data = best.parsed
        print(f"\n🏢 F10资料")
        print(f"数据源: eltdx (独有功能)")
        print("=" * 70)
        
        if data.get('status') == 'success':
            profile = data.get('profile', {})
            topics = data.get('topics', [])
            finance = data.get('finance', {})
            
            print(f"\n📊 {code}")
            print(f"  ├─ 公司名称: {profile.get('name', '未知')}")
            print(f"  ├─ 所属行业: {profile.get('industry', '未知')}")
            print(f"  ├─ 上市日期: {profile.get('list_date', '未知')}")
            print(f"  ├─ 主营业务: {profile.get('main_business', '未知')[:50]}...")
            
            if topics:
                print(f"  ├─ 热点题材:")
                for t in topics[:3]:
                    print(f"  │   • {t.get('name', '')}: {t.get('reason', '')}")
            
            if finance:
                print(f"  └─ 财务评分: {finance.get('score', '未知')} (运营:{finance.get('operation', '-')} 盈利:{finance.get('profit', '-')} 成长:{finance.get('growth', '-')})")
        else:
            print(f"❌ {code}: {data.get('message', '无数据')}")
    else:
        print(f"❌ 获取失败: {best.error}")


def cmd_minute(code: str, output_json: bool = False):
    """获取分时数据（eltdx提供）"""
    if not EltdxAdapter._is_available():
        print("❌ eltdx未安装，请先执行: pip install eltdx")
        return
    
    print(f"🔍 查询分时数据...")
    results = probe_sources("minute", code=code)
    
    if not results:
        print("❌ 无可用数据源")
        return
    
    best = results[0]
    
    if output_json:
        print(json.dumps({
            "timestamp": datetime.now().isoformat(),
            "source": best.source,
            "success": best.success,
            "data": best.parsed,
            "error": best.error,
        }, ensure_ascii=False, indent=2))
        return
    
    if best.success and best.parsed:
        data = best.parsed
        print(f"\n📈 分时数据")
        print(f"数据源: eltdx")
        print("=" * 70)
        
        if data.get('status') == 'success':
            print(f"\n📊 {code}")
            print(f"  ├─ 交易日期: {data.get('trading_date', '-')}")
            print(f"  ├─ 昨收价: {data.get('prev_close', '-')} 元")
            print(f"  ├─ 开盘价: {data.get('open_price', '-')} 元")
            print(f"  ├─ 均价: {data.get('avg_price', 0):.2f} 元")
            print(f"  ├─ 分时点数: {data.get('points', 0)}")
            
            last_point = data.get('last_point')
            if last_point:
                print(f"  └─ 最新分时: {last_point.get('time', '-')} 价格:{last_point.get('price', '-')}元 均价:{last_point.get('avg_price', '-')}元")
            
            # 显示最后几个分时点
            details = data.get('details', [])
            if details:
                print(f"\n📋 最后{len(details)}个分时点:")
                print(f"{'时间':<10} {'价格':>8} {'均价':>8} {'成交量':>10}")
                print("-" * 40)
                for point in details[-10:]:
                    print(f"{point.get('time', '-'):<10} {point.get('price', '-'):>8} {point.get('avg_price', '-'):>8} {point.get('volume', '-'):>10}")
        else:
            print(f"❌ {code}: {data.get('message', '无数据')}")
    else:
        print(f"❌ 获取失败: {best.error}")


def main():
    args = sys.argv[1:] if len(sys.argv) > 1 else ["health"]

    if not args or args[0] in ("health", "-h", "--help", "status"):
        if args[0] in ("-h", "--help"):
            print(__doc__)
            return
        cmd_health()

    elif args[0] == "quote":
        codes = None
        output_json = False
        i = 1
        while i < len(args):
            if args[i] in ("--codes", "-c") and i + 1 < len(args):
                codes = args[i + 1].split(",")
                i += 2
            elif args[i] == "--json":
                output_json = True
                i += 1
            else:
                i += 1
        cmd_quote(codes, output_json)

    elif args[0] in ("watchlist", "wl", "自选股"):
        output_json = "--json" in args
        cmd_watchlist(output_json)

    elif args[0] == "compare":
        code = "600170.SH"
        dtype = "quote"
        i = 1
        while i < len(args):
            if args[i] in ("--code", "-c") and i + 1 < len(args):
                code = args[i + 1]
                i += 2
            elif args[i] in ("--type", "-t") and i + 1 < len(args):
                dtype = args[i + 1]
                i += 2
            else:
                i += 1
        cmd_compare(code, dtype)

    elif args[0] in ("northbound", "nb", "北向资金"):
        output_json = "--json" in args
        cmd_northbound(output_json)

    elif args[0] in ("dragontiger", "dt", "龙虎榜"):
        output_json = "--json" in args
        cmd_dragontiger(output_json)

    elif args[0] in ("limitpool", "lp", "涨停池"):
        output_json = "--json" in args
        cmd_limitpool(output_json)

    # --- v3.3 eltdx独有数据 ---
    elif args[0] in ("auction", "竞价", "集合竞价"):
        codes = []
        output_json = False
        i = 1
        while i < len(args):
            if args[i] in ("--codes", "-c") and i + 1 < len(args):
                codes = args[i + 1].split(",")
                i += 2
            elif args[i] == "--json":
                output_json = True
                i += 1
            else:
                i += 1
        if not codes:
            codes = [item[0] for item in WATCHLIST]
        cmd_auction(codes, output_json)

    elif args[0] in ("tick", "逐笔", "逐笔成交"):
        code = ""
        date = datetime.now().strftime("%Y%m%d")
        output_json = False
        i = 1
        while i < len(args):
            if args[i] in ("--code", "-c") and i + 1 < len(args):
                code = args[i + 1]
                i += 2
            elif args[i] in ("--date", "-d") and i + 1 < len(args):
                date = args[i + 1]
                i += 2
            elif args[i] == "--json":
                output_json = True
                i += 1
            else:
                i += 1
        if not code:
            print("❌ 请指定股票代码: --code sz000001")
            return
        cmd_tick(code, date, output_json)

    elif args[0] in ("f10", "F10", "资料"):
        code = ""
        output_json = False
        i = 1
        while i < len(args):
            if args[i] in ("--code", "-c") and i + 1 < len(args):
                code = args[i + 1]
                i += 2
            elif args[i] == "--json":
                output_json = True
                i += 1
            else:
                i += 1
        if not code:
            print("❌ 请指定股票代码: --code 000001")
            return
        cmd_f10(code, output_json)

    elif args[0] in ("minute", "分时", "分时数据"):
        code = ""
        output_json = False
        i = 1
        while i < len(args):
            if args[i] in ("--code", "-c") and i + 1 < len(args):
                code = args[i + 1]
                i += 2
            elif args[i] == "--json":
                output_json = True
                i += 1
            else:
                i += 1
        if not code:
            print("❌ 请指定股票代码: --code sz000001")
            return
        cmd_minute(code, output_json)

    # --- v3.2 全市场综合分析 ---
    elif args[0] in ("news", "要闻"):
        output_json = "--json" in args
        cmd_market_news(output_json)

    elif args[0] in ("sector", "板块", "四象限"):
        output_json = "--json" in args
        cmd_market_sector(output_json)

    elif args[0] in ("sentiment", "情绪", "时钟"):
        output_json = "--json" in args
        cmd_market_sentiment(output_json)

    elif args[0] in ("report", "报告"):
        output_json = "--json" in args
        cmd_market_report(output_json)

    else:
        print(f"未知命令: {args[0]}")
        print("用法: python data_router.py [health|quote|watchlist|compare|northbound|dragontiger|limitpool|auction|tick|f10|minute|news|sector|sentiment|report] [--json]")
        sys.exit(1)


if __name__ == "__main__":
    main()
