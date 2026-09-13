# -*- coding: utf-8 -*-
"""测试夹具：统一加载游戏 / 配置 / 存档模块，并提供捕获输出、脚本输入、源码读取等工具。

说明：本文件不是测试用例（文件名无 test_ 前缀，unittest 不会收集），
      所有测试模块通过 `import 夹具` 复用它，避免每个文件重复写加载逻辑。
"""
import contextlib
import importlib.util
import io
import os
import sys

仓库根目录 = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if 仓库根目录 not in sys.path:
    sys.path.insert(0, 仓库根目录)

# 生产模块清单：架构检查与"仅标准库"白名单都以它为准（历史备份快照不参与扫描）
生产模块 = ("蜀汉突围.py", "config_loader.py", "save_manager.py")
# 允许出现的本地模块名（非第三方）
本地模块名 = ("config_loader", "save_manager")


def 载入模块(文件名, 模块名):
    """按路径加载仓库根目录下的 .py 文件；每次调用都得到全新模块状态。"""
    路径 = os.path.join(仓库根目录, 文件名)
    规格 = importlib.util.spec_from_file_location(模块名, 路径)
    模块 = importlib.util.module_from_spec(规格)
    规格.loader.exec_module(模块)
    return 模块


def 载入游戏():
    """加载一份全新的游戏模块（不会触发主循环）。"""
    return 载入模块("蜀汉突围.py", "蜀汉突围_测试实例")


def 载入配置模块():
    """加载一份全新的配置加载模块。"""
    return 载入模块("config_loader.py", "config_loader_测试实例")


def 载入存档模块():
    """加载一份全新的存档模块。"""
    return 载入模块("save_manager.py", "save_manager_测试实例")


def 捕获输出(可调用, *参数, **关键字):
    """执行可调用对象并捕获 stdout，返回 (返回值, 输出文本)。"""
    缓冲 = io.StringIO()
    with contextlib.redirect_stdout(缓冲):
        结果 = 可调用(*参数, **关键字)
    return 结果, 缓冲.getvalue()


def 脚本输入(模块, 输入序列):
    """把模块的 input 替换为脚本输入队列（模拟玩家逐行输入）。"""
    队列 = list(输入序列)
    模块.input = lambda 提示="": 队列.pop(0)
    return 队列


def 运行对局(模块, 输入序列, **主循环参数):
    """驱动一局（或一段流程）并返回控制台输出文本。"""
    脚本输入(模块, 输入序列)
    _, 输出 = 捕获输出(模块.主循环, **主循环参数)
    return 输出


def 读取源码(文件名):
    with open(os.path.join(仓库根目录, 文件名), encoding="utf-8") as 文件:
        return 文件.read()


def 源码行们(文件名):
    return 读取源码(文件名).splitlines()


def 临时目录(前缀="蜀汉测试_"):
    """创建临时目录（调用方可自行清理）。"""
    import tempfile
    return tempfile.mkdtemp(prefix=前缀)
