# -*- coding: utf-8 -*-
"""
Vinted 商品图片抓取 — 纯业务逻辑模块
所有 GUI 依赖已移除，通过回调函数与任意 GUI 框架对接。
"""
import os
import sys
import io
import shutil
import random
import string
import hashlib
import threading
import requests
import piexif
import numpy as np
from PIL import Image, ImageEnhance, ImageFilter, ImageDraw, ImageFont
from tqdm import tqdm
from time import sleep
import configparser
from datetime import datetime, timedelta
import win32api
import win32con
import win32com.client
# Selenium
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException

# ====================== 基础配置（核心参数完全不动） ======================
PROXY = ""
MANUAL_WAIT_TIME = 3
DEFAULT_SAVE_ROOT = "Processed_Images"
# 图片防重复核心参数
CROP_RATIO = (0.002, 0.005)
ROTATE_RANGE = (0.1, 0.3)
BRIGHTNESS_ADJUST = (-0.15, 0.15)
CONTRAST_ADJUST = (-0.15, 0.15)
APPEND_BYTES = (128, 256)
# 智能压缩
COMPRESS_QUALITY_RANGE = (95, 98)
# 隐形水印
WATERMARK_TEXT = "VINTED"
WATERMARK_OPACITY = 1
WATERMARK_POSITION = "随机"  # 随机 / 左上 / 右上 / 左下 / 右下
# JPEG 重编码防重（频域级，95+ 肉眼无差异）
JPEG_QUALITY_RANGE = (95, 98)
SUBSAMPLING_OPTIONS = ["4:2:0", "4:2:2", "4:4:4"]
# 并发下载
DOWNLOAD_WORKERS = 4
# 高级防检测参数
BLOCK_SHIFT_RANGE = (0.3, 1.5)       # 亚像素偏移量（像素），破坏 JPEG 8x8 块对齐
NOISE_AMP_RANGE = (1, 3)             # 空间相关噪声幅度范围
SPATIAL_BRIGHTNESS_STRENGTH = (0.001, 0.003)  # 空间亮度渐变坡度

# ====================== 国家-城市-经纬度地理数据（完全不动） ======================
GEO_DATA = {
    "法国": {
        "巴黎": (48.8566, 2.3522), "里昂": (45.7640, 4.8357), "马赛": (43.2965, 5.3698),
        "波尔多": (44.8378, -0.5792), "里尔": (50.6292, 3.0573), "南特": (47.2184, -1.5536),
        "尼斯": (43.7102, 7.2620), "斯特拉斯堡": (48.5734, 7.7521), "图卢兹": (43.6047, 1.4442),
        "蒙彼利埃": (43.6108, 3.8767), "雷恩": (48.1173, -1.6778), "格勒诺布尔": (45.1885, 5.7245),
        "第戎": (47.3220, 5.0415), "昂热": (47.4784, -0.5632), "勒阿弗尔": (49.4938, 0.1077),
        "克莱蒙费朗": (45.7772, 3.0870), "圣艾蒂安": (45.4397, 4.3872), "土伦": (43.1242, 5.9280)
    },
    "西班牙": {
        "马德里": (40.4168, -3.7038), "巴塞罗那": (41.3851, 2.1734), "瓦伦西亚": (39.4699, -0.3763),
        "塞维利亚": (37.3891, -5.9845), "马拉加": (36.7213, -4.4214), "毕尔巴鄂": (43.2630, -2.9350),
        "萨拉戈萨": (41.6488, -0.8891), "帕尔马": (39.5696, 2.6502), "穆尔西亚": (37.9922, -1.1307),
        "阿利坎特": (38.3452, -0.4810), "科尔多瓦": (37.8882, -4.7794), "巴利亚多利德": (41.6523, -4.7245),
        "维哥": (42.2406, -8.7207), "格拉纳达": (37.1773, -3.5986), "潘普洛纳": (42.8125, -1.6458),
        "桑坦德": (43.4623, -3.8099), "拉斯帕尔马斯": (28.1235, -15.4363), "希洪": (43.5322, -5.6611)
    },
    "英国": {
        "伦敦": (51.5074, -0.1278), "曼彻斯特": (53.4808, -2.2426), "伯明翰": (52.4862, -1.8904),
        "利物浦": (53.4084, -2.9916), "利兹": (53.8008, -1.5491), "爱丁堡": (55.9533, -3.1883),
        "格拉斯哥": (55.8642, -4.2518), "布里斯托尔": (51.4545, -2.5879), "纽卡斯尔": (54.9783, -1.6174),
        "谢菲尔德": (53.3811, -1.4701), "诺丁汉": (52.9548, -1.1581), "南安普敦": (50.9097, -1.4044),
        "莱斯特": (52.6369, -1.1398), "加的夫": (51.4816, -3.1791), "贝尔法斯特": (54.5973, -5.9301),
        "考文垂": (52.4068, -1.5197), "赫尔": (53.7457, -0.3367), "普利茅斯": (50.3755, -4.1427)
    },
    "意大利": {
        "罗马": (41.9028, 12.4964), "米兰": (45.4642, 9.1900), "都灵": (45.0703, 7.6869),
        "佛罗伦萨": (43.7696, 11.2558), "威尼斯": (45.4372, 12.3358), "那不勒斯": (40.8518, 14.2681),
        "博洛尼亚": (44.4949, 11.3426), "巴勒莫": (38.1157, 13.3615), "维罗纳": (45.4384, 10.9916),
        "热那亚": (44.4056, 8.9463), "巴里": (41.1171, 16.8719), "卡塔尼亚": (37.5079, 15.0892),
        "的里雅斯特": (45.6495, 13.7768), "帕多瓦": (45.4064, 11.8768), "布雷西亚": (45.5416, 10.2118),
        "帕尔马": (44.8015, 10.3280), "莫代纳": (44.6474, 10.9252), "佩鲁贾": (43.1107, 12.3908)
    },
    "德国": {
        "柏林": (52.5200, 13.4050), "慕尼黑": (48.1351, 11.5820), "汉堡": (53.5511, 9.9937),
        "法兰克福": (50.1109, 8.6821), "科隆": (50.9375, 6.9603), "杜塞尔多夫": (51.2277, 6.7735),
        "斯图加特": (48.7758, 9.1829), "莱比锡": (51.3397, 12.3731), "汉诺威": (52.3759, 9.7320),
        "多特蒙德": (51.5136, 7.4653), "埃森": (51.4556, 7.0116), "不来梅": (53.0793, 8.8017),
        "德累斯顿": (51.0504, 13.7373), "纽伦堡": (49.4521, 11.0767), "杜伊斯堡": (51.4344, 6.7624),
        "波恩": (50.7374, 7.0982), "曼海姆": (49.4875, 8.4660), "卡尔斯鲁厄": (49.0069, 8.4037)
    },
    "卢森堡": {
        "卢森堡市": (49.6116, 6.1319), "埃希特纳赫": (49.8103, 6.5241), "迪基希": (49.8059, 6.1009),
        "格雷文马赫": (49.6775, 6.4530), "雷米希": (49.5441, 6.3698), "菲安登": (49.9343, 6.0791)
    },
    "爱尔兰": {
        "都柏林": (53.3498, -6.2603), "科克": (51.8969, -8.4863), "利默里克": (52.6680, -8.6239),
        "戈尔韦": (53.2707, -9.0568), "沃特福德": (52.2593, -7.1101), "德罗赫达": (53.7175, -6.3541),
        "邓多克": (54.0059, -6.4048), "斯莱戈": (54.2766, -8.4761), "基尔肯尼": (52.6541, -7.2525)
    },
    "波兰": {
        "华沙": (52.2297, 21.0122), "克拉科夫": (50.0647, 19.9450), "罗兹": (51.7592, 19.4560),
        "弗罗茨瓦夫": (51.1079, 17.0385), "波兹南": (52.4064, 16.9252), "格但斯克": (54.3520, 18.6466),
        "什切青": (53.4285, 14.5528), "比得哥什": (53.1235, 18.0084), "卢布林": (51.2465, 22.5684),
        "格丁尼亚": (54.5189, 18.5305), "卡托维兹": (50.2649, 19.0238), "托伦": (53.0138, 18.5984),
        "热舒夫": (50.0412, 21.9990), "奥尔什丁": (53.7784, 20.4801), "比亚韦斯托克": (53.1325, 23.1688),
        "凯尔采": (50.8661, 20.6286), "琴斯特霍瓦": (50.8118, 19.1203), "拉多姆": (51.4027, 21.1471)
    },
    "美国": {
        "纽约": (40.7128, -74.0060), "洛杉矶": (34.0522, -118.2437), "芝加哥": (41.8781, -87.6298),
        "休斯顿": (29.7604, -95.3698), "迈阿密": (25.7617, -80.1918), "西雅图": (47.6062, -122.3321),
        "旧金山": (37.7749, -122.4194), "波士顿": (42.3601, -71.0589), "达拉斯": (32.7767, -96.7970)
    },
    "俄罗斯": {
        "莫斯科": (55.7558, 37.6176), "圣彼得堡": (59.9343, 30.3351), "新西伯利亚": (55.0084, 82.9357),
        "叶卡捷琳堡": (56.8389, 60.6057), "喀山": (55.8304, 49.0661), "下诺夫哥罗德": (56.3269, 44.0059),
        "车里雅宾斯克": (55.1644, 61.4368), "萨马拉": (53.1959, 50.1002), "顿河畔罗斯托夫": (47.2226, 39.7186)
    },
    "荷兰": {
        "阿姆斯特丹": (52.3676, 4.9041), "鹿特丹": (51.9225, 4.4792), "海牙": (52.0705, 4.3007),
        "乌得勒支": (52.0907, 5.1214), "埃因霍温": (51.4416, 5.4697), "蒂尔堡": (51.5605, 5.0913),
        "格罗宁根": (53.2194, 6.5665), "马斯特里赫特": (50.8514, 5.6909), "奈梅亨": (51.8125, 5.8372)
    },
    "葡萄牙": {
        "里斯本": (38.7223, -9.1393), "波尔图": (41.1579, -8.6291), "布拉加": (41.5454, -8.4265),
        "科英布拉": (40.2033, -8.4265), "法鲁": (37.0194, -7.9304), "丰沙尔": (32.6497, -16.9033),
        "阿威罗": (40.6333, -8.6500), "塞图巴尔": (38.5244, -8.8926), "维塞乌": (40.6610, -7.9097)
    }
}

# ====================== 运行时状态 ======================
CONFIG_FILE = "vinted_config.ini"
STOP_TASK = False
LOG_FILE = ""
CUSTOM_SAVE_ROOT = DEFAULT_SAVE_ROOT
SESSION_SAVE_ROOT = ""  # 当前会话实际保存目录（含时间戳子文件夹）
SELECTED_COUNTRY = None
SELECTED_CITY = None
SELECTED_GPS_MODE = None
SELECTED_GPS_DATA = None
SESSION_GPS = None   # (lat, lon, city_name) 会话级GPS
SESSION_EXIF = None  # (make, model, software, dev_model, exposure, fnum, iso, lens) 会话级EXIF
SESSION_JPEG = None  # (quality, subsampling) 会话级JPEG参数
SESSION_DT_BASE = None  # 会话起始时间，每张图递增几分钟
TOTAL_TASKS = 0
CURRENT_TASK = 0
SUCCESS_COUNT = 0
FAIL_COUNT = 0
FAILED_URLS = []
FAIL_REASONS = {}
TOTAL_IMAGES = 0   # 累计处理图片数（GUI 统计用）
_images_lock = threading.Lock()
COMPRESS_ENABLED = False
WATERMARK_ENABLED = False
LOSSLESS_ENABLED = False  # 无损画质模式：quality=100 + 4:4:4
ADVANCED_ANTI_DETECT_ENABLED = False  # 高级防检测：JPEG块破坏 + 空间噪声 + 空变亮度
DEVICE_CROP_ENABLED = False  # 机模画幅匹配：裁切到随机设备原生比例
CUSTOM_CROP_ENABLED = False  # 自定义裁剪
CROP_TOP_PCT = 0             # 上边裁切百分比 0-50
CROP_BOTTOM_PCT = 0          # 下边
CROP_LEFT_PCT = 0            # 左边
CROP_RIGHT_PCT = 0           # 右边

# 深度防重处理模式（针对平台重复检测）
DEEP_ANTI_DUPLICATE_ENABLED = False  # 深度防重：透视变换 + 镜头畸变 + 参数增强
# DEEP_PERSPECTIVE_STRONG 已移除，统一使用轻度档避免白边
DEEP_MODE_VARIANTS = 2               # 深度模式输出版本数（1-3）

# 深度模式参数集
DEEP_ROTATE_RANGE = (0.8, 1.5)
DEEP_CROP_RATIO = (0.015, 0.04)
DEEP_NOISE_SIGMA_RANGE = (3, 8)
DEEP_BRIGHTNESS_ADJUST = (-4.0, 4.0)
DEEP_CONTRAST_ADJUST = (-4.0, 4.0)
DEEP_JPEG_QUALITY_RANGE = (85, 94)
DEEP_BLOCK_SHIFT_RANGE = (1.5, 3.0)
DEEP_SPATIAL_BRIGHTNESS_STRENGTH = (0.004, 0.01)
DEEP_WARMTH_RANGE = (-0.10, 0.10)
DEEP_GAMMA_RANGE = (0.93, 1.07)
DEEP_LENS_DISTORTION_RANGE = (-0.010, 0.010)   # 镜头畸变加强以补偿去掉仿射剪切

# 回调函数引用（由 GUI 层设置）
_on_log = None          # (content: str, level: str) -> None
_log_lock = threading.Lock()  # 并发日志写入保护
_on_status = None       # (status_text: str) -> None
_on_progress = None     # (current: int, total: int, success: int, fail: int) -> None
_on_finished = None     # (stopped: bool) -> None


# ====================== 工具函数 ======================
def load_config():
    config = configparser.ConfigParser()
    if os.path.exists(CONFIG_FILE):
        try:
            config.read(CONFIG_FILE, encoding="utf-8")
            return config["SETTINGS"] if "SETTINGS" in config else {}
        except Exception:
            return {}
    return {}


def save_config(settings):
    config = configparser.ConfigParser()
    config["SETTINGS"] = settings
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        config.write(f)


def decimal_to_dms(decimal):
    degrees = int(abs(decimal))
    minutes = int((abs(decimal) - degrees) * 60)
    seconds = round(((abs(decimal) - degrees - minutes/60) * 3600) * 100, 2)
    return (degrees, 1), (minutes, 1), (round(seconds * 100), 100)


ENABLE_FILE_LOG = True  # GUI 可设为 False 关闭文件日志

def write_log(content, level="info"):
    global LOG_FILE
    with _log_lock:
        if LOG_FILE and ENABLE_FILE_LOG:
            import time as _time
            with open(LOG_FILE, "a", encoding="utf-8") as f:
                f.write(f"[{_time.strftime('%H:%M:%S')}] {content}\n")
    try:
        print(content)
    except (UnicodeEncodeError, OSError):
        pass
    if _on_log:
        _on_log(content, level)


def random_filename(ext=".jpg"):
    return ''.join(random.choices(string.ascii_letters + string.digits, k=16)) + ext


# ====================== 机模画幅映射 ======================
DEVICE_LIST = [
    "随机",
    # Apple
    "iPhone 17 Pro Max", "iPhone 17 Pro", "iPhone 17",
    "iPhone 16 Pro Max", "iPhone 16 Pro", "iPhone 16",
    "iPhone 15 Pro Max", "iPhone 15 Pro", "iPhone 15",
    "iPhone 14 Pro", "iPhone 14", "iPhone 13 Pro", "iPhone 13", "iPhone SE",
    # Samsung (欧洲销量第一)
    "Galaxy S24 Ultra", "Galaxy S24", "Galaxy S23 Ultra", "Galaxy S23",
    "Galaxy A55", "Galaxy A54", "Galaxy A35",
    # Google (欧洲热门)
    "Pixel 9 Pro", "Pixel 9", "Pixel 8 Pro", "Pixel 8", "Pixel 7a",
    # Huawei
    "HUAWEI P70 Pro", "HUAWEI P70", "Mate 60 Pro", "Mate 60",
    # Xiaomi / Redmi
    "Xiaomi 14 Ultra", "Xiaomi 14", "Xiaomi 13T Pro",
    "Redmi Note 13 Pro", "Redmi Note 12",
    # OnePlus
    "OnePlus 12", "OnePlus 11", "OnePlus Nord 4",
    # Sony
    "Xperia 1 VI", "Xperia 5 V",
    # OPPO
    "OPPO Find X7", "OPPO Reno 11",
    # Motorola
    "Moto G84", "Moto Edge 50",
    # 相机
    "Canon EOS R5", "Canon EOS R6", "Canon EOS R8",
    "Nikon Z8", "Nikon Z6 III", "Nikon Zf",
    "Sony A7 IV", "Sony A7C II", "Sony A7R V",
    "Fujifilm X-T5", "Leica Q3", "Panasonic S5 II",
    "DJI Mini 4 Pro", "GoPro HERO12",
]
SELECTED_DEVICE = "随机"

# 所有手机 4:3，所有相机 3:2
def _get_device_ratio(device):
    cameras_32 = ["Canon", "Nikon", "Sony A7", "Sony A7C", "Sony A7R",
                  "Fujifilm", "Leica", "Panasonic"]
    for c in cameras_32:
        if c in device:
            return (3, 2)
    return (4, 3)


def _custom_crop_pct(img, top_pct, bottom_pct, left_pct, right_pct):
    """按四边百分比裁切图片。每个边 0-50%，合计不超过 95%。"""
    if top_pct == 0 and bottom_pct == 0 and left_pct == 0 and right_pct == 0:
        return img
    ow, oh = img.size
    # 限制合计不超过 95%
    if top_pct + bottom_pct > 95:
        scale = 95 / (top_pct + bottom_pct)
        top_pct = top_pct * scale
        bottom_pct = bottom_pct * scale
    if left_pct + right_pct > 95:
        scale = 95 / (left_pct + right_pct)
        left_pct = left_pct * scale
        right_pct = right_pct * scale
    top = int(oh * top_pct / 100)
    bottom = int(oh * bottom_pct / 100)
    left = int(ow * left_pct / 100)
    right = int(ow * right_pct / 100)
    if oh - top - bottom <= 0 or ow - left - right <= 0:
        return img
    return img.crop((left, top, ow - right, oh - bottom))

DEVICE_INFO_MAP = {
    # Apple
    "iPhone 17 Pro Max": ("Apple", "iPhone 17 Pro Max", "Photos"),
    "iPhone 17 Pro": ("Apple", "iPhone 17 Pro", "Photos"),
    "iPhone 17": ("Apple", "iPhone 17", "Photos"),
    "iPhone 16 Pro Max": ("Apple", "iPhone 16 Pro Max", "Photos"),
    "iPhone 16 Pro": ("Apple", "iPhone 16 Pro", "Photos"),
    "iPhone 16": ("Apple", "iPhone 16", "Photos"),
    "iPhone 15 Pro Max": ("Apple", "iPhone 15 Pro Max", "Photos"),
    "iPhone 15 Pro": ("Apple", "iPhone 15 Pro", "Photos"),
    "iPhone 15": ("Apple", "iPhone 15", "Photos"),
    "iPhone 14 Pro": ("Apple", "iPhone 14 Pro", "Photos"),
    "iPhone 14": ("Apple", "iPhone 14", "Photos"),
    "iPhone 13 Pro": ("Apple", "iPhone 13 Pro", "Photos"),
    "iPhone 13": ("Apple", "iPhone 13", "Photos"),
    "iPhone SE": ("Apple", "iPhone SE", "Photos"),
    # Samsung
    "Galaxy S24 Ultra": ("Samsung", "Galaxy S24 Ultra", "Gallery"),
    "Galaxy S24": ("Samsung", "Galaxy S24", "Gallery"),
    "Galaxy S23 Ultra": ("Samsung", "Galaxy S23 Ultra", "Gallery"),
    "Galaxy S23": ("Samsung", "Galaxy S23", "Gallery"),
    "Galaxy A55": ("Samsung", "Galaxy A55", "Gallery"),
    "Galaxy A54": ("Samsung", "Galaxy A54", "Gallery"),
    "Galaxy A35": ("Samsung", "Galaxy A35", "Gallery"),
    # Google
    "Pixel 9 Pro": ("Google", "Pixel 9 Pro", "Google Photos"),
    "Pixel 9": ("Google", "Pixel 9", "Google Photos"),
    "Pixel 8 Pro": ("Google", "Pixel 8 Pro", "Google Photos"),
    "Pixel 8": ("Google", "Pixel 8", "Google Photos"),
    "Pixel 7a": ("Google", "Pixel 7a", "Google Photos"),
    # Huawei
    "HUAWEI P70 Pro": ("HUAWEI", "P70 Pro", "Snapseed"),
    "HUAWEI P70": ("HUAWEI", "P70", "Snapseed"),
    "Mate 60 Pro": ("HUAWEI", "Mate 60 Pro", "System Camera"),
    "Mate 60": ("HUAWEI", "Mate 60", "System Camera"),
    # Xiaomi
    "Xiaomi 14 Ultra": ("Xiaomi", "14 Ultra", "Lightroom"),
    "Xiaomi 14": ("Xiaomi", "14", "Lightroom"),
    "Xiaomi 13T Pro": ("Xiaomi", "13T Pro", "Lightroom"),
    "Redmi Note 13 Pro": ("Xiaomi", "Redmi Note 13 Pro", "Lightroom"),
    "Redmi Note 12": ("Xiaomi", "Redmi Note 12", "Snapseed"),
    # OnePlus
    "OnePlus 12": ("OnePlus", "OnePlus 12", "Photos"),
    "OnePlus 11": ("OnePlus", "OnePlus 11", "Photos"),
    "OnePlus Nord 4": ("OnePlus", "Nord 4", "Photos"),
    # Sony
    "Xperia 1 VI": ("Sony", "Xperia 1 VI", "Photos"),
    "Xperia 5 V": ("Sony", "Xperia 5 V", "Photos"),
    # OPPO
    "OPPO Find X7": ("OPPO", "Find X7", "Photos"),
    "OPPO Reno 11": ("OPPO", "Reno 11", "Photos"),
    # Motorola
    "Moto G84": ("Motorola", "Moto G84", "Photos"),
    "Moto Edge 50": ("Motorola", "Edge 50", "Photos"),
    # 相机
    "Canon EOS R5": ("Canon", "EOS R5", "Lightroom"),
    "Canon EOS R6": ("Canon", "EOS R6", "Lightroom"),
    "Canon EOS R8": ("Canon", "EOS R8", "Lightroom"),
    "Nikon Z8": ("Nikon", "Z8", "Lightroom"),
    "Nikon Z6 III": ("Nikon", "Z6 III", "Lightroom"),
    "Nikon Zf": ("Nikon", "Zf", "Lightroom"),
    "Sony A7 IV": ("Sony", "A7 IV", "Lightroom"),
    "Sony A7C II": ("Sony", "A7C II", "Lightroom"),
    "Sony A7R V": ("Sony", "A7R V", "Lightroom"),
    "Fujifilm X-T5": ("Fujifilm", "X-T5", "Lightroom"),
    "Leica Q3": ("Leica", "Q3", "Lightroom"),
    "Panasonic S5 II": ("Panasonic", "S5 II", "Lightroom"),
    "DJI Mini 4 Pro": ("DJI", "Mini 4 Pro", "Photos"),
    "GoPro HERO12": ("GoPro", "HERO12", "Photos"),
}


# ====================== 深度防重变换函数 ======================
def _apply_perspective(img, max_offset_pct):
    """仿射剪切+微缩放：模拟拍摄角度变化，破坏 pHash 低频指纹"""
    w, h = img.size
    m = max_offset_pct * 0.25  # 配合后续 4px 边缘裁切，留有充足余量
    shear_x = random.uniform(-m, m)
    shear_y = random.uniform(-m, m)
    scale = 1.0 + random.uniform(-m * 0.3, m * 0.3)
    tx = w / 2 * (1 - scale) - shear_x * h / 2
    ty = h / 2 * (1 - scale) - shear_y * w / 2
    coeffs = (scale, shear_x, tx, shear_y, scale, ty)
    return img.transform((w, h), Image.AFFINE, coeffs, resample=Image.BICUBIC, fillcolor=(255, 255, 255))


def _apply_lens_distortion(img_array, k1):
    """镜头畸变模拟：桶形/枕形径向畸变（纯 numpy 双线性插值）"""
    h, w = img_array.shape[:2]
    cx, cy = (w - 1) / 2.0, (h - 1) / 2.0
    y, x = np.mgrid[0:h, 0:w].astype(np.float32)
    xn = (x - cx) / cx
    yn = (y - cy) / cy
    r2 = xn * xn + yn * yn
    factor = 1.0 / (1.0 + k1 * r2)
    x_src = cx + (x - cx) * factor
    y_src = cy + (y - cy) * factor
    x_src = np.clip(x_src, 0, w - 1)
    y_src = np.clip(y_src, 0, h - 1)
    x0 = np.floor(x_src).astype(np.int32)
    y0 = np.floor(y_src).astype(np.int32)
    x1 = np.clip(x0 + 1, 0, w - 1)
    y1 = np.clip(y0 + 1, 0, h - 1)
    wx = (x_src - x0).reshape(h, w, 1)
    wy = (y_src - y0).reshape(h, w, 1)
    result = np.zeros_like(img_array)
    for c in range(3):
        result[:, :, c] = (
            (1 - wx[:,:,0]) * (1 - wy[:,:,0]) * img_array[y0, x0, c] +
            wx[:,:,0] * (1 - wy[:,:,0]) * img_array[y0, x1, c] +
            (1 - wx[:,:,0]) * wy[:,:,0] * img_array[y1, x0, c] +
            wx[:,:,0] * wy[:,:,0] * img_array[y1, x1, c]
        )
    return result.astype(np.uint8)


def _generate_gaussian_noise(img_array, sigma):
    """高斯加权噪点：暗部噪点更明显，模拟 CMOS 传感器特性"""
    h, w = img_array.shape[:2]
    noise = np.random.normal(0, sigma, (h, w, 3)).astype(np.int16)
    luminance = (0.299 * img_array[:, :, 0].astype(np.float32) +
                 0.587 * img_array[:, :, 1].astype(np.float32) +
                 0.114 * img_array[:, :, 2].astype(np.float32)) / 255.0
    weight = 1.5 - 0.8 * luminance
    weight = weight.reshape(h, w, 1)
    return (noise * weight).astype(np.int16)


def _detect_previous_processing(image_path):
    """检测图片是否已被本工具处理过（检查 UserComment 中的位置标记）"""
    try:
        img = Image.open(image_path)
        exif_raw = img.info.get("exif")
        img.close()
        if not exif_raw:
            return False
        exif = piexif.load(exif_raw)
        user_comment = exif.get("Exif", {}).get(piexif.ExifIFD.UserComment, b"")
        if isinstance(user_comment, bytes):
            user_comment = user_comment.decode("utf-8", errors="ignore")
        # 仅通过我们独有的特征判断：UserComment 中的 "Shooting Location"
        if "Shooting Location" in str(user_comment):
            return True
    except Exception:
        pass
    return False


# ====================== 结构级变换（对抗 CNN 检测） ======================

def _find_coeffs(pa, pb):
    """从四对点计算 PIL PERSPECTIVE 8 系数矩阵"""
    matrix = []
    for p1, p2 in zip(pa, pb):
        matrix.append([p1[0], p1[1], 1, 0, 0, 0, -p2[0]*p1[0], -p2[0]*p1[1]])
        matrix.append([0, 0, 0, p1[0], p1[1], 1, -p2[1]*p1[0], -p2[1]*p1[1]])
    A = np.array(matrix, dtype=np.float64)
    B = np.array(pb, dtype=np.float64).reshape(8)
    try:
        coeffs = np.linalg.solve(A, B)
        return tuple(coeffs.tolist())
    except np.linalg.LinAlgError:
        return (1,0,0,0,1,0,0,0)  # identity


def _apply_perspective_proper(img, max_offset_pct):
    """透视变形：四角随机偏移 + PIL PERSPECTIVE 8系数，正确实现无伪影"""
    w, h = img.size
    max_off = max(1, int(min(w, h) * max_offset_pct))
    src_corners = [
        (random.randint(0, max_off), random.randint(0, max_off)),
        (w - 1 - random.randint(0, max_off), random.randint(0, max_off)),
        (w - 1 - random.randint(0, max_off), h - 1 - random.randint(0, max_off)),
        (random.randint(0, max_off), h - 1 - random.randint(0, max_off)),
    ]
    dst_corners = [(0,0), (w,0), (w,h), (0,h)]
    coeffs = _find_coeffs(dst_corners, src_corners)
    return img.transform((w, h), Image.PERSPECTIVE, coeffs, resample=Image.BICUBIC, fillcolor=(255,255,255))


def _apply_elastic_distortion(img_array, grid_size=8, max_disp=2.0):
    """弹性局部扭曲：纯 numpy 双线性平滑上采样，无网格线"""
    h, w = img_array.shape[:2]
    gh, gw = grid_size, grid_size
    dx = (np.random.rand(gh, gw) * 2 - 1) * max_disp
    dy = (np.random.rand(gh, gw) * 2 - 1) * max_disp
    # 纯 numpy 双线性插值上采样位移场
    y_ratio = (gh - 1) / (h - 1) if h > 1 else 0
    x_ratio = (gw - 1) / (w - 1) if w > 1 else 0
    y_src = np.arange(h, dtype=np.float32) * y_ratio
    x_src = np.arange(w, dtype=np.float32) * x_ratio
    y0 = np.floor(y_src).astype(np.int32); x0 = np.floor(x_src).astype(np.int32)
    y1 = np.clip(y0+1, 0, gh-1); x1 = np.clip(x0+1, 0, gw-1)
    wy = (y_src - y0).astype(np.float32); wx = (x_src - x0).astype(np.float32)
    # 双线性插值到全分辨率
    dx_up = ((1-wy[:,None])*(1-wx[None,:])*dx[y0[:,None],x0[None,:]] +
             (1-wy[:,None])*wx[None,:]*dx[y0[:,None],x1[None,:]] +
             wy[:,None]*(1-wx[None,:])*dx[y1[:,None],x0[None,:]] +
             wy[:,None]*wx[None,:]*dx[y1[:,None],x1[None,:]])
    dy_up = ((1-wy[:,None])*(1-wx[None,:])*dy[y0[:,None],x0[None,:]] +
             (1-wy[:,None])*wx[None,:]*dy[y0[:,None],x1[None,:]] +
             wy[:,None]*(1-wx[None,:])*dy[y1[:,None],x0[None,:]] +
             wy[:,None]*wx[None,:]*dy[y1[:,None],x1[None,:]])
    y_idx, x_idx = np.mgrid[0:h, 0:w].astype(np.float32)
    map_x = np.clip(x_idx + dy_up, 0, w-1)
    map_y = np.clip(y_idx + dx_up, 0, h-1)
    x0m = np.floor(map_x).astype(np.int32); y0m = np.floor(map_y).astype(np.int32)
    x1m = np.clip(x0m+1, 0, w-1); y1m = np.clip(y0m+1, 0, h-1)
    wxm = (map_x - x0m).astype(np.float32); wym = (map_y - y0m).astype(np.float32)
    result = np.zeros_like(img_array)
    for c in range(3):
        result[:,:,c] = ((1-wxm)*(1-wym)*img_array[y0m,x0m,c] + wxm*(1-wym)*img_array[y0m,x1m,c] +
                         (1-wxm)*wym*img_array[y1m,x0m,c] + wxm*wym*img_array[y1m,x1m,c])
    return result.astype(np.uint8)


def _apply_background_shift(img_array, strength=0.08):
    """背景渐变偏移：远离中心的区域叠加色温偏移"""
    h, w = img_array.shape[:2]
    cy, cx = (h-1)/2, (w-1)/2
    max_dist = np.sqrt(cx*cx + cy*cy)
    y, x = np.mgrid[0:h, 0:w].astype(np.float32)
    dist = np.sqrt((x-cx)**2 + (y-cy)**2)
    weight = np.clip((dist / max_dist - 0.5) * 2, 0, 1)
    weight = weight.reshape(h, w, 1)
    arr = img_array.astype(np.float32)
    warmth = random.uniform(-strength, strength)
    if warmth > 0:
        arr[:,:,0] += weight[:,:,0] * warmth * 255
        arr[:,:,2] -= weight[:,:,0] * warmth * 128
    else:
        arr[:,:,2] += weight[:,:,0] * abs(warmth) * 255
        arr[:,:,0] -= weight[:,:,0] * abs(warmth) * 128
    return np.clip(arr, 0, 255).astype(np.uint8)


def _generate_frequency_texture(h, w):
    """生成中频主导纹理：FFT → 仅保留中频带 → IFFT"""
    # 随机频谱
    spectrum = np.random.randn(h, w) + 1j * np.random.randn(h, w)
    # 构建带通掩膜（保留中频，滤除低频和高频）
    y, x = np.mgrid[-h//2:h//2, -w//2:w//2]
    dist = np.sqrt(x*x + y*y).astype(np.float32)
    max_d = min(h, w) / 2
    # 带通：0.08×max 到 0.4×max 之间
    mask = np.clip((dist - 0.08*max_d) / (0.05*max_d), 0, 1) * np.clip((0.4*max_d - dist) / (0.05*max_d), 0, 1)
    mask = np.fft.ifftshift(mask)
    # 频域滤波 → 空间域
    texture = np.real(np.fft.ifft2(spectrum * mask))
    # 归一化到 [-1, 1]
    tx_max = np.abs(texture).max()
    if tx_max > 0:
        texture = texture / tx_max
    return texture.astype(np.float32)


def _apply_texture_overlay(img_array, opacity=0.005):
    """梯度自适应纹理叠加：平坦区域多叠，边缘区域少叠"""
    h, w = img_array.shape[:2]
    # Sobel 梯度检测
    gray = (0.299*img_array[:,:,0].astype(np.float32) +
            0.587*img_array[:,:,1].astype(np.float32) +
            0.114*img_array[:,:,2].astype(np.float32))
    gx = np.gradient(gray, axis=1)
    gy = np.gradient(gray, axis=0)
    edge = np.sqrt(gx*gx + gy*gy)
    # 归一化 + 反转（边缘小 → 平坦大）
    edge_norm = np.clip(edge / (edge.max() + 1e-8), 0, 1)
    grad_weight = 1 - edge_norm  # 边缘 0，平坦 1
    # 生成中频纹理
    texture = _generate_frequency_texture(h, w)
    # 纹理按梯度权重叠加到 RGB
    arr = img_array.astype(np.float32)
    alpha = opacity * 255
    for c in range(3):
        arr[:,:,c] += texture * grad_weight * alpha
    return np.clip(arr, 0, 255).astype(np.uint8)


def _apply_lighting_gradient(img_array, strength=0.02):
    """随机光影渐变：模拟不同方向和色温的光源，视觉上只是光线微不同"""
    h, w = img_array.shape[:2]
    angle = random.uniform(0, 2 * np.pi)
    y, x = np.mgrid[0:h, 0:w].astype(np.float32)
    proj = x * np.cos(angle) + y * np.sin(angle)
    proj_norm = (proj - proj.min()) / (proj.max() - proj.min() + 1e-8)  # 0→1
    gradient = (proj_norm * 2 - 1).reshape(h, w, 1)  # -1 → 1
    arr = img_array.astype(np.float32)
    warmth = random.uniform(-0.5, 0.5)  # 暖色或冷色
    s = strength * 255
    if warmth > 0:
        arr[:,:,0] += gradient[:,:,0] * s * (1 + warmth)
        arr[:,:,2] += gradient[:,:,0] * s * (1 - warmth)
    else:
        arr[:,:,2] += gradient[:,:,0] * s * (1 + abs(warmth))
        arr[:,:,0] += gradient[:,:,0] * s * (1 - abs(warmth))
    return np.clip(arr, 0, 255).astype(np.uint8)


def _apply_local_liquefy(img_array, num_points=4, max_disp=2):
    """局部液化变形：随机锚点+高斯径向位移，模拟面料微变形"""
    h, w = img_array.shape[:2]
    result = img_array.astype(np.float32).copy()
    for _ in range(num_points):
        cx = random.randint(w//6, 5*w//6)
        cy = random.randint(h//6, 5*h//6)
        dx = random.uniform(-max_disp, max_disp)
        dy = random.uniform(-max_disp, max_disp)
        sigma = random.uniform(min(w,h)*0.06, min(w,h)*0.12)
        y_idx, x_idx = np.mgrid[0:h, 0:w].astype(np.float32)
        dist2 = (x_idx - cx)**2 + (y_idx - cy)**2
        weight = np.exp(-dist2 / (2 * sigma * sigma)).reshape(h, w, 1)
        result[:,:,0] += weight[:,:,0] * dx
        result[:,:,1] += weight[:,:,0] * dy
    # 双线性重采样
    y_src = np.tile(np.arange(h, dtype=np.float32).reshape(h,1), (1,w)) + result[:,:,1]
    x_src = np.tile(np.arange(w, dtype=np.float32).reshape(1,w), (h,1)) + result[:,:,0]
    x_src = np.clip(x_src, 0, w-1); y_src = np.clip(y_src, 0, h-1)
    x0 = np.floor(x_src).astype(np.int32); y0 = np.floor(y_src).astype(np.int32)
    x1 = np.clip(x0+1, 0, w-1); y1 = np.clip(y0+1, 0, h-1)
    wx = (x_src - x0).astype(np.float32); wy = (y_src - y0).astype(np.float32)
    out = np.zeros_like(img_array)
    for c in range(3):
        out[:,:,c] = ((1-wx)*(1-wy)*img_array[y0,x0,c] + wx*(1-wy)*img_array[y0,x1,c] +
                       (1-wx)*wy*img_array[y1,x0,c] + wx*wy*img_array[y1,x1,c])
    return out.astype(np.uint8)


def _apply_lab_shift(img_array, ab_shift=3):
    """LAB色域变换：AB通道微平移，L不变，CNN颜色敏感度高"""
    rgb = img_array.astype(np.float32) / 255.0
    # RGB → XYZ
    mask = rgb > 0.04045
    rgb_lin = np.where(mask, ((rgb + 0.055) / 1.055) ** 2.4, rgb / 12.92)
    xyz = np.zeros_like(rgb_lin)
    xyz[:,:,0] = 0.4124564*rgb_lin[:,:,0] + 0.3575761*rgb_lin[:,:,1] + 0.1804375*rgb_lin[:,:,2]
    xyz[:,:,1] = 0.2126729*rgb_lin[:,:,0] + 0.7151522*rgb_lin[:,:,1] + 0.0721750*rgb_lin[:,:,2]
    xyz[:,:,2] = 0.0193339*rgb_lin[:,:,0] + 0.1191920*rgb_lin[:,:,1] + 0.9503041*rgb_lin[:,:,2]
    # XYZ → LAB (D65)
    xn, yn, zn = 0.95047, 1.0, 1.08883
    fx = _lab_f(xyz[:,:,0]/xn); fy = _lab_f(xyz[:,:,1]/yn); fz = _lab_f(xyz[:,:,2]/zn)
    L = 116*fy - 16
    A = 500*(fx - fy) + random.uniform(-ab_shift, ab_shift)
    B = 200*(fy - fz) + random.uniform(-ab_shift, ab_shift)
    # LAB → RGB
    fy2 = (L + 16) / 116
    fx2 = A / 500 + fy2; fz2 = fy2 - B / 200
    x2 = xn * _lab_finv(fx2); y2 = yn * _lab_finv(fy2); z2 = zn * _lab_finv(fz2)
    rgb_lin2 = np.zeros_like(rgb_lin)
    rgb_lin2[:,:,0] =  3.2404542*x2 - 1.5371385*y2 - 0.4985314*z2
    rgb_lin2[:,:,1] = -0.9692660*x2 + 1.8760108*y2 + 0.0415560*z2
    rgb_lin2[:,:,2] =  0.0556434*x2 - 0.2040259*y2 + 1.0572252*z2
    rgb_lin2 = np.clip(rgb_lin2, 0, 1)
    m2 = rgb_lin2 > 0.0031308
    rgb2 = np.where(m2, 1.055 * (rgb_lin2 ** (1/2.4)) - 0.055, 12.92 * rgb_lin2)
    return np.clip(rgb2 * 255, 0, 255).astype(np.uint8)

def _lab_f(t):
    d = (6/29)**3
    return np.where(t > d, t**(1/3), t/(3*29*29/6/6) + 4/29)
def _lab_finv(t):
    d = 6/29
    return np.where(t > d, t**3, 3*d*d*(t - 4/29))


# ====================== 核心函数 ======================
def _verify_license_quick():
    """隐蔽的授权检查（不抛异常，返回 False 而非阻止，避免暴露检查点）"""
    try:
        import license_system as _ls
        if _ls.is_tampered():
            return False
        return True
    except Exception:
        return True  # 模块不存在时不拦截（开发环境容错）


def process_image(image_path, skip_gps=False):
    global SELECTED_COUNTRY, SELECTED_CITY, SELECTED_GPS_MODE, SELECTED_GPS_DATA, COMPRESS_ENABLED, WATERMARK_ENABLED
    global DEEP_ANTI_DUPLICATE_ENABLED, DEEP_MODE_VARIANTS, LOSSLESS_ENABLED, SESSION_DT_BASE
    if _on_status:
        _on_status("正在处理图片")
    img = None
    try:
        img = Image.open(image_path)
        original_width, original_height = img.size

        # 自动检测二次处理
        _prev_processed = DEEP_ANTI_DUPLICATE_ENABLED and _detect_previous_processing(image_path)
        if _prev_processed and _on_status:
            _on_status("检测到已处理图片，将深度重建指纹")

        # 剥离 ICC 配置（移除颜色指纹）
        img.info.pop('icc_profile', None)

        if img.mode in ("RGBA", "P", "L", "CMYK"):
            background = Image.new("RGB", img.size, (255, 255, 255))
            if img.mode == "RGBA":
                background.paste(img, mask=img.split()[-1])
            else:
                background.paste(img)
            img = background

        # ---- JPEG 8x8 块对齐破坏：亚像素平移 ----
        if ADVANCED_ANTI_DETECT_ENABLED or DEEP_ANTI_DUPLICATE_ENABLED:
            shift_range = DEEP_BLOCK_SHIFT_RANGE if DEEP_ANTI_DUPLICATE_ENABLED else BLOCK_SHIFT_RANGE
            shift_x = random.uniform(*shift_range) * random.choice([-1, 1])
            shift_y = random.uniform(*shift_range) * random.choice([-1, 1])
            img = img.transform(
                img.size, Image.AFFINE,
                (1, 0, shift_x, 0, 1, shift_y),
                resample=Image.BICUBIC, fillcolor=(255, 255, 255)
            )

        # ---- 防重处理：RGBA 一次转换，合并旋转+缩放+裁剪 ----
        rot_range = DEEP_ROTATE_RANGE if DEEP_ANTI_DUPLICATE_ENABLED else ROTATE_RANGE
        crop_ratio = DEEP_CROP_RATIO if DEEP_ANTI_DUPLICATE_ENABLED else CROP_RATIO
        rotate_angle = random.uniform(*rot_range) * random.choice([-1, 1])
        img = img.convert("RGBA")
        # expand=True 扩展画布避免旋转产生透明角 → 后续不会出现白边
        img = img.rotate(rotate_angle, expand=True, resample=Image.BICUBIC)
        # 居中裁切回原始尺寸
        rw, rh = img.size
        rl = (rw - original_width) // 2
        rt = (rh - original_height) // 2
        img = img.crop((rl, rt, rl + original_width, rt + original_height))

        # 微裁剪
        img = img.crop((
            int(original_width * random.uniform(*crop_ratio)),
            int(original_height * random.uniform(*crop_ratio)),
            original_width - int(original_width * random.uniform(*crop_ratio)),
            original_height - int(original_height * random.uniform(*crop_ratio)),
        ))
        img = img.resize((original_width, original_height), resample=Image.BICUBIC)

        # RGBA → RGB（白底合成）
        background = Image.new("RGB", img.size, (255, 255, 255))
        background.paste(img, mask=img.split()[-1])
        img = background

        # ---- 弹性局部扭曲：粗网格位移破坏 CNN 空间结构指纹 ----
        if DEEP_ANTI_DUPLICATE_ENABLED:
            img_array = np.array(img)
            img_array = _apply_elastic_distortion(img_array, grid_size=4, max_disp=1.0)
            img = Image.fromarray(img_array)

        # 局部液化已移除：均值偏移大、产生色阶断层

        # ---- 镜头畸变：模拟桶形/枕形畸变 ----
        if DEEP_ANTI_DUPLICATE_ENABLED:
            k1 = random.uniform(*DEEP_LENS_DISTORTION_RANGE)
            if abs(k1) > 0.001:
                img_array = np.array(img)
                img_array = _apply_lens_distortion(img_array, k1)
                img = Image.fromarray(img_array)

        # 边缘去白边：深度模式 3px 确保旋转+畸变残留完全消除
        ec = 3 if DEEP_ANTI_DUPLICATE_ENABLED else 2
        img = img.crop((ec, ec, original_width - ec, original_height - ec))
        img = img.resize((original_width, original_height), resample=Image.BICUBIC)

        # ---- 背景渐变偏移：边缘区域色温微变，不影响主体 ----
        if DEEP_ANTI_DUPLICATE_ENABLED:
            img_array = np.array(img)
            img_array = _apply_background_shift(img_array, strength=0.08)
            img = Image.fromarray(img_array)

        # ---- 像素域微调 ----
        img_array = np.array(img, dtype=np.int16)
        if DEEP_ANTI_DUPLICATE_ENABLED:
            sigma = random.uniform(*DEEP_NOISE_SIGMA_RANGE)
            img_array += _generate_gaussian_noise(img_array, sigma)
        elif ADVANCED_ANTI_DETECT_ENABLED:
            h, w = img_array.shape[:2]
            noise_amp = random.randint(*NOISE_AMP_RANGE)
            big_noise = np.random.randint(-noise_amp, noise_amp + 1, (h + 2, w + 2, 3), dtype=np.int16)
            correlated_noise = (
                big_noise[:-2, :-2] + big_noise[1:-1, :-2] + big_noise[2:, :-2] +
                big_noise[:-2, 1:-1] + big_noise[1:-1, 1:-1] + big_noise[2:, 1:-1] +
                big_noise[:-2, 2:] + big_noise[1:-1, 2:] + big_noise[2:, 2:]
            ) // 9
            img_array += correlated_noise
        else:
            for channel in range(3):
                img_array[:, :, channel] += random.randint(-1, 1)
        img_array = np.clip(img_array, 0, 255).astype(np.uint8)
        img = Image.fromarray(img_array)

        # 高斯模糊 + 锐化
        img = img.filter(ImageFilter.GaussianBlur(radius=random.uniform(0.2, 0.4)))
        img = ImageEnhance.Sharpness(img).enhance(1.0 + random.uniform(0.1, 0.2))

        # 亮度/对比度微调
        if ADVANCED_ANTI_DETECT_ENABLED or DEEP_ANTI_DUPLICATE_ENABLED:
            img_array = np.array(img, dtype=np.float32)
            h, w = img_array.shape[:2]
            angle = random.uniform(0, 2 * np.pi)
            spatial_str = DEEP_SPATIAL_BRIGHTNESS_STRENGTH if DEEP_ANTI_DUPLICATE_ENABLED else SPATIAL_BRIGHTNESS_STRENGTH
            bright_range = DEEP_BRIGHTNESS_ADJUST if DEEP_ANTI_DUPLICATE_ENABLED else BRIGHTNESS_ADJUST
            contrast_range = DEEP_CONTRAST_ADJUST if DEEP_ANTI_DUPLICATE_ENABLED else CONTRAST_ADJUST
            steepness = random.uniform(*spatial_str)
            y_coords, x_coords = np.mgrid[0:h, 0:w]
            projection = x_coords * np.cos(angle) + y_coords * np.sin(angle)
            gradient = 1.0 + steepness * (projection / max(h, w) - 0.5)
            bf = 1 + random.uniform(*bright_range) / 100
            cf = 1 + random.uniform(*contrast_range) / 100
            for c in range(3):
                img_array[:, :, c] = (img_array[:, :, c] - 128) * cf * gradient + 128 * bf
            img_array = np.clip(img_array, 0, 255).astype(np.uint8)
            img = Image.fromarray(img_array)
        else:
            bf = 1 + random.uniform(*BRIGHTNESS_ADJUST) / 100
            img = ImageEnhance.Brightness(img).enhance(bf)
            cf = 1 + random.uniform(*CONTRAST_ADJUST) / 100
            img = ImageEnhance.Contrast(img).enhance(cf)

        # ---- 色温偏置 + Gamma：模拟不同光线和曝光环境 ----
        if ADVANCED_ANTI_DETECT_ENABLED or DEEP_ANTI_DUPLICATE_ENABLED:
            img_array = np.array(img, dtype=np.float32)
            warmth_range = DEEP_WARMTH_RANGE if DEEP_ANTI_DUPLICATE_ENABLED else (-0.03, 0.03)
            gamma_range = DEEP_GAMMA_RANGE if DEEP_ANTI_DUPLICATE_ENABLED else (0.97, 1.03)
            warmth = random.uniform(*warmth_range)
            if warmth > 0:
                img_array[:, :, 0] *= 1 + warmth
                img_array[:, :, 2] *= 1 - warmth * 0.5
            else:
                img_array[:, :, 2] *= 1 + abs(warmth)
                img_array[:, :, 0] *= 1 - abs(warmth) * 0.5
            img_array = np.clip(img_array, 0, 255).astype(np.uint8)
            img = Image.fromarray(img_array)
            gamma = random.uniform(*gamma_range)
            if abs(gamma - 1.0) > 0.005:
                img_array = np.array(img, dtype=np.float32) / 255.0
                img_array = np.power(img_array, gamma) * 255.0
                img_array = np.clip(img_array, 0, 255).astype(np.uint8)
                img = Image.fromarray(img_array)

        # ---- 随机光影渐变：模拟不同方向/色温光源照射 ----
        if DEEP_ANTI_DUPLICATE_ENABLED:
            img_array = np.array(img)
            strength = random.uniform(0.01, 0.03)
            img_array = _apply_lighting_gradient(img_array, strength)
            img = Image.fromarray(img_array)

        # ---- 中频纹理叠加：频率感知+梯度自适应，对抗 CNN 特征匹配 ----
        if DEEP_ANTI_DUPLICATE_ENABLED:
            img_array = np.array(img)
            opacity = random.uniform(0.001, 0.003)
            img_array = _apply_texture_overlay(img_array, opacity)
            img = Image.fromarray(img_array)

        # LAB色域变换已移除：gamma转换累积误差导致严重banding/clipping

        # ---- 隐形水印 ----
        if WATERMARK_ENABLED:
            try:
                watermark = Image.new("RGBA", img.size, (255, 255, 255, 0))
                draw = ImageDraw.Draw(watermark)
                font_size = max(int(original_width / 20), 12)
                try:
                    font = ImageFont.truetype("arial.ttf", font_size)
                except Exception:
                    font = ImageFont.load_default()
                cx = (original_width - font_size * len(WATERMARK_TEXT)) // 2
                cy = (original_height - font_size) // 2
                rx = original_width - font_size * len(WATERMARK_TEXT) - 10
                by = original_height - font_size - 10
                if WATERMARK_POSITION == "随机":
                    pos_x = random.choice([10, cx, rx])
                    pos_y = random.choice([10, cy, by])
                elif WATERMARK_POSITION == "左上":
                    pos_x = 10; pos_y = 10
                elif WATERMARK_POSITION == "中上":
                    pos_x = cx; pos_y = 10
                elif WATERMARK_POSITION == "右上":
                    pos_x = rx; pos_y = 10
                elif WATERMARK_POSITION == "左中":
                    pos_x = 10; pos_y = cy
                elif WATERMARK_POSITION == "居中":
                    pos_x = cx; pos_y = cy
                elif WATERMARK_POSITION == "右中":
                    pos_x = rx; pos_y = cy
                elif WATERMARK_POSITION == "左下":
                    pos_x = 10; pos_y = by
                elif WATERMARK_POSITION == "中下":
                    pos_x = cx; pos_y = by
                elif WATERMARK_POSITION == "右下":
                    pos_x = rx; pos_y = by
                else:
                    pos_x = 10; pos_y = 10
                draw.text((pos_x, pos_y), WATERMARK_TEXT, font=font,
                          fill=(255, 255, 255, WATERMARK_OPACITY))
                img = Image.alpha_composite(img.convert("RGBA"), watermark).convert("RGB")
            except Exception as e:
                write_log(f"⚠️ 水印添加跳过：{e}", "warning")

        # ---- EXIF 地理信息（本地防重跳过） ----
        exif_bytes = b""
        if not skip_gps:
            try:
                # 会话级 EXIF：同批次共享设备、曝光参数，时间递增
                if SESSION_EXIF:
                    make, model, software, dev_model, exposure, fnum, iso, lens = SESSION_EXIF
                else:
                    models = list(DEVICE_INFO_MAP.keys())
                    dev_model = random.choice(models)
                    make, model, software = DEVICE_INFO_MAP[dev_model]
                    exposure = (random.randint(1, 200), 1000)
                    fnum = (random.randint(16, 28), 10)
                    iso = random.randint(50, 1600)
                    lens = f"f/{random.uniform(1.8, 5.6):.1f} {random.randint(12, 200)}mm"
                if SESSION_DT_BASE:
                    SESSION_DT_BASE += timedelta(minutes=random.randint(1, 5))
                    dt = SESSION_DT_BASE.strftime("%Y:%m:%d %H:%M:%S")
                else:
                    dt = datetime.now().strftime("%Y:%m:%d %H:%M:%S")

                exif_dict = {"0th": {}, "Exif": {}, "GPS": {}}
                exif_dict["0th"] = {
                    piexif.ImageIFD.Make: make,
                    piexif.ImageIFD.Model: model,
                    piexif.ImageIFD.Software: software,
                    piexif.ImageIFD.DateTime: dt,
                    piexif.ImageIFD.Orientation: 1,
                }
                exif_dict["Exif"] = {
                    piexif.ExifIFD.ExposureTime: exposure,
                    piexif.ExifIFD.FNumber: fnum,
                    piexif.ExifIFD.ISOSpeedRatings: iso,
                    piexif.ExifIFD.DateTimeOriginal: dt,
                    piexif.ExifIFD.LensModel: lens,
                }

                final_lat, final_lon, final_city = None, None, None
                if SESSION_GPS:
                    # 同一会话共享 GPS，加微小抖动模拟同地点多次拍摄
                    base_lat, base_lon, city_name = SESSION_GPS
                    final_lat = base_lat + random.uniform(-0.001, 0.001)
                    final_lon = base_lon + random.uniform(-0.001, 0.001)
                    final_city = city_name
                elif SELECTED_CITY == "全国随机":
                    country = SELECTED_COUNTRY
                    if country not in GEO_DATA:
                        country = "法国"
                    city_dict = GEO_DATA[country]
                    lats = [lat for lat, lon in city_dict.values()]
                    lons = [lon for lat, lon in city_dict.values()]
                    final_lat = random.uniform(min(lats), max(lats))
                    final_lon = random.uniform(min(lons), max(lons))
                    final_city = random.choice(list(city_dict.keys()))
                elif SELECTED_GPS_MODE == "random":
                    city_name, base_lat, base_lon = SELECTED_GPS_DATA
                    final_lat = base_lat + random.uniform(-0.05, 0.05)
                    final_lon = base_lon + random.uniform(-0.05, 0.05)
                    final_city = city_name
                elif SELECTED_GPS_MODE == "fixed":
                    city_name, base_lat, base_lon = SELECTED_GPS_DATA
                    final_lat = base_lat + random.uniform(-0.01, 0.01)
                    final_lon = base_lon + random.uniform(-0.01, 0.01)
                    final_city = city_name

                if final_lat is not None and final_lon is not None:
                    lat_dms = decimal_to_dms(final_lat)
                    exif_dict["GPS"][piexif.GPSIFD.GPSLatitudeRef] = 'N' if final_lat >= 0 else 'S'
                    exif_dict["GPS"][piexif.GPSIFD.GPSLatitude] = lat_dms
                    lon_dms = decimal_to_dms(final_lon)
                    exif_dict["GPS"][piexif.GPSIFD.GPSLongitudeRef] = 'E' if final_lon >= 0 else 'W'
                    exif_dict["GPS"][piexif.GPSIFD.GPSLongitude] = lon_dms
                    loc = f"Shooting Location: {SELECTED_COUNTRY} {final_city}".encode("utf-8")
                    exif_dict["Exif"][piexif.ExifIFD.UserComment] = b"ASCII\x00\x00\x00" + loc
                    write_log(f"📍 已写入地理信息：{SELECTED_COUNTRY} {final_city} | {final_lat:.6f}, {final_lon:.6f}")

            except Exception as e:
                write_log(f"EXIF地理信息写入异常: {e}", "warning")

        # 机模画幅匹配：轻量裁切 + 阈值保护
        if DEVICE_CROP_ENABLED:
            device = SELECTED_DEVICE if SELECTED_DEVICE != "随机" else model
            ratio = _get_device_ratio(device)
            if ratio:
                tw, th = ratio
                ow, oh = img.size
                # 如果图片是竖版而目标是横版（或反之），自动翻转目标比例匹配图片方向
                if (ow > oh) != (tw > th):
                    tw, th = th, tw
                cur_ratio = ow / oh
                target_ratio = tw / th
                diff_pct = abs(cur_ratio - target_ratio) / target_ratio
                # 差不到 3% 跳过，最多裁 5%
                if diff_pct >= 0.03:
                    crop_max = int(min(ow, oh) * 0.05)
                    if ow / oh > target_ratio:
                        # 图片太宽：裁左右各一半
                        target_w = int(oh * target_ratio)
                        trim = min(ow - target_w, crop_max * 2)
                        if trim > 0:
                            trim //= 2
                            img = img.crop((trim, 0, ow - trim, oh))
                    else:
                        # 图片太高：裁上下各一半
                        target_h = int(ow / target_ratio)
                        trim = min(oh - target_h, crop_max * 2)
                        if trim > 0:
                            trim //= 2
                            img = img.crop((0, trim, ow, oh - trim))

        # 自定义裁剪：按用户设定的四边百分比裁切
        if CUSTOM_CROP_ENABLED:
            img = _custom_crop_pct(img, CROP_TOP_PCT, CROP_BOTTOM_PCT, CROP_LEFT_PCT, CROP_RIGHT_PCT)

        # EXIF 缩略图 + dump（置於機模裁切之後，確保縮略圖與主圖一致）
        exif_bytes = b""
        if not skip_gps:
            try:
                if ADVANCED_ANTI_DETECT_ENABLED:
                    try:
                        thumb = img.copy()
                        thumb.thumbnail((160, 120))
                        thumb_buf = io.BytesIO()
                        thumb.save(thumb_buf, format="JPEG", quality=60)
                        exif_dict["thumbnail"] = thumb_buf.getvalue()
                        exif_dict["0th"][piexif.ImageIFD.XPComment] = \
                            random.choice(["Edited with Snapseed", "VSCO", "Lightroom CC", "Photos", ""]).encode('utf-16-le')
                    except Exception as e:
                        pass
                exif_bytes = piexif.dump(exif_dict)
            except Exception as e:
                write_log(f"EXIF dump异常: {e}", "warning")

        # PNG 中间格式：破坏 JPEG 双重压缩痕迹
        if ADVANCED_ANTI_DETECT_ENABLED or DEEP_ANTI_DUPLICATE_ENABLED:
            try:
                png_buf = io.BytesIO()
                img.save(png_buf, format="PNG")
                png_buf.seek(0)
                img.close()
                img = Image.open(png_buf)
            except Exception as e:
                write_log(f"PNG中间转换跳过: {e}", "warning")

        # JPEG 保存策略（会话级一致性）
        if SESSION_JPEG:
            save_quality, subsampling = SESSION_JPEG
        elif LOSSLESS_ENABLED:
            save_quality = 100
            subsampling = "4:4:4"
        elif COMPRESS_ENABLED:
            save_quality = random.randint(*COMPRESS_QUALITY_RANGE)
            subsampling = random.choice(SUBSAMPLING_OPTIONS)
        elif DEEP_ANTI_DUPLICATE_ENABLED:
            save_quality = random.randint(*DEEP_JPEG_QUALITY_RANGE)
            subsampling = random.choice(SUBSAMPLING_OPTIONS)
        else:
            save_quality = random.randint(*JPEG_QUALITY_RANGE)
            subsampling = random.choice(SUBSAMPLING_OPTIONS)

        temp_path = image_path + "_processed.jpg"
        save_kwargs = {"format": "JPEG", "quality": save_quality, "subsampling": subsampling, "optimize": True}
        if exif_bytes:
            save_kwargs["exif"] = exif_bytes
        img.save(temp_path, **save_kwargs)
        img.close()
        img = None

        # MD5 修改
        with open(temp_path, "ab") as f:
            f.write(random.randbytes(random.randint(*APPEND_BYTES)))

        # 深度模式：在重命名前计算与原图的指纹差异度
        _score = None
        if DEEP_ANTI_DUPLICATE_ENABLED:
            _orig = _out = None
            try:
                _orig = Image.open(image_path)
                _out = Image.open(temp_path)
                _os = np.array(_orig.resize((32, 32), Image.BICUBIC)).astype(np.float32)
                _ds = np.array(_out.resize((32, 32), Image.BICUBIC)).astype(np.float32)
                _score = int(np.abs(_os - _ds).mean() * 100 / 255)
            except Exception:
                pass
            finally:
                if _orig: _orig.close()
                if _out: _out.close()

        orig_base = os.path.splitext(os.path.basename(image_path))[0]
        rand6 = ''.join(random.choices(string.ascii_letters + string.digits, k=6))
        new_filename = f"{orig_base}_d{_score}_{rand6}.jpg" if _score is not None else f"{orig_base}_{rand6}.jpg"
        new_path = os.path.join(os.path.dirname(image_path), new_filename)
        os.replace(temp_path, new_path)
        try:
            os.remove(image_path)
        except OSError:
            pass

        file_size = round(os.path.getsize(new_path) / 1024, 2)
        if _score is not None:
            write_log(f"✅ 深度处理完成 | {new_filename} | 差异度 {_score} | {file_size}KB | Q={save_quality}", "success")
        else:
            with open(new_path, "rb") as f:
                new_md5 = hashlib.md5(f.read()).hexdigest()
            write_log(f"✅ 防重处理成功 | {new_filename} | {file_size}KB | Q={save_quality} SS={subsampling} | MD5={new_md5[:12]}...", "success")
        global TOTAL_IMAGES
        with _images_lock:
            TOTAL_IMAGES += 1
        return True
    except Exception as e:
        write_log(f"❌ 图片处理失败 | 路径：{image_path} | 错误：{e}", "error")
        if img:
            try:
                img.close()
            except Exception:
                pass
        return False


def _ensure_chrome():
    """确保 Chrome + ChromeDriver 可用，返回 (chrome_path, chromedriver_path)"""
    import zipfile, io as _io

    chrome_dir = os.path.join(os.environ.get("LOCALAPPDATA", os.path.expanduser("~")), "ImageMAX", "chrome")
    chrome_exe = os.path.join(chrome_dir, "chrome.exe")
    driver_exe = os.path.join(chrome_dir, "chromedriver.exe")

    # 两者都已缓存 → 直接返回
    if os.path.exists(chrome_exe) and os.path.exists(driver_exe):
        return chrome_exe, driver_exe

    write_log("首次使用需下载运行环境（约 180MB，仅此一次）...", "info")
    if _on_status:
        _on_status("首次使用，正在准备运行环境...")
    try:
        os.makedirs(chrome_dir, exist_ok=True)

        # 获取 Chrome + ChromeDriver 下载地址（同版本，保证匹配）
        api = "https://googlechromelabs.github.io/chrome-for-testing/last-known-good-versions-with-downloads.json"
        resp = requests.get(api, headers={"User-Agent": "Mozilla/5.0"}, timeout=30)
        data = resp.json()
        channel = data.get("channels", {}).get("Stable", {})
        chrome_url = driver_url = None
        for c in channel.get("downloads", {}).get("chrome", []):
            if c["platform"] == "win64":
                chrome_url = c["url"]
                break
        for d in channel.get("downloads", {}).get("chromedriver", []):
            if d["platform"] == "win64":
                driver_url = d["url"]
                break
        if not chrome_url or not driver_url:
            raise Exception("无法获取下载地址")

        # 下载 Chrome
        if not os.path.exists(chrome_exe):
            _download_and_extract(chrome_url, chrome_dir, "Chrome")
        # 下载 ChromeDriver
        if not os.path.exists(driver_exe):
            _download_and_extract(driver_url, chrome_dir, "ChromeDriver")

        # 解压后 chromedriver 可能在子目录，移动到根
        for root, dirs, files in os.walk(chrome_dir):
            for f in files:
                if f == "chromedriver.exe" and os.path.join(root, f) != driver_exe:
                    import shutil
                    shutil.move(os.path.join(root, f), driver_exe)
                    break

        if os.path.exists(chrome_exe) and os.path.exists(driver_exe):
            write_log("运行环境就绪", "success")
            return chrome_exe, driver_exe
        raise Exception("环境文件缺失")
    except Exception as e:
        write_log(f"环境准备失败: {e}", "error")
        raise Exception("运行环境准备失败，请检查网络连接")


def _download_and_extract(url, target_dir, label):
    """下载 ZIP 并解压到目标目录"""
    import zipfile
    zip_path = os.path.join(target_dir, f"_{label}.zip")
    r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, stream=True, timeout=600)
    total = int(r.headers.get("Content-Length", 0))
    downloaded = 0
    with open(zip_path, "wb") as f:
        for chunk in r.iter_content(chunk_size=65536):
            f.write(chunk)
            downloaded += len(chunk)
            if total > 0 and _on_status:
                pct = min(downloaded * 100 // total, 100)
                if pct % 20 == 0:
                    _on_status(f"下载{label} {pct}%")
    with zipfile.ZipFile(zip_path) as z:
        root = z.namelist()[0].split("/")[0]
        for name in z.namelist():
            if name.endswith("/"):
                continue
            dest = os.path.join(target_dir, name[len(root)+1:])
            os.makedirs(os.path.dirname(dest), exist_ok=True)
            with z.open(name) as src, open(dest, "wb") as dst:
                dst.write(src.read())
    os.remove(zip_path)


def init_chrome(debug_mode):
    if _on_status:
        _on_status("正在启动浏览器")

    # 自管理 Chrome + ChromeDriver（同版本，永不冲突）
    chrome_binary, driver_path = _ensure_chrome()
    service = Service(executable_path=driver_path)

    options = webdriver.ChromeOptions()
    options.binary_location = chrome_binary
    if not debug_mode:
        options.add_argument("--headless=new")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--start-maximized")
    options.add_argument("--disable-notifications")
    options.add_argument("--disable-popup-blocking")
    options.add_argument("--disable-logging")
    options.add_argument("--log-level=3")
    options.add_experimental_option("excludeSwitches", ["enable-automation", "enable-logging"])
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_experimental_option("useAutomationExtension", False)
    options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")
    if PROXY.strip():
        options.add_argument(f"--proxy-server={PROXY}")
        write_log(f"✅ 已加载代理：{PROXY.split('@')[-1]}", "success")
    driver = webdriver.Chrome(service=service, options=options)
    driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
    driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
        "source": """
            Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
            window.navigator.chrome = { runtime: {} };
            Object.defineProperty(navigator, 'plugins', {get: () => [1, 2, 3, 4, 5]});
            Object.defineProperty(navigator, 'languages', {get: () => ['fr-FR', 'fr', 'en-GB', 'en']});
        """
    })
    driver.maximize_window()
    return driver


def close_all_popups(driver, wait):
    write_log("正在关闭弹窗...")
    # 用 WebDriverWait 代替固定 sleep，弹窗出现即处理
    close_js = """
        var btns = document.querySelectorAll(
            'button[aria-label="Close"], [data-testid="modal-close-button"], .web_ui__Modal__close, [class*="close"]'
        );
        btns.forEach(function(b) { if(b) b.click(); });
        var cookie = document.querySelector(
            'button[id*="onetrust-accept"], [class*="accept-btn"]'
        );
        if(cookie) { cookie.click(); }
        var masks = document.querySelectorAll(
            '.web_ui__Overlay, .web_ui__Dialog, [data-testid*="modal"], [class*="Modal"], [class*="Overlay"]'
        );
        masks.forEach(function(m) { if(m) m.remove(); });
        document.body.style.overflow = 'auto';
        document.documentElement.style.overflow = 'auto';
        return document.querySelectorAll(
            'button[aria-label="Close"], [data-testid="modal-close-button"], .web_ui__Overlay'
        ).length;
    """
    try:
        # 最多等 3 秒让弹窗出现，然后一次性全关
        driver.execute_script("return document.readyState === 'complete' || true")
        sleep(1.5)  # 给页面一点时间渲染弹窗
        remaining = driver.execute_script(close_js)
        write_log(f"✅ 弹窗已处理（残余: {remaining}）", "success")
    except Exception as e:
        write_log(f"弹窗处理跳过：{e}", "warning")


def _download_single_image(args):
    """单张图片下载 + 处理（供 ThreadPoolExecutor 并发调用）"""
    img_url, save_folder, download_headers, proxies, img_idx = args
    if not _verify_license_quick():
        return False
    try:
        session = requests.Session()
        if proxies:
            session.proxies.update(proxies)
        for retry in range(3):
            if STOP_TASK:
                session.close()
                return False
            try:
                if retry > 0:
                    delay = retry * 2 + random.uniform(0, 1)
                    sleep(delay)
                res = session.get(img_url, headers=download_headers, timeout=(10, 60))
                if res.status_code == 200 and len(res.content) > 1024 * 5:
                    if ".webp" in img_url:
                        ext = "webp"
                    elif ".jpg" in img_url or ".jpeg" in img_url:
                        ext = "jpg"
                    elif ".png" in img_url:
                        ext = "png"
                    else:
                        ext = "jpg"
                    temp_path = os.path.join(save_folder, f"temp_{img_idx + 1}.{ext}")
                    with open(temp_path, "wb") as f:
                        f.write(res.content)
                    write_log(f"第{img_idx + 1}张下载成功 | {round(len(res.content)/1024, 2)}KB", "success")
                    # 深度模式多版本：复制变体副本再分别处理
                    variants = DEEP_MODE_VARIANTS if DEEP_ANTI_DUPLICATE_ENABLED else 1
                    if variants > 1:
                        result = True
                        for v in range(2, variants + 1):
                            v_path = os.path.join(save_folder, f"temp_{img_idx + 1}_v{v}.{ext}")
                            shutil.copy2(temp_path, v_path)
                            if not process_image(v_path):
                                result = False
                        if not process_image(temp_path):
                            result = False
                    else:
                        result = process_image(temp_path)
                    session.close()
                    return result
                else:
                    write_log(f"第{retry + 1}次重试 | 状态码：{res.status_code}", "warning")
            except Exception as e:
                write_log(f"第{retry + 1}次下载失败 | {e}", "error")
                sleep(1)
        session.close()
        write_log(f"❌ 第{img_idx + 1}张最终下载失败", "error")
        return False
    except Exception:
        return False
    finally:
        session.close()


def scrape_vinted_by_browser(url, save_folder, debug_mode, driver=None, wait_time=0):
    global STOP_TASK, FAIL_COUNT, FAILED_URLS
    if _on_status:
        _on_status("正在抓取商品图片")
    if STOP_TASK:
        return False

    own_driver = False
    try:
        write_log(f"======================")
        write_log(f"开始抓取商品：{url}")
        if STOP_TASK:
            write_log("❌ 任务已停止", "warning")
            return False

        # 复用或创建 driver
        if driver is None:
            driver = init_chrome(debug_mode)
            own_driver = True
        wait = WebDriverWait(driver, 15)

        # 页面级重试：driver.get(url) → sleep → 检查 body 文本 → 等容器
        item_photo_container = None
        for page_retry in range(3):
            driver.get(url)
            sleep(2)  # 给页面渲染时间

            # 快速检测已知错误文本（不依赖元素等待）
            try:
                body = driver.execute_script(
                    "return (document.body?.innerText || '').substring(0, 200)"
                ).lower()
            except Exception:
                body = ""
            if "we're experiencing some technical issues" in body:
                write_log(f"⚠️ Server Error，立即重试（第{page_retry+1}/3次）", "warning")
                sleep(1)
                continue

            # 页面正常 → 等 item-photos 容器（单次 5s 超时，不逐个 xpath 等）
            try:
                item_photo_container = WebDriverWait(driver, 8).until(
                    EC.presence_of_element_located((
                        By.XPATH,
                        "//div[@data-testid='item-photos']"
                        "|//div[contains(@class,'item-photos')]"
                        "|//div[contains(@class,'photos')]//ancestor::div[contains(@class,'item')]"
                        "|//div[contains(@class,'carousel')]//ancestor::div[contains(@class,'item-photo')]"
                    ))
                )
                break
            except Exception:
                write_log(f"⚠️ 第{page_retry+1}次未找到商品容器", "warning")
                sleep(1)

        if not item_photo_container:
            write_log("❌ 3次重试后仍无法加载商品页面", "error")
            FAILED_URLS.append(url)
            FAIL_REASONS[url] = "页面加载失败（3次重试）"
            if own_driver:
                driver.quit()
            return False

        # 获取 Cookie
        cookies = driver.get_cookies()
        page_cookie = "; ".join([f"{c['name']}={c['value']}" for c in cookies])
        write_log("✅ 已获取页面 Cookie", "success")

        # ---- 逐个点击缩略图，触发全部图片加载 ----
        img_urls = []
        seen_photoids = set()
        for _round in range(15):
            btns = driver.find_elements(By.CSS_SELECTOR,
                'button.item-thumbnail[data-photoid],'
                'button[data-testid*="thumb"],'
                'div[class*="thumb"] button'
            )
            clicked = False
            for btn in btns:
                try:
                    pid = btn.get_attribute('data-photoid') or ''
                    if pid and pid in seen_photoids:
                        continue
                    driver.execute_script("arguments[0].click();", btn)
                    if pid:
                        seen_photoids.add(pid)
                    clicked = True
                    sleep(1)
                    break
                except Exception:
                    continue
            if not clicked:
                break

        # 从 DOM 提取所有已加载的 f800 大图
        dom_urls = driver.execute_script("""
            var imgs = document.querySelectorAll('img');
            var out = [];
            imgs.forEach(function(img) {
                var s = img.src || img.getAttribute('data-src') || '';
                if (s.indexOf('images1.vinted.net') !== -1 && s.indexOf('/f800/') !== -1) {
                    if (out.indexOf(s) === -1) out.push(s);
                }
            });
            return out;
        """)
        img_urls = list(dict.fromkeys(dom_urls or []))

        # 并发探测更高分辨率（f2000 或原图）
        if img_urls:
            import re as _re
            from concurrent.futures import ThreadPoolExecutor, as_completed

            def _probe_upgrade(u):
                if not _re.search(r'/f\d+/', u):
                    return u
                best = u
                for cand in [_re.sub(r'/f\d+/', '/f2000/', u), _re.sub(r'/f\d+/', '/', u)]:
                    if cand == u: continue
                    try:
                        if requests.head(cand, headers={
                            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                            "Referer": url, "Cookie": page_cookie,
                        }, timeout=3).status_code == 200:
                            best = cand; break
                    except Exception: pass
                return best

            upgraded = []
            with ThreadPoolExecutor(max_workers=DOWNLOAD_WORKERS) as ex:
                futures = {ex.submit(_probe_upgrade, u): i for i, u in enumerate(img_urls)}
                results = [None] * len(img_urls)
                for f in as_completed(futures):
                    results[futures[f]] = f.result()
                upgraded = results
            new_count = sum(1 for a, b in zip(img_urls, upgraded) if a != b)
            if new_count:
                write_log(f"📐 分辨率升级: {new_count} 张已升级", "success")
            img_urls = upgraded

        write_log(f"🖼️ 已加载 {len(seen_photoids)} 个缩略图，收集到 {len(img_urls)} 张大图", "info")

        if not img_urls:
            write_log("❌ 未提取到商品高清主图", "error")
            FAILED_URLS.append(url)
            FAIL_REASONS[url] = "未提取到商品图片"
            if own_driver:
                driver.quit()
            return False

        write_log(f"✅ 提取到 {len(img_urls)} 张有效高清原图", "success")

        # ---- 并发下载 ----
        download_headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Referer": url, "Cookie": page_cookie,
            "Accept": "image/avif,image/webp,image/apng,image/jpeg,image/*,*/*;q=0.8",
        }
        proxies = {"http": PROXY, "https": PROXY} if PROXY.strip() else None
        from concurrent.futures import ThreadPoolExecutor, as_completed

        tasks = [(u, save_folder, download_headers, proxies, i) for i, u in enumerate(img_urls)]
        success_count = 0
        with ThreadPoolExecutor(max_workers=DOWNLOAD_WORKERS) as executor:
            futures = {executor.submit(_download_single_image, t): t for t in tasks}
            for future in as_completed(futures):
                if future.result():
                    success_count += 1

        write_log(f"✅ 商品处理完成 | 总图：{len(img_urls)} | 成功：{success_count}", "success")
        return True

    except Exception as e:
        write_log(f"❌ 商品抓取失败 | {url} | {e}", "error")
        FAILED_URLS.append(url)
        FAIL_REASONS[url] = str(e)[:80]
        return False
    finally:
        if driver and own_driver:
            try:
                driver.quit()
            except Exception:
                pass


def _cleanup_old_logs(save_root, days=3):
    """清理超过指定天数的 Process_Log 文件"""
    import time as _t
    try:
        now = _t.time()
        cutoff = now - days * 86400
        for f in os.listdir(save_root):
            if f.startswith("Process_Log") and f.endswith(".txt"):
                fp = os.path.join(save_root, f)
                if os.path.getmtime(fp) < cutoff:
                    os.remove(fp)
    except Exception:
        pass


def _download_batch(img_urls, save_folder, download_headers, session=None):
    """并发下载图片批次，返回 (ok, fail)。session 不为 None 时使用共享 session"""
    from concurrent.futures import ThreadPoolExecutor, as_completed
    results = []
    worker_f = _download_depop_image if session is not None else _download_single_image
    arg_template = (session,) if session is not None else ({},)
    download_args = [(u, save_folder, download_headers, *arg_template, i)
                     for i, u in enumerate(img_urls)]
    with ThreadPoolExecutor(max_workers=min(DOWNLOAD_WORKERS, len(img_urls))) as executor:
        futures = {executor.submit(worker_f, arg): arg for arg in download_args}
        for future in as_completed(futures):
            results.append(future.result())
    ok = sum(1 for r in results if r)
    return ok, len(img_urls) - ok


def _download_depop_image(args):
    """下载单张图片（每次创建独立 session，线程安全）"""
    img_url, save_folder, download_headers, cookies, img_idx = args
    if not _verify_license_quick():
        return False
    session = requests.Session()
    for c in (cookies or []):
        session.cookies.set(c['name'], c['value'], domain=c.get('domain', ''))
    try:
        for retry in range(3):
            if STOP_TASK:
                return False
            try:
                if retry > 0:
                    sleep(retry * 2 + random.uniform(0, 1))
                res = session.get(img_url, headers=download_headers, timeout=(10, 60))
                if res.status_code == 200 and len(res.content) > 1024:
                    ext = "webp" if ".webp" in img_url else "png" if ".png" in img_url else "jpg"
                    temp_path = os.path.join(save_folder, f"temp_{img_idx + 1}.{ext}")
                    with open(temp_path, "wb") as f:
                        f.write(res.content)
                    write_log(f"第{img_idx + 1}张下载成功 | {round(len(res.content)/1024, 2)}KB", "success")
                    # 深度模式多版本
                    variants = DEEP_MODE_VARIANTS if DEEP_ANTI_DUPLICATE_ENABLED else 1
                    if variants > 1:
                        result = True
                        for v in range(2, variants + 1):
                            v_path = os.path.join(save_folder, f"temp_{img_idx + 1}_v{v}.{ext}")
                            shutil.copy2(temp_path, v_path)
                            if not process_image(v_path):
                                result = False
                        if not process_image(temp_path):
                            result = False
                    else:
                        result = process_image(temp_path)
                    return result
                else:
                    write_log(f"第{img_idx + 1}张第{retry + 1}次重试 | 状态码：{res.status_code}", "warning")
            except Exception as e:
                write_log(f"第{img_idx + 1}张第{retry + 1}次下载失败 | {e}", "error")
                sleep(1)
        write_log(f"❌ 第{img_idx + 1}张最终下载失败", "error")
        return False
    except Exception:
        return False
    finally:
        session.close()


def scrape_depop_by_browser(url, save_folder, debug_mode, driver=None):
    """Depop 商品图片采集"""
    global STOP_TASK, FAIL_COUNT, FAILED_URLS
    if _on_status:
        _on_status("正在抓取 Depop 商品图片")
    if STOP_TASK:
        return False

    own_driver = False
    try:
        write_log(f"======================")
        write_log(f"开始抓取 Depop 商品：{url}")
        if STOP_TASK:
            return False

        if driver is None:
            driver = init_chrome(debug_mode)
            own_driver = True
        wait = WebDriverWait(driver, 15)

        # 页面加载 + 重试
        for page_retry in range(3):
            driver.get(url)
            sleep(3)
            try:
                body = driver.execute_script(
                    "return (document.body?.innerText || '').substring(0, 300)"
                ).lower()
            except Exception:
                body = ""
            # Depop 错误页检测
            if "something went wrong" in body or "page not found" in body:
                write_log(f"⚠️ Depop 页面异常，重试（第{page_retry+1}/3次）", "warning")
                sleep(2)
                continue
            # 等商品图片加载
            try:
                WebDriverWait(driver, 8).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR,
                        "img[src*='media-photos.depop.com']"))
                )
                break
            except Exception:
                write_log(f"⚠️ 第{page_retry+1}次未找到图片容器", "warning")
                sleep(1)

        # 滚动加载所有图片
        last_height = driver.execute_script("return document.body.scrollHeight")
        for _ in range(10):
            driver.execute_script("window.scrollBy(0, 600)")
            sleep(0.8)
            new_height = driver.execute_script("return document.body.scrollHeight")
            if new_height == last_height:
                break
            last_height = new_height

        # 获取 Cookie（用于后续 download session）
        cookies = driver.get_cookies()

        # 提取商品图片 — 限第一个轮播容器（商品主图），排除推荐
        import re as _re
        dom_urls = driver.execute_script("""
            var out = [];
            // 只取第一个 carousel 容器内的图片
            var carousel = document.querySelector('[class*="carouselContainer"], [class*="carousel__"]');
            if (carousel) {
                var imgs = carousel.querySelectorAll('img');
            } else {
                var imgs = document.querySelectorAll('img');
            }
            imgs.forEach(function(img) {
                var s = img.src || '';
                if (s.indexOf('media-photos.depop.com') !== -1 && out.indexOf(s) === -1) out.push(s);
            });
            return out;
        """)
        img_urls = list(dict.fromkeys(dom_urls or []))

        if not img_urls:
            write_log("❌ 未提取到 Depop 商品图片", "error")
            FAILED_URLS.append(url)
            FAIL_REASONS[url] = "未提取到商品图片"
            if own_driver:
                driver.quit()
            return False

        # 图片 ID 去重 + 升级 P10
        seen = set()
        final_urls = []
        for u in img_urls:
            m = _re.search(r'/(\d{9,11})_', u)
            pid = m.group(1) if m else u
            if pid not in seen:
                seen.add(pid)
                final_urls.append(_re.sub(r'/P\d+\.', '/P10.', u) if '/P' in u.split('/')[-1] else u)
        img_urls = final_urls
        write_log(f"✅ 提取到 {len(img_urls)} 张 Depop 商品图片", "success")

        # 用 requests 下载（每线程独立 session，线程安全）
        download_headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Referer": url,
            "Accept": "image/avif,image/webp,image/apng,image/*,*/*;q=0.8",
            "Accept-Language": "en-GB,en;q=0.9",
        }
        from concurrent.futures import ThreadPoolExecutor, as_completed
        results = []
        download_args = [(u, save_folder, download_headers, cookies, i)
                         for i, u in enumerate(img_urls)]
        with ThreadPoolExecutor(max_workers=min(DOWNLOAD_WORKERS, len(img_urls))) as executor:
            futures = {executor.submit(_download_depop_image, arg): arg
                       for arg in download_args}
            for future in as_completed(futures):
                results.append(future.result())

        ok = sum(1 for r in results if r)
        fail = len(results) - ok
        if fail > 0:
            write_log(f"❌ {fail} 张图片下载失败", "error")
        write_log(f"✅ Depop 商品处理完成：成功 {ok}/{len(img_urls)} 张", "success")
        return ok > 0

    except Exception as e:
        write_log(f"❌ Depop 抓取异常：{e}", "error")
        FAILED_URLS.append(url)
        FAIL_REASONS[url] = str(e)[:100]
        return False
    finally:
        if own_driver and driver:
            try:
                driver.quit()
            except Exception:
                pass


def scrape_vc_by_browser(url, save_folder, debug_mode, driver=None):
    """Vestiaire Collective 商品图片采集"""
    global STOP_TASK, FAIL_COUNT, FAILED_URLS
    if _on_status:
        _on_status("正在抓取 VC 商品图片")
    if STOP_TASK:
        return False

    own_driver = False
    try:
        write_log(f"======================")
        write_log(f"开始抓取 VC 商品：{url}")
        if STOP_TASK:
            return False

        if driver is None:
            driver = init_chrome(debug_mode)
            own_driver = True

        # 页面加载 + 重试
        for page_retry in range(3):
            driver.get(url)
            sleep(3)
            if "Sorry" not in driver.title and "error" not in driver.title.lower():
                break
            write_log(f"⚠️ VC 页面异常，重试（第{page_retry+1}/3次）", "warning")
            sleep(2)

        # 提取产品图片 — images.vestiairecollective.com + /produit/
        import re as _re
        dom_urls = driver.execute_script("""
            var out = [];
            var imgs = document.querySelectorAll('img');
            imgs.forEach(function(img) {
                var s = img.src || '';
                if (s.indexOf('images.vestiairecollective.com') !== -1 && s.indexOf('/produit/') !== -1) {
                    if (out.indexOf(s) === -1) out.push(s);
                }
            });
            return out;
        """)
        img_urls = list(dict.fromkeys(dom_urls or []))

        if not img_urls:
            write_log("❌ 未提取到 VC 商品图片", "error")
            FAILED_URLS.append(url)
            if own_driver:
                driver.quit()
            return False

        # 去重（同图号不同分辨率） + 升级到原图
        seen_nums = set()
        final_urls = []
        for u in img_urls:
            m = _re.search(r'-(\d+)_\d+\.(jpg|jpeg|png|webp)', u)
            num = m.group(1) if m else u
            if num not in seen_nums:
                seen_nums.add(num)
                # 去掉 w=128 等缩略参数，用 w=4000 取原图
                upgraded = _re.sub(r'/images/resized/(?:w=\d+,)?(?:q=\d+,)?(?:f=\w+,)?/?',
                                   '/images/resized/w=4000,q=100,f=auto,/',
                                   u)
                # 如果升级后URL没变化，说明不在resized路径下，直接去参数
                if upgraded == u:
                    upgraded = _re.sub(r'(w|h|q)=\d+&?', '', u).rstrip('?&')
                final_urls.append(upgraded)
        img_urls = final_urls
        write_log(f"✅ 提取到 {len(img_urls)} 张 VC 商品图片", "success")

        # 直接下载（不需要 cookie，VC 图片公开）
        download_headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Referer": url,
            "Accept": "image/avif,image/webp,image/apng,image/*,*/*;q=0.8",
        }
        from concurrent.futures import ThreadPoolExecutor, as_completed
        results = []
        download_args = [(u, save_folder, download_headers, {}, i)
                         for i, u in enumerate(img_urls)]
        with ThreadPoolExecutor(max_workers=min(DOWNLOAD_WORKERS, len(img_urls))) as executor:
            futures = {executor.submit(_download_single_image, arg): arg
                       for arg in download_args}
            for future in as_completed(futures):
                results.append(future.result())

        ok = sum(1 for r in results if r)
        fail = len(results) - ok
        if fail > 0:
            write_log(f"❌ {fail} 张图片下载失败", "error")
        write_log(f"✅ VC 商品处理完成：成功 {ok}/{len(img_urls)} 张", "success")
        return ok > 0

    except Exception as e:
        write_log(f"❌ VC 抓取异常：{e}", "error")
        FAILED_URLS.append(url)
        return False
    finally:
        if own_driver and driver:
            try:
                driver.quit()
            except Exception:
                pass


def scrape_poshmark_by_browser(url, save_folder, debug_mode, driver=None):
    """Poshmark 商品图片采集"""
    global STOP_TASK, FAIL_COUNT, FAILED_URLS
    if _on_status:
        _on_status("正在抓取 Poshmark 商品图片")
    if STOP_TASK:
        return False

    own_driver = False
    try:
        write_log(f"======================")
        write_log(f"开始抓取 Poshmark 商品：{url}")
        if STOP_TASK:
            return False

        if driver is None:
            driver = init_chrome(debug_mode)
            own_driver = True

        for page_retry in range(3):
            driver.get(url)
            sleep(3)
            if "Poshmark" in driver.title:
                break
            write_log(f"⚠️ Poshmark 页面异常，重试（第{page_retry+1}/3次）", "warning")
            sleep(2)

        # 提取产品图片 — cloudfront.net + /posts/
        import re as _re
        dom_urls = driver.execute_script("""
            var out = [];
            var imgs = document.querySelectorAll('img');
            imgs.forEach(function(img) {
                var s = img.src || '';
                if (s.indexOf('cloudfront.net') !== -1 && s.indexOf('/posts/') !== -1) {
                    if (out.indexOf(s) === -1) out.push(s);
                }
            });
            return out;
        """)
        img_urls = list(dict.fromkeys(dom_urls or []))

        if not img_urls:
            write_log("❌ 未提取到 Poshmark 商品图片", "error")
            FAILED_URLS.append(url)
            if own_driver:
                driver.quit()
            return False

        # s_→l_ 升级大图，去重
        seen_ids = set()
        final_urls = []
        for u in img_urls:
            m = _re.search(r'/([sl])_([a-f0-9]{24})\.', u)
            if m:
                pid = m.group(2)
                if pid not in seen_ids:
                    seen_ids.add(pid)
                    final_urls.append(u.replace(f"/{m.group(1)}_", "/l_"))
            else:
                final_urls.append(u)
        img_urls = list(dict.fromkeys(final_urls))
        write_log(f"✅ 提取到 {len(img_urls)} 张 Poshmark 商品图片", "success")

        # 直接下载（CloudFront 不需要 auth）
        download_headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Referer": url,
            "Accept": "image/avif,image/webp,image/apng,image/*,*/*;q=0.8",
        }
        from concurrent.futures import ThreadPoolExecutor, as_completed
        results = []
        download_args = [(u, save_folder, download_headers, {}, i)
                         for i, u in enumerate(img_urls)]
        with ThreadPoolExecutor(max_workers=min(DOWNLOAD_WORKERS, len(img_urls))) as executor:
            futures = {executor.submit(_download_single_image, arg): arg
                       for arg in download_args}
            for future in as_completed(futures):
                results.append(future.result())

        ok = sum(1 for r in results if r)
        fail = len(results) - ok
        if fail > 0:
            write_log(f"❌ {fail} 张图片下载失败", "error")
        write_log(f"✅ Poshmark 商品处理完成：成功 {ok}/{len(img_urls)} 张", "success")
        return ok > 0

    except Exception as e:
        write_log(f"❌ Poshmark 抓取异常：{e}", "error")
        FAILED_URLS.append(url)
        return False
    finally:
        if own_driver and driver:
            try:
                driver.quit()
            except Exception:
                pass


def scrape_grailed_by_browser(url, save_folder, debug_mode, driver=None):
    """Grailed 商品图片采集"""
    global STOP_TASK, FAIL_COUNT, FAILED_URLS
    if _on_status:
        _on_status("正在抓取 Grailed 商品图片")
    if STOP_TASK:
        return False

    own_driver = False
    try:
        write_log(f"======================")
        write_log(f"开始抓取 Grailed 商品：{url}")
        if STOP_TASK:
            return False

        if driver is None:
            driver = init_chrome(debug_mode)
            own_driver = True

        for page_retry in range(3):
            driver.get(url)
            sleep(3)
            if "Grailed" in driver.title:
                break
            write_log(f"⚠️ Grailed 页面异常，重试（第{page_retry+1}/3次）", "warning")
            sleep(2)

        # 提取产品图片 — 只取商品主图区，排除推荐
        import re as _re
        dom_urls = driver.execute_script("""
            var out = [];
            // 限定商品主图区域
            var gallery = document.querySelector('[class*="PhotoGallery_"], [class*="photoGallery"]');
            if (!gallery) gallery = document.querySelector('[class*="LeftColumn_"] [class*="Photo_"]');
            var imgs = gallery ? gallery.querySelectorAll('img') : document.querySelectorAll('img');
            // 如果限定区图片太少，退回到全页
            if (imgs.length < 2) imgs = document.querySelectorAll('img');
            imgs.forEach(function(img) {
                var s = img.src || '';
                if (s.indexOf('media-assets.grailed.com') !== -1 && s.indexOf('/listing/') !== -1) {
                    if (out.indexOf(s) === -1) out.push(s);
                }
            });
            return out;
        """)
        img_urls = list(dict.fromkeys(dom_urls or []))

        if not img_urls:
            write_log("❌ 未提取到 Grailed 商品图片", "error")
            FAILED_URLS.append(url)
            if own_driver:
                driver.quit()
            return False

        # 去重：URL末尾hash之前的路径
        seen = set()
        final_urls = []
        for u in img_urls:
            m = _re.search(r'/temp/([a-f0-9]{32})', u)
            pid = m.group(1) if m else u
            if pid not in seen:
                seen.add(pid)
                final_urls.append(u.split("?")[0] + "?format=original")
        img_urls = final_urls
        write_log(f"✅ 提取到 {len(img_urls)} 张 Grailed 商品图片", "success")

        download_headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Referer": url,
            "Accept": "image/avif,image/webp,image/apng,image/*,*/*;q=0.8",
        }
        from concurrent.futures import ThreadPoolExecutor, as_completed
        results = []
        download_args = [(u, save_folder, download_headers, {}, i)
                         for i, u in enumerate(img_urls)]
        with ThreadPoolExecutor(max_workers=min(DOWNLOAD_WORKERS, len(img_urls))) as executor:
            futures = {executor.submit(_download_single_image, arg): arg
                       for arg in download_args}
            for future in as_completed(futures):
                results.append(future.result())

        ok = sum(1 for r in results if r)
        fail = len(results) - ok
        if fail > 0:
            write_log(f"❌ {fail} 张图片下载失败", "error")
        write_log(f"✅ Grailed 商品处理完成：成功 {ok}/{len(img_urls)} 张", "success")
        return ok > 0

    except Exception as e:
        write_log(f"❌ Grailed 抓取异常：{e}", "error")
        FAILED_URLS.append(url)
        return False
    finally:
        if own_driver and driver:
            try:
                driver.quit()
            except Exception:
                pass


def scrape_mercari_by_browser(url, save_folder, debug_mode, driver=None):
    """Mercari 商品图片采集 — 从 JSON-LD 提取"""
    global STOP_TASK, FAIL_COUNT, FAILED_URLS
    if _on_status:
        _on_status("正在抓取 Mercari 商品图片")
    if STOP_TASK:
        return False

    own_driver = False
    try:
        write_log(f"======================")
        write_log(f"开始抓取 Mercari 商品：{url}")
        if STOP_TASK:
            return False

        if driver is None:
            driver = init_chrome(debug_mode)
            own_driver = True

        for page_retry in range(3):
            driver.get(url)
            sleep(3)
            if "Mercari" in driver.title or "mercari" in driver.current_url:
                break
            sleep(2)

        # 从 JSON-LD 提取图片（Mercari 在 Product schema 里直接放了图片列表）
        import re as _re, json as _json
        ld_pat = r'<script type="application/ld\+json"[^>]*>(.*?)</script>'
        img_urls = []
        for m in _re.finditer(ld_pat, driver.page_source, _re.DOTALL):
            try:
                d = _json.loads(m.group(1))
                if d.get("@type") == "Product":
                    imgs = d.get("image", [])
                    if isinstance(imgs, list):
                        img_urls = imgs
                    elif isinstance(imgs, str):
                        img_urls = [imgs]
                    break
            except Exception: pass

        if not img_urls:
            write_log("❌ 未提取到 Mercari 商品图片", "error")
            FAILED_URLS.append(url)
            if own_driver:
                driver.quit()
            return False

        # 去重 + 高清升级
        seen = set()
        final_urls = []
        for u in img_urls:
            m = _re.search(r'(m\d+)_(\d+)\.(jpg|jpeg|png|webp)', u)
            if m:
                key = "{}_{}".format(m.group(1), m.group(2))
                if key not in seen:
                    seen.add(key)
                    hq = "https://u-mercari-images.mercdn.net/photos/{}_{}.{}?width=4096&quality=100".format(
                        m.group(1), m.group(2), m.group(3))
                    final_urls.append(hq)
        img_urls = final_urls
        write_log("✅ 提取到 {} 张 Mercari 商品图片".format(len(img_urls)), "success")

        download_headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Referer": url,
            "Accept": "image/avif,image/webp,image/apng,image/*,*/*;q=0.8",
        }
        from concurrent.futures import ThreadPoolExecutor, as_completed
        results = []
        download_args = [(u, save_folder, download_headers, {}, i)
                         for i, u in enumerate(img_urls)]
        with ThreadPoolExecutor(max_workers=min(DOWNLOAD_WORKERS, len(img_urls))) as executor:
            futures = {executor.submit(_download_single_image, arg): arg
                       for arg in download_args}
            for future in as_completed(futures):
                results.append(future.result())

        ok = sum(1 for r in results if r)
        fail = len(results) - ok
        if fail > 0:
            write_log("❌ {} 张图片下载失败".format(fail), "error")
        write_log("✅ Mercari 商品处理完成：成功 {}/{} 张".format(ok, len(img_urls)), "success")
        return ok > 0

    except Exception as e:
        write_log("❌ Mercari 抓取异常：{}".format(e), "error")
        FAILED_URLS.append(url)
        return False
    finally:
        if own_driver and driver:
            try:
                driver.quit()
            except Exception:
                pass


def scrape_wallapop_by_browser(url, save_folder, debug_mode, driver=None):
    """Wallapop 商品图片采集"""
    global STOP_TASK, FAIL_COUNT, FAILED_URLS
    if _on_status:
        _on_status("正在抓取 Wallapop 商品图片")
    if STOP_TASK:
        return False

    own_driver = False
    try:
        write_log(f"======================")
        write_log(f"开始抓取 Wallapop 商品：{url}")
        if STOP_TASK:
            return False

        if driver is None:
            driver = init_chrome(debug_mode)
            own_driver = True

        for page_retry in range(3):
            driver.get(url)
            sleep(3)
            if "WALLAPOP" in driver.title.upper():
                break
            sleep(2)

        # 提取 cdn.wallapop.com 产品图
        import re as _re
        dom_urls = driver.execute_script("""
            var out = [];
            var imgs = document.querySelectorAll('img');
            imgs.forEach(function(img) {
                var s = img.src || '';
                if (s.indexOf('cdn.wallapop.com') !== -1 && s.indexOf('W640') !== -1) {
                    if (out.indexOf(s) === -1) out.push(s);
                }
            });
            return out;
        """)
        img_urls = list(dict.fromkeys(dom_urls or []))

        if not img_urls:
            write_log("❌ 未提取到 Wallapop 商品图片", "error")
            FAILED_URLS.append(url)
            if own_driver:
                driver.quit()
            return False

        # 去重 + 尝试去参数取原图
        cookies = driver.get_cookies()
        seen = set()
        final_urls = []
        for u in img_urls:
            m = _re.search(r'(i\d{10,12})', u)
            pid = m.group(1) if m else u
            if pid not in seen:
                seen.add(pid)
                # 去 ?pictureSize= 参数取原图
                orig = u.split("?")[0]
                final_urls.append(orig)
        img_urls = final_urls
        write_log("✅ 提取到 {} 张 Wallapop 商品图片".format(len(img_urls)), "success")

        # 用浏览器 cookie 下载（每线程独立 session，线程安全）
        download_headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Referer": url,
            "Accept": "image/avif,image/webp,image/apng,image/*,*/*;q=0.8",
        }
        from concurrent.futures import ThreadPoolExecutor, as_completed
        results = []
        download_args = [(u, save_folder, download_headers, cookies, i)
                         for i, u in enumerate(img_urls)]
        with ThreadPoolExecutor(max_workers=min(DOWNLOAD_WORKERS, len(img_urls))) as executor:
            futures = {executor.submit(_download_depop_image, arg): arg
                       for arg in download_args}
            for future in as_completed(futures):
                results.append(future.result())

        ok = sum(1 for r in results if r)
        fail = len(results) - ok
        if fail > 0:
            write_log("❌ {} 张图片下载失败".format(fail), "error")
        write_log("✅ Wallapop 商品处理完成：成功 {}/{} 张".format(ok, len(img_urls)), "success")
        return ok > 0

    except Exception as e:
        write_log("❌ Wallapop 抓取异常：{}".format(e), "error")
        FAILED_URLS.append(url)
        return False
    finally:
        if own_driver and driver:
            try:
                driver.quit()
            except Exception:
                pass


def start_crawl_task(urls_text, debug_mode, wait_time=0):
    global STOP_TASK, LOG_FILE, CUSTOM_SAVE_ROOT, SESSION_SAVE_ROOT, TOTAL_TASKS, CURRENT_TASK, SUCCESS_COUNT, FAIL_COUNT, FAILED_URLS
    import time as _time
    _start = _time.time()

    # 内部完整性校验
    if not _verify_license_quick():
        write_log("任务初始化校验失败", "error")
        if _on_finished:
            _on_finished(stopped=False)
        return

    STOP_TASK = False
    CURRENT_TASK = 0
    SUCCESS_COUNT = 0
    FAIL_COUNT = 0
    FAILED_URLS = []
    FAIL_REASONS = {}
    global TOTAL_IMAGES
    TOTAL_IMAGES = 0

    base_root = CUSTOM_SAVE_ROOT.strip() or DEFAULT_SAVE_ROOT
    if not os.path.exists(base_root):
        os.makedirs(base_root)
    _cleanup_old_logs(base_root, days=3)
    ts = datetime.now().strftime("%Y%m%d_%H%M")
    save_root = os.path.join(base_root, f"Crawl_{ts}")
    os.makedirs(save_root, exist_ok=True)
    SESSION_SAVE_ROOT = save_root
    if ENABLE_FILE_LOG:
        LOG_FILE = os.path.join(save_root, "Process_Log.txt")
        with open(LOG_FILE, "w", encoding="utf-8") as f:
            f.write("")

    write_log("=" * 50)
    init_session_gps()
    init_session_exif()
    init_session_jpeg()
    write_log("图像重构引擎启动", "info")
    write_log(f"📂 保存路径：{save_root}", "info")
    if SELECTED_CITY == "全国随机":
        write_log(f"📍 地理模式：全国随机（{SELECTED_COUNTRY}）", "info")
    else:
        write_log(f"📍 地理模式：{SELECTED_GPS_MODE}（{SELECTED_COUNTRY} {SELECTED_CITY}）", "info")
    write_log(f"🖼️  智能压缩：{'开' if COMPRESS_ENABLED else '关'} | 水印：{'开' if WATERMARK_ENABLED else '关'}", "info")
    write_log(f"🛡️  高级防检测：{'开' if ADVANCED_ANTI_DETECT_ENABLED else '关'}", "info")
    write_log(f"🚀 加速：浏览器复用 + 并发下载×{DOWNLOAD_WORKERS}", "info")

    urls = list(dict.fromkeys([u.strip() for u in urls_text.split("\n") if u.strip() and "http" in u]))
    TOTAL_TASKS = len(urls)
    if not urls:
        write_log("❌ 请输入至少一个有效的商品链接！", "error")
        if _on_finished:
            _on_finished(stopped=False)
        return

    write_log(f"待处理商品：{TOTAL_TASKS} | 调试：{'开' if debug_mode else '关'}", "info")
    write_log("=" * 50)

    # ---- 浏览器复用：整个任务共享一个 driver ----
    shared_driver = None
    if not debug_mode:
        try:
            shared_driver = init_chrome(debug_mode)
            write_log("🚀 Chrome 已启动，所有链接共享此浏览器", "success")
        except Exception as e:
            write_log(f"⚠️ 浏览器启动失败，将逐链接创建：{e}", "warning")

    try:
        for index, url in enumerate(urls):
            if STOP_TASK:
                write_log("❌ 任务已手动停止", "warning")
                break
            CURRENT_TASK = index + 1
            if _on_progress:
                _on_progress(CURRENT_TASK, TOTAL_TASKS, SUCCESS_COUNT, FAIL_COUNT)

            # 按域名分流平台
            if "wallapop.com" in url:
                result = scrape_wallapop_by_browser(url, save_root, debug_mode, driver=shared_driver)
            elif "mercari.com" in url:
                result = scrape_mercari_by_browser(url, save_root, debug_mode, driver=shared_driver)
            elif "grailed.com" in url:
                result = scrape_grailed_by_browser(url, save_root, debug_mode, driver=shared_driver)
            elif "poshmark.com" in url:
                result = scrape_poshmark_by_browser(url, save_root, debug_mode, driver=shared_driver)
            elif "vestiairecollective.com" in url:
                result = scrape_vc_by_browser(url, save_root, debug_mode, driver=shared_driver)
            elif "depop.com" in url:
                result = scrape_depop_by_browser(url, save_root, debug_mode, driver=shared_driver)
            else:
                result = scrape_vinted_by_browser(url, save_root, debug_mode,
                                                   driver=shared_driver, wait_time=wait_time)
            if result:
                SUCCESS_COUNT += 1
            else:
                FAIL_COUNT += 1

            if _on_progress:
                _on_progress(CURRENT_TASK, TOTAL_TASKS, SUCCESS_COUNT, FAIL_COUNT)

            if not STOP_TASK and index < len(urls) - 1:
                sleep(random.uniform(2, 4))  # 商品间短暂间隔

    finally:
        if shared_driver:
            try:
                shared_driver.quit()
                write_log("Chrome 浏览器已关闭", "info")
            except Exception:
                pass

    elapsed = round(_time.time() - _start, 1)
    write_log("=" * 50)
    if STOP_TASK:
        write_log(f"🎉 任务已停止！耗时 {elapsed}s", "info")
        if _on_status:
            _on_status("已停止")
    else:
        write_log(f"🎉 全部完成！耗时 {elapsed}s", "success")
        if _on_status:
            _on_status("已完成")
    write_log(f"总：{TOTAL_TASKS} | 成功：{SUCCESS_COUNT} | 失败：{FAIL_COUNT}", "info")
    write_log(f"📂 图片位置：{save_root}", "info")
    write_log("=" * 50)
    if _on_finished:
        _on_finished(STOP_TASK)


# ====================== 工具函数（GUI 无关） ======================
def open_save_dir(save_root=None):
    save_path = save_root or CUSTOM_SAVE_ROOT.strip() or DEFAULT_SAVE_ROOT
    try:
        if not os.path.exists(save_path):
            return False, "保存目录不存在！"
        img_files = [f for f in os.listdir(save_path) if f.lower().endswith((".jpg", ".jpeg", ".png", ".webp"))]
        if img_files:
            img_files.sort(key=lambda x: os.path.getmtime(os.path.join(save_path, x)), reverse=True)
            latest_file = img_files[0]
            latest_file_path = os.path.join(save_path, latest_file)
            shell = win32com.client.Dispatch("Shell.Application")
            folder = shell.NameSpace(os.path.abspath(save_path))
            if folder:
                folder.SortColumns = "prop:System.DateModified;desc"
            win32api.ShellExecute(0, "open", "explorer.exe", f"/select,{os.path.abspath(latest_file_path)}", None, win32con.SW_SHOWNORMAL)
            write_log(f"✅ 已打开图片目录，按修改时间降序排序，自动选中最新文件", "success")
        else:
            shell = win32com.client.Dispatch("Shell.Application")
            folder = shell.NameSpace(os.path.abspath(save_path))
            if folder:
                folder.SortColumns = "prop:System.DateModified;desc"
            os.startfile(save_path)
            write_log(f"✅ 已打开图片目录，按修改时间降序排序", "success")
        return True, ""
    except Exception as e:
        try:
            os.startfile(save_path)
            write_log(f"✅ 已打开图片目录", "success")
            return True, ""
        except Exception:
            return False, f"打开目录失败：{str(e)}"


def parse_geo(selected_country, selected_city, mode_text):
    """解析地理位置选择，返回 (gps_mode, gps_data)"""
    if selected_city == "全国随机":
        return "random_country", selected_country
    if selected_country not in GEO_DATA:
        return "random_country", "法国"
    city_dict = GEO_DATA[selected_country]
    if selected_city not in city_dict:
        first_city = next(iter(city_dict.keys()))
        base_lat, base_lon = city_dict[first_city]
        return "random", (first_city, base_lat, base_lon)
    base_lat, base_lon = city_dict[selected_city]
    gps_data = (selected_city, base_lat, base_lon)
    if mode_text == "随机位置":
        return "random", gps_data
    else:
        return "fixed", gps_data


def set_geo(selected_country, selected_city, mode_text):
    """设置全局地理位置变量"""
    global SELECTED_COUNTRY, SELECTED_CITY, SELECTED_GPS_MODE, SELECTED_GPS_DATA
    SELECTED_COUNTRY = selected_country
    SELECTED_CITY = selected_city
    SELECTED_GPS_MODE, SELECTED_GPS_DATA = parse_geo(selected_country, selected_city, mode_text)


def init_session_gps():
    """初始化当前会话的共享 GPS 坐标。一次会话内所有图片使用同一城市、相近坐标。"""
    global SESSION_GPS
    if SELECTED_CITY == "全国随机":
        country = SELECTED_COUNTRY
        if country not in GEO_DATA:
            country = "法国"
        city_dict = GEO_DATA[country]
        lats = [lat for lat, lon in city_dict.values()]
        lons = [lon for lat, lon in city_dict.values()]
        lat = random.uniform(min(lats), max(lats))
        lon = random.uniform(min(lons), max(lons))
        city = random.choice(list(city_dict.keys()))
    elif SELECTED_GPS_MODE == "random":
        city_name, base_lat, base_lon = SELECTED_GPS_DATA
        lat = base_lat + random.uniform(-0.05, 0.05)
        lon = base_lon + random.uniform(-0.05, 0.05)
        city = city_name
    elif SELECTED_GPS_MODE == "fixed":
        city_name, base_lat, base_lon = SELECTED_GPS_DATA
        lat = base_lat + random.uniform(-0.01, 0.01)
        lon = base_lon + random.uniform(-0.01, 0.01)
        city = city_name
    else:
        return
    SESSION_GPS = (lat, lon, city)
    write_log(f"📍 会话GPS已初始化：{SELECTED_COUNTRY} {city} | {lat:.6f}, {lon:.6f}", "info")


def init_session_exif():
    """初始化当前会话的共享 EXIF 参数。同批次图片使用同一设备、相近拍摄时间。"""
    global SESSION_EXIF, SESSION_DT_BASE
    if SELECTED_DEVICE != "随机" and SELECTED_DEVICE in DEVICE_INFO_MAP:
        make, model, software = DEVICE_INFO_MAP[SELECTED_DEVICE]
        dev_model = model
    else:
        models = list(DEVICE_INFO_MAP.keys())
        dev_model = random.choice(models)
        make, model, software = DEVICE_INFO_MAP[dev_model]
    exposure = (random.randint(1, 200), 1000)
    fnum = (random.randint(16, 28), 10)
    iso = random.randint(50, 1600)
    lens = f"f/{random.uniform(1.8, 5.6):.1f} {random.randint(12, 200)}mm"
    SESSION_EXIF = (make, model, software, dev_model, exposure, fnum, iso, lens)
    # 随机一个过去的时间作为拍摄起点（最近30天内）
    SESSION_DT_BASE = datetime.now() - timedelta(days=random.randint(0, 30),
                                                   hours=random.randint(0, 23),
                                                   minutes=random.randint(0, 59))
    write_log(f"📷 会话EXIF已初始化：{make} {model} ISO{iso} f/{fnum[0]/fnum[1]:.1f}", "info")


def init_session_jpeg():
    """初始化当前会话的共享 JPEG 参数。"""
    global SESSION_JPEG
    if LOSSLESS_ENABLED:
        SESSION_JPEG = (100, "4:4:4")
    elif COMPRESS_ENABLED:
        SESSION_JPEG = (random.randint(*COMPRESS_QUALITY_RANGE), random.choice(SUBSAMPLING_OPTIONS))
    elif DEEP_ANTI_DUPLICATE_ENABLED:
        SESSION_JPEG = (random.randint(*DEEP_JPEG_QUALITY_RANGE), random.choice(SUBSAMPLING_OPTIONS))
    else:
        SESSION_JPEG = (random.randint(*JPEG_QUALITY_RANGE), random.choice(SUBSAMPLING_OPTIONS))
