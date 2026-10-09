# -*- coding: utf-8 -*-
"""配准描图工作台：把"任意一张参考地图"变成"可用的经纬度边界数据"。

═══════════════════════════════════════════════════════════════════
【它解决什么问题】
你手上有一张权威参考图（例如自然资源部的标准地图，或《中国历史地图集》的扫描页），
但它只是**一张图片**——没有经纬度，点上去不知道点在哪儿，也没法直接进游戏。

本工具做两件事：
  ① **配准**：你点 3 个以上"认得出的地标"（城市、河口、海峡最窄处…），
     每个输入它的真实经纬度，工具就算出「图上像素 → 经纬度」的换算关系；
  ② **描图**：配准完成后，你在图上的每一次点击都会自动记成一个经纬度点，
     连起来就是一条边界；导出成 JSON 可直接粘进 config/map.json。

【为什么游戏里不用官方底图】
官方标准地图一经修改（叠加内容）用于公开传播需重新送审。所以推荐做法是：
**官方图只作你描图时的参考（不进仓库），游戏里放你描出来的矢量** ——
矢量既是你自己的作品，又能无限缩放、体积还小。

【用法】
    python tools/描图工作台.py                  # 打开工作台
    python tools/描图工作台.py 参考图.png         # 启动时直接载入参考图
    python tools/描图工作台.py --参考 docs/地图精度预览.html   # 不行：这里要的是图片

操作步骤（窗口左上角也有同样的提示）：
    第 1 步【载入参考图】  选择你的参考地图（PNG / GIF；JPG 需先转成 PNG）
    第 2 步【配准】        点"开始配准"→ 在图上依次点地标 → 每次在弹出的框里填"经度,纬度"
                           至少 3 个、尽量分散（例如一个在西南、一个在东北、一个居中）
    第 3 步【描图】        点"开始描图"→ 在图上连续点击，连成边界 → 回车或点"闭合"
    第 4 步【导出】        点"导出 JSON"，把结果粘进 config/map.json
    中途可随时"保存工作/载入工作"，下次接着画（文件：描图工作.json）

依赖：仅标准库（tkinter）。参考图会被缩放显示，但**配准按原始像素计算**，精度不受缩放影响。
"""
import json
import math
import os
import sys
import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog, ttk

根目录 = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(根目录, "ui"))
sys.path.insert(0, os.path.join(根目录, "src"))

import 地图  # noqa: E402  （复用同一套投影，保证与游戏内地图完全对齐）

工作文件 = os.path.join(根目录, "描图工作.json")
背景色, 面板色, 边色 = "#222831", "#f7f4ec", "#c9bfa8"
提示语 = ("第1步 载入参考图 → 第2步 配准（点≥3个地标，填真实经纬度）→ "
        "第3步 描图（连续点击）→ 第4步 导出 JSON")


# ══════════════════════════════════════════════════════════════════
#  一、配准数学（纯函数，可单独测试）
# ══════════════════════════════════════════════════════════════════
def 解仿射(像素点们, 世界点们):
    """由若干「图像像素 ↔ 世界坐标」对应点解出仿射变换（最小二乘）。

    求 x = a·u + b·v + c， y = d·u + e·v + f（u,v 为图像像素，x,y 为投影后世界坐标）。
    3 个点即可精确求解；多于 3 个点用最小二乘（更稳）。返回系数元组或 None（点数不足/退化）。
    """
    if len(像素点们) < 3:
        return None
    # 构造 A·[a,b,c]ᵀ = X 与 A·[d,e,f]ᵀ = Y 的正规方程 AᵀA·θ = Aᵀb
    A = [[u, v, 1.0] for u, v in 像素点们]
    ATA = [[sum(A[k][i] * A[k][j] for k in range(len(A))) for j in range(3)] for i in range(3)]
    ATX = [sum(A[k][i] * 世界点们[k][0] for k in range(len(A))) for i in range(3)]
    ATY = [sum(A[k][i] * 世界点们[k][1] for k in range(len(A))) for i in range(3)]
    行列式 = (ATA[0][0] * (ATA[1][1] * ATA[2][2] - ATA[1][2] * ATA[2][1])
           - ATA[0][1] * (ATA[1][0] * ATA[2][2] - ATA[1][2] * ATA[2][0])
           + ATA[0][2] * (ATA[1][0] * ATA[2][1] - ATA[1][1] * ATA[2][0]))
    if abs(行列式) < 1e-12:
        return None                      # 三点共线等退化情形
    def 解(右端):
        逆 = []
        for i in range(3):
            行 = []
            for j in range(3):
                子 = [[ATA[r][c] for c in range(3) if c != j] for r in range(3) if r != i]
                代数余子式 = (子[0][0] * 子[1][1] - 子[0][1] * 子[1][0]) * (-1) ** (i + j)
                行.append(代数余子式)
            逆.append(行)
        # 逆 = 伴随矩阵ᵀ / 行列式
        return [sum(逆[j][i] * 右端[j] for j in range(3)) / 行列式 for i in range(3)]
    a, b, c = 解(ATX)
    d, e, f = 解(ATY)
    return (a, b, c, d, e, f)


def 像素转世界(系数, u, v):
    a, b, c, d, e, f = 系数
    return (a * u + b * v + c, d * u + e * v + f)


def 世界转经纬(世界x, 世界y):
    """投影的逆运算 —— 直接复用 ui/地图.py（换了投影这里自动跟着变）。"""
    return 地图.逆投影(世界x, 世界y)


def 残差折算度(误差们, 世界点们):
    """把"世界像素"残差折算成"度"（人看得懂的量）。

    圆锥投影下"1 像素 = 多少度"随纬度变化（中国范围内约 ±5%），
    所以按每个控制点各自纬度的局部比例尺逐点折算，再取最大值，而不是除以一个常数。
    """
    if not 误差们:
        return None
    纬度们 = [地图.逆投影(x, y)[1] for x, y in 世界点们]
    return round(max(误差 * 地图.度每像素(纬度) for 误差, 纬度 in zip(误差们, 纬度们)), 4)


def 残差(像素点们, 世界点们, 系数):
    """配准误差（世界像素单位）——用于告诉用户"配准准不准"。"""
    误差 = []
    for (u, v), (x, y) in zip(像素点们, 世界点们):
        px, py = 像素转世界(系数, u, v)
        误差.append(math.hypot(px - x, py - y))
    return 误差


def 解四参数(像素点们, 世界点们):
    """解「横纵独立缩放 + 平移」的四参数变换（x = sx·u + tx，y = sy·v + ty）。

    为什么还要一个四参数？——整幅地图的仿射是六参数，但 **tkinter 的 Canvas 不能平滑缩放位图**
    （只有整数倍的 zoom / subsample），所以游戏内底图只能按固定的整数缩放级别绘制。
    把六参数退化成"只有缩放和平移、没有旋转和错切"的四参数后，游戏内就能直接用
    `图像坐标 × 缩放 + 平移` 一步换算到画布坐标，不需要每帧重采样图片。

    代价是精度略低于六参数（官方标准地图是正射的，旋转/错切本来就接近 0，
    所以两者残差通常只差一个很小的量）。返回 (sx, tx, sy, ty) 或 None。
    """
    n = len(像素点们)
    if n < 2:
        return None

    def 一元(源, 目标):
        和源 = sum(源)
        和目标 = sum(目标)
        和积 = sum(s * t for s, t in zip(源, 目标))
        和方 = sum(s * s for s in 源)
        分母 = n * 和方 - 和源 * 和源
        if abs(分母) < 1e-12:
            return None                     # 所有地标在这一维上重合，退化
        斜率 = (n * 和积 - 和源 * 和目标) / 分母
        return (斜率, (和目标 - 斜率 * 和源) / n)

    横 = 一元([p[0] for p in 像素点们], [q[0] for q in 世界点们])
    纵 = 一元([p[1] for p in 像素点们], [q[1] for q in 世界点们])
    if 横 is None or 纵 is None:
        return None
    return (横[0], 横[1], 纵[0], 纵[1])


def 四参数残差(像素点们, 世界点们, 系数):
    """四参数变换的配准误差（世界像素单位）。"""
    sx, tx, sy, ty = 系数
    误差 = []
    for (u, v), (x, y) in zip(像素点们, 世界点们):
        误差.append(math.hypot(sx * u + tx - x, sy * v + ty - y))
    return 误差


# ══════════════════════════════════════════════════════════════════
#  二、工作台窗口
# ══════════════════════════════════════════════════════════════════
class 工作台(tk.Tk):

    def __init__(self, 初始图=None):
        super().__init__()
        self.title("蜀汉突围 · 配准描图工作台")
        self.geometry("1280x860")
        self.configure(bg=面板色)

        self.图片 = None
        self.图片尺寸 = (0, 0)
        self.缩放 = 1.0
        self.偏移 = [0.0, 0.0]
        self.状态 = "空闲"          # 空闲 / 配准 / 描图
        self.控制点像素 = []         # [(u, v), …]
        self.控制点世界 = []         # [(x, y), …]
        self.当前线 = []            # [(lon, lat), …]
        self.完成线们 = []           # [{"名":…, "点":[(lon,lat),…]}, …]
        self.系数 = None
        self.起始图 = 初始图

        self._建界面()
        if 初始图 and os.path.isfile(初始图):
            self.载入图片(初始图)
        self._重绘()

    # ── 界面 ──
    def _建界面(self):
        左 = ttk.Frame(self, padding=10)
        左.pack(side="left", fill="y")
        ttk.Label(左, text="配准描图工作台", font=("Microsoft YaHei UI", 13, "bold")).pack(anchor="w")
        ttk.Label(左, text=提示语, wraplength=250, justify="left",
                 foreground="#6f6558").pack(anchor="w", pady=(4, 10))

        框 = ttk.LabelFrame(左, text=" 1 参考图 ", padding=(8, 6))
        框.pack(fill="x", pady=4)
        ttk.Button(框, text="载入参考图…", command=self.选图片).pack(fill="x")
        self.图名 = ttk.Label(框, text="（未载入）", wraplength=230, foreground="#6f6558")
        self.图名.pack(anchor="w", pady=(4, 0))

        框 = ttk.LabelFrame(左, text=" 2 配准 ", padding=(8, 6))
        框.pack(fill="x", pady=4)
        self.配准钮 = ttk.Button(框, text="开始配准（点地标）", command=self.切换配准)
        self.配准钮.pack(fill="x")
        ttk.Label(框, text="已配准地标：", foreground="#6f6558").pack(anchor="w", pady=(6, 0))
        self.地标列表 = tk.Listbox(框, height=6, width=32)
        self.地标列表.pack(fill="x")
        ttk.Button(框, text="删除选中地标", command=self.删地标).pack(fill="x", pady=(4, 0))
        self.配准信息 = ttk.Label(框, text="尚未配准", wraplength=230, foreground="#8c3b3b")
        self.配准信息.pack(anchor="w", pady=(4, 0))

        框 = ttk.LabelFrame(左, text=" 3 描图 ", padding=(8, 6))
        框.pack(fill="x", pady=4)
        self.描图钮 = ttk.Button(框, text="开始描图（连续点击）", command=self.切换描图)
        self.描图钮.pack(fill="x")
        钮行 = ttk.Frame(框)
        钮行.pack(fill="x", pady=(4, 0))
        ttk.Button(钮行, text="撤销一点", width=10, command=self.撤销点).pack(side="left")
        ttk.Button(钮行, text="闭合", width=8, command=self.闭合线).pack(side="left", padx=4)
        ttk.Button(框, text="清空当前线", command=self.清空线).pack(fill="x", pady=(4, 0))
        self.描图信息 = ttk.Label(框, text="当前线：0 点", foreground="#6f6558")
        self.描图信息.pack(anchor="w", pady=(4, 0))

        框 = ttk.LabelFrame(左, text=" 4 导出 ", padding=(8, 6))
        框.pack(fill="x", pady=4)
        ttk.Button(框, text="导出 JSON（当前线）", command=self.导出).pack(fill="x")
        ttk.Button(框, text="保存工作 / 载入工作", command=self.保存工作).pack(fill="x", pady=(4, 0))
        ttk.Button(框, text="载入上次工作", command=self.载入工作).pack(fill="x", pady=(4, 0))

        框 = ttk.LabelFrame(左, text=" 视图 ", padding=(8, 6))
        框.pack(fill="x", pady=4)
        ttk.Button(框, text="适应窗口", command=self.适应窗口).pack(fill="x")
        self.显示州界 = tk.BooleanVar(value=True)
        ttk.Checkbutton(框, text="叠加现有州界（对照）", variable=self.显示州界,
                       command=self._重绘).pack(anchor="w")

        # 画布
        右 = ttk.Frame(self)
        右.pack(side="right", fill="both", expand=True, padx=(0, 10), pady=10)
        self.画布 = tk.Canvas(右, background=背景色, highlightthickness=0, cursor="crosshair")
        self.画布.pack(fill="both", expand=True)
        self.画布.bind("<Button-1>", self.点画布)
        self.画布.bind("<Motion>", self.移画布)
        self.画布.bind("<MouseWheel>", self.滚轮)
        self.画布.bind("<ButtonPress-2>", self.按下中键)
        self.画布.bind("<B2-Motion>", self.拖中键)
        self.画布.bind("<Configure>", lambda 事件: self._重绘())

        self.状态栏 = ttk.Label(self, text="就绪", padding=(12, 4))
        self.状态栏.pack(side="bottom", fill="x")

    # ── 参考图 ──
    def 选图片(self):
        路径 = filedialog.askopenfilename(
            title="选择参考地图（PNG / GIF；JPG 请先转成 PNG）",
            filetypes=[("图片", "*.png *.gif *.ppm *.pgm"), ("全部文件", "*.*")])
        if 路径:
            self.载入图片(路径)

    def 载入图片(self, 路径):
        try:
            self.图片 = tk.PhotoImage(file=路径)
        except Exception as 异常:
            messagebox.showerror("载入失败",
                              f"这张图 tkinter 读不了：{异常}\n\n"
                              f"• 支持 PNG / GIF / PPM；JPG 需要先转成 PNG\n"
                              f"• 转换命令（构建期工具，可选）：python -c \"from PIL import Image;"
                              f"Image.open('旧.jpg').save('新.png')\"")
            return
        self.图片尺寸 = (self.图片.width(), self.图片.height())
        self.起始图 = 路径
        self.图名.configure(text=os.path.basename(路径) + f"（{self.图片尺寸[0]}×{self.图片尺寸[1]}）")
        self.适应窗口()
        self._设状态("参考图已载入。下一步：点「开始配准」，在图上点地标并填它的真实经纬度。")

    def 适应窗口(self):
        if not self.图片:
            return
        宽, 高 = max(self.画布.winfo_width(), 100), max(self.画布.winfo_height(), 100)
        图宽, 图高 = self.图片尺寸
        self.缩放 = min(宽 / 图宽, 高 / 图高)
        self.偏移 = [(宽 - 图宽 * self.缩放) / 2, (高 - 图高 * self.缩放) / 2]
        self._重绘()

    # ── 坐标换算：屏幕 ↔ 图像像素 →（配准）→ 经纬度 ──
    def 屏幕到像素(self, 屏幕x, 屏幕y):
        return ((屏幕x - self.偏移[0]) / self.缩放, (屏幕y - self.偏移[1]) / self.缩放)

    def 像素到屏幕(self, u, v):
        return (u * self.缩放 + self.偏移[0], v * self.缩放 + self.偏移[1])

    def 屏幕到经纬(self, 屏幕x, 屏幕y):
        if self.系数 is None:
            return None
        u, v = self.屏幕到像素(屏幕x, 屏幕y)
        世界x, 世界y = 像素转世界(self.系数, u, v)
        return 世界转经纬(世界x, 世界y)

    # ── 配准 ──
    def 切换配准(self):
        if not self.图片:
            messagebox.showinfo("先载入参考图", "第 1 步要先把参考图载进来。")
            return
        self.状态 = "配准" if self.状态 != "配准" else "空闲"
        self.配准钮.configure(text="结束配准" if self.状态 == "配准" else "开始配准（点地标）")
        self.描图钮.configure(text="开始描图（连续点击）")
        self._设状态("配准中：在图上点一个认得出的地标（城市/河口等），然后填它的真实经纬度。"
                  "至少 3 个，越分散越准。")

    def 加地标(self, 屏幕x, 屏幕y):
        u, v = self.屏幕到像素(屏幕x, 屏幕y)
        if not (0 <= u <= self.图片尺寸[0] and 0 <= v <= self.图片尺寸[1]):
            self._设状态("点跑到参考图外面了，请在图上点。")
            return
        文本 = simpledialog.askstring(
            "输入该地标的真实经纬度",
            f"你在图上点的是哪里？请填它的真实经纬度：\n\n"
            f"格式：经度,纬度　（例：113.6,34.7 是郑州；104.1,30.6 是成都）\n"
            f"也可以直接填《地图精度预览》或常识里的城市坐标。\n\n"
            f"当前已配准 {len(self.控制点像素)} 个，至少需要 3 个。",
            parent=self)
        if not 文本:
            return
        try:
            经度, 纬度 = [float(x.strip()) for x in 文本.replace("，", ",").split(",")[:2]]
        except Exception:
            messagebox.showerror("格式不对", "请按「经度,纬度」填写，例如 113.6,34.7")
            return
        self.控制点像素.append((u, v))
        self.控制点世界.append(地图.投影(经度, 纬度))
        self.更新配准()

    def 更新配准(self):
        self.地标列表.delete(0, "end")
        for i, ((u, v), (x, y)) in enumerate(zip(self.控制点像素, self.控制点世界), 1):
            经度, 纬度 = 世界转经纬(x, y)
            self.地标列表.insert("end", f"{i}. 图({u:.0f},{v:.0f}) → {经度:.2f},{纬度:.2f}")
        self.系数 = 解仿射(self.控制点像素, self.控制点世界) if len(self.控制点像素) >= 3 else None
        if self.系数 is None:
            self.配准信息.configure(
                text=f"已点 {len(self.控制点像素)} 个地标；至少需要 3 个（且不能共线）",
                foreground="#8c3b3b")
        else:
            误差 = 残差(self.控制点像素, self.控制点世界, self.系数)
            最大 = 残差折算度(误差, self.控制点世界)     # 换算成度，直观一些
            self.配准信息.configure(
                text=f"✅ 配准完成（{len(误差)} 点，最大残差 ≈ {最大:.3f}°）\n"
                     f"{'残差偏大，建议加更分散的地标' if 最大 > 0.15 else '精度可用'}",
                foreground="#2f6b3f" if 最大 <= 0.15 else "#a0301f")
            self._导出配准()
        self._重绘()

    def _导出配准(self):
        """把配准结果落成 配准.json —— 游戏内底图直接读这个文件，不用把系数抄进代码里。

        文件写在仓库根目录，属于"构建期产物"：换底图时重跑一次工作台即可重新生成，
        游戏代码不需要任何改动（这就是溯源 B 层「变更可查」想要的效果）。
        """
        一般 = self.系数
        简化 = 解四参数(self.控制点像素, self.控制点世界)
        点们 = []
        for (u, v), (x, y) in zip(self.控制点像素, self.控制点世界):
            经度, 纬度 = 世界转经纬(x, y)
            点们.append({"像素": [round(u, 2), round(v, 2)],
                        "世界": [round(x, 2), round(y, 2)],
                        "经纬": [round(经度, 4), round(纬度, 4)]})

        def 残差度(误差们, 世界点们):
            return 残差折算度(误差们, 世界点们)

        数据 = {
            "说明": ("由 tools/描图工作台.py 导出。游戏内底图据此把图片像素换算成经纬度；"
                    "换底图后重跑工作台即可，游戏代码不用改。"),
            "来源": "人工描图（在工作台上手点地标）",
            "图像": os.path.relpath(self.起始图, 根目录).replace("\\", "/") if self.起始图 else "",
            "图像宽高": list(self.图片尺寸),
            "控制点": 点们,
            "一般仿射": {
                "含义": "x = a·u + b·v + c；y = d·u + e·v + f（u,v 为图像像素，x,y 为投影世界坐标）",
                "系数": [round(值, 10) for 值 in 一般],
                "最大残差_度": 残差度(残差(self.控制点像素, self.控制点世界, 一般), self.控制点世界),
            },
            "简化四参数": {
                "含义": "x = sx·u + tx；y = sy·v + ty（无旋转/错切，供 tkinter 定点缩放底图用）",
                "系数": [round(值, 10) for 值 in 简化] if 简化 else None,
                "最大残差_度": 残差度(四参数残差(self.控制点像素, self.控制点世界, 简化),
                                     self.控制点世界) if 简化 else None,
            },
            "投影": {"中央经线": 地图.中央经线, "圆锥常数": 地图.圆锥常数,
                   "参考纬度": 地图.参考纬度, "缩放": 地图.缩放},
        }
        路径 = os.path.join(根目录, "config", "底图配准.json")
        with open(路径, "w", encoding="utf-8", newline="\n") as 文件:
            json.dump(数据, 文件, ensure_ascii=False, indent=1)
        self._设状态(f"配准已写入 {os.path.relpath(路径, 根目录)}（游戏底图会读它）")

    def 删地标(self):
        选中 = self.地标列表.curselection()
        if not 选中:
            return
        i = 选中[0]
        if i < len(self.控制点像素):
            self.控制点像素.pop(i)
            self.控制点世界.pop(i)
            self.更新配准()

    # ── 描图 ──
    def 切换描图(self):
        if self.系数 is None:
            messagebox.showinfo("先完成配准", "描图前必须先配准：至少要 3 个地标，否则点上去不知道是哪儿。")
            return
        self.状态 = "描图" if self.状态 != "描图" else "空闲"
        self.描图钮.configure(text="结束描图" if self.状态 == "描图" else "开始描图（连续点击）")
        self.配准钮.configure(text="开始配准（点地标）")
        self._设状态("描图中：连续点击连成边界；回车或点「闭合」结束这条线；可随时撤销。")

    def 加描点(self, 屏幕x, 屏幕y):
        经纬 = self.屏幕到经纬(屏幕x, 屏幕y)
        if 经纬 is None:
            return
        self.当前线.append(经纬)
        self.描图信息.configure(text=f"当前线：{len(self.当前线)} 点，末点 "
                              f"{经纬[0]:.3f},{经纬[1]:.3f}")
        self._重绘()

    def 撤销点(self):
        if self.当前线:
            self.当前线.pop()
            self.描图信息.configure(text=f"当前线：{len(self.当前线)} 点")
            self._重绘()

    def 清空线(self):
        if self.当前线 and not messagebox.askyesno("清空", "丢弃当前这条线？"):
            return
        self.当前线 = []
        self.描图信息.configure(text="当前线：0 点")
        self._重绘()

    def 闭合线(self):
        if len(self.当前线) < 3:
            messagebox.showinfo("点太少", "边界至少要 3 个点。")
            return
        名 = simpledialog.askstring("命名这条边界", "给这条边界起个名字（例如：南阳郡）：", parent=self)
        if not 名:
            return
        self.完成线们.append({"名": 名, "点": [tuple(p) for p in self.当前线]})
        self.当前线 = []
        self.描图信息.configure(text=f"当前线：0 点（已完成 {len(self.完成线们)} 条）")
        self._set_title()
        self._重绘()

    def _set_title(self):
        self.title(f"蜀汉突围 · 配准描图工作台 —— 已完成 {len(self.完成线们)} 条边界")

    # ── 鼠标 ──
    def 点画布(self, 事件):
        if self.状态 == "配准":
            self.加地标(事件.x, 事件.y)
        elif self.状态 == "描图":
            self.加描点(事件.x, 事件.y)

    def 移画布(self, 事件):
        经纬 = self.屏幕到经纬(事件.x, 事件.y)
        if 经纬 is None:
            self.状态栏.configure(text="（未配准：先点「开始配准」，或忽略此处）")
        else:
            self.状态栏.configure(text=f"光标经纬度：{经纬[0]:.4f}, {经纬[1]:.4f}"
                                  f"　｜　缩放 {self.缩放:.2f}×　｜　{self.状态}")

    def 滚轮(self, 事件):
        因子 = 1.15 if 事件.delta > 0 else 1 / 1.15
        u, v = self.屏幕到像素(事件.x, 事件.y)
        self.缩放 = max(0.05, min(30.0, self.缩放 * 因子))
        self.偏移[0] = 事件.x - u * self.缩放
        self.偏移[1] = 事件.y - v * self.缩放
        self._重绘()

    def 按下中键(self, 事件):
        self._拖动到 = (事件.x, 事件.y, self.偏移[0], self.偏移[1])

    def 拖中键(self, 事件):
        if not hasattr(self, "_拖动到"):
            return
        起x, 起y, 偏x, 偏y = self._拖动到
        self.偏移 = [偏x + (事件.x - 起x), 偏y + (事件.y - 起y)]
        self._重绘()

    # ── 绘制 ──
    def _重绘(self):
        self.画布.delete("all")
        宽, 高 = self.画布.winfo_width(), self.画布.winfo_height()
        if self.图片:
            self.画布.create_image(self.偏移[0], self.偏移[1], anchor="nw",
                                 image=self.图片)
        else:
            self.画布.create_text(宽 / 2, 高 / 2, fill="#8899aa",
                                text="先载入参考图（左侧「1 参考图」）",
                                font=("Microsoft YaHei UI", 14))
        if self.显示州界.get():
            self._画现有州界()
        self._画控制点()
        self._画描线()

    def _画现有州界(self):
        """把 config/map.json 里现有的州界叠上来，便于对照调整。"""
        路径 = os.path.join(根目录, "config", "map.json")
        if not os.path.isfile(路径):
            return
        try:
            with open(路径, encoding="utf-8") as 文件:
                数据 = json.load(文件)
        except (OSError, json.JSONDecodeError):
            return
        for 州 in 数据.get("州", []):
            点们 = []
            for 经度, 纬度 in 州["边界"]:
                if self.系数 is None:
                    continue
                世界x, 世界y = 地图.投影(经度, 纬度)
                a, b, c, d, e, f = self.系数
                # 反解：由世界坐标 → 图像像素（系数可逆，此处用最小二乘解出的仿射直接求逆）
                行列式 = a * e - b * d
                if abs(行列式) < 1e-12:
                    continue
                u = (e * (世界x - c) - b * (世界y - f)) / 行列式
                v = (-d * (世界x - c) + a * (世界y - f)) / 行列式
                x, y = self.像素到屏幕(u, v)
                点们.extend((x, y))
            if len(点们) >= 6:
                self.画布.create_polygon(点们, outline="#ffcc44", width=1.4,
                                       fill="", dash=(5, 3))

    def _画控制点(self):
        for i, (u, v) in enumerate(self.控制点像素, 1):
            x, y = self.像素到屏幕(u, v)
            self.画布.create_oval(x - 5, y - 5, x + 5, y + 5, outline="#ff5555", width=2)
            self.画布.create_text(x + 9, y - 9, text=str(i), fill="#ff8888",
                                font=("Microsoft YaHei UI", 9, "bold"))

    def _画描线(self):
        if len(self.当前线) >= 2:
            平铺 = []
            for 经度, 纬度 in self.当前线:
                世界x, 世界y = 地图.投影(经度, 纬度)
                a, b, c, d, e, f = self.系数
                行列式 = a * e - b * d
                if abs(行列式) < 1e-12:
                    continue
                u = (e * (世界x - c) - b * (世界y - f)) / 行列式
                v = (-d * (世界x - c) + a * (世界y - f)) / 行列式
                x, y = self.像素到屏幕(u, v)
                平铺.extend((x, y))
            if len(平铺) >= 4:
                self.画布.create_line(平铺, fill="#44dd88", width=2)
            for i in range(0, len(平铺) - 1, 2):
                self.画布.create_oval(平铺[i] - 2, 平铺[i + 1] - 2,
                                   平铺[i] + 2, 平铺[i + 1] + 2,
                                   fill="#44dd88", outline="")
        for 线 in self.完成线们:
            self.画布.create_text(20, 20 + 16 * self.完成线们.index(线),
                                anchor="nw", fill="#44dd88",
                                text=f"✔ {线['名']}（{len(线['点'])} 点）",
                                font=("Microsoft YaHei UI", 10))

    # ── 导出 / 存档 ──
    def 导出(self):
        if not self.当前线 and not self.完成线们:
            messagebox.showinfo("没有内容", "先描一条边界（至少 3 个点）再导出。")
            return
        片段 = []
        for 线 in self.完成线们 + ([{"名": self._临时名(), "点": self.当前线}] if self.当前线 else []):
            片段.append({"名": 线["名"], "点数": len(线["点"]), "点": [[round(p[0], 4), round(p[1], 4)]
                                                              for p in 线["点"]]})
        路径 = os.path.join(根目录, "描图导出.json")
        with open(路径, "w", encoding="utf-8", newline="\n") as 文件:
            json.dump({"说明": "由 tools/描图工作台.py 导出，可直接粘进 config/map.json 的「州」数组",
                     "边界": 片段}, 文件, ensure_ascii=False, indent=1)
        预览 = json.dumps(片段[:1], ensure_ascii=False)[:400]
        messagebox.showinfo(
            "已导出",
            f"写到：{os.path.relpath(路径, 根目录)}\n\n"
            f"共 {len(片段)} 条边界。前 400 字符预览：\n{预览}…\n\n"
            f"下一步：把点列表粘进 config/map.json（或告诉我，我来接进游戏并补测试）。")
        self._设状态(f"已导出 {len(片段)} 条边界到 描图导出.json")

    def _临时名(self):
        return "未命名_" + str(len(self.完成线们) + 1)

    def 保存工作(self):
        数据 = {"控制点像素": self.控制点像素, "控制点世界": self.控制点世界,
              "当前线": self.当前线, "完成线们": self.完成线们,
              "起始图": self.起始图 or ""}
        with open(工作文件, "w", encoding="utf-8", newline="\n") as 文件:
            json.dump(数据, 文件, ensure_ascii=False)
        self._设状态(f"工作已保存：{os.path.relpath(工作文件, 根目录)}")

    def 载入工作(self):
        if not os.path.isfile(工作文件):
            messagebox.showinfo("没有存档", f"还没保存过工作（{os.path.relpath(工作文件, 根目录)}）。")
            return
        with open(工作文件, encoding="utf-8") as 文件:
            数据 = json.load(文件)
        self.控制点像素 = [tuple(p) for p in 数据.get("控制点像素", [])]
        self.控制点世界 = [tuple(p) for p in 数据.get("控制点世界", [])]
        self.当前线 = [tuple(p) for p in 数据.get("当前线", [])]
        self.完成线们 = [{"名": 线["名"], "点": [tuple(p) for p in 线["点"]]}
                     for 线 in 数据.get("完成线们", [])]
        if 数据.get("起始图") and os.path.isfile(数据["起始图"]):
            self.载入图片(数据["起始图"])
        self.更新配准()
        self._set_title()
        self._设状态(f"已载入工作：{len(self.完成线们)} 条边界、{len(self.控制点像素)} 个地标")

    def _设状态(self, 文本):
        self.状态栏.configure(text=文本)


def 主函数():
    try:
        探针 = tk.Tk()
        探针.destroy()
    except Exception as 异常:
        print(f"没有可用的图形环境：{异常!r}")
        return 1
    初始 = sys.argv[1] if len(sys.argv) > 1 and not sys.argv[1].startswith("-") else None
    工作台(初始).mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(主函数())
