# -*- coding: utf-8 -*-
"""
Vinted 抓图工具 — 客户端授权模块
HWID 绑定 + RSA 签名验证 + AES 加密 + 反调试 + exe 自检 + 定时校验 + 有效期
打包进 exe，不单独分发。
"""
import os
import sys
import json
import hashlib
import subprocess
import threading
import time as _time
import struct

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.backends import default_backend

# ====================== 公钥（打包前替换为你生成的实际公钥） ======================
# 运行 license_gen.py --gen-keys 获取公钥，替换此变量
_PUBLIC_KEY_PEM = b"""-----BEGIN PUBLIC KEY-----
MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEA0dKDBHyRn8/QqyQkIX53
sZRa9JLaDPokdXM+wwBb0ZC8s2PH7IMjaUBwrZF5XmbYzQbTisUT5Zaw4dogH+nx
095O9ktlLhrFQbBxNZpORAlTRp8FzX1XxiZ91vzVtt6OAgVZ9F6PTotO4uoLpAIE
8F51Hi5KX7ooeaBNqS9hl+SyWjFQh+D3e+64EMRyEUnDm11SA6l+nYIMa3PVBmAM
8HNzVEdqVvr8cwK1r772qO2RO4XZWG6OgvwIyg+oS2pJ3bk3V9J+g9e1ntb2UcuO
d6CViXfmWtPjtYRiSSk81iaThP+dSJ9o/N/fvTnmTfbvvM2TdJMFhPTiqD1FVB5N
AQIDAQAB
-----END PUBLIC KEY-----"""


def _get_public_key():
    """获取 RSA 公钥对象"""
    key_data = _PUBLIC_KEY_PEM
    if isinstance(key_data, str):
        key_data = key_data.encode("utf-8")
    return serialization.load_pem_public_key(key_data, backend=default_backend())


# ====================== HWID 采集 ======================

def _run_cmd(cmd):
    """执行命令返回 stdout 字符串"""
    try:
        si = subprocess.STARTUPINFO()
        si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        si.wShowWindow = subprocess.SW_HIDE
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=10,
                           startupinfo=si, creationflags=subprocess.CREATE_NO_WINDOW)
        return r.stdout.strip()
    except Exception:
        return ""


def get_raw_hwid():
    """采集原始硬件指纹：主板 + CPU + 系统盘序列号"""
    parts = []

    # 主板序列号
    mb = _run_cmd(["wmic", "baseboard", "get", "serialnumber"])
    if mb:
        lines = [l.strip() for l in mb.split("\n") if l.strip() and "SerialNumber" not in l]
        if lines:
            parts.append(lines[0])

    # CPU ID
    cpu = _run_cmd(["wmic", "cpu", "get", "processorid"])
    if cpu:
        lines = [l.strip() for l in cpu.split("\n") if l.strip() and "ProcessorId" not in l]
        if lines:
            parts.append(lines[0])

    # 系统盘序列号
    disk = _run_cmd([
        "wmic", "diskdrive",
        "where", "DeviceID='\\\\\\\\.\\\\PHYSICALDRIVE0'",
        "get", "serialnumber"
    ])
    if disk:
        lines = [l.strip() for l in disk.split("\n") if l.strip() and "SerialNumber" not in l]
        if lines:
            parts.append(lines[0])

    # 至少需要 2 个有效标识，不足则用 MAC 补
    if len(parts) < 2:
        mac = _run_cmd(["wmic", "nic", "where", "NetEnabled=True", "get", "MACAddress"])
        if mac:
            lines = [l.strip() for l in mac.split("\n") if l.strip() and "MACAddress" not in l]
            if lines:
                parts.append(lines[0])

    if len(parts) < 2:
        # 极端情况：用计算机名 + 用户名兜底
        parts.append(os.environ.get("COMPUTERNAME", "UNKNOWN"))
        parts.append(os.environ.get("USERNAME", "UNKNOWN"))

    return "|".join(parts)


def get_hwid():
    """生成格式化的机器码：SHA256(raw_hwid)[:16] → ABCD-1234-EFGH-5678"""
    raw = get_raw_hwid()
    h = hashlib.sha256(raw.encode("utf-8")).hexdigest().upper()[:16]
    return "-".join([h[i:i+4] for i in range(0, 16, 4)])


# ====================== License 文件（AES-256-GCM 加密） ======================

_LICENSE_DIR = os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")), "ImageMAX")
_LICENSE_PATH = os.path.join(_LICENSE_DIR, "license.dat")



def _derive_aes_key(hwid_raw):
    """从原始 HWID 派生 AES 密钥（SHA256 取前 32 字节）"""
    return hashlib.sha256(hwid_raw.encode("utf-8")).digest()


def _encrypt_license(data_dict, hwid_raw):
    """加密 license 数据 → 写入 license.dat（nonce 随机，前置写入）"""
    aesgcm = AESGCM(_derive_aes_key(hwid_raw))
    nonce = os.urandom(12)
    plaintext = json.dumps(data_dict, sort_keys=True).encode("utf-8")
    ciphertext = aesgcm.encrypt(nonce, plaintext, None)
    os.makedirs(_LICENSE_DIR, exist_ok=True)
    with open(_LICENSE_PATH, "wb") as f:
        f.write(nonce + ciphertext)


def _decrypt_license(hwid_raw):
    """读取并解密 license.dat，失败返回 None。兼容新旧两种格式。"""
    if not os.path.exists(_LICENSE_PATH):
        return None
    try:
        with open(_LICENSE_PATH, "rb") as f:
            data = f.read()
        aesgcm = AESGCM(_derive_aes_key(hwid_raw))
        # 尝试 v2 格式（12 字节随机 nonce + ciphertext）
        if len(data) >= 12:
            try:
                nonce, ciphertext = data[:12], data[12:]
                plaintext = aesgcm.decrypt(nonce, ciphertext, None)
                return json.loads(plaintext.decode("utf-8"))
            except Exception:
                pass
        # 回退 v1 格式（确定性 nonce，全文件即为 ciphertext）
        nonce = hashlib.sha256(b"vinted_scraper_v3_2026" + hwid_raw.encode("utf-8")).digest()[:12]
        plaintext = aesgcm.decrypt(nonce, data, None)
        return json.loads(plaintext.decode("utf-8"))
    except Exception:
        return None


# ====================== 核心验证 ======================

def _verify_signature(hwid, signature_b64):
    """RSA 验证签名"""
    import base64
    try:
        pubkey = _get_public_key()
        sig = base64.b64decode(signature_b64)
        pubkey.verify(
            sig,
            hwid.encode("utf-8"),
            padding.PSS(mgf=padding.MGF1(hashes.SHA256()),
                        salt_length=padding.PSS.MAX_LENGTH),
            hashes.SHA256()
        )
        return True
    except Exception:
        return False


REVOKE_URL = "https://vt-proxy.vtmax.workers.dev/revoke"


def _check_remote_revoked(hwid):
    """查询远程黑名单，返回 (is_revoked: bool, error: str)"""
    import urllib.request
    import urllib.error
    try:
        req = urllib.request.Request(
            f"{REVOKE_URL}?hwid={hwid}",
            headers={"User-Agent": "ImageMAX/1.0"}
        )
        with urllib.request.urlopen(req, timeout=8) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return data.get("revoked", False), ""
    except urllib.error.URLError as e:
        return False, f"网络错误：{e.reason}"
    except Exception as e:
        return False, f"查询失败：{e}"
    return False, ""


def check_license():
    """
    验证当前 license 是否有效。
    返回 (is_valid: bool, message: str, remaining_days: int or None)
    """
    raw = get_raw_hwid()
    data = _decrypt_license(raw)
    if data is None:
        return False, "未找到有效授权文件", None

    # 验证 HWID 是否匹配
    stored_hwid = data.get("hwid", "")
    current_hwid = get_hwid()
    if stored_hwid != current_hwid:
        return False, f"授权文件与当前机器不匹配\n{stored_hwid} ≠ {current_hwid}", None

    # 验证 RSA 签名
    signature = data.get("signature", "")
    if not _verify_signature(current_hwid, signature):
        return False, "授权签名无效（文件可能被篡改）", None

    # 检查有效期
    expires = data.get("expires_at")
    if expires:
        try:
            expire_time = _time.mktime(_time.strptime(expires, "%Y-%m-%d"))
            now = _time.time()
            if now > expire_time:
                return False, f"授权已于 {expires} 到期，请联系管理员续期", 0
            remaining = int((expire_time - now) / 86400) + 1
        except Exception:
            remaining = None
    else:
        remaining = None  # 永久有效

    # 远程黑名单检查（仅在授权有效时查询）
    revoked, revoke_err = _check_remote_revoked(current_hwid)
    if revoked:
        return False, "授权已被管理员停用，请联系管理员", None

    return True, "授权有效", remaining


def activate(activation_code):
    """
    激活软件。
    激活码格式：VINTED-BASE64SIGNATURE-EXPIRYDATE
    返回 (success: bool, message: str)
    """
    code = activation_code.strip().replace(" ", "")
    if not code.startswith("VINTED-"):
        return False, "激活码格式错误"

    parts = code.split("-", 2)  # ["VINTED", "SIGNATURE_B64", "EXPIRY_DATE(optional)"]
    if len(parts) < 2:
        return False, "激活码格式错误"

    current_hwid = get_hwid()
    signature_b64 = parts[1]
    expiry_date = parts[2] if len(parts) > 2 else None

    # 验证 RSA 签名
    if not _verify_signature(current_hwid, signature_b64):
        return False, "激活码无效（与当前机器不匹配）"

    # 保存 license
    data = {
        "hwid": current_hwid,
        "signature": signature_b64,
        "issued_at": _time.strftime("%Y-%m-%dT%H:%M:%S", _time.localtime()),
        "expires_at": expiry_date if expiry_date else None,
    }
    _encrypt_license(data, get_raw_hwid())
    return True, "激活成功"


# ====================== 反调试检测 ======================

_DEBUGGER_NAMES = [
    "x64dbg", "x32dbg", "ollydbg", "ida", "ida64", "idaq",
    "windbg", "immunity", "devenv", "processhacker",
    "procexp", "procmon", "hxd", "cheatengine",
    "scylla", "lordpe", "peid", "die", "exeinfope",
    "pestudio", "resourcehacker", "reshacker",
    "pyinstxtractor", "uncompyle6", "decompyle3",
]


def is_debugger_present():
    """检测常见逆向/调试工具进程"""
    try:
        out = _run_cmd(["wmic", "process", "get", "name"])
        if out:
            names_lower = out.lower()
            for name in _DEBUGGER_NAMES:
                if name.lower() in names_lower:
                    return True
    except Exception:
        pass
    return False


# ====================== exe 完整性校验 ======================

_EXPECTED_HASH = None  # PyInstaller 编译时写入


def set_expected_hash(h):
    """打包脚本调用，设置预期的 exe SHA256"""
    global _EXPECTED_HASH
    _EXPECTED_HASH = h


def verify_exe_integrity():
    """自检 exe 文件是否被篡改"""
    if _EXPECTED_HASH is None:
        return True  # 未设置期望值则跳过
    try:
        exe_path = sys.executable
        with open(exe_path, "rb") as f:
            actual = hashlib.sha256(f.read()).hexdigest()
        return actual == _EXPECTED_HASH
    except Exception:
        return False


# ====================== 定时校验 ======================

_TAMPER_DETECTED = False


def _background_license_check(interval_seconds=900):
    """后台线程：定期重新验证 license"""
    global _TAMPER_DETECTED
    while True:
        _time.sleep(interval_seconds)
        valid, msg, remaining = check_license()
        if not valid:
            _TAMPER_DETECTED = True
            break


def start_background_check(interval_seconds=900):
    """启动后台定时校验线程"""
    t = threading.Thread(target=_background_license_check,
                         args=(interval_seconds,), daemon=True)
    t.start()


def is_tampered():
    """检查是否在运行期间被篡改"""
    return _TAMPER_DETECTED
