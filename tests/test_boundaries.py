# -*- coding: utf-8 -*-
"""边界测试：阈值恰好相等、上下限、越界拒绝等高风险边界（规则本身见 test_rules）。"""
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import 夹具


class 边界测试(unittest.TestCase):

    def setUp(self):
        self.游戏 = 夹具.载入游戏()

    # —— 军事阈值：恰好相等不算越线 ——

    def test_边界_强攻_恰好等于倍率不算必胜(self):
        守军 = 6000
        阈值 = int(守军 * self.游戏.配置["战斗"]["强攻"]["兵力倍率下限"])
        self.assertFalse(self.游戏.计算强攻判定(阈值, 守军)[0])
        self.assertTrue(self.游戏.计算强攻判定(阈值 + 1, 守军)[0])

    def test_边界_围攻_恰好等于倍率不可围攻(self):
        守军 = 6000
        阈值 = int(守军 * self.游戏.配置["战斗"]["围攻"]["兵力倍率下限"])
        self.assertFalse(self.游戏.计算围攻判定(阈值, 守军)[0])
        self.assertTrue(self.游戏.计算围攻判定(阈值 + 1, 守军)[0])

    def test_边界_必败_恰好等于倍率不判必败(self):
        守军 = 6000
        阈值 = int(守军 * self.游戏.配置["战斗"]["必败"]["兵力倍率上限"])
        self.assertFalse(self.游戏.计算必败判定(阈值, 守军)[0])
        self.assertTrue(self.游戏.计算必败判定(阈值 - 1, 守军)[0])

    def test_边界_攻城结算_恰好等于破城倍率不算城破(self):
        守军, 进攻 = 5000, 0
        倍率 = self.游戏.配置["战斗"]["攻破城池"]["兵力倍率下限"]
        守值 = self.游戏.攻城结算(1, 守军, None)[1]
        进攻 = int(守值 * 倍率)
        self.assertFalse(self.游戏.攻城结算(进攻, 守军, None)[0])
        self.assertTrue(self.游戏.攻城结算(进攻 + 1, 守军, None)[0])

    # —— 精锐与资源上下限 ——

    def test_边界_精锐比例封顶到上限(self):
        上限 = self.游戏.配置["兵种"]["精锐"]["比例上限"]
        self.游戏.蜀汉["精锐比例"] = 上限
        self.游戏.按姓名查找("关羽")["任务"] = "镇守城池"
        self.游戏.按姓名查找("关羽")["子任务"] = "练兵"
        夹具.捕获输出(self.游戏.结算回合)
        self.assertEqual(self.游戏.蜀汉["精锐比例"], 上限)

    def test_边界_粮草为零时不出现负数(self):
        self.游戏.蜀汉["粮草"] = 0
        夹具.捕获输出(self.游戏.结算回合)
        self.assertGreaterEqual(self.游戏.蜀汉["粮草"], 0)

    def test_边界_民心与好感不超过上限(self):
        self.游戏.蜀汉["民心"] = 100
        self.游戏.蜀汉["东吴好感"] = 100
        夹具.脚本输入(self.游戏, ["2"])      # 好感>70 会弹出东吴结盟抉择，脚本选"婉拒"
        夹具.捕获输出(self.游戏.结算回合)
        self.assertLessEqual(self.游戏.蜀汉["民心"], 100)
        self.assertLessEqual(self.游戏.蜀汉["东吴好感"], 100)

    # —— 冬季惩罚两档 ——

    def test_边界_冬季在外全额惩罚(self):
        档位 = self.游戏.配置["季节"]["冬季惩罚"]["有进攻"]
        self.游戏.当前月份, self.游戏.季节 = 12, "冬季"
        夹具.捕获输出(self.游戏.结算回合)
        兵力 = 18000
        预期 = int(兵力 * (1 - 档位["冻伤比例"]))
        self.assertEqual(self.游戏.蜀汉["兵力"], 预期)

    def test_边界_冬季退守惩罚减半(self):
        档位 = self.游戏.配置["季节"]["冬季惩罚"]["退守"]
        self.游戏.当前月份, self.游戏.季节 = 12, "冬季"
        self.游戏.按姓名查找("魏延")["任务"] = "驻守险关"      # 无北伐先锋、无围攻 → 退守
        夹具.捕获输出(self.游戏.结算回合)
        预期 = int(18000 * (1 - 档位["冻伤比例"]))
        self.assertEqual(self.游戏.蜀汉["兵力"], 预期)
        self.assertGreater(self.游戏.蜀汉["兵力"], int(18000 * (1 - 0.02)))

    # —— 结局阈值 ——

    def test_边界_压力恰好100不灭国_101灭国(self):
        self.游戏.回合计数 = 5
        self.游戏.蜀汉["魏国压力"] = 100
        self.assertIsNone(self.游戏.结局判定())
        self.游戏.蜀汉["魏国压力"] = 101
        self.assertIn("星落秋风", self.游戏.结局判定())

    def test_边界_兵力恰好为0触发灭国(self):
        self.游戏.回合计数 = 5
        self.游戏.蜀汉["兵力"] = 0
        self.assertIn("星落秋风", self.游戏.结局判定())

    def test_边界_满20回合按兵力是否超过初始值区分结局(self):
        self.游戏.回合计数 = 20
        self.游戏.蜀汉["兵力"] = self.游戏.初始兵力 + 1
        self.assertIn("汉家尚有可为", self.游戏.结局判定())
        self.游戏.蜀汉["兵力"] = self.游戏.初始兵力
        self.assertIn("中性", self.游戏.结局判定())

    def test_边界_洛阳未打通粮道时不可攻(self):
        self.assertFalse(self.游戏.洛阳可攻判定())
        可选 = [城 for 城 in self.游戏.敌方城池 if self.游戏.敌方城池[城]["归属"] == "曹魏"]
        self.assertIn("洛阳", 可选)
        self.游戏.敌方城池["樊城"]["归属"] = "蜀汉"
        self.assertTrue(self.游戏.洛阳可攻判定())

    # —— 配置边界 ——

    def _造配置(self, 文件名, 路径段, 新值):
        加载器 = 夹具.载入配置模块()
        目标 = tempfile.mkdtemp(dir=夹具.临时目录())
        根 = os.path.join(夹具.仓库根目录, "config")
        import shutil
        shutil.copytree(根, os.path.join(目标, "config"))
        路径 = os.path.join(目标, "config", 文件名)
        with open(路径, encoding="utf-8") as 文件:
            内容 = json.load(文件)
        指针 = 内容
        for 段 in 路径段[:-1]:
            指针 = 指针[段]
        指针[路径段[-1]] = 新值
        with open(路径, "w", encoding="utf-8") as 文件:
            json.dump(内容, 文件, ensure_ascii=False, indent=2)
        return os.path.join(目标, "config")

    def _取错误(self, 配置目录):
        try:
            夹具.载入配置模块().载入配置(配置目录=配置目录, 严格=True)
            return ""
        except Exception as 异常:
            return str(异常)

    def test_边界_配置数值下限与上限都合法(self):
        # 用无交叉约束的字段验证范围端点（比例上限另有"练兵加成≤上限"的一致性约束）
        self.assertEqual(self._取错误(self._造配置("units.json", ["募兵", "兵力增加"], 1)), "")
        self.assertEqual(self._取错误(self._造配置("units.json", ["募兵", "兵力增加"], 100000)), "")

    def test_边界_配置数值越界被拒绝(self):
        self.assertIn("超出范围", self._取错误(self._造配置("units.json", ["精锐", "比例上限"], 0)))
        self.assertIn("超出范围", self._取错误(self._造配置("units.json", ["精锐", "比例上限"], 101)))

    def test_边界_配置布尔值不被当作整数接受(self):
        self.assertIn("期望", self._取错误(self._造配置("units.json", ["募兵", "兵力增加"], True)))

    def test_边界_配置季节月份少一个月被拒绝(self):
        self.assertIn("未被任何季节覆盖",
                      self._取错误(self._造配置("seasons.json", ["季节月份", "夏季"], [6, 7])))

    def test_边界_配置战斗倍率零与二合法_超出非法(self):
        self.assertEqual(self._取错误(self._造配置("battle.json", ["强攻", "损失系数"], 0)), "")
        self.assertEqual(self._取错误(self._造配置("battle.json", ["强攻", "损失系数"], 2)), "")
        self.assertIn("超出范围", self._取错误(self._造配置("battle.json", ["强攻", "损失系数"], 2.5)))

    # —— 存档边界 ——

    def test_边界_存档版本1可读_0与99被拒(self):
        存档 = 夹具.载入存档模块()
        目录 = 夹具.临时目录()
        游戏 = 夹具.载入游戏()
        self.assertTrue(存档.保存游戏(游戏.__dict__, "边界", 目录)[0])
        成功, 提示, _ = 存档.读取存档("边界", 目录)
        self.assertTrue(成功)
        路径 = 存档.存档路径("边界", 目录)
        with open(路径, encoding="utf-8") as 文件:
            数据 = json.load(文件)
        for 版本, 关键字 in ((0, "旧版本"), (99, "更新的程序版本")):
            数据["存档版本"] = 版本
            with open(路径, "w", encoding="utf-8") as 文件:
                json.dump(数据, 文件, ensure_ascii=False)
            成功, 提示, _ = 存档.读取存档("边界", 目录)
            self.assertFalse(成功)
            self.assertIn(关键字, 提示)

    def test_边界_存档名长度与字符限制(self):
        存档 = 夹具.载入存档模块()
        目录 = 夹具.临时目录()
        游戏 = 夹具.载入游戏()
        self.assertFalse(存档.保存游戏(游戏.__dict__, "a" * 33, 目录)[0])
        self.assertTrue(存档.保存游戏(游戏.__dict__, "a" * 32, 目录)[0])
        for 非法名 in ("子目录/名字", "子目录\\名字", "带空格 的名字", "带*号"):
            self.assertFalse(存档.保存游戏(游戏.__dict__, 非法名, 目录)[0], 非法名)

    def test_边界_存档月份越界被判损坏(self):
        存档 = 夹具.载入存档模块()
        目录 = 夹具.临时目录()
        游戏 = 夹具.载入游戏()
        存档.保存游戏(游戏.__dict__, "月份", 目录)
        路径 = 存档.存档路径("月份", 目录)
        with open(路径, encoding="utf-8") as 文件:
            数据 = json.load(文件)
        数据["日期"]["当前月份"] = 13
        with open(路径, "w", encoding="utf-8") as 文件:
            json.dump(数据, 文件, ensure_ascii=False)
        成功, 提示, _ = 存档.读取存档("月份", 目录)
        self.assertFalse(成功)
        self.assertIn("1~12", 提示)


if __name__ == "__main__":
    unittest.main(verbosity=2)
