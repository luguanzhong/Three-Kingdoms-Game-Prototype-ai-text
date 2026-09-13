# -*- coding: utf-8 -*-
"""架构测试：零随机约束、仅标准库依赖、可编译性与判定函数的确定性。

白名单说明（记录原因，避免误伤）：
1. 扫描范围仅限 `夹具.生产模块`（蜀汉突围.py / config_loader.py / save_manager.py）——
   `蜀汉突围_*备份.py` 是历史版本快照、不参与运行，扫描它只会产生噪声。
2. 本目录下的测试代码允许出现 `random` 等字样（它们正是用来断言"生产代码不含这些字样"的），
   因此不纳入扫描；这是有意的白名单，不是漏检。
"""
import os
import py_compile
import re
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import 夹具

# 随机相关关键字（覆盖标准库 random / secrets 与常见随机调用）
随机关键字 = ("random", "randint", "randrange", "shuffle", "choice", "choices",
              "uniform", "sample", "getrandbits", "seed", "secrets", "urandom")
关键字模式 = re.compile(r"(" + "|".join(随机关键字) + r")", re.IGNORECASE)
# 允许的标准库模块（生产代码只应使用这些 + 本地模块）
标准库白名单 = {"os", "sys", "time", "json", "io", "contextlib", "shutil",
                "tempfile", "importlib", "importlib.util", "py_compile"}


class 架构测试(unittest.TestCase):

    def test_架构_生产模块不含随机调用(self):
        """逐文件逐行扫描，失败时给出 文件:行号:内容。"""
        命中 = []
        for 文件名 in 夹具.生产模块:
            for 行号, 行 in enumerate(夹具.源码行们(文件名), 1):
                for 匹配 in 关键字模式.finditer(行):
                    命中.append(f"{文件名}:{行号}: 出现随机关键字 {匹配.group(0)!r} → {行.strip()}")
        self.assertEqual(命中, [], "生产代码出现随机调用：\n" + "\n".join(命中))

    def test_架构_生产模块不导入随机库(self):
        命中 = []
        for 文件名 in 夹具.生产模块:
            源码 = 夹具.读取源码(文件名)
            for 模式 in ("import random", "from random", "import secrets", "from secrets"):
                if 模式 in 源码:
                    命中.append(f"{文件名}: {模式}")
        self.assertEqual(命中, [], "生产代码导入了随机库：" + "；".join(命中))

    def test_架构_生产模块仅使用标准库与本地模块(self):
        违规 = []
        for 文件名 in 夹具.生产模块:
            for 行号, 行 in enumerate(夹具.源码行们(文件名), 1):
                匹配 = re.match(r"\s*(?:import|from)\s+([A-Za-z_][\w.]*)", 行)
                if not 匹配:
                    continue
                模块名 = 匹配.group(1)
                顶层 = 模块名.split(".")[0]
                if 顶层 in 标准库白名单 or 模块名 in 标准库白名单 or 顶层 in 夹具.本地模块名:
                    continue
                违规.append(f"{文件名}:{行号}: {模块名}")
        self.assertEqual(违规, [], "出现非标准库/非本地模块导入：" + "；".join(违规))

    def test_架构_生产模块可编译(self):
        临时 = tempfile.mkdtemp(prefix="蜀汉编译_")
        for 文件名 in 夹具.生产模块:
            try:
                py_compile.compile(os.path.join(夹具.仓库根目录, 文件名),
                                   cfile=os.path.join(临时, 文件名 + "c"), doraise=True)
            except py_compile.PyCompileError as 异常:
                self.fail(f"{文件名} 编译失败：{异常}")

    def test_架构_判定函数对同一输入结果稳定(self):
        """零随机的行为级校验：同输入连续调用两次结果必须完全一致。"""
        游戏 = 夹具.载入游戏()
        样例 = [(9000, 5000), (4500, 5000), (2000, 5000)]
        for 进攻, 守军 in 样例:
            self.assertEqual(游戏.计算强攻判定(进攻, 守军), 游戏.计算强攻判定(进攻, 守军))
            self.assertEqual(游戏.计算围攻判定(进攻, 守军), 游戏.计算围攻判定(进攻, 守军))
            self.assertEqual(游戏.计算必败判定(进攻, 守军), 游戏.计算必败判定(进攻, 守军))
        关羽 = 游戏.按姓名查找("关羽")
        self.assertEqual(游戏.防御加成计算(关羽), 游戏.防御加成计算(关羽))

    def test_架构_两次独立加载的初始状态一致(self):
        """模块级字面量必须是纯粹的：两次加载得到同样的开局状态与日期。"""
        甲, 乙 = 夹具.载入游戏(), 夹具.载入游戏()
        self.assertEqual(甲.蜀汉, 乙.蜀汉)
        self.assertEqual(甲.将领们, 乙.将领们)
        self.assertEqual(甲.显示日期(), 乙.显示日期())
        self.assertEqual(甲.总回合数, 乙.总回合数)

    def test_架构_白名单内确实存在历史备份与测试目录(self):
        """确保白名单不是借口：目录里确实有需要排除的备份与测试文件。"""
        备份 = [名 for 名 in os.listdir(夹具.仓库根目录)
               if 名.startswith("蜀汉突围_") and 名.endswith("备份.py")]
        self.assertTrue(备份, "未找到历史备份快照（白名单前提不成立）")
        self.assertTrue(os.path.isdir(os.path.join(夹具.仓库根目录, "tests")))


if __name__ == "__main__":
    unittest.main(verbosity=2)
