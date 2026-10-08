# -*- coding: utf-8 -*-
"""资产台账工具（溯源 A / D 层的命令行入口）。

用法：
    python tools/资产台账.py                  # 打印台账并校验（提交前跑一次）
    python tools/资产台账.py 校验              # 同上（显式）
    python tools/资产台账.py 生成文档           # 重新生成 docs/资产来源与许可.md
    python tools/资产台账.py 填校验值           # 重新计算所有资产的 sha256 并写回台账
    python tools/资产台账.py 列出               # 只列出条目（简洁表格）

为什么要有"填校验值"：替换资产（例如换上你写的隶书）之后，文件指纹变了，
此时必须更新台账，否则 `tests/test_assets.py` 会因为"校验值不一致"判红 —— 这是**故意设计的**
（它保证"台账里记的那份文件"就是"仓库里实际那份"，防止有人悄悄换了文件不更新记录）。
"""
import hashlib
import json
import os
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
根目录 = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(根目录, "src"))
sys.path.insert(0, os.path.join(根目录, "ui"))

import 资产  # noqa: E402


def 路径们():
    return os.path.join(资产.资产根目录(), "manifest.json")


def 打印台账():
    台账, 错误 = 资产.载入台账()
    if 错误:
        print("✗ " + "；".join(错误))
        return 1
    条目们 = 台账.get("资产") or []
    print(f"资产台账（共 {len(条目们)} 条）")
    print("=" * 96)
    print(f"{'编号':<10}{'类别':<6}{'名称':<26}{'状态':<6}{'归属':<8}{'许可':<14}{'体积':<10}")
    print("-" * 96)
    for 条 in 条目们:
        print(f"{条.get('编号', ''):<10}{条.get('类别', ''):<6}{条.get('名称', '')[:24]:<26}"
              f"{条.get('状态', ''):<6}{条.get('归属', ''):<8}{条.get('许可', ''):<14}"
              f"{条.get('体积', ''):<10}")
    print("-" * 96)
    统计 = 资产.资产统计()
    print(f"按状态：{统计['按状态']}　按归属：{统计['按归属']}")
    待替换 = [条 for 条 in 条目们 if 条.get("状态") in ("占位", "过渡")]
    if 待替换:
        print("\n待替换（仍是临时的，别忘了）：")
        for 条 in 待替换:
            print(f"  · {条.get('名称')}　→ {条.get('替换计划', '（未写替换计划）')}")
    return 0


def 校验():
    错误 = 资产.校验台账()
    if 错误:
        print("✗ 台账校验未通过：")
        for 项 in 错误:
            print("   · " + 项)
        return 1
    print("✓ 台账校验通过：字段齐备、文件存在、许可随附、校验值一致、无未登记文件")
    return 0


def 填校验值():
    台账, 错误 = 资产.载入台账()
    if 错误:
        print("✗ " + "；".join(错误))
        return 1
    改动 = 0
    for 条 in 台账.get("资产", []):
        文件 = 条.get("文件")
        if not 文件:
            continue
        全路径 = os.path.join(资产.资产根目录(), 文件)
        if not os.path.isfile(全路径):
            print(f"  ⚠ 文件不存在，跳过：{文件}")
            continue
        with open(全路径, "rb") as 句柄:
            指纹 = "sha256:" + hashlib.sha256(句柄.read()).hexdigest()
        体积 = f"{os.path.getsize(全路径) / 1024:.1f} KB"
        if 条.get("校验") != 指纹 or 条.get("体积") != 体积:
            条["校验"], 条["体积"] = 指纹, 体积
            改动 += 1
            print(f"  更新 {条.get('名称')}：{指纹[:22]}…　{体积}")
    with open(路径们(), "w", encoding="utf-8", newline="\n") as 文件句柄:
        json.dump(台账, 文件句柄, ensure_ascii=False, indent=1)
    print(f"✓ 已写回台账（更新 {改动} 条）")
    return 0


def 生成文档():
    台账, 错误 = 资产.载入台账()
    if 错误:
        print("✗ " + "；".join(错误))
        return 1
    行 = ["# 资产来源与许可", "",
         "> **本文件由 `python tools/资产台账.py 生成文档` 自动生成，请勿手改**；",
         "> 要改内容请改 `assets/manifest.json` 后重新生成。",
         "> 分区与溯源机制见 [区域划分与溯源.md](区域划分与溯源.md)。", "",
         "## 状态含义", ""]
    for 键, 值 in 台账.get("状态含义", {}).items():
        行.append(f"- **{键}**：{值}")
    行 += ["", "## 归属含义", ""]
    for 键, 值 in 台账.get("归属含义", {}).items():
        行.append(f"- **{键}**：{值}")
    行 += ["", "## 资产清单", "",
          "| 编号 | 区域 | 类别 | 名称 | 作者 / 来源 | 许可 | 获取日期 | 状态 | 归属 | 校验值 |",
          "| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |"]
    for 条 in 台账.get("资产", []):
        来源 = f"[{条.get('原作者', '')}]({条.get('来源', '')})" if str(条.get("来源", "")).startswith("http") else 条.get("原作者", "")
        许可 = 条.get("许可", "")
        if 条.get("许可文件"):
            许可 += f"<br>（[许可全文](../assets/{条['许可文件']})）"
        指纹 = str(条.get("校验", ""))
        行.append(f"| {条.get('编号', '')} | {条.get('区域', '')} | {条.get('类别', '')} | "
                 f"{条.get('名称', '')} | {来源} | {许可} | {条.get('获取日期', '')} | "
                 f"**{条.get('状态', '')}** | {条.get('归属', '')} | `{指纹[:19]}…` |")
    行 += ["", "## 逐条说明", ""]
    for 条 in 台账.get("资产", []):
        行 += [f"### {条.get('编号', '')}　{条.get('名称', '')}", "",
             f"- **文件**：`assets/{条.get('文件', '')}`（{条.get('体积', '?')}）",
             f"- **来源**：{条.get('来源', '')}",
             f"- **原作者**：{条.get('原作者', '')}",
             f"- **许可**：{条.get('许可', '')}",
             f"- **校验值**：`{条.get('校验', '')}`",
             f"- **状态 / 归属**：{条.get('状态', '')} / {条.get('归属', '')}",
             f"- **说明**：{条.get('说明', '')}",
             f"- **替换计划**：{条.get('替换计划', '（无）')}", ""]
    行 += ["---", "",
          "<p align=\"center\"><sub>由 tools/资产台账.py 生成　·　"
          "改资产请先改 assets/manifest.json 再重新生成本文件</sub></p>", ""]
    输出 = os.path.join(根目录, "docs", "资产来源与许可.md")
    with open(输出, "w", encoding="utf-8", newline="\n") as 文件句柄:
        文件句柄.write("\n".join(行))
    print(f"✓ 已生成 {os.path.relpath(输出, 根目录)}（{len(台账.get('资产', []))} 条资产）")
    return 0


def 主函数():
    参数 = sys.argv[1] if len(sys.argv) > 1 else "校验"
    if 参数 in ("校验",):
        if 打印台账() != 0:
            return 1
        print()
        return 校验()
    if 参数 == "列出":
        return 打印台账()
    if 参数 == "填校验值":
        return 填校验值()
    if 参数 in ("生成文档", "文档"):
        return 生成文档()
    print(__doc__)
    return 2


if __name__ == "__main__":
    raise SystemExit(主函数())
