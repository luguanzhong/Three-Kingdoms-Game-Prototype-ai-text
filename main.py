# -*- coding: utf-8 -*-
"""《三国·蜀汉突围》统一入口（命令行的唯一推荐入口）。

用法：
    python main.py                  # 新开局（交互式游玩）
    python main.py --demo           # 无人值守自动演示（跑满 20 回合）
    python main.py --load save1     # 读取存档续局
    python main.py --list-saves     # 列出全部存档
    python main.py --check-config   # 校验 config/ 配置合法性
    python main.py --help           # 查看全部参数

说明：游戏实现位于 `src/蜀汉突围.py`（单文件三段式结构：状态定义 / 确定性判定 / 主循环）。
本文件只做两件事——把 `src/` 加入模块搜索路径，然后把命令行参数原样转发给它的 主函数()。
因此 `python main.py <参数>` 与 `python src/蜀汉突围.py <参数>` 完全等价。
"""
import os
import sys

仓库根目录 = os.path.dirname(os.path.abspath(__file__))
源码目录 = os.path.join(仓库根目录, "src")
if 源码目录 not in sys.path:
    sys.path.insert(0, 源码目录)

import 蜀汉突围  # noqa: E402  （必须等 sys.path 就绪后再导入）


if __name__ == "__main__":
    raise SystemExit(蜀汉突围.主函数())
