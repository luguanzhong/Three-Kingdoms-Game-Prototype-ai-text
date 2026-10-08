# -*- coding: utf-8 -*-
"""把《三国·蜀汉突围》图形界面打包成单文件 exe（Windows）。

用法：
    python tools/打包exe.py                # 输出到 dist/蜀汉突围.exe
    python tools/打包exe.py --名字 我的游戏  # 自定义 exe 名字

依赖说明：
    * **运行期**：零第三方依赖（引擎、门面、界面全部只用标准库，界面用标准库 tkinter）；
    * **构建期**：需要 PyInstaller（仅打包时用到，不属于运行依赖）。未安装时本脚本会给出安装命令。

打包后的行为：
    * config/ 随包释放（PyInstaller 的 --add-data），因此**没有外部配置文件也能跑**；
      想改数值时，把 config/ 放到 exe 同级目录即可覆盖（见 README「配置」一节）；
    * saves/ 写在 **exe 同级目录**（见 src/save_manager.定位存档根目录），程序退出后存档保留；
    * 双击即玩；也可命令行 `蜀汉突围.exe --自检` 做无人工自检（结果写系统临时目录）。
"""
import os
import shutil
import subprocess
import sys

仓库根目录 = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
入口脚本 = os.path.join(仓库根目录, "ui", "主界面.py")
配置文件 = os.path.join(仓库根目录, "config")
资产目录 = os.path.join(仓库根目录, "assets")


def 主函数():
    名字 = "蜀汉突围"
    参数 = sys.argv[1:]
    if "--名字" in 参数:
        名字 = 参数[参数.index("--名字") + 1]

    try:
        import PyInstaller  # noqa: F401
    except ImportError:
        print("未安装 PyInstaller（构建期工具，不属于运行依赖）。请先执行：")
        print(f"    {sys.executable} -m pip install pyinstaller")
        return 1

    if not os.path.isfile(入口脚本):
        print(f"找不到入口脚本：{入口脚本}")
        return 1
    if not os.path.isdir(配置文件):
        print(f"找不到配置目录：{配置文件}")
        return 1
    if not os.path.isdir(资产目录):
        print(f"找不到资产目录：{资产目录}（字体与配色都在里面，缺了界面会退到系统字体）")
        return 1

    # Windows 上 --add-data 的分隔符是分号（Linux/macOS 是冒号）
    分隔符 = ";" if os.name == "nt" else ":"
    命令 = [
        sys.executable, "-m", "PyInstaller",
        "--noconfirm", "--clean",
        "--onefile",                       # 打成单个 exe
        "--windowed",                      # 只开图形窗口，不带黑色控制台
        "--name", 名字,
        "--paths", os.path.join(仓库根目录, "src"),
        "--add-data", f"{配置文件}{分隔符}config",   # 配置随包，缺省也能跑
        "--add-data", f"{资产目录}{分隔符}assets",   # 美术资产随包（字体/配色/台账）
        # 引擎与门面是"按名字导入"的本地模块，显式声明避免静态分析漏掉
        "--hidden-import", "蜀汉突围",
        "--hidden-import", "config_loader",
        "--hidden-import", "save_manager",
        "--hidden-import", "游戏接口",
        "--distpath", os.path.join(仓库根目录, "dist"),
        "--workpath", os.path.join(仓库根目录, "build"),
        "--specpath", os.path.join(仓库根目录, "build"),
        入口脚本,
    ]
    print("执行打包命令：")
    print("  " + " ".join(命令) + "\n")
    结果 = subprocess.run(命令, cwd=仓库根目录)
    if 结果.returncode != 0:
        print(f"\n打包失败，PyInstaller 返回码 {结果.returncode}")
        return 结果.returncode

    产物 = os.path.join(仓库根目录, "dist", 名字 + (".exe" if os.name == "nt" else ""))
    if not os.path.isfile(产物):
        print(f"\n命令成功但没找到产物：{产物}")
        return 1
    大小 = os.path.getsize(产物) / (1024 * 1024)
    print(f"\n打包成功：{产物}")
    print(f"体积：{大小:.1f} MB　（引擎＋界面＋tkinter＋配置，全部内置，双击即可运行）")
    print("验证建议：在产物目录执行　" + os.path.basename(产物) + " --自检　"
          f"（结果写入 {os.path.join(os.environ.get('TEMP', '.'), '蜀汉突围_自检报告.txt')}）")
    return 0


if __name__ == "__main__":
    raise SystemExit(主函数())
