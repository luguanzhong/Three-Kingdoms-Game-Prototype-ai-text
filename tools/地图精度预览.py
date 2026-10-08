# -*- coding: utf-8 -*-
"""地图精度预览：把"现有手绘轮廓"与"Natural Earth 真实海岸线 / 河流"并排画出来，供决策对比。

用法：
    python tools/地图精度预览.py                    # 输出 docs/地图精度预览.html 并打印统计
    python tools/地图精度预览.py --容差 0.06         # 调整抽稀容差（度）；越小越精细
    python tools/地图精度预览.py --输出 别处.html

设计说明：
    * **只读不改**：本工具不修改 config/map.json，也不参与游戏运行，纯粹用于"换数据之前先看看差多少"；
    * 数据源为 Natural Earth（**公有领域**），只取**自然地理**图层（海岸线、河流、湖泊），
      **刻意不取国界** —— 三国时期没有现代国界，且各国对边界的画法存在争议，取之无益；
    * 抽稀用 Douglas-Peucker（纯标准库实现），用于把 10 万级的原始点压到游戏可接受的点数；
    * 生成的是单文件 HTML（内联 SVG），浏览器直接打开，可与 docs/三国州域对照图.html 对照着看。
"""
import argparse
import json
import math
import os
import sys
import urllib.request

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
根目录 = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# 与项目一致的投影（等距圆柱近似）
经度基准, 经度系数 = 73.0, 19.0
纬度基准, 纬度系数 = 54.0, 23.0
中国框 = (73.0, 18.0, 136.0, 54.5)          # 经度下限、纬度下限、经度上限、纬度上限

自然地球 = "https://raw.githubusercontent.com/nvkelso/natural-earth-vector/master/geojson/"
图层 = {
    "海岸线": "ne_50m_coastline.geojson",
    "河流": "ne_50m_rivers_lake_centerlines.geojson",
    "湖泊": "ne_50m_lakes.geojson",
}


def 投影(经纬):
    return ((经纬[0] - 经度基准) * 经度系数, (纬度基准 - 经纬[1]) * 纬度系数)


def 取图层(名):
    """下载并缓存到临时目录（避免每次都重下）。"""
    import tempfile
    缓存 = os.path.join(tempfile.gettempdir(), "mapdata_" + 名 + ".geojson")
    路径 = os.path.join(tempfile.gettempdir(), "mapdata_" + 图层[名].replace(".geojson", "") + ".json")
    if os.path.isfile(路径) and os.path.getsize(路径) > 1000:
        with open(路径, encoding="utf-8") as 文件:
            return json.load(文件)
    print(f"  下载 {名} …")
    with urllib.request.urlopen(自然地球 + 图层[名], timeout=120) as 响应:
        数据 = json.loads(响应.read().decode("utf-8"))
    with open(路径, "w", encoding="utf-8") as 文件:
        json.dump(数据, 文件)
    return 数据


def 在图框内(经纬):
    return 中国框[0] <= 经纬[0] <= 中国框[2] and 中国框[1] <= 经纬[1] <= 中国框[3]


def 切段(线):
    """把一条线裁到图框内：返回若干条"框内连续段"。"""
    段们, 当前 = [], []
    for 点 in 线:
        if 在图框内(点):
            当前.append(点)
        elif 当前:
            if len(当前) >= 2:
                段们.append(当前)
            当前 = []
    if len(当前) >= 2:
        段们.append(当前)
    return 段们


def 抽稀(点们, 容差):
    """Douglas-Peucker 抽稀（纯标准库）。"""
    if len(点们) < 3 or 容差 <= 0:
        return 点们
    起, 止 = 点们[0], 点们[-1]
    dx, dy = 止[0] - 起[0], 止[1] - 起[1]
    分母 = math.hypot(dx, dy)
    最远, 最远距 = 0, -1.0
    for i in range(1, len(点们) - 1):
        点 = 点们[i]
        if 分母 == 0:
            距 = math.hypot(点[0] - 起[0], 点[1] - 起[1])
        else:
            距 = abs(dy * 点[0] - dx * 点[1] + 止[0] * 起[1] - 止[1] * 起[0]) / 分母
        if 距 > 最远距:
            最远, 最远距 = i, 距
    if 最远距 > 容差:
        左 = 抽稀(点们[:最远 + 1], 容差)
        右 = 抽稀(点们[最远:], 容差)
        return 左[:-1] + 右
    return [起, 止]


def 取坐标列(几何):
    """支持 LineString / MultiLineString / Polygon / MultiPolygon。"""
    类 = 几何.get("type")
    坐标 = 几何.get("coordinates") or []
    if 类 == "LineString":
        return [坐标]
    if 类 == "MultiLineString":
        return [线 for 线 in 坐标]
    if 类 == "Polygon":
        return [环 for 环 in 坐标]
    if 类 == "MultiPolygon":
        return [环 for 面 in 坐标 for 环 in 面]
    return []


def 整理(数据, 容差, 最少点数=3):
    线们, 原始点数 = [], 0
    for 要素 in 数据.get("features", []):
        for 线 in 取坐标列(要素.get("geometry") or {}):
            原始点数 += len(线)
            点们 = [(float(p[0]), float(p[1])) for p in 线]
            for 段 in 切段(点们):
                简 = 抽稀(段, 容差)
                if len(简) >= 最少点数:
                    线们.append(简)
    return 线们, 原始点数


def 路径(线, 闭合=False):
    指令 = []
    for i, 经纬 in enumerate(线):
        x, y = 投影(经纬)
        指令.append(f"{'M' if i == 0 else 'L'}{x:.1f},{y:.1f}")
    if 闭合:
        指令.append("Z")
    return " ".join(指令)


def 统计点数(线们):
    return sum(len(线) for 线 in 线们)


def 主函数():
    解析 = argparse.ArgumentParser(description="地图精度预览（只读，不改项目数据）")
    解析.add_argument("--输出", default=os.path.join(根目录, "docs", "地图精度预览.html"))
    解析.add_argument("--容差", type=float, default=0.04, help="抽稀容差（度），越小越精细")
    解析.add_argument("--州容差", type=float, default=0.25, help="州界抽稀容差（度）")
    参数 = 解析.parse_args()

    with open(os.path.join(根目录, "config", "map.json"), encoding="utf-8") as 文件:
        现有 = json.load(文件)

    原始轮廓 = [tuple(点) for 点 in 现有["底图"]["中国轮廓"]]
    print(f"现有手绘轮廓：{len(原始轮廓)} 点")

    print("取 Natural Earth 自然地理图层（公有领域；不取国界）：")
    海岸线, 海岸原始 = 整理(取图层("海岸线"), 参数.容差)
    河流, 河流原始 = 整理(取图层("河流"), 参数.容差)
    湖泊, 湖泊原始 = 整理(取图层("湖泊"), 参数.容差)
    print(f"  海岸线：原始 {海岸原始} 点 → 抽稀 {统计点数(海岸线)} 点（{len(海岸线)} 段）")
    print(f"  河流：  原始 {河流原始} 点 → 抽稀 {统计点数(河流)} 点（{len(河流)} 段）")
    print(f"  湖泊：  原始 {湖泊原始} 点 → 抽稀 {统计点数(湖泊)} 点（{len(湖泊)} 段）")

    # 州界（两边用同一份，便于看出"底图变了但州界没动"）
    州界线 = "".join(
        f'      <path d="{路径(抽稀([tuple(p) for p in 州["边界"]] + [tuple(州["边界"][0])],参数.州容差), True)}" '
        f'fill="{州["色"]}" fill-opacity="0.30" stroke="rgba(60,50,40,.5)" stroke-width="1"/>\n'
        for 州 in 现有["州"])

    视图 = "-30 -30 1250 910"
    甲 = f'      <path d="{路径(原始轮廓, True)}" fill="#f2eee2" stroke="#98a2ab" ' \
        f'stroke-width="1.4" stroke-dasharray="6 4"/>\n'
    乙 = ('      <rect x="-30" y="-30" width="1250" height="910" fill="#e6eef4"/>\n'
         + "".join(f'      <path d="{路径(线)}" fill="none" stroke="#9aa4ad" stroke-width="1.1"/>\n'
                 for 线 in 海岸线)
         + "".join(f'      <path d="{路径(线, True)}" fill="#eef2ea" stroke="#9aa4ad" stroke-width="0.8"/>\n'
                 for 线 in 湖泊)
         + "".join(f'      <path d="{路径(线)}" fill="none" stroke="#5f9bc4" stroke-width="0.9"/>\n'
                 for 线 in 河流))

    统计行 = [
        ("中国轮廓点数", f"{len(原始轮廓)}", f"{统计点数(海岸线)}（{len(海岸线)} 段海岸线）"),
        ("水系", "0", f"{统计点数(河流)} 点河流 + {统计点数(湖泊)} 点湖泊"),
        ("州界", f"{sum(len(州['边界']) for 州 in 现有['州'])} 点（未改动）",
         f"{sum(len(州['边界']) for 州 in 现有['州'])} 点（同一份，便于对比）"),
        ("数据来源", "手工估算（本人）", "Natural Earth 50m（公有领域）"),
        ("许可", "无第三方", "公有领域，无需授权（台账登记即可）"),
    ]

    html = f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<title>地图精度预览 · 现有 vs 真实地理数据</title>
<style>
  body {{ margin:0; padding:22px 18px 40px; background:#f7f4ec; color:#2b2b2b;
         font-family:"Microsoft YaHei UI","PingFang SC",sans-serif; }}
  h1 {{ font-size:21px; margin:0 0 6px; letter-spacing:1px; color:#3a2f24; }}
  .sub {{ font-size:13px; color:#6b6156; margin:0 0 16px; line-height:1.8; }}
  .row {{ display:flex; gap:16px; flex-wrap:wrap; }}
  .card {{ flex:1 1 460px; background:#fff; border:1px solid #ddd6c6; border-radius:12px;
          padding:10px; box-shadow:0 2px 12px rgba(90,78,60,.07); }}
  .card h2 {{ font-size:14px; margin:2px 0 8px; color:#4a4036; }}
  svg {{ display:block; width:100%; height:auto; }}
  table {{ border-collapse:collapse; margin-top:18px; font-size:12.5px;
          background:#fff; border:1px solid #ddd6c6; border-radius:10px; overflow:hidden; }}
  th, td {{ padding:7px 12px; border-bottom:1px solid #eee7d8; text-align:left; }}
  th {{ background:#f0ebdd; font-weight:700; color:#4a4036; }}
  .warn {{ margin-top:14px; font-size:12.5px; color:#8c3b3b; line-height:1.9;
          background:#fdf6f2; border:1px solid #e8cfc4; border-radius:10px; padding:10px 14px; }}
  code {{ background:#efe9dc; padding:1px 5px; border-radius:3px; }}
</style>
</head>
<body>
  <h1>地图精度预览 · 现有手绘轮廓 vs 真实地理数据</h1>
  <p class="sub">
    左边是当前游戏里在用的轮廓（89 点手工近似）；右边换成
    <b>Natural Earth 50m</b> 的真实海岸线、河流与湖泊，抽稀容差 {参数.容差}°。
    两侧<b>叠的是同一份州界</b>，所以你能直接看出"只换底图、不动州郡"的效果。
  </p>
  <div class="row">
    <div class="card">
      <h2>① 现状：89 点手工近似（海岸线是"直尺画的"）</h2>
      <svg viewBox="{视图}">
        <rect x="-30" y="-30" width="1250" height="910" fill="#e6eef4"/>
{甲}{州界线}      </svg>
    </div>
    <div class="card">
      <h2>② 真实数据：Natural Earth 50m 海岸线 + 河流 + 湖泊（公有领域）</h2>
      <svg viewBox="{视图}">
{乙}{州界线}      </svg>
    </div>
  </div>

  <table>
    <tr><th>项目</th><th>① 现状</th><th>② 真实数据</th></tr>
    {"".join(f"<tr><td>{a}</td><td>{b}</td><td>{c}</td></tr>" for a, b, c in 统计行)}
  </table>

  <div class="warn">
    <b>两条必须要说清的事：</b><br>
    1. 本预览<b>只取自然地理</b>（海岸线/河流/湖泊），<b>刻意没有取国界</b> ——
       三国时期不存在现代国界，且 Natural Earth 对边界的画法与中国官方标准地图不一致，
       取之无益。换句话说：这张图提升的是"地理真实感"，不涉及边界表述。<br>
    2. 本文件是<b>决策用的对比图</b>，<b>没有改动 <code>config/map.json</code>，也没有改动游戏</b>。
       你决定之后，我才把数据接进 <code>map.json</code>（并登记台账、更新测试）。
  </div>
</body>
</html>
'''
    os.makedirs(os.path.dirname(参数.输出), exist_ok=True)
    with open(参数.输出, "w", encoding="utf-8", newline="\n") as 文件:
        文件.write(html)
    体积 = os.path.getsize(参数.输出) / 1024
    print(f"\n已生成对比预览：{os.path.relpath(参数.输出, 根目录)}（{体积:.0f} KB）")
    print("提示：这只是预览，config/map.json 与游戏均未改动。")
    return 0


if __name__ == "__main__":
    raise SystemExit(主函数())
