# -*- coding: utf-8 -*-
"""区域隔离与资产溯源的强制层（"隔离强度＝中"的落地）。

这一组用例存在的意义：把"约定"变成"测试会红的事实"。

  【一】主题与台账：配色合法、字体候选链有兜底、台账字段齐备、文件与许可存在、校验值一致；
  【二】写死检测：界面代码里**不许**再出现写死的颜色与字体族名（否则换皮又要改代码）；
  【三】运行时解析：字体候选链能落到真实存在的字体、主题缺失时退到内置兜底而不崩。
"""
import os
import re
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import 夹具  # noqa: E402

sys.path.insert(0, 夹具.源码目录)
sys.path.insert(0, os.path.join(夹具.仓库根目录, "ui"))
import 资产  # noqa: E402

# 禁止写死扫描的对象：界面里"使用"资产的两个文件。
# 不含 ui/资产.py —— 它是内置兜底主题的存放处，属于"声明"而非"使用"。
禁止写死文件 = ("ui/主界面.py", "ui/地图.py")
禁止出现的字体族 = ("Microsoft YaHei UI", "Consolas", "SimSun", "KaiTi",
            "Cascadia Mono", "Courier New", "宋体", "微软雅黑")
颜色模式 = re.compile(r"#[0-9a-fA-F]{6}")


def 是否在注释或字符串说明里(行):
    """粗略排除注释行，避免把说明文字里的示例算成违规。"""
    去空白 = 行.strip()
    return 去空白.startswith("#") or 去空白.startswith('"""') or 去空白.startswith("'''")


class 主题与台账(unittest.TestCase):

    def test_主题文件存在且可解析(self):
        根 = 资产.资产根目录()
        self.assertTrue(os.path.isfile(os.path.join(根, "theme.json")),
                        "assets/theme.json 必须存在（配色与字体的唯一声明处）")
        self.assertEqual(资产.主题警告, [], "主题加载不应有警告")

    def test_配色全部是合法十六进制(self):
        for 段 in ("界面配色", "地图配色"):
            色表 = 资产.主题.get(段, {})
            self.assertTrue(色表, f"{段} 不应为空")
            for 名, 值 in 色表.items():
                self.assertRegex(str(值), r"^#[0-9a-fA-F]{6}$", f"{段}.{名} 不是合法颜色：{值}")

    def test_字体候选链有兜底(self):
        for 用途, 条目 in 资产.主题["字体"].items():
            候选 = 条目.get("候选") or []
            self.assertTrue(候选, f"字体「{用途}」的候选链不应为空")
            self.assertGreaterEqual(len(候选), 2,
                                    f"字体「{用途}」应至少给出一个兜底候选，否则换字体失败时界面会变成方块")

    def test_字号与地图参数齐备(self):
        for 名 in ("正文", "小字", "地图标注", "地图州名", "日志"):
            self.assertGreater(资产.字号(名, 0), 0, f"字号「{名}」应存在且为正")
        self.assertGreater(资产.地图参数("标签缩放门槛", 0), 0)
        self.assertGreater(资产.地图参数("点击命中半径", 0), 0)

    def test_台账校验通过(self):
        """溯源 A/D 层：每条资产都要有来源、作者、许可、日期、校验值、状态与归属。"""
        错误 = 资产.校验台账()
        self.assertEqual(错误, [], "资产台账校验未通过：\n" + "\n".join(错误))

    def test_第三方资产必须随附许可文本(self):
        """溯源 D 层：第三方资产必须随附一份有实质内容的许可/授权文本。"""
        台账, _ = 资产.载入台账()
        第三方 = [条 for 条 in 台账.get("资产", []) if 条.get("归属") == "第三方"]
        self.assertTrue(第三方, "本轮至少应有一条第三方资产（过渡字体、官方底图）以验证该规则")
        for 条 in 第三方:
            self.assertTrue(条.get("许可文件"), f"{条.get('名称')} 缺少许可文件字段")
            全路径 = os.path.join(资产.资产根目录(), 条["许可文件"])
            self.assertTrue(os.path.isfile(全路径), f"许可文本不存在：{条['许可文件']}")
            with open(全路径, encoding="utf-8") as 文件:
                正文 = 文件.read()
            self.assertGreater(len(正文.strip()), 200,
                               f"{条.get('名称')} 的许可/授权文本太短，等于没说明白")

    def test_字体资产必须随附OFL全文(self):
        """字体许可更严：不能只写一句"用了某字体"，必须带 OFL 全文。"""
        台账, _ = 资产.载入台账()
        字体条 = [条 for 条 in 台账.get("资产", []) if 条.get("类别") == "字体"]
        self.assertTrue(字体条, "本轮应有一条过渡字体资产")
        for 条 in 字体条:
            if 条.get("归属") != "第三方":
                continue
            全路径 = os.path.join(资产.资产根目录(), 条["许可文件"])
            with open(全路径, encoding="utf-8") as 文件:
                正文 = 文件.read()
            self.assertIn("SIL OPEN FONT LICENSE", 正文.upper().replace("  ", " "),
                          f"{条.get('名称')} 的许可文本应包含 OFL 全文")
            self.assertIn("Reserved Font Name", 正文,
                          f"{条.get('名称')} 的 OFL 文本应保留 Reserved Font Name 条款，"
                          "否则无法解释为何要改用「蜀汉过渡楷」这个字体名")

    def test_官方底图必须写明风险与替换路径(self):
        """官方标准地图是"用得住、但传不得"的资产：说明里必须同时写清风险与退路。"""
        台账, _ = 资产.载入台账()
        底图条 = [条 for 条 in 台账.get("资产", [])
                  if 条.get("类别") == "图片" and "地图" in 条.get("名称", "")]
        self.assertTrue(底图条, "本轮应登记一张官方标准地图底图")
        for 条 in 底图条:
            全路径 = os.path.join(资产.资产根目录(), 条["许可文件"])
            self.assertTrue(os.path.isfile(全路径), f"说明文本不存在：{条['许可文件']}")
            with open(全路径, encoding="utf-8") as 文件:
                正文 = 文件.read()
            for 关键词, 理由 in (("审图号", "要写清底图是哪一号标准地图"),
                                 ("送审", "要写清修改后公开传播需要重新送审"),
                                 ("替换", "要写清将来换掉它怎么换")):
                self.assertIn(关键词, 正文, f"官方底图说明里缺少「{关键词}」：{理由}")

    def test_每条资产都标了状态与替换计划(self):
        台账, _ = 资产.载入台账()
        状态集 = set(台账.get("状态含义", {}))
        for 条 in 台账.get("资产", []):
            self.assertIn(条.get("状态"), 状态集, f"{条.get('名称')} 的状态不在定义范围内")
            self.assertTrue(("替换计划" in 条) or 条.get("状态") == "定稿",
                            f"{条.get('名称')} 是临时资产却没写替换计划")

    def test_未登记的资产文件会被检出(self):
        """反向检查：往资产目录里丢一个文件但不登记，校验必须报错。"""
        探针 = os.path.join(资产.资产根目录(), "images", "_未登记探针.png")
        os.makedirs(os.path.dirname(探针), exist_ok=True)
        with open(探针, "wb") as 文件:
            文件.write(b"not a real png")
        try:
            错误 = 资产.校验台账()
            self.assertTrue(any("未登记" in 项 for 项 in 错误),
                            f"未登记的资产文件应被检出，实际错误：{错误}")
        finally:
            os.remove(探针)


class 禁止写死(unittest.TestCase):
    """溯源 C 层：界面代码不许内联颜色与字体族名，否则"换资产不改代码"就是空话。"""

    def test_界面代码不含写死的颜色(self):
        违规 = []
        for 文件 in 禁止写死文件:
            源码 = 夹具.读取源码(文件)
            for 行号, 行 in enumerate(源码.splitlines(), 1):
                if 是否在注释或字符串说明里(行):
                    continue
                for 命中 in 颜色模式.finditer(行):
                    违规.append(f"{文件}:{行号}: 写死颜色 {命中.group(0)} → 应改为 资产.颜色(...)/资产.地图颜色(...)")
        self.assertEqual(违规, [], "界面代码出现写死的颜色：\n" + "\n".join(违规))

    def test_界面代码不含写死的字体族(self):
        违规 = []
        for 文件 in 禁止写死文件:
            源码 = 夹具.读取源码(文件)
            for 行号, 行 in enumerate(源码.splitlines(), 1):
                if 是否在注释或字符串说明里(行):
                    continue
                for 族 in 禁止出现的字体族:
                    if f'"{族}"' in 行 or f"'{族}'" in 行:
                        违规.append(f"{文件}:{行号}: 写死字体族 {族} → 应改为 资产.字体(...)")
        self.assertEqual(违规, [], "界面代码出现写死的字体族：\n" + "\n".join(违规))

    def test_禁止写死检查自身有效(self):
        """自检：确认扫描规则真的能抓到违规写法（避免规则形同虚设）。"""
        假行 = '    self.configure(font=("Microsoft YaHei UI", 10), background="#ff0000")'
        self.assertTrue(颜色模式.search(假行), "颜色规则应能命中")
        self.assertTrue(any(f'"{族}"' in 假行 for 族 in 禁止出现的字体族), "字体规则应能命中")


class 运行时解析(unittest.TestCase):

    def setUp(self):
        try:
            import tkinter
            探针 = tkinter.Tk()
            探针.destroy()
        except Exception as 异常:
            self.skipTest(f"当前环境无图形界面：{异常!r}")

    def test_字体解析返回可用元组(self):
        import tkinter  # noqa: F401
        for 用途 in ("标题", "正文", "等宽"):
            结果 = 资产.字体(用途)
            self.assertIsInstance(结果, tuple)
            self.assertGreaterEqual(len(结果), 2)
            self.assertIsInstance(结果[0], str)
            self.assertGreater(int(结果[1]), 0)

    def test_子集字体可被注册且Tk可见(self):
        """过渡字体必须真的能被用上：文件存在 → 进程私有注册 → Tk 字体列表可见。"""
        import tkinter
        import tkinter.font
        根 = tkinter.Tk()
        try:
            已注册 = 资产.注册字体文件()
            self.assertTrue(已注册, "assets/fonts/ 下应有字体文件被注册")
            族 = {名.lower() for 名 in tkinter.font.families()}
            首选 = 资产.主题["字体"]["正文"]["候选"][0]
            self.assertIn(首选.lower(), 族,
                          f"候选链首位的字体「{首选}」应在注册后对 Tk 可见")
        finally:
            根.destroy()

    def test_主题缺失时退到内置兜底(self):
        原函数 = 资产.资产根目录
        资产.资产根目录 = lambda: os.path.join(夹具.仓库根目录, "不存在的资产目录")
        try:
            主题 = 资产.载入主题()
            self.assertTrue(资产.主题警告, "主题缺失时应有警告")
            self.assertIn("界面配色", 主题)
            self.assertTrue(主题["界面配色"], "内置兜底主题不应为空")
            self.assertTrue(资产.颜色("窗口底").startswith("#"))
        finally:
            资产.资产根目录 = 原函数
            资产.载入主题()          # 恢复正常主题


if __name__ == "__main__":
    unittest.main(verbosity=2)
