# -*- coding: utf-8 -*-
"""
Vinted 商品图片抓取工具 — PySide6 GUI（紧凑版）
Cal.com 极简风格 · 单窗口布局
"""
import os
import sys
import glob

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QGroupBox, QLabel, QLineEdit, QPlainTextEdit, QComboBox,
    QCheckBox, QPushButton, QProgressBar, QFileDialog, QMenu,
    QMessageBox, QDialog, QFrame, QSizePolicy, QListWidget, QScrollArea,
)
from PySide6.QtCore import Qt, Signal, QThread, QTimer, QMimeData
from PySide6.QtGui import QFont, QIcon, QPixmap, QPainter
import Vinted_抓图 as backend
import license_system as license_mgr
import update_checker

# 发布模式开关：True=隐藏日志面板及调试功能，False=全部显示
RELEASE_MODE = False

# 发布版专业文案映射（旧文本→新文本）
_RELEASE_DICT = {
    # 分组标题
    "商品链接管理": "任务队列",
    "基础参数设置": "处理配置",
    "任务操作": "执行控制",
    "运行日志": "处理记录",
    # 标签
    "商品链接（一行一个）：": "商品链接：",
    "保存路径：": "存储路径：",
    "拍摄地理：": "地理信息：",
    "有效链接：": "队列：",
    "成功：": "✓ ",
    "失败：": "✗ ",
    "状态：空闲中": "就绪",
    "状态：已停止": "已终止",
    "状态：已完成": "处理完成",
    "状态：正在停止任务": "正在安全终止...",
    "授权剩余": "授权有效期",
    # 复选框
    "智能压缩": "智能画质",
    "隐形水印": "数字水印",
    "无损画质": "原画输出",
    "高级防检测": "AI指纹重构",
    "机模画幅匹配": "机型自定义",
    "深度防重处理": "指纹深度重建",
    "输出版本数": "指纹版本数",
    # 按钮
    "开始抓取": "开始采集",
    "停止任务": "终止",
    "打开目录": "浏览文件",
    "本地防重 ▾": "本地处理 ▾",
    "一键清空": "清空",
    "批量导入": "导入",
    "链接去重": "去重",
    "导出失败链接": "导出失败项",
    "恢复默认": "重置",
    "清空日志": "清空",
    "检查更新": "版本更新",
    "激活软件": "激活",
    "验证中...": "验证中...",
    "复制": "复制",
    "退出": "退出",
    # 状态消息
    "正在启动浏览器": "正在初始化引擎...",
    "正在抓取商品图片": "正在采集商品图像...",
    "正在处理图片": "正在重构图像...",
    "开始抓取商品": "开始采集",
    "已获取页面 Cookie": "已建立安全会话",
    "已加载": "已解析",
    "缩略图": "预览",
    "收集到": "获取",
    "张大图": "张图像",
    "提取到": "采集到",
    "有效高清原图": "高清原始图像",
    "下载成功": "获取成功",
    "防重处理成功": "图像重构完成",
    "已写入地理信息": "已嵌入位置元数据",
    "商品处理完成": "采集完成",
    "商品抓取失败": "采集失败",
    "浏览器启动失败": "引擎初始化失败",
    "Chrome 已启动": "渲染引擎已就绪",
    "Chrome 浏览器已关闭": "渲染引擎已关闭",
    "全部完成": "任务结束",
    "任务已停止": "任务已终止",
    "Server Error": "服务器异常",
    "未找到商品容器": "页面结构异常",
    "页面加载失败": "页面加载失败",
    "未提取到商品图片": "未能提取图像数据",
    "分辨率升级": "画质增强",
    "张已升级": "张已优化",
    "已复制": "已复制",
    "请发送给卖家": "请发送给卖家",
    "已是最新版本": "已是最新版本",
    "发现新版本": "发现新版本",
    "正在下载更新": "正在获取更新...",
    "更新下载失败": "更新获取失败",
    "正在应用更新": "正在安装更新...",
    "正在检查更新": "正在检查更新...",
    "状态：正在下载更新": "正在获取更新包...",
    "请先粘贴激活码": "请输入激活码",
    "正在验证激活码...": "正在验证授权...",
    "激活出错：": "验证失败：",
    "已复制，请发送给卖家": "已复制标识，请发送给卖家",
}


def _tr(text):
    """发布模式下替换文案为专业表述"""
    if not RELEASE_MODE:
        return text
    result = text
    for old, new in _RELEASE_DICT.items():
        result = result.replace(old, new)
    return result


# ====================== 拖拽文本框 ======================
class DropPlainTextEdit(QPlainTextEdit):
    """支持拖拽 .txt 文件直接导入链接"""
    file_dropped = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            for url in event.mimeData().urls():
                if url.toLocalFile().lower().endswith('.txt'):
                    event.acceptProposedAction()
                    return
        event.ignore()

    def dropEvent(self, event):
        for url in event.mimeData().urls():
            path = url.toLocalFile()
            if path.lower().endswith('.txt') and os.path.exists(path):
                self.file_dropped.emit(path)
                event.acceptProposedAction()
                return
        event.ignore()


# ====================== 本地防重 Worker ======================
class LocalProcessWorker(QThread):
    log_signal = Signal(str, str)
    progress_signal = Signal(int, int)
    finished_signal = Signal(int)

    def __init__(self, paths, parent=None):
        super().__init__(parent)
        self.paths = paths

    def run(self):
        import Vinted_抓图 as be
        be._on_log = lambda c, l: self.log_signal.emit(c, l)
        be._on_status = lambda t: self.log_signal.emit(t, "info")
        total = len(self.paths)
        ok = 0
        for i, p in enumerate(self.paths):
            self.progress_signal.emit(i + 1, total)
            if not os.path.exists(p):
                self.log_signal.emit(f"文件不存在，跳过: {os.path.basename(p)}", "warning")
                continue
            if be.process_image(p, skip_gps=False):
                ok += 1
        self.finished_signal.emit(ok)


# ====================== Vinted 抓图 Worker ======================
class CrawlWorker(QThread):
    log_signal = Signal(str, str)
    status_signal = Signal(str)
    progress_signal = Signal(int, int, int, int)
    finished_signal = Signal(bool)

    def __init__(self, urls_text, debug_mode, parent=None):
        super().__init__(parent)
        self.urls_text = urls_text
        self.debug_mode = debug_mode

    def run(self):
        backend._on_log = lambda c, l: self.log_signal.emit(c, l)
        backend._on_status = lambda t: self.status_signal.emit(t)
        backend._on_progress = lambda c, t, s, f: self.progress_signal.emit(c, t, s, f)
        backend._on_finished = lambda s: self.finished_signal.emit(s)
        backend.start_crawl_task(self.urls_text, self.debug_mode)


# ====================== 软件激活对话框 ======================
class ActivationDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._activated = False
        self.setWindowTitle("图像重构MAX — 软件激活")
        self.setFixedSize(440, 400)
        self.setWindowFlags(Qt.Dialog | Qt.MSWindowsFixedSizeDialogHint)
        self.setStyleSheet("""
            QDialog { background-color: #ffffff; }
            QLabel { color: #374151; background: transparent; }
        """)
        self._build_ui()

    def _make_card(self):
        card = QFrame()
        card.setStyleSheet("""
            QFrame { background: #fafbfc; border: 1px solid #e8eaed;
            border-radius: 8px; }
        """)
        return card

    def _make_separator(self):
        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setStyleSheet("QFrame { border: none; border-top: 1px solid #e8eaed; background: transparent; }")
        sep.setFixedHeight(1)
        return sep

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(30, 24, 30, 20)
        root.setSpacing(0)

        # ---- 标题 ----
        brand = QLabel("图像重构MAX")
        brand.setAlignment(Qt.AlignCenter)
        brand.setStyleSheet("font-size: 20px; font-weight: 700; color: #111111;")
        root.addWidget(brand)
        sub = QLabel(_tr("软件激活"))
        sub.setAlignment(Qt.AlignCenter)
        sub.setStyleSheet("font-size: 12px; color: #9ca3af;")
        root.addWidget(sub)
        root.addSpacing(8)
        # 技术标签
        tech_row = QHBoxLayout()
        tech_row.setSpacing(4)
        for t in ["AI 深度重构", "JPEG 指纹重建", "时空元数据", "画幅智能匹配", "…等"]:
            l = QLabel(t)
            l.setAlignment(Qt.AlignCenter)
            l.setStyleSheet("font-size: 9px; color: #999; background: transparent; border: 1px solid #e0e0e0; border-radius: 3px; padding: 1px 6px;")
            tech_row.addWidget(l)
        tech_row.addStretch()
        root.addLayout(tech_row)
        root.addSpacing(10)

        # ---- 步骤 1 ----
        s1h = QHBoxLayout(); s1h.setSpacing(6)
        s1h.addWidget(self._step_badge("1"))
        s1h.addWidget(self._section_title(_tr("设备标识")))
        s1h.addStretch()
        root.addLayout(s1h)
        root.addSpacing(4)

        c1 = self._make_card()
        c1l = QHBoxLayout(c1); c1l.setContentsMargins(8, 2, 8, 2); c1l.setSpacing(6)
        self.hwid_display = QLineEdit()
        self.hwid_display.setReadOnly(True)
        self.hwid_display.setText(license_mgr.get_hwid())
        self.hwid_display.setStyleSheet("""
            QLineEdit { border: none; background: transparent; font-family: Consolas;
            font-size: 14px; letter-spacing: 1px; color: #111111; padding: 4px 0; }
        """)
        c1l.addWidget(self.hwid_display, 1)
        b1 = QPushButton("复制")
        b1.setFixedWidth(44)
        b1.setStyleSheet("""
            QPushButton { font-size: 12px; background: #ffffff; border: 1px solid #d1d5db;
            border-radius: 4px; padding: 3px 0; color: #374151; }
            QPushButton:hover { background: #f3f4f6; }
            QPushButton:pressed { background: #e5e7eb; }
        """)
        b1.clicked.connect(self._copy_hwid)
        c1l.addWidget(b1)
        root.addWidget(c1)

        root.addWidget(self._hint(_tr("请将以上标识发送给卖家获取激活码")))
        root.addSpacing(12)

        # ---- 步骤 2 ----
        s2h = QHBoxLayout(); s2h.setSpacing(6)
        s2h.addWidget(self._step_badge("2"))
        s2h.addWidget(self._section_title(_tr("激活码")))
        s2h.addStretch()
        root.addLayout(s2h)
        root.addSpacing(4)

        c2 = self._make_card()
        c2l = QVBoxLayout(c2); c2l.setContentsMargins(8, 2, 8, 2)
        self.code_input = QLineEdit()
        self.code_input.setPlaceholderText(_tr("粘贴激活码到此处"))
        self.code_input.setStyleSheet("""
            QLineEdit { border: none; background: transparent; font-family: Consolas;
            font-size: 13px; color: #111111; padding: 4px 0; }
        """)
        c2l.addWidget(self.code_input)
        root.addWidget(c2)

        root.addWidget(self._hint(_tr("激活码由卖家提供，一机一码")))
        root.addSpacing(14)

        # ---- 状态提示 ----
        self.msg_label = QLabel("")
        self.msg_label.setAlignment(Qt.AlignCenter)
        self.msg_label.setStyleSheet("font-size: 12px; color: #6b7280; min-height: 18px;")
        root.addWidget(self.msg_label)
        root.addSpacing(8)

        # ---- 按钮 ----
        bh = QHBoxLayout(); bh.setSpacing(10)
        bh.addStretch()
        self.btn_activate = QPushButton(_tr("激活软件"))
        self.btn_activate.setStyleSheet("""
            QPushButton { font-size: 13px; font-weight: 600; background: #111111;
            border: none; border-radius: 6px; padding: 8px 28px; color: #ffffff; }
            QPushButton:hover { background: #2d2d2d; }
            QPushButton:disabled { background: #b0b0b0; }
        """)
        self.btn_activate.setCursor(Qt.PointingHandCursor)
        self.btn_activate.clicked.connect(self._do_activate)
        bh.addWidget(self.btn_activate)
        self.btn_exit = QPushButton(_tr("退出"))
        self.btn_exit.setStyleSheet("""
            QPushButton { font-size: 13px; background: #ffffff; border: 1px solid #d1d5db;
            border-radius: 6px; padding: 8px 22px; color: #6b7280; }
            QPushButton:hover { background: #f9fafb; color: #374151; }
        """)
        self.btn_exit.clicked.connect(self.reject)
        bh.addWidget(self.btn_exit)
        bh.addStretch()
        root.addLayout(bh)

        root.addSpacing(14)
        root.addWidget(self._make_separator())
        root.addSpacing(8)
        contact = QLabel(_tr("需要激活码？请联系 微信：UU_L777777"))
        contact.setAlignment(Qt.AlignCenter)
        contact.setStyleSheet("font-size: 11px; color: #b0b0b0;")
        root.addWidget(contact)

    def _step_badge(self, num):
        b = QLabel(num)
        b.setAlignment(Qt.AlignCenter)
        b.setFixedSize(16, 16)
        b.setStyleSheet("font-size: 11px; font-weight: bold; color: #fff; background: #111111; border-radius: 8px;")
        return b

    def _section_title(self, text):
        l = QLabel(text)
        l.setStyleSheet("font-size: 13px; font-weight: 600; color: #374151;")
        return l

    def _hint(self, text):
        l = QLabel(text)
        l.setStyleSheet("font-size: 11px; color: #9ca3af; padding: 2px 0;")
        return l

    def _copy_hwid(self):
        QApplication.clipboard().setText(self.hwid_display.text())
        self.msg_label.setStyleSheet("font-size: 12px; color: #10b981;")
        self.msg_label.setText(_tr("已复制，请发送给卖家"))

    def _do_activate(self):
        code = self.code_input.text().strip()
        if not code:
            self.msg_label.setStyleSheet("font-size: 12px; color: #ef4444;")
            self.msg_label.setText(_tr("请先粘贴激活码"))
            return
        self.btn_activate.setEnabled(False)
        self.btn_activate.setText(_tr("验证中..."))
        self.msg_label.setStyleSheet("font-size: 12px; color: #6b7280;")
        self.msg_label.setText(_tr("正在验证激活码..."))
        QApplication.processEvents()
        try:
            ok, msg = license_mgr.activate(code)
            if ok:
                self._activated = True
                self.accept()
            else:
                self.btn_activate.setEnabled(True)
                self.btn_activate.setText("激活软件")
                self.msg_label.setStyleSheet("font-size: 12px; color: #ef4444;")
                self.msg_label.setText(msg)
        except Exception as e:
            self.btn_activate.setEnabled(True)
            self.btn_activate.setText("激活软件")
            self.msg_label.setStyleSheet("font-size: 12px; color: #ef4444;")
            self.msg_label.setText(f"激活出错：{e}")

    def is_activated(self):
        return self._activated


# ====================== 主窗口 ======================
class AiBgReplaceWorker(QThread):
    progress = Signal(int, int)
    finished = Signal(int, int)
    status = Signal(str)
    error = Signal(str)

    def __init__(self, paths, hwid, out_dir):
        super().__init__()
        self.paths = paths
        self.hwid = hwid
        self.out_dir = out_dir

    def run(self):
        import requests
        ok = 0
        total = len(self.paths)
        for i, p in enumerate(self.paths):
            self.status.emit(f"处理中 ({i+1}/{total})...")
            try:
                with open(p, "rb") as f:
                    files = {"image": (os.path.basename(p), f, "image/jpeg")}
                    data = {"hwid": self.hwid}
                    r = requests.post(
                        "https://vt-proxy.vtmax.workers.dev/ai-bg-replace",
                        files=files, data=data, timeout=180
                    )
                if r.status_code == 200 and len(r.content) > 1000:
                    out_name = f"{os.path.splitext(os.path.basename(p))[0]}_ai.jpg"
                    out_path = os.path.join(self.out_dir, out_name)
                    with open(out_path, "wb") as fo:
                        fo.write(r.content)
                    ok += 1
                elif r.status_code == 402:
                    self.error.emit("AI 余额不足，请联系管理员充值")
                    break
                else:
                    err = r.json().get("error", "未知错误") if r.headers.get("content-type","").startswith("application/json") else "服务异常"
                    self.error.emit(f"处理失败: {err}")
            except Exception as e:
                self.error.emit(f"网络错误: {e}")
            self.progress.emit(i + 1, total)
        self.finished.emit(ok, total)


class AiBgDialog(QDialog):
    def __init__(self, parent, hwid):
        super().__init__(parent)
        self.hwid = hwid
        self.paths = []
        self.setWindowTitle("AI 背景替换")
        self.setMinimumSize(520, 420)
        self.resize(560, 460)
        self._build()

    def _build(self):
        self.setStyleSheet("QDialog{background:#fff;} QLabel{color:#374151;background:transparent;} QListWidget{background:#fff;border:1px solid #e5e7eb;border-radius:6px;font-size:12px;color:#111;}")
        lo = QVBoxLayout(self)
        lo.setContentsMargins(24, 20, 24, 20)
        lo.setSpacing(10)

        # 标题
        title = QLabel("AI 真实场景替换")
        title.setStyleSheet("font-size:16px; font-weight:700; color:#111; background:transparent;")
        lo.addWidget(title)

        # 副标题
        sub = QLabel("借助AI大模型，为商品图片替换真实感背景")
        sub.setStyleSheet("font-size:12px; color:#999; background:transparent;")
        lo.addWidget(sub)

        # 余额
        self.credits_label = QLabel("查询余额中...")
        self.credits_label.setStyleSheet("font-size:12px; color:#10b981; background:transparent;")
        lo.addWidget(self.credits_label)
        self._refresh_credits()

        lo.addSpacing(4)

        # 文件选择
        btn_row = QHBoxLayout()
        btn_row.setSpacing(6)
        btn_add = QPushButton("添加图片")
        btn_add.setObjectName("btnSecondary")
        btn_add.setCursor(Qt.PointingHandCursor)
        btn_add.clicked.connect(self._add_files)
        btn_row.addWidget(btn_add)
        btn_clear = QPushButton("清空列表")
        btn_clear.setObjectName("btnSecondary")
        btn_clear.setCursor(Qt.PointingHandCursor)
        btn_clear.clicked.connect(self._clear_list)
        btn_row.addWidget(btn_clear)
        btn_row.addStretch()
        self.count_label = QLabel("已选：0 张")
        self.count_label.setStyleSheet("font-size:12px; color:#888; background:transparent;")
        btn_row.addWidget(self.count_label)
        lo.addLayout(btn_row)

        # 文件列表
        self.list_widget = QListWidget()
        self.list_widget.setMinimumHeight(120)
        lo.addWidget(self.list_widget, 1)

        # 进度
        self.progress_bar = QProgressBar()
        self.progress_bar.setMaximum(100)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setFixedHeight(5)
        lo.addWidget(self.progress_bar)
        self.status_label = QLabel("")
        self.status_label.setStyleSheet("font-size:11px; color:#888; background:transparent;")
        lo.addWidget(self.status_label)

        # 按钮
        btn_bot = QHBoxLayout()
        btn_bot.setSpacing(8)
        self.btn_process = QPushButton("开始处理")
        self.btn_process.setObjectName("btnStart")
        self.btn_process.setCursor(Qt.PointingHandCursor)
        self.btn_process.clicked.connect(self._start_process)
        self.btn_process.setEnabled(False)
        btn_bot.addWidget(self.btn_process)
        btn_bot.addStretch()
        self.btn_open = QPushButton("打开输出目录")
        self.btn_open.setObjectName("btnSecondary")
        self.btn_open.setCursor(Qt.PointingHandCursor)
        self.btn_open.clicked.connect(self._open_out)
        btn_bot.addWidget(self.btn_open)
        lo.addLayout(btn_bot)

    def _refresh_credits(self):
        try:
            import requests
            r = requests.get(f"https://vt-proxy.vtmax.workers.dev/ai-credits?hwid={self.hwid}", timeout=10)
            if r.status_code == 200:
                c = r.json().get("credits", 0)
                self.credits_label.setText(f"剩余次数：{c} 次")
        except:
            self.credits_label.setText("剩余次数：—")

    def _add_files(self):
        files, _ = QFileDialog.getOpenFileNames(self, "选择图片", "",
            "图片文件 (*.jpg *.jpeg *.png *.webp *.bmp)")
        for f in files:
            if f not in self.paths:
                self.paths.append(f)
                self.list_widget.addItem(os.path.basename(f))
        self._update_count()

    def _clear_list(self):
        self.paths.clear()
        self.list_widget.clear()
        self._update_count()

    def _update_count(self):
        self.count_label.setText(f"已选：{len(self.paths)} 张")
        self.btn_process.setEnabled(len(self.paths) > 0)

    def _start_process(self):
        if not self.paths:
            return
        self.btn_process.setEnabled(False)
        self._refresh_credits()
        out_dir = QFileDialog.getExistingDirectory(self, "选择输出目录")
        if not out_dir:
            self.btn_process.setEnabled(True)
            return

        self.worker = AiBgReplaceWorker(self.paths, self.hwid, out_dir)
        self.worker.progress.connect(lambda c,t: self.progress_bar.setValue(int(c/t*100)))
        self.worker.status.connect(lambda s: self.status_label.setText(s))
        self.worker.error.connect(lambda e: QMessageBox.warning(self, "错误", e))
        self.worker.finished.connect(self._on_finished)
        self.worker.start()

    def _on_finished(self, ok, total):
        self.progress_bar.setValue(100)
        self.status_label.setText(f"完成：{ok}/{total} 张处理成功")
        self._refresh_credits()
        self.btn_process.setEnabled(True)

    def _open_out(self):
        import subprocess
        subprocess.Popen(["explorer", os.path.abspath(".")])


class VintedScraperGUI(QMainWindow):
    def __init__(self):
        super().__init__()
        self._worker = None
        self._local_worker = None
        self._geo_setting_up = False

        self.setWindowTitle(f"图像重构MAX v{update_checker.CURRENT_VERSION} · 已就绪")
        # 窗口图标
        icon_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "app_icon.ico")
        if not os.path.exists(icon_path):
            frozen = getattr(sys, '_MEIPASS', None)
            if frozen:
                icon_path = os.path.join(frozen, "app_icon.ico")
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))
        if RELEASE_MODE:
            self.setMinimumSize(460, 570)
            self.setMaximumHeight(570)
            self.resize(520, 570)
        else:
            self.setMinimumSize(460, 650)
            self.resize(520, 700)

        screen = QApplication.primaryScreen().geometry()
        self.move((screen.width() - 500) // 2, (screen.height() - self.height()) // 2)

        self._load_config()
        self._build_ui()
        self._apply_config_to_ui()
        self._load_stylesheet()
        self._connect_signals()

        # 显示授权到期信息
        _, _, remaining = license_mgr.check_license()
        if remaining is not None:
            self.license_label.setText(_tr(f"授权剩余 {remaining} 天"))
        else:
            self.license_label.setText(_tr("永久授权"))

        # 启动后 3 秒静默检查更新
        QTimer.singleShot(3000, self._auto_check_update)

    # ---- 配置 ----
    def _load_config(self):
        cfg = backend.load_config()
        self._save_path = cfg.get("save_path", backend.DEFAULT_SAVE_ROOT)
        self._country = cfg.get("country", "法国")
        self._city = cfg.get("city", "全国随机")
        self._mode = cfg.get("mode", "随机位置")
        self._compress = cfg.get("compress_enabled", "False") == "True"
        self._watermark = cfg.get("watermark_enabled", "False") == "True"
        self._lossless = cfg.get("lossless_enabled", "False") == "True"
        self._advanced_anti_detect = cfg.get("advanced_anti_detect", "False") == "True"
        self._device_crop = cfg.get("device_crop", "False") == "True"
        self._device_model = cfg.get("device_model", "随机")
        self._deep_anti_duplicate = cfg.get("deep_anti_duplicate", "False") == "True"
        self._help_shown = cfg.get("help_shown", "False") == "True"
        self._deep_variants = int(cfg.get("deep_variants", "2"))

        backend.CUSTOM_SAVE_ROOT = self._save_path
        backend.COMPRESS_ENABLED = self._compress
        backend.WATERMARK_ENABLED = self._watermark
        backend.LOSSLESS_ENABLED = self._lossless
        backend.ADVANCED_ANTI_DETECT_ENABLED = self._advanced_anti_detect
        backend.DEVICE_CROP_ENABLED = self._device_crop
        backend.SELECTED_DEVICE = self._device_model
        backend.DEEP_ANTI_DUPLICATE_ENABLED = self._deep_anti_duplicate
        backend.DEEP_MODE_VARIANTS = self._deep_variants

        # 累计统计
        self._total_images = int(cfg.get("total_images", "0"))
        self._total_tasks = int(cfg.get("total_tasks", "0"))
        backend.set_geo(self._country, self._city, self._mode)

        geo = cfg.get("window_geometry", "")
        if geo:
            try:
                parts = geo.replace("+", "x").split("x")
                if len(parts) == 4:
                    w, h, x, y = int(parts[0]), int(parts[1]), int(parts[2]), int(parts[3])
                    self.resize(w, h)
                    self.move(x, y)
            except:
                pass

        # 恢复上次的链接
        saved_urls = cfg.get("last_urls", "")
        if saved_urls:
            self._restore_urls = saved_urls
        else:
            self._restore_urls = ""

        self._path_save_timer = QTimer(self)
        self._path_save_timer.setSingleShot(True)
        self._path_save_timer.setInterval(500)
        self._path_save_timer.timeout.connect(self._do_save_path)

    def _save_config(self):
        backend.save_config({
            "save_path": self._save_path,
            "country": self._country, "city": self._city, "mode": self._mode,
            "compress_enabled": str(self._compress),
            "watermark_enabled": str(self._watermark),
            "lossless_enabled": str(self._lossless),
            "advanced_anti_detect": str(self._advanced_anti_detect),
            "device_crop": str(self._device_crop),
            "device_model": self._device_model,
            "deep_anti_duplicate": str(self._deep_anti_duplicate),
            "help_shown": str(self._help_shown),
            "deep_variants": str(self._deep_variants),
            "total_images": str(self._total_images),
            "total_tasks": str(self._total_tasks),
        })

    def _load_stylesheet(self):
        p = os.path.join(os.path.dirname(os.path.abspath(__file__)), "vinted_style.qss")
        if os.path.exists(p):
            with open(p, "r", encoding="utf-8") as f:
                self.setStyleSheet(f.read())

    # ---- UI ----
    def _build_ui(self):
        c = QWidget()
        self.setCentralWidget(c)
        root = QVBoxLayout(c)
        root.setContentsMargins(10, 10, 10, 10)
        root.setSpacing(8)

        self._build_url_section(root)
        self._build_settings_section(root)
        self._build_task_section(root)
        if not RELEASE_MODE:
            self._build_log_section(root)

        # 技术规格脚注
        footer = QLabel(f"v{update_checker.CURRENT_VERSION} · 多维数字指纹重建 · 自适应传感器模拟 · 12 级深度处理管线 · 等多项核心技术")
        footer.setStyleSheet("font-size:10px; color:#888; background:transparent; padding:0 4px 2px 4px;")
        footer.setAlignment(Qt.AlignCenter)
        root.addWidget(footer)

    # ---- 模块 1：商品链接管理 ----
    def _build_url_section(self, parent):
        g = QGroupBox(_tr("商品链接管理"))
        lo = QVBoxLayout(g)
        lo.setContentsMargins(0, 8, 0, 4)
        lo.setSpacing(4)

        top = QHBoxLayout()
        top.addWidget(QLabel(_tr("商品链接（一行一个）：")))
        top.addStretch()
        self.btn_update = QPushButton(_tr("检查更新"))
        self.btn_update.setFlat(True)
        self.btn_update.setCursor(Qt.PointingHandCursor)
        self.btn_update.setStyleSheet("QPushButton { font-size: 11px; color: #b0b0b0; border: none; background: transparent; } QPushButton:hover { color: #111111; }")
        self.btn_update.clicked.connect(self._check_for_updates)
        self.btn_help = QPushButton("使用说明")
        self.btn_help.setFlat(True)
        self.btn_help.setCursor(Qt.PointingHandCursor)
        self.btn_help.setStyleSheet("QPushButton { font-size: 11px; color: #b0b0b0; border: none; background: transparent; } QPushButton:hover { color: #111111; }")
        self.btn_help.clicked.connect(self._show_help)
        top.addWidget(self.btn_help)
        top.addWidget(self.btn_update)
        self.url_count_label = QLabel(_tr("有效链接：0"))
        self.url_count_label.setObjectName("urlCountLabel")
        top.addWidget(self.url_count_label)
        lo.addLayout(top)

        self.txt_urls = DropPlainTextEdit()
        self.txt_urls.setPlaceholderText(_tr("粘贴商品链接，一行一个...（也可拖拽 .txt 文件）"))
        self.txt_urls.setMaximumHeight(68)
        lo.addWidget(self.txt_urls)

        btn = QHBoxLayout()
        btn.setSpacing(6)
        self.btn_clear_urls = QPushButton(_tr("一键清空"))
        self.btn_clear_urls.setObjectName("btnSecondary")
        btn.addWidget(self.btn_clear_urls)
        self.btn_import_urls = QPushButton(_tr("批量导入"))
        self.btn_import_urls.setObjectName("btnSecondary")
        btn.addWidget(self.btn_import_urls)
        self.btn_dedup_urls = QPushButton(_tr("链接去重"))
        self.btn_dedup_urls.setObjectName("btnSecondary")
        btn.addWidget(self.btn_dedup_urls)
        btn.addStretch()
        self.btn_export_fail = QPushButton(_tr("导出失败链接"))
        self.btn_export_fail.setObjectName("btnSecondary")
        btn.addWidget(self.btn_export_fail)
        lo.addLayout(btn)

        parent.addWidget(g)

    # ---- 模块 2：基础参数设置 ----
    def _build_settings_section(self, parent):
        g = QGroupBox(_tr("基础参数设置"))
        lo = QVBoxLayout(g)
        lo.setContentsMargins(0, 8, 0, 4)
        lo.setSpacing(6)

        # 行 1：保存路径
        r1 = QHBoxLayout()
        r1.setSpacing(6)
        r1.addWidget(QLabel(_tr("保存路径："), fixedWidth=60))
        self.entry_path = QLineEdit()
        self.entry_path.setPlaceholderText(backend.DEFAULT_SAVE_ROOT)
        r1.addWidget(self.entry_path, 1)
        self.btn_browse = QPushButton(_tr("浏览"))
        self.btn_browse.setObjectName("btnBrowse")
        r1.addWidget(self.btn_browse)
        lo.addLayout(r1)

        # 行 2：拍摄地理
        r2 = QHBoxLayout()
        r2.setSpacing(6)
        r2.addWidget(QLabel(_tr("拍摄地理："), fixedWidth=60))
        self.combo_country = QComboBox()
        self.combo_country.addItems(list(backend.GEO_DATA.keys()))
        self.combo_country.wheelEvent = lambda e: e.ignore()
        r2.addWidget(self.combo_country, 1)
        self.combo_city = QComboBox()
        self.combo_city.wheelEvent = lambda e: e.ignore()
        r2.addWidget(self.combo_city, 1)
        self.combo_mode = QComboBox()
        self.combo_mode.addItems(["随机位置", "固定位置"])
        self.combo_mode.wheelEvent = lambda e: e.ignore()
        r2.addWidget(self.combo_mode, 1)
        lo.addLayout(r2)

        # 能力标签行
        tag_row = QHBoxLayout()
        tag_label = QLabel("图像结构重组 · EXIF元数据注入 · 色温Gamma校正 · 传感器噪声模拟 · 等多项核心处理")
        tag_label.setStyleSheet("font-size:10px; color:#999; background:transparent; padding:2px 0;")
        tag_row.addWidget(tag_label)
        tag_row.addStretch()
        lo.addLayout(tag_row)

        # 指示灯
        self._dots = {}
        def _add_chk(layout, text, tip):
            chk = QCheckBox(_tr(text)); chk.setToolTip(tip)
            chk.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
            dot = QLabel(); dot.setFixedSize(4,4); dot.setStyleSheet("background:#10b981;border-radius:2px;")
            wrap = QWidget(); wrap.setStyleSheet("background:transparent;")
            wrap.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
            hh = QHBoxLayout(wrap); hh.setContentsMargins(0,0,0,0); hh.setSpacing(1)
            hh.addWidget(chk); hh.addWidget(dot)
            hh.setAlignment(dot, Qt.AlignTop)
            layout.addWidget(wrap, 0, Qt.AlignLeft)
            self._dots[chk] = dot
            return chk

        # 行 3：复选框行1
        r3 = QHBoxLayout()
        r3.setSpacing(10)

        self.chk_compress   = _add_chk(r3, "智能压缩", "智能画质优化，适度降低文件大小")
        self.chk_lossless   = _add_chk(r3, "无损画质", "原画输出，quality=100")
        self.chk_watermark  = _add_chk(r3, "隐形水印", "添加防重数字水印")
        self.chk_advanced_anti_detect = _add_chk(r3, "高级防检测", "AI 防护引擎")
        r3.addStretch()
        self.btn_reset = QPushButton(_tr("恢复默认"))
        self.btn_reset.setObjectName("btnSecondary")
        r3.addWidget(self.btn_reset)
        lo.addLayout(r3)

        # 行 3b：复选框行2
        r3b = QHBoxLayout()
        r3b.setSpacing(10)

        self.chk_device_crop = _add_chk(r3b, "机模画幅匹配", "根据随机设备型号裁切到原生画幅比例")
        self.combo_device = QComboBox()
        self.combo_device.addItems(backend.DEVICE_LIST)
        self.combo_device.setToolTip("选择模拟设备型号")
        self.combo_device.wheelEvent = lambda e: e.ignore()
        self.combo_device.setMaximumWidth(160)
        r3b.addWidget(self.combo_device)
        r3b.addSpacing(10)
        self.chk_deep_anti_duplicate = _add_chk(r3b, "深度防重处理", "仿射剪切+镜头畸变+参数增强，针对平台重复检测重建图像指纹")
        lbl_var = QLabel(_tr("输出版本数"))
        lbl_var.setStyleSheet("font-size:12px; color:#888; background:transparent;")
        r3b.addWidget(lbl_var)
        self.combo_variants = QComboBox()
        self.combo_variants.addItems(["1", "2", "3"])
        self.combo_variants.setCurrentIndex(1)
        self.combo_variants.setToolTip("深度模式下输出多个指纹不同的版本")
        self.combo_variants.wheelEvent = lambda e: e.ignore()
        self.combo_variants.setMaximumWidth(50)
        r3b.addWidget(self.combo_variants)
        r3b.addStretch()
        lo.addLayout(r3b)

        parent.addWidget(g)

    # ---- 模块 3：任务操作 ----
    def _build_task_section(self, parent):
        g = QGroupBox(_tr("任务操作"))
        lo = QVBoxLayout(g)
        lo.setContentsMargins(0, 8, 0, 4)
        lo.setSpacing(6)

        # 状态 + 统计
        bar = QHBoxLayout()
        self.status_label = QLabel(_tr("状态：空闲中"))
        self.status_label.setObjectName("statusLabel")
        bar.addWidget(self.status_label)
        bar.addStretch()
        self.license_label = QLabel("")
        self.license_label.setObjectName("licenseLabel")
        bar.addWidget(self.license_label)
        bar.addSpacing(8)
        self.stats_label = QLabel("")
        self.stats_label.setStyleSheet("font-size: 11px; color: #999; background: transparent;")
        bar.addWidget(self.stats_label)
        bar.addSpacing(12)
        self.stat_label = QLabel(_tr('<span style="color:#10b981;">成功：0</span> | <span style="color:#ef4444;">失败：0</span>'))
        self.stat_label.setObjectName("statLabel")
        self.stat_label.setTextFormat(Qt.RichText)
        bar.addWidget(self.stat_label)
        lo.addLayout(bar)

        # 进度条
        self.progress_bar = QProgressBar()
        self.progress_bar.setMaximum(100)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setFixedHeight(5)
        lo.addWidget(self.progress_bar)

        # 按钮
        btn = QHBoxLayout()
        btn.setSpacing(5)
        self.btn_start = QPushButton(_tr("开始抓取"))
        self.btn_start.setObjectName("btnStart")
        btn.addWidget(self.btn_start)
        self.btn_stop = QPushButton(_tr("停止任务"))
        self.btn_stop.setObjectName("btnStop")
        self.btn_stop.setEnabled(False)
        btn.addWidget(self.btn_stop)
        btn.addStretch()
        self.btn_open_dir = QPushButton(_tr("打开目录"))
        self.btn_open_dir.setObjectName("btnSecondary")
        btn.addWidget(self.btn_open_dir)
        self.btn_local = QPushButton(_tr("本地防重 ▾"))
        self.btn_local.setObjectName("btnSecondary")
        btn.addWidget(self.btn_local)
        self.btn_ai_bg = QPushButton("AI 背景替换")
        self.btn_ai_bg.setObjectName("btnSecondary")
        self.btn_ai_bg.setStyleSheet("QPushButton#btnSecondary { color: #10b981; border-color: #10b981; } QPushButton#btnSecondary:hover { background-color: #ecfdf5; }")
        self.btn_ai_bg.clicked.connect(self._show_ai_bg_dialog)
        btn.addWidget(self.btn_ai_bg)
        lo.addLayout(btn)

        parent.addWidget(g)

    # ---- 模块 4：运行日志 ----
    def _build_log_section(self, parent):
        g = QGroupBox(_tr("运行日志"))
        lo = QVBoxLayout(g)
        lo.setContentsMargins(0, 8, 0, 2)
        lo.setSpacing(4)

        tb = QHBoxLayout()
        tb.addStretch()
        self.btn_clear_log = QPushButton(_tr("清空日志"))
        self.btn_clear_log.setObjectName("btnSecondary")
        tb.addWidget(self.btn_clear_log)
        lo.addLayout(tb)

        self.log_view = QPlainTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setMaximumBlockCount(3000)
        self.log_view.setFont(QFont("Consolas", 10))
        self.log_view.setStyleSheet("""
            QPlainTextEdit {
                background-color: #fafafa; border: 1px solid #e5e7eb;
                border-radius: 6px; padding: 6px 10px; color: #374151;
                font-family: "Consolas", "Courier New", monospace; font-size: 12px;
            }
        """)
        self.log_view.setContextMenuPolicy(Qt.CustomContextMenu)
        self.log_view.customContextMenuRequested.connect(self._show_log_menu)
        lo.addWidget(self.log_view)

        parent.addWidget(g, 1)

    # ---- 配置 → UI ----
    def _apply_config_to_ui(self):
        self._geo_setting_up = True
        self.entry_path.setText(self._save_path)
        self.combo_country.setCurrentText(self._country)
        self._update_city_list()
        self.combo_city.setCurrentText(self._city)
        self.combo_mode.setCurrentText(self._mode)
        self._update_mode_state()
        self.chk_compress.setChecked(self._compress)
        self.chk_watermark.setChecked(self._watermark)
        self.chk_lossless.setChecked(self._lossless)
        self.chk_advanced_anti_detect.setChecked(self._advanced_anti_detect)
        self.chk_device_crop.setChecked(self._device_crop)
        self.combo_device.setCurrentText(self._device_model)
        self.chk_deep_anti_duplicate.setChecked(self._deep_anti_duplicate)
        self.combo_variants.setCurrentText(str(self._deep_variants))
        self._update_dots()
        self._geo_setting_up = False
        self._update_stats_display()
        if getattr(self, '_restore_urls', ''):
            self.txt_urls.setPlainText(self._restore_urls)
        self._update_url_count()

    # ---- 信号 ----
    def _connect_signals(self):
        self.entry_path.mouseDoubleClickEvent = lambda e: self._open_save_dir()
        self.txt_urls.textChanged.connect(self._update_url_count)
        self.txt_urls.file_dropped.connect(self._on_file_dropped)
        self.btn_clear_urls.clicked.connect(self._clear_urls)
        self.btn_import_urls.clicked.connect(self._import_urls)
        self.btn_dedup_urls.clicked.connect(self._deduplicate_urls)
        self.btn_export_fail.clicked.connect(self._export_failed_urls)
        self.entry_path.textChanged.connect(self._on_path_text_changed)
        self.btn_browse.clicked.connect(self._browse_path)
        self.combo_country.currentTextChanged.connect(self._on_country_changed)
        self.combo_city.currentTextChanged.connect(self._on_city_changed)
        self.combo_mode.currentTextChanged.connect(self._on_mode_changed)
        self.chk_compress.toggled.connect(self._on_compress_toggled)
        self.chk_watermark.toggled.connect(self._on_watermark_toggled)
        self.chk_lossless.toggled.connect(self._on_lossless_toggled)
        self.chk_advanced_anti_detect.toggled.connect(self._on_advanced_anti_detect_toggled)
        self.chk_device_crop.toggled.connect(self._on_device_crop_toggled)
        self.combo_device.currentTextChanged.connect(self._on_device_changed)
        self.chk_deep_anti_duplicate.toggled.connect(self._on_deep_anti_duplicate_toggled)
        self.combo_variants.currentTextChanged.connect(self._on_variants_changed)
        self.btn_reset.clicked.connect(self._reset_defaults)
        self.btn_start.clicked.connect(self._start_crawl)
        self.btn_stop.clicked.connect(self._stop_crawl)
        self.btn_open_dir.clicked.connect(self._open_save_dir)
        if not RELEASE_MODE:
            self.btn_clear_log.clicked.connect(self._clear_log)
        self.btn_local.clicked.connect(self._show_local_menu)

        # 窗口级拖拽：图片文件拖入触发本地防重
        self.setAcceptDrops(True)

    # ---- URL 管理 ----
    def _update_url_count(self):
        text = self.txt_urls.toPlainText()
        urls = [u.strip() for u in text.split("\n") if u.strip() and "http" in u]
        self.url_count_label.setText(f"有效链接：{len(list(dict.fromkeys(urls)))}")

    def _on_file_dropped(self, path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                self.txt_urls.setPlainText(f.read())
            self._deduplicate_urls()
            self._add_log(f"✅ 已拖拽导入：{os.path.basename(path)}", "success")
        except Exception as e:
            QMessageBox.critical(self, "错误", f"导入失败：{e}")

    def _clear_urls(self):
        self.txt_urls.clear()

    def _import_urls(self):
        path, _ = QFileDialog.getOpenFileName(self, "选择链接文件", "", "文本文件 (*.txt);;所有文件 (*.*)")
        if path and os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    self.txt_urls.setPlainText(f.read())
                self._deduplicate_urls()
                self._add_log("✅ 成功从文件导入链接", "success")
            except Exception as e:
                QMessageBox.critical(self, "错误", f"导入失败：{e}")

    def _deduplicate_urls(self):
        text = self.txt_urls.toPlainText()
        urls = list(dict.fromkeys([u.strip() for u in text.split("\n") if u.strip()]))
        self.txt_urls.setPlainText("\n".join(urls))

    def _export_failed_urls(self):
        if not backend.FAILED_URLS:
            QMessageBox.information(self, "提示", "暂无失败的链接！")
            return
        path, _ = QFileDialog.getSaveFileName(self, "保存失败链接", "failed_urls.txt", "文本文件 (*.txt)")
        if path:
            with open(path, "w", encoding="utf-8") as f:
                f.write("\n".join(backend.FAILED_URLS))

    # ---- 设置回调 ----
    def _on_path_text_changed(self, text):
        """每次按键只更新内存值，500ms 无输入后才写磁盘"""
        self._save_path = text.strip() or backend.DEFAULT_SAVE_ROOT
        backend.CUSTOM_SAVE_ROOT = self._save_path
        self._path_save_timer.start()

    def _do_save_path(self):
        self._save_config()

    def _browse_path(self):
        path = QFileDialog.getExistingDirectory(self, "选择图片保存文件夹")
        if path:
            self.entry_path.setText(path)

    def _on_country_changed(self, text):
        self._country = text
        self._update_city_list()
        self._update_geo()
        self._save_config()

    def _on_city_changed(self, text):
        if self._geo_setting_up: return
        self._city = text
        self._update_mode_state()
        self._update_geo()
        self._save_config()

    def _on_mode_changed(self, text):
        if self._geo_setting_up: return
        self._mode = text
        self._update_geo()
        self._save_config()

    def _update_city_list(self):
        self._geo_setting_up = True
        cities = ["全国随机"] + list(backend.GEO_DATA.get(self._country, {}).keys())
        cur = self.combo_city.currentText()
        self.combo_city.clear()
        self.combo_city.addItems(cities)
        if cur in cities:
            self.combo_city.setCurrentText(cur)
        self._geo_setting_up = False

    def _update_mode_state(self):
        self.combo_mode.setEnabled(self.combo_city.currentText() != "全国随机")

    def _update_geo(self):
        backend.set_geo(self._country, self._city, self._mode)

    def _on_compress_toggled(self, v):
        self._compress = v
        backend.COMPRESS_ENABLED = v
        if v:
            self.chk_lossless.setChecked(False)
        self._update_dots()
        self._save_config()

    def _on_watermark_toggled(self, v):
        self._watermark = v
        backend.WATERMARK_ENABLED = v
        self._update_dots()
        self._save_config()

    def _on_lossless_toggled(self, v):
        self._lossless = v
        backend.LOSSLESS_ENABLED = v
        if v:
            self.chk_compress.setChecked(False)
            if self.chk_advanced_anti_detect.isChecked() or self.chk_deep_anti_duplicate.isChecked():
                QMessageBox.information(self, "原画输出提示",
                    "原画输出（quality=100）会跳过 JPEG 质量随机化，\n"
                    "AI指纹重构和指纹深度重建的防重效果将略微降低。\n\n"
                    "建议：日常使用建议关闭原画输出，\n"
                    "需要最高画质时再开启。")
        self._update_dots()
        self._save_config()

    def _on_advanced_anti_detect_toggled(self, v):
        self._advanced_anti_detect = v
        backend.ADVANCED_ANTI_DETECT_ENABLED = v
        if v and self.chk_lossless.isChecked():
            QMessageBox.information(self, "原画输出提示",
                "当前已开启原画输出（quality=100），\n"
                "AI指纹重构的 JPEG 质量随机化将被跳过，\n"
                "防重效果略微降低。")
        self._update_dots()
        self._save_config()

    def _on_device_crop_toggled(self, v):
        self._device_crop = v
        backend.DEVICE_CROP_ENABLED = v
        self._update_dots()
        self._save_config()

    def _on_device_changed(self, text):
        self._device_model = text
        backend.SELECTED_DEVICE = text
        self._save_config()

    def _update_dots(self):
        for chk, dot in self._dots.items():
            dot.setStyleSheet(f"background:{'#10b981' if chk.isChecked() else '#444'};border-radius:2px;")

    def _on_deep_anti_duplicate_toggled(self, v):
        self._deep_anti_duplicate = v
        backend.DEEP_ANTI_DUPLICATE_ENABLED = v
        if v and self.chk_lossless.isChecked():
            QMessageBox.information(self, "原画输出提示",
                "当前已开启原画输出（quality=100），\n"
                "指纹深度重建的 JPEG 质量随机化将被跳过，\n"
                "防重效果略微降低。")
        self._update_dots()
        self._save_config()

    def _on_variants_changed(self, text):
        self._deep_variants = int(text)
        backend.DEEP_MODE_VARIANTS = int(text)
        self._save_config()

    def _reset_defaults(self):
        if QMessageBox.Yes == QMessageBox.question(self, "确认", "恢复所有默认设置并重启？"):
            if os.path.exists(backend.CONFIG_FILE):
                os.remove(backend.CONFIG_FILE)
            os.execl(sys.executable, sys.executable, *sys.argv)

    # ---- 任务 ----
    def _start_crawl(self):
        if self._worker and self._worker.isRunning():
            return
        text = self.txt_urls.toPlainText().strip()
        if not text:
            return QMessageBox.warning(self, "警告", "请输入至少一个商品链接！")
        # 校验链接格式
        urls = [u.strip() for u in text.split("\n") if u.strip()]
        valid = [u for u in urls if "http" in u]
        if not valid:
            return QMessageBox.warning(self, "警告", "未检测到有效的商品链接！\n\n请确认链接格式正确")
        save_path = self.entry_path.text().strip() or backend.DEFAULT_SAVE_ROOT
        if not os.path.exists(save_path):
            if QMessageBox.Yes != QMessageBox.question(self, "提示", f"目录不存在，是否创建？\n{save_path}"):
                return
            os.makedirs(save_path)
        backend.CUSTOM_SAVE_ROOT = save_path
        self._save_path = save_path
        self._save_config()

        self._set_ui_running(True)
        self.status_label.setText("处理中…")
        self._worker = CrawlWorker(text, False)
        self._worker.log_signal.connect(self._add_log)
        self._worker.status_signal.connect(lambda s: self.status_label.setText("处理中…"))
        self._worker.progress_signal.connect(self._on_progress)
        self._worker.finished_signal.connect(self._on_task_finished)
        self._worker.start()

    def _stop_crawl(self):
        backend.STOP_TASK = True
        self.status_label.setText(_tr("状态：正在停止任务"))
        self.btn_stop.setEnabled(False)
        self._add_log("⚠️ 正在停止任务，请稍候...", "warning")

    def _on_progress(self, current, total, success, fail):
        if total > 0:
            self.progress_bar.setMaximum(total)
            self.progress_bar.setValue(current)
        self.stat_label.setText(f'<span style="color:#10b981;">成功：{success}</span> | <span style="color:#ef4444;">失败：{fail}</span>')

    def _on_task_finished(self, stopped):
        self._set_ui_running(False)
        self._worker = None
        self._last_output_dir = backend.CUSTOM_SAVE_ROOT if backend.CUSTOM_SAVE_ROOT and os.path.isdir(backend.CUSTOM_SAVE_ROOT) else None
        self.status_label.setText(_tr("状态：已停止") if stopped else "处理完成")
        _session_images = backend.TOTAL_IMAGES
        if not stopped:
            self._total_tasks += backend.TOTAL_TASKS
            self._total_images += _session_images
            backend.TOTAL_IMAGES = 0
            self._save_config()
            self._update_stats_display()

        total, success, fail = backend.TOTAL_TASKS, backend.SUCCESS_COUNT, backend.FAIL_COUNT
        # 处理清单
        features = []
        if backend.ADVANCED_ANTI_DETECT_ENABLED:
            features.append("  ✓  AI指纹重构引擎")
            features.append("  ✓  色温映射 & 曝光补偿")
            features.append("  ✓  JPEG 指纹重建")
        if backend.WATERMARK_ENABLED:
            features.append("  ✓  数字指纹水印")
        if backend.DEVICE_CROP_ENABLED:
            features.append("  ✓  机型自定义")
        features.append("  ✓  时空元数据注入")
        feature_text = "\n".join(features) if features else ""

        info = f"处理商品：{total}    采集图片：{_session_images}    成功：{success}    失败：{fail}"
        if feature_text:
            info += f"\n\n已应用处理：\n{feature_text}"
        if fail > 0 and backend.FAIL_REASONS:
            reasons = []
            for url in backend.FAILED_URLS[-3:]:
                r = backend.FAIL_REASONS.get(url, "未知错误")
                short_url = url.split("?")[0].split("/")[-1] if "/" in url else url[-20:]
                reasons.append(f"  {short_url}: {r}")
            info += "\n\n失败项目：\n" + "\n".join(reasons)

        msg = QMessageBox(self)
        msg.setWindowTitle(_tr("任务完成"))
        msg.setIcon(QMessageBox.Information)
        msg.setStandardButtons(QMessageBox.Ok)
        msg.setDefaultButton(QMessageBox.Ok)
        msg.setText(_tr(f"任务执行完毕"))
        msg.setInformativeText(info)
        msg.setStyleSheet("QMessageBox QLabel#qt_msgbox_informativelabel { font-size: 13px; }")
        btn_open = msg.addButton("浏览文件", QMessageBox.ActionRole)
        btn_preview = msg.addButton("预览对比", QMessageBox.ActionRole)
        btn_clear = msg.addButton("清空队列", QMessageBox.ActionRole)
        btn_export = None
        if backend.FAILED_URLS:
            btn_export = msg.addButton("导出失败项", QMessageBox.ActionRole)
        msg.exec()
        clicked = msg.clickedButton()
        if clicked == btn_open:
            self._open_save_dir()
        elif clicked == btn_preview:
            self._show_preview()
        elif clicked == btn_clear:
            self._clear_urls()
        elif btn_export and clicked == btn_export:
            self._export_failed_urls()

    def _update_stats_display(self):
        self.stats_label.setText(f"累计 {self._total_tasks} 次采集 · {self._total_images} 张图像")

    def _show_ai_bg_dialog(self):
        QMessageBox.information(self, "AI 背景替换",
            "该功能正在紧锣密鼓地开发中，即将与您见面。\n\n"
            "借助最先进的AI大模型，为您一键替换图片背景，\n"
            "模拟个人卖家的真实拍摄场景，效果以假乱真。\n\n"
            "敬请期待！")

    def _get_hwid(self):
        try:
            import license_system
            return license_system.get_hwid()
        except:
            return "UNKNOWN"

    def _set_ui_running(self, running):
        self.btn_start.setEnabled(not running)
        self.btn_stop.setEnabled(running)
        self.txt_urls.setReadOnly(running)
        self.entry_path.setReadOnly(running)
        self.combo_country.setEnabled(not running)
        self.combo_city.setEnabled(not running)
        self.combo_mode.setEnabled(not running and self.combo_city.currentText() != "全国随机")
        self.chk_compress.setEnabled(not running)
        self.chk_watermark.setEnabled(not running)
        self.chk_lossless.setEnabled(not running)
        self.chk_advanced_anti_detect.setEnabled(not running)
        self.chk_device_crop.setEnabled(not running)
        self.chk_deep_anti_duplicate.setEnabled(not running)
        self.combo_device.setEnabled(not running)
        self.btn_local.setEnabled(not running)
        self.btn_ai_bg.setEnabled(not running)
        if not running:
            backend.STOP_TASK = False
            self.progress_bar.setMaximum(100)
            self.progress_bar.setValue(0)
            self._update_dots()

    # ---- 日志 ----
    def _add_log(self, content, level="info"):
        content = _tr(content)
        if RELEASE_MODE:
            return  # 静默模式不显示日志
        colors = {"success": "#10b981", "warning": "#f59e0b", "error": "#ef4444", "info": "#374151"}
        c = colors.get(level, "#374151")
        self.log_view.appendHtml(f'<span style="color:{c};white-space:pre;">{content.replace("&","&amp;").replace("<","&lt;").replace(">","&gt;")}</span>')
        self.log_view.verticalScrollBar().setValue(self.log_view.verticalScrollBar().maximum())

    def _clear_log(self):
        if not RELEASE_MODE:
            self.log_view.clear()

    def _show_log_menu(self, pos):
        if RELEASE_MODE:
            return
        m = QMenu(self)
        a1 = m.addAction("复制选中内容")
        a2 = m.addAction("复制全部日志")
        m.addSeparator()
        a3 = m.addAction("清空日志")
        action = m.exec(self.log_view.mapToGlobal(pos))
        if action == a1:
            self.log_view.copy()
        elif action == a2:
            QApplication.clipboard().setText(self.log_view.toPlainText())
        elif action == a3:
            self._clear_log()

    # ---- 本地防重 ----
    def _show_local_menu(self):
        if self._local_worker and self._local_worker.isRunning():
            return
        m = QMenu(self)
        a1 = m.addAction("选择图片文件...")
        a2 = m.addAction("选择图片文件夹...")
        action = m.exec(self.btn_local.mapToGlobal(self.btn_local.rect().bottomLeft()))
        if action == a1:
            self._local_select_files()
        elif action == a2:
            self._local_select_folder()

    def _local_select_files(self):
        paths, _ = QFileDialog.getOpenFileNames(
            self, "选择图片文件", "",
            "图片文件 (*.jpg *.jpeg *.png *.webp *.bmp);;所有文件 (*.*)"
        )
        if paths:
            self._run_local_worker(paths)

    def _local_select_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "选择图片文件夹")
        if not folder:
            return
        paths = []
        for ext in ('.jpg', '.jpeg', '.png', '.webp', '.bmp'):
            paths.extend(glob.glob(os.path.join(folder, '**', '*' + ext), recursive=True))
            paths.extend(glob.glob(os.path.join(folder, '**', '*' + ext.upper()), recursive=True))
        if paths:
            self._run_local_worker(paths)
        else:
            self._add_log("⚠️ 所选文件夹中没有图片文件", "warning")

    def _run_local_worker(self, paths):
        import shutil as _shutil
        variants = backend.DEEP_MODE_VARIANTS if backend.DEEP_ANTI_DUPLICATE_ENABLED else 1
        # 输出到保存路径，不存在则用第一张图目录兜底
        base_dir = self._save_path if self._save_path and os.path.isdir(self._save_path) else (os.path.dirname(paths[0]) if paths else ".")
        from datetime import datetime
        ts = datetime.now().strftime("%Y%m%d_%H%M")
        out_dir = os.path.join(base_dir, f"Processed_{ts}")
        os.makedirs(out_dir, exist_ok=True)
        self._last_output_dir = out_dir
        self._last_source_paths = list(paths)

        expanded = []
        self._deep_copies = []
        for p in paths:
            base, ext = os.path.splitext(os.path.basename(p))
            cp = os.path.join(out_dir, f"{base}{ext}")
            _shutil.copy2(p, cp)
            expanded.append(cp)
            self._deep_copies.append(cp)
            for v in range(2, variants + 1):
                cp_v = os.path.join(out_dir, f"{base}_v{v}{ext}")
                _shutil.copy2(p, cp_v)
                expanded.append(cp_v)
                self._deep_copies.append(cp_v)
        if variants > 1:
            self._add_log(f"🖼 开始本地处理，{len(paths)} 张图片 → 深度模式各输出 {variants} 个版本，共 {len(expanded)} 次 → {out_dir}", "info")
        else:
            self._add_log(f"🖼 开始本地防重处理，共 {len(paths)} 张图片 → {out_dir}", "info")
        self._local_worker = LocalProcessWorker(expanded)
        self._local_worker.log_signal.connect(self._add_log)
        self._local_worker.progress_signal.connect(
            lambda c, t: (self.progress_bar.setMaximum(t), self.progress_bar.setValue(c),
                          self.status_label.setText(f"本地处理中... {c}/{t}"))
        )
        self._local_worker.finished_signal.connect(self._on_local_finished)
        self.btn_local.setEnabled(False)
        self.status_label.setText("本地处理中...")
        self._local_worker.start()

    def _on_local_finished(self, ok):
        self._deep_copies = []
        self._local_worker = None
        self.btn_local.setEnabled(True)
        self.progress_bar.setMaximum(100)
        self.progress_bar.setValue(0)
        self.status_label.setText(f"本地处理完成，成功 {ok} 张")
        self._add_log(f"✅ 本地防重完成，成功 {ok} 张", "success")
        if ok > 0:
            msg = QMessageBox(self)
            msg.setWindowTitle("处理完成")
            msg.setText(f"本地处理完成，成功 {ok} 张")
            msg.setStandardButtons(QMessageBox.Ok)
            btn_open = msg.addButton("浏览文件", QMessageBox.ActionRole)
            btn_preview = msg.addButton("预览对比", QMessageBox.ActionRole)
            msg.exec()
            if msg.clickedButton() == btn_open:
                self._open_save_dir()
            elif msg.clickedButton() == btn_preview:
                self._show_preview()

    def _show_help(self):
        dlg = QDialog(self)
        dlg.setWindowTitle("使用说明")
        dlg.setMinimumSize(520, 520)
        dlg.resize(560, 580)
        dlg.setStyleSheet("""
            QDialog { background-color: #1a1a1a; }
            QLabel { color: #ccc; background: transparent; }
            QTextBrowser { border: 1px solid #333; border-radius: 8px; padding: 16px;
                background-color: #222; color: #bbb; }
        """)
        layout = QVBoxLayout(dlg)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(0)

        html = """<style>
body { font-family: 'Microsoft YaHei','PingFang SC',sans-serif; font-size:14px; color:#bbb; line-height:1.8; margin:0; background:#222; text-align:center; }
li { text-align:left; display:inline-block; width:100%; }
h2 { font-size:17px; color:#e0e0e0; margin:20px 0 8px 0; padding-bottom:6px; border-bottom:1px solid #2a2a2a; }
h2:first-child { margin-top:0; }
b { color:#e0e0e0; }
.q { color:#10b981; font-weight:600; margin-top:12px; }
.a { color:#888; margin-left:0; margin-bottom:4px; }
.num { display:inline-block; background:#333; color:#ccc; width:20px; height:20px; border-radius:10px; text-align:center; line-height:20px; font-size:11px; margin-right:6px; }
li { margin:2px 0; list-style:none; }
</style>
<h2>使用步骤</h2>
<li><span class=num>1</span> 粘贴商品链接，一行一个</li>
<li><span class=num>2</span> 勾选需要的处理配置（推荐全开）</li>
<li><span class=num>3</span> 设置保存路径</li>
<li><span class=num>4</span> 设置国家城市</li>
<li><span class=num>5</span> 点击 <b>开始采集</b></li>
<li><span class=num>6</span> 完成后点击 <b>浏览文件</b></li>

<h2>处理配置</h2>
<li><b>智能画质</b> &nbsp;智能优化图像体积，兼顾画质与上传速度</li>
<li><b>原画输出</b> &nbsp;无损级保留全部图像细节，与智能画质互斥</li>
<li><b>数字水印</b> &nbsp;嵌入不可见数字标识，可用于版权保护</li>
<li><b>AI指纹重构</b> &nbsp;多维重建图像特征空间，推荐始终开启</li>
<li><b>指纹深度重建</b> &nbsp;深层结构重组，适用于补图或旧图翻新场景</li>
<li><b>机型自定义</b> &nbsp;模拟指定设备成像特征，保持随机即可</li>
<li style='color:#666;font-size:12px;margin-top:6px;'>提示：AI指纹重构和指纹深度重建涉及图像重编码，画质会有轻微下降，日常使用建议仅开启AI指纹重构即可</li>

<h2>本地处理</h2>
<li>拖入图片或文件夹到窗口，或点击 <b>本地处理</b> 选择</li>
<li>支持 JPG / PNG / WebP / BMP 格式</li>
<li>结果输出到 Processed 文件夹，原图不动</li>

<h2>常见问题</h2>
<div class=q>Q: 提示未检测到有效链接？</div>
<div class=a>A: 请检查链接格式是否正确。</div>
<div class=q>Q: 处理后图片看起来一样？</div>
<div class=a>A: 肉眼一样但数字指纹已完全重建。</div>
<div class=q>Q: 提示授权已过期？</div>
<div class=a>A: 联系管理员续期，获取新激活码重新激活。</div>
<div class=q>Q: 软件闪退或报错？</div>
<div class=a>A: 确认杀毒软件没有拦截，加入白名单。</div>

<div style='color:#555;font-size:12px;text-align:center;margin-top:24px;'>微信：UU_L777777</div>"""

        from PySide6.QtWidgets import QTextBrowser
        view = QTextBrowser()
        view.setHtml(html)
        view.setStyleSheet("")
        view.setOpenExternalLinks(False)
        layout.addWidget(view, 1)

        btn = QPushButton("关闭")
        btn.setFixedWidth(100)
        btn.setStyleSheet("QPushButton { background:#333; color:#ccc; border:1px solid #444; border-radius:6px; padding:6px 20px; font-size:13px; } QPushButton:hover { background:#3a3a3a; border-color:#555; }")
        btn.clicked.connect(dlg.accept)
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        btn_row.addWidget(btn)
        btn_row.addStretch()
        layout.addLayout(btn_row)
        dlg.exec()

    def _auto_check_update(self):
        """启动时静默检查更新"""
        has_update, version, changelog, url = update_checker.check_for_update()
        if has_update:
            self._add_log(f"发现新版本 v{version}，点击「检查更新」升级", "warning")

    def _show_preview(self):
        # 优先显示最近一次处理的输出目录
        recent_dir = getattr(self, '_last_output_dir', None)
        if recent_dir and os.path.isdir(recent_dir):
            search_dir = recent_dir
            jpgs = sorted(glob.glob(os.path.join(search_dir, "*.jpg")))
        else:
            search_dir = self._save_path if self._save_path and os.path.isdir(self._save_path) else "."
            jpgs = sorted(glob.glob(os.path.join(search_dir, "*.jpg")) + glob.glob(os.path.join(search_dir, "Processed_*", "*.jpg")))
        save_dir = search_dir
        if not jpgs:
            QMessageBox.information(self, "预览", "暂无可预览的图片")
            return
        # 匹配原图：文件名去掉随机后缀
        import re
        pairs = []
        for p in jpgs:
            base = os.path.basename(p)
            # 匹配 {name}_d{score}_{rand6}.jpg 或 {name}_{rand6}.jpg
            m = re.match(r'(.+?)(?:_d\d+)?_[A-Za-z0-9]{6}\.jpg$', base)
            if m:
                orig_name = m.group(1) + '.jpg'
                # 变体文件去掉 _v2/_v3 后缀，匹配回原始文件名
                orig_name = re.sub(r'_v\d+(?=\.jpg$)', '', orig_name)
                # 在同目录、上级目录、保存目录、原始来源目录找原图
                search_dirs = [os.path.dirname(p), os.path.dirname(os.path.dirname(p)), save_dir]
                for sp in getattr(self, '_last_source_paths', []) or []:
                    sd = os.path.dirname(sp)
                    if sd not in search_dirs:
                        search_dirs.append(sd)
                for d in search_dirs:
                    orig_path = os.path.join(d, orig_name)
                    if os.path.exists(orig_path) and orig_path != p:
                        pairs.append((orig_path, p))
                        break
                else:
                    pairs.append((None, p))
            else:
                pairs.append((None, p))

        dlg = QDialog(self)
        dlg.setWindowTitle("预览对比")
        dlg.setMinimumSize(1060, 640)
        dlg.resize(1120, 700)
        dlg.setStyleSheet("QDialog { background: #1a1a1a; }")

        main_lo = QVBoxLayout(dlg)
        main_lo.setContentsMargins(16, 12, 16, 12)
        main_lo.setSpacing(10)

        # ---- 标题 ----
        title = QLabel(f"处理结果 · 共 {len(pairs)} 张")
        title.setStyleSheet("font-size: 15px; font-weight: 600; color: #e0e0e0;")
        main_lo.addWidget(title)

        # ---- 主体：左侧缩略图卡片 + 右侧对比 ----
        body = QHBoxLayout()
        body.setSpacing(14)

        # 左侧缩略图卡片列表
        left_panel = QVBoxLayout()
        left_panel.setSpacing(0)
        left_label = QLabel("缩略图")
        left_label.setStyleSheet("font-size: 11px; color: #777; padding: 0 0 4px 4px;")
        left_panel.addWidget(left_label)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFixedWidth(150)
        scroll.setStyleSheet("QScrollArea { background: #1a1a1a; border: none; } QScrollBar:vertical { background: #1a1a1a; width: 5px; } QScrollBar::handle:vertical { background: #444; border-radius: 2px; min-height: 20px; } QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }")
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        thumb_container = QWidget()
        thumb_container.setStyleSheet("background: #1a1a1a;")
        thumb_lo = QVBoxLayout(thumb_container)
        thumb_lo.setContentsMargins(0, 0, 4, 0)
        thumb_lo.setSpacing(6)

        # 提取差异度
        def _extract_score(path):
            m = re.search(r'_d(\d+)_', os.path.basename(path))
            return int(m.group(1)) if m else None

        card_widgets = []
        for i, (o, p) in enumerate(pairs):
            card = QFrame()
            card.setFixedSize(130, 106)
            card.setCursor(Qt.PointingHandCursor)
            card.setStyleSheet("QFrame { background: #222; border: 2px solid #2a2a2a; border-radius: 8px; } QFrame:hover { background: #2a2a2a; }")
            card_lo = QVBoxLayout(card)
            card_lo.setContentsMargins(4, 4, 4, 4)
            card_lo.setSpacing(2)
            # 缩略图
            thumb_lbl = QLabel()
            thumb_lbl.setFixedSize(118, 72)
            thumb_lbl.setAlignment(Qt.AlignCenter)
            thumb_lbl.setStyleSheet("background: #1a1a1a; border-radius: 4px; border: none;")
            pix_path = p if os.path.exists(p) else (o if o and os.path.exists(o) else None)
            if pix_path:
                pix = QPixmap(pix_path).scaled(118, 72, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                thumb_lbl.setPixmap(pix)
            else:
                thumb_lbl.setText("—")
                thumb_lbl.setStyleSheet("background: #1a1a1a; border-radius: 4px; border: none; color: #555; font-size: 11px;")
            card_lo.addWidget(thumb_lbl)
            # 差异度 + 文件名
            score = _extract_score(p) if p else None
            info_lbl = QLabel()
            if score is not None:
                info_text = f"<span style='color:#10b981;font-weight:600;'>差异 {score}</span>"
            else:
                info_text = f"<span style='color:#555;'>无分值</span>"
            name = os.path.basename(p)[:20] if p else "—"
            info_text += f"<br><span style='color:#888;font-size:9px;'>{name}</span>"
            info_lbl.setText(info_text)
            info_lbl.setStyleSheet("font-size: 10px; color: #aaa; padding: 0 2px; border: none;")
            card_lo.addWidget(info_lbl)
            thumb_lo.addWidget(card)
            card_widgets.append(card)

        thumb_lo.addStretch()
        scroll.setWidget(thumb_container)
        left_panel.addWidget(scroll)
        body.addLayout(left_panel)

        # 右侧对比区域
        right_panel = QVBoxLayout()
        right_panel.setSpacing(8)

        # 对比图区 — QLabel 直接嵌入，缩放时只渲染可见区域
        cmp = QHBoxLayout()
        cmp.setSpacing(0)

        BASE_SIZE = 360
        zoom_level = [1.0]
        ZOOM_MIN, ZOOM_MAX, ZOOM_STEP = 1.0, 8.0, 0.25
        pan_x = [0]   # 共享平移偏移（放大后在完整图片坐标系中）
        pan_y = [0]

        def _make_image_label():
            lbl = QLabel()
            lbl.setMinimumSize(300, 300)
            lbl.setAlignment(Qt.AlignCenter)
            lbl.setStyleSheet("background: #111; border-radius: 10px; border: 1px solid #2a2a2a;")
            return lbl

        orig_label = _make_image_label()
        cmp.addWidget(orig_label, 1)

        # 中间箭头 + 缩放指示
        mid_col = QVBoxLayout()
        mid_col.addStretch()
        arrow = QLabel("→")
        arrow.setStyleSheet("font-size: 22px; color: #10b981; font-weight: 700;")
        arrow.setAlignment(Qt.AlignCenter)
        arrow.setFixedWidth(40)
        mid_col.addWidget(arrow)
        zoom_label = QLabel("1.0×")
        zoom_label.setAlignment(Qt.AlignCenter)
        zoom_label.setStyleSheet("font-size: 11px; color: #10b981; font-weight: 600; padding: 2px 0;")
        mid_col.addWidget(zoom_label)
        mid_col.addStretch()
        cmp.addLayout(mid_col)

        proc_label = _make_image_label()
        cmp.addWidget(proc_label, 1)

        right_panel.addLayout(cmp)

        # 差异度徽章
        diff_badge = QLabel("")
        diff_badge.setAlignment(Qt.AlignCenter)
        diff_badge.setStyleSheet("font-size: 20px; font-weight: 700; color: #10b981; padding: 2px 0;")
        diff_badge.hide()
        right_panel.addWidget(diff_badge)
        # 隐藏的占位
        diff_spacer = QLabel("")
        diff_spacer.setFixedHeight(28)
        right_panel.addWidget(diff_spacer)

        # 文件信息栏
        info_bar = QHBoxLayout()
        orig_info = QLabel("")
        orig_info.setStyleSheet("font-size: 10px; color: #777;")
        info_bar.addWidget(orig_info)
        info_bar.addStretch()
        proc_info = QLabel("")
        proc_info.setStyleSheet("font-size: 10px; color: #777;")
        info_bar.addWidget(proc_info)
        right_panel.addLayout(info_bar)

        body.addLayout(right_panel, 1)
        main_lo.addLayout(body)

        # ---- 导航栏 ----
        nav = QHBoxLayout()
        nav.addStretch()
        btn_prev = QPushButton("◀")
        btn_prev.setFixedSize(36, 30)
        page_label = QLabel("0 / 0")
        page_label.setStyleSheet("font-size: 12px; color: #aaa;")
        page_label.setAlignment(Qt.AlignCenter)
        page_label.setFixedWidth(60)
        btn_next = QPushButton("▶")
        btn_next.setFixedSize(36, 30)
        for b in [btn_prev, btn_next]:
            b.setStyleSheet("QPushButton { background: #2a2a2a; color: #aaa; border: 1px solid #333; border-radius: 4px; font-size: 12px; } QPushButton:hover { background: #3a3a3a; color: #fff; border-color: #555; }")
        nav.addWidget(btn_prev)
        nav.addWidget(page_label)
        nav.addWidget(btn_next)
        nav.addStretch()
        main_lo.addLayout(nav)

        # ---- 底部按钮 ----
        bottom = QHBoxLayout()
        btn_browse = QPushButton("浏览文件夹")
        btn_browse.setStyleSheet("QPushButton { background: #2a2a2a; color: #ccc; border: 1px solid #333; border-radius: 5px; padding: 6px 14px; font-size: 12px; } QPushButton:hover { background: #3a3a3a; color: #fff; }")
        btn_browse.clicked.connect(lambda: (dlg.accept(), self._open_save_dir()))
        bottom.addWidget(btn_browse)
        bottom.addStretch()
        btn_close = QPushButton("关闭")
        btn_close.setStyleSheet("QPushButton { background: #2a2a2a; color: #ccc; border: 1px solid #333; border-radius: 5px; padding: 6px 16px; font-size: 12px; } QPushButton:hover { background: #3a3a3a; color: #fff; }")
        btn_close.clicked.connect(dlg.close)
        bottom.addWidget(btn_close)
        main_lo.addLayout(bottom)

        # ---- 逻辑函数 ----
        def _show_full(path):
            if not path or not os.path.exists(path):
                return
            pix = QPixmap(path)
            if pix.isNull():
                return
            fd = QDialog(dlg)
            fd.setWindowTitle(os.path.basename(path))
            fd.setStyleSheet("background: #0d0d0d;")
            fl = QVBoxLayout(fd)
            fl.setContentsMargins(0, 0, 0, 0)
            screen = QApplication.primaryScreen().availableGeometry()
            max_w = int(screen.width() * 0.85)
            max_h = int(screen.height() * 0.85)
            fl2 = QLabel()
            fl2.setPixmap(pix.scaled(max_w, max_h, Qt.KeepAspectRatio, Qt.SmoothTransformation))
            fl2.setAlignment(Qt.AlignCenter)
            fl.addWidget(fl2)
            fd.exec()

        current_idx = [0]
        _orig_pixmap = [None]
        _proc_pixmap = [None]

        def _render_visible(label, full_pm):
            """取 full_pm 中当前 pan+zoom 对应的可见区域渲染到 label"""
            if not full_pm or full_pm.isNull():
                return
            lw, lh = label.width(), label.height()
            if lw <= 0 or lh <= 0:
                lw, lh = BASE_SIZE, BASE_SIZE
            z = zoom_level[0]
            # 完整缩放后的图
            pw = max(1, int(lw * z))
            ph = max(1, int(lh * z))
            full = full_pm.scaled(pw, ph, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            # 计算可见区域
            ox = pan_x[0]
            oy = pan_y[0]
            # clamp offset
            ox = max(0, min(ox, max(0, full.width() - lw)))
            oy = max(0, min(oy, max(0, full.height() - lh)))
            pan_x[0], pan_y[0] = ox, oy
            # 如果缩放图小于视口，居中
            if full.width() <= lw:
                ox = 0
            if full.height() <= lh:
                oy = 0
            copy_w = min(lw, full.width() - ox)
            copy_h = min(lh, full.height() - oy)
            if copy_w > 0 and copy_h > 0:
                visible = full.copy(ox, oy, copy_w, copy_h)
                # 画到纯黑底上以处理不满视口的情况
                canvas = QPixmap(lw, lh)
                canvas.fill(Qt.black)
                painter = QPainter(canvas)
                painter.drawPixmap((lw - copy_w) // 2, (lh - copy_h) // 2, visible)
                painter.end()
                label.setPixmap(canvas)
            else:
                label.clear()

        def _apply_zoom():
            _render_visible(orig_label, _orig_pixmap[0])
            _render_visible(proc_label, _proc_pixmap[0])
            z = zoom_level[0]
            zoom_label.setText(f"{z:.1f}×")
            if z > 2.0:
                zoom_label.setStyleSheet("font-size: 11px; color: #f59e0b; font-weight: 600; padding: 2px 0;")
            else:
                zoom_label.setStyleSheet("font-size: 11px; color: #10b981; font-weight: 600; padding: 2px 0;")

        def _pan_both(dx, dy):
            z = zoom_level[0]
            if z <= 1.0:
                return
            # 拖拽方向：鼠标下移 → 图片下移（看到上方内容）
            pan_x[0] -= int(dx * z)
            pan_y[0] -= int(dy * z)
            _apply_zoom()

        def _zoom_wheel(event):
            delta = event.angleDelta().y()
            if delta > 0:
                zoom_level[0] = min(ZOOM_MAX, zoom_level[0] + ZOOM_STEP)
            elif delta < 0:
                zoom_level[0] = max(ZOOM_MIN, zoom_level[0] - ZOOM_STEP)
            _apply_zoom()

        def _zoom_reset():
            zoom_level[0] = 1.0
            pan_x[0] = pan_y[0] = 0
            _apply_zoom()

        def _install_interaction(label, side):
            drag_start = [None]
            drag_triggered = [False]

            def press(event):
                if event.button() == Qt.LeftButton:
                    drag_start[0] = event.globalPos()
                    drag_triggered[0] = False
                elif event.button() == Qt.RightButton:
                    _zoom_reset()

            def move_handler(event):
                if drag_start[0] is not None:
                    delta = event.globalPos() - drag_start[0]
                    if abs(delta.x()) > 4 or abs(delta.y()) > 4:
                        drag_triggered[0] = True
                        _pan_both(delta.x(), delta.y())
                        drag_start[0] = event.globalPos()

            def release(event):
                if event.button() == Qt.LeftButton:
                    if not drag_triggered[0] and drag_start[0] is not None:
                        path = (_orig_paths[current_idx[0]] if side == 0
                                else _proc_paths[current_idx[0]])
                        if path:
                            _show_full(path)
                    drag_start[0] = None
                    drag_triggered[0] = False

            label.mousePressEvent = press
            label.mouseMoveEvent = move_handler
            label.mouseReleaseEvent = release
            label.wheelEvent = _zoom_wheel

        _orig_paths = [None] * len(pairs)
        _proc_paths = [None] * len(pairs)

        _install_interaction(orig_label, 0)
        _install_interaction(proc_label, 1)

        def show_pair(idx):
            if idx < 0 or idx >= len(pairs):
                return
            current_idx[0] = idx
            o, p = pairs[idx]

            # 切换图片时重置缩放和平移
            zoom_level[0] = 1.0
            pan_x[0] = pan_y[0] = 0

            # 差异度徽章
            score = _extract_score(p) if p else None
            if score is not None:
                diff_badge.setText(f"差异度 {score}")
                diff_badge.show()
                diff_spacer.hide()
            else:
                diff_badge.hide()
                diff_spacer.show()

            # 处理图
            _proc_pixmap[0] = QPixmap(p) if p and os.path.exists(p) else QPixmap()
            _proc_paths[idx] = p if p and os.path.exists(p) else None
            _default_style = "background: #111; border-radius: 10px; border: 1px solid #2a2a2a;"
            if not _proc_pixmap[0].isNull():
                proc_label.setText("")
                proc_label.setStyleSheet(_default_style)
                sz = os.path.getsize(p) / 1024
                dims = f"{_proc_pixmap[0].width()}×{_proc_pixmap[0].height()}"
                proc_info.setText(f"{os.path.basename(p)}  ·  {dims}  ·  {sz:.0f}KB")
            else:
                _proc_pixmap[0] = None
                _proc_paths[idx] = None
                proc_label.setText("加载失败")
                proc_label.setStyleSheet("background: #111; border-radius: 10px; border: 1px solid #2a2a2a; color: #555; font-size: 16px;")
                proc_info.setText("")

            # 原图
            if o and os.path.exists(o):
                _orig_pixmap[0] = QPixmap(o)
                _orig_paths[idx] = o
                if not _orig_pixmap[0].isNull():
                    orig_label.setText("")
                    orig_label.setStyleSheet(_default_style)
                    sz = os.path.getsize(o) / 1024
                    dims = f"{_orig_pixmap[0].width()}×{_orig_pixmap[0].height()}"
                    orig_info.setText(f"{os.path.basename(o)}  ·  {dims}  ·  {sz:.0f}KB")
                else:
                    _orig_pixmap[0] = None
                    _orig_paths[idx] = None
                    orig_label.setText("加载失败")
                    orig_label.setStyleSheet("background: #111; border-radius: 10px; border: 1px solid #2a2a2a; color: #555; font-size: 16px;")
                    orig_info.setText("")
            else:
                _orig_pixmap[0] = None
                _orig_paths[idx] = None
                orig_label.setText("原图无缓存")
                orig_label.setStyleSheet("background: #111; border-radius: 10px; border: 1px solid #2a2a2a; color: #555; font-size: 16px;")
                orig_info.setText("")

            _apply_zoom()

            page_label.setText(f"{idx + 1} / {len(pairs)}")

            # 缩略图卡片高亮
            for i, card in enumerate(card_widgets):
                if i == idx:
                    card.setStyleSheet("QFrame { background: #2a382a; border: 2px solid #10b981; border-radius: 8px; } QFrame:hover { background: #2d3f2d; }")
                else:
                    card.setStyleSheet("QFrame { background: #222; border: 2px solid #2a2a2a; border-radius: 8px; } QFrame:hover { background: #2a2a2a; }")

        def navigate(delta):
            new_idx = current_idx[0] + delta
            if 0 <= new_idx < len(pairs):
                show_pair(new_idx)

        btn_prev.clicked.connect(lambda: navigate(-1))
        btn_next.clicked.connect(lambda: navigate(1))

        # 缩略图卡片点击事件
        for i, card in enumerate(card_widgets):
            card.mousePressEvent = (lambda e, idx=i: show_pair(idx))

        # 键盘导航
        def key_handler(event):
            if event.key() == Qt.Key_Left:
                navigate(-1)
            elif event.key() == Qt.Key_Right:
                navigate(1)
            elif event.key() == Qt.Key_Escape:
                dlg.close()
            else:
                QDialog.keyPressEvent(dlg, event)
        dlg.keyPressEvent = key_handler

        # 初始显示 — 延迟等布局完成再渲染
        if pairs:
            show_pair(0)
            QTimer.singleShot(50, _apply_zoom)

        # 窗口大小变化时重渲染
        def _on_resize(event):
            QDialog.resizeEvent(dlg, event)
            if pairs:
                QTimer.singleShot(0, _apply_zoom)
        dlg.resizeEvent = _on_resize

        dlg.exec()

    def _check_for_updates(self):
        self._add_log("正在检查更新...", "info")
        has_update, version, changelog, url = update_checker.check_for_update()
        if not has_update:
            self._add_log(f"已是最新版本（v{update_checker.CURRENT_VERSION}）", "success")
            QMessageBox.information(self, "检查更新", f"已是最新版本 v{update_checker.CURRENT_VERSION}")
            return
        reply = QMessageBox.question(
            self, "发现新版本",
            f"发现新版本 v{version}\n\n更新内容：\n{changelog}\n\n是否立即更新？",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply != QMessageBox.Yes:
            return
        self._add_log(f"正在下载 v{version}...", "info")
        wait_dlg = QMessageBox(self)
        wait_dlg.setWindowTitle("版本更新")
        wait_dlg.setText("正在下载更新，请稍候...")
        wait_dlg.setInformativeText("更新过程中请勿关闭程序或断开网络，\n下载完成后将自动重启软件。")
        wait_dlg.setStandardButtons(QMessageBox.NoButton)
        wait_dlg.setWindowModality(Qt.WindowModal)
        wait_dlg.show()
        QApplication.processEvents()
        # 延迟 200ms 启动下载，确保对话框完全渲染
        def _do_download():
            exe = update_checker.download_update(url,
                lambda d, t: wait_dlg.setInformativeText(f"正在下载 {d//1024//1024}/{t//1024//1024}MB\n\n更新过程中请勿关闭程序或断开网络，\n下载完成后将自动重启软件。"))
            wait_dlg.close()
            if not exe:
                self._add_log("更新下载失败", "error")
                QMessageBox.critical(self, "更新失败", "下载失败，请稍后重试。")
                return
            self._add_log("正在应用更新...", "info")
            update_checker.apply_update(exe)
        QTimer.singleShot(200, _do_download)

    # ---- 窗口级拖拽（图片文件/文件夹） ----
    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            for url in event.mimeData().urls():
                p = url.toLocalFile()
                if os.path.isdir(p) or p.lower().endswith(('.jpg', '.jpeg', '.png', '.webp', '.bmp')):
                    event.acceptProposedAction()
                    return
        event.ignore()

    def dropEvent(self, event):
        paths = []
        for url in event.mimeData().urls():
            p = url.toLocalFile()
            if os.path.isdir(p):
                for ext in ('.jpg', '.jpeg', '.png', '.webp', '.bmp'):
                    paths.extend(glob.glob(os.path.join(p, '*'+ext)))
                    paths.extend(glob.glob(os.path.join(p, '*'+ext.upper())))
            elif p.lower().endswith(('.jpg', '.jpeg', '.png', '.webp', '.bmp')):
                paths.append(p)
        if paths:
            event.acceptProposedAction()
            self._run_local_worker(paths)

    # ---- 目录 ----
    def _open_save_dir(self):
        ok, err = backend.open_save_dir(self._save_path)
        if not ok:
            QMessageBox.warning(self, "警告", err)

    # ---- 关闭 ----
    def closeEvent(self, event):
        if self._worker and self._worker.isRunning():
            reply = QMessageBox.question(self, "退出", "任务正在运行中，确定退出？")
            if reply == QMessageBox.Yes:
                backend.STOP_TASK = True
                self._worker.quit()
                self._worker.wait(3000)
                self._save_geometry()
                event.accept()
            else:
                event.ignore()
        else:
            self._save_geometry()
            event.accept()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Return and event.modifiers() == Qt.ControlModifier:
            if self.btn_start.isEnabled():
                self._start_crawl()
        elif event.key() == Qt.Key_Escape:
            if self.btn_stop.isEnabled():
                self._stop_crawl()
        else:
            super().keyPressEvent(event)

    def _save_geometry(self):
        r = self.geometry()
        cfg = backend.load_config()
        cfg["window_geometry"] = f"{r.width()}x{r.height()}+{r.x()}+{r.y()}"
        cfg["last_urls"] = self.txt_urls.toPlainText()
        backend.save_config(cfg)


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("ImageMAX")
    # 任务栏图标
    icon_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "app_icon.ico")
    if not os.path.exists(icon_path):
        frozen = getattr(sys, '_MEIPASS', None)
        if frozen:
            icon_path = os.path.join(frozen, "app_icon.ico")
    if os.path.exists(icon_path):
        app.setWindowIcon(QIcon(icon_path))

    # 反调试检测
    if license_mgr.is_debugger_present():
        QMessageBox.critical(None, "安全警告", "检测到调试或逆向工具，软件无法启动。")
        sys.exit(1)

    # License 验证
    valid, msg, remaining = license_mgr.check_license()
    if not valid:
        dlg = ActivationDialog()
        if dlg.exec() != QDialog.Accepted or not dlg.is_activated():
            sys.exit(0)
        valid, msg, remaining = license_mgr.check_license()
        if not valid:
            QMessageBox.critical(None, "激活失败", f"激活验证失败：{msg}")
            sys.exit(1)

    # 启动后台定时校验
    license_mgr.start_background_check(900)

    window = VintedScraperGUI()
    # 在主窗口设置定时器显示授权状态（后台检测到篡改时关闭）
    tamper_timer = QTimer(window)
    tamper_timer.timeout.connect(lambda: _check_tamper(window))
    tamper_timer.start(60000)  # 每分钟检查一次
    window.show()
    if not window._help_shown:
        QTimer.singleShot(500, lambda: _welcome_guide(window))
        window._help_shown = True
        window._save_config()
    sys.exit(app.exec())

def _welcome_guide(window):
    QMessageBox.information(window, "欢迎",
        "欢迎使用图像重构MAX！\n\n"
        "使用前建议先查看完整教程，\n"
        "点击右上角「使用说明」即可。")
    # 按钮闪烁引导
    btn = window.btn_help
    original = btn.styleSheet()
    for i in range(4):
        color = "#10b981" if i % 2 == 0 else "#b0b0b0"
        QTimer.singleShot(i * 600 + 100, lambda c=color, b=btn: b.setStyleSheet(
            f"QPushButton {{ font-size: 11px; color: {c}; border: 1px solid {c}; "
            f"border-radius: 4px; padding: 2px 8px; background: transparent; }}"))
    QTimer.singleShot(2600, lambda: btn.setStyleSheet(original))


def _check_tamper(window):
    """检查运行时是否检测到篡改"""
    if license_mgr.is_tampered():
        QMessageBox.critical(window, "授权到期", "授权有效期已过，软件需要重启。\n请联系管理员续期。")
        sys.exit(1)


if __name__ == "__main__":
    main()
