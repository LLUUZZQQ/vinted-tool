@echo off
echo Test 1: python --version
C:\Users\LUZQ\AppData\Local\Programs\Python\Python310\python.exe --version > test_log.txt 2>&1
echo Exit: %ERRORLEVEL%
type test_log.txt
echo.
echo Test 2: import PyInstaller
C:\Users\LUZQ\AppData\Local\Programs\Python\Python310\python.exe -c "import PyInstaller; print('OK')" >> test_log.txt 2>&1
echo Exit: %ERRORLEVEL%
type test_log.txt
pause
