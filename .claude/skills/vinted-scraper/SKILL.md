---
name: vinted-scraper
description: Vinted 商品图片抓取 + 防重处理工具。当用户提到 Vinted 抓图、图片抓取、防重处理、商品图片下载、vinted_gui.py、Vinted_抓图.py、vinted_style.qss、本地防重、批量处理图片、EXIF 注入、JPEG 重编码、图片指纹清除、或提及修改/优化抓图速度/防重效果/图片画质/GUI界面时使用此 skill。也适用于添加新 GUI 控件、调整样式、新增配置开关、修改抓取逻辑、调试 Server Error、缩略图轮播、CDN 分辨率升级等任务。
---

# Vinted 商品图片抓取工具

## 项目文件

```
├── Vinted_抓图.py          # 纯业务逻辑（818行），无 GUI 依赖
├── vinted_gui.py           # PySide6 GUI（751行），Cal.com 极简风格
├── vinted_style.qss        # Cal.com QSS 样式表（214行）
├── vinted_config.ini       # 运行时自动生成，持久化用户设置
└── DESIGN.md               # Cal.com 设计系统参考（不直接影响代码）
```

## 架构

```
vinted_gui.py (启动入口)
  ├── VintedScraperGUI(QMainWindow)  — 单窗口，4 个 QGroupBox 垂直排列
  │   ├── 商品链接管理  — QPlainTextEdit + 按钮栏（支持拖拽 .txt）
  │   ├── 基础参数设置  — 路径/地理/checkbox 行
  │   ├── 任务操作      — 状态+进度条+按钮行（开始/停止/打开目录/本地防重）
  │   └── 运行日志      — QPlainTextEdit 只读 + 右键菜单
  ├── CrawlWorker(QThread)       — Vinted 抓取线程，通过 signals 通信
  ├── LocalProcessWorker(QThread) — 本地图片防重线程
  └── DropPlainTextEdit          — 支持拖拽 .txt 文件导入链接

Vinted_抓图.py (被 GUI import)
  ├── 常量配置     — PROXY, CROP_RATIO, GEO_DATA, JPEG_QUALITY_RANGE 等
  ├── 全局状态     — STOP_TASK, FAILED_URLS, COMPRESS_ENABLED 等
  ├── 回调接口     — _on_log, _on_status, _on_progress, _on_finished
  ├── 工具函数     — load/save_config, write_log, decimal_to_dms
  ├── process_image()           — 图片防重处理（核心）
  ├── init_chrome()             — Selenium Chrome 启动
  ├── close_all_popups()        — JS 注入关闭弹窗
  ├── scrape_vinted_by_browser()— 页面抓取 + 缩略图点击 + URL 提取
  ├── _download_single_image()  — 并发下载工作函数
  └── start_crawl_task()        — 主循环：浏览器复用 + 逐 URL 抓取
```

## 关键设计决策

- **回调而非 tkinter**：backend 通过 `_on_log` / `_on_status` / `_on_progress` / `_on_finished` 四个回调与任意 GUI 通信
- **QThread + Signal**：所有耗时操作走 QThread，跨线程只用 signals 更新 UI
- **浏览器复用**：`start_crawl_task` 创建一次 Chrome，传入所有 URL 共享
- **缩略图逐个点击**：`button.item-thumbnail[data-photoid]` 每点一个等 1 秒，让轮播滚动渲染新缩略图
- **DOM 提取 URL**：点完缩略图后从 DOM 取所有 `/f800/` 的 `<img>` src，不用 `page_source`
- **并发分辨率探测**：ThreadPoolExecutor 4 线程探测 f2000/原图，再并发 4 线程下载
- **配置持久化**：`vinted_config.ini` (ConfigParser)，GUI 的 `_save_config()` 写盘，`_load_config()` 恢复

## process_image() 防重流水线

按执行顺序：

1. **ICC 剥离** — `img.info.pop('icc_profile', None)` 移除颜色指纹
2. **色彩空间统一** — RGBA/P/L/CMYK → RGB
3. **RGBA 旋转** — 0.1-0.3° 随机微旋转（白底填充）
4. **缩放+裁剪合并** — 微缩放 0.1% + 微裁剪 0.2-0.5% → resize 回原尺寸
5. **像素噪点** — 每通道 ±1 随机抖动
6. **模糊+锐化** — GaussianBlur 0.2-0.4 + Sharpness 1.1-1.2
7. **亮度/对比度** — ±0.15% 微调
8. **隐形水印**（可选）— 透明度 1/255，肉眼不可见
9. **EXIF 注入**（Vinted 模式）— 随机设备 + 随机日期 + GPS 坐标
10. **JPEG 保存** — 根据模式选择 quality/subsampling：
    - `LOSSLESS_ENABLED` → quality=100, 4:4:4
    - `COMPRESS_ENABLED` → quality=95-98, 随机 subsampling
    - 默认（防重）→ quality=95-98, 随机 subsampling
11. **随机字节追加** — 128-256 字节追加到文件尾，彻底改 MD5

### skip_gps 参数

`process_image(path, skip_gps=True)` 跳过 GPS/EXIF 注入（本地防重使用）。

## 图片提取策略（核心经验）

**失败的方法**：
- `page_source` 正则提取 → 全部 404（URL 缺少 session token）
- 批量 JS 点击缩略图 → Vinted React 不同时处理多次点击
- 查看器 `data-testid="image-carousel-button-right"` → headless 模式点击不导航

**成功的方法**：
1. 找到所有 `button.item-thumbnail[data-photoid]`
2. 用 `data-photoid` 去重，逐个 `driver.execute_script("arguments[0].click();", btn)`
3. 每个点击后 `sleep(1)` 等 React 渲染
4. 每轮 `find_elements` 重新查询（新缩略图渲染后出现在 DOM 中）
5. 全部点完后从 DOM 提取所有 `img[src*="/f800/"]`
6. 并发探测 f2000/原图分辨率 → 最终下载

## Server Error 处理

Vinted 偶发返回错误页面（标题正常、body 含 "technical issues"）。
- `driver.get(url)` 后 `sleep(2)` → JS 检查 body 文本
- 命中 → 立即 `driver.get(url)` 重试（不用 `refresh`）
- 最多 3 次，日志打 `⚠️ Server Error，立即重试`
- 等 item-photos 容器用合并 XPath `|`（单次 8s 超时，不逐个 xpath 等）

## GUI 注意事项

### QComboBox 下拉箭头
Qt6 Windows：只要 QSS 碰了 QComboBox 任何属性，系统原生箭头消失。必须用 `::down-arrow { image: url(data:image/svg+xml;base64,...) }` 提供自定义箭头。

### QMessageBox
必须 `setStandardButtons(QMessageBox.Ok)` 否则 X 按钮关不掉。需显式 QSS 否则文字颜色继承全局可能看不清。

### 配置初始化和持久化
- `_load_config()` 在 `__init__` 中调用，所有 `self._xxx` 变量 + `backend.XXX` 全局初始化
- `_save_config()` 每次设置变更时调用（checkbox toggle 等），路径输入用 500ms debounce timer
- `_apply_config_to_ui()` 在 UI 构建后调用，设置控件初始值

### 按钮布局
500px 宽窗口，任务按钮行最多 4 个按钮（开始抓取 | 停止任务 | 打开目录 | 本地防重 ▾）。"清空日志"移到日志区标题栏。

## 添加新功能模式

### 添加新配置开关
1. `Vinted_抓图.py`：加全局变量 `XXX_ENABLED = False`
2. `vinted_gui.py` `_load_config()`：读配置 `self._xxx = cfg.get("xxx_enabled", "False") == "True"` + 设置 `backend.XXX_ENABLED`
3. `_save_config()`：加 `"xxx_enabled": str(self._xxx)` 
4. `_build_xxx_section()`：加对应的 QCheckBox
5. `_connect_signals()`：加 `toggled.connect`
6. 加 handler `_on_xxx_toggled(self, v):` + `_save_config()`
7. `_apply_config_to_ui()`：加 `self.chk_xxx.setChecked()`
8. `_set_ui_running()`：加 `self.chk_xxx.setEnabled(not running)`

### 添加新按钮
1. 在对应 QGroupBox 的按钮栏加 `self.btn_xxx = QPushButton(...)`
2. `_connect_signals()` 加 `clicked.connect`
3. 写 handler 方法
4. `_set_ui_running()` 控制 enable/disable

### 修改抓取逻辑
只改 `Vinted_抓图.py`：
- 页面加载策略 → `scrape_vinted_by_browser()` 
- 图片提取方式 → 缩略图点击部分
- 下载策略 → `_download_single_image()` + `start_crawl_task()` 的 ThreadPoolExecutor
- 防重参数 → 常量 + `process_image()`

## 已知问题和修复记录

| 问题 | 原因 | 修复 |
|------|------|------|
| Server Error 页面卡住 | Vinted 反爬，标题正常 body 异常 | 文本检测 + `driver.get()` 重试 |
| 只抓到 5 张而非全部 | 缩略图轮播懒加载 | 逐个点击缩略图触发渲染 |
| page_source 提取全部 404 | URL 缺少 session token | 改回 DOM 提取 (`img.src`) |
| 查看器箭头点击不导航 | headless 模式 React 事件不触发 | 放弃查看器，用缩略图逐个点击 |
| WebP 源 `subsampling="keep"` 崩溃 | PIL 只对 JPEG 源支持 keep | 改为显式 `"4:4:4"` |
| QGroupBox 内容重叠 | padding-top 和 margin-top 冲突 | `padding: 0px 12px 10px 12px`，标题活在 margin 区 |
| 下载图片偏小（100KB vs 原图 1MB） | 只取了 f800 分辨率 | 加并发 HEAD 探测 f2000/原图 |
| QComboBox 箭头消失 | Qt6 Windows 原生渲染被 QSS 覆盖 | 内嵌 SVG base64 箭头 |
| 本地防重误注入法国 GPS | `process_image` 无条件写 EXIF | 加 `skip_gps` 参数 |
| 文件对话框弹两次 | 先弹文件选择再弹文件夹选择 | 改成 QMenu 二选一 |
| Worker 重入崩溃 | 连按两次开始创建两个 worker | `_start_crawl` 开头 `if isRunning(): return` |
| 每次按键写 vinted_config.ini | `textChanged` → `_save_config` | 改用 500ms QTimer debounce |

## 不要做的事

- **不要用 `page_source` 提取图片 URL** — CDN 需要 session token，只有 DOM `img.src` 有
- **不要批量 JS 点击缩略图** — React 不同时处理，逐个点击 + sleep(1)
- **不要在 QSS 中给 QGroupBox 同时设 padding-top 和 margin-top** — 标题重叠
- **不要给 QComboBox 写 QSS 而不提供 `::down-arrow` image** — 箭头消失
- **不要在 QMessageBox 中省略 `setStandardButtons(QMessageBox.Ok)`** — X 按钮失效
- **不要用 `print()` 输出含 emoji 的日志** — Windows GBK 控制台崩溃，用 try/except 保护
- **不要忘记 `_on_path_changed` 需要 debounce** — 每次按键写磁盘
- **本地防重要传 `skip_gps=True`** — 否则图片被注入法国 GPS
- **改缩进时不要用脚本批量处理** — 手工逐行确保正确
