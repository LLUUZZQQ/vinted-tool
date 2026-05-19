"""高清截图脚本"""
import os, io, time
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from PIL import Image

here = os.path.dirname(os.path.abspath(__file__))
html_path = os.path.join(here, '宣传图.html')

opts = Options()
opts.add_argument('--headless=new')
opts.add_argument('--force-device-scale-factor=2')
opts.add_argument('--window-size=750,2000')

driver = webdriver.Chrome(service=Service(os.path.join(here, 'chromedriver.exe')), options=opts)
driver.get('file:///' + html_path.replace('\\', '/'))
time.sleep(1.5)

el = driver.find_element('css selector', '.poster')
png = el.screenshot_as_png
driver.quit()

img = Image.open(io.BytesIO(png))
out = os.path.join(here, '宣传图.png')
img.save(out, 'PNG')
print(f'Done: {img.width}x{img.height}')
