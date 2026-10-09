# -*- coding: utf-8 -*-
"""生成《三国州域 · 现代底图对照图》（纯内联 SVG 的单文件 HTML）。

用法：
    python tools/生成州域对照图.py            # 输出到 docs/三国州域对照图.html
    python tools/生成州域对照图.py 输出路径    # 自定义输出路径

设计说明：
1. **数据与渲染分离**：所有地理数据都以「经纬度」形式写在下面的常量里，
   由 投影() 统一换算成 SVG 坐标。改地名、挪边界、加城池都只改数据，不动渲染代码。
   （这正是 docs/路线图.md 周期 3「地图数据化」要走的同一套路子。）
2. **投影**：简单等距圆柱近似 —— x = (经度-73)×19，y = (54-纬度)×23。
   纬度方向刻意拉伸了一点，避免中国地图看起来被压扁。
3. **不依赖任何外部资源**：无图片、无 API、无字体文件、无第三方库（纯标准库）。
4. **司隶与雍州的处理**：原需求中「司隶含陕西渭河平原」与「雍州含关中」互相冲突
   （同一个关中平原被两个州同时覆盖）。历史上：
     - 东汉：关中（京兆尹/左冯翊/右扶风）属**司隶校尉部**；
     - 建安十八年（213）曹操复《禹贡》九州、省司隶，关中改隶**雍州**；
     - 曹魏：司隶（河南/河内/河东/弘农）与雍州（关中+陇东）**并存**。
   本图采**曹魏制**：司隶＝洛阳为中心的中原＋晋南，雍州＝关中＋陇东，两者不重叠。
   理由：与「洛阳为魏都」的时代设定自洽。该说明也印在图上，避免被误认为画错。
"""
import json
import os
import sys

根目录 = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(根目录, "ui"))
sys.path.insert(0, os.path.join(根目录, "src"))

# ══════════════════════════════════════════════════════════════════
#  一、投影与基础数据
# ══════════════════════════════════════════════════════════════════
# 投影一律复用 ui/地图.py（它读 config/投影.json）——不再在本文件里抄一份公式。
# 这是"一套数据、两个渲染器"的前提：换投影时对照图与游戏内地图会一起变，不会各画各的。
import 地图  # noqa: E402


def 投影(经纬):
    """(经度, 纬度) → (x, y)，与游戏内地图完全同一套投影。"""
    return 地图.投影(经纬[0], 经纬[1])


def 路径(点列, 闭合=True):
    """把经纬度点列转成 SVG path 的 d 属性。"""
    指令 = []
    for 序号, 点 in enumerate(点列):
        x, y = 投影(点)
        指令.append(f"{'M' if 序号 == 0 else 'L'}{x:.1f},{y:.1f}")
    if 闭合:
        指令.append("Z")
    return " ".join(指令)


# —— 地图数据：一律从 config/map.json 读取（唯一来源）——
# 游戏内的图形地图（ui/地图.py）读的是同一份数据：一套边界、两个渲染器，改一处即两处生效。
数据路径 = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                     "config", "map.json")
with open(数据路径, encoding="utf-8") as 文件:
    地图数据 = json.load(文件)

中国轮廓 = [tuple(点) for 点 in 地图数据["底图"]["中国轮廓"]]
岛屿 = {名: [tuple(点) for 点 in 点列] for 名, 点列 in 地图数据["底图"]["岛屿"].items()}
内部界线 = 地图数据["底图"]["内部界线"]
州列表 = 地图数据["州"]
注释文字 = 地图数据["注释"]
图例顺序 = [州["名"] for 州 in 州列表]


# ══════════════════════════════════════════════════════════════════
#  三、SVG 生成
# ══════════════════════════════════════════════════════════════════
def 生成州图层():
    片段 = []
    for 州 in 州列表:
        片段.append(
            f'      <path class="prov" d="{路径(州["边界"])}" fill="{州["色"]}">\n'
            f'        <title>{州["悬停"]}</title>\n'
            f'      </path>'
        )
    return "\n".join(片段)


def 生成标注层():
    片段 = []
    for 州 in 州列表:
        x, y = 投影(州["锚点"])
        片段.append(
            f'      <g class="label">\n'
            f'        <text class="l-name" x="{x:.1f}" y="{y:.1f}">{州["名"]}</text>\n'
            f'        <text class="l-cap" x="{x:.1f}" y="{y + 15:.1f}">{州["标注"]}</text>\n'
            f'        <text class="l-now" x="{x:.1f}" y="{y + 28:.1f}">{州["今"]}</text>\n'
            f'      </g>'
        )
    return "\n".join(片段)


def 生成图例():
    左列x, 右列x = 40, 224
    起y, 行距 = 640, 24
    框x, 框y, 框w, 框h = 18, 556, 442, 316
    片段 = [
        f'      <rect x="{框x}" y="{框y}" width="{框w}" height="{框h}" rx="10" '
        f'fill="#fffdf8" stroke="#c9bfa8" stroke-width="1.2" opacity="0.97"/>',
        f'      <text x="{框x + 22}" y="{框y + 30}" class="lg-title">'
        f'图例 · 州域色块（共十三州，不含交州）</text>',
    ]
    for 序号, 州 in enumerate(州列表):
        列x = 左列x if 序号 < 7 else 右列x
        行y = 起y + (序号 if 序号 < 7 else 序号 - 7) * 行距
        片段.append(
            f'      <rect x="{列x}" y="{行y - 9}" width="21" height="12" rx="2.5" '
            f'fill="{州["色"]}" fill-opacity="0.75" stroke="{州["色"]}" stroke-width="1"/>'
        )
        片段.append(
            f'      <text x="{列x + 28}" y="{行y}" class="lg-item">{州["名"]} · {州["治所"]}</text>'
        )
    片段.append(
        f'      <line x1="{框x + 22}" y1="800" x2="{框x + 框w - 22}" y2="800" '
        f'stroke="#d8cfba" stroke-width="1"/>'
    )
    for 序号, 文本 in enumerate(注释文字):
        片段.append(
            f'      <text x="{框x + 22}" y="{816 + 序号 * 14}" class="note">{文本}</text>'
        )
    return "\n".join(片段)




def 生成HTML():
    return f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>三国州域 · 现代底图对照图</title>
<style>
  /* 若日后要换成隶书：把下面 --title-font 换成你的隶书 webfont 即可，
     例如 @font-face {{ font-family:"LiShu"; src:url("lishu.woff2"); }}
     正文与小字建议保留衬线/黑体，隶书小字号可读性较差。 */
  :root {{
    --title-font: "Noto Serif SC", "Source Han Serif SC", "STZhongsong", "SimSun", serif;
    --body-font:  "Noto Sans SC", "Microsoft YaHei", "PingFang SC", sans-serif;
    --paper: #f7f4ec;
    --sea:   #eaf1f6;
    --land:  #f3f0e6;
  }}
  * {{ box-sizing: border-box; }}
  html, body {{
    margin: 0; padding: 0;
    background: var(--paper);
    font-family: var(--body-font);
    color: #2b2b2b;
  }}
  .wrap {{ max-width: 1320px; margin: 0 auto; padding: 26px 20px 46px; }}
  h1 {{
    font-family: var(--title-font);
    font-size: 26px; font-weight: 700; letter-spacing: 3px;
    margin: 0 0 6px; color: #3a2f24;
  }}
  .sub {{ margin: 0 0 4px; font-size: 13px; color: #6b6156; letter-spacing: .5px; }}
  .hint {{ margin: 0 0 10px; font-size: 12.5px; color: #8a7f72; }}
  .stage {{
    background: #fff; border: 1px solid #ddd6c6; border-radius: 12px;
    box-shadow: 0 2px 14px rgba(90, 78, 60, .07);
    padding: 8px; overflow: hidden;
  }}
  svg {{ display: block; width: 100%; height: auto; }}

  /* —— 现代底图 —— */
  .sea    {{ fill: var(--sea); }}
  .land   {{ fill: var(--land); stroke: #9aa4ad; stroke-width: 1.6;
             stroke-dasharray: 6 4; stroke-linejoin: round; }}
  .island {{ fill: var(--land); stroke: #9aa4ad; stroke-width: 1.4;
             stroke-dasharray: 5 3; }}
  .inner  {{ fill: none; stroke: #b9c1c8; stroke-width: 1.3;
             stroke-dasharray: 3 4; stroke-linecap: round; }}

  /* —— 州域色块 —— */
  .prov {{
    fill-opacity: .58;
    stroke: rgba(60, 50, 40, .45);
    stroke-width: 1.1;
    stroke-linejoin: round;
    transition: fill-opacity .16s ease;
    cursor: help;
  }}
  .prov:hover {{ fill-opacity: .88; stroke-width: 1.8; stroke: #3a2f24; }}

  /* —— 标注（用白色描边做「光晕」，保证压在任何色块上都读得清）—— */
  text {{ font-family: var(--title-font); paint-order: stroke; }}
  .l-name {{
    font-size: 16.5px; font-weight: 700; letter-spacing: 2px;
    text-anchor: middle; fill: #241d16;
    stroke: #fffdf7; stroke-width: 3.6; stroke-linejoin: round;
  }}
  .l-cap {{
    font-size: 10.5px; text-anchor: middle; fill: #33302b;
    stroke: #fffdf7; stroke-width: 3;
  }}
  .l-now {{
    font-size: 10px; text-anchor: middle; fill: #5a5348;
    stroke: #fffdf7; stroke-width: 3;
  }}
  .label {{ pointer-events: none; }}

  /* —— 图例与注释 —— */
  .lg-title {{ font-size: 12.5px; font-weight: 700; fill: #3a2f24; letter-spacing: .5px; }}
  .lg-item  {{ font-size: 11px; fill: #33302b; }}
  .note {{ font-family: var(--body-font); font-size: 9.5px; fill: #7b7266; }}
  .west {{ font-family: var(--title-font); font-size: 17px; letter-spacing: 6px;
           fill: #8a7f72; text-anchor: middle; }}
  footer {{ margin-top: 14px; font-size: 12px; color: #8a7f72; line-height: 1.9; }}
  footer code {{ background: #efe9dc; padding: 1px 5px; border-radius: 3px; }}
</style>
</head>
<body>
<div class="wrap">
  <h1>三国州域 · 现代底图对照图</h1>
  <p class="sub">东汉末至曹魏（约 200–265 年）· 十三州（不含交州）· 采曹魏制：司隶与雍州并存</p>
  <p class="hint">鼠标悬停任意色块，可查看州名、治所（含汉末移治）与今地对照。</p>

  <div class="stage">
    <svg viewBox="-30 -30 1250 910" xmlns="http://www.w3.org/2000/svg" role="img"
         aria-label="三国十三州州域与现代中国底图对照图">
      <!-- ① 现代底图：海面 + 简化中国轮廓（虚线代表今国界，仅示意） -->
      <rect class="sea" x="-30" y="-30" width="1250" height="910" rx="8"/>
      <path class="land" d="{路径(中国轮廓)}">
        <title>简化的中国轮廓（示意，非精确国界）</title>
      </path>
{chr(10).join(f'      <path class="island" d="{路径(点列)}"><title>{名}（现代底图；三国时期未设州）</title></path>' for 名, 点列 in 岛屿.items())}
{chr(10).join(f'''      <path class="inner" d="{路径(界["点"], 闭合=False)}">
        <title>{界["名"]}</title>
      </path>''' for 界 in 内部界线)}

      <!-- ② 十三州州域色块 -->
      <g id="provinces">
{生成州图层()}
      </g>

      <!-- ③ 州名 / 治所 / 今地 标注 -->
      <g id="labels">
{生成标注层()}
      </g>

      <!-- ④ 西域标注（凉州以西，不设州） -->
      <text class="west" x="{投影((83.5, 39.8))[0]:.1f}" y="{投影((83.5, 39.8))[1]:.1f}">西域</text>

      <!-- ⑤ 图例 + 考据注释 -->
      <g id="legend">
{生成图例()}
      </g>
    </svg>
  </div>

  <footer>
    数据与渲染分离：本图由 <code>tools/生成州域对照图.py</code> 生成，
    所有边界均以经纬度定义后统一投影，改动边界或地名只需改数据再重新运行脚本。<br>
    底图轮廓为简化多边形近似（无外部图片与 API，纯内联 SVG）；
    州域边界依《中国历史地图集》与《续汉书·郡国志》所列郡国大势勾勒，属示意性绘制。
  </footer>
</div>
</body>
</html>
'''


def 主函数():
    根目录 = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    输出 = sys.argv[1] if len(sys.argv) > 1 else os.path.join(根目录, "docs", "三国州域对照图.html")
    os.makedirs(os.path.dirname(输出), exist_ok=True)
    with open(输出, "w", encoding="utf-8", newline="\n") as 文件:
        文件.write(生成HTML())
    print(f"已生成：{输出}")
    print(f"州数：{len(州列表)}，轮廓点数：{len(中国轮廓)}，岛屿：{len(岛屿)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(主函数())
