# -*- coding: utf-8 -*-
"""郡界骨架生成器：把「郡治 + 属县」的点位算成可视的郡界骨架。

用法：
    python tools/郡界骨架生成.py                 # 生成 docs/郡界骨架预览.html
    python tools/郡界骨架生成.py --容差 0.08      # 海岸线抽稀容差（度）
    python tools/郡界骨架生成.py --仅郡治          # 只用郡治点位（对比用；默认连属县一起用）

数据来源（都是本仓库自己的数据，无第三方几何数据）：
    config/古今地名对照.json  → 每个郡的治所坐标（19 郡）
    config/郡属县.json        → 首批 6 郡的属县与参照点（约 90 县）

它做什么、不做什么（**务必看清，避免把骨架当考据边界用**）：
    ✅ 做：以每个郡治与属县为种子点，用**泰森多边形**算出"离最近的点归谁"的骨架，
        叠在 Natural Earth 真实海岸线上；同一郡的所有格子用同一颜色、只留细内边，
        因此看上去是一整块郡域，细线能看到"县级细分"。
    ❌ 不做：它不是考据出来的历史边界。泰森多边形**只知道距离**，不知道史料记载的属县归属，
        更不知道山脉与河流。它只是**一版可讨论、可修改的底稿**。
    进化路线：① 补更多属县点位（边数随之增加）② 用真实县界替换几何骨架 ③ 关键段吸附到山脊/河道。
"""
import argparse
import json
import math
import os
import sys
import urllib.request

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
根目录 = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(根目录, "ui"))
import 地图  # noqa: E402  （复用同一套投影）

自然地球 = ("https://raw.githubusercontent.com/nvkelso/natural-earth-vector/master/geojson/"
        "ne_50m_land.geojson")

州色 = {
    "司隶": "#e57373", "豫州": "#f39c12", "冀州": "#8fa8b8", "兖州": "#e6d5a8",
    "徐州": "#a1887f", "青州": "#a5c9a5", "荆州": "#4fa3c7", "扬州": "#5c6bc0",
    "益州": "#4caf50", "凉州": "#9e8fb2", "雍州": "#b0353a", "并州": "#6b8e6b",
    "幽州": "#3d6188",
}
骨架框 = (99.0, 19.5, 126.5, 38.5)


# ══════════════════════════════════════════════════════════════════
#  一、泰森多边形（半平面裁剪，纯标准库）
# ══════════════════════════════════════════════════════════════════
def 裁剪半平面(多边形, 种子, 对手):
    mx, my = (种子[0] + 对手[0]) / 2.0, (种子[1] + 对手[1]) / 2.0
    dx, dy = 对手[0] - 种子[0], 对手[1] - 种子[1]

    def 在内(点):
        return (点[0] - mx) * dx + (点[1] - my) * dy <= 0

    def 交点(甲, 乙):
        分母 = (乙[0] - 甲[0]) * dx + (乙[1] - 甲[1]) * dy
        if abs(分母) < 1e-15:
            return 甲
        t = -(((甲[0] - mx) * dx + (甲[1] - my) * dy) / 分母)
        t = max(0.0, min(1.0, t))
        return (甲[0] + t * (乙[0] - 甲[0]), 甲[1] + t * (乙[1] - 甲[1]))

    结果 = []
    for i in range(len(多边形)):
        当前, 下一个 = 多边形[i], 多边形[(i + 1) % len(多边形)]
        当前内, 下一个内 = 在内(当前), 在内(下一个)
        if 当前内:
            结果.append(当前)
        if 当前内 != 下一个内:
            结果.append(交点(当前, 下一个))
    return 结果


def 泰森格(种子们, 框):
    外框 = [(框[0], 框[1]), (框[2], 框[1]), (框[2], 框[3]), (框[0], 框[3])]
    格子 = []
    for i, 种子 in enumerate(种子们):
        多边形 = list(外框)
        for j, 对手 in enumerate(种子们):
            if i != j and 多边形:
                多边形 = 裁剪半平面(多边形, 种子, 对手)
        格子.append(多边形)
    return 格子


def 去重(点们, 间隔=1e-9):
    结果 = []
    for 点 in 点们:
        if not 结果 or math.hypot(点[0] - 结果[-1][0], 点[1] - 结果[-1][1]) > 间隔:
            结果.append(点)
    return 结果


# ══════════════════════════════════════════════════════════════════
#  二、数据：郡治 + 属县
# ══════════════════════════════════════════════════════════════════
def 载入点位(仅郡治=False):
    """返回 (点列表, 统计)。每个点：{郡, 州, 县, 坐标, 置信度, 是治所}"""
    点位 = []
    对照 = json.load(open(os.path.join(根目录, "config", "古今地名对照.json"), encoding="utf-8"))
    属县路径 = os.path.join(根目录, "config", "郡属县.json")
    属县 = (json.load(open(属县路径, encoding="utf-8")).get("郡属县", {})
          if os.path.isfile(属县路径) else {})

    for 条 in 对照["条目"]:
        郡 = 条["郡"]
        if not 仅郡治 and 郡 in 属县:
            # 有属县数据的郡：用属县点位（其中治所所在县会自然落在郡治附近）
            for 县 in 属县[郡]:
                点位.append({"郡": 郡, "州": 条["州"], "县": 县["县"],
                           "坐标": tuple(县["坐标"]), "置信度": 县["置信度"],
                           "是治所": 县["县"] == 条["治所"] or 县["县"] in 条["治所"]})
        else:
            点位.append({"郡": 郡, "州": 条["州"], "县": 条["治所"],
                       "坐标": tuple(条["治所坐标"]), "置信度": 条["置信度"],
                       "是治所": True})
    统计 = {"点总数": len(点位),
          "含属县的郡": len({p["郡"] for p in 点位 if not p["是治所"]}),
          "按置信度": {}}
    for 点 in 点位:
        统计["按置信度"][点["置信度"]] = 统计["按置信度"].get(点["置信度"], 0) + 1
    return 点位, 统计


# ══════════════════════════════════════════════════════════════════
#  三、底图
# ══════════════════════════════════════════════════════════════════
def 取陆地():
    import tempfile
    缓存 = os.path.join(tempfile.gettempdir(), "mapdata_land50.json")
    if os.path.isfile(缓存) and os.path.getsize(缓存) > 1000:
        with open(缓存, encoding="utf-8") as 文件:
            return json.load(文件)
    print("  下载陆地轮廓（Natural Earth 50m，公有领域）…")
    with urllib.request.urlopen(自然地球, timeout=120) as 响应:
        数据 = json.loads(响应.read().decode("utf-8"))
    with open(缓存, "w", encoding="utf-8") as 文件:
        json.dump(数据, 文件)
    return 数据


def 抽稀(点们, 容差):
    if len(点们) < 3 or 容差 <= 0:
        return 点们
    起, 止 = 点们[0], 点们[-1]
    dx, dy = 止[0] - 起[0], 止[1] - 起[1]
    分母 = math.hypot(dx, dy)
    最远, 最远距 = 0, -1.0
    for i in range(1, len(点们) - 1):
        点 = 点们[i]
        距 = (math.hypot(点[0] - 起[0], 点[1] - 起[1]) if 分母 == 0
              else abs(dy * 点[0] - dx * 点[1] + 止[0] * 起[1] - 止[1] * 起[0]) / 分母)
        if 距 > 最远距:
            最远, 最远距 = i, 距
    if 最远距 > 容差:
        return 抽稀(点们[:最远 + 1], 容差)[:-1] + 抽稀(点们[最远:], 容差)
    return [起, 止]


def 陆地段们(数据, 容差):
    框 = 骨架框
    段们 = []
    for 要素 in 数据.get("features", []):
        几何 = 要素.get("geometry") or {}
        类 = 几何.get("type")
        坐标 = 几何.get("coordinates") or []
        面们 = ([坐标] if 类 == "Polygon" else 坐标) if 类 in ("Polygon", "MultiPolygon") else []
        for 面 in 面们:
            for 环 in 面:
                点们 = [(float(p[0]), float(p[1])) for p in 环]
                if not any(框[0] - 2 <= x <= 框[2] + 2 and 框[1] - 2 <= y <= 框[3] + 2
                           for x, y in 点们):
                    continue
                段们.append(抽稀(点们, 容差))
    return 段们


def 路径(点列, 闭合=True):
    指令 = []
    for i, 经纬 in enumerate(点列):
        x, y = 地图.投影(经纬[0], 经纬[1])
        指令.append(f"{'M' if i == 0 else 'L'}{x:.1f},{y:.1f}")
    if 闭合:
        指令.append("Z")
    return " ".join(指令)


def 导出骨架数据(有效, 点位, 输出路径):
    """把骨架固化成 config/郡界骨架.json，供游戏直接渲染（游戏不做几何计算）。"""
    按郡 = {}
    for 点, 格 in 有效:
        条 = 按郡.setdefault(点["郡"], {"郡": 点["郡"], "州": 点["州"], "格": [], "县": []})
        条["格"].append([[round(x, 4), round(y, 4)] for x, y in 格])
    对照 = json.load(open(os.path.join(根目录, "config", "古今地名对照.json"), encoding="utf-8"))
    索引 = {条["郡"]: 条 for 条 in 对照["条目"]}
    for 点 in 点位:
        条 = 按郡.get(点["郡"])
        if 条 is None:
            continue
        条["县"].append({"县": 点["县"], "置信度": 点["置信度"],
                       "坐标": [round(点["坐标"][0], 4), round(点["坐标"][1], 4)],
                       "是治所": 点["是治所"]})
    for 郡名, 条 in 按郡.items():
        源 = 索引.get(郡名, {})
        条["治所"] = 源.get("治所", "")
        条["治所今地"] = 源.get("治所今地", "")
        条["整体置信度"] = 源.get("置信度", "中")
        条["交界带今地"] = 源.get("交界带今地", "")
        条["待核"] = 源.get("待核", [])
    顺序 = sorted(按郡.values(), key=lambda 条: (条["州"], 条["郡"]))
    置信统计 = {}
    for 条 in 顺序:
        for 县 in 条["县"]:
            置信统计[县["置信度"]] = 置信统计.get(县["置信度"], 0) + 1
    数据 = {
        "说明": "郡界几何骨架：由「郡治 + 属县」点位算出的泰森多边形，供游戏地图渲染。",
        "警告": ("**这不是考据边界**。泰森多边形只知道\"离哪个点位更近\"，"
               "不知道史料记载的属县归属，也不知道山脉与河流。它只是便于讨论与修改的底稿；"
               "正式边界需以属县考据、真实县界或手绘定稿替换。"),
        "生成方式": ("tools/郡界骨架生成.py（半平面裁剪实现的泰森多边形；"
                 "点位来自 config/古今地名对照.json 与 config/郡属县.json）"),
        "点数": len(点位),
        "郡数": len(顺序),
        "县置信度统计": 置信统计,
        "郡": 顺序,
    }
    with open(输出路径, "w", encoding="utf-8", newline="\n") as 文件:
        json.dump(数据, 文件, ensure_ascii=False, indent=1)
    print(f"已导出骨架数据：{os.path.relpath(输出路径, 根目录)}"
          f"（{os.path.getsize(输出路径) / 1024:.0f} KB，{len(顺序)} 郡）")
    return 数据


def 主函数():
    解析 = argparse.ArgumentParser(description="生成郡界几何骨架预览（只读，不改游戏数据）")
    解析.add_argument("--容差", type=float, default=0.05)
    解析.add_argument("--仅郡治", action="store_true", help="只用郡治点位（用于对比：点少则边少）")
    解析.add_argument("--导出数据", nargs="?", const=os.path.join(根目录, "config", "郡界骨架.json"),
                    help="把骨架固化成 JSON 供游戏渲染（默认写 config/郡界骨架.json）")
    解析.add_argument("--输出", default=os.path.join(根目录, "docs", "郡界骨架预览.html"))
    参数 = 解析.parse_args()

    点位, 统计 = 载入点位(参数.仅郡治)
    print(f"点位：共 {统计['点总数']} 个（含属县点位的郡 {统计['含属县的郡']} 个）")
    print(f"  按置信度：{统计['按置信度']}")

    种子们 = [p["坐标"] for p in 点位]
    格子们 = [去重(格) for 格 in 泰森格(种子们, 骨架框)]
    有效 = [(点, 格) for 点, 格 in zip(点位, 格子们) if len(格) >= 3]
    print(f"泰森多边形：{len(有效)} 个有效格子")
    平均边数 = sum(len(格) for _, 格 in 有效) / max(len(有效), 1)
    print(f"平均边数：{平均边数:.1f}")
    print("  ※ 注意：泰森多边形每个格子的边数平均恒为 6 左右，**加点不会让格子边数变多**；")
    print("     加点的作用是让格子变小 → 郡界由更多小段拼成 → 边界更曲折、细节更多。")

    陆地段们_ = 陆地段们(取陆地(), 参数.容差)
    print(f"陆地轮廓：{len(陆地段们_)} 段 / {sum(len(s) for s in 陆地段们_)} 点")
    陆地路径文本 = "".join(f"{路径(段)} " for 段 in 陆地段们_)

    # 格子：同郡同色、细内边（内边体现"县级细分"）
    格片段 = []
    for 点, 格 in 有效:
        色 = 州色.get(点["州"], "#999999")
        中文说明 = (f'{点["郡"]}·{点["县"]}'
                  + ("（治所）" if 点["是治所"] else "")
                  + f'｜置信度 {点["置信度"]}')
        格片段.append(
            f'      <path d="{路径(格)}" fill="{色}" fill-opacity="0.42" '
            f'stroke="rgba(255,255,255,.55)" stroke-width="0.5">'
            f'<title>{中文说明}</title></path>')
    # 治所标注与点
    治所片段 = []
    for 点 in 点位:
        if not 点["是治所"]:
            continue
        x, y = 地图.投影(*点["坐标"])
        治所片段.append(
            f'      <circle cx="{x:.1f}" cy="{y:.1f}" r="5" fill="#fffdf8" '
            f'stroke="#2b2620" stroke-width="1.8"/>'
            f'<text x="{x + 9:.1f}" y="{y + 5:.1f}" font-size="14" fill="#241f18" '
            f'stroke="#fffdf7" stroke-width="3.4" paint-order="stroke" '
            f'font-family="Microsoft YaHei UI, sans-serif">{点["郡"]}</text>')
    # 属县小点
    属县片段 = []
    for 点 in 点位:
        if 点["是治所"]:
            continue
        x, y = 地图.投影(*点["坐标"])
        色 = {"高": "#2f6b3f", "中": "#a06a1f", "存疑": "#b0353a"}[点["置信度"]]
        属县片段.append(
            f'      <circle cx="{x:.1f}" cy="{y:.1f}" r="2.6" fill="{色}" '
            f'stroke="#fff" stroke-width="0.8"><title>{点["郡"]}·{点["县"]}'
            f'（{点["置信度"]}）</title></circle>')

    按郡 = {}
    for 点, _格 in 有效:
        按郡.setdefault(点["郡"], 0)
        按郡[点["郡"]] += 1
    行们 = "".join(
        f"<tr><td>{next(p['州'] for p in 点位 if p['郡'] == 郡)}</td>"
        f"<td>{郡}</td><td>{数}</td></tr>"
        for 郡, 数 in sorted(按郡.items(), key=lambda x: -x[1]))

    html = f'''<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8">
<title>郡界骨架预览（属县点位版 · 几何推断）</title>
<style>
 body {{ margin:0; padding:20px 16px 40px; background:#f7f4ec; color:#2b2b2b;
        font-family:"Microsoft YaHei UI","PingFang SC",sans-serif; }}
 h1 {{ font-size:20px; margin:0 0 6px; color:#3a2f24; }}
 .sub {{ font-size:13px; color:#6b6156; line-height:1.9; margin:0 0 12px; }}
 .warn {{ background:#fdf6f2; border:1px solid #e8cfc4; border-radius:10px;
         padding:10px 14px; font-size:12.5px; color:#8c3b3b; line-height:1.9; margin:0 0 12px; }}
 .ok {{ background:#f2f8f2; border:1px solid #cfe0cf; border-radius:10px;
       padding:10px 14px; font-size:12.5px; color:#2f6b3f; line-height:1.9; margin:0 0 12px; }}
 .card {{ background:#fff; border:1px solid #ddd6c6; border-radius:12px; padding:10px;
         box-shadow:0 2px 12px rgba(90,78,60,.07); }}
 svg {{ display:block; width:100%; height:auto; }}
 table {{ border-collapse:collapse; margin-top:16px; font-size:12.5px; background:#fff;
         border:1px solid #ddd6c6; border-radius:10px; overflow:hidden; width:100%; }}
 th, td {{ padding:6px 12px; border-bottom:1px solid #eee7d8; text-align:left; }}
 th {{ background:#f0ebdd; color:#4a4036; }}
 code {{ background:#efe9dc; padding:1px 5px; border-radius:3px; }}
</style></head><body>
 <h1>郡界骨架预览 <span style="font-size:13px;color:#8c3b3b">（{"只用郡治" if 参数.仅郡治 else "郡治＋属县"}点位 · 几何推断）</span></h1>
 <p class="sub">
   做法：每个<b>郡治与属县</b>各是一个种子点，用<b>泰森多边形</b>算出"离最近的点归谁"；
   同一郡的格子用同一颜色，因此看上去是一整块郡域，细白线是<b>县级细分</b>。
   底图为 Natural Earth 真实海岸线（公有领域），裁剪到陆地内。
 </p>
 <div class="ok">
   <b>对比用：</b>用 <code>python tools/郡界骨架生成.py --仅郡治</code> 可生成"只用郡治"的版本 ——
   那版平均每个格子只有 5~7 条边，正是你说"就只是一些多边形"的样子。
   本版用上了 <b>{统计["点总数"]}</b> 个点位，郡界由<b>更多小段</b>拼成，曲折度明显提升。（注意：泰森多边形每个格子的边数平均恒为 6 左右，<b>加点不会让格子边数变多</b>，而是让格子变小、边界更细碎。）
 </div>
 <div class="warn">
   <b>它仍然不是考据边界。</b>泰森多边形只知道"离哪个点更近"，
   并不知道史料记载的属县归属，也不知道山脉与河流。
   · 属县点：<span style="color:#2f6b3f">绿=置信度高</span>　
   <span style="color:#a06a1f">橙=中</span>　<span style="color:#b0353a">红=存疑（不得用于定界）</span><br>
   进化路线：① 补更多属县点位 ② 用真实县界替换几何骨架 ③ 关键段吸附到山脊与河道。
 </div>
 <div class="card">
   <svg viewBox="-30 -30 1250 910" xmlns="http://www.w3.org/2000/svg">
     <rect x="-30" y="-30" width="1250" height="910" fill="#e6eef4"/>
     <clipPath id="陆地裁切"><path d="{陆地路径文本}"/></clipPath>
     <g clip-path="url(#陆地裁切)">
{chr(10).join(格片段)}
     </g>
     <path d="{陆地路径文本}" fill="none" stroke="#8b959e" stroke-width="1.3"/>
{chr(10).join(属县片段)}
{chr(10).join(治所片段)}
   </svg>
 </div>
 <table>
   <tr><th>州</th><th>郡</th><th>本版点位数（治所＋属县）</th></tr>
   {行们}
 </table>
</body></html>
'''
    os.makedirs(os.path.dirname(参数.输出), exist_ok=True)
    with open(参数.输出, "w", encoding="utf-8", newline="\n") as 文件:
        文件.write(html)
    print(f"\n已生成：{os.path.relpath(参数.输出, 根目录)}"
          f"（{os.path.getsize(参数.输出) / 1024:.0f} KB）")
    if 参数.导出数据:
        导出骨架数据(有效, 点位, 参数.导出数据)
    print("提醒：几何骨架，非考据边界；config/map.json 未改动。")
    return 0


if __name__ == "__main__":
    raise SystemExit(主函数())
