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
import os
import tkinter as tk

# —— 投影：与 tools/生成州域对照图.py 完全一致（等距圆柱近似）——
经度基准, 经度系数 = 73.0, 19.0
纬度基准, 纬度系数 = 54.0, 23.0


def 投影(经度, 纬度):
    """(经度, 纬度) → 世界像素坐标（与州域对照图同一套投影，两图可对齐）。"""
    return ((经度 - 经度基准) * 经度系数, (纬度基准 - 纬度) * 纬度系数)


def 混合(色一, 色二, 比例):
    """把 色二 按比例混进 色一（替代画布缺失的透明度）。比例 0~1。"""
    def 分量(色):
        return int(色[1:3], 16), int(色[3:5], 16), int(色[5:7], 16)
    r1, g1, b1 = 分量(色一)
    r2, g2, b2 = 分量(色二)
    return "#%02x%02x%02x" % (int(r1 + (r2 - r1) * 比例),
                              int(g1 + (g2 - g1) * 比例),
                              int(b1 + (b2 - b1) * 比例))


配色 = {
    "海": "#dde8f0", "陆": "#f2eee2", "轮廓": "#98a2ab", "界线": "#bcc4ca",
    "州名": "#8f8578", "州名描边": "#f2eee2",
    "蜀": "#2f6b3f", "魏": "#8c3b3b", "蜀浅": "#5d9668", "魏浅": "#b5706f",
    "围攻": "#d98324", "标签底": "#fffdf8", "标签边": "#c3b9a4",
    "标签字": "#241f18", "标签次": "#6f6558", "选中": "#1f6f9c",
}
州色混合比例 = 0.34          # 州色混进陆地色的比例
标签字号 = 9
州名字号 = 9


# ══════════════════════════════════════════════════════════════════
#  数据加载与校验
# ══════════════════════════════════════════════════════════════════
def 地图数据路径():
    """复用 config_loader 对项目根目录的判定（源码运行 / 打包 exe 都成立）。"""
    try:
        import config_loader
        return os.path.join(config_loader.项目根目录, "config", "map.json")
    except Exception:
        return os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                            "config", "map.json")


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


# ══════════════════════════════════════════════════════════════════
#  画布控件
# ══════════════════════════════════════════════════════════════════
class 地图画布(tk.Canvas):
    """可缩放 / 可平移 / 城池可点的游戏地图。"""

    最小缩放, 最大缩放 = 0.25, 24.0
    点击命中半径 = 14
    标签缩放门槛 = 4.0          # 低于此缩放只画城池点位与名称提示，不画数据标签

    def __init__(self, 父窗口, 数据, 城池回调=None, **关键字):
        super().__init__(父窗口, background=配色["海"], highlightthickness=0,
                       cursor="fleur", **关键字)
        self.数据 = 数据
        self.城池回调 = 城池回调
        self.缩放 = 1.0
        self.偏移x = 0.0
        self.偏移y = 0.0
        self.首次适应 = False
        self.选中城池 = None
        self.悬停城池 = None
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
        经度余量, 纬度余量 = 1.6, 1.2
        x0 -= 经度余量 * 经度系数
        x1 += 经度余量 * 经度系数
        y0 -= 纬度余量 * 纬度系数
        y1 += 纬度余量 * 纬度系数
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
                            fill="#8c3b3b", font=("Microsoft YaHei UI", 11))
            return
        self.create_rectangle(0, 0, self.winfo_width(), self.winfo_height(),
                              fill=配色["海"], width=0, tags="背景")
        self._画底图()
        self._画州域()
        self._画州名()
        self._画城池()
        self._画图例()

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
            色 = 混合(配色["陆"], 州.get("色", "#cccccc"), 州色混合比例)
            self.create_polygon(self._点列表到屏幕(州["边界"]), fill=色,
                                outline=混合(色, "#3c3228", 0.45), width=0.8,
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
                             font=("Microsoft YaHei UI", 州名字号),
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
                                 font=("Microsoft YaHei UI", 8, "bold"), tags="地图")
            self.create_oval(x - 半径, y - 半径, x + 半径, y + 半径, fill=主色,
                             outline="#ffffff", width=1.6, tags=("地图", f"城_{城['名']}"))
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
                                    font=("Microsoft YaHei UI", 标签字号), tags="地图")
                    return 框
        # 实在放不下（画布过小）：仍画一个，保证信息不丢
        框 = (x + 13, y - 估高 / 2, x + 13 + 估宽, y + 估高 / 2)
        self.create_rectangle(*框, fill=配色["标签底"], outline=主色, width=1.2, tags="地图")
        self.create_text(框[0] + 8, 框[1] + 5, text=文本, anchor="nw",
                        fill=配色["标签字"], font=("Microsoft YaHei UI", 标签字号), tags="地图")
        return 框

    def _画图例(self):
        条目 = [("●", 配色["蜀"], "蜀汉城池"), ("●", 配色["魏"], "曹魏城池"),
              ("◎", 配色["围攻"], "围攻中")]
        行高, 顶距 = 18, 9
        宽 = 300
        高 = 行高 * 2 + 顶距 * 2 - 4
        x1, y1 = 10, self.winfo_height() - 高 - 10
        self.create_rectangle(x1, y1, x1 + 宽, y1 + 高, fill=配色["标签底"],
                             outline=配色["标签边"], width=1, tags="图例")
        偏移 = 10
        for 符号, 色, 文字 in 条目:
            self.create_text(x1 + 偏移, y1 + 顶距 + 2, text=符号, anchor="w", fill=色,
                            font=("Microsoft YaHei UI", 11), tags="图例")
            self.create_text(x1 + 偏移 + 15, y1 + 顶距 + 3, text=文字, anchor="w",
                            fill=配色["标签次"], font=("Microsoft YaHei UI", 8),
                            tags="图例")
            偏移 += 15 + len(文字) * 12 + 16
        self.create_text(x1 + 10, y1 + 顶距 + 行高 + 4,
                        text="滚轮缩放 · 拖动平移 · 点击城池查看详情与行动",
                        anchor="nw", fill=配色["标签次"],
                        font=("Microsoft YaHei UI", 8), tags="图例")
        self.create_text(x1 + 宽 - 10, y1 + 顶距 + 3, text=f"缩放 {self.缩放:.2f}×",
                        anchor="e", fill=配色["标签次"],
                        font=("Microsoft YaHei UI", 8), tags="图例")

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
