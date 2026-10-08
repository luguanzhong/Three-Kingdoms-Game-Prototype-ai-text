# -*- coding: utf-8 -*-
"""《三国·蜀汉突围》图形界面（tkinter，Python 标准库，零第三方依赖）。

启动：
    python ui/主界面.py            # 直接运行
    python main.py --gui           # 从根入口进入

设计要点
--------
1. **界面不含任何游戏规则**。所有判定、结算、菜单流程都由引擎（src/蜀汉突围.py）完成，
   界面只做两件事：把状态画出来、把玩家意图送回去（见 src/游戏接口.py 的说明）。
2. **菜单即按钮**：引擎本来是用 print 打印菜单、用 input 读答案；本界面把引擎打印出来的
   「1. xxx / A. xxx」解析成可点击的按钮——因此**新增任何引擎菜单都不需要改界面代码**。
3. 存档为三个固定槽位（slot1~slot3），可存可读，槽位摘要直接读存档文件。
4. 打包：`python tools/打包exe.py` 生成单文件 exe（见该脚本说明）。
"""
import os
import re
import sys
import tkinter as tk
from tkinter import messagebox, ttk

# 生产模块位于 src/：无论从哪个目录启动都能找到
# 打包成 exe 后，模块由 PyInstaller 释放到 sys._MEIPASS，此时 sys.path 已包含该目录，
# 因此这里只在源码运行时按目录关系补路径（打包时不会用到）。
def _定位目录():
    if getattr(sys, "frozen", False):
        根 = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(sys.executable)))
        return 根, os.path.join(根, "src")
    return (os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))


仓库根目录, 源码目录 = _定位目录()
自己目录 = os.path.dirname(os.path.abspath(__file__))
for 目录 in (源码目录, 仓库根目录, 自己目录):
    if os.path.isdir(目录) and 目录 not in sys.path:
        sys.path.insert(0, 目录)

import 游戏接口  # noqa: E402  （本地模块）
import 资产  # noqa: E402  （本地模块：配色与字体一律经它读取）
import 地图  # noqa: E402  （本地模块：游戏内图形地图）

# 从引擎打印的菜单里认出「可点击选项」：1. xxx ／ A. xxx ／ 1、xxx ／ 1) xxx
选项模式 = re.compile(r"^\s*([0-9]{1,2}|[A-Za-z])[.、)]\s*(\S.*)$")

# 配色一律来自 assets/theme.json（经 ui/资产.py 读取），本文件不得写死颜色。
配色 = {
    "底": 资产.颜色("窗口底"), "面": 资产.颜色("面板底"), "边": 资产.颜色("边框"),
    "主字": 资产.颜色("主字"), "次字": 资产.颜色("次字"),
    "蜀": 资产.颜色("蜀汉"), "魏": 资产.颜色("曹魏"), "吴": 资产.颜色("东吴"),
}


class 选项对话框(tk.Toplevel):
    """把引擎打印的菜单变成可点选项的模态对话框。

    返回约定与引擎一致：**取消 → "0"**（引擎中 0 普遍表示"返回/放弃"）。
    """

    def __init__(self, 父窗口, 提示, 最近输出):
        super().__init__(父窗口)
        self.结果 = "0"
        self.title("请选择")
        self.configure(bg=配色["底"])
        self.resizable(False, False)
        self.transient(父窗口)

        提示 = (提示 or "").strip() or "请输入："
        # 选项可能出现在"提示文本"里（例如 请选择：1. 接受结盟  2. 婉拒：），也可能在刚打印的菜单里
        选项 = self._解析(提示) or self._解析("\n".join(最近输出[-30:]))

        外框 = ttk.Frame(self, padding=14)
        外框.pack(fill="both", expand=True)

        ttk.Label(外框, text=提示, style="提示.TLabel",
                  wraplength=430, justify="left").pack(anchor="w", pady=(0, 4))

        if 选项:
            ttk.Label(外框, text="可选项（点击即确认）：", style="次.TLabel").pack(anchor="w")
            钮框 = ttk.Frame(外框)
            钮框.pack(fill="x", pady=(4, 8))
            for 值, 文本 in 选项:
                ttk.Button(钮框, text=f"{值}. {文本}"[:58], width=52,
                           command=lambda 值=值: self._选定(值)).pack(fill="x", pady=2)

        手框 = ttk.Frame(外框)
        手框.pack(fill="x", pady=(8, 0))
        ttk.Label(手框, text="或手动输入：", style="次.TLabel").pack(side="left")
        self.输入框 = ttk.Entry(手框, width=14)
        self.输入框.pack(side="left", padx=6)
        self.输入框.bind("<Return>", lambda 事件: self._选定(self.输入框.get().strip()))
        ttk.Button(手框, text="确定", command=lambda: self._选定(self.输入框.get().strip())).pack(side="left")
        ttk.Button(手框, text="取消(返回)", command=self._取消).pack(side="left", padx=6)

        if not 选项:
            self.输入框.focus_set()

        self._居中(父窗口)
        self.grab_set()
        self.protocol("WM_DELETE_WINDOW", self._取消)
        self.wait_window(self)

    @staticmethod
    def _解析(文本):
        """按出现顺序抽取选项；遇到空行/非选项行则重置（只保留最后一段连续菜单）。"""
        结果 = []
        for 行 in 文本.splitlines():
            if not 行.strip():
                continue
            匹配 = 选项模式.match(行)
            if 匹配:
                结果.append((匹配.group(1), 匹配.group(2).strip()))
            else:
                结果 = []      # 不在菜单块里 → 清空，确保只取最后一段
        return 结果

    def _选定(self, 值):
        值 = (值 or "").strip()
        if 值 == "":
            值 = "0"
        self.结果 = 值
        self.destroy()

    def _取消(self):
        self.结果 = "0"
        self.destroy()

    def _居中(self, 父窗口):
        self.update_idletasks()
        宽, 高 = self.winfo_width(), self.winfo_height()
        x = 父窗口.winfo_rootx() + (父窗口.winfo_width() - 宽) // 2
        y = 父窗口.winfo_rooty() + (父窗口.winfo_height() - 高) // 3
        self.geometry(f"+{max(x, 0)}+{max(y, 0)}")


class 主窗口(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("三国 · 蜀汉突围")
        self.configure(bg=配色["底"])
        self.geometry("1280x900")
        self.minsize(1080, 740)
        self.会话 = 游戏接口.会话()
        self.自动演示中 = False
        self.地图数据, self.地图错误 = 地图.载入地图数据()
        self.骨架数据, self.骨架错误 = 地图.载入郡界骨架()
        self.图谱 = None
        self._建样式()
        self._建菜单()
        self._建布局()
        self.新开局(问确认=False)

    # ── 样式 ──
    def _建样式(self):
        样式 = ttk.Style(self)
        try:
            样式.theme_use("clam")
        except tk.TclError:
            pass
        样式.configure(".", background=配色["底"], foreground=配色["主字"],
                    font=资产.字体("正文", 10))
        样式.configure("TFrame", background=配色["底"])
        样式.configure("TLabel", background=配色["底"], foreground=配色["主字"])
        样式.configure("提示.TLabel", font=资产.字体("标题", 11, True),
                    foreground=资产.颜色("深字"))
        样式.configure("次.TLabel", foreground=配色["次字"], font=资产.字体("正文", 9))
        样式.configure("标题.TLabel", font=资产.字体("标题", 11, True), foreground=资产.颜色("标题字"))
        样式.configure("数值.TLabel", font=资产.字体("等宽", 11, True))
        样式.configure("TLabelframe", background=配色["底"], bordercolor=配色["边"])
        样式.configure("TLabelframe.Label", background=配色["底"], foreground=资产.颜色("小标题字"),
                    font=资产.字体("标题", 10, True))
        样式.configure("TButton", padding=(6, 5))
        样式.configure("行动.TButton", font=资产.字体("标题", 10, True), padding=(6, 8))
        样式.configure("回合.TButton", font=资产.字体("标题", 11, True), padding=(6, 10))
        样式.configure("Treeview", rowheight=23, fieldbackground=配色["面"])
        样式.configure("Treeview.Heading", font=资产.字体("标题", 9, True))

    # ── 菜单栏 ──
    def _建菜单(self):
        条 = tk.Menu(self)
        游戏 = tk.Menu(条, tearoff=0)
        游戏.add_command(label="新开局", accelerator="Ctrl+N", command=lambda: self.新开局())
        游戏.add_separator()
        读取 = tk.Menu(游戏, tearoff=0)
        保存 = tk.Menu(游戏, tearoff=0)
        for 槽位 in 游戏接口.槽位们:
            名 = 游戏接口.槽位显示名[槽位]
            读取.add_command(label=名, command=lambda 槽位=槽位: self.读档(槽位))
            保存.add_command(label=名, command=lambda 槽位=槽位: self.存档(槽位))
        游戏.add_cascade(label="读取存档", menu=读取)
        游戏.add_cascade(label="保存到槽位", menu=保存)
        游戏.add_separator()
        游戏.add_command(label="退出", accelerator="Alt+F4", command=self.退出)
        条.add_cascade(label="游戏", menu=游戏)

        视图 = tk.Menu(条, tearoff=0)
        视图.add_command(label="刷新局面", command=self.刷新)
        视图.add_command(label="清空战报", command=lambda: self._写战报("（战报已清空）", 清空=True))
        条.add_cascade(label="视图", menu=视图)

        帮助 = tk.Menu(条, tearoff=0)
        帮助.add_command(label="玩法速览", command=self._玩法速览)
        帮助.add_command(label="关于", command=self._关于)
        条.add_cascade(label="帮助", menu=帮助)
        self.config(menu=条)
        self.bind("<Control-n>", lambda 事件: self.新开局())

    # ── 布局 ──
    def _建布局(self):
        self.columnconfigure(0, weight=0)
        self.columnconfigure(1, weight=1)
        self.columnconfigure(2, weight=0)
        self.rowconfigure(1, weight=1)
        self.rowconfigure(2, weight=0)

        # 顶部信息条
        顶 = ttk.Frame(self, padding=(12, 8, 12, 4))
        顶.grid(row=0, column=0, columnspan=3, sticky="ew")
        self.顶部标签 = ttk.Label(顶, text="", style="标题.TLabel")
        self.顶部标签.pack(side="left")
        self.大事标签 = ttk.Label(顶, text="", style="次.TLabel")
        self.大事标签.pack(side="right")

        # 左：局势
        左 = ttk.Frame(self, padding=(12, 0, 6, 8))
        左.grid(row=1, column=0, sticky="nsw")
        self._建局势面板(左)

        # 中：图形地图（主区） + 工具栏 + 数据表标签页（下移）
        中 = ttk.Frame(self, padding=(6, 0, 6, 8))
        中.grid(row=1, column=1, sticky="nsew")
        中.columnconfigure(0, weight=1)
        中.rowconfigure(1, weight=1)

        工具 = ttk.Frame(中)
        工具.grid(row=0, column=0, sticky="ew", pady=(0, 4))
        ttk.Label(工具, text="战区地图", style="标题.TLabel").pack(side="left")
        for 文字, 命令 in (("放大 ＋", lambda: self._地图缩放(1.3)),
                        ("缩小 －", lambda: self._地图缩放(1 / 1.3)),
                        ("适应全图", lambda: self._地图动作("适应全图")),
                        ("居中战场", lambda: self._地图动作("居中战场"))):
            ttk.Button(工具, text=文字, width=9, command=命令).pack(side="right", padx=2)
        # 郡界骨架开关（骨架是几何推断，必须能一眼关掉、也要能一眼看出它是骨架）
        self.骨架开关 = tk.BooleanVar(value=True)
        self.粗骨架开关 = tk.BooleanVar(value=False)
        ttk.Checkbutton(工具, text="郡界骨架", variable=self.骨架开关,
                       command=self._切换骨架).pack(side="right", padx=(8, 0))
        ttk.Checkbutton(工具, text="含仅治所（虚线·更不可信）", variable=self.粗骨架开关,
                       command=self._切换骨架).pack(side="right", padx=(8, 0))
        self.地图提示 = ttk.Label(工具, text="", style="次.TLabel")
        self.地图提示.pack(side="left", padx=(10, 0))

        if self.地图数据 is None:
            框 = ttk.LabelFrame(中, text=" 战区地图 ", padding=10)
            框.grid(row=1, column=0, sticky="nsew")
            ttk.Label(框, text="地图不可用：\n" + "\n".join(self.地图错误)
                     + "\n\n（游戏其余功能不受影响；config/map.json 修复后重启即可）",
                     style="次.TLabel", justify="left").pack(anchor="w")
        else:
            self.图谱 = 地图.地图画布(中, self.地图数据, 城池回调=self.城池被点击,
                                骨架数据=self.骨架数据)
            self.图谱.grid(row=1, column=0, sticky="nsew")
            有依据 = len(self.图谱.骨架郡们(False)) if self.骨架数据 else 0
            提示 = f"郡界骨架：{有依据} 郡（有属县依据）· 悬停可看古今对照"
            if self.骨架数据 is None:
                提示 = "（郡界骨架未载入；" + (self.骨架错误[0] if self.骨架错误 else "") + "）"
            self.地图提示.configure(text=提示)

        self.书 = ttk.Notebook(中, height=176)
        self.书.grid(row=2, column=0, sticky="ew", pady=(6, 0))
        self.将领表 = self._建表格(self.书, "将领", ("姓名", "位置", "任务", "子任务", "指令", "状态"),
                              (58, 58, 84, 54, 74, 54))
        self.书.add(self.将领表.master, text="  将领  ")
        self.魏城表 = self._建表格(self.书, "城池", ("城池", "归属", "守军", "粮草", "守将"),
                             (72, 58, 74, 66, 64))
        self.书.add(self.魏城表.master, text="  曹魏城池  ")
        self.蜀城表 = self._建表格(self.书, "城池", ("城池", "兵力", "驻将"),
                             (72, 78, 180))
        self.书.add(self.蜀城表.master, text="  蜀汉城池  ")
        态势框 = ttk.Frame(self.书)
        态势框.rowconfigure(0, weight=1)
        态势框.columnconfigure(0, weight=1)
        self.态势文本 = tk.Text(态势框, wrap="none", font=资产.字体("等宽", 9),
                           bg=资产.颜色("日志底"), fg=资产.颜色("日志字"), insertbackground=资产.颜色("日志字"),
                           relief="flat", padx=10, pady=6, height=9)
        self.态势文本.grid(row=0, column=0, sticky="nsew")
        滚 = ttk.Scrollbar(态势框, orient="vertical", command=self.态势文本.yview)
        滚.grid(row=0, column=1, sticky="ns")
        self.态势文本.configure(yscrollcommand=滚.set, state="disabled")
        self.书.add(态势框, text="  战区态势图（文字版·调试用）  ")

        # 右：行动 + 存档位
        右 = ttk.Frame(self, padding=(6, 0, 12, 8))
        右.grid(row=1, column=2, sticky="nse")
        self._建行动面板(右)
        self._建存档面板(右)

        # 底：战报
        底 = ttk.LabelFrame(self, text=" 战报 ", padding=(8, 4, 8, 8))
        底.grid(row=2, column=0, columnspan=3, sticky="nsew", padx=12, pady=(0, 6))
        底.columnconfigure(0, weight=1)
        self.战报 = tk.Text(底, height=11, wrap="word", font=资产.字体("正文", 10),
                         bg=资产.颜色("面板底"), fg=资产.颜色("标签字"), relief="flat", padx=8, pady=6)
        self.战报.grid(row=0, column=0, sticky="nsew")
        战滚 = ttk.Scrollbar(底, orient="vertical", command=self.战报.yview)
        战滚.grid(row=0, column=1, sticky="ns")
        self.战报.configure(yscrollcommand=战滚.set, state="disabled")

        # 状态栏
        self.状态 = ttk.Label(self, text="就绪", style="次.TLabel", padding=(14, 0, 12, 8))
        self.状态.grid(row=3, column=0, columnspan=3, sticky="ew")

    def _建局势面板(self, 父):
        框 = ttk.LabelFrame(父, text=" 局势 ", padding=(10, 6, 10, 8))
        框.pack(fill="x")
        self.局势标签 = {}
        行定义 = [
            ("回合", "回合"), ("日期", "日期"), ("季节", "季节"),
            ("蜀汉兵力", "蜀汉兵力"), ("有效兵力", "有效兵力"), ("精锐比例", "精锐比例"),
            ("粮草", "粮草"), ("民心", "民心"), ("魏国压力", "魏国压力"),
            ("东吴好感", "东吴好感"), ("东吴观望", "东吴观望"), ("外交倾向", "外交倾向"),
            ("控制城池", "控制城池"), ("势力值比", "势力值比"),
        ]
        for 序号, (键, 标签) in enumerate(行定义):
            ttk.Label(框, text=标签, style="次.TLabel").grid(row=序号, column=0, sticky="w", pady=1)
            值 = ttk.Label(框, text="—", style="数值.TLabel")
            值.grid(row=序号, column=1, sticky="e", padx=(10, 0), pady=1)
            self.局势标签[键] = 值
        框.columnconfigure(0, weight=1)

        情报框 = ttk.LabelFrame(父, text=" 情报 ", padding=(10, 6, 10, 8))
        情报框.pack(fill="x", pady=(8, 0))
        self.情报标签 = ttk.Label(情报框, text="—", style="次.TLabel", justify="left")
        self.情报标签.pack(anchor="w")

        盟框 = ttk.LabelFrame(父, text=" 外交状态 ", padding=(10, 6, 10, 8))
        盟框.pack(fill="x", pady=(8, 0))
        self.盟约标签 = ttk.Label(盟框, text="—", style="次.TLabel", justify="left")
        self.盟约标签.pack(anchor="w")

    def _建表格(self, 父, 名称, 列, 宽度):
        框 = ttk.Frame(父)
        框.rowconfigure(0, weight=1)
        框.columnconfigure(0, weight=1)
        表 = ttk.Treeview(框, columns=列, show="headings", height=8)
        for 名, 宽 in zip(列, 宽度):
            表.heading(名, text=名)
            表.column(名, width=宽, anchor="center", stretch=(名 in ("驻将",)))
        表.grid(row=0, column=0, sticky="nsew")
        滚 = ttk.Scrollbar(框, orient="vertical", command=表.yview)
        滚.grid(row=0, column=1, sticky="ns")
        表.configure(yscrollcommand=滚.set)
        表.tag_configure("殁", foreground=资产.颜色("已殁灰"))
        表.tag_configure("俘", foreground=资产.颜色("危险"))
        表.tag_configure("伤", foreground=资产.颜色("重伤橙"))
        return 表

    def _建行动面板(self, 父):
        框 = ttk.LabelFrame(父, text=" 决策 ", padding=(10, 8, 10, 10))
        框.pack(fill="x")
        self.行动按钮 = {}
        for 行动 in 游戏接口.行动表:
            钮 = ttk.Button(框, text=行动["标题"], style="行动.TButton", width=20,
                          command=lambda 键=行动["键"]: self.执行行动(键))
            钮.pack(fill="x", pady=2)
            self.行动按钮[行动["键"]] = 钮
            ttk.Label(框, text=行动["说明"], style="次.TLabel",
                     wraplength=176, justify="left").pack(anchor="w", pady=(0, 4))
        ttk.Separator(框).pack(fill="x", pady=(2, 8))
        self.结束按钮 = ttk.Button(框, text="结束本回合，推进结算  ▶", style="回合.TButton",
                              command=self.结束回合)
        self.结束按钮.pack(fill="x")
        self.自动按钮 = ttk.Button(框, text="自动演示本局（到结局）", command=self.自动演示)
        self.自动按钮.pack(fill="x", pady=(6, 0))

    def _建存档面板(self, 父):
        框 = ttk.LabelFrame(父, text=" 存档位 ", padding=(10, 8, 10, 10))
        框.pack(fill="x", pady=(8, 0))
        self.槽位标签 = {}
        for 序号, 槽位 in enumerate(游戏接口.槽位们):
            行 = ttk.Frame(框)
            行.pack(fill="x", pady=3)
            说明 = ttk.Label(行, text="—", style="次.TLabel", wraplength=176, justify="left")
            说明.pack(anchor="w")
            钮行 = ttk.Frame(行)
            钮行.pack(anchor="w", pady=(2, 0))
            ttk.Button(钮行, text=f"存入{序号 + 1}", width=8,
                       command=lambda 槽位=槽位: self.存档(槽位)).pack(side="left")
            ttk.Button(钮行, text=f"读取{序号 + 1}", width=8,
                       command=lambda 槽位=槽位: self.读档(槽位)).pack(side="left", padx=4)
            self.槽位标签[槽位] = 说明
        读取 = ttk.Button(框, text="刷新存档列表", command=self.刷新槽位)
        读取.pack(fill="x", pady=(6, 0))

    # ── 会话驱动 ──
    def 新开局(self, 问确认=True):
        if 问确认 and not messagebox.askyesno(
                "新开局", "将放弃当前进度（未存档的部分会丢失），确定开始新的一局？"):
            return
        self.自动演示中 = False
        self._写战报("", 清空=True)          # 先清空，再让引擎把开局画面写进来
        try:
            self.会话.新开局(输出回调=self._写战报, 询问回调=self._询问)
        except Exception as 异常:      # 引擎自身出错也要给出可读提示，而不是让界面崩掉
            messagebox.showerror("开局失败", f"引擎启动失败：{异常!r}")
            return
        self.刷新槽位()
        self.刷新()
        self._设状态("新开局就绪：每回合只能执行一件大事，先部署将领再考虑出兵。")

    def 执行行动(self, 行动键):
        if self.自动演示中:
            messagebox.showinfo("自动演示中", "请先等自动演示结束（或关掉程序重开）。")
            return
        成功, 提示 = self.会话.执行行动(行动键)
        self.刷新()

    def 结束回合(self):
        if self.自动演示中:
            return
        有结局, 结局 = self.会话.结束回合()
        self.刷新()
        self.刷新槽位()
        if 有结局:
            self._报告结局(结局)

    def 存档(self, 槽位):
        名 = 游戏接口.槽位显示名[槽位]
        if self.会话.游戏 is None:
            return
        成功, 提示 = self.会话.保存到槽位(槽位)
        self._写战报(提示)
        self.刷新槽位()
        self._设状态(提示)
        if 成功:
            messagebox.showinfo("存档", 提示)

    def 读档(self, 槽位):
        名 = 游戏接口.槽位显示名[槽位]
        概览 = {项["槽位"]: 项 for 项 in self.会话.槽位概览()}
        if not 概览[槽位]["有档"]:
            messagebox.showwarning("读档", f"{名}是空档位，没有可读取的存档。")
            return
        if not messagebox.askyesno("读档", f"从{名}继续？当前未存档的进度会丢失。\n"
                                          f"存档内容：{概览[槽位]['摘要']}"):
            return
        成功, 提示 = self.会话.读档开局(槽位, 输出回调=self._写战报, 询问回调=self._询问)
        self._写战报(提示)
        self.刷新()
        self.刷新槽位()
        self._设状态(提示)
        if not 成功:
            messagebox.showerror("读档失败", 提示)

    def 自动演示(self):
        if self.自动演示中:
            return
        if self.会话.游戏 is None:
            return
        self.自动演示中 = True
        self._写战报("—— 自动演示开始（按引擎默认策略推演至结局）——")
        self._演示一步()

    def _演示一步(self):
        if not self.自动演示中:
            return
        有结局, 结局 = self.会话.自动演示一回合()
        self.刷新()
        if 有结局:
            self.自动演示中 = False
            self._报告结局(结局)
            return
        if self.会话.游戏.回合计数 > self.会话.游戏.总回合数:
            self.自动演示中 = False
            return
        self.after(60, self._演示一步)      # 让出事件循环，界面保持响应

    def 退出(self):
        if messagebox.askyesno("退出", "确定退出《三国·蜀汉突围》？"):
            self.destroy()

    # ── 与引擎交互 ──
    def _询问(self, 提示):
        """引擎调用 input() 时走这里：弹出选项对话框。"""
        self.update_idletasks()
        对话框 = 选项对话框(self, 提示, self._最近战报行())
        return 对话框.结果

    def _写战报(self, 文本, 清空=False):
        self.战报.configure(state="normal")
        if 清空:
            self.战报.delete("1.0", "end")
        else:
            self.战报.insert("end", 文本 + "\n")
        self.战报.see("end")
        self.战报.configure(state="disabled")

    def _最近战报行(self):
        return self.战报.get("1.0", "end").splitlines()

    # ── 刷新显示 ──
    def 刷新(self):
        局面 = self.会话.局面()
        if not 局面:
            return
        蜀 = 局面["蜀汉"]
        吴 = 局面["东吴"]
        势力比 = 局面["蜀汉势力值"] / max(局面["曹魏势力值"], 1)
        self.顶部标签.configure(
            text=f"第 {局面['回合']} / {局面['总回合']} 回合　·　{局面['日期']}　·　{局面['季节']}　"
                 f"·　{局面['控制城池']} 城在握")
        self.大事标签.configure(
            text=("本回合大事：已执行（请结束本回合）" if 局面["大事已用"] else "本回合大事：可用"),
            foreground=(资产.颜色("强调") if 局面["大事已用"] else 资产.颜色("成功")))

        值 = {
            "回合": f"{局面['回合']} / {局面['总回合']}",
            "日期": 局面["日期"],
            "季节": 局面["季节"],
            "蜀汉兵力": f"{蜀['兵力']:,}",
            "有效兵力": f"{局面['有效兵力']:,}",
            "精锐比例": f"{蜀.get('精锐比例', 0)}%",
            "粮草": f"{蜀['粮草']:,}",
            "民心": f"{蜀.get('民心', '—')}",
            "魏国压力": f"{蜀['魏国压力']}",
            "东吴好感": f"{蜀['东吴好感']}",
            "东吴观望": f"{吴['观望态度']}",
            "外交倾向": f"{局面['全局'].get('东吴外交倾向', '—')}"
                    + ("（已结盟）" if 局面["已结盟"] else ""),
            "控制城池": f"{局面['控制城池']}",
            "势力值比": f"{势力比:.2f}",
        }
        for 键, 显示 in 值.items():
            if 键 in self.局势标签:
                self.局势标签[键].configure(text=str(显示))
        情报 = 局面["情报"]
        情报行 = [f"{名}：{'已有' if 有 else '无'}" for 名, 有 in 情报.items()]
        self.情报标签.configure(text="\n".join(情报行) if 情报行 else "—")
        盟 = []
        盟.append("与东吴：已结盟" if 局面["已结盟"] else "与东吴：未结盟")
        围攻 = 局面["围攻"]
        盟.append(f"围攻中：{围攻['目标']}（还需 {围攻['剩余']} 回合）" if 围攻 else "围攻中：无")
        self.盟约标签.configure(text="\n".join(盟))

        self._填表(self.将领表, [
            (将["姓名"], 将["位置"], 将["任务"], 将["子任务"], 将["指令"], 将["状态"],
             "殁" if 将["状态"] == "已殁" else ("俘" if 将["状态"] == "被俘"
                                        else ("伤" if 将["状态"] == "重伤" else "")))
            for 将 in 局面["将领们"]])
        self._填表(self.魏城表, [
            (城["城池"], 城["归属"], f"{城['守军']:,}", f"{城['粮草']:,}", 城["守将"],
             "俘" if 城["归属"] == "蜀汉" else "")
            for 城 in 局面["敌方城池"]])
        self._填表(self.蜀城表, [(城["城池"], f"{城['兵力']:,}", 城["将领"], "")
                              for 城 in 局面["蜀汉城池"]])

        self.态势文本.configure(state="normal")
        self.态势文本.delete("1.0", "end")
        self.态势文本.insert("end", self.会话.态势图())
        self.态势文本.configure(state="disabled")

        for 键, 钮 in self.行动按钮.items():
            可用 = next(项["可用"] for 项 in 游戏接口.行动清单(self.会话) if 项["键"] == 键)
            钮.configure(state=("normal" if 可用 and not self.自动演示中 else "disabled"))
        结束态 = "normal" if (not 局面["结局"] and not self.自动演示中) else "disabled"
        self.结束按钮.configure(state=结束态)

        if self.图谱 is not None:                     # 地图随局面一起刷新
            self.图谱.重绘(局面)

    # ── 地图 ──
    def _地图缩放(self, 因子):
        if self.图谱 is not None:
            self.图谱.缩放一步(因子)

    def _地图动作(self, 名称):
        if self.图谱 is None:
            return
        {"适应全图": self.图谱.适应全图, "居中战场": self.图谱.居中战场}[名称]()

    def _切换骨架(self):
        if self.图谱 is None:
            return
        self.图谱.设显示骨架(self.骨架开关.get())
        self.图谱.设显示粗骨架(self.粗骨架开关.get())
        self._设状态(f"郡界骨架：{'显示' if self.骨架开关.get() else '隐藏'}"
                  f"（{'含' if self.粗骨架开关.get() else '不含'}仅有治所的粗骨架）"
                  f"；骨架为几何推断，非考据边界")

    def 城池被点击(self, 城名):
        """在地图上点了某座城：弹出详情，并可直接发起与该城相关的行动。

        行动的"目标序号"由门面向引擎自己的列表函数求得（见 游戏接口.序号_*），
        界面不复制任何筛选或排序逻辑。
        """
        局面 = self.会话.局面()
        if not 局面:
            return
        if self.自动演示中:
            self._设状态("自动演示进行中；结束演示后再操作地图。")
            return
        魏城 = next((项 for 项 in 局面["敌方城池"] if 项["城池"] == 城名), None)
        蜀城 = next((项 for 项 in 局面["蜀汉城池"] if 项["城池"] == 城名), None)
        if 魏城 is None and 蜀城 is None:
            return
        归属 = 魏城["归属"] if 魏城 is not None else "蜀汉"
        类型 = next((城.get("类型", "") for 城 in (self.地图数据 or {}).get("城池", [])
                   if 城["名"] == 城名), "")
        驻将们 = [将["姓名"] for 将 in 局面["将领们"]
                if 将["位置"] == 城名 and 将["状态"] != "已殁"]

        对话 = tk.Toplevel(self)
        对话.title(f"{城名} · {归属}")
        对话.configure(bg=配色["底"])
        对话.transient(self)
        对话.resizable(False, False)
        外 = ttk.Frame(对话, padding=14)
        外.pack(fill="both", expand=True)
        ttk.Label(外, text=f"{城名}（{归属}{'·' + 类型 if 类型 else ''}）",
                 style="提示.TLabel").pack(anchor="w")

        行们 = [("归属", 归属)]
        if 魏城 is not None:
            行们 += [("守军", f"{魏城['守军']:,}"), ("粮草", f"{魏城['粮草']:,}"),
                   ("守将", 魏城["守将"])]
        if 蜀城 is not None:
            行们.append(("兵力", f"{蜀城['兵力']:,}"))
        行们.append(("驻将", "、".join(驻将们) if 驻将们 else "无"))
        围攻 = 局面["围攻"]
        if 围攻 and 围攻.get("目标") == 城名:
            行们.append(("战况", f"围攻中：还需 {围攻['剩余']} 回合（领将 {围攻['领将']}）"))
        信息 = ttk.Frame(外)
        信息.pack(fill="x", pady=(8, 4))
        for 序号, (键, 值) in enumerate(行们):
            ttk.Label(信息, text=键, style="次.TLabel").grid(row=序号, column=0, sticky="w", pady=1)
            ttk.Label(信息, text=str(值), style="数值.TLabel").grid(
                row=序号, column=1, sticky="w", padx=(12, 0), pady=1)

        铜牌 = ttk.LabelFrame(外, text=" 可执行的操作 ", padding=(10, 6, 10, 8))
        铜牌.pack(fill="x", pady=(8, 4))
        阻挡 = ("本局已结束" if 局面["结局"]
              else ("本回合已用过大事，请先结束本回合" if 局面["大事已用"] else ""))

        if 归属 == "蜀汉":
            if 驻将们:
                姓 = 驻将们[0]
                序 = self.会话.序号_可行动将领(姓)
                if 序 is not None:
                    ttk.Button(铜牌, text=f"部署将领任务（{姓}）", width=28,
                               command=lambda: self._从城池执行(
                                   对话, "部署任务", [序], f"部署{姓}的任务")).pack(fill="x", pady=2)
                    ttk.Button(铜牌, text=f"设定守城指令（{姓}）", width=28,
                               command=lambda: self._从城池执行(
                                   对话, "守城指令", [序], f"设定{姓}的城破指令")).pack(fill="x", pady=2)
                else:
                    ttk.Label(铜牌, text=f"{姓}当前不可行动（重伤 / 被俘 / 已殁）",
                             style="次.TLabel").pack(anchor="w")
            else:
                ttk.Label(铜牌, text="该城暂无驻将：可先用「部署将领任务」派将前来",
                         style="次.TLabel").pack(anchor="w")
        else:
            序军事 = self.会话.序号_军事目标(城名)
            序劝降 = self.会话.序号_可劝降目标(城名)
            if 序军事 is not None:
                钮 = ttk.Button(铜牌, text=f"发起军事行动 · 目标{城名}", width=28,
                              command=lambda: self._从城池执行(
                                  对话, "军事行动", [序军事], f"进攻{城名}"))
                钮.pack(fill="x", pady=2)
                if 阻挡:
                    钮.configure(state="disabled")
            else:
                原因 = ("北伐之路未通：需先夺取宛城或樊城以打通粮道"
                      if 城名 == "洛阳" else "当前无法进攻该城")
                ttk.Label(铜牌, text=f"✕ {原因}", style="次.TLabel",
                         wraplength=240, justify="left").pack(anchor="w")
            if 序劝降 is not None:
                钮 = ttk.Button(铜牌, text=f"计谋 · 劝降{城名}守将", width=28,
                              command=lambda: self._从城池执行(
                                  对话, "计谋", ["6", 序劝降], f"劝降{城名}"))
                钮.pack(fill="x", pady=2)
                if 阻挡:
                    钮.configure(state="disabled")
            if 阻挡:
                ttk.Label(铜牌, text="（" + 阻挡 + "）", style="次.TLabel",
                         wraplength=240, justify="left").pack(anchor="w", pady=(4, 0))

        ttk.Button(外, text="关闭", command=对话.destroy).pack(fill="x", pady=(6, 0))
        对话.bind("<Escape>", lambda 事件: 对话.destroy())
        self._居中窗口(对话)

    def _从城池执行(self, 对话, 行动键, 预设答案, 说明):
        """先关掉城池详情窗，再执行行动（避免两个模态窗互相抢占），最后刷新界面。"""
        对话.destroy()
        self.update_idletasks()
        self._设状态(说明 + "……")
        成功, 提示 = self.会话.执行行动(行动键, 预设答案=预设答案)
        self.刷新()
        if 提示:
            self._设状态(提示)

    def _居中窗口(self, 窗口):
        窗口.update_idletasks()
        x = self.winfo_rootx() + (self.winfo_width() - 窗口.winfo_width()) // 2
        y = self.winfo_rooty() + (self.winfo_height() - 窗口.winfo_height()) // 3
        窗口.geometry(f"+{max(x, 0)}+{max(y, 0)}")

    def _填表(self, 表, 行们):
        表.delete(*表.get_children())
        for 行 in 行们:
            表.insert("", "end", values=行[:-1], tags=(行[-1],) if 行[-1] else ())

    def 刷新槽位(self):
        for 项 in self.会话.槽位概览():
            标签 = self.槽位标签[项["槽位"]]
            if 项["有档"]:
                文本 = (f"{项['显示名']}：{项['摘要']}\n{项['时间']}"
                      if 项["状态"] == "正常" else f"{项['显示名']}：⚠ {项['状态']}")
            else:
                文本 = f"{项['显示名']}：空档位"
            标签.configure(text=文本)

    def _报告结局(self, 结局):
        self._写战报("")
        messagebox.showinfo("本局结束", f"{结局}\n\n（可在「游戏 → 新开局」重开，或读取存档）")
        self.状态.configure(text="本局已结束：" + 结局)

    def _设状态(self, 文本):
        self.状态.configure(text=文本)

    # ── 帮助 ──
    def _玩法速览(self):
        messagebox.showinfo(
            "玩法速览",
            "1. 每回合只能执行【一件大事】：军事 / 计谋 / 外交，执行后请点「结束本回合」。\n"
            "2. 部署将领任务与设定守城指令不占大事名额，可多次操作。\n"
            "3. 计谋没有概率：满足前置条件（如已有情报）即 100% 成功。\n"
            "4. 军事胜负看兵力阈值：进攻兵力 > 守军×1.5 强攻必胜；> ×0.8 可围攻；< ×0.5 判必败。\n"
            "5. 攻占洛阳（需先取宛城或樊城打通粮道）即达成「北伐大捷」。\n"
            "6. 存档有三个槽位，随时可存可读（读档会覆盖当前未存档的进度）。")

    def _关于(self):
        messagebox.showinfo(
            "关于",
            "三国 · 蜀汉突围 —— 图形界面版\n\n"
            "纯 Python 标准库实现（含本界面，tkinter 属标准库），零第三方依赖。\n"
            "界面不含任何游戏规则：所有判定与结算都由引擎完成，\n"
            "界面只负责显示状态与返回玩家意图。\n\n"
            "存档位于程序同级的 saves/ 目录（slot1~slot3）。")


def 主函数():
    try:
        窗口 = 主窗口()
    except Exception as 异常:
        print(f"界面启动失败：{异常!r}")
        return 1
    窗口.mainloop()
    return 0


def 自检():
    """无人工介入的自检（用于验证打包后的 exe 能否真正工作）。

    做四件事：构建界面 → 跑 3 个回合 → 存 / 读一个槽位 → 核对状态一致。
    结果写入系统临时目录的《蜀汉突围_自检报告.txt》，退出码 0 表示全部通过。
    注意：存档写在临时目录（不碰玩家真实存档），且需要可用的图形环境。
    """
    import tempfile
    结果行 = []
    失败 = []

    def 记(文本, 通过=None):
        标记 = "" if 通过 is None else ("[通过] " if 通过 else "[失败] ")
        结果行.append(标记 + 文本)
        if 通过 is False:
            失败.append(文本)

    记(f"Python：{sys.version.split()[0]}　打包运行：{bool(getattr(sys, 'frozen', False))}")
    try:
        import 游戏接口
        import save_manager
        import config_loader
        记(f"引擎与门面导入成功；存档默认目录：{save_manager.默认存档目录()}")
        配置目录 = os.path.join(config_loader.项目根目录, "config")
        记(f"配置目录：{配置目录}", os.path.isdir(配置目录))
        记("五个配置文件齐备",
            all(os.path.isfile(os.path.join(配置目录, 名)) for 名 in
                ("units.json", "schemes.json", "seasons.json", "diplomacy.json", "battle.json")))
    except Exception as 异常:
        记(f"引擎导入失败：{异常!r}", False)
        return _写自检报告(结果行, 失败)

    窗口 = None
    try:
        窗口 = 主窗口()
        窗口.update()
        记("主窗口构建成功", True)
    except Exception as 异常:
        记(f"主窗口构建失败：{异常!r}", False)
        return _写自检报告(结果行, 失败)

    try:
        局 = 窗口.会话
        # 存档改到临时目录，避免污染玩家真实存档
        临时 = tempfile.mkdtemp(prefix="蜀汉自检_")
        原目录 = save_manager.默认存档目录
        save_manager.默认存档目录 = lambda: 临时

        开局 = 局.局面()
        记(f"新开局：第 {开局['回合']} 回合 · {开局['日期']} · 兵力 {开局['蜀汉']['兵力']} · "
          f"{开局['控制城池']} 城", 开局["回合"] == 1)
        记("配置加载无警告（配置文件被正确找到并校验通过）",
            not getattr(局.游戏, "配置警告", ""))
        记("开局兵力为 18000（读取配置后的初始值）", 开局["蜀汉"]["兵力"] == 18000)

        for _ in range(3):
            局.结束回合()
        窗口.update()
        记(f"连续推进 3 回合后：第 {局.局面()['回合']} 回合 · {局.局面()['日期']}",
           局.局面()["回合"] == 4)

        存前回合 = 局.局面()["回合"]
        成功, 提示 = 局.保存到槽位("slot3")
        记(f"保存到存档位 3：{提示}", 成功)

        成功, 提示 = 局.读档开局("slot3", 输出回调=lambda 文本: None,
                              询问回调=lambda 提示: "0")
        记(f"从存档位 3 读回：{提示}", 成功)
        记("读档后回合数与存档时一致", 局.局面()["回合"] == 存前回合)

        概览 = {项["槽位"]: 项 for 项 in 局.槽位概览()}
        记("存档位概览：位3 有档、位1 空档",
           概览["slot3"]["有档"] and not 概览["slot1"]["有档"])

        态势 = 局.态势图()
        记(f"战区态势图渲染：{len(态势.splitlines())} 行", bool(态势.strip()))

        # —— 美术资产区域：主题 / 字体私有注册 / 台账（打包后尤其要确认字体被打进去了）——
        记(f"主题已载入：界面配色 {len(资产.主题['界面配色'])} 项 · "
          f"地图配色 {len(资产.主题['地图配色'])} 项 · 字体 {len(资产.主题['字体'])} 组",
            bool(资产.主题["界面配色"]) and bool(资产.主题["字体"]))
        注册 = 资产.注册字体文件()
        记(f"字体进程私有注册：{len(注册)} 个文件", bool(注册))
        首选 = 资产.主题["字体"]["正文"]["候选"][0]
        实际 = 资产.字体("正文")[0]
        记(f"正文字体解析为「{实际}」，候选链首位为「{首选}」", 实际 == 首选)
        台账错误 = 资产.校验台账()
        记(f"资产台账校验通过（共 {资产.资产统计()['总数']} 条资产）", not 台账错误)
        if 台账错误:
            结果行.append("      · " + "；".join(台账错误[:3]))

        # —— 郡界骨架：数据 / 渲染 / 悬停命中 ——
        if 窗口.骨架数据 is None:
            记("郡界骨架未载入：" + "；".join(窗口.骨架错误[:1]), False)
        else:
            有依据 = 窗口.图谱.骨架郡们(False)
            粗的 = [条 for 条 in 窗口.图谱.骨架郡们(True) if 条 not in 有依据]
            记(f"郡界骨架已载入：{窗口.骨架数据['郡数']} 郡，其中 {len(有依据)} 郡有属县依据"
              f"、{len(粗的)} 郡仅有治所", len(有依据) >= 6)
            记("骨架数据自带「非考据边界」警告字段", bool(窗口.骨架数据.get("警告")))
            抽检 = [条 for 条 in 有依据 if 条["郡"] in ("南郡", "南阳郡", "汉中郡")]
            命中合格 = True
            for 条 in 抽检:
                治所 = next((县 for 县 in 条["县"] if 县.get("是治所")), 条["县"][0])
                x, y = 窗口.图谱.世界到屏幕(*地图.投影(*治所["坐标"]))
                命中 = 窗口.图谱.命中郡(x, y)
                if 命中 is None or 命中["郡"] != 条["郡"]:
                    命中合格 = False
                    结果行.append(f"      · {条['郡']}治所处命中到 "
                              f"{'空' if 命中 is None else 命中['郡']}，应为 {条['郡']}")
            记(f"悬停命中抽检（{len(抽检)} 郡治所处应命中自身）", 命中合格)
            越界 = 窗口.图谱.命中郡(5, 5)
            记("画布角落处不命中任何郡", 越界 is None)

        # —— 地图：数据 / 渲染 / 命中 ——
        记(f"地图数据已载入：{len(窗口.地图数据['州'])} 州 · "
          f"{len(窗口.地图数据['城池'])} 城池",
           窗口.地图数据 is not None and not 窗口.地图错误)
        if 窗口.图谱 is not None:
            窗口.图谱.居中战场()
            窗口.update()
            可见 = 窗口.图谱.可视城池()
            记(f"居中战场后可见城池：{len(可见)} / 10", len(可见) == 10)
            # 标签只在缩放足够时绘制（缩略视野下避免十个标签挤成一团）：
            # 这里先把缩放推到门槛之上，再检查标签的数量与不重叠。
            if 窗口.图谱.缩放 < 地图.地图画布.标签缩放门槛:
                窗口.图谱.缩放一步(4.8 / 窗口.图谱.缩放)
                窗口.update()
            框们 = list(窗口.图谱.标签矩形.values())
            重叠 = 0
            for i in range(len(框们)):
                for j in range(i + 1, len(框们)):
                    a1, b1, a2, b2 = 框们[i]
                    c1, d1, c2, d2 = 框们[j]
                    if not (a2 < c1 or a1 > c2 or b2 < d1 or b1 > d2):
                        重叠 += 1
            记(f"缩放 {窗口.图谱.缩放:.1f}× 下城池数据标签：{len(框们)} 个，重叠 {重叠} 处",
               len(框们) == 10 and 重叠 == 0)
            位置 = 窗口.图谱.城池屏幕位置("襄阳")
            记("地图点击命中城池（襄阳）",
               窗口.图谱.命中城池(*位置) == "襄阳")
            窗口.图谱.适应全图()
            窗口.update()
            宽, 高 = 窗口.图谱.winfo_width(), 窗口.图谱.winfo_height()
            越界 = [名 for 名 in ("成都", "江陵", "阆中", "汉中", "永安",
                               "襄阳", "樊城", "宛城", "上庸", "洛阳")
                  if not (0 <= 窗口.图谱.城池屏幕位置(名)[0] <= 宽
                          and 0 <= 窗口.图谱.城池屏幕位置(名)[1] <= 高)]
            记(f"适应全图后十城均在画布内（越界 {len(越界)} 座）", not 越界)

        # 真实存档目录可写性探针：确认打包后确实能在 exe 同级目录落盘存档
        # （只写一个探针文件并立即删除，不动玩家任何真实存档）
        真实目录 = 原目录()
        try:
            os.makedirs(真实目录, exist_ok=True)
            探针 = os.path.join(真实目录, "._可写性探针")
            with open(探针, "w", encoding="utf-8") as 文件:
                文件.write("probe")
            os.remove(探针)
            记(f"真实存档目录可写：{真实目录}", True)
        except OSError as 异常:
            记(f"真实存档目录不可写：{真实目录}（{异常}）", False)
        save_manager.默认存档目录 = 原目录
    except Exception as 异常:
        import traceback
        记(f"自检过程抛出异常：{异常!r}", False)
        结果行.append(traceback.format_exc())
    finally:
        if 窗口 is not None:
            窗口.destroy()
    return _写自检报告(结果行, 失败)


def _写自检报告(结果行, 失败):
    import tempfile
    路径 = os.path.join(tempfile.gettempdir(), "蜀汉突围_自检报告.txt")
    头部 = ("《三国·蜀汉突围》图形界面自检报告\n"
          + "=" * 46 + "\n")
    尾部 = ("=" * 46 + "\n" + ("全部通过 ✅\n" if not 失败 else f"存在失败项 {len(失败)} 条 ❌\n"))
    try:
        with open(路径, "w", encoding="utf-8") as 文件:
            文件.write(头部 + "\n".join(结果行) + "\n" + 尾部)
    except OSError:
        pass
    try:                      # --windowed 打包时无控制台，这里能输出就输出
        print("\n".join(结果行))
    except Exception:
        pass
    return 0 if not 失败 else 1


if __name__ == "__main__":
    if "--自检" in sys.argv:
        raise SystemExit(自检())
    raise SystemExit(主函数())
