@echo off
setlocal enabledelayedexpansion

echo ===================================================
echo   Multimodal Biometric System - Environment Setup
echo ===================================================
echo.

:: 1. Check Python installation
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python is not installed or not added to your PATH.
    echo Please install Python 3.8 or higher before running this script.
    pause
    exit /b 1
)

:: 2. Create Virtual Environment
echo [1/3] Creating Python Virtual Environment (venv_demo)...
if not exist "venv_demo" (
    python -m venv venv_demo
    if %errorlevel% neq 0 (
        echo [ERROR] Failed to create the virtual environment.
        pause
        exit /b 1
    )
    echo [+] Virtual environment 'venv_demo' created successfully.
) else (
    echo [+] Virtual environment 'venv_demo' already exists.
)

:: 3. Activate Virtual Environment and Install Dependencies
echo.
echo [2/3] Activating environment and installing dependencies...
call venv_demo\Scripts\activate.bat
if %errorlevel% neq 0 (
    echo [ERROR] Failed to activate the virtual environment.
    pause
    exit /b 1
)

echo [+] Upgrading pip...
python -m pip install --upgrade pip

echo [+] Installing packages from requirements.txt...
python -m pip install -r requirements.txt
if %errorlevel% neq 0 (
    echo [ERROR] Failed to install one or more dependencies. Check the logs above.
    pause
    exit /b 1
)
echo [+] All dependencies installed successfully.

:: 4. Dependency Readiness Check
echo.
echo [3/3] Performing system readiness and dependency check...
python -c "import sys, numpy, pandas, torch, torchvision, cv2, sklearn, tqdm, dlib, PIL, scipy, matplotlib, joblib, urllib.request; print('\n[PASS] All core AI/ML modules successfully imported. System is Ready!\n')"
if %errorlevel% neq 0 (
    echo [ERROR] Dependency check failed. Some modules are missing or failed to import.
    pause
    exit /b 1
)

:: 5. Extract Dlib Model if Needed
echo.
echo [+] Checking for crucial Dlib Shape Predictor Model...
if exist "download_dlib_model.py" (
    python download_dlib_model.py
) else (
    echo [WARN] download_dlib_model.py not found. Make sure the Dlib landmark model is downloaded.
)

echo.
echo ===================================================
echo   Setup Complete!
echo   The system is fully prepared for demonstration.
echo.  
echo   To begin execution, ensure the virtual environment is 
echo   activated: "venv_demo\Scripts\activate"
echo   Then run: "python main.py"
echo ===================================================
pause
