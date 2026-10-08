# -*- coding: utf-8 -*-
"""资产与主题加载器：界面对"美术资产"的**唯一入口**。

═══════════════════════════════════════════════════════════════════
【为什么要有这一层】
界面代码里原本写死了 41 处颜色、20 处字体名 —— 换一次皮要改 20 处代码，而且换字体必须动 Python。
现在改成：**一切经本模块读取 assets/ 下的声明文件**。

    ui/*.py  →  ui/资产.py  →  assets/theme.json（配色 / 字体 / 字号 / 地图参数）
                            →  assets/fonts/*.ttf（运行时私有注册，不装进系统）
                            →  assets/manifest.json（台账：来源 / 作者 / 许可 / 校验值 / 状态）

于是"换字体、换配色"变成：**放文件 + 改一行声明**，代码零改动。
`tests/test_assets.py` 会逐行扫描 ui/*.py，禁止再出现写死的颜色与字体名。

【字体合规】
打包/运行时不把字体装进系统，而是用 Windows 的 AddFontResourceExW 做**进程私有注册**
（FR_PRIVATE），程序退出即失效。这是标准做法，也避免污染用户系统。
"""
import ctypes
import hashlib
import json
import os
import sys

# 内置兜底主题：assets/theme.json 缺失或损坏时用它，保证界面仍能启动（只是外观回到最朴素的配色）
内置主题 = {
    "界面配色": {"窗口底": "#f6f3ea", "面板底": "#fffdf8", "边框": "#c9bfa8",
             "主字": "#2b2620", "次字": "#6f6558", "深字": "#1f1a15",
             "标题字": "#3a2f24", "小标题字": "#4a4036", "强调": "#a03030",
             "成功": "#2f6b3f", "危险": "#8c3b3b",
             "蜀汉": "#2f6b3f", "曹魏": "#8c3b3b", "东吴": "#39558c",
             "日志底": "#1e2430", "日志字": "#d8e0ea"},
    "地图配色": {"海": "#dde8f0", "陆": "#f2eee2", "轮廓": "#98a2ab", "界线": "#bcc4ca",
             "州名": "#8f8578", "州名描边": "#f2eee2",
             "蜀汉": "#2f6b3f", "曹魏": "#8c3b3b", "蜀汉浅": "#5d9668", "曹魏浅": "#b5706f",
             "围攻": "#d98324", "选中": "#1f6f9c",
             "标签底": "#fffdf8", "标签边": "#c3b9a4", "标签字": "#241f18", "标签次": "#6f6558",
             "城池描边": "#ffffff", "州界描边基色": "#3c3228", "默认州色": "#cccccc",
             "错误字": "#8c3b3b"},
    "字体": {"标题": {"候选": ["Microsoft YaHei UI", "SimSun"], "粗": True},
           "正文": {"候选": ["Microsoft YaHei UI", "SimSun"], "粗": False},
           "等宽": {"候选": ["Consolas", "Courier New"], "粗": False}},
    "字号": {"窗口标题": 11, "面板小标题": 10, "正文": 10, "小字": 9, "提示": 11,
           "数值": 11, "回合按钮": 11, "表格": 9,
           "地图标注": 9, "地图州名": 9, "地图图例": 8, "地图图例符号": 11, "日志": 9},
    "地图参数": {"州色混合比例": 0.34, "州界描边混合比例": 0.45,
             "标签缩放门槛": 4.0, "点击命中半径": 14},
}

主题 = dict(内置主题)
主题警告 = []
_已注册字体 = []
_系统字体缓存 = None


def 资产根目录():
    """assets/ 的位置。复用 config_loader 对项目根目录的判定，源码运行与打包 exe 都成立。"""
    try:
        import config_loader
        return os.path.join(config_loader.项目根目录, "assets")
    except Exception:
        return os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets")


def 载入主题():
    """读取 assets/theme.json（逐层与内置兜底合并，缺字段不至于让界面崩）。"""
    global 主题, 主题警告
    路径 = os.path.join(资产根目录(), "theme.json")
    结果 = {键: dict(值) for 键, 值 in 内置主题.items()}
    警告 = []
    if not os.path.isfile(路径):
        警告.append(f"主题文件不存在：{路径}（已用内置兜底主题）")
    else:
        try:
            with open(路径, encoding="utf-8") as 文件:
                外部 = json.load(文件)
            for 段 in ("界面配色", "地图配色", "字号", "地图参数"):
                if isinstance(外部.get(段), dict):
                    结果[段].update(外部[段])
            if isinstance(外部.get("字体"), dict):
                for 用途, 条目 in 外部["字体"].items():
                    if isinstance(条目, dict) and 条目.get("候选"):
                        结果["字体"][用途] = dict(条目)
        except (OSError, json.JSONDecodeError) as 异常:
            警告.append(f"主题文件无法解析：{异常}（已用内置兜底主题）")
    主题 = 结果
    主题警告 = 警告
    return 主题


def 颜色(名, 默认="#000000"):
    """界面配色。"""
    return 主题.get("界面配色", {}).get(名, 默认)


def 地图颜色(名, 默认="#000000"):
    """地图配色。"""
    return 主题.get("地图配色", {}).get(名, 默认)


def 字号(名, 默认=10):
    return int(主题.get("字号", {}).get(名, 默认))


def 地图参数(名, 默认=0.0):
    return 主题.get("地图参数", {}).get(名, 默认)


def _系统字体集():
    """当前 Tk 能看到的字体族集合（结果缓存；没有图形环境时返回空集）。

    注意：缓存变量名为 _系统字体缓存，**不能**与本函数同名 ——
    同名会让 `global` 指向函数自身，函数就会把"自己"当结果返回。
    """
    global _系统字体缓存
    if _系统字体缓存 is None:
        try:
            import tkinter.font
            _系统字体缓存 = {名.lower() for 名 in tkinter.font.families()}
        except Exception:
            _系统字体缓存 = set()
    return _系统字体缓存


def 字体(用途="正文", 号=None, 粗=None):
    """返回 tkinter 可用的字体元组，按候选链依次尝试，取第一个系统确实存在的字体族。

    这样即使 assets/fonts/ 里的字体缺失或注册失败，界面也能退到系统字体正常显示，
    而不是抛异常或显示成方块。
    """
    条目 = 主题.get("字体", {}).get(用途) or {"候选": ["Microsoft YaHei UI"], "粗": False}
    候选 = list(条目.get("候选") or [])
    if 号 is None:
        号 = 字号({"标题": "面板小标题", "正文": "正文"}.get(用途, "正文"), 10)
    if 粗 is None:
        粗 = bool(条目.get("粗", False))
    系统 = _系统字体集()
    选中 = None
    if 系统:
        for 名 in 候选:
            if 名.lower() in 系统:
                选中 = 名
                break
    if 选中 is None:
        选中 = 候选[-1] if 候选 else "TkDefaultFont"
    return (选中, 号, "bold") if 粗 else (选中, 号)


def 注册字体文件():
    """把 assets/fonts/ 下的字体做**进程私有注册**（Windows：AddFontResourceExW + FR_PRIVATE）。

    不安装到系统、退出即失效，因此不会污染用户机器；失败也不报错（界面会退到系统字体）。
    返回已注册的文件名列表。
    """
    global _已注册字体, _系统字体缓存
    if _已注册字体:
        return 已注册列表()
    目录 = os.path.join(资产根目录(), "fonts")
    if not os.path.isdir(目录):
        return []
    if not hasattr(ctypes, "windll"):
        return []                     # 非 Windows：交由系统字体兜底
    for 名 in sorted(os.listdir(目录)):
        if not 名.lower().endswith((".ttf", ".otf", ".ttc")):
            continue
        路径 = os.path.join(目录, 名)
        try:
            ctypes.windll.gdi32.AddFontResourceExW(ctypes.c_wchar_p(路径), 0x10, 0)
            _已注册字体.append(名)
        except Exception:
            continue
    _系统字体缓存 = None             # 字体集变了，清缓存重新枚举
    return 已注册列表()


def 已注册列表():
    return [名 for 名 in _已注册字体]


# ══════════════════════════════════════════════════════════════════
#  台账（溯源 A / D 层的执行者）
# ══════════════════════════════════════════════════════════════════
台账必填字段 = ("编号", "区域", "类别", "名称", "文件", "来源", "原作者", "许可",
           "获取日期", "校验", "状态", "归属")
允许状态 = ("占位", "过渡", "定稿", "已归档")
允许归属 = ("本人", "第三方", "AI协作")


def 载入台账():
    """返回 (台账字典, 错误列表)。"""
    路径 = os.path.join(资产根目录(), "manifest.json")
    if not os.path.isfile(路径):
        return {}, [f"资产台账不存在：{路径}"]
    try:
        with open(路径, encoding="utf-8") as 文件:
            台账 = json.load(文件)
    except (OSError, json.JSONDecodeError) as 异常:
        return {}, [f"资产台账无法解析：{异常}"]
    return 台账, []


def 校验台账():
    """逐条校验台账：字段齐备、文件存在、许可文本存在、校验值一致、状态与归属合法。"""
    台账, 错误 = 载入台账()
    if 错误:
        return 错误
    条目们 = 台账.get("资产")
    if not isinstance(条目们, list):
        return ["资产台账缺少「资产」列表"]
    根 = 资产根目录()
    已见编号 = set()
    for 序号, 条 in enumerate(条目们, 1):
        位置 = f"第 {序号} 条（{条.get('名称', '未命名')}）"
        for 字段 in 台账必填字段:
            if not str(条.get(字段, "")).strip():
                错误.append(f"{位置}：缺少必填字段「{字段}」")
        if 条.get("编号") in 已见编号:
            错误.append(f"{位置}：编号重复「{条.get('编号')}」")
        已见编号.add(条.get("编号"))
        if 条.get("状态") not in 允许状态:
            错误.append(f"{位置}：状态非法「{条.get('状态')}」（应为 {'/'.join(允许状态)}）")
        if 条.get("归属") not in 允许归属:
            错误.append(f"{位置}：归属非法「{条.get('归属')}」（应为 {'/'.join(允许归属)}）")
        文件 = 条.get("文件") or ""
        全路径 = os.path.join(根, 文件)
        if 文件 and not os.path.isfile(全路径):
            错误.append(f"{位置}：文件不存在 {文件}")
        elif 文件:
            if str(条.get("校验", "")).startswith("sha256:"):
                with open(全路径, "rb") as 文件:
                    实际 = hashlib.sha256(文件.read()).hexdigest()
                if 实际 != 条["校验"].split(":", 1)[1]:
                    错误.append(f"{位置}：校验值不一致（文件被改动过？重跑 tools/资产台账.py 填校验值）")
            许可文件 = 条.get("许可文件")
            if 许可文件 and not os.path.isfile(os.path.join(根, 许可文件)):
                错误.append(f"{位置}：许可文本缺失 {许可文件}（第三方资产必须随附许可）")
            elif not 许可文件 and 条.get("归属") == "第三方":
                错误.append(f"{位置}：第三方资产必须登记「许可文件」")
    # 反向检查：磁盘上有资产文件却没登记
    登记过 = {(条.get("文件") or "").replace("/", os.sep) for 条 in 条目们}
    for 子目录 in ("fonts", "images", "audio"):
        目录 = os.path.join(根, 子目录)
        if not os.path.isdir(目录):
            continue
        for 名 in sorted(os.listdir(目录)):
            if 名.startswith(".") or 名.lower().endswith((".txt", ".md")):
                continue
            相对 = os.path.join(子目录, 名)
            if 相对 not in 登记过:
                错误.append(f"资产未登记入台账：{相对}（每个文件都要有来源与许可）")
    return 错误


def 资产统计():
    """给界面/自检用的简要统计。"""
    台账, _ = 载入台账()
    条目们 = 台账.get("资产") or []
    按状态 = {}
    按归属 = {}
    for 条 in 条目们:
        按状态[条.get("状态", "未知")] = 按状态.get(条.get("状态", "未知"), 0) + 1
        按归属[条.get("归属", "未知")] = 按归属.get(条.get("归属", "未知"), 0) + 1
    return {"总数": len(条目们), "按状态": 按状态, "按归属": 按归属}


载入主题()
