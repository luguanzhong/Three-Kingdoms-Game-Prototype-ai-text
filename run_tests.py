# -*- coding: utf-8 -*-
"""一键测试入口：python run_tests.py [--fast] [--区域 名称]

- 默认：发现并运行 tests/ 下全部用例（含"旧自测全量回归"，整体约 1.5 分钟）。
- --fast：跳过耗时的旧自测全量回归，只跑秒级的分类用例（适合改代码时快速自检）。
- --区域：只跑与某个区域相关的用例（区域隔离的配套入口，互不干扰）。
退出码：全部通过 0，否则 1（可直接用于 CI 或 git hook）。
"""
import argparse
import os
import sys
import time
import unittest

# 区域 → 相关测试模块（与 docs/区域划分与溯源.md 的区域表对应）
区域用例 = {
    "引擎": ("test_rules", "test_boundaries", "test_endings", "test_architecture", "test_legacy_suite"),
    "数值": ("test_boundaries",),
    "地理": ("test_map", "test_tracing", "test_baseimage"),
    "美术": ("test_assets", "test_baseimage"),
    "界面": ("test_gui_facade", "test_map", "test_assets"),
    "文案": (),          # 尚未抽离，暂无专属用例
    "测试": ("test_architecture",),
    "文档": (),
    "构建": ("test_tracing",),
    "归档": ("test_architecture",),
    "运行": ("test_gui_facade",),
}


def 展开用例(套件):
    """把嵌套的 TestSuite 展平成单个用例列表（用于 --fast / --区域 过滤）。"""
    for 元素 in 套件:
        if isinstance(元素, unittest.TestSuite):
            yield from 展开用例(元素)
        else:
            yield 元素


def 主函数():
    解析 = argparse.ArgumentParser(description="蜀汉突围 · 一键测试")
    解析.add_argument("--fast", action="store_true",
                      help="跳过旧自测全量回归（耗时较久），只跑分类用例")
    解析.add_argument("--区域", choices=sorted(区域用例),
                      help="只跑与该区域相关的用例（见 docs/区域划分与溯源.md）")
    参数 = 解析.parse_args()

    仓库根 = os.path.dirname(os.path.abspath(__file__))
    tests目录 = os.path.join(仓库根, "tests")
    if 仓库根 not in sys.path:
        sys.path.insert(0, 仓库根)
    if not os.path.isdir(tests目录):
        print(f"找不到测试目录：{tests目录}")
        return 1

    套件 = unittest.TestLoader().discover(start_dir=tests目录, top_level_dir=tests目录)
    过滤说明 = []
    if 参数.fast:
        用例们 = [用例 for 用例 in 展开用例(套件) if "旧自测" not in 用例.id()]
        套件 = unittest.TestSuite(用例们)
        过滤说明.append("--fast：已跳过旧自测全量回归")
    if 参数.区域:
        模块们 = 区域用例[参数.区域]
        if not 模块们:
            用例们 = []
        else:
            用例们 = [用例 for 用例 in 展开用例(套件)
                    if any(模块 in 用例.id() for 模块 in 模块们)]
        套件 = unittest.TestSuite(用例们)
        过滤说明.append(f"--区域 {参数.区域}：只跑 {'、'.join(模块们) if 模块们 else '（暂无专属用例）'}")

    print("=" * 68)
    print("蜀汉突围 · 一键测试" + ("（" + "；".join(过滤说明) + "）" if 过滤说明 else ""))
    print("=" * 68)
    开始 = time.time()
    结果 = unittest.TextTestRunner(verbosity=2, stream=sys.stdout).run(套件)
    用时 = time.time() - 开始

    总数 = 结果.testsRun
    失败 = len(结果.failures)
    错误 = len(结果.errors)
    跳过 = len(result_skipped(结果))
    通过 = 总数 - 失败 - 错误 - 跳过

    print("\n" + "=" * 68)
    print(f"总数：{总数} ｜ 通过：{通过} ｜ 失败：{失败} ｜ 错误：{错误} ｜ 跳过：{跳过} ｜ 用时：{用时:.1f} 秒")
    if 失败 or 错误:
        print("失败/错误明细（也可回看上面的 ----- 区块）：")
        for 用例, 说明 in list(结果.failures) + list(结果.errors):
            首行 = 说明.strip().splitlines()[-1] if 说明.strip() else ""
            print(f"  · {用例.id()} → {首行}")
        print("结论：测试未全部通过")
    else:
        print("结论：全部通过")
    print("=" * 68)
    return 0 if not (失败 or 错误) else 1


def result_skipped(结果):
    """兼容不同 Python 版本读取跳过列表。"""
    return getattr(结果, "skipped", [])


if __name__ == "__main__":
    raise SystemExit(主函数())
