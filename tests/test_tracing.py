# -*- coding: utf-8 -*-
"""配准描图工作台的数学部分（tools/描图工作台.py）回归用例。

为什么单独测这个：配准是整条"参考图 → 经纬度数据"链路的命门。
仿射解错了，后面描出来的边界会整体偏移/旋转/缩放错位，而且**看起来还很像样**，最难发现。
"""
import importlib.util
import math
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import 夹具  # noqa: E402

sys.path.insert(0, os.path.join(夹具.仓库根目录, "ui"))
import 地图  # noqa: E402

规格 = importlib.util.spec_from_file_location(
    "描图工作台", os.path.join(夹具.仓库根目录, "tools", "描图工作台.py"))
工作台 = importlib.util.module_from_spec(规格)
规格.loader.exec_module(工作台)


class 配准数学(unittest.TestCase):

    def test_能精确还原已知仿射变换(self):
        """构造一个已知的仿射变换，用它造控制点，再解回来必须一致。"""
        真系数 = (0.05, 0.01, 100.0, -0.008, 0.06, 500.0)      # a b c d e f
        控制点像素, 控制点世界 = [], []
        for u, v in ((100, 120), (900, 150), (500, 800), (1200, 900), (60, 700)):
            控制点像素.append((u, v))
            控制点世界.append(工作台.像素转世界(真系数, u, v))
        解出 = 工作台.解仿射(控制点像素, 控制点世界)
        self.assertIsNotNone(解出)
        for 期望, 实际 in zip(真系数, 解出):
            self.assertAlmostEqual(期望, 实际, places=6,
                                   msg="解出的仿射系数与真值不符")

    def test_三点即可解且残差为零(self):
        点像素 = [(0, 0), (1000, 0), (0, 800)]
        点世界 = [(200.0, 300.0), (260.0, 310.0), (208.0, 356.0)]
        系数 = 工作台.解仿射(点像素, 点世界)
        self.assertIsNotNone(系数)
        误差 = 工作台.残差(点像素, 点世界, 系数)
        self.assertLess(max(误差), 1e-9, "三点精确解应无残差")

    def test_点数不足返回None(self):
        self.assertIsNone(工作台.解仿射([(0, 0), (1, 1)], [(0.0, 0.0), (1.0, 1.0)]))

    def test_共线点被判为退化(self):
        """三点共线时无法确定唯一仿射，必须返回 None 而不是给出胡乱的解。"""
        点像素 = [(0, 0), (100, 100), (200, 200)]
        点世界 = [(0.0, 0.0), (10.0, 10.0), (20.0, 20.0)]
        self.assertIsNone(工作台.解仿射(点像素, 点世界), "共线点应判为退化")

    def test_经纬往返无损(self):
        """经纬度 → 投影 → 逆投影，必须回到原值（这是描图精度的一半）。"""
        for 经度, 纬度 in ((116.4, 39.9), (104.1, 30.6), (112.1, 32.0), (73.5, 39.5)):
            世界x, 世界y = 地图.投影(经度, 纬度)
            回去 = 工作台.世界转经纬(世界x, 世界y)
            self.assertAlmostEqual(经度, 回去[0], places=9)
            self.assertAlmostEqual(纬度, 回去[1], places=9)

    def test_像素经纬往返无损(self):
        """配准后：给定像素 → 经纬度 → 反向求像素，必须回到原点（描点不会漂）。"""
        真系数 = (0.05, 0.01, 100.0, -0.008, 0.06, 500.0)
        a, b, c, d, e, f = 真系数
        行列式 = a * e - b * d
        for u, v in ((100, 120), (640, 480), (1180, 830)):
            世界x, 世界y = 工作台.像素转世界(真系数, u, v)
            经度, 纬度 = 工作台.世界转经纬(世界x, 世界y)
            世界x2, 世界y2 = 地图.投影(经度, 纬度)
            u2 = (e * (世界x2 - c) - b * (世界y2 - f)) / 行列式
            v2 = (-d * (世界x2 - c) + a * (世界y2 - f)) / 行列式
            self.assertAlmostEqual(u, u2, places=6, msg="像素 u 往返不一致")
            self.assertAlmostEqual(v, v2, places=6, msg="像素 v 往返不一致")

    def test_残差能反映配准误差(self):
        """故意给一个错点，残差必须把它暴露出来。"""
        点像素 = [(0, 0), (1000, 0), (0, 800), (1000, 800)]
        点世界 = [(0.0, 0.0), (100.0, 0.0), (0.0, 80.0),
                (100.0, 80.0)]
        好系数 = 工作台.解仿射(点像素, 点世界)
        点世界错 = list(点世界)
        点世界错[3] = (400.0, 400.0)          # 第 4 点故意偏得很远
        坏系数 = 工作台.解仿射(点像素, 点世界错)
        好误差 = max(工作台.残差(点像素, 点世界, 好系数))
        坏误差 = max(工作台.残差(点像素, 点世界错, 坏系数))
        self.assertGreater(坏误差, 好误差 + 1.0, "错点应产生明显更大的残差")


if __name__ == "__main__":
    unittest.main(verbosity=2)
