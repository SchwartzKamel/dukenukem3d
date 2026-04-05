@echo off
title Duke Nukem 3D Launcher
echo ============================================
echo  Duke Nukem 3D - Modern Port
echo ============================================
echo.

REM Check for required files
set MISSING=0

if not exist "%~dp0duke3d.exe" (
    echo ERROR: duke3d.exe not found!
    set MISSING=1
)
if not exist "%~dp0SDL2.dll" (
    echo ERROR: SDL2.dll not found!
    echo   This file should be in the same folder as duke3d.exe
    set MISSING=1
)
if not exist "%~dp0DUKE3D.GRP" (
    echo ERROR: DUKE3D.GRP not found!
    echo   This file should be in the same folder as duke3d.exe
    set MISSING=1
)

if %MISSING%==1 (
    echo.
    echo Please make sure all files from the release zip are extracted
    echo to the same folder.
    echo.
    pause
    exit /b 1
)

echo All required files found.
echo Starting Duke Nukem 3D...
echo.

REM Run the game from its directory
cd /d "%~dp0"
duke3d.exe %*
set EXITCODE=%ERRORLEVEL%

echo.
echo Duke Nukem 3D exited with code: %EXITCODE%

if exist duke3d_startup.log (
    echo.
    echo === Startup Log ===
    type duke3d_startup.log
    echo.
)

if %EXITCODE% NEQ 0 (
    echo.
    echo The game exited with an error. Check above for details.
)

echo.
pause
