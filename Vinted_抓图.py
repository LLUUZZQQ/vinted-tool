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
DEFAULT_SAVE_ROOT = "Vinted_Processed_Images"
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
        "尼斯": (43.7102, 7.2620), "斯特拉斯堡": (48.5734, 7.7521), "图卢兹": (43.6047, 1.4442)
    },
    "西班牙": {
        "马德里": (40.4168, -3.7038), "巴塞罗那": (41.3851, 2.1734), "瓦伦西亚": (39.4699, -0.3763),
        "塞维利亚": (37.3891, -5.9845), "马拉加": (36.7213, -4.4214), "毕尔巴鄂": (43.2630, -2.9350),
        "萨拉戈萨": (41.6488, -0.8891), "帕尔马": (39.5696, 2.6502), "穆尔西亚": (37.9922, -1.1307)
    },
    "英国": {
        "伦敦": (51.5074, -0.1278), "曼彻斯特": (53.4808, -2.2426), "伯明翰": (52.4862, -1.8904),
        "利物浦": (53.4084, -2.9916), "利兹": (53.8008, -1.5491), "爱丁堡": (55.9533, -3.1883),
        "格拉斯哥": (55.8642, -4.2518), "布里斯托尔": (51.4545, -2.5879), "纽卡斯尔": (54.9783, -1.6174)
    },
    "意大利": {
        "罗马": (41.9028, 12.4964), "米兰": (45.4642, 9.1900), "都灵": (45.0703, 7.6869),
        "佛罗伦萨": (43.7696, 11.2558), "威尼斯": (45.4372, 12.3358), "那不勒斯": (40.8518, 14.2681),
        "博洛尼亚": (44.4949, 11.3426), "巴勒莫": (38.1157, 13.3615), "维罗纳": (45.4384, 10.9916)
    },
    "德国": {
        "柏林": (52.5200, 13.4050), "慕尼黑": (48.1351, 11.5820), "汉堡": (53.5511, 9.9937),
        "法兰克福": (50.1109, 8.6821), "科隆": (50.9375, 6.9603), "杜塞尔多夫": (51.2277, 6.7735),
        "斯图加特": (48.7758, 9.1829), "莱比锡": (51.3397, 12.3731), "汉诺威": (52.3759, 9.7320)
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
SELECTED_COUNTRY = None
SELECTED_CITY = None
SELECTED_GPS_MODE = None
SELECTED_GPS_DATA = None
TOTAL_TASKS = 0
CURRENT_TASK = 0
SUCCESS_COUNT = 0
FAIL_COUNT = 0
FAILED_URLS = []
FAIL_REASONS = {}
COMPRESS_ENABLED = False
WATERMARK_ENABLED = False
LOSSLESS_ENABLED = False  # 无损画质模式：quality=100 + 4:4:4
ADVANCED_ANTI_DETECT_ENABLED = False  # 高级防检测：JPEG块破坏 + 空间噪声 + 空变亮度

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
        except:
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
    return (degrees, 1), (minutes, 1), (int(seconds * 100), 100)


def write_log(content, level="info"):
    global LOG_FILE
    with _log_lock:
        if LOG_FILE:
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
    if _on_status:
        _on_status("正在处理图片")
    img = None
    try:
        img = Image.open(image_path)
        original_width, original_height = img.size

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
        if ADVANCED_ANTI_DETECT_ENABLED:
            shift_x = random.uniform(*BLOCK_SHIFT_RANGE) * random.choice([-1, 1])
            shift_y = random.uniform(*BLOCK_SHIFT_RANGE) * random.choice([-1, 1])
            img = img.transform(
                img.size, Image.AFFINE,
                (1, 0, shift_x, 0, 1, shift_y),
                resample=Image.BICUBIC, fillcolor=(255, 255, 255)
            )

        # ---- 防重处理：RGBA 一次转换，合并旋转+缩放+裁剪 ----
        rotate_angle = random.uniform(*ROTATE_RANGE) * random.choice([-1, 1])
        img = img.convert("RGBA")
        img = img.rotate(rotate_angle, expand=False, resample=Image.BICUBIC)

        # 微缩放 + 微裁剪合并执行
        scale_w = int(original_width * (1 + random.uniform(-0.001, 0.001)))
        scale_h = int(original_height * (1 + random.uniform(-0.001, 0.001)))
        crop_l = int(original_width * random.uniform(*CROP_RATIO))
        crop_t = int(original_height * random.uniform(*CROP_RATIO))
        crop_r = original_width - int(original_width * random.uniform(*CROP_RATIO))
        crop_b = original_height - int(original_height * random.uniform(*CROP_RATIO))

        img = img.resize((scale_w, scale_h), resample=Image.BICUBIC)
        img = img.crop((crop_l, crop_t, crop_r, crop_b))
        img = img.resize((original_width, original_height), resample=Image.BICUBIC)

        # RGBA → RGB（白底合成）
        background = Image.new("RGB", img.size, (255, 255, 255))
        background.paste(img, mask=img.split()[-1])
        img = background

        # 边缘去白边：2px 裁剪消除仿射变换和旋转的白色残留
        img = img.crop((2, 2, original_width - 2, original_height - 2))
        img = img.resize((original_width, original_height), resample=Image.BICUBIC)

        # ---- 像素域微调（高级防检测使用空间相关噪声模拟传感器） ----
        img_array = np.array(img, dtype=np.int16)
        if ADVANCED_ANTI_DETECT_ENABLED:
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

        # 亮度/对比度微调（高级防检测使用空间渐变模拟镜头暗角）
        if ADVANCED_ANTI_DETECT_ENABLED:
            img_array = np.array(img, dtype=np.float32)
            h, w = img_array.shape[:2]
            angle = random.uniform(0, 2 * np.pi)
            steepness = random.uniform(*SPATIAL_BRIGHTNESS_STRENGTH)
            y_coords, x_coords = np.mgrid[0:h, 0:w]
            projection = x_coords * np.cos(angle) + y_coords * np.sin(angle)
            gradient = 1.0 + steepness * (projection / max(h, w) - 0.5)
            bf = 1 + random.uniform(*BRIGHTNESS_ADJUST) / 100
            cf = 1 + random.uniform(*CONTRAST_ADJUST) / 100
            for c in range(3):
                img_array[:, :, c] = (img_array[:, :, c] - 128) * cf * gradient + 128 * bf
            img_array = np.clip(img_array, 0, 255).astype(np.uint8)
            img = Image.fromarray(img_array)
        else:
            bf = 1 + random.uniform(*BRIGHTNESS_ADJUST) / 100
            img = ImageEnhance.Brightness(img).enhance(bf)
            cf = 1 + random.uniform(*CONTRAST_ADJUST) / 100
            img = ImageEnhance.Contrast(img).enhance(cf)

        # ---- 隐形水印 ----
        if WATERMARK_ENABLED:
            try:
                watermark = Image.new("RGBA", img.size, (255, 255, 255, 0))
                draw = ImageDraw.Draw(watermark)
                font_size = max(int(original_width / 20), 12)
                try:
                    font = ImageFont.truetype("arial.ttf", font_size)
                except:
                    font = ImageFont.load_default()
                pos_x = random.choice([10, original_width - font_size * len(WATERMARK_TEXT) - 10])
                pos_y = random.choice([10, original_height - font_size - 10])
                draw.text((pos_x, pos_y), WATERMARK_TEXT, font=font,
                          fill=(255, 255, 255, WATERMARK_OPACITY))
                img = Image.alpha_composite(img.convert("RGBA"), watermark).convert("RGB")
            except Exception as e:
                write_log(f"⚠️ 水印添加跳过：{e}", "warning")

        # ---- EXIF 地理信息（本地防重跳过） ----
        exif_bytes = b""
        if not skip_gps:
            try:
                random_year = random.randint(2024, 2026)
                random_month = random.randint(1, 12)
                random_day = random.randint(1, 28)
                random_hour = random.randint(0, 23)
                random_min = random.randint(0, 59)
                random_sec = random.randint(0, 59)
                dt = f"{random_year}:{random_month:02d}:{random_day:02d} {random_hour:02d}:{random_min:02d}:{random_sec:02d}"

                exif_dict = {"0th": {}, "Exif": {}, "GPS": {}}
                exif_dict["0th"] = {
                    piexif.ImageIFD.Make: random.choice(["iPhone", "HUAWEI", "Xiaomi", "Canon", "Nikon"]),
                    piexif.ImageIFD.Model: random.choice(["iPhone 14", "iPhone 15", "P70", "Mate 60", "EOS R5"]),
                    piexif.ImageIFD.Software: random.choice(["Photos", "Snapseed", "Lightroom", "System Camera"]),
                    piexif.ImageIFD.DateTime: dt,
                    piexif.ImageIFD.Orientation: 1,
                }
                exif_dict["Exif"] = {
                    piexif.ExifIFD.ExposureTime: (random.randint(1, 200), 1000),
                    piexif.ExifIFD.FNumber: (random.randint(16, 28), 10),
                    piexif.ExifIFD.ISOSpeedRatings: random.randint(50, 1600),
                    piexif.ExifIFD.DateTimeOriginal: dt,
                    piexif.ExifIFD.LensModel: f"f/{random.uniform(1.8, 5.6):.1f} {random.randint(12, 200)}mm",
                }

                final_lat, final_lon, final_city = None, None, None
                if SELECTED_CITY == "全国随机":
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

                # EXIF 缩略图 + JPEG 注释（模拟真实相机元数据）
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
                        write_log(f"EXIF缩略图跳过: {e}", "warning")

                exif_bytes = piexif.dump(exif_dict)
            except Exception as e:
                write_log(f"EXIF地理信息写入异常: {e}", "warning")

        # PNG 中间格式：破坏 JPEG 双重压缩痕迹
        if ADVANCED_ANTI_DETECT_ENABLED:
            try:
                png_buf = io.BytesIO()
                img.save(png_buf, format="PNG")
                png_buf.seek(0)
                img.close()
                img = Image.open(png_buf)
            except Exception as e:
                write_log(f"PNG中间转换跳过: {e}", "warning")

        # JPEG 保存策略
        if LOSSLESS_ENABLED:
            save_quality = 100
            subsampling = "4:4:4"
        elif COMPRESS_ENABLED:
            save_quality = random.randint(*COMPRESS_QUALITY_RANGE)
            subsampling = random.choice(SUBSAMPLING_OPTIONS)
        else:
            save_quality = random.randint(*JPEG_QUALITY_RANGE)
            subsampling = random.choice(SUBSAMPLING_OPTIONS)

        temp_path = image_path + "_processed.jpg"
        save_kwargs = {"format": "JPEG", "quality": save_quality, "subsampling": subsampling}
        if exif_bytes:
            save_kwargs["exif"] = exif_bytes
        img.save(temp_path, **save_kwargs)
        img.close()
        img = None

        # MD5 修改
        with open(temp_path, "ab") as f:
            f.write(random.randbytes(random.randint(*APPEND_BYTES)))

        new_filename = random_filename(".jpg")
        new_path = os.path.join(os.path.dirname(image_path), new_filename)
        os.replace(temp_path, new_path)
        os.remove(image_path)

        file_size = round(os.path.getsize(new_path) / 1024, 2)
        with open(new_path, "rb") as f:
            new_md5 = hashlib.md5(f.read()).hexdigest()
        write_log(f"✅ 防重处理成功 | {new_filename} | {file_size}KB | Q={save_quality} SS={subsampling} | MD5={new_md5[:12]}...", "success")
        return True
    except Exception as e:
        write_log(f"❌ 图片处理失败 | 路径：{image_path} | 错误：{e}", "error")
        if img:
            try:
                img.close()
            except:
                pass
        return False


def _ensure_chrome():
    """确保 Chrome 可用。返回 (chrome_binary_path 或 None)"""
    import zipfile, io as _io
    # 1. 系统已安装 → 直接用
    try:
        out = subprocess.run(
            ['reg', 'query', r'HKEY_CURRENT_USER\Software\Google\Chrome\BLBeacon', '/v', 'version'],
            capture_output=True, text=True, timeout=5
        )
        if 'version' in out.stdout:
            return None
    except:
        pass
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"SOFTWARE\Google\Chrome\BLBeacon") as k:
            winreg.QueryValueEx(k, "version")
            return None
    except:
        pass

    # 2. 已有缓存的便携版
    chrome_dir = os.path.join(os.environ.get("LOCALAPPDATA", os.path.expanduser("~")), "VTMAX", "chrome")
    chrome_exe = os.path.join(chrome_dir, "chrome.exe")
    if os.path.exists(chrome_exe):
        return chrome_exe

    # 3. 自动下载便携版
    write_log("正在准备运行环境（首次使用需下载浏览器）...", "info")
    if _on_status:
        _on_status("正在准备运行环境...")
    try:
        os.makedirs(chrome_dir, exist_ok=True)
        # 获取下载地址
        api = "https://googlechromelabs.github.io/chrome-for-testing/last-known-good-versions-with-downloads.json"
        resp = requests.get(api, headers={"User-Agent": "Mozilla/5.0"}, timeout=30)
        data = resp.json()
        for ch in data.get("channels", {}).get("Stable", {}).get("downloads", {}).get("chrome", []):
            if ch["platform"] == "win64":
                chrome_url = ch["url"]
                break
        else:
            raise Exception("无法获取下载地址")
        # 下载
        write_log("正在下载浏览器（约 150MB，仅首次）...", "info")
        zip_path = os.path.join(chrome_dir, "chrome.zip")
        r = requests.get(chrome_url, headers={"User-Agent": "Mozilla/5.0"}, stream=True, timeout=600)
        total = int(r.headers.get("Content-Length", 0))
        downloaded = 0
        with open(zip_path, "wb") as f:
            for chunk in r.iter_content(chunk_size=65536):
                f.write(chunk)
                downloaded += len(chunk)
                if total > 0 and _on_status:
                    pct = downloaded * 100 // total
                    if pct % 25 == 0:
                        _on_status(f"正在准备运行环境 {pct}%...")
        # 解压
        write_log("正在解压...", "info")
        if _on_status:
            _on_status("正在解压浏览器...")
        with zipfile.ZipFile(zip_path) as z:
            root = z.namelist()[0].split("/")[0]
            for name in z.namelist():
                if name.endswith("/"):
                    continue
                dest = os.path.join(chrome_dir, name[len(root)+1:])
                os.makedirs(os.path.dirname(dest), exist_ok=True)
                with z.open(name) as src, open(dest, "wb") as dst:
                    dst.write(src.read())
        os.remove(zip_path)
        if os.path.exists(chrome_exe):
            write_log("浏览器就绪", "success")
            return chrome_exe
        raise Exception("解压后未找到 chrome.exe")
    except Exception as e:
        write_log(f"环境准备失败: {e}", "error")
        raise Exception(
            "运行环境准备失败，请检查网络连接\n\n"
            "或手动安装 Google Chrome 浏览器后重试"
        )


def init_chrome(debug_mode):
    if _on_status:
        _on_status("正在启动浏览器")

    # 确保 Chrome 可用（无 Chrome 则自动下载便携版）
    chrome_binary = _ensure_chrome()

    # 获取 chromedriver 路径
    frozen_dir = getattr(sys, '_MEIPASS', None)
    driver_path = None
    if frozen_dir:
        bundled = os.path.join(frozen_dir, 'chromedriver.exe')
        exe_dir = os.path.dirname(sys.executable)
        target = os.path.join(exe_dir, 'chromedriver.exe')
        if not os.path.exists(target) and os.path.exists(bundled):
            try:
                shutil.copy2(bundled, target)
            except:
                pass
        if os.path.exists(target):
            driver_path = target
        elif os.path.exists(bundled):
            driver_path = bundled
    if not driver_path:
        script_dir = os.path.dirname(os.path.abspath(__file__))
        local = os.path.join(script_dir, 'chromedriver.exe')
        if os.path.exists(local):
            driver_path = local

    if driver_path:
        service = Service(executable_path=driver_path)
    else:
        try:
            service = Service()
        except:
            raise Exception("Chromedriver 未找到")

    options = webdriver.ChromeOptions()
    if chrome_binary:
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
    except:
        return False


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
            except:
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
            except:
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
                except:
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
                    except: pass
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
        if driver and own_driver:
            driver.quit()
        return False


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
    except:
        pass


def start_crawl_task(urls_text, debug_mode, wait_time=0):
    global STOP_TASK, LOG_FILE, CUSTOM_SAVE_ROOT, TOTAL_TASKS, CURRENT_TASK, SUCCESS_COUNT, FAIL_COUNT, FAILED_URLS
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

    save_root = CUSTOM_SAVE_ROOT.strip() or DEFAULT_SAVE_ROOT
    if not os.path.exists(save_root):
        os.makedirs(save_root)
    _cleanup_old_logs(save_root, days=3)
    LOG_FILE = os.path.join(save_root, "Process_Log.txt")
    with open(LOG_FILE, "w", encoding="utf-8") as f:
        f.write("")

    write_log("=" * 50)
    write_log("Vinted 防重复终极版启动 v2", "info")
    write_log(f"📂 保存路径：{save_root}", "info")
    if SELECTED_CITY == "全国随机":
        write_log(f"📍 地理模式：全国随机（{SELECTED_COUNTRY}）", "info")
    else:
        write_log(f"📍 地理模式：{SELECTED_GPS_MODE}（{SELECTED_COUNTRY} {SELECTED_CITY}）", "info")
    write_log(f"🖼️  智能压缩：{'开' if COMPRESS_ENABLED else '关'} | 水印：{'开' if WATERMARK_ENABLED else '关'}", "info")
    write_log(f"🛡️  高级防检测：{'开' if ADVANCED_ANTI_DETECT_ENABLED else '关'}", "info")
    write_log(f"🚀 加速：浏览器复用 + 并发下载×{DOWNLOAD_WORKERS}", "info")

    urls = list(dict.fromkeys([u.strip() for u in urls_text.split("\n") if u.strip() and "vinted." in u]))
    TOTAL_TASKS = len(urls)
    if not urls:
        write_log("❌ 请输入至少一个有效的 Vinted 商品链接！", "error")
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

            # 兼容旧接口：传递 wait_time 参数到内部
            if scrape_vinted_by_browser(url, save_root, debug_mode,
                                        driver=shared_driver, wait_time=wait_time):
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
            except:
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
        except:
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
