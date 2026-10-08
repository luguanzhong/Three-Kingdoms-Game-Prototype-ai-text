# -*- coding: utf-8 -*-
"""游戏内图形地图（ui/地图.py）的回归用例。

分两类：
  【数据】不需要图形环境：地图数据文件的合法性、十个城池的齐备性、异常数据的处理；
  【渲染】需要图形环境（无显示时自动跳过）：投影与缩放、点击命中、标签不重叠、归属配色、围攻高亮。
"""
import importlib.util
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import 夹具  # noqa: E402

sys.path.insert(0, 夹具.源码目录)
sys.path.insert(0, os.path.join(夹具.仓库根目录, "ui"))
import 地图  # noqa: E402

游戏城池 = {"成都", "江陵", "阆中", "汉中", "永安", "襄阳", "樊城", "宛城", "上庸", "洛阳"}


class 地图数据(unittest.TestCase):

    def test_数据文件合法且无校验错误(self):
        数据, 错误 = 地图.载入地图数据()
        self.assertIsNotNone(数据, "地图数据应当可以载入")
        self.assertEqual(错误, [], "地图数据不应有校验错误")

    def test_十三州与十城池齐备(self):
        数据, _ = 地图.载入地图数据()
        self.assertEqual(len(数据["州"]), 13, "应为十三州（不含交州）")
        self.assertEqual({城["名"] for 城 in 数据["城池"]}, 游戏城池,
                         "地图城池必须与引擎里的十座城池完全一致")
        for 州 in 数据["州"]:
            self.assertGreaterEqual(len(州["边界"]), 3, f"州「{州['名']}」边界点太少")

    def test_城池来源与类型合法(self):
        数据, _ = 地图.载入地图数据()
        for 城 in 数据["城池"]:
            self.assertIn(城["来源"], ("敌方城池", "蜀汉城池", "将领驻地"))
            self.assertIn(城["归属"], ("蜀汉", "曹魏"))
            self.assertIn("类型", 城)
        self.assertEqual(len({城["名"] for 城 in 数据["城池"] if 城["来源"] == "敌方城池"}), 5)
        self.assertEqual(len({城["名"] for 城 in 数据["城池"] if 城["归属"] == "蜀汉"}), 5)
        self.assertEqual(len({城["名"] for 城 in 数据["城池"] if 城["归属"] == "曹魏"}), 5)

    def test_城池坐标落在州界经纬度范围内(self):
        """十座城必须落在整幅图的范围内，否则缩放到全图时会跑出画面。"""
        数据, _ = 地图.载入地图数据()
        点们 = 数据["底图"]["中国轮廓"]
        经度们 = [点[0] for 点 in 点们]
        纬度们 = [点[1] for 点 in 点们]
        for 城 in 数据["城池"]:
            self.assertTrue(min(经度们) <= 城["经度"] <= max(经度们),
                            f"{城['名']} 经度超出底图范围")
            self.assertTrue(min(纬度们) <= 城["纬度"] <= max(纬度们),
                            f"{城['名']} 纬度超出底图范围")

    def test_文件缺失不抛异常只报错(self):
        数据, 错误 = 地图.载入地图数据(os.path.join(tempfile.gettempdir(), "不存在的图.json"))
        self.assertIsNone(数据)
        self.assertTrue(错误)
        self.assertIn("不存在", 错误[0])

    def test_非法坐标被检出(self):
        坏数据 = {"底图": {"中国轮廓": [[100, 30], [110, 30], [110, 40]]}, "州": [],
                "城池": [{"名": "错城", "经度": "东经一百度", "纬度": 30, "来源": "敌方城池"}]}
        路径 = os.path.join(tempfile.mkdtemp(prefix="蜀汉地图_"), "map.json")
        with open(路径, "w", encoding="utf-8") as 文件:
            json.dump(坏数据, 文件, ensure_ascii=False)
        数据, 错误 = 地图.载入地图数据(路径)
        self.assertTrue(any("经纬度非法" in 项 for 项 in 错误), f"应检出坐标非法：{错误}")

    def test_投影与对照图一致(self):
        """同一套投影：襄阳与成都的相对位置必须"成都偏西、襄阳偏东"。"""
        襄阳 = 地图.投影(112.12, 32.00)
        成都 = 地图.投影(104.07, 30.57)
        self.assertLess(成都[0], 襄阳[0], "成都在西侧")
        self.assertGreater(成都[1], 襄阳[1], "成都在南侧（y 轴向下）")


class 地图渲染(unittest.TestCase):

    def setUp(self):
        try:
            import tkinter
            探针 = tkinter.Tk()
            探针.destroy()
        except Exception as 异常:
            self.skipTest(f"当前环境无图形界面，跳过渲染用例：{异常!r}")
        import tkinter
        import 游戏接口
        self.根 = tkinter.Tk()
        self.根.geometry("1000x640")
        self.数据, _ = 地图.载入地图数据()
        self.局 = 游戏接口.会话()
        self.局.新开局(输出回调=lambda 文本: None, 询问回调=lambda 提示: "0")
        self.局面 = self.局.局面()
        self.画布 = 地图.地图画布(self.根, self.数据)
        self.画布.pack(fill="both", expand=True)
        self.根.update()
        self.画布.重绘(self.局面)
        self.根.update()

    def tearDown(self):
        if getattr(self, "根", None) is not None:
            self.根.destroy()

    # ── 视图 ──
    def test_适应全图后十城都在画布内(self):
        self.画布.适应全图()
        self.根.update()
        宽, 高 = self.画布.winfo_width(), self.画布.winfo_height()
        for 城名 in 游戏城池:
            x, y = self.画布.城池屏幕位置(城名)
            self.assertTrue(0 <= x <= 宽 and 0 <= y <= 高,
                            f"{城名} 在适应全图后跑出了画布：({x:.0f}, {y:.0f})")

    def test_居中战场后十城可见且分散(self):
        self.画布.居中战场()
        self.根.update()
        self.assertEqual(sorted(self.画布.可视城池()), sorted(游戏城池),
                         "居中战场后十座城都应可见")
        襄阳 = self.画布.城池屏幕位置("襄阳")
        洛阳 = self.画布.城池屏幕位置("洛阳")
        距 = ((襄阳[0] - 洛阳[0]) ** 2 + (襄阳[1] - 洛阳[1]) ** 2) ** 0.5
        self.assertGreater(距, 80, "居中战场后襄阳与洛阳应明显分开")

    def test_缩放以给定点为锚点(self):
        锚点 = (420, 300)
        世界前 = self.画布.屏幕到世界(*锚点)
        self.画布.缩放一步(1.5, *锚点)
        世界后 = self.画布.屏幕到世界(*锚点)
        self.assertAlmostEqual(世界前[0], 世界后[0], places=6, msg="缩放后锚点世界坐标应不变")
        self.assertAlmostEqual(世界前[1], 世界后[1], places=6)

    def test_缩放有上下限(self):
        for _ in range(40):
            self.画布.缩放一步(1.5)
        self.assertLessEqual(self.画布.缩放, 地图.地图画布.最大缩放)
        for _ in range(80):
            self.画布.缩放一步(1 / 1.5)
        self.assertGreaterEqual(self.画布.缩放, 地图.地图画布.最小缩放)

    # ── 点击命中 ──
    def test_命中城池(self):
        self.画布.居中战场()
        self.根.update()
        for 城名 in 游戏城池:
            x, y = self.画布.城池屏幕位置(城名)
            self.assertEqual(self.画布.命中城池(x, y), 城名, f"点{城名}应命中{城名}")
        self.assertIsNone(self.画布.命中城池(5, 5), "空白处不应命中任何城池")

    def test_命中取最近的一座(self):
        """襄阳与樊城相距很近：点在其中一座上应命中它自己，而不是邻居。"""
        self.画布.居中战场()
        self.根.update()
        for 城名 in ("襄阳", "樊城", "宛城"):
            x, y = self.画布.城池屏幕位置(城名)
            self.assertEqual(self.画布.命中城池(x, y), 城名)

    def test_点击回调被触发(self):
        收到 = []
        self.画布.城池回调 = 收到.append
        self.画布.居中战场()
        self.根.update()
        x, y = self.画布.城池屏幕位置("江陵")

        class 假事件:
            pass
        事件 = 假事件()
        事件.x, 事件.y = int(x), int(y)
        self.画布._按下(事件)
        self.画布._松开(事件)
        self.assertEqual(收到, ["江陵"], "点击城池应回调城名")

    # ── 渲染内容 ──
    def test_标签互不重叠(self):
        """居中战场（缩放足够）时，十个数据标签必须互不压叠。"""
        self.画布.居中战场()
        self.根.update()
        self.assertGreater(self.画布.缩放, 地图.地图画布.标签缩放门槛,
                           "测试前提：居中战场后缩放应超过标签门槛")
        self.assertEqual(len(self.画布.标签矩形), 10, "十座城都应画出标签")
        框们 = list(self.画布.标签矩形.items())
        for i in range(len(框们)):
            for j in range(i + 1, len(框们)):
                名一, (a1, b1, a2, b2) = 框们[i]
                名二, (c1, d1, c2, d2) = 框们[j]
                重叠 = not (a2 < c1 or a1 > c2 or b2 < d1 or b1 > d2)
                self.assertFalse(重叠, f"标签重叠：{名一} 与 {名二}")

    def test_缩放过小时只画点位不画标签(self):
        self.画布.适应全图()
        self.根.update()
        if self.画布.缩放 >= 地图.地图画布.标签缩放门槛:
            self.skipTest("该画布尺寸下全图缩放已超过标签门槛")
        self.assertEqual(self.画布.标签矩形, {}, "缩放过小时不应画数据标签")
        圆点 = [项 for 项 in self.画布.find_all()
               if self.画布.type(项) == "oval" and 地图.配色["蜀"] in
               (self.画布.itemcget(项, "fill"), self.画布.itemcget(项, "outline"))]
        self.assertGreaterEqual(len(圆点), 5, "缩小时仍应画出城池点位")

    def test_归属配色随引擎状态(self):
        self.画布.居中战场()
        self.根.update()
        填充 = lambda 城名: self.画布.itemcget(self.画布.find_withtag(f"城_{城名}")[0], "fill")
        self.assertEqual(填充("成都"), 地图.配色["蜀"], "成都开局属蜀汉")
        self.assertEqual(填充("襄阳"), 地图.配色["魏"], "襄阳开局属曹魏")

    def test_围攻中的城池被高亮(self):
        局面 = dict(self.局面)
        局面["围攻"] = {"目标": "襄阳", "剩余": 2, "领将": "关羽", "出征兵力": 9000}
        self.画布.居中战场()
        self.画布.重绘(局面)
        self.根.update()
        文本s = [self.画布.itemcget(项, "text") for 项 in self.画布.find_all()
               if self.画布.type(项) == "text"]
        self.assertIn("围攻中", 文本s, "围攻中的城池应有高亮标记")
        圈 = [项 for 项 in self.画布.find_all()
             if self.画布.type(项) == "oval"
             and self.画布.itemcget(项, "outline") == 地图.配色["围攻"]]
        self.assertTrue(圈, "围攻中的城池应有橙色外圈")

    def test_数据缺失时画布给出提示而不崩溃(self):
        画布 = 地图.地图画布(self.根, None)
        画布.pack(fill="both", expand=True)
        self.根.update()
        画布.重绘({})
        文本s = [画布.itemcget(项, "text") for 项 in 画布.find_all()
               if 画布.type(项) == "text"]
        self.assertTrue(any("地图数据不可用" in 项 for 项 in 文本s))
        画布.destroy()


class 古今地名对照(unittest.TestCase):
    """考据数据（config/古今地名对照.json）：州郡 ↔ 现代地名，边界考证的依据来源。"""

    @classmethod
    def setUpClass(cls):
        规格 = importlib.util.spec_from_file_location(
            "古今地名对照工具", os.path.join(夹具.仓库根目录, "tools", "古今地名对照.py"))
        cls.工具 = importlib.util.module_from_spec(规格)
        规格.loader.exec_module(cls.工具)

    def test_数据校验通过(self):
        数据, 错误 = self.工具.载入()
        self.assertEqual(错误, [], "数据文件应能载入")
        错误, _提示 = self.工具.校验(数据)
        self.assertEqual(错误, [], "考据数据校验未通过：\n" + "\n".join(错误))

    def test_每条都有依据与交界带今地(self):
        """没有依据、或没写交界带今地的条目，不允许存在（否则边界就没有参照物）。"""
        数据, _ = self.工具.载入()
        for 条 in 数据["条目"]:
            self.assertTrue(条["依据"], f"{条['郡']} 没有依据")
            self.assertTrue(条["交界带今地"].strip(), f"{条['郡']} 没有交界带今地")
            self.assertIn(条["置信度"], self.工具.合法置信度)

    def test_存疑条目标注明确(self):
        """史料有争议的条目必须显式标为存疑，并写明待核事项 —— 防止被当成定论用。"""
        数据, _ = self.工具.载入()
        存疑 = [条 for 条 in 数据["条目"] if 条["置信度"] == "存疑"]
        for 条 in 存疑:
            self.assertTrue(条["待核"], f"{条['郡']} 标为存疑却没写待核事项")

    def test_覆盖战场相关区域(self):
        """首批至少覆盖战场（荆州）与益州核心，否则对本游戏没有实际用处。"""
        数据, _ = self.工具.载入()
        州们 = {条["州"] for 条 in 数据["条目"]}
        for 必需 in ("荆州", "益州"):
            self.assertIn(必需, 州们, f"首批考据应覆盖{必需}")
        郡们 = {条["郡"] for 条 in 数据["条目"]}
        for 必需 in ("南郡", "襄阳郡", "汉中郡", "巴西郡", "巴东郡"):
            self.assertIn(必需, 郡们, f"首批考据应包含{必需}（游戏内城池所在郡）")

    def test_生成的文档与数据同步(self):
        """防陈旧：改了 JSON 却没重新生成文档时，必须报错。"""
        数据, _ = self.工具.载入()
        文档 = os.path.join(夹具.仓库根目录, "docs", "古今地名对照.md")
        self.assertTrue(os.path.isfile(文档), "docs/古今地名对照.md 应已生成")
        with open(文档, encoding="utf-8") as 文件:
            正文 = 文件.read()
        self.assertIn(f"当前进度：{len(数据['条目'])} 郡", 正文,
                      "文档里的郡数与数据不一致 —— 请跑 python tools/古今地名对照.py 生成文档")

    def test_邻郡关系双向自洽性可被检查(self):
        """单边记载只作提示、不判错（史料本身常不对称），但要确保检查逻辑真的能发现它。"""
        假数据 = {"条目": [
            {"郡": "甲郡", "州": "荆州", "治所": "甲", "治所今地": "甲地",
             "今范围概述": "甲", "交界邻郡": ["乙郡"], "交界带今地": "甲乙之间",
             "置信度": "高", "依据": ["测试用"], "待核": []},
            {"郡": "乙郡", "州": "荆州", "治所": "乙", "治所今地": "乙地",
             "今范围概述": "乙", "交界邻郡": ["丙郡"], "交界带今地": "乙丙之间",
             "置信度": "中", "依据": ["测试用"], "待核": []},
        ]}
        错误, 提示 = self.工具.校验(假数据)
        self.assertEqual(错误, [], "假数据本身应合法")
        self.assertTrue(any("甲郡" in 项 and "乙郡" in 项 for 项 in 提示),
                        f"应提示甲/乙之间的单边记载，实际提示：{提示}")


class 郡属县数据(unittest.TestCase):
    """考据数据（config/郡属县.json）：郡 → 属县 → 现代参照点。边界从几何骨架升级为有依据的边界，靠的就是它。"""

    @classmethod
    def setUpClass(cls):
        路径 = os.path.join(夹具.仓库根目录, "config", "郡属县.json")
        with open(路径, encoding="utf-8") as 文件:
            cls.数据 = json.load(文件)
        cls.属县 = cls.数据["郡属县"]

    def test_六郡齐备(self):
        for 郡 in ("南郡", "襄阳郡", "南阳郡", "汉中郡", "巴西郡", "巴东郡"):
            self.assertIn(郡, self.属县, f"首批应包含{郡}")

    def test_每条字段齐备且置信度合法(self):
        for 郡, 县们 in self.属县.items():
            self.assertIsInstance(县们, list, f"{郡} 的值应是列表")
            self.assertTrue(县们, f"{郡} 不应为空")
            for 县 in 县们:
                for 字段 in ("县", "今地", "坐标", "置信度", "备注"):
                    self.assertIn(字段, 县, f"{郡}·{县.get('县')} 缺少字段 {字段}")
                self.assertIn(县["置信度"], ("高", "中", "存疑"))
                self.assertEqual(len(县["坐标"]), 2, f"{郡}·{县['县']} 坐标应为 [经度, 纬度]")

    def test_属县不得跨郡重复(self):
        """同一个县只能属于一个郡 —— 否则同一个坐标会在两郡各生成一个退化格子。"""
        见过 = {}
        重复 = []
        for 郡, 县们 in self.属县.items():
            for 县 in 县们:
                if 县["县"] in 见过:
                    重复.append(f"{县['县']}（{见过[县['县']]} 与 {郡}）")
                见过[县["县"]] = 郡
        self.assertEqual(重复, [], "属县跨郡重复：\n" + "\n".join(重复))

    def test_坐标不重复且落在中国范围内(self):
        坐标集 = {}
        越界 = []
        for 郡, 县们 in self.属县.items():
            for 县 in 县们:
                经度, 纬度 = 县["坐标"]
                if not (73 <= 经度 <= 136 and 18 <= 纬度 <= 54):
                    越界.append(f"{郡}·{县['县']} {县['坐标']}")
                键 = (round(经度, 4), round(纬度, 4))
                坐标集.setdefault(键, []).append(f"{郡}·{县['县']}")
        self.assertEqual(越界, [], "坐标越界：\n" + "\n".join(越界))
        重合 = [v for v in 坐标集.values() if len(v) > 1]
        self.assertEqual(重合, [], f"坐标完全相同的点：{重合}")

    def test_存疑条目必须写清理由(self):
        for 郡, 县们 in self.属县.items():
            for 县 in 县们:
                if 县["置信度"] == "存疑":
                    self.assertTrue(县["备注"].strip(),
                                    f"{郡}·{县['县']} 标为存疑却未写备注说明原因")

    def test_南郡与襄阳郡的划出关系有记录(self):
        """208 年分置襄阳郡时从南郡划走六县 —— 这个考据细节必须记在数据里，不能被悄悄丢掉。"""
        self.assertIn("南郡", self.数据.get("郡说明", {}), "应在顶层「郡说明」记录南郡与襄阳郡的划出关系")
        说明 = self.数据["郡说明"]["南郡"]
        for 县名 in ("襄阳", "宜城", "中卢", "临沮", "邔", "鄀"):
            self.assertIn(县名, 说明, f"南郡说明里应提到划出的{县名}")
        南郡名 = {县["县"] for 县 in self.属县["南郡"]}
        襄阳名 = {县["县"] for 县 in self.属县["襄阳郡"]}
        self.assertFalse(南郡名 & 襄阳名, "南郡与襄阳郡不应有同名属县")


class 郡界骨架数据(unittest.TestCase):
    """郡界骨架数据侧（无需图形环境）：结构、警告字段、点在多边形内。"""

    @classmethod
    def setUpClass(cls):
        cls.骨架, cls.错误 = 地图.载入郡界骨架()

    def test_骨架数据可载入且无校验错误(self):
        self.assertIsNotNone(self.骨架, f"骨架数据应可载入：{self.错误}")
        self.assertEqual(self.错误, [], "骨架数据校验未通过：\n" + "\n".join(self.错误))

    def test_必须自带非考据边界警告(self):
        """这是安全阀：骨架若被当成考据边界用，整个地图的可信度就崩了。"""
        self.assertTrue(self.骨架.get("警告"), "骨架数据必须显式声明它不是考据边界")
        警告 = self.骨架["警告"]
        self.assertIn("不是考据边界", 警告)
        self.assertIn("泰森多边形", 警告)

    def test_六郡有属县依据(self):
        有依据 = [条["郡"] for 条 in self.骨架["郡"] if len(条.get("县") or []) >= 2]
        for 郡 in ("南郡", "襄阳郡", "南阳郡", "汉中郡", "巴西郡", "巴东郡"):
            self.assertIn(郡, 有依据, f"{郡} 应有属县依据（点位数 ≥ 2）")

    def test_每郡字段齐备且引用古今对照(self):
        for 条 in self.骨架["郡"]:
            for 字段 in ("郡", "州", "格", "县", "治所", "治所今地", "整体置信度"):
                self.assertIn(字段, 条, f"骨架条目缺少字段 {字段}")
            self.assertTrue(条["格"], f"{条['郡']} 没有格子")
            self.assertTrue(条["治所今地"], f"{条['郡']} 没有治所今地名")

    def test_骨架引用的一致性(self):
        """骨架里的县与治所必须与 config/郡属县.json、config/古今地名对照.json 对得上。"""
        对照 = json.loads(夹具.读取源码("config/古今地名对照.json")) if False else None
        with open(os.path.join(夹具.仓库根目录, "config", "古今地名对照.json"),
                  encoding="utf-8") as 文件:
            对照 = json.load(文件)
        索引 = {条["郡"]: 条 for 条 in 对照["条目"]}
        for 条 in self.骨架["郡"]:
            self.assertIn(条["郡"], 索引, f"{条['郡']} 不在古今地名对照里")
            self.assertEqual(条["治所今地"], 索引[条["郡"]]["治所今地"],
                             f"{条['郡']} 的治所今地与对照表不一致（数据不同步？）")

    def test_点在多边形内_凸多边形(self):
        方 = [[0, 0], [10, 0], [10, 10], [0, 10]]
        self.assertTrue(地图.点在多边形内((5, 5), 方))
        self.assertFalse(地图.点在多边形内((15, 5), 方))
        self.assertFalse(地图.点在多边形内((5, -1), 方))

    def test_点在多边形内_凹多边形(self):
        """L 形：凹口里的点必须判为"不在内"（射线法最容易在这里写错）。"""
        凹 = [[0, 0], [10, 0], [10, 4], [4, 4], [4, 10], [0, 10]]
        self.assertTrue(地图.点在多边形内((2, 2), 凹))
        self.assertFalse(地图.点在多边形内((7, 7), 凹), "凹口内的点不应判为在内")

    def test_骨架数据缺失时只报错不崩(self):
        数据, 错误 = 地图.载入郡界骨架(os.path.join(tempfile.gettempdir(), "没有这个.json"))
        self.assertIsNone(数据)
        self.assertTrue(错误)
        self.assertIn("未找到", 错误[0])


class 郡界骨架渲染(unittest.TestCase):
    """郡界骨架在画布上的行为（需图形环境）：绘制、开关、悬停命中、提示框不越界。"""

    def setUp(self):
        try:
            import tkinter
            探针 = tkinter.Tk()
            探针.destroy()
        except Exception as 异常:
            self.skipTest(f"当前环境无图形界面：{异常!r}")
        import tkinter
        import 游戏接口
        self.根 = tkinter.Tk()
        self.根.geometry("1200x760")
        self.地图数据, _ = 地图.载入地图数据()
        self.骨架, _ = 地图.载入郡界骨架()
        self.局 = 游戏接口.会话()
        self.局.新开局(输出回调=lambda 文本: None, 询问回调=lambda 提示: "0")
        self.画布 = 地图.地图画布(self.根, self.地图数据, 骨架数据=self.骨架)
        self.画布.pack(fill="both", expand=True)
        self.根.update()
        self.画布.重绘(self.局.局面())
        self.根.update()

    def tearDown(self):
        if getattr(self, "根", None) is not None:
            self.根.destroy()

    def _与骨架有关的项(self, 标签):
        return [项 for 项 in self.画布.find_withtag(标签)]

    def test_默认绘制有依据的郡且可整体关闭(self):
        self.画布.设显示骨架(True)
        self.根.update()
        有骨架项 = self._与骨架有关的项("郡界")
        self.assertTrue(有骨架项, "默认应绘制郡界骨架")
        self.画布.设显示骨架(False)
        self.根.update()
        self.assertEqual(self._与骨架有关的项("郡界"), [], "关闭后不应再有郡界项")
        self.画布.设显示骨架(True)

    def test_默认不画仅有治所的粗骨架(self):
        self.画布.设显示粗骨架(False)
        self.根.update()
        细 = len(self._与骨架有关的项("郡界"))
        self.画布.设显示粗骨架(True)
        self.根.update()
        全部 = len(self._与骨架有关的项("郡界"))
        self.assertGreater(全部, 细, "打开粗骨架后应有更多格子被绘制")

    def test_悬停命中郡(self):
        self.画布.居中战场()
        self.根.update()
        命中数 = 0
        for 条 in self.画布.骨架郡们(False):
            治所 = next((县 for 县 in 条["县"] if 县.get("是治所")), 条["县"][0])
            x, y = self.画布.世界到屏幕(*地图.投影(*治所["坐标"]))
            命中 = self.画布.命中郡(x, y)
            self.assertIsNotNone(命中, f"{条['郡']} 治所处应命中某个郡")
            self.assertEqual(命中["郡"], 条["郡"], f"{条['郡']} 治所处命中了 {命中['郡']}")
            命中数 += 1
        self.assertGreaterEqual(命中数, 6, "至少应有 6 个郡参与命中抽检")

    def test_悬停提示带骨架字样且不越界(self):
        self.画布.居中战场()
        self.根.update()
        条 = self.画布.骨架郡们(False)[0]
        治所 = next((县 for 县 in 条["县"] if 县.get("是治所")), 条["县"][0])
        x, y = self.画布.世界到屏幕(*地图.投影(*治所["坐标"]))
        self.画布.悬停郡 = self.画布.命中郡(x, y)
        self.画布._画郡提示()
        self.根.update()
        提示项 = self._与骨架有关的项("郡提示")
        self.assertTrue(提示项, "悬停后应画出提示框")
        文本 = "".join(self.画布.itemcget(项, "text") for 项 in 提示项
                    if self.画布.type(项) == "text")
        self.assertIn("骨架", 文本, "提示框必须写明这是骨架")
        self.assertIn("非考据边界", 文本)
        self.assertIn(条["郡"], 文本)
        框 = self.画布.bbox("郡提示")
        self.assertLessEqual(框[2], self.画布.winfo_width(), "提示框不得超出画布右边界")
        self.assertLessEqual(框[3], self.画布.winfo_height(), "提示框不得超出画布下边界")

    def test_图例含骨架说明且框不越界(self):
        self.画布.适应全图()
        self.根.update()
        图例文本 = "".join(self.画布.itemcget(项, "text") for 项 in self._与骨架有关的项("图例")
                     if self.画布.type(项) == "text")
        self.assertIn("骨架", 图例文本, "图例必须说明郡界是骨架")
        框 = self.画布.bbox("图例")
        self.assertLessEqual(框[2], self.画布.winfo_width(), "图例框不得超出画布右边界")
        self.assertLessEqual(框[3], self.画布.winfo_height(), "图例框不得超出画布下边界")
        self.assertGreaterEqual(框[0], 0)
        self.assertGreaterEqual(框[1], 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
