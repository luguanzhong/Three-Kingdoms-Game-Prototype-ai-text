# -*- coding: utf-8 -*-
"""回归测试：为真实修复过的缺陷与曾暴露过的薄弱点固化用例。

每个用例的 docstring 标注来源（CHANGELOG / 开发日志中的真实记录），不虚构历史。
"""
import json
import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import 夹具


class 回归测试(unittest.TestCase):

    # —— M2 修复：非严格模式改为"整体回退"，非法值不得进入判定逻辑 ——

    def test_regression_M2_非法配置不泄漏进游戏逻辑(self):
        """来源：M2 CHANGELOG「修复」——此前部分合并会让非法值进入判定。"""
        加载器 = 夹具.载入配置模块()
        目录 = 造配置(("battle.json", ["强攻", "损失系数"], 5))
        回退 = 加载器.载入配置(配置目录=目录, 严格=False)
        self.assertEqual(回退, 加载器.内置默认配置())
        self.assertEqual(回退["战斗"]["强攻"]["损失系数"], 0.8)

    def test_regression_M2_非法配置报错含文件字段期望与实际(self):
        """来源：M2 CHANGELOG「新增」——报错格式统一为 文件 + 字段 + 期望 + 实际。"""
        错误 = 取错误(造配置(("battle.json", ["强攻", "损失系数"], "很痛")))
        self.assertIn("config/battle.json", 错误)
        self.assertIn("战斗.强攻.损失系数", 错误)
        self.assertIn("期望", 错误)
        self.assertIn("实际", 错误)

    def test_regression_M2_字段拼写错误被指出(self):
        """来源：M2 CHANGELOG「新增」——未知字段提示（多为拼写错误）。"""
        错误 = 取错误(造配置(("battle.json", ["强攻", "损失系树"], 0.8)))
        self.assertIn("未知字段", 错误)

    # —— M3 修复：城池必填字段差异（曾导致所有存档被判损坏） ——

    def test_regression_M3_真实存档不被误判损坏(self):
        """来源：M3 CHANGELOG「修复」——校验把敌方城池的"守军"误用到蜀汉城池（后者为"兵力"）。"""
        存档 = 夹具.载入存档模块()
        游戏 = 夹具.载入游戏()
        数据 = 存档.采集状态(游戏.__dict__)
        self.assertEqual(存档.校验存档(数据), [])

    def test_regression_M3_蜀汉城池缺守军字段不算损坏(self):
        """专项回归：永安只有"兵力"没有"守军"，不得因此判损坏。"""
        存档 = 夹具.载入存档模块()
        游戏 = 夹具.载入游戏()
        数据 = 存档.采集状态(游戏.__dict__)
        self.assertNotIn("守军", 数据["蜀汉城池"]["永安"])
        self.assertEqual(存档.校验存档(数据), [])
        # 反面：敌方城池缺"守军"必须报错
        数据2 = 存档.采集状态(游戏.__dict__)
        数据2["敌方城池"]["襄阳"].pop("守军")
        错误 = 存档.校验存档(数据2)
        self.assertTrue(any("襄阳.缺少字段 守军" in 一条 for 一条 in 错误))

    def test_regression_M3_损坏存档返回失败而非抛异常(self):
        """来源：M3 CHANGELOG「新增」——损坏存档只给可读提示，不抛裸异常。"""
        存档 = 夹具.载入存档模块()
        目录 = 夹具.临时目录()
        os.makedirs(目录, exist_ok=True)
        with open(os.path.join(目录, "坏.json"), "w", encoding="utf-8") as 文件:
            文件.write("{ 不是合法 JSON ")
        游戏 = 夹具.载入游戏()
        状态前 = 指纹(存档, 游戏)
        成功, 提示 = 存档.载入游戏(游戏.__dict__, "坏", 目录)
        self.assertFalse(成功)
        self.assertIn("JSON 解析失败", 提示)
        self.assertEqual(指纹(存档, 游戏), 状态前, "读档失败不应改动当前局面")

    def test_regression_M3_存档名非法字符被拒绝且不产生文件(self):
        """来源：M3 实测——非交互管道传入的乱码存档名被明确拒绝，游戏继续运行。"""
        存档 = 夹具.载入存档模块()
        目录 = 夹具.临时目录()
        游戏 = 夹具.载入游戏()
        成功, 提示 = 存档.保存游戏(游戏.__dict__, "坏/名字", 目录)
        self.assertFalse(成功)
        self.assertIn("非法字符", 提示)
        self.assertEqual(os.listdir(目录), [], "非法存档名不应产生任何文件")

    def test_regression_M3_存档写入为原子替换且无残留(self):
        """来源：M3 CHANGELOG「新增」——先写 .tmp 再 os.replace。"""
        存档 = 夹具.载入存档模块()
        目录 = 夹具.临时目录()
        游戏 = 夹具.载入游戏()
        self.assertTrue(存档.保存游戏(游戏.__dict__, "原子", 目录)[0])
        文件们 = sorted(os.listdir(目录))
        self.assertEqual(文件们, ["原子.json"])

    # —— 高风险边界固化（M2 自测阶段曾写错期望值，暴露该任务的产出语义） ——

    def test_regression_练兵任务按统御产出_驻守险关无额外产出(self):
        """来源：M2 自测期望值修正记录——练兵任务会额外增加兵力，冬季用例须避开该干扰。"""
        游戏 = 夹具.载入游戏()
        游戏.蜀汉["粮草"] = 80
        游戏.蜀汉["兵力"] = 18000
        游戏.按姓名查找("魏延")["任务"] = "练兵"          # 统御7 → 每回合 +35
        夹具.捕获输出(游戏.结算回合)
        self.assertEqual(游戏.蜀汉["兵力"], 18000 + 7 * 5)

        游戏2 = 夹具.载入游戏()
        游戏2.按姓名查找("魏延")["任务"] = "驻守险关"      # 无产出
        夹具.捕获输出(游戏2.结算回合)
        self.assertEqual(游戏2.蜀汉["兵力"], 18000)

    def test_regression_冬季惩罚按是否有军队在外分档(self):
        """来源：M1 冬季系统设计——判定依据为"北伐先锋任务或围攻进行中"。"""
        游戏 = 夹具.载入游戏()
        self.assertTrue(游戏.有进攻行为判定())
        游戏.按姓名查找("魏延")["任务"] = "练兵"
        self.assertFalse(游戏.有进攻行为判定())
        游戏.全局["围攻状态"] = {"目标": "襄阳", "剩余": 2, "领将": "魏延", "出征兵力": 10000}
        self.assertTrue(游戏.有进攻行为判定())


def 造配置(改动):
    """把 config/ 复制到临时目录并按 (文件名, [路径段...], 新值) 改写一个字段。"""
    文件名, 路径段, 新值 = 改动
    目标 = tempfile.mkdtemp(dir=夹具.临时目录())
    shutil.copytree(os.path.join(夹具.仓库根目录, "config"), os.path.join(目标, "config"))
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


def 取错误(配置目录):
    try:
        夹具.载入配置模块().载入配置(配置目录=配置目录, 严格=True)
        return ""
    except Exception as 异常:
        return str(异常)


def 指纹(存档模块, 游戏模块):
    """状态指纹（去掉时间戳），用于证明"失败读档不改动局面"。"""
    数据 = 存档模块.采集状态(游戏模块.__dict__)
    数据.pop("保存时间", None)
    return json.dumps(数据, ensure_ascii=False, sort_keys=True)


if __name__ == "__main__":
    unittest.main(verbosity=2)
