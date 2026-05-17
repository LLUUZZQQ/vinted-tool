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
    QMessageBox, QDialog, QFrame,
)
from PySide6.QtCore import Qt, Signal, QThread, QTimer, QMimeData
from PySide6.QtGui import QFont
import Vinted_抓图 as backend
import license_system as license_mgr
import update_checker


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
            if be.process_image(p, skip_gps=True):
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
        self.setWindowTitle("Vinted Tool — 软件激活")
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
        brand = QLabel("Vinted")
        brand.setAlignment(Qt.AlignCenter)
        brand.setStyleSheet("font-size: 20px; font-weight: 700; color: #111111;")
        root.addWidget(brand)
        sub = QLabel("软件激活")
        sub.setAlignment(Qt.AlignCenter)
        sub.setStyleSheet("font-size: 12px; color: #9ca3af;")
        root.addWidget(sub)
        root.addSpacing(16)

        # ---- 步骤 1 ----
        s1h = QHBoxLayout(); s1h.setSpacing(6)
        s1h.addWidget(self._step_badge("1"))
        s1h.addWidget(self._section_title("设备标识"))
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

        root.addWidget(self._hint("请将以上标识发送给卖家获取激活码"))
        root.addSpacing(12)

        # ---- 步骤 2 ----
        s2h = QHBoxLayout(); s2h.setSpacing(6)
        s2h.addWidget(self._step_badge("2"))
        s2h.addWidget(self._section_title("激活码"))
        s2h.addStretch()
        root.addLayout(s2h)
        root.addSpacing(4)

        c2 = self._make_card()
        c2l = QVBoxLayout(c2); c2l.setContentsMargins(8, 2, 8, 2)
        self.code_input = QLineEdit()
        self.code_input.setPlaceholderText("粘贴激活码到此处")
        self.code_input.setStyleSheet("""
            QLineEdit { border: none; background: transparent; font-family: Consolas;
            font-size: 13px; color: #111111; padding: 4px 0; }
        """)
        c2l.addWidget(self.code_input)
        root.addWidget(c2)

        root.addWidget(self._hint("激活码由卖家提供，一机一码"))
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
        self.btn_activate = QPushButton("激活软件")
        self.btn_activate.setStyleSheet("""
            QPushButton { font-size: 13px; font-weight: 600; background: #111111;
            border: none; border-radius: 6px; padding: 8px 28px; color: #ffffff; }
            QPushButton:hover { background: #2d2d2d; }
            QPushButton:disabled { background: #b0b0b0; }
        """)
        self.btn_activate.setCursor(Qt.PointingHandCursor)
        self.btn_activate.clicked.connect(self._do_activate)
        bh.addWidget(self.btn_activate)
        self.btn_exit = QPushButton("退出")
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
        contact = QLabel("需要激活码？请联系 微信：UU_L777777")
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
        self.msg_label.setText("已复制，请发送给卖家")

    def _do_activate(self):
        code = self.code_input.text().strip()
        if not code:
            self.msg_label.setStyleSheet("font-size: 12px; color: #ef4444;")
            self.msg_label.setText("请先粘贴激活码")
            return
        self.btn_activate.setEnabled(False)
        self.btn_activate.setText("验证中...")
        self.msg_label.setStyleSheet("font-size: 12px; color: #6b7280;")
        self.msg_label.setText("正在验证激活码...")
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
class VintedScraperGUI(QMainWindow):
    def __init__(self):
        super().__init__()
        self._worker = None
        self._local_worker = None
        self._geo_setting_up = False

        self.setWindowTitle(f"Vinted 商品图片抓取工具 v{update_checker.CURRENT_VERSION}")
        self.setMinimumSize(440, 600)
        self.resize(500, 650)

        screen = QApplication.primaryScreen().geometry()
        self.move((screen.width() - 500) // 2, (screen.height() - 650) // 2)

        self._load_config()
        self._build_ui()
        self._apply_config_to_ui()
        self._load_stylesheet()
        self._connect_signals()

        # 显示授权到期信息
        _, _, remaining = license_mgr.check_license()
        if remaining is not None:
            self.license_label.setText(f"授权剩余 {remaining} 天")
        else:
            self.license_label.setText("永久授权")

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

        backend.CUSTOM_SAVE_ROOT = self._save_path
        backend.COMPRESS_ENABLED = self._compress
        backend.WATERMARK_ENABLED = self._watermark
        backend.LOSSLESS_ENABLED = self._lossless
        backend.ADVANCED_ANTI_DETECT_ENABLED = self._advanced_anti_detect
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
        self._build_log_section(root)

    # ---- 模块 1：商品链接管理 ----
    def _build_url_section(self, parent):
        g = QGroupBox("商品链接管理")
        lo = QVBoxLayout(g)
        lo.setContentsMargins(0, 8, 0, 4)
        lo.setSpacing(4)

        top = QHBoxLayout()
        top.addWidget(QLabel("商品链接（一行一个）："))
        top.addStretch()
        self.btn_update = QPushButton("检查更新")
        self.btn_update.setFlat(True)
        self.btn_update.setCursor(Qt.PointingHandCursor)
        self.btn_update.setStyleSheet("QPushButton { font-size: 11px; color: #b0b0b0; border: none; background: transparent; } QPushButton:hover { color: #111111; }")
        self.btn_update.clicked.connect(self._check_for_updates)
        top.addWidget(self.btn_update)
        self.url_count_label = QLabel("有效链接：0")
        self.url_count_label.setObjectName("urlCountLabel")
        top.addWidget(self.url_count_label)
        lo.addLayout(top)

        self.txt_urls = DropPlainTextEdit()
        self.txt_urls.setPlaceholderText("粘贴 Vinted 商品链接，一行一个...（也可拖拽 .txt 文件）")
        self.txt_urls.setMaximumHeight(68)
        lo.addWidget(self.txt_urls)

        btn = QHBoxLayout()
        btn.setSpacing(6)
        self.btn_clear_urls = QPushButton("一键清空")
        self.btn_clear_urls.setObjectName("btnSecondary")
        btn.addWidget(self.btn_clear_urls)
        self.btn_import_urls = QPushButton("批量导入")
        self.btn_import_urls.setObjectName("btnSecondary")
        btn.addWidget(self.btn_import_urls)
        self.btn_dedup_urls = QPushButton("链接去重")
        self.btn_dedup_urls.setObjectName("btnSecondary")
        btn.addWidget(self.btn_dedup_urls)
        btn.addStretch()
        self.btn_export_fail = QPushButton("导出失败链接")
        self.btn_export_fail.setObjectName("btnSecondary")
        btn.addWidget(self.btn_export_fail)
        lo.addLayout(btn)

        parent.addWidget(g)

    # ---- 模块 2：基础参数设置 ----
    def _build_settings_section(self, parent):
        g = QGroupBox("基础参数设置")
        lo = QVBoxLayout(g)
        lo.setContentsMargins(0, 8, 0, 4)
        lo.setSpacing(6)

        # 行 1：保存路径
        r1 = QHBoxLayout()
        r1.setSpacing(6)
        r1.addWidget(QLabel("保存路径：", fixedWidth=60))
        self.entry_path = QLineEdit()
        self.entry_path.setPlaceholderText(backend.DEFAULT_SAVE_ROOT)
        r1.addWidget(self.entry_path, 1)
        self.btn_browse = QPushButton("浏览")
        self.btn_browse.setObjectName("btnBrowse")
        r1.addWidget(self.btn_browse)
        lo.addLayout(r1)

        # 行 2：拍摄地理
        r2 = QHBoxLayout()
        r2.setSpacing(6)
        r2.addWidget(QLabel("拍摄地理：", fixedWidth=60))
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

        # 行 3：复选框 + 恢复按钮
        r3 = QHBoxLayout()
        r3.setSpacing(12)
        self.chk_compress = QCheckBox("智能压缩")
        self.chk_compress.setToolTip("智能压缩图片，肉眼无感知")
        r3.addWidget(self.chk_compress)
        self.chk_watermark = QCheckBox("隐形水印")
        self.chk_watermark.setToolTip("添加隐形防重水印")
        r3.addWidget(self.chk_watermark)
        r3.addStretch()
        self.btn_reset = QPushButton("恢复默认")
        self.btn_reset.setObjectName("btnSecondary")
        r3.addWidget(self.btn_reset)
        lo.addLayout(r3)

        # 行 3b：高级复选框
        r3b = QHBoxLayout()
        r3b.setSpacing(12)
        self.chk_lossless = QCheckBox("无损画质")
        self.chk_lossless.setToolTip("quality=100，防重效果减弱")
        r3b.addWidget(self.chk_lossless)
        self.chk_advanced_anti_detect = QCheckBox("高级防检测")
        self.chk_advanced_anti_detect.setToolTip("JPEG块破坏+传感器噪声模拟+空间亮度渐变+EXIF增强")
        r3b.addWidget(self.chk_advanced_anti_detect)
        r3b.addStretch()
        lo.addLayout(r3b)

        parent.addWidget(g)

    # ---- 模块 3：任务操作 ----
    def _build_task_section(self, parent):
        g = QGroupBox("任务操作")
        lo = QVBoxLayout(g)
        lo.setContentsMargins(0, 8, 0, 4)
        lo.setSpacing(6)

        # 状态 + 统计
        bar = QHBoxLayout()
        self.status_label = QLabel("状态：空闲中")
        self.status_label.setObjectName("statusLabel")
        bar.addWidget(self.status_label)
        bar.addStretch()
        self.license_label = QLabel("")
        self.license_label.setObjectName("licenseLabel")
        bar.addWidget(self.license_label)
        bar.addSpacing(12)
        self.stat_label = QLabel("成功：0 | 失败：0")
        self.stat_label.setObjectName("statLabel")
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
        btn.setSpacing(8)
        self.btn_start = QPushButton("开始抓取")
        self.btn_start.setObjectName("btnStart")
        btn.addWidget(self.btn_start)
        self.btn_stop = QPushButton("停止任务")
        self.btn_stop.setObjectName("btnStop")
        self.btn_stop.setEnabled(False)
        btn.addWidget(self.btn_stop)
        btn.addStretch()
        self.btn_open_dir = QPushButton("打开目录")
        self.btn_open_dir.setObjectName("btnSecondary")
        btn.addWidget(self.btn_open_dir)
        self.btn_local = QPushButton("本地防重 ▾")
        self.btn_local.setObjectName("btnSecondary")
        btn.addWidget(self.btn_local)
        lo.addLayout(btn)

        parent.addWidget(g)

    # ---- 模块 4：运行日志 ----
    def _build_log_section(self, parent):
        g = QGroupBox("运行日志")
        lo = QVBoxLayout(g)
        lo.setContentsMargins(0, 8, 0, 2)
        lo.setSpacing(4)

        tb = QHBoxLayout()
        tb.addStretch()
        self.btn_clear_log = QPushButton("清空日志")
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
        self._geo_setting_up = False
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
        self.btn_reset.clicked.connect(self._reset_defaults)
        self.btn_start.clicked.connect(self._start_crawl)
        self.btn_stop.clicked.connect(self._stop_crawl)
        self.btn_open_dir.clicked.connect(self._open_save_dir)
        self.btn_clear_log.clicked.connect(self._clear_log)
        self.btn_local.clicked.connect(self._show_local_menu)

        # 窗口级拖拽：图片文件拖入触发本地防重
        self.setAcceptDrops(True)

    # ---- URL 管理 ----
    def _update_url_count(self):
        text = self.txt_urls.toPlainText()
        urls = [u.strip() for u in text.split("\n") if u.strip() and "vinted." in u]
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
        self._save_config()

    def _on_watermark_toggled(self, v):
        self._watermark = v
        backend.WATERMARK_ENABLED = v
        self._save_config()

    def _on_lossless_toggled(self, v):
        self._lossless = v
        backend.LOSSLESS_ENABLED = v
        self._save_config()

    def _on_advanced_anti_detect_toggled(self, v):
        self._advanced_anti_detect = v
        backend.ADVANCED_ANTI_DETECT_ENABLED = v
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
        save_path = self.entry_path.text().strip() or backend.DEFAULT_SAVE_ROOT
        if not os.path.exists(save_path):
            if QMessageBox.Yes != QMessageBox.question(self, "提示", f"目录不存在，是否创建？\n{save_path}"):
                return
            os.makedirs(save_path)
        backend.CUSTOM_SAVE_ROOT = save_path
        self._save_path = save_path
        self._save_config()

        self._set_ui_running(True)
        self.status_label.setText("状态：正在启动任务")

        self._worker = CrawlWorker(text, False)
        self._worker.log_signal.connect(self._add_log)
        self._worker.status_signal.connect(lambda s: self.status_label.setText(f"状态：{s}"))
        self._worker.progress_signal.connect(self._on_progress)
        self._worker.finished_signal.connect(self._on_task_finished)
        self._worker.start()

    def _stop_crawl(self):
        backend.STOP_TASK = True
        self.status_label.setText("状态：正在停止任务")
        self.btn_stop.setEnabled(False)
        self._add_log("⚠️ 正在停止任务，请稍候...", "warning")

    def _on_progress(self, current, total, success, fail):
        if total > 0:
            self.progress_bar.setMaximum(total)
            self.progress_bar.setValue(current)
        self.stat_label.setText(f"成功：{success} | 失败：{fail}")

    def _on_task_finished(self, stopped):
        self._set_ui_running(False)
        self._worker = None
        self.status_label.setText("状态：已停止" if stopped else "状态：已完成")

        total, success, fail = backend.TOTAL_TASKS, backend.SUCCESS_COUNT, backend.FAIL_COUNT
        msg = QMessageBox(self)
        msg.setWindowTitle("任务完成")
        msg.setIcon(QMessageBox.Information)
        msg.setStandardButtons(QMessageBox.Ok)
        msg.setDefaultButton(QMessageBox.Ok)
        msg.setText(f"任务执行完成！")
        msg.setInformativeText(f"总商品数：{total}    成功：{success}    失败：{fail}")
        btn_open = msg.addButton("打开图片目录", QMessageBox.ActionRole)
        btn_clear = msg.addButton("重新开始", QMessageBox.ActionRole)
        btn_export = None
        if backend.FAILED_URLS:
            btn_export = msg.addButton("导出失败链接", QMessageBox.ActionRole)
        msg.exec()
        clicked = msg.clickedButton()
        if clicked == btn_open:
            self._open_save_dir()
        elif clicked == btn_clear:
            self._clear_urls()
        elif btn_export and clicked == btn_export:
            self._export_failed_urls()

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
        self.btn_local.setEnabled(not running)
        if not running:
            backend.STOP_TASK = False
            self.progress_bar.setMaximum(100)
            self.progress_bar.setValue(0)

    # ---- 日志 ----
    def _add_log(self, content, level="info"):
        colors = {"success": "#10b981", "warning": "#f59e0b", "error": "#ef4444", "info": "#374151"}
        c = colors.get(level, "#374151")
        self.log_view.appendHtml(f'<span style="color:{c};white-space:pre;">{content.replace("&","&amp;").replace("<","&lt;").replace(">","&gt;")}</span>')
        self.log_view.verticalScrollBar().setValue(self.log_view.verticalScrollBar().maximum())

    def _clear_log(self):
        self.log_view.clear()

    def _show_log_menu(self, pos):
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
        self._add_log(f"🖼️ 开始本地防重处理，共 {len(paths)} 张图片", "info")
        self._local_worker = LocalProcessWorker(paths)
        self._local_worker.log_signal.connect(self._add_log)
        self._local_worker.progress_signal.connect(
            lambda c, t: (self.progress_bar.setMaximum(t), self.progress_bar.setValue(c))
        )
        self._local_worker.finished_signal.connect(self._on_local_finished)
        self.btn_local.setEnabled(False)
        self._local_worker.start()

    def _on_local_finished(self, ok):
        self._local_worker = None
        self.btn_local.setEnabled(True)
        self.progress_bar.setMaximum(100)
        self.progress_bar.setValue(0)
        self._add_log(f"✅ 本地防重完成，成功 {ok} 张", "success")

    def _auto_check_update(self):
        """启动时静默检查更新"""
        has_update, version, changelog, url = update_checker.check_for_update()
        if has_update:
            self._add_log(f"发现新版本 v{version}，点击「检查更新」升级", "warning")

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
        self.status_label.setText("状态：正在下载更新...")
        QApplication.processEvents()
        new_exe = update_checker.download_update(url,
            lambda d, t: self.status_label.setText(f"状态：正在下载更新 {d//1024//1024}/{t//1024//1024}MB"))
        if not new_exe:
            self._add_log("更新下载失败", "error")
            QMessageBox.critical(self, "更新失败", "下载失败，请稍后重试。")
            return
        self._add_log("正在应用更新...", "info")
        update_checker.apply_update(new_exe)

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
        backend.save_config(cfg)


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("VintedScraper")

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
    sys.exit(app.exec())


def _check_tamper(window):
    """检查运行时是否检测到篡改"""
    if license_mgr.is_tampered():
        QMessageBox.critical(window, "授权失效", "授权验证失败，软件将退出。")
        sys.exit(1)


if __name__ == "__main__":
    main()
