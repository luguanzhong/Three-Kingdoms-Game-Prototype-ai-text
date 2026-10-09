# -*- coding: utf-8 -*-
"""官方底图图层：把 assets/images/标准地图-中国.png 按配准结果铺在地图画布最下层。

═══════════════════════════════════════════════════════════════════
【它解决什么问题】
州郡界、城池、郡界骨架都是"经纬度 → 投影 → 画布"画出来的矢量图。底下没有东西时，
用户只能看到一堆线；铺上官方标准地图之后，一眼就能看出这些线与真实地理的对应关系。

【tkinter 的三个硬限制，决定了这里的所有写法】
1. **PhotoImage 不能旋转**，只能整数倍 `zoom(m)` / `subsample(n)` 缩放。
   → 所以配准时特意把"官方底图相对游戏坐标系的 2.82° 旋转"折算成中央经线的偏移
     （见 tools/底图配准.py 的 等效中央经线()），使底图与游戏坐标系**轴对齐**；
     config/底图配准.json 里的六参数因此退化成 b=d=0、a=e 的纯缩放＋平移，tkinter 才画得准。
     本模块会**检查**这一点：万一配准带旋转，就拒绝绘制并说明原因，而不是画一张歪图。
2. **缩放倍率只能是 m/n（两个整数之比）**。
   → 底图打开时，画布缩放会**吸附**到能被 m/n 精确表示的档位，这样底图与矢量图层
     用的是同一个比例尺，叠出来没有系统性错位（宁可档位粗一点，也不要"图对不齐"）。
   → 底图关闭时不吸附，缩放行为与以前**完全一致**（硬要求）。
3. **位图不能整幅塞进内存再放大**：4200×2963 放大 3 倍就是 1.2 亿像素。
   → 每帧只裁出**可见的那一块**再缩放（`PhotoImage copy -from`），内存与耗时都可控。
"""
import json
import math
import os
import tkinter as tk

import 地图  # noqa: E402  （同目录：投影与配置路径都走它）

最大放大 = 12         # m 的上限（画布像素 / 图像像素）；给到 12 是为了高档位的 m/n 也够细
最大缩小 = 60         # n 的上限
最小倍率 = 1.0 / 最大缩小
最大倍率 = float(最大放大)
默认图像 = os.path.join("assets", "images", "标准地图-中国.png")


def 配准路径():
    return 地图.配置路径("底图配准.json")


def 项目根目录():
    return os.path.dirname(os.path.dirname(地图.配置路径("map.json")))


def 载入配准(路径=None):
    """读 config/底图配准.json。返回 (数据 或 None, 问题列表)。

    读不到不是错误、也不该让游戏崩：底图只是"锦上添花"，缺了照样能玩。
    """
    路径 = 路径 or 配准路径()
    if not os.path.isfile(路径):
        return None, [f"还没有底图配准文件（{os.path.relpath(路径, 项目根目录())}）；"
                     f"跑一次 python tools/底图配准.py 就会生成"]
    try:
        with open(路径, encoding="utf-8") as 文件:
            数据 = json.load(文件)
    except (OSError, json.JSONDecodeError) as 异常:
        return None, [f"底图配准文件读不了：{异常!r}"]
    系数 = (数据.get("像素到世界") or {}).get("系数")
    if not (isinstance(系数, list) and len(系数) == 6
            and all(isinstance(值, (int, float)) and not isinstance(值, bool) for 值 in 系数)):
        return None, ["底图配准文件里的「像素到世界」系数不是 6 个数字"]
    宽高 = 数据.get("图像宽高")
    if not (isinstance(宽高, list) and len(宽高) == 2):
        return None, ["底图配准文件里缺「图像宽高」"]
    a, b, c, d, e, f = [float(值) for 值 in 系数]
    尺度 = max(abs(a), abs(e), 1e-9)
    if max(abs(b), abs(d)) > 尺度 * 1e-6:
        return None, [f"底图配准里含旋转或错切（b={b:g}、d={d:g}），tkinter 画不了旋转位图 —— "
                     f"请用 python tools/底图配准.py 重跑（它给的是轴对齐结果）"]
    问题 = []
    if abs(abs(a) - abs(e)) > 尺度 * 1e-6:
        问题.append(f"底图横纵缩放不一致（a={a:g}、e={e:g}），叠上去会有轻微拉伸")
    return 数据, 问题


class 底图图层(object):
    """一张已经配准好的底图：负责坐标换算、"裁哪一块、缩放几倍"。"""

    def __init__(self, 数据, 图像路径=None):
        self.数据 = 数据
        系数 = 数据["像素到世界"]["系数"]
        self.a, self.b, self.c, self.d, self.e, self.f = [float(值) for 值 in 系数]
        相对 = 数据.get("图像") or 默认图像
        self.图像路径 = 图像路径 or os.path.join(项目根目录(), 相对)
        self.图像宽, self.图像高 = [int(值) for 值 in 数据["图像宽高"]]
        self.源图 = None
        self.错误 = []
        self._缓存键 = None
        self._缓存 = None

    # ── 坐标换算 ──
    def 像素到世界(self, u, v):
        return (self.a * u + self.b * v + self.c, self.d * u + self.e * v + self.f)

    def 世界到像素(self, x, y):
        行列式 = self.a * self.e - self.b * self.d
        if abs(行列式) < 1e-12:
            return None
        return ((self.e * (x - self.c) - self.b * (y - self.f)) / 行列式,
                (-self.d * (x - self.c) + self.a * (y - self.f)) / 行列式)

    def 世界每像素(self):
        """1 个图像像素等于多少世界像素（轴对齐时横纵相同）。"""
        return abs(self.a)

    def 可用(self):
        return os.path.isfile(self.图像路径)

    def 缺图说明(self):
        return f"底图图片不存在：{os.path.relpath(self.图像路径, 项目根目录())}"

    # ── 缩放档位 ──
    def 吸附档位(self, 目标倍率):
        """把目标倍率吸附到能被 m/n 精确表示的档位，返回 (m, n, 精确倍率)。

        倍率 = 画布像素 / 图像像素。搜索面很小（m ≤ 8、n ≤ 60），一次几百次比较，够快。
        """
        目标 = min(max(目标倍率, 最小倍率), 最大倍率)
        最好 = None
        for n in range(1, 最大缩小 + 1):
            for m in range(1, 最大放大 + 1):
                倍率 = m / n
                if 倍率 < 最小倍率 * 0.99 or 倍率 > 最大倍率 * 1.01:
                    continue
                差 = abs(math.log(倍率 / 目标))
                if 最好 is None or 差 < 最好[0]:
                    最好 = (差, m, n, 倍率)
        if 最好 is None:
            return (1, 最大缩小, 最小倍率)
        return (最好[1], 最好[2], 最好[3])

    # ── 取图 ──
    def 取源图(self):
        if self.源图 is None:
            try:
                self.源图 = tk.PhotoImage(file=self.图像路径)
            except Exception as 异常:                      # noqa: BLE001
                self.错误.append(f"底图载入失败：{异常!r}")
                return None
            if (self.源图.width(), self.源图.height()) != (self.图像宽, self.图像高):
                self.错误.append(
                    f"底图尺寸与配准文件不符（图 {self.源图.width()}×{self.源图.height()}，"
                    f"配准 {self.图像宽}×{self.图像高}）—— 换过图就必须重跑配准")
                self.源图 = None
        return self.源图

    def 造块(self, u0, v0, u1, v1, m, n):
        """裁出图像像素矩形 [u0,v0)-(u1,v1) 并缩放到 m/n 倍。返回 PhotoImage 或 None。

        `subsample(n).zoom(m)` 的像素相位是确定的（取第 0、n、2n… 个像素，各放大成 m×m 的块），
        所以第 i 块的中心对应图像像素 u0 + i·n —— 上层据此定位即可做到**逐像素对齐**。
        """
        源 = self.取源图()
        if 源 is None:
            return None
        u0 = max(0, min(int(u0), self.图像宽 - 1))
        v0 = max(0, min(int(v0), self.图像高 - 1))
        u1 = max(u0 + 1, min(int(math.ceil(u1)), self.图像宽))
        v1 = max(v0 + 1, min(int(math.ceil(v1)), self.图像高))
        宽, 高 = u1 - u0, v1 - v0
        n = max(1, min(n, 宽, 高))
        键 = (u0, v0, 宽, 高, m, n)
        if self._缓存键 == 键 and self._缓存 is not None:
            return self._缓存
        裁 = tk.PhotoImage(width=宽, height=高)
        源.tk.call(裁.name, "copy", 源.name, "-from", u0, v0, u1, v1, "-to", 0, 0)
        图 = 裁.subsample(n) if n > 1 else 裁
        图 = 图.zoom(m) if m > 1 else 图
        self._缓存键 = 键
        self._缓存 = 图
        return 图
