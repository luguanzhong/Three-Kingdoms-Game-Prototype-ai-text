# -*- coding: utf-8 -*-
"""图形界面门面（src/游戏接口.py）的回归用例。

为什么必须有这一组用例：
    门面（游戏接口.会话）是"取代控制台外壳"的新控制器。只要它和引擎自己的 主循环()
    有一点点走偏（少推进一次日期、多算一次回合、大事名额放水），玩家在 GUI 里玩的就不再是
    同一个游戏，而 126 项自测**保护不到 GUI**。所以这里用四条用例把门面钉死：

    【一】一致性：同样"什么都不做"打满 20 回合，门面推进出的最终状态必须与
          引擎 主循环(自动演示=False) 的结果**逐字段相同**（只有保存时间允许不同）。
    【二】大事名额：每回合至多一件大事 —— 与 决策阶段() 的 `已行大事` 同义。
    【三】存档槽位：三个槽位的存 / 读往返，状态指纹必须一致；空槽位读取要被拒。
    【四】界面冒烟：主窗口能构建与销毁（无显示环境时自动跳过），
          并验证"把引擎菜单解析成可点选项"的解析逻辑。
"""
import contextlib
import io
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import 夹具  # noqa: E402

sys.path.insert(0, 夹具.源码目录)
import save_manager  # noqa: E402
import 游戏接口  # noqa: E402


def 指纹(模块):
    """状态指纹：去掉保存时间后的整份状态（与旧自测的比对方式一致）。"""
    状态 = save_manager.采集状态(模块.__dict__)
    状态.pop("保存时间", None)
    import json
    return json.dumps(状态, ensure_ascii=False, sort_keys=True)


class 门面一致性(unittest.TestCase):
    """【一】门面推进 vs 引擎主循环推进 —— 必须逐字段相同。"""

    def test_门面推进与引擎主循环结果完全一致(self):
        """同样"每回合什么都不做"打满 20 回合，两条路径的最终状态必须相同。

        这是本文件最重要的一条：它证明 GUI 玩到的是**同一个游戏**，
        而不是"看起来像、但回合推进差半拍"的另一个实现。
        """
        # ① 引擎自己的主循环：扮演幕僚 + 每回合输入 6（结束本回合＝什么都不做）
        #    注意：输入提供者必须"无限供应同一个答案"——20 回合里可能还会插入
        #    「东吴提议结盟」的询问（第 1135 行），答案固定为 6 时被引擎按"婉拒"处理，
        #    两条路径的回答保持一致，才能比状态。
        引擎 = 夹具.载入游戏()
        引擎.input = lambda 提示="": "6"
        原睡眠 = 引擎.time.sleep
        引擎.time.sleep = lambda 秒: None      # 跳掉显示停顿只为提速，不改变任何状态
        缓冲 = io.StringIO()
        try:
            with contextlib.redirect_stdout(缓冲):
                引擎.主循环(自动演示=False)
        finally:
            引擎.time.sleep = 原睡眠
        输出 = 缓冲.getvalue()
        self.assertIn("决策阶段", 输出, "主循环没有进入决策阶段，测试前提不成立")
        self.assertIn("【结局】", 输出, "主循环未跑到结局，测试前提不成立")

        # ② 门面：新开局 + 连续结束回合（同样什么都不做、同样用 6 回答一切询问）
        #    无需打桩 time.sleep：门面的 结束回合() 不做显示停顿（停顿只在引擎的主循环里）
        局 = 游戏接口.会话()
        局.新开局(输出回调=lambda 文本: None, 询问回调=lambda 提示: "6")
        有结局 = False
        for _ in range(引擎.总回合数 + 2):
            有结局, _结局 = 局.结束回合()
            if 有结局:
                break
        self.assertTrue(有结局, "门面没能推出结局")

        # ③ 逐字段比对
        self.assertEqual(局.游戏.回合计数, 引擎.回合计数,
                         "门面与主循环的回合数不一致：回合推进记账有偏差")
        self.assertEqual(局.游戏.显示日期(), 引擎.显示日期(),
                         "门面与主循环的日期不一致：推进日期与回合计数的顺序可能颠倒了")
        self.assertEqual(指纹(局.游戏), 指纹(引擎),
                         "门面推进出的状态与引擎主循环不一致——GUI 玩到的将不是同一个游戏")


class 大事名额(unittest.TestCase):
    """【二】每回合一件大事 —— 与 决策阶段() 同义。"""

    def setUp(self):
        self.局 = 游戏接口.会话()
        # 询问回调答 "1"：外交菜单里第 1 项是「割地示好」，必定成功且占用大事名额
        self.局.新开局(输出回调=lambda 文本: None, 询问回调=lambda 提示: "1")

    def 取行动(self, 键):
        return next(项 for 项 in 游戏接口.行动表 if 项["键"] == 键)

    def test_初始状态大事可用(self):
        self.assertFalse(self.局.大事已用)
        for 键 in ("军事行动", "计谋", "外交"):
            self.assertTrue(self.局.行动可用(self.取行动(键))[0], f"{键} 开局应可用")

    def test_执行一件大事后其余大事被拒(self):
        # 外交·割地示好：开局粮草 80 ≥ 30，必定成功且占用大事名额
        成功, _ = self.局.执行行动("外交")
        self.assertTrue(成功)
        self.assertTrue(self.局.大事已用, "外交成功后未占用大事名额")
        可用, 原因 = self.局.行动可用(self.取行动("军事行动"))
        self.assertFalse(可用, "同一回合内不应允许第二件大事")
        self.assertIn("大事", 原因)
        # 轻量行动不受限制
        self.assertTrue(self.局.行动可用(self.取行动("部署任务"))[0])

    def test_结束回合后大事名额重置(self):
        self.局.大事已用 = True
        self.局.结束回合()
        self.assertFalse(self.局.大事已用, "进入新回合后大事名额应重置")

    def test_大局已结束时行动全部禁用(self):
        self.局.结局 = "【结局】测试用"
        可用, 原因 = self.局.行动可用(self.取行动("计谋"))
        self.assertFalse(可用)
        self.assertIn("结束", 原因)

    def test_外交只在返回大事时占名额(self):
        """外交菜单返回 None（选了"返回"）时不得占用大事名额。"""
        self.局.询问回调 = lambda 提示: "0"
        成功, _ = self.局.执行行动("外交")
        self.assertTrue(成功)
        self.assertFalse(self.局.大事已用, "选了返回却被算作执行了大事")


class 存档槽位(unittest.TestCase):
    """【三】三个槽位的存 / 读往返。"""

    def setUp(self):
        import tempfile
        self.临时目录 = tempfile.mkdtemp(prefix="蜀汉GUI存档_")
        self.原默认目录 = save_manager.默认存档目录
        save_manager.默认存档目录 = lambda: self.临时目录
        self.局 = 游戏接口.会话()
        self.局.新开局(输出回调=lambda 文本: None, 询问回调=lambda 提示: "0")

    def tearDown(self):
        save_manager.默认存档目录 = self.原默认目录
        import shutil
        shutil.rmtree(self.临时目录, ignore_errors=True)

    def test_三个槽位都可用(self):
        self.assertEqual(len(游戏接口.槽位们), 3, "本轮要求恰好三个存档位")
        for 槽位 in 游戏接口.槽位们:
            成功, 提示 = self.局.保存到槽位(槽位)
            self.assertTrue(成功, f"{槽位} 保存失败：{提示}")

    def test_存取往返状态一致(self):
        self.局.结束回合()
        self.局.结束回合()
        存前 = 指纹(self.局.游戏)
        成功, 提示 = self.局.保存到槽位("slot2")
        self.assertTrue(成功, 提示)

        # 重开一局（状态归零），再从槽位读回
        成功, 提示 = self.局.读档开局("slot2", 输出回调=lambda 文本: None,
                                  询问回调=lambda 提示: "0")
        self.assertTrue(成功, 提示)
        self.assertEqual(指纹(self.局.游戏), 存前, "读档后状态与存档时不一致")

    def test_空槽位读取被拒且不破坏当前进度(self):
        存前 = 指纹(self.局.游戏)
        成功, 提示 = self.局.保存读档("slot3")
        self.assertFalse(成功, "空槽位不应读取成功")
        self.assertEqual(指纹(self.局.游戏), 存前, "读档失败时不应改变当前状态")

    def test_槽位概览区分有档与空档(self):
        self.局.保存到槽位("slot1")
        概览 = {项["槽位"]: 项 for 项 in self.局.槽位概览()}
        self.assertTrue(概览["slot1"]["有档"])
        self.assertFalse(概览["slot2"]["有档"])
        self.assertIn("第", 概览["slot1"]["摘要"] + "第", "槽位摘要应包含回合信息")

    def test_非法槽位被拒(self):
        成功, 提示 = self.局.保存到槽位("slot9")
        self.assertFalse(成功)
        self.assertIn("无效槽位", 提示)


class 界面冒烟(unittest.TestCase):
    """【四】界面构建冒烟 + 菜单解析。"""

    def test_菜单解析把引擎选项变按钮(self):
        样例 = "1. 镇守城池\n2. 驻守险关\n0. 返回"
        选项 = 游戏接口_解析(样例)
        self.assertEqual([值 for 值, _ in 选项], ["1", "2", "0"])

    def test_菜单解析只取最后一段(self):
        样例 = "1. 关羽\n2. 张飞\n0. 返回\n\n【军事行动】目标城池：\n1. 襄阳\n0. 返回"
        选项 = 游戏接口_解析(样例)
        self.assertEqual([值 for 值, _ in 选项], ["1", "0"], "应只保留最后一段菜单（目标城池）")

    def test_菜单解析支持字母选项(self):
        选项 = 游戏接口_解析("A. 牺牲部队\nB. 牺牲将领")
        self.assertEqual([值 for 值, _ in 选项], ["A", "B"])

    def test_主窗口可构建与销毁(self):
        try:
            import tkinter
            探针 = tkinter.Tk()
            探针.destroy()
        except Exception as 异常:
            self.skipTest(f"当前环境无图形界面，跳过界面构建：{异常!r}")
        sys.path.insert(0, os.path.join(夹具.仓库根目录, "ui"))
        try:
            import 主界面
        except Exception as 异常:
            self.fail(f"界面模块导入失败：{异常!r}")
        窗口 = None
        try:
            窗口 = 主界面.主窗口()
            窗口.update()
            局面 = 窗口.会话.局面()
            self.assertIn("蜀汉", 局面)
            self.assertEqual(局面["回合"], 1)
            self.assertTrue(窗口.会话.态势图().strip(), "战区态势图不应为空")
        finally:
            if 窗口 is not None:
                窗口.destroy()


def 游戏接口_解析(文本):
    """调用界面里的菜单解析（静态方法，不需创建窗口）。"""
    sys.path.insert(0, os.path.join(夹具.仓库根目录, "ui"))
    import 主界面
    return 主界面.选项对话框._解析(文本)


if __name__ == "__main__":
    unittest.main(verbosity=2)
