"""模拟用户没有Chrome——自动下载便携版并启动"""
import os, sys

# 1. 清除便携版缓存
cache = os.path.join(os.environ["LOCALAPPDATA"], "VTMAX", "chrome")
if os.path.exists(cache):
    import shutil; shutil.rmtree(cache)
    print("[清理] 已删除便携版缓存\n")

# 2. 备份并临时移除 Chrome 注册表
import winreg, shutil
backup_key = None
reg_path = r"Software\Google\Chrome\BLBeacon"
try:
    key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, reg_path, 0, winreg.KEY_READ | winreg.KEY_WRITE)
    backup_key = {}
    i = 0
    while True:
        try:
            n, v, t = winreg.EnumValue(key, i)
            backup_key[n] = (v, t)
            i += 1
        except:
            break
    winreg.CloseKey(key)
    winreg.DeleteKey(winreg.HKEY_CURRENT_USER, reg_path)
    print("[模拟] Chrome 注册表已临时隐藏\n")
except Exception as e:
    print(f"[警告] 注册表操作失败: {e}\n")

try:
    import Vinted_抓图 as be
    be._on_log = lambda c, l: print(f"  [{l}] {c[:100]}")
    be._on_status = lambda t: print(f"  [status] {t}")

    print("="*60)
    print("测试：无 Chrome 环境下启动")
    print("="*60)
    driver = be.init_chrome(True)
    print(f"\nSUCCESS! {driver.title}")
    driver.quit()

finally:
    # 3. 恢复注册表
    if backup_key is not None:
        try:
            key = winreg.CreateKey(winreg.HKEY_CURRENT_USER, reg_path)
            for n, (v, t) in backup_key.items():
                winreg.SetValueEx(key, n, 0, t, v)
            winreg.CloseKey(key)
            print("\n[恢复] Chrome 注册表已还原")
        except Exception as e:
            print(f"\n[警告] 注册表恢复失败: {e}")
