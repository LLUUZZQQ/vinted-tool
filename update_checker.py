# -*- coding: utf-8 -*-
"""
Vinted 抓图工具 — 在线更新模块
从远程 URL 获取最新版本信息，下载并替换 exe。
"""
import os
import sys
import json
import hashlib
import tempfile
import urllib.request
import subprocess

# 更新检查 URL（替换为你实际的文件地址）
# 该 URL 应返回 JSON：{"version": "2.0.0", "download_url": "...", "changelog": "..."}
UPDATE_URL = "https://vt-proxy.vtmax.workers.dev/update.json"

# 当前版本
CURRENT_VERSION = "2.7.5"


def _fetch_json(url, timeout=10):
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "VintedScraper/1.0"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception:
        return None


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
    下载新版本 exe 到临时文件。
    返回临时文件路径，失败返回 None。
    """
    try:
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".exe")
        req = urllib.request.Request(download_url, headers={"User-Agent": "VintedScraper/1.0"})
        with urllib.request.urlopen(req, timeout=300) as resp:
            total = resp.headers.get("Content-Length")
            total = int(total) if total else 0
            downloaded = 0
            while True:
                chunk = resp.read(8192)
                if not chunk:
                    break
                tmp.write(chunk)
                downloaded += len(chunk)
                if progress_callback and total > 0:
                    progress_callback(downloaded, total)
        tmp.close()
        return tmp.name
    except Exception as e:
        return None


def apply_update(new_exe_path):
    """
    替换当前 exe 并重启。
    生成一个批处理脚本，等待当前进程退出后替换文件，然后重新启动。
    """
    exe_dir = os.path.dirname(sys.executable)
    current_exe = sys.executable
    backup = current_exe + ".old"
    bat_path = os.path.join(exe_dir, "_update.bat")

    bat = f"""@echo off
chcp 65001 >nul
echo 正在更新 Vinted 抓图工具...
timeout /t 2 /nobreak >nul
:retry
del "{backup}" 2>nul
move "{current_exe}" "{backup}" >nul 2>&1
move "{new_exe_path}" "{current_exe}" >nul 2>&1
if exist "{current_exe}" (
    echo 更新完成，正在启动...
    start "" "{current_exe}"
    del "%~f0" 2>nul
    exit
)
echo 重试中...
timeout /t 2 /nobreak >nul
goto retry
"""
    with open(bat_path, "w", encoding="utf-8") as f:
        f.write(bat)

    # 启动更新脚本，退出当前进程
    subprocess.Popen(
        ["cmd.exe", "/c", bat_path],
        creationflags=subprocess.CREATE_NEW_CONSOLE if hasattr(subprocess, "CREATE_NEW_CONSOLE") else 0,
        shell=True
    )
    os._exit(0)
