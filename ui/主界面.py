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
for 目录 in (源码目录, 仓库根目录):
    if os.path.isdir(目录) and 目录 not in sys.path:
        sys.path.insert(0, 目录)

import 游戏接口  # noqa: E402  （本地模块）

# 从引擎打印的菜单里认出「可点击选项」：1. xxx ／ A. xxx ／ 1、xxx ／ 1) xxx
选项模式 = re.compile(r"^\s*([0-9]{1,2}|[A-Za-z])[.、)]\s*(\S.*)$")

配色 = {
    "底": "#f6f3ea", "面": "#fffdf8", "边": "#c9bfa8",
    "主字": "#2b2620", "次字": "#6f6558", "蜀": "#2f6b3f", "魏": "#8c3b3b", "吴": "#39558c",
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
        self.geometry("1220x820")
        self.minsize(1040, 700)
        self.会话 = 游戏接口.会话()
        self.自动演示中 = False
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
                    font=("Microsoft YaHei UI", 10))
        样式.configure("TFrame", background=配色["底"])
        样式.configure("TLabel", background=配色["底"], foreground=配色["主字"])
        样式.configure("提示.TLabel", font=("Microsoft YaHei UI", 11, "bold"),
                    foreground="#1f1a15")
        样式.configure("次.TLabel", foreground=配色["次字"], font=("Microsoft YaHei UI", 9))
        样式.configure("标题.TLabel", font=("Microsoft YaHei UI", 11, "bold"), foreground="#3a2f24")
        样式.configure("数值.TLabel", font=("Consolas", 11, "bold"))
        样式.configure("TLabelframe", background=配色["底"], bordercolor=配色["边"])
        样式.configure("TLabelframe.Label", background=配色["底"], foreground="#4a4036",
                    font=("Microsoft YaHei UI", 10, "bold"))
        样式.configure("TButton", padding=(6, 5))
        样式.configure("行动.TButton", font=("Microsoft YaHei UI", 10, "bold"), padding=(6, 8))
        样式.configure("回合.TButton", font=("Microsoft YaHei UI", 11, "bold"), padding=(6, 10))
        样式.configure("Treeview", rowheight=23, fieldbackground=配色["面"])
        样式.configure("Treeview.Heading", font=("Microsoft YaHei UI", 9, "bold"))

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

        # 中：将领 / 城池 / 态势图
        中 = ttk.Frame(self, padding=(6, 0, 6, 8))
        中.grid(row=1, column=1, sticky="nsew")
        self.书 = ttk.Notebook(中)
        self.书.pack(fill="both", expand=True)
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
        self.态势文本 = tk.Text(态势框, wrap="none", font=("Consolas", 10),
                           bg="#1e2430", fg="#d8e0ea", insertbackground="#d8e0ea",
                           relief="flat", padx=10, pady=8)
        self.态势文本.grid(row=0, column=0, sticky="nsew")
        滚 = ttk.Scrollbar(态势框, orient="vertical", command=self.态势文本.yview)
        滚.grid(row=0, column=1, sticky="ns")
        self.态势文本.configure(yscrollcommand=滚.set, state="disabled")
        self.书.add(态势框, text="  战区态势图  ")

        # 右：行动 + 存档位
        右 = ttk.Frame(self, padding=(6, 0, 12, 8))
        右.grid(row=1, column=2, sticky="nse")
        self._建行动面板(右)
        self._建存档面板(右)

        # 底：战报
        底 = ttk.LabelFrame(self, text=" 战报 ", padding=(8, 4, 8, 8))
        底.grid(row=2, column=0, columnspan=3, sticky="nsew", padx=12, pady=(0, 6))
        底.columnconfigure(0, weight=1)
        self.战报 = tk.Text(底, height=11, wrap="word", font=("Microsoft YaHei UI", 10),
                         bg="#fffdf8", fg="#241f18", relief="flat", padx=8, pady=6)
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
        表.tag_configure("殁", foreground="#9a9a9a")
        表.tag_configure("俘", foreground="#8c3b3b")
        表.tag_configure("伤", foreground="#a06a1f")
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
            foreground=("#a03030" if 局面["大事已用"] else "#2f6b3f"))

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
