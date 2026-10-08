# -*- coding: utf-8 -*-
"""字体子集化：把体积巨大的完整字库裁成"只用得到的字"，并按规定改名。

═══════════════════════════════════════════════════════════════════
【为什么需要这个工具】
完整中文字库动辄 20 MB 以上（霞鹜文楷 Regular 为 24.4 MB），直接入库会让仓库迅速膨胀。
而游戏真正会显示的字只有一两千个 —— 裁掉其余字形后通常只剩几百 KB，可以放心进 git。

【许可合规（很重要，不是可选项）】
本项目过渡期使用 **霞鹜文楷（LXGW WenKai）**，许可为 **SIL OFL 1.1**（已核实：Debian 主仓库
packages 的版权文件标注 `License: OFL-1.1`）。OFL 有两条与"修改"相关的硬要求：
  1. 修改版（**子集化属于修改**）**不得继续使用原有保留字体名** —— 因此本工具会强制把
     字体家族名改为你指定的新名字（默认「蜀汉过渡楷」），并写入描述说明派生来源；
  2. 分发时必须**随附 OFL 许可文本** —— 因此 assets/fonts/ 下必须放 LICENSE 文本，
     由 tools/资产台账.py 校验（缺许可文本会被判红）。
若日后换成自写字库，本工具同样适用（只是不再需要改名）。

【依赖说明】
本工具需要 `fonttools`（构建期依赖，**不是运行依赖**）：
    python -m pip install fonttools

【用法】
    # 1) 先下载完整字库到临时目录（不要放进仓库）
    #    例：LXGWWenKai-Regular.ttf  https://github.com/lxgw/LxgwWenKai/releases
    # 2) 子集化（默认扫描 src/ ui/ config/ 三个区域，覆盖游戏运行时全部可见文字）
    python tools/字体子集化.py 下载的字体.ttf --输出 assets/fonts/蜀汉过渡楷-子集.ttf
    # 3) 记入台账：python tools/资产台账.py 填校验值
"""
import argparse
import hashlib
import os
import sys

根目录 = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
默认扫描 = ("src", "ui", "config")
默认家族名 = "蜀汉过渡楷"

# 除扫描到的字符外，再补一批"运行时可能出现"的字符：数字、标点、全角符号、常用单位
补集 = (
    "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"
    " .,:;!?()[]{}<>+-*/=%#@&_|~^$'\"`\\"
    "　、。，；：？！（）【】《》〈〉「」『』—…·～×÷≤≥≠→←↑↓★☆●○◎◆◇■□▲▼"
    "年月光日时回合第共人万兵粮草城关将帅军马步骑弩箭火水风土金木"
)


def 扫描字符(目录们):
    """扫描指定目录下的文本文件，收集所有会被显示出来的字符。"""
    字符集 = set(补集)
    文件数 = 0
    for 目录 in 目录们:
        全路径 = os.path.join(根目录, 目录)
        if not os.path.isdir(全路径):
            continue
        for 当前, _子目录, 文件们 in os.walk(全路径):
            for 名 in 文件们:
                if not 名.endswith((".py", ".json", ".txt", ".md")):
                    continue
                try:
                    with open(os.path.join(当前, 名), encoding="utf-8") as 文件:
                        字符集 |= set(文件.read())
                except (OSError, UnicodeDecodeError):
                    continue
                文件数 += 1
    # 只保留"能显示出来"的字符：ASCII 可见字符 + 中文 + 中日韩标点 + 全角符号
    可用 = {c for c in 字符集
           if c.isprintable() and (ord(c) >= 0x20)
           and (ord(c) < 0x7F or 0x2000 <= ord(c) <= 0x206F
                or 0x3000 <= ord(c) <= 0x303F or 0x4E00 <= ord(c) <= 0x9FFF
                or 0xFF00 <= ord(c) <= 0xFFEF or 0x3400 <= ord(c) <= 0x4DBF)}
    return 可用, 文件数


def 改家族名(字体, 家族名, 说明):
    """按 OFL 要求把派生字体的家族名改成新名字，并写入派生说明。"""
    def 设置(标识, 文本):
        for 记录 in 字体["name"].names:
            if 记录.nameID == 标识:
                try:
                    记录.string = 文本
                except Exception:
                    pass
    设置(1, 家族名)                     # Family
    设置(2, "Regular")                  # Subfamily
    设置(4, 家族名 + " Regular")         # Full name
    设置(6, 家族名.replace(" ", ""))      # PostScript name
    设置(16, 家族名)                     # Typographic Family
    设置(10, 说明)                      # Description：说明派生来源（不改动原版权行）


def 主函数():
    解析 = argparse.ArgumentParser(description="字体子集化（构建期工具）")
    解析.add_argument("源字体", help="完整字库路径（.ttf/.otf）")
    解析.add_argument("--输出", default=os.path.join(根目录, "assets", "fonts", "蜀汉过渡楷-子集.ttf"))
    解析.add_argument("--家族名", default=默认家族名,
                    help="派生字体的家族名（OFL 要求修改版不得沿用原保留名）")
    解析.add_argument("--扫描", nargs="*", default=list(默认扫描),
                    help="扫描哪些目录来收集字符（默认 src ui config）")
    解析.add_argument("--来源", default="霞鹜文楷 LXGW WenKai（SIL OFL 1.1）",
                    help="派生来源说明，写入字体描述字段")
    参数 = 解析.parse_args()

    try:
        from fontTools import subset
    except ImportError:
        print("需要 fonttools（构建期依赖）：")
        print(f"    {sys.executable} -m pip install fonttools")
        return 1
    if not os.path.isfile(参数.源字体):
        print(f"找不到源字体：{参数.源字体}")
        return 1

    字符集, 文件数 = 扫描字符(参数.扫描)
    文本 = "".join(sorted(字符集))
    print(f"扫描 {文件数} 个文本文件，收集到 {len(字符集)} 个不同字符")

    选项 = subset.Options()
    选项.layout_features = ["*"]
    选项.name_IDs = ["*"]
    选项.name_legacy = True
    选项.notdef_outline = True
    选项.recalc_bounds = True
    选项.drop_tables = ["DSIG"]
    字体 = subset.load_font(参数.源字体, 选项)
    子集器 = subset.Subsetter(options=选项)
    子集器.populate(text=文本)
    子集器.subset(字体)
    改家族名(字体, 参数.家族名,
            f"本文件为子集化派生版本（来源：{参数.来源}）。已按 SIL OFL 1.1 要求更改家族名，"
            f"仅保留游戏用到的字形；许可全文见同目录 LICENSE 文本。")
    os.makedirs(os.path.dirname(参数.输出), exist_ok=True)
    subset.save_font(字体, 参数.输出, 选项)

    原大小 = os.path.getsize(参数.源字体)
    新大小 = os.path.getsize(参数.输出)
    with open(参数.输出, "rb") as 文件:
        指纹 = hashlib.sha256(文件.read()).hexdigest()
    print(f"源字体 {原大小 / 1024 / 1024:.1f} MB → 子集 {新大小 / 1024:.1f} KB"
          f"（缩小到 {新大小 / 原大小 * 100:.2f}%）")
    print(f"输出：{os.path.relpath(参数.输出, 根目录)}")
    print(f"家族名：{参数.家族名}（请在 assets/theme.json 的字体候选链中使用这个名字）")
    print(f"sha256：{指纹}")
    return 0


if __name__ == "__main__":
    raise SystemExit(主函数())
