# -*- coding: utf-8 -*-
"""按区域查看 git 历史（溯源 B 层的入口）。

用法：
    python tools/区域日志.py --列表            # 列出全部区域及其路径
    python tools/区域日志.py 美术               # 美术区域的全部提交
    python tools/区域日志.py 引擎 -n 10         # 最近 10 条
    python tools/区域日志.py 美术 --统计        # 只看该区域的提交数量与改动规模
    python tools/区域日志.py 全局               # 全仓库（等于 git log）

设计说明：
    * 不做"每个区域一个分支" —— 单人项目里分支维护成本远高于收益；
      改为**目录隔离 + 按路径过滤历史**，效果一样而冲突为零；
    * 提交信息建议带区域前缀（`[美术] …`），但不做强制的提交钩子；
      本工具会顺带统计前缀的使用情况，便于你自己养成习惯。
"""
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# 区域 → 路径（与 docs/区域划分与溯源.md 的表格保持一致）
区域路径 = {
    "引擎": ["src/"],
    "数值": ["config/", "!config/map.json"],
    "地理": ["config/map.json"],
    "美术": ["assets/"],
    "界面": ["ui/"],
    "文案": [],                       # 暂未抽离（文案内联在 src/ 中）
    "测试": ["tests/", "自测_确定性判定.py", "run_tests.py"],
    "文档": ["docs/", "README.md", "CHANGELOG.md", "DEMO.md", "LICENSE"],
    "构建": ["tools/"],
    "归档": ["legacy/"],
    "运行": ["saves/"],
    "全局": [],
}


def 跑git(参数们):
    结果 = subprocess.run(["git", *参数们], capture_output=True, text=True, encoding="utf-8",
                        errors="replace")
    return 结果.returncode, (结果.stdout or "").strip(), (结果.stderr or "").strip()


def 主函数():
    参数 = sys.argv[1:]
    if not 参数 or 参数[0] in ("-h", "--help"):
        print(__doc__)
        return 0
    if 参数[0] == "--列表":
        print("区域　　　　对应路径")
        print("-" * 46)
        for 名, 路径 in 区域路径.items():
            print(f"{名:<8}{'　'.join(路径) if 路径 else '（暂未抽离 / 全仓库）'}")
        return 0

    区域 = 参数[0]
    if 区域 not in 区域路径:
        print(f"未知区域：{区域}\n可用区域：{'、'.join(区域路径)}")
        return 2
    余下 = 参数[1:]
    条数 = "20"
    if "-n" in 余下:
        条数 = 余下[余下.index("-n") + 1]
    只看统计 = "--统计" in 余下

    路径们 = [项 for 项 in 区域路径[区域] if not 项.startswith("!")]
    排除 = [项[1:] for 项 in 区域路径[区域] if 项.startswith("!")]
    if not 路径们:
        if 区域 == "文案":
            print("「文案」区域尚未抽离：当前约 183 处中文文案内联在 src/ 中。")
            print("抽出后本工具会自动生效（见 docs/叙事文案区域说明.md）。")
            return 0
        路径们 = ["."]

    基础 = ["log", f"--pretty=format:%h | %ad | %s", "--date=short"]
    if 只看统计:
        基础 = ["log", "--pretty=format:%h", "--date=short"]
    码, 输出, 错误 = 跑git(基础 + ["-n", 条数, "--", *路径们])
    if 码 != 0:
        print("git 调用失败：" + (错误 or "未知错误"))
        return 1
    if 错误:
        pass

    if 只看统计:
        行们 = [行 for 行 in 输出.splitlines() if 行.strip()]
        print(f"区域「{区域}」：{len(行们)} 次提交（最近 {条数} 条以内）")
        print(f"涉及路径：{'、'.join(路径们)}")
        码, 规模, _ = 跑git(["log", "--oneline", "--numstat", "--", *路径们])
        if 码 == 0:
            文件数, 增, 删 = set(), 0, 0
            for 行 in 规模.splitlines():
                段 = 行.split("\t")
                if len(段) == 3 and 段[0].isdigit():
                    文件数.add(段[2])
                    增 += int(段[0])
                    删 += int(段[1])
            print(f"累计改动：{len(文件数)} 个文件，+{增} / -{删} 行")
        return 0

    print(f"区域「{区域}」的提交历史（路径：{'、'.join(路径们)}）")
    print("=" * 88)
    print(输出 if 输出 else "（该区域暂无提交）")
    print("=" * 88)

    # 顺带看看前缀习惯
    码, 全部, _ = 跑git(["log", f"--pretty=%s", "-n", "200"])
    if 码 == 0:
        with_prefix = [行 for 行 in 全部.splitlines() if 行.strip().startswith("[")]
        print(f"提交信息带区域前缀的比例：{len(with_prefix)} / {len(全部.splitlines())}"
              f"（约定见 docs/区域划分与溯源.md，非强制）")
    if 排除:
        print(f"注：已排除 {'、'.join(排除)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(主函数())
