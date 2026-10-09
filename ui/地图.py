# -*- coding: utf-8 -*-
"""游戏内图形地图（tkinter Canvas）：读取 config/map.json，可缩放、可平移、城池可点。

═══════════════════════════════════════════════════════════════════
【设计要点】
1. **数据与渲染分离**：全部地理数据（中国轮廓、十三州边界、十个城池经纬度）都在
   `config/map.json` 里，本文件只负责「把经纬度投影成画布坐标并画出来」。
   同一份数据还被 tools/生成州域对照图.py 用来生成 docs/三国州域对照图.html——
   一套边界、两个渲染器，改一处即两处生效。
2. **几何随缩放、符号不随缩放**：州界与轮廓按缩放变化，而城池圆点、文字标签保持**固定屏幕尺寸**，
   这样放到最大或缩到最小时，城池与数字都始终看得清（地图软件的通行做法）。
3. **零第三方依赖**：只用标准库（json / os / tkinter）。
4. **不碰游戏状态**：本控件只"读"局面快照并渲染；城池点击只是把城名回调出去，
   由主界面决定弹什么菜单 —— 规则仍然全在引擎里。

【配色】tkinter 的画布多边形不支持透明度，因此州色与陆地色**预先按比例混合**成实色
（比 stipple 网点更好看、也没有网点瑕疵）。
"""
import json
import math
import os
import tkinter as tk

import 资产  # noqa: E402  （同目录：配色与字体一律经它读取）


# ══════════════════════════════════════════════════════════════════
#  投影：兰勃特等角圆锥（与官方 1:400万《中国全图》同一类投影）
# ══════════════════════════════════════════════════════════════════
# 【为什么从等距圆柱改成圆锥】
# 等距圆柱（x∝经度、y∝纬度）画中国会把北部拉宽、南部压扁；官方标准地图用的是圆锥投影。
# 两张图叠在一起时，等距圆柱的误差在中国西部与东北可达数十公里 —— 底图铺在下面、
# 州郡界叠在上面时就会明显错位。换成同一类投影后两者才对得齐。
#
# 【公式】球面兰勃特等角圆锥（丢掉常数因子，只保留形状）：
#     t(φ) = tan(π/4 + φ/2)
#     u(φ) = t(φ)^(-n)                        # 顶点到该纬线的"半径"
#     θ    = n · (λ - λ₀)                      # 经度按圆锥常数放大成极角
#     世界x = 缩放 · u · sin θ
#     世界y = 缩放 · (u(φ₀) - u · cos θ)        # y 轴向下为正，φ₀ 处为 0
# 逆变换是闭式的（不需要迭代），因此"屏幕 → 经纬"同样精确：
#     θ = atan2(X, Y)，u = hypot(X, Y)，λ = λ₀ + θ/n，φ = 2·atan(u^(-1/n)) - π/2
#
# 参数全部来自 config/投影.json —— 本文件不写死任何数字（源码里只留一份兜底默认值，
# 与配置文件一致，防止配置文件缺失时地图整个消失）。
默认投影参数 = {"中央经线": 105.0, "圆锥常数": 0.5911395, "参考纬度": 36.0, "缩放": 2800.0}


def 配置路径(文件名):
    """config/ 下某个文件的绝对路径（源码运行 / 打包 exe 都成立）。"""
    try:
        import config_loader
        return os.path.join(config_loader.项目根目录, "config", 文件名)
    except Exception:
        return os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                            "config", 文件名)


def 载入投影参数(路径=None):
    """读 config/投影.json；文件缺失或字段非法时退到内置默认值并说明原因。"""
    路径 = 路径 or 配置路径("投影.json")
    参数 = dict(默认投影参数)
    问题 = []
    if not os.path.isfile(路径):
        return 参数, [f"投影参数文件不存在：{路径}（已退到内置默认投影）"]
    try:
        with open(路径, encoding="utf-8") as 文件:
            原始 = json.load(文件)
    except (OSError, json.JSONDecodeError) as 异常:
        return 参数, [f"投影参数文件读不了：{异常!r}（已退到内置默认投影）"]
    for 键 in ("中央经线", "圆锥常数", "参考纬度", "缩放"):
        值 = 原始.get(键)
        if isinstance(值, (int, float)) and not isinstance(值, bool):
            参数[键] = float(值)
        else:
            问题.append(f"投影参数「{键}」缺失或不是数字，已用默认值 {默认投影参数[键]}")
    if not 0.0 < 参数["圆锥常数"] <= 1.0:
        问题.append(f"圆锥常数 {参数['圆锥常数']} 不在 (0, 1] 内，已用默认值")
        参数["圆锥常数"] = 默认投影参数["圆锥常数"]
    if 参数["缩放"] <= 0:
        问题.append("缩放必须为正，已用默认值")
        参数["缩放"] = 默认投影参数["缩放"]
    参数["来源"] = 原始.get("拟合状态") or "未标注"
    return 参数, 问题


投影参数, 投影警告 = 载入投影参数()
中央经线 = 投影参数["中央经线"]
圆锥常数 = 投影参数["圆锥常数"]
参考纬度 = 投影参数["参考纬度"]
缩放 = 投影参数["缩放"]


def _半径(纬度):
    """顶点到该纬线的半径 u(φ) = tan(π/4+φ/2)^(-n)。"""
    return math.tan(math.pi / 4 + math.radians(纬度) / 2) ** (-圆锥常数)


_参考半径 = _半径(参考纬度)


def 投影(经度, 纬度):
    """(经度, 纬度) → 世界像素坐标（与 tools/生成州域对照图.py 同一套投影，两图可对齐）。

    y 轴向下为正（与画布一致），而圆锥投影的天然 y 是向北为正，所以这里取了负号。
    """
    极角 = 圆锥常数 * math.radians(经度 - 中央经线)
    半径 = _半径(纬度)
    return (缩放 * 半径 * math.sin(极角),
            缩放 * (半径 * math.cos(极角) - _参考半径))


def 逆投影(世界x, 世界y):
    """世界像素坐标 → (经度, 纬度)。闭式解，与 投影() 严格互逆。"""
    x = 世界x / 缩放
    y = _参考半径 + 世界y / 缩放
    极角 = math.atan2(x, y)
    半径 = math.hypot(x, y)
    if 半径 <= 0:
        return (中央经线, 90.0)
    return (中央经线 + math.degrees(极角) / 圆锥常数,
            math.degrees(2 * math.atan(半径 ** (-1.0 / 圆锥常数))) - 90.0)


def 度每像素(纬度=36.0, 经度=None):
    """该处 1 个世界像素约等于多少度（南北方向实测，等角投影各方向一致）。

    用途：把配准残差从"像素"换算成"度"（人看得懂），以及给视野留边距。
    圆锥投影下比例尺随纬度变化（中国范围内约 ±5%），所以需要传纬度。
    """
    经度 = 中央经线 if 经度 is None else 经度
    北 = 投影(经度, 纬度 + 0.5)
    南 = 投影(经度, 纬度 - 0.5)
    return 1.0 / math.hypot(北[0] - 南[0], 北[1] - 南[1])


def 投影说明():
    """一句话描述当前投影（日志、关于框、测试报错时用）。"""
    return (f"兰勃特等角圆锥（中央经线 {中央经线:g}°，圆锥常数 {圆锥常数:.6g}，"
            f"缩放 {缩放:g}，{投影参数.get('来源')}）")


def 混合(色一, 色二, 比例):
    """把 色二 按比例混进 色一（替代画布缺失的透明度）。比例 0~1。"""
    def 分量(色):
        return int(色[1:3], 16), int(色[3:5], 16), int(色[5:7], 16)
    r1, g1, b1 = 分量(色一)
    r2, g2, b2 = 分量(色二)
    return "#%02x%02x%02x" % (int(r1 + (r2 - r1) * 比例),
                              int(g1 + (g2 - g1) * 比例),
                              int(b1 + (b2 - b1) * 比例))


# 配色一律来自 assets/theme.json（经 ui/资产.py 读取），本文件不得写死颜色。
# 这里把主题里的完整键名映射成原先的短键名，其余代码保持不变。
配色 = {
    "海": 资产.地图颜色("海"), "陆": 资产.地图颜色("陆"),
    "轮廓": 资产.地图颜色("轮廓"), "界线": 资产.地图颜色("界线"),
    "州名": 资产.地图颜色("州名"), "州名描边": 资产.地图颜色("州名描边"),
    "蜀": 资产.地图颜色("蜀汉"), "魏": 资产.地图颜色("曹魏"),
    "蜀浅": 资产.地图颜色("蜀汉浅"), "魏浅": 资产.地图颜色("曹魏浅"),
    "围攻": 资产.地图颜色("围攻"), "选中": 资产.地图颜色("选中"),
    "标签底": 资产.地图颜色("标签底"), "标签边": 资产.地图颜色("标签边"),
    "标签字": 资产.地图颜色("标签字"), "标签次": 资产.地图颜色("标签次"),
}
州色混合比例 = 资产.地图参数("州色混合比例", 0.34)          # 州色混进陆地色的比例
标签字号 = 资产.字号("地图标注", 9)
州名字号 = 资产.字号("地图州名", 9)


# ══════════════════════════════════════════════════════════════════
#  数据加载与校验
# ══════════════════════════════════════════════════════════════════
def 地图数据路径():
    """复用 config_loader 对项目根目录的判定（源码运行 / 打包 exe 都成立）。"""
    return 配置路径("map.json")


def 载入地图数据(路径=None):
    """读取并做基本校验。返回 (数据, 错误列表)。数据缺失不应让游戏崩溃，只让地图不可用。"""
    路径 = 路径 or 地图数据路径()
    错误 = []
    if not os.path.isfile(路径):
        return None, [f"地图数据文件不存在：{路径}（游戏其余功能不受影响）"]
    try:
        with open(路径, encoding="utf-8") as 文件:
            数据 = json.load(文件)
    except (OSError, json.JSONDecodeError) as 异常:
        return None, [f"地图数据无法解析：{路径} → {异常}"]
    for 键 in ("底图", "州", "城池"):
        if 键 not in 数据:
            return 数据, [f"地图数据缺少必需字段：{键}"]
    州名集 = {州.get("名") for 州 in 数据["州"]}
    for 序号, 州 in enumerate(数据["州"], 1):
        if not 州.get("名"):
            错误.append(f"第 {序号} 个州缺少名称")
        if len(州.get("边界") or []) < 3:
            错误.append(f"州「{州.get('名', 序号)}」边界点不足 3 个")
    for 序号, 城 in enumerate(数据["城池"], 1):
        if not 城.get("名"):
            错误.append(f"第 {序号} 个城池缺少名称")
            continue
        try:
            经度, 纬度 = float(城["经度"]), float(城["纬度"])
        except (KeyError, TypeError, ValueError):
            错误.append(f"城池「{城['名']}」的经纬度非法")
            continue
        if not (73 <= 经度 <= 136 and 18 <= 纬度 <= 54):
            错误.append(f"城池「{城['名']}」坐标超出中国范围：{经度}, {纬度}")
        if 城.get("来源") not in ("敌方城池", "蜀汉城池", "将领驻地"):
            错误.append(f"城池「{城['名']}」的来源非法：{城.get('来源')!r}")
        if 城.get("归属") not in ("蜀汉", "曹魏"):
            错误.append(f"城池「{城['名']}」的归属非法：{城.get('归属')!r}")
    if not 州名集:
        错误.append("州列表为空")
    return 数据, 错误


def 载入郡界骨架(路径=None):
    """读取 config/郡界骨架.json（可选数据）。返回 (数据, 错误列表)。

    这是**几何骨架**（由郡治与属县点位算出的泰森多边形），不是考据边界；
    界面上必须始终带着"骨架"字样展示，避免被误当成历史定论。
    数据缺失只让这一层不显示，不影响游戏其余部分。
    """
    路径 = 路径 or os.path.join(os.path.dirname(地图数据路径()), "郡界骨架.json")
    if not os.path.isfile(路径):
        return None, [f"未找到郡界骨架数据：{路径}"
                   f"（可跑 python tools/郡界骨架生成.py --导出数据 生成）"]
    错误 = []
    try:
        with open(路径, encoding="utf-8") as 文件:
            数据 = json.load(文件)
    except (OSError, json.JSONDecodeError) as 异常:
        return None, [f"郡界骨架数据无法解析：{异常}"]
    郡们 = 数据.get("郡")
    if not isinstance(郡们, list) or not 郡们:
        错误.append("郡界骨架数据缺少「郡」列表")
        return 数据, 错误
    for 条 in 郡们:
        格们 = 条.get("格") or []
        if not 格们:
            错误.append(f"「{条.get('郡')}」没有格子数据")
        for 格 in 格们:
            if len(格) < 3:
                错误.append(f"「{条.get('郡')}」有少于 3 点的退化格子")
            for 点 in 格:
                if len(点) != 2 or not (-180 <= 点[0] <= 180 and -90 <= 点[1] <= 90):
                    错误.append(f"「{条.get('郡')}」格子中有非法坐标 {点}")
    if not 数据.get("警告"):
        错误.append("骨架数据缺少「警告」字段（必须显式声明它不是考据边界）")
    return 数据, 错误


def 点在多边形内(点, 多边形):
    """射线法：判断 (经度, 纬度) 是否落在多边形内。多边形为 [[经,纬], ...]。"""
    x, y = 点
    内 = False
    个数 = len(多边形)
    for i in range(个数):
        x1, y1 = 多边形[i][0], 多边形[i][1]
        x2, y2 = 多边形[(i + 1) % 个数][0], 多边形[(i + 1) % 个数][1]
        if (y1 > y) != (y2 > y):
            交点x = x1 + (y - y1) * (x2 - x1) / (y2 - y1)
            if x < 交点x:
                内 = not 内
    return 内


# ══════════════════════════════════════════════════════════════════
#  画布控件
# ══════════════════════════════════════════════════════════════════
class 地图画布(tk.Canvas):
    """可缩放 / 可平移 / 城池可点的游戏地图。"""

    最小缩放, 最大缩放 = 0.25, 24.0
    点击命中半径 = 资产.地图参数("点击命中半径", 14)
    标签缩放门槛 = 资产.地图参数("标签缩放门槛", 4.0)          # 低于此缩放只画城池点位与名称提示，不画数据标签
    骨架明细门槛 = 2                                            # 点位数 ≥ 此值才算"有属县依据"的郡

    def __init__(self, 父窗口, 数据, 城池回调=None, 骨架数据=None, **关键字):
        super().__init__(父窗口, background=配色["海"], highlightthickness=0,
                       cursor="fleur", **关键字)
        self.数据 = 数据
        self.骨架 = 骨架数据
        self.城池回调 = 城池回调
        self.缩放 = 1.0
        self.偏移x = 0.0
        self.偏移y = 0.0
        self.首次适应 = False
        self.选中城池 = None
        self.悬停城池 = None
        self.悬停郡 = None
        self.显示骨架 = True          # 郡界骨架（有属县依据的 6 郡）
        self.显示粗骨架 = False       # 仅有治所单点的郡（更不可信，默认不显示）
        self.局面 = {}
        self.标签矩形 = {}          # 城名 -> (x1, y1, x2, y2) 屏幕坐标，用于防重叠
        self._拖动起点 = None
        self._拖动位移 = 0.0
        self.bind("<Configure>", self._尺寸变化)
        self.bind("<MouseWheel>", self._滚轮)
        self.bind("<Button-4>", lambda 事件: self.缩放一步(1.15, 事件.x, 事件.y))   # Linux 上滚
        self.bind("<Button-5>", lambda 事件: self.缩放一步(1 / 1.15, 事件.x, 事件.y))
        self.bind("<ButtonPress-1>", self._按下)
        self.bind("<B1-Motion>", self._拖动)
        self.bind("<ButtonRelease-1>", self._松开)
        self.bind("<Motion>", self._鼠标移动)

    # ── 郡界骨架：开关与查询 ──
    def 设骨架(self, 骨架数据):
        self.骨架 = 骨架数据
        self.重绘()

    def 设显示骨架(self, 显示):
        self.显示骨架 = bool(显示)
        self.重绘()

    def 设显示粗骨架(self, 显示):
        self.显示粗骨架 = bool(显示)
        self.重绘()

    def 骨架郡们(self, 含粗=False):
        """返回要绘制的郡条目列表。含粗=False 时只含"有属县依据"（点位数 ≥ 门槛）的郡。"""
        if not self.骨架:
            return []
        return [条 for 条 in self.骨架.get("郡", [])
               if 含粗 or len(条.get("县") or []) >= self.骨架明细门槛]

    def 命中郡(self, 屏幕x, 屏幕y):
        """返回屏幕点落在哪个郡的骨架格里（未命中返回 None）。"""
        经纬 = self.屏幕到经纬(屏幕x, 屏幕y)
        if 经纬 is None:
            return None
        for 条 in self.骨架郡们(self.显示粗骨架):
            for 格 in 条.get("格") or []:
                if 点在多边形内(经纬, 格):
                    return 条
        return None

    def 屏幕到经纬(self, 屏幕x, 屏幕y):
        """屏幕坐标 → 经纬度（与 屏幕到世界 配套，供命中郡使用）。"""
        return 逆投影(*self.屏幕到世界(屏幕x, 屏幕y))

    def _鼠标移动(self, 事件):
        """悬停：城池优先，其次郡界骨架；只重画提示层，避免整图重绘导致卡顿。"""
        新郡 = None
        if self.骨架 is not None and (self.显示骨架 or self.显示粗骨架):
            新郡 = self.命中郡(事件.x, 事件.y)
        if (新郡 or {}).get("郡") != (self.悬停郡 or {}).get("郡"):
            self.悬停郡 = 新郡
            self._画郡提示()

    # ── 坐标变换 ──
    def 世界到屏幕(self, 世界x, 世界y):
        return 世界x * self.缩放 + self.偏移x, 世界y * self.缩放 + self.偏移y

    def 屏幕到世界(self, 屏幕x, 屏幕y):
        return (屏幕x - self.偏移x) / self.缩放, (屏幕y - self.偏移y) / self.缩放

    def _点列表到屏幕(self, 点列):
        平铺 = []
        for 经度, 纬度 in 点列:
            x, y = self.世界到屏幕(*投影(经度, 纬度))
            平铺.extend((x, y))
        return 平铺

    # ── 视图控制 ──
    def _尺寸变化(self, 事件=None):
        if not self.首次适应 and self.winfo_width() > 50:
            self.适应全图()
            self.首次适应 = True

    def 适应全图(self):
        """把整幅十三州图放进当前画布。"""
        if not self.数据:
            return
        宽, 高 = max(self.winfo_width(), 50), max(self.winfo_height(), 50)
        框 = self.世界范围(self.数据["底图"].get("中国轮廓") or [])
        if 框 is None:
            return
        x0, y0, x1, y1 = 框
        self.缩放 = min(宽 / max(x1 - x0, 1), 高 / max(y1 - y0, 1)) * 0.96
        self.缩放 = max(self.最小缩放, min(self.最大缩放, self.缩放))
        self.偏移x = (宽 - (x1 - x0) * self.缩放) / 2 - x0 * self.缩放
        self.偏移y = (高 - (y1 - y0) * self.缩放) / 2 - y0 * self.缩放
        self.重绘()

    def 居中战场(self):
        """缩放到十个游戏城池所在的荆襄—汉中战场（其余地区概括显示）。"""
        if not self.数据:
            return
        宽, 高 = max(self.winfo_width(), 50), max(self.winfo_height(), 50)
        框 = self.世界范围([(城["经度"], 城["纬度"]) for 城 in self.数据["城池"]])
        if 框 is None:
            return
        x0, y0, x1, y1 = 框
        # 留出边距，避免城池贴在画布边缘（同时给标签留位置）
        # 注意：圆锥投影下"1 像素 = 多少度"随纬度变化，所以余量按战场纬度处的比例尺折算，
        # 而不是像等距圆柱那样直接乘常数。
        余量 = 1.0 / 度每像素(32.0)
        x0 -= 余量
        x1 += 余量
        y0 -= 余量
        y1 += 余量
        self.缩放 = min(宽 / max(x1 - x0, 1), 高 / max(y1 - y0, 1))
        self.缩放 = max(self.最小缩放, min(self.最大缩放, self.缩放))
        self.偏移x = (宽 - (x1 - x0) * self.缩放) / 2 - x0 * self.缩放
        self.偏移y = (高 - (y1 - y0) * self.缩放) / 2 - y0 * self.缩放
        self.重绘()

    def 缩放一步(self, 因子, 屏幕x=None, 屏幕y=None):
        """以给定屏幕点（默认画布中心）为锚点缩放。"""
        屏幕x = self.winfo_width() / 2 if 屏幕x is None else 屏幕x
        屏幕y = self.winfo_height() / 2 if 屏幕y is None else 屏幕y
        世界x, 世界y = self.屏幕到世界(屏幕x, 屏幕y)
        新缩放 = max(self.最小缩放, min(self.最大缩放, self.缩放 * 因子))
        if abs(新缩放 - self.缩放) < 1e-9:
            return
        self.缩放 = 新缩放
        self.偏移x = 屏幕x - 世界x * self.缩放
        self.偏移y = 屏幕y - 世界y * self.缩放
        self.重绘()

    def 世界范围(self, 经纬点列):
        if not 经纬点列:
            return None
        点们 = [投影(*点) for 点 in 经纬点列]
        return (min(p[0] for p in 点们), min(p[1] for p in 点们),
                max(p[0] for p in 点们), max(p[1] for p in 点们))

    # ── 鼠标 ──
    def _滚轮(self, 事件):
        self.缩放一步(1.15 if 事件.delta > 0 else 1 / 1.15, 事件.x, 事件.y)

    def _按下(self, 事件):
        self._拖动起点 = (事件.x, 事件.y, self.偏移x, self.偏移y)
        self._拖动位移 = 0.0

    def _拖动(self, 事件):
        if self._拖动起点 is None:
            return
        起x, 起y, 起偏x, 起偏y = self._拖动起点
        新偏x, 新偏y = 起偏x + (事件.x - 起x), 起偏y + (事件.y - 起y)
        self._拖动位移 = max(self._拖动位移, abs(事件.x - 起x) + abs(事件.y - 起y))
        self.move("地图", 新偏x - self.偏移x, 新偏y - self.偏移y)   # 拖动时只平移，不重排标签
        self.偏移x, self.偏移y = 新偏x, 新偏y

    def _松开(self, 事件):
        if self._拖动起点 is None:
            return
        位移 = self._拖动位移
        self._拖动起点 = None
        if 位移 < 4:                       # 几乎没动 → 当作点击
            城名 = self.命中城池(事件.x, 事件.y)
            if 城名 and self.城池回调 is not None:
                self.选中城池 = 城名
                self.重绘()
                self.城池回调(城名)
                return
        self.重绘()                        # 拖完重绘一次，标签回到正确位置

    def 命中城池(self, 屏幕x, 屏幕y):
        最近, 最近距 = None, self.点击命中半径 + 1
        for 城 in self.数据["城池"]:
            x, y = self.世界到屏幕(*投影(城["经度"], 城["纬度"]))
            距 = ((x - 屏幕x) ** 2 + (y - 屏幕y) ** 2) ** 0.5
            if 距 <= self.点击命中半径 and 距 < 最近距:
                最近, 最近距 = 城["名"], 距
        return 最近

    # ── 渲染 ──
    def 重绘(self, 局面=None):
        if 局面 is not None:
            self.局面 = 局面
        self.delete("all")
        if not self.数据:
            self.create_text(self.winfo_width() / 2, self.winfo_height() / 2,
                            text="地图数据不可用（config/map.json 缺失或非法）",
                            fill=资产.地图颜色("错误字"), font=资产.字体("正文", 11))
            return
        self.create_rectangle(0, 0, self.winfo_width(), self.winfo_height(),
                              fill=配色["海"], width=0, tags="背景")
        self._画底图()
        self._画州域()
        self._画州名()
        self._画郡界()
        self._画城池()
        self._画图例()
        self._画郡提示()

    def _画郡界(self):
        """画郡界骨架：只画"有属县依据"的郡；仅有治所单点的郡默认不画（更不可信）。

        骨架的格子只做**淡填充 + 虚线边**，与"州界底"和"城池"区分开，
        并且图例里明确写着"骨架"二字 —— 不允许被误当成考据边界。
        """
        if not self.骨架 or not (self.显示骨架 or self.显示粗骨架):
            return
        州色表 = {州["名"]: 州.get("色") or 资产.地图颜色("默认州色")
                for 州 in self.数据.get("州", [])}
        for 条 in self.骨架郡们(self.显示粗骨架):
            有依据 = len(条.get("县") or []) >= self.骨架明细门槛
            色 = 州色表.get(条.get("州"), 资产.地图颜色("默认州色"))
            填充 = 混合(配色["陆"], 色, 0.22 if 有依据 else 0.10)
            边色 = 混合(配色["陆"], 色, 0.75) if 有依据 else 资产.地图颜色("界线")
            for 格 in 条.get("格") or []:
                if len(格) < 3:
                    continue
                self.create_polygon(self._点列表到屏幕(格), fill=填充,
                                    outline=边色,
                                    width=1.4 if 有依据 else 0.8,
                                    dash=() if 有依据 else (4, 4),
                                    tags=("地图", "郡界"))

    def _画郡提示(self):
        """鼠标悬停在某郡上时，在画布一角显示该郡的详情（含"骨架"警示）。"""
        self.delete("郡提示")
        if not self.悬停郡:
            return
        条 = self.悬停郡
        县们 = 条.get("县") or []
        治所县 = next((县 for 县 in 县们 if 县.get("是治所")), None)
        行们 = [
            f'{条.get("郡", "")}（{条.get("州", "")}）',
            f'治所 {条.get("治所", "—")} → {条.get("治所今地", "—")}',
            f'本图点位 {len(县们)} 个（治所＋属县）',
            f'交界带：{条.get("交界带今地", "—")}',
            f'⚠ 骨架：几何推断，非考据边界（整体置信度 {条.get("整体置信度", "?")}）',
        ]
        if 条.get("待核"):
            行们.append("待核：" + "；".join(条["待核"][:2]))
        宽 = 460
        高 = 18 * len(行们) + 16
        x1, y1 = 12, 12
        self.create_rectangle(x1, y1, x1 + 宽, y1 + 高, fill=配色["标签底"],
                             outline=配色["围攻"], width=1.4, tags="郡提示")
        self.create_text(x1 + 10, y1 + 8, anchor="nw", justify="left",
                        text="\n".join(行们), fill=配色["标签字"],
                        font=资产.字体("正文", 9), tags="郡提示")

    def _画底图(self):
        轮廓 = self.数据["底图"].get("中国轮廓") or []
        if 轮廓:
            self.create_polygon(self._点列表到屏幕(轮廓), fill=配色["陆"],
                                outline=配色["轮廓"], width=1.2, dash=(6, 4),
                                tags="地图")
        for 名, 点列 in (self.数据["底图"].get("岛屿") or {}).items():
            self.create_polygon(self._点列表到屏幕(点列), fill=配色["陆"],
                                outline=配色["轮廓"], width=1.0, dash=(5, 3),
                                tags="地图")
        for 界线 in (self.数据["底图"].get("内部界线") or []):
            self.create_line(self._点列表到屏幕(界线["点"]), fill=配色["界线"],
                             width=1.0, dash=(3, 4), tags="地图")

    def _画州域(self):
        for 州 in self.数据["州"]:
            色 = 混合(配色["陆"], 州.get("色", 资产.地图颜色("默认州色")), 州色混合比例)
            self.create_polygon(self._点列表到屏幕(州["边界"]), fill=色,
                                outline=混合(色, 资产.地图颜色("州界描边基色"),
                               资产.地图参数("州界描边混合比例", 0.45)), width=0.8,
                                tags=("地图", f"州_{州['名']}"))

    def _画州名(self):
        """州名只在缩放足够时显示，避免全图视图下互相压叠。"""
        if self.缩放 < 0.55:
            return
        for 州 in self.数据["州"]:
            if not 州.get("锚点"):
                continue
            x, y = self.世界到屏幕(*投影(*州["锚点"]))
            self.create_text(x, y, text=州["名"], fill=配色["州名"],
                             font=资产.字体("正文", 州名字号),
                             tags="地图")

    def _取城池状态(self, 城):
        """从局面快照里取出该城的显示信息。

        地图**不自己算规则**，只按「来源」搬运引擎给的状态；引擎里没有城池条目的城
        （成都/江陵/阆中/汉中：兵力算在蜀汉主力野战军里，只有将领驻地）则用数据字段的归属显示。
        返回 None 表示这座城当前不显示。
        """
        名 = 城["名"]
        来源 = 城.get("来源")
        围攻 = self.局面.get("围攻")
        围攻中 = bool(围攻 and 围攻.get("目标") == 名)
        驻将们 = [将 for 将 in self.局面.get("将领们", []) if 将["位置"] == 名
                and 将["状态"] != "已殁"]
        驻将文本 = ("驻将 " + "、".join(f"{将['姓名']}·{将['任务']}" for 将 in 驻将们)
                 if 驻将们 else "驻将 空")

        if 来源 == "敌方城池":
            条目 = next((c for c in self.局面.get("敌方城池", []) if c["城池"] == 名), None)
            if 条目 is None:
                return None
            归属 = 条目["归属"]
            if 归属 == "蜀汉":            # 已被攻占：显示驻军与驻将，不再显示曹魏守军
                return {"归属": 归属, "主数据": "已归蜀汉（新占）",
                        "次数据": 驻将文本, "围攻中": 围攻中}
            return {"归属": 归属, "主数据": f"守军 {条目['守军']:,}　粮 {条目['粮草']:,}",
                    "次数据": f"守将 {条目['守将']}", "围攻中": 围攻中}

        if 来源 == "蜀汉城池":
            条目 = next((c for c in self.局面.get("蜀汉城池", []) if c["城池"] == 名), None)
            主数据 = f"兵力 {条目['兵力']:,}　粮 {条目['粮草']:,}" if 条目 else "驻军 —"
            return {"归属": "蜀汉", "主数据": 主数据, "次数据": 驻将文本, "围攻中": 围攻中}

        # 将领驻地：引擎无城池条目，兵力计入蜀汉主力
        return {"归属": 城.get("归属", "蜀汉"), "主数据": "主力野战军（不在城下）",
                "次数据": 驻将文本, "围攻中": 围攻中}

    def _画城池(self):
        """城池：几何点固定屏幕尺寸；标签用「候选方位 + 防重叠」摆放。"""
        self.标签矩形 = {}
        已放标签 = []
        城池们 = []
        for 城 in self.数据["城池"]:
            状态 = self._取城池状态(城)
            if 状态 is None:
                continue
            x, y = self.世界到屏幕(*投影(城["经度"], 城["纬度"]))
            城池们.append((城, 状态, x, y))
        # 先画所有点与高亮，再画标签，保证标签永远压在最上层
        for 城, 状态, x, y in 城池们:
            主色 = 配色["蜀"] if 状态["归属"] == "蜀汉" else 配色["魏"]
            半径 = 6 if 城.get("类型") == "首都" else 5
            if 城["名"] == self.选中城池:
                self.create_oval(x - 半径 - 4, y - 半径 - 4, x + 半径 + 4, y + 半径 + 4,
                                 outline=配色["选中"], width=2, tags="地图")
            if 状态["围攻中"]:
                self.create_oval(x - 半径 - 5, y - 半径 - 5, x + 半径 + 5, y + 半径 + 5,
                                 outline=配色["围攻"], width=3, tags="地图")
                self.create_text(x, y - 半径 - 12, text="围攻中", fill=配色["围攻"],
                                 font=资产.字体("标题", 8, True), tags="地图")
            self.create_oval(x - 半径, y - 半径, x + 半径, y + 半径, fill=主色,
                             outline=资产.地图颜色("城池描边"), width=1.6, tags=("地图", f"城_{城['名']}"))
        for 城, 状态, x, y in 城池们:
            if self.缩放 < self.标签缩放门槛:
                continue        # 缩得太小时只留点位，避免十个标签挤成一团（放大即出现）
            框 = self._放标签(城, 状态, x, y, 已放标签)
            已放标签.append(框)
            self.标签矩形[城["名"]] = 框

    def _放标签(self, 城, 状态, x, y, 已放标签):
        """在城池周围**螺旋搜索**第一个不与已放标签重叠、且留在画布内的位置。

        为什么要螺旋搜索而不是固定几个方位：全图视野下十个城池在屏幕上只占很小一块，
        襄阳/樊城/宛城更是挤在一起；固定方位必然互相压叠。这里按"由近到远"逐圈试，
        确定性（无随机），且能把标签推到稍远处仍指着同一座城。
        """
        主色 = 配色["蜀"] if 状态["归属"] == "蜀汉" else 配色["魏"]
        行一 = 城["名"] + ("（围攻中）" if 状态["围攻中"] else "")
        行二 = 状态["主数据"]
        文本 = f"{行一}\n{行二}\n{状态['次数据']}"
        估宽 = max(len(行一) * 12.5, len(行二) * 7.4, len(状态["次数据"]) * 7.4) + 16
        估高 = 44
        画布宽, 画布高 = self.winfo_width(), self.winfo_height()

        def 可用(x1, y1):
            x2, y2 = x1 + 估宽, y1 + 估高
            if x1 < 3 or y1 < 3 or x2 > 画布宽 - 3 or y2 > 画布高 - 3:
                return None
            for a1, b1, a2, b2 in 已放标签:
                if not (x2 < a1 or x1 > a2 or y2 < b1 or y1 > b2):
                    return None
            return (x1, y1, x2, y2)

        # 由近及远：圈半径递增，每圈八个方位（含正东南西北与四角）
        for 半径 in (13, 34, 55, 78, 102, 128, 156, 186, 218):
            for 偏x, 偏y in ((半径, -估高 / 2), (-半径 - 估宽, -估高 / 2),
                           (0, 半径), (0, -半径 - 估高),
                           (半径 * 0.75, 半径 * 0.75),
                           (-半径 * 0.75 - 估宽, 半径 * 0.75),
                           (半径 * 0.75, -半径 * 0.75 - 估高),
                           (-半径 * 0.75 - 估宽, -半径 * 0.75 - 估高)):
                框 = 可用(x + 偏x, y + 偏y)
                if 框 is not None:
                    self.create_rectangle(*框, fill=配色["标签底"], outline=主色,
                                         width=1.2, tags="地图")
                    self.create_text(框[0] + 8, 框[1] + 5, text=文本, anchor="nw",
                                    fill=配色["标签字"],
                                    font=资产.字体("正文", 标签字号), tags="地图")
                    return 框
        # 实在放不下（画布过小）：仍画一个，保证信息不丢
        框 = (x + 13, y - 估高 / 2, x + 13 + 估宽, y + 估高 / 2)
        self.create_rectangle(*框, fill=配色["标签底"], outline=主色, width=1.2, tags="地图")
        self.create_text(框[0] + 8, 框[1] + 5, text=文本, anchor="nw",
                        fill=配色["标签字"], font=资产.字体("正文", 标签字号), tags="地图")
        return 框

    def _画图例(self):
        条目 = [("●", 配色["蜀"], "蜀汉城池"), ("●", 配色["魏"], "曹魏城池"),
              ("◎", 配色["围攻"], "围攻中")]
        行高, 顶距 = 18, 9
        有骨架说明 = bool(self.骨架 and (self.显示骨架 or self.显示粗骨架))
        宽 = 620 if 有骨架说明 else 300
        高 = 行高 * 2 + 顶距 * 2 - 4 + (16 if 有骨架说明 else 0)
        x1, y1 = 10, self.winfo_height() - 高 - 10
        self.create_rectangle(x1, y1, x1 + 宽, y1 + 高, fill=配色["标签底"],
                             outline=配色["标签边"], width=1, tags="图例")
        偏移 = 10
        for 符号, 色, 文字 in 条目:
            self.create_text(x1 + 偏移, y1 + 顶距 + 2, text=符号, anchor="w", fill=色,
                            font=资产.字体("正文", 11), tags="图例")
            self.create_text(x1 + 偏移 + 15, y1 + 顶距 + 3, text=文字, anchor="w",
                            fill=配色["标签次"], font=资产.字体("正文", 8),
                            tags="图例")
            偏移 += 15 + len(文字) * 12 + 16
        self.create_text(x1 + 10, y1 + 顶距 + 行高 + 4,
                        text="滚轮缩放 · 拖动平移 · 点击城池查看详情与行动",
                        anchor="nw", fill=配色["标签次"],
                        font=资产.字体("正文", 8), tags="图例")
        self.create_text(x1 + 宽 - 10, y1 + 顶距 + 3, text=f"缩放 {self.缩放:.2f}×",
                        anchor="e", fill=配色["标签次"],
                        font=资产.字体("正文", 8), tags="图例")
        # 郡界骨架的说明（只在显示骨架时出现；必须带"骨架"二字，避免被当成考据边界）
        if 有骨架说明:
            有依据 = len(self.骨架郡们(False))
            粗 = len(self.骨架郡们(True)) - 有依据
            说明 = f"郡界为几何骨架（泰森多边形推断）：{有依据} 郡有属县依据"
            if 粗 and self.显示粗骨架:
                说明 += f" + {粗} 郡仅治所（虚线·更不可信）"
            说明 += "　—— 非考据边界，悬停可看该郡古今对照"
            self.create_text(x1 + 10, y1 + 顶距 + 行高 * 2 + 2, text=说明,
                            anchor="nw", fill=配色["围攻"],
                            font=资产.字体("正文", 8), tags="图例")

    # ── 供测试与外部查询 ──
    def 城池屏幕位置(self, 城名):
        for 城 in self.数据["城池"]:
            if 城["名"] == 城名:
                return self.世界到屏幕(*投影(城["经度"], 城["纬度"]))
        return None

    def 可视城池(self):
        """返回当前画布窗口内可见的城池名（用于测试与日志）。"""
        可见 = []
        for 城 in self.数据["城池"]:
            x, y = self.世界到屏幕(*投影(城["经度"], 城["纬度"]))
            if 0 <= x <= self.winfo_width() and 0 <= y <= self.winfo_height():
                可见.append(城["名"])
        return 可见
