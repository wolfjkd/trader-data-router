#!/usr/bin/env python3
"""
trader-data-router 单元测试
"""

import unittest
from unittest.mock import patch, MagicMock
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from data_router import (
    DataSourceResult,
    TencentAdapter,
    _score_to_grade,
    select_best,
    INDEXES,
    WATCHLIST,
)


class TestDataSourceResult(unittest.TestCase):
    """测试 DataSourceResult 类"""

    def test_init(self):
        result = DataSourceResult("test_source", "quote")
        self.assertEqual(result.source, "test_source")
        self.assertEqual(result.data_type, "quote")
        self.assertFalse(result.success)
        self.assertEqual(result.response_time_ms, 0)
        self.assertIsNone(result.data)
        self.assertIsNone(result.parsed)
        self.assertIsNone(result.error)
        self.assertEqual(result.score, 0.0)
        self.assertEqual(result.availability_score, 0.0)
        self.assertEqual(result.timeliness_score, 0.0)
        self.assertEqual(result.quality_score, 0.0)
        self.assertIsInstance(result.timestamp, str)

    def test_to_dict(self):
        result = DataSourceResult("tencent", "quote")
        result.success = True
        result.response_time_ms = 150
        result.score = 95.5
        result.availability_score = 100.0
        result.timeliness_score = 90.0
        result.quality_score = 97.0
        result.data = "test data"
        d = result.to_dict()
        self.assertEqual(d["source"], "tencent")
        self.assertTrue(d["success"])
        self.assertEqual(d["response_time_ms"], 150)
        self.assertEqual(d["score"], 95.5)
        self.assertEqual(d["has_data"], True)


class TestScoreToGrade(unittest.TestCase):
    """测试评分转等级"""

    def test_grade_a(self):
        self.assertEqual(_score_to_grade(85), "A")
        self.assertEqual(_score_to_grade(90), "A")
        self.assertEqual(_score_to_grade(100), "A")

    def test_grade_b(self):
        self.assertEqual(_score_to_grade(70), "B")
        self.assertEqual(_score_to_grade(84), "B")

    def test_grade_c(self):
        self.assertEqual(_score_to_grade(50), "C")
        self.assertEqual(_score_to_grade(69), "C")

    def test_grade_d(self):
        self.assertEqual(_score_to_grade(49), "D")
        self.assertEqual(_score_to_grade(0), "D")


class TestSelectBest(unittest.TestCase):
    """测试最优数据源选择"""

    def test_empty_results(self):
        result, reason = select_best([])
        self.assertIsNone(result)
        self.assertEqual(reason, "无可用数据源")

    def test_all_below_threshold(self):
        r1 = DataSourceResult("tencent", "quote")
        r1.score = 40.0
        result, reason = select_best([r1])
        self.assertIsNone(result)
        self.assertIn("低于50.0分阈值", reason)

    def test_single_best(self):
        r1 = DataSourceResult("tencent", "quote")
        r1.score = 90.0
        r1.response_time_ms = 200
        result, reason = select_best([r1])
        self.assertEqual(result.source, "tencent")
        self.assertIn("胜出", reason)

    def test_faster_when_close(self):
        r1 = DataSourceResult("tencent", "quote")
        r1.score = 85.0
        r1.response_time_ms = 500
        r2 = DataSourceResult("wind", "quote")
        r2.score = 82.0
        r2.response_time_ms = 200
        result, reason = select_best([r1, r2])
        self.assertEqual(result.source, "wind")
        self.assertIn("更快", reason)


class TestConfig(unittest.TestCase):
    """测试配置常量"""

    def test_indexes(self):
        self.assertEqual(len(INDEXES), 3)
        self.assertIn("sh000001", INDEXES)

    def test_watchlist_format(self):
        for item in WATCHLIST:
            self.assertIsInstance(item, tuple)
            self.assertEqual(len(item), 2)
            self.assertIsInstance(item[0], str)
            self.assertIsInstance(item[1], str)


if __name__ == "__main__":
    unittest.main()