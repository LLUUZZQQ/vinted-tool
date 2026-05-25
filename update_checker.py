# -*- coding: utf-8 -*-
"""
Vinted 抓图工具 — 在线更新模块
从远程 URL 获取最新版本信息，下载并替换 exe。
"""
import os
import sys
import json
import hashlib
import urllib.request
import urllib.error
import subprocess

# 更新检查 URL（替换为你实际的文件地址）
# 该 URL 应返回 JSON：{"version": "2.0.0", "download_url": "...", "changelog": "..."}
UPDATE_URL = "https://vt-proxy.vtmax.workers.dev/update.json"

# 当前版本
CURRENT_VERSION = "3.6.16"
_last_error = ""  # 最近一次下载错误信息


def _fetch_json(url, timeout=10):
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "ImageMAX/1.0"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.URLError as e:
        return {"_error": f"网络错误：{e.reason}"}
    except (json.JSONDecodeError, UnicodeDecodeError):
        return {"_error": "响应格式异常"}
    except Exception as e:
        return {"_error": f"检查失败：{e}"}


def check_for_update():
    """
    检查是否有新版本。
    返回 (has_update: bool, version: str, changelog: str, download_url: str)
    """
    data = _fetch_json(UPDATE_URL)
    if not data:
        return False, CURRENT_VERSION, "", ""
    remote_version = data.get("version", "0")
    try:
        remote_parts = [int(x) for x in remote_version.split(".")]
        local_parts = [int(x) for x in CURRENT_VERSION.split(".")]
        if remote_parts > local_parts:
            return True, remote_version, data.get("changelog", ""), data.get("download_url", "")
    except Exception:
        pass
    return False, CURRENT_VERSION, "", ""


def download_update(download_url, progress_callback=None):
    """
    下载新版本 exe 到程序同目录。
    返回临时文件路径，失败返回 None。
    """
    try:
        exe_dir = os.path.dirname(sys.executable)
        tmp_path = os.path.join(exe_dir, "_update_new.exe")
        # 清理上次残留
        for f in [tmp_path, os.path.join(exe_dir, "_update.old")]:
            if os.path.exists(f):
                try:
                    os.remove(f)
                except:
                    pass
        req = urllib.request.Request(download_url, headers={"User-Agent": "ImageMAX/1.0"})
        with urllib.request.urlopen(req, timeout=600) as resp:
            total = resp.headers.get("Content-Length")
            total = int(total) if total else 0
            downloaded = 0
            with open(tmp_path, "wb") as f:
                while True:
                    chunk = resp.read(65536)
                    if not chunk:
                        break
                    f.write(chunk)
                    downloaded += len(chunk)
                    if progress_callback and total > 0:
                        progress_callback(downloaded, total)
        # 校验文件完整性
        if total > 0:
            actual = os.path.getsize(tmp_path)
            if actual < total * 0.95:
                os.remove(tmp_path)
                return None
        return tmp_path
    except Exception as e:
        global _last_error
        _last_error = str(e)[:200]
        if os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except Exception:
                pass
        return None


def apply_update(new_exe_path):
    """
    替换当前 exe 并重启。
    使用 copy 替代 move（同盘 copy 可靠），校验后删除旧版。
    """
    exe_dir = os.path.dirname(sys.executable)
    current_exe = sys.executable
    backup = os.path.join(exe_dir, "_update.old")
    bat_path = os.path.join(exe_dir, "_update.bat")
    # 转义路径中的特殊字符（延迟变量 ! 和转义符 ^）
    safe_current = current_exe.replace("^", "^^").replace("!", "^^!")
    safe_backup = backup.replace("^", "^^").replace("!", "^^!")
    safe_new = new_exe_path.replace("^", "^^").replace("!", "^^!")

    bat = f"""@echo off
chcp 65001 >nul
set retry=0
echo 正在更新...
timeout /t 2 /nobreak >nul
:retry
set /a retry+=1
if %retry% gtr 5 (
    echo 更新失败，请重启软件后重试
    pause
    del "{safe_backup}" 2>nul
    exit /b 1
)
del "{safe_backup}" 2>nul
rename "{safe_current}" "_update.old" >nul 2>&1
copy /y "{safe_new}" "{safe_current}" >nul 2>&1
if exist "{safe_current}" (
    echo 更新完成，正在启动...
    del "{safe_new}" 2>nul
    start "" "{safe_current}"
    del "%~f0" 2>nul
    exit
)
echo 重试中...
timeout /t 2 /nobreak >nul
goto retry
"""
    with open(bat_path, "w", encoding="utf-8") as f:
        f.write(bat)

    subprocess.Popen(
        ["cmd.exe", "/c", bat_path],
        creationflags=subprocess.CREATE_NEW_CONSOLE if hasattr(subprocess, "CREATE_NEW_CONSOLE") else 0,
        shell=True
    )
    os._exit(0)
