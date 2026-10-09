# -*- coding: utf-8 -*-
"""官方底图图层的用例（ui/底图.py + ui/地图.py 的 _铺底图）。

底图最容易出的错不是"崩"，而是"**看起来对、其实错位**"：整幅图偏了几百像素，
粗看仍然是一张中国地图。所以这里不只测"有没有画出来"，而是把它**钉在像素几何上**：
  1. 配准必须是轴对齐的（b=d=0）—— 否则 tkinter 根本画不了旋转位图
  2. 吸附档位必须精确等于 m/n，且吸附后是"不动点"（再吸附一次不再变）
  3. 底图关闭时画布上不能有任何 image 元素，缩放也不能被改动（行为与以前完全一致）
  4. 底图打开时，画出来的图块的四角必须与该图块覆盖的经纬范围**换算到屏幕后重合**
     （这是"底图与州郡界对齐"的可计算版本）
  5. 图片缺失或配准缺失时要优雅退化，不许抛异常
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import 夹具  # noqa: E402

sys.path.insert(0, os.path.join(夹具.仓库根目录, "ui"))
import 地图  # noqa: E402
import 底图  # noqa: E402


def 有图形环境():
    try:
        import tkinter
        探针 = tkinter.Tk()
        探针.destroy()
        return True
    except Exception:                                       # noqa: BLE001
        return False


class 配准数据(unittest.TestCase):

    def setUp(self):
        self.数据, self.问题 = 底图.载入配准()
        if self.数据 is None:
            self.skipTest("还没有 config/底图配准.json（先跑 tools/底图配准.py）")

    def test_配准是轴对齐的(self):
        """b、d 是旋转/错切分量：只要不是 0，tkinter 就画不准，必须拒画而不是硬画。"""
        a, b, c, d, e, f = self.数据["像素到世界"]["系数"]
        self.assertAlmostEqual(b, 0.0, places=9, msg="配准含旋转（b≠0），tkinter 画不了")
        self.assertAlmostEqual(d, 0.0, places=9, msg="配准含错切（d≠0），tkinter 画不了")
        self.assertAlmostEqual(abs(a), abs(e), places=9, msg="横纵缩放必须一致")

    def test_图像宽高与配准一致(self):
        """换图不重跑配准，这里的尺寸就会对不上 —— 必须判红，不许悄悄按错的尺寸画。"""
        if not 有图形环境():
            self.skipTest("当前环境无图形界面，读不了 PNG")
        import tkinter
        根 = tkinter.Tk()                      # PhotoImage 需要一个活着的根窗口
        try:
            图层 = 底图.底图图层(self.数据)
            self.assertTrue(图层.可用(), f"底图图片没找到：{图层.图像路径}")
            源 = 图层.取源图()
            self.assertIsNotNone(源, f"底图读不出来：{图层.错误}")
            self.assertEqual((源.width(), 源.height()), (图层.图像宽, 图层.图像高),
                             "底图实际尺寸与配准文件不符（换过图就必须重跑 tools/底图配准.py）")
        finally:
            根.destroy()

    def test_像素世界往返一致(self):
        图层 = 底图.底图图层(self.数据)
        for u, v in ((0, 0), (2100, 1481), (4199, 2962)):
            x, y = 图层.像素到世界(u, v)
            回 = 图层.世界到像素(x, y)
            self.assertAlmostEqual(回[0], u, places=6)
            self.assertAlmostEqual(回[1], v, places=6)

    def test_带旋转的配准会被拒绝(self):
        """往系数里塞一个旋转，载入必须直接失败并给出原因（不能悄悄画歪图）。"""
        假 = {"像素到世界": {"系数": [0.3, 0.02, 0.0, -0.02, 0.3, 0.0]}, "图像宽高": [100, 100]}
        路径 = os.path.join(夹具.仓库根目录, "config", "_临时假配准.json")
        import json
        with open(路径, "w", encoding="utf-8") as 文件:
            json.dump(假, 文件, ensure_ascii=False)
        try:
            数据, 问题 = 底图.载入配准(路径)
            self.assertIsNone(数据, "带旋转的配准不应被接受")
            self.assertTrue(any("旋转" in 说明 or "错切" in 说明 for 说明 in 问题),
                            f"应说明原因，实际：{问题}")
        finally:
            os.remove(路径)


class 缩放档位(unittest.TestCase):

    def setUp(self):
        self.数据, _ = 底图.载入配准()
        if self.数据 is None:
            self.skipTest("还没有底图配准文件")
        self.图层 = 底图.底图图层(self.数据)

    def test_吸附倍率精确等于m比n(self):
        for 目标 in (0.05, 0.2, 0.29, 0.5, 0.9, 1.0, 1.7, 3.3, 7.9):
            m, n, 倍率 = self.图层.吸附档位(目标)
            self.assertAlmostEqual(倍率, m / n, places=12,
                                   msg=f"目标 {目标} 吸附到 {m}/{n} 但倍率不是 m/n")
            self.assertLess(abs(倍率 / min(max(目标, 底图.最小倍率), 底图.最大倍率) - 1), 0.06,
                            f"目标 {目标} 吸附到 {倍率:.4f} 偏差过大")

    def test_吸附后是不动点(self):
        """吸附过的倍率再吸附一次必须不变 —— 否则每帧都会微调缩放，画面会呼吸。"""
        for 目标 in (0.13, 0.42, 1.05, 2.7):
            m, n, 倍率 = self.图层.吸附档位(目标)
            m2, n2, 倍率2 = self.图层.吸附档位(倍率)
            self.assertAlmostEqual(倍率2, 倍率, places=12, msg=f"{倍率} 不是吸附不动点")


class 画布集成(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        if not 有图形环境():
            raise unittest.SkipTest("当前环境无图形界面")

    def setUp(self):
        import tkinter
        self.根 = tkinter.Tk()
        self.根.geometry("900x600")
        数据, 错误 = 地图.载入地图数据()
        self.assertIsNotNone(数据, f"地图数据应可载入：{错误}")
        self.画布 = 地图.地图画布(self.根, 数据)
        self.画布.pack(fill="both", expand=True)
        self.根.update()

    def tearDown(self):
        self.根.destroy()

    def test_默认关闭且不改变原有行为(self):
        """硬要求：底图关闭时，画布上不能有 image 元素，缩放也不能被吸附改动。"""
        self.画布.适应全图()
        self.根.update()
        原缩放 = self.画布.缩放
        self.assertFalse(self.画布.显示底图, "底图应默认关闭")
        self.assertEqual([项 for 项 in self.画布.find_all()
                          if self.画布.type(项) == "image"], [],
                         "底图关闭时不应有任何 image 元素")
        self.画布.重绘()
        self.assertEqual(self.画布.缩放, 原缩放, "底图关闭时重绘不得改动缩放")
        self.assertIn("关闭", self.画布.底图状态())

    def test_打开后画出底图并对齐(self):
        self.画布.适应全图()
        self.根.update()
        self.画布.设显示底图(True)
        self.根.update()
        项们 = [项 for 项 in self.画布.find_all() if self.画布.type(项) == "image"]
        self.assertEqual(len(项们), 1, f"应恰好有一张底图，实际 {len(项们)}")
        if not self.画布.底图层.可用():
            self.skipTest("底图图片缺失，跳过几何校验")
        图层 = self.画布.底图层
        倍率 = 图层.世界每像素() * self.画布.缩放
        m, n, 精确 = 图层.吸附档位(倍率)
        self.assertAlmostEqual(精确, 倍率, places=9,
                               msg="打开底图后缩放必须正好落在 m/n 档位上（否则会系统性错位）")
        # ① 图块锚点必须落在"裁块原点那个像素"换算到屏幕的位置上
        #    （这是"底图与州郡界对齐"的可计算版本：把坐标换算链走通一遍）
        图 = self.画布._底图图
        锚 = self.画布.coords(项们[0])
        应锚 = self.画布.世界到屏幕(*图层.像素到世界(*self.画布._底图裁原点))
        self.assertLess(abs(锚[0] - 应锚[0]), 1.0, f"底图锚点横向错位：{锚[0]} vs {应锚[0]:.2f}")
        self.assertLess(abs(锚[1] - 应锚[1]), 1.0, f"底图锚点纵向错位：{锚[1]} vs {应锚[1]:.2f}")
        # ② 图块覆盖的图像像素数 × 倍率，必须正好等于它画出来的画布宽度
        #    （倍率是 m/n，所以这里应当零误差；有一点点都说明缩放档位没对齐）
        画出宽 = 图.width() * m
        应画宽 = 图.width() * n * 精确
        self.assertLess(abs(画出宽 - 应画宽), 0.001,
                        f"图块宽度与倍率不符：画出 {画出宽}，按倍率应是 {应画宽:.3f}")
        # ③ bbox 左上角与锚点一致（anchor='nw'）；右边/下边会被画布裁掉，不作为判据
        框 = self.画布.bbox(项们[0])
        self.assertLess(abs(框[0] - 应锚[0]), 2, f"左上角横向错位：{框[0]} vs {应锚[0]:.1f}")
        self.assertLess(abs(框[1] - 应锚[1]), 2, f"左上角纵向错位：{框[1]} vs {应锚[1]:.1f}")

    def test_底图在最下层(self):
        self.画布.设显示底图(True)
        self.根.update()
        全部 = self.画布.find_all()
        self.assertEqual(self.画布.type(全部[0]), "image", "底图必须是画布上的第一个（最下层）元素")
        if self.画布._底图项 is not None:
            self.assertEqual(全部[0], self.画布._底图项)

    def test_关掉之后回到原样(self):
        self.画布.适应全图()
        self.根.update()
        self.画布.设显示底图(True)
        self.根.update()
        self.画布.设显示底图(False)
        self.根.update()
        self.assertEqual([项 for 项 in self.画布.find_all()
                          if self.画布.type(项) == "image"], [], "关掉后不该留下 image 元素")
        self.assertIsNone(self.画布._底图项)

    def test_图片缺失时优雅退化(self):
        假数据 = dict(self.画布.数据 and {})
        配准, 问题 = 底图.载入配准()
        if 配准 is None:
            self.skipTest("没有配准文件")
        self.画布.底图层 = 底图.底图图层(配准, 图像路径=os.path.join(夹具.仓库根目录, "不存在的图.png"))
        self.assertFalse(self.画布.底图层.可用())
        self.画布.显示底图 = True
        self.画布.重绘()                      # 不许抛异常
        self.根.update()
        self.assertTrue(any("不存在" in 说明 for 说明 in self.画布.底图问题),
                        f"应记下缺图说明，实际：{self.画布.底图问题}")


if __name__ == "__main__":
    unittest.main(verbosity=2)
