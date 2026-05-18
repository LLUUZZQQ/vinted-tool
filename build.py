"""单独的打包脚本，双击运行即可"""
import subprocess, sys, os, shutil

os.chdir(os.path.dirname(os.path.abspath(__file__)))

# 清理
for d in ['dist', 'build']:
    if os.path.exists(d):
        try: shutil.rmtree(d)
        except: pass

# 打包
print("Building...")
result = subprocess.run(
    [sys.executable, '-m', 'PyInstaller', 'vinted_build.spec'],
    capture_output=True, text=True
)
print(result.stdout[-2000:] if result.stdout else "(no stdout)")
if result.stderr:
    print("STDERR:", result.stderr[-500:])
print(f"\nExit: {result.returncode}")

if os.path.exists('dist/VintedTool.exe'):
    size = os.path.getsize('dist/VintedTool.exe')
    print(f"SUCCESS: dist/VintedTool.exe ({size//1024//1024}MB)")
else:
    print("FAILED: No exe produced")
input("Press Enter...")
