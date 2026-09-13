# -*- coding: utf-8 -*-
"""规则测试：验证核心判定与结算的规则语义（不含边界相等与异常路径，见 test_boundaries）。"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import 夹具


class 规则测试(unittest.TestCase):
    """每次用例都用全新游戏状态，避免相互影响。"""

    def setUp(self):
        self.游戏 = 夹具.载入游戏()
        self.配置 = self.游戏.配置

    # —— 军事判定 ——

    def test_强攻判定_兵力明显高于守军时必胜且损失按守军系数(self):
        必胜, 损失, 说明 = self.游戏.计算强攻判定(12000, 6000)
        self.assertTrue(必胜)
        self.assertEqual(损失, int(6000 * self.配置["战斗"]["强攻"]["损失系数"]))
        self.assertIn("强攻必胜", 说明)

    def test_强攻判定_兵力不足时给出所需阈值(self):
        必胜, 损失, 说明 = self.游戏.计算强攻判定(6000, 6000)
        self.assertFalse(必胜)
        self.assertEqual(损失, 0)
        self.assertIn("无必胜把握", 说明)

    def test_围攻判定_兵力高于守军八成时可围攻(self):
        可围, 说明 = self.游戏.计算围攻判定(6000, 6000)
        self.assertTrue(可围)
        self.assertIn("围攻可行", 说明)

    def test_必败判定_兵力低于守军五成时判必败并提示死士突袭(self):
        必败, 说明 = self.游戏.计算必败判定(2000, 6000)
        self.assertTrue(必败)
        self.assertIn("死士突袭", 说明)

    def test_攻城结算_守值随防御加成提高(self):
        无将守值 = self.游戏.攻城结算(10000, 5000, None)[1]
        关将 = self.游戏.按姓名查找("关羽")
        有将守值 = self.游戏.攻城结算(10000, 5000, 关将)[1]
        self.assertEqual(无将守值, 5000)
        self.assertGreater(有将守值, 无将守值)

    # —— 将领与任务 ——

    def test_防御加成_驻守险关高于镇守城池(self):
        关羽 = self.游戏.按姓名查找("关羽")      # 镇守城池，统御9
        张飞 = self.游戏.按姓名查找("张飞")      # 驻守险关，统御8
        加成系数 = self.配置["战斗"]["防御加成"]
        self.assertAlmostEqual(self.游戏.防御加成计算(关羽), 9 * 加成系数["镇守城池系数"])
        self.assertAlmostEqual(self.游戏.防御加成计算(张飞), 8 * 加成系数["驻守险关系数"])
        self.assertGreater(self.游戏.防御加成计算(张飞), self.游戏.防御加成计算(关羽))

    def test_城破伤亡判定_提前撤退必定存活(self):
        将领 = dict(self.游戏.按姓名查找("关羽"))
        说明 = self.游戏.城破伤亡判定(将领, "提前撤退")
        self.assertEqual(将领["状态"], "正常")
        self.assertIn("提前撤退", 说明)

    def test_城破伤亡判定_死守按统御分档(self):
        高统御 = dict(self.游戏.按姓名查找("关羽"))    # 统御9
        低统御 = dict(self.游戏.按姓名查找("魏延"))    # 统御7
        self.游戏.城破伤亡判定(高统御, "死守")
        self.游戏.城破伤亡判定(低统御, "死守")
        self.assertEqual(高统御["状态"], "重伤")
        self.assertEqual(低统御["状态"], "已殁")

    def test_城破伤亡判定_未指定指令被俘(self):
        将领 = dict(self.游戏.按姓名查找("赵云"))
        self.游戏.城破伤亡判定(将领, "默认驻守")
        self.assertEqual(将领["状态"], "被俘")

    def test_任务结算_屯田按内政与民心产粮(self):
        粮草前 = self.游戏.蜀汉["粮草"]
        兵力前 = self.游戏.蜀汉["兵力"]
        self.游戏.结算回合()
        诸葛亮 = self.游戏.按姓名查找("诸葛亮")
        预期屯田 = int(诸葛亮["内政"] * 2 * 100 / 100)
        消耗 = max(1, 兵力前 // 1000 // 2)           # 张飞驻守险关 → 消耗减半
        self.assertEqual(self.游戏.蜀汉["粮草"], 粮草前 - 消耗 + 预期屯田)

    def test_有效兵力_随精锐比例线性提升(self):
        基准 = self.游戏.有效兵力计算()
        精锐 = self.配置["兵种"]["精锐"]
        self.游戏.蜀汉["精锐比例"] = 50
        预期 = int(self.游戏.蜀汉["兵力"] * (精锐["有效兵力系数基准"] + 50 / 精锐["有效兵力系数分母"]))
        self.assertEqual(self.游戏.有效兵力计算(), 预期)
        self.assertGreater(self.游戏.有效兵力计算(), 基准)

    # —— 计谋（前置条件制） ——

    def test_计谋_侦查后劫粮道成功并按配置削减曹魏(self):
        曹魏兵力前 = self.游戏.曹魏["兵力"]
        成功, _ = 夹具.捕获输出(self.游戏.计谋_侦查粮道)
        self.assertTrue(成功)
        成功, 说明 = self.游戏.计谋_劫粮道()
        self.assertTrue(成功)
        参数 = self.配置["计谋"]["劫粮道"]
        self.assertEqual(self.游戏.曹魏["兵力"], int(曹魏兵力前 * 参数["曹魏兵力系数"]))
        self.assertIn("劫粮道成功", 说明)

    def test_计谋_侦查后火攻成功并按配置削减曹魏(self):
        夹具.捕获输出(self.游戏.计谋_侦查风向)
        成功, _ = self.游戏.计谋_火攻()
        self.assertTrue(成功)
        self.assertLess(self.游戏.曹魏["兵力"], 80000)

    def test_计谋_据险而守要求险关与驻守任务(self):
        失败说明 = self.游戏.计谋_据险而守(self.游戏.按姓名查找("诸葛亮"))[1]
        self.assertIn("前置条件不满足", 失败说明)
        成功, _ = self.游戏.计谋_据险而守(self.游戏.按姓名查找("张飞"))
        self.assertTrue(成功)

    def test_计谋_劝降按忠诚与智谋判定(self):
        宛城守将 = self.游戏.敌方城池["宛城"]["守将"]
        关羽 = self.游戏.按姓名查找("关羽")        # 智谋6，不满足
        诸葛亮 = self.游戏.按姓名查找("诸葛亮")    # 智谋10，满足
        self.assertFalse(self.游戏.计谋_劝降("宛城", 宛城守将, 关羽)[0])
        成功, 说明 = self.游戏.计谋_劝降("宛城", 宛城守将, 诸葛亮)
        self.assertTrue(成功)
        self.assertEqual(self.游戏.敌方城池["宛城"]["归属"], "蜀汉")
        self.assertIn("侯音", 说明)

    # —— 东吴均势外交 ——

    def test_东吴AI_蜀汉势强转亲魏(self):
        self.游戏.蜀汉["兵力"] = 300000
        夹具.捕获输出(self.游戏.结算回合)
        self.assertEqual(self.游戏.全局["东吴外交倾向"], "亲魏")
        亲魏 = self.配置["外交"]["亲魏"]
        self.assertEqual(self.游戏.东吴["观望态度"], 50 + 亲魏["观望调整"])

    def test_东吴AI_曹魏势强转亲蜀(self):
        夹具.捕获输出(self.游戏.结算回合)
        self.assertEqual(self.游戏.全局["东吴外交倾向"], "亲蜀")

    def test_东吴AI_势均力敌转观望(self):
        self.游戏.蜀汉["兵力"] = 80000
        夹具.捕获输出(self.游戏.结算回合)
        self.assertEqual(self.游戏.全局["东吴外交倾向"], "观望")

    # —— 势力值与城池统计 ——

    def test_势力值_按兵力城池与统御加权(self):
        权重 = self.配置["外交"]["势力值"]
        总统御 = sum(将["统御"] for 将 in self.游戏.将领们)
        self.assertEqual(self.游戏.计算势力值("蜀汉"),
                         18000 + self.游戏.蜀汉控制城池数() * 权重["城池权重"] + 总统御 * 权重["统御权重"])

    def test_城池统计_攻占后蜀汉城池数增加(self):
        前 = self.游戏.蜀汉控制城池数()
        夹具.脚本输入(self.游戏, ["A"])      # 攻占后弹出"割地/拒绝"抉择，脚本选 A
        夹具.捕获输出(self.游戏.攻占城池, "上庸", self.游戏.按姓名查找("魏延"), 0.8, "强攻")
        self.assertEqual(self.游戏.蜀汉控制城池数(), 前 + 1)

    # —— 月份与季节 ——

    def test_月份推进_跨年进位并更新季节(self):
        起始日期 = self.游戏.显示日期()
        self.assertEqual(起始日期, "建安十三年九月")
        for _ in range(3):
            self.游戏.推进日期()
        self.assertEqual(self.游戏.显示日期(), "建安十三年十二月")
        self.assertEqual(self.游戏.季节, "冬季")
        self.游戏.推进日期()
        self.assertEqual(self.游戏.显示日期(), "建安十四年一月")

    def test_记录_带建安年月前缀(self):
        self.游戏.记录("测试事件")
        self.assertTrue(self.游戏.全局["事件日志"][-1].startswith("【建安十三年九月】"))

    # —— 显示与态势图 ——

    def test_态势图_渲染归属与要点标记(self):
        _, 输出 = 夹具.捕获输出(self.游戏.绘制战区态势图)
        for 关键字 in ("【战区态势图】", "★洛阳★", "【蜀】永安◆", "【魏】襄阳", "图例"):
            self.assertIn(关键字, 输出)


if __name__ == "__main__":
    unittest.main(verbosity=2)
