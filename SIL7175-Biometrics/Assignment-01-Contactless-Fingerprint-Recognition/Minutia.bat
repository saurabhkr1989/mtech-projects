@echo off
REM --- CRYPTO/BIO SECURITY BUILD SCRIPT ---
REM Course: M.Tech Cryptography & Cyber Security
REM Purpose: Automated Environment Setup & Secure Compilation

REM 1. CONFIGURATION (Update this path to your actual SDK location)
REM NOTE: Based on your log, your path is C:\VeriFinger. Ensure this matches!
set SDK_ROOT=C:\VeriFinger

REM 2. PROJECT SETTINGS
set SOURCE_FILE=MinutiaeExtractor.cpp
set OUT_EXE=MinutiaeExtractor.exe

REM 3. ENVIRONMENT CHECK & AUTO-LOAD
echo [System] Checking for C++ Compiler (cl.exe)...
where cl >nul 2>nul
if %errorlevel% neq 0 (
    echo [Env] Compiler not found in current path.
    echo [Env] Attempting to auto-load Visual Studio Developer Tools...
    call :SetupVSEnvironment
)

REM 4. VERIFY ENVIRONMENT AGAIN
where cl >nul 2>nul
if %errorlevel% neq 0 (
    echo.
    echo [CRITICAL ERROR] Visual Studio Build Tools not found!
    echo -----------------------------------------------------------
    echo SOLUTION:
    echo 1. Press Windows Key, type "Developer Command Prompt".
    echo 2. Open "Developer Command Prompt for VS 2022".
    echo 3. Run this script again from that window.
    echo -----------------------------------------------------------
    exit /b 1
)

echo [System] Compiler detected. Starting Secure Build...
echo [Config] SDK Path: %SDK_ROOT%

REM 5. COMPILATION COMMAND
REM /EHsc = Exception Handling
REM /std:c++14 = Language Standard
REM /I = Include Headers
REM /link /LIBPATH = Link Security Modules

cl /nologo /EHsc /std:c++14 %SOURCE_FILE% ^
   /I "%SDK_ROOT%\Include" ^
   /link /LIBPATH:"%SDK_ROOT%\Lib\Win64_x64" ^
   NCore.dll.lib NBiometrics.dll.lib NBiometricClient.dll.lib NMedia.dll.lib NLicensing.dll.lib ^
   /OUT:%OUT_EXE%

REM 6. CHECK STATUS
if %errorlevel% neq 0 (
    echo.
    echo [Error] Build Failed. Check the SDK path or code errors.
    exit /b %errorlevel%
)

echo.
echo [Success] Artifact Generated: %OUT_EXE%
echo [Tip] Run it using: %OUT_EXE% "finger.jpg"
exit /b 0

REM --- HELPER FUNCTIONS ---
:SetupVSEnvironment
REM Try to find VS 2022 Community/Pro/Ent
if exist "C:\Program Files\Microsoft Visual Studio\2022\Community\VC\Auxiliary\Build\vcvars64.bat" (
    call "C:\Program Files\Microsoft Visual Studio\2022\Community\VC\Auxiliary\Build\vcvars64.bat"
    exit /b 0
)
if exist "C:\Program Files\Microsoft Visual Studio\2022\Professional\VC\Auxiliary\Build\vcvars64.bat" (
    call "C:\Program Files\Microsoft Visual Studio\2022\Professional\VC\Auxiliary\Build\vcvars64.bat"
    exit /b 0
)
if exist "C:\Program Files\Microsoft Visual Studio\2022\Enterprise\VC\Auxiliary\Build\vcvars64.bat" (
    call "C:\Program Files\Microsoft Visual Studio\2022\Enterprise\VC\Auxiliary\Build\vcvars64.bat"
    exit /b 0
)

REM Try to find VS 2019
if exist "C:\Program Files (x86)\Microsoft Visual Studio\2019\Community\VC\Auxiliary\Build\vcvars64.bat" (
    call "C:\Program Files (x86)\Microsoft Visual Studio\2019\Community\VC\Auxiliary\Build\vcvars64.bat"
    exit /b 0
)
REM If we get here, we couldn't find it automatically.
exit /b 1