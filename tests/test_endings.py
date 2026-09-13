# -*- coding: utf-8 -*-
"""结局测试：四条结局路径与其优先级（含一次 20 回合集成对局）。"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import 夹具


class 结局测试(unittest.TestCase):

    def setUp(self):
        self.游戏 = 夹具.载入游戏()

    def test_结局_洛阳归蜀即北伐大捷(self):
        夹具.脚本输入(self.游戏, ["A"])
        夹具.捕获输出(self.游戏.攻占城池, "洛阳", self.游戏.按姓名查找("魏延"), 0.8, "强攻")
        self.assertEqual(self.游戏.敌方城池["洛阳"]["归属"], "蜀汉")
        self.assertIn("北伐大捷", self.游戏.结局判定())

    def test_结局_北伐大捷优先级最高(self):
        # 洛阳分支在结局判定中最先检查：即使兵力归零/压力爆表也判北伐大捷
        夹具.脚本输入(self.游戏, ["A"])
        夹具.捕获输出(self.游戏.攻占城池, "洛阳", self.游戏.按姓名查找("魏延"), 0.8, "强攻")
        self.游戏.蜀汉["兵力"] = 0
        self.游戏.蜀汉["魏国压力"] = 999
        self.assertIn("北伐大捷", self.游戏.结局判定())

    def test_结局_兵力归零为星落秋风(self):
        self.游戏.回合计数 = 3
        self.游戏.蜀汉["兵力"] = 0
        self.assertEqual(self.游戏.结局判定(), "【结局】星落秋风，蜀汉重蹈覆辙")

    def test_结局_压力超百为星落秋风(self):
        self.游戏.回合计数 = 3
        self.游戏.蜀汉["魏国压力"] = 101
        self.assertEqual(self.游戏.结局判定(), "【结局】星落秋风，蜀汉重蹈覆辙")

    def test_结局_满20回合且兵力超初始为好结局(self):
        self.游戏.回合计数 = 20
        self.游戏.蜀汉["兵力"] = self.游戏.初始兵力 + 1
        self.assertIn("汉家尚有可为", self.游戏.结局判定())

    def test_结局_满20回合兵力未超初始为中性结局(self):
        self.游戏.回合计数 = 20
        self.游戏.蜀汉["兵力"] = self.游戏.初始兵力
        self.assertIn("兵力未复旧观", self.游戏.结局判定())

    def test_结局_未到20回合且未触发硬条件时无结局(self):
        self.游戏.回合计数 = 10
        self.assertIsNone(self.游戏.结局判定())

    def test_结局_整局集成_自动演示跑满20回合并输出结局与将领结算(self):
        """集成用例：无人值守跑完 20 回合（含 0.5 秒暂停，耗时约 10 秒）。"""
        输出 = 夹具.运行对局(self.游戏, ["2"])
        self.assertIn("【结局】", 输出)
        self.assertIn("【将领结局】", 输出)
        self.assertIn("战区态势图", 输出)
        self.assertIn("建安十四年", 输出)      # 跨年推进确实发生


if __name__ == "__main__":
    unittest.main(verbosity=2)
