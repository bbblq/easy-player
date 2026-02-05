@echo off
echo ========================================================
echo          EasyPlayer Single File Build (Bundled)
echo ========================================================
echo.

:: Ensure ffmpeg exists
if not exist "ffmpeg.exe" (
    echo [ERROR] ffmpeg.exe not found! 
    echo Please run 'python download_ffmpeg.py' first or copy ffmpeg.exe here.
    echo Exiting...
    pause
    exit /b 1
)

echo [INFO] FFmpeg found! Bundling into single executable...
echo.
echo Building...
echo.

:: Using --onefile to create a single exe
:: Using --add-data "source;dest" for windows
pyinstaller --noconfirm --onefile --windowed --name "EasyPlayer" ^
    --icon "assets/icon.ico" ^
    --add-data "assets;assets" ^
    --add-data "ffmpeg.exe;." ^
    --add-data "ffprobe.exe;." ^
    main.py

echo.
echo ========================================================
if %errorlevel% neq 0 (
    echo [ERROR] Build Failed!
    pause
    exit /b %errorlevel%
) else (
    echo [SUCCESS] Build Complete! 
    echo Single EXE is located at: dist\EasyPlayer.exe
)
echo ========================================================
pause
