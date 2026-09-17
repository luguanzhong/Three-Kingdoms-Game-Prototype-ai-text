# -*- coding: utf-8 -*-
"""旧自测全量回归：把 `自测_确定性判定.py`（126 项断言）原样纳入一键测试。

设计说明：M4 不做大搬家——原文件保留在仓库根目录、断言内容不改、仍可单独运行：
    python 自测_确定性判定.py
（目录规范化时仅为其补了 3 行 `src/` 路径引导，126 项断言与用例逻辑零改动。）
本用例只是把它整体执行一次并核对结果，因此原有 126 项断言一项不丢。
"""
import contextlib
import io
import os
import re
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import 夹具

原有断言数下限 = 126


class 旧自测全量回归(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.输出 = ""
        cls.退出码 = None
        cls.异常 = None
        缓冲 = io.StringIO()
        try:
            with contextlib.redirect_stdout(缓冲):
                夹具.载入模块("自测_确定性判定.py", "旧自测_全量回归实例")
        except SystemExit as 退出:          # 脚本内部断言失败会 raise SystemExit(1)
            cls.退出码 = 退出.code
        except Exception as 异常:            # 其它异常也要转成清晰的用例失败
            cls.异常 = 异常
        cls.输出 = 缓冲.getvalue()

    def test_旧自测脚本_全部通过(self):
        self.assertIsNone(self.异常, f"旧自测脚本抛出异常：{self.异常!r}")
        self.assertIsNone(self.退出码, "旧自测脚本存在失败断言（SystemExit 非空）")
        self.assertIn("项自测通过", self.输出)

    def test_旧自测脚本_断言数不少于基线(self):
        数字 = re.findall(r"全部 (\d+) 项自测通过", self.输出)
        self.assertTrue(数字, "未找到断言统计行，输出片段：" + self.输出[-300:])
        self.assertGreaterEqual(int(数字[-1]), 原有断言数下限)

    def test_旧自测脚本_仍保留零随机检查(self):
        源码 = 夹具.读取源码("自测_确定性判定.py")
        self.assertIn('"random" not in', 源码)

    def test_旧自测脚本_仍保留分类章节(self):
        源码 = 夹具.读取源码("自测_确定性判定.py")
        for 章节 in ("【一】", "【五】", "【七】", "【九】", "【十】"):
            self.assertIn(章节, 源码, f"缺少章节 {章节}")


if __name__ == "__main__":
    unittest.main(verbosity=2)
