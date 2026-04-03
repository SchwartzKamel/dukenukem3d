@echo off
REM Duke3D: Neon Noir - Windows Native Build Script
REM Requires: Visual Studio Build Tools OR MinGW-w64, plus SDL2 development libraries
REM
REM Usage:
REM   build_windows.bat          - Build with auto-detected compiler
REM   build_windows.bat msvc     - Force MSVC
REM   build_windows.bat mingw    - Force MinGW

setlocal enabledelayedexpansion

echo ===================================
echo  Duke3D: Neon Noir - Windows Build
echo ===================================
echo.

REM Check for SDL2
if not defined SDL2_DIR (
    echo SDL2_DIR not set. Checking common locations...
    if exist "C:\SDL2\include\SDL.h" set SDL2_DIR=C:\SDL2
    if exist "%USERPROFILE%\SDL2\include\SDL.h" set SDL2_DIR=%USERPROFILE%\SDL2
    if exist ".\SDL2\include\SDL.h" set SDL2_DIR=.\SDL2
)

if not defined SDL2_DIR (
    echo.
    echo ERROR: SDL2 not found!
    echo.
    echo Download SDL2 development libraries from: https://github.com/libsdl-org/SDL/releases
    echo Extract to C:\SDL2 or set SDL2_DIR environment variable
    echo You need SDL2-devel-X.XX.X-VC.zip for MSVC or SDL2-devel-X.XX.X-mingw.zip for MinGW
    exit /b 1
)

echo SDL2 found at: %SDL2_DIR%

set COMPILER=%1
if "%COMPILER%"=="" (
    REM Auto-detect
    where cl >nul 2>&1
    if !errorlevel! equ 0 (
        set COMPILER=msvc
    ) else (
        where gcc >nul 2>&1
        if !errorlevel! equ 0 (
            set COMPILER=mingw
        ) else (
            echo ERROR: No compiler found! Install Visual Studio Build Tools or MinGW-w64.
            exit /b 1
        )
    )
)

echo Using compiler: %COMPILER%
echo.

if not exist build_win mkdir build_win

if "%COMPILER%"=="msvc" goto :build_msvc
if "%COMPILER%"=="mingw" goto :build_mingw
echo ERROR: Unknown compiler "%COMPILER%". Use "msvc" or "mingw".
exit /b 1

:build_msvc
echo --- Building with MSVC ---
set CC=cl
set CFLAGS=/nologo /O2 /W0 /DSUPERBUILD /DPLATFORM_WIN32 /D_CRT_SECURE_NO_WARNINGS
set SDL_INC=/I"%SDL2_DIR%\include"
set SDL_LIB=/LIBPATH:"%SDL2_DIR%\lib\x64"
set INCLUDES=/Icompat /ISRC /Isource
set LIBS=SDL2.lib SDL2main.lib shell32.lib

REM Engine objects
echo Compiling ENGINE.C...
%CC% %CFLAGS% %SDL_INC% %INCLUDES% /DENGINE /c /Tc SRC\ENGINE.C /Fo:build_win\engine_ENGINE.obj
if errorlevel 1 goto :fail
echo Compiling CACHE1D.C...
%CC% %CFLAGS% %SDL_INC% %INCLUDES% /c /Tc SRC\CACHE1D.C /Fo:build_win\engine_CACHE1D.obj
if errorlevel 1 goto :fail
echo Compiling MMULTI.C...
%CC% %CFLAGS% %SDL_INC% %INCLUDES% /c /Tc SRC\MMULTI.C /Fo:build_win\engine_MMULTI.obj
if errorlevel 1 goto :fail

REM Game objects
for %%f in (GAME ACTORS GAMEDEF GLOBAL MENUES PLAYER PREMAP SECTOR SOUNDS RTS CONFIG ANIMLIB) do (
    echo Compiling %%f.C...
    %CC% %CFLAGS% %SDL_INC% %INCLUDES% /c /Tc source\%%f.C /Fo:build_win\game_%%f.obj
    if errorlevel 1 goto :fail
)

REM Compat objects
for %%f in (sdl_driver audio_stub mact_stub) do (
    echo Compiling %%f.c...
    %CC% /nologo /O2 /W3 /D_CRT_SECURE_NO_WARNINGS %SDL_INC% %INCLUDES% /c compat\%%f.c /Fo:build_win\compat_%%f.obj
    if errorlevel 1 goto :fail
)

REM Link
echo.
echo Linking duke3d.exe...
set OBJS=build_win\*.obj
link /nologo /OUT:duke3d.exe %OBJS% %SDL_LIB% %LIBS% /SUBSYSTEM:CONSOLE
if errorlevel 1 goto :fail
echo.
echo Build complete: duke3d.exe
goto :done

:build_mingw
echo --- Building with MinGW ---
set CC=gcc
set CFLAGS=-std=gnu89 -O2 -w -DSUPERBUILD -DPLATFORM_WIN32
set SDL_INC=-I"%SDL2_DIR%\x86_64-w64-mingw32\include\SDL2"
set SDL_LIB=-L"%SDL2_DIR%\x86_64-w64-mingw32\lib"
set INCLUDES=-Icompat -ISRC -Isource
set LIBS=%SDL_LIB% -lmingw32 -lSDL2main -lSDL2 -lm -lws2_32 -mwindows

REM Engine
echo Compiling ENGINE.C...
%CC% %CFLAGS% %SDL_INC% %INCLUDES% -DENGINE -x c -c SRC\ENGINE.C -o build_win\engine_ENGINE.o
if errorlevel 1 goto :fail
echo Compiling CACHE1D.C...
%CC% %CFLAGS% %SDL_INC% %INCLUDES% -x c -c SRC\CACHE1D.C -o build_win\engine_CACHE1D.o
if errorlevel 1 goto :fail
echo Compiling MMULTI.C...
%CC% %CFLAGS% %SDL_INC% %INCLUDES% -x c -c SRC\MMULTI.C -o build_win\engine_MMULTI.o
if errorlevel 1 goto :fail

REM Game
for %%f in (GAME ACTORS GAMEDEF GLOBAL MENUES PLAYER PREMAP SECTOR SOUNDS RTS CONFIG ANIMLIB) do (
    echo Compiling %%f.C...
    %CC% %CFLAGS% %SDL_INC% %INCLUDES% -x c -c source\%%f.C -o build_win\game_%%f.o
    if errorlevel 1 goto :fail
)

REM Compat
for %%f in (sdl_driver audio_stub mact_stub) do (
    echo Compiling %%f.c...
    %CC% -std=gnu11 -O2 -Wall -DPLATFORM_WIN32 %SDL_INC% %INCLUDES% -c compat\%%f.c -o build_win\compat_%%f.o
    if errorlevel 1 goto :fail
)

REM Link
echo.
echo Linking duke3d.exe...
%CC% build_win\*.o -o duke3d.exe %LIBS%
if errorlevel 1 goto :fail
echo.
echo Build complete: duke3d.exe
goto :done

:fail
echo.
echo BUILD FAILED!
endlocal
exit /b 1

:done
echo.
echo Copy SDL2.dll to the same directory as duke3d.exe to run.
echo Generate assets: python tools\generate_assets.py --no-ai
endlocal
exit /b 0
