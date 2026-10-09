# -*- coding: utf-8 -*-
"""投影本身的回归用例（ui/地图.py 的兰勃特等角圆锥）。

为什么单独测：投影是**所有地理数据的公共出口**。州郡界、城池、郡界骨架、州域对照图
全都经过它。投影一改，全项目的坐标一起变；改错了不会报错，只会"图慢慢变得不对"。

这些用例只依赖投影参数文件与纯数学，不需要图形界面。
"""
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import 夹具  # noqa: E402

sys.path.insert(0, os.path.join(夹具.仓库根目录, "ui"))
import 地图  # noqa: E402


class 圆锥投影(unittest.TestCase):

    def test_是圆锥而非等距圆柱(self):
        """等距圆柱下"1° 经度 → 像素宽"是常数；圆锥投影下它必须随纬度明显变小。

        这条就是"我们真的换成圆锥投影了"的判据，也正是当初换投影的目的。
        （按 cos 纬度算：48°N 处 1° 经度的实地距离约为 22°N 处的 0.72 倍。）
        """
        低纬左, 低纬右 = 地图.投影(106.0, 22.0), 地图.投影(107.0, 22.0)
        高纬左, 高纬右 = 地图.投影(106.0, 48.0), 地图.投影(107.0, 48.0)
        低纬跨 = abs(低纬右[0] - 低纬左[0])
        高纬跨 = abs(高纬右[0] - 高纬左[0])
        self.assertLess(高纬跨, 低纬跨 * 0.85,
                        f"48°N 处 1° 经度应明显窄于 22°N 处（实得 {高纬跨:.2f} vs {低纬跨:.2f}）")
        self.assertGreater(低纬跨 / 高纬跨, 1.2, "两者的比值应接近 cos 纬度之比")

    def test_往返无损(self):
        """投影与逆投影必须严格互逆：悬停查经纬、按经纬定位都靠它。"""
        for 经度, 纬度 in ((73.6, 39.5), (116.4, 39.9), (104.07, 30.57), (134.7, 48.4), (109.5, 18.3)):
            x, y = 地图.投影(经度, 纬度)
            回 = 地图.逆投影(x, y)
            self.assertAlmostEqual(回[0], 经度, places=8)
            self.assertAlmostEqual(回[1], 纬度, places=8)

    def test_中央经线不弯(self):
        """中央经线上的点必须 x=0（圆锥投影的轴线是直线）。"""
        x, _ = 地图.投影(地图.中央经线, 35.0)
        self.assertAlmostEqual(x, 0.0, places=9)
        x2, _ = 地图.投影(地图.中央经线 + 10.0, 45.0)
        self.assertNotAlmostEqual(x2, 0.0, places=3)

    def test_相对方位不乱(self):
        """投影不能把南北/东西搞反 —— 这是最容易被符号错误破坏的性质。"""
        成都 = 地图.投影(104.07, 30.57)
        襄阳 = 地图.投影(112.12, 32.00)
        广州 = 地图.投影(113.26, 23.13)
        self.assertLess(成都[0], 襄阳[0], "成都在襄阳西侧")
        self.assertLess(襄阳[1], 广州[1], "广州在襄阳南侧（y 轴向下为正）")

    def test_圆锥常数与标准纬线一致(self):
        """config/投影.json 里的圆锥常数应等于双标准纬线 25°/47° 的理论值。

        这不是"抄一个数进来"，而是独立的数学核对：拟合官方底图时算出来的也是 0.5911，
        两者吻合说明参数没被改错（见 tools/底图配准.py 的输出）。
        """
        import math
        标准 = (math.log(math.cos(math.radians(25)) / math.cos(math.radians(47)))
               / math.log(math.tan(math.radians(68.5)) / math.tan(math.radians(57.5))))
        self.assertAlmostEqual(地图.圆锥常数, 标准, places=6,
                               msg="圆锥常数与 25°/47° 双标准纬线的理论值不符")

    def test_度每像素随纬度变化且量级正确(self):
        低纬 = 地图.度每像素(20.0)
        高纬 = 地图.度每像素(50.0)
        self.assertGreater(高纬, 低纬, "高纬处 1 像素对应的度数应更大")
        self.assertTrue(0.01 < 低纬 < 0.1, f"20°N 处 1 像素 ≈ {低纬} 度，量级不对")
        # 1 度纬度 ≈ 111.32 千米，据此反推千米每像素，量级需与 project 的取图一致
        千米每像素 = 111.32 * 地图.度每像素(35.0)
        self.assertTrue(1.0 < 千米每像素 < 10.0, f"比例尺 {千米每像素:.2f} 千米/像素 不像整幅中国图的量级")

    def test_参数文件缺失时退到默认值而不是崩(self):
        """配置文件被删/改坏时，地图整体消失是最糟的结果 —— 必须退到内置默认并给出说明。"""
        参数, 问题 = 地图.载入投影参数(os.path.join(tempfile.gettempdir(), "不存在的投影参数.json"))
        self.assertEqual(参数["中央经线"], 地图.默认投影参数["中央经线"])
        self.assertTrue(问题, "退化时必须给出说明（不能悄悄用默认值）")

    def test_参数文件里的非法值会被挡下(self):
        路径 = os.path.join(tempfile.mkdtemp(prefix="投影_"), "投影.json")
        with open(路径, "w", encoding="utf-8") as 文件:
            json.dump({"中央经线": "东经一百零五度", "圆锥常数": 3.0, "缩放": -5,
                      "参考纬度": 36.0}, 文件, ensure_ascii=False)
        参数, 问题 = 地图.载入投影参数(路径)
        self.assertEqual(参数["中央经线"], 地图.默认投影参数["中央经线"])
        self.assertEqual(参数["圆锥常数"], 地图.默认投影参数["圆锥常数"], "圆锥常数超出 (0,1] 应被挡下")
        self.assertEqual(参数["缩放"], 地图.默认投影参数["缩放"], "负缩放应被挡下")
        self.assertGreaterEqual(len(问题), 3, f"三处非法值都该有说明，实际：{问题}")

    def test_投影说明可读(self):
        说明 = 地图.投影说明()
        self.assertIn("圆锥", 说明)
        self.assertIn("中央经线", 说明)


if __name__ == "__main__":
    unittest.main(verbosity=2)
