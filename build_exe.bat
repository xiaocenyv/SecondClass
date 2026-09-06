@echo off
rem 一键打包 SecondClass.exe（需要本机 Python 3.10+）
cd /d %~dp0

echo [1/3] 安装依赖（requests / pycryptodome / pillow / pyinstaller）...
python -m pip install -r requirements.txt pillow pyinstaller || goto :err

echo [2/3] 生成图标...
python scripts\make_icon.py || goto :err

echo [3/3] PyInstaller 打包...
python -m PyInstaller --noconfirm --clean --onefile --windowed ^
  --name SecondClass --icon assets\app.ico ^
  --version-file version_info.txt app.py || goto :err

echo.
echo 打包完成: dist\SecondClass.exe
pause
exit /b 0

:err
echo.
echo 打包失败，请检查上方错误信息。
pause
exit /b 1
