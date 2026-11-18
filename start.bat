@echo off
title SkillSync - Student Skill and Project Team Finder
cd /d "%~dp0"

echo =====================================================================
echo          SkillSync: Student Skill ^& Project Team Finder
echo          BMS Institute of Technology ^& Management - CSE 13
echo =====================================================================
echo.

:: Check for Python virtual environment
if not exist "venv\Scripts\python.exe" (
    echo [INFO] Virtual environment not found. Setting up venv...
    python -m venv venv
    if errorlevel 1 (
        echo [ERROR] Failed to create virtual environment. Please check your Python installation.
        pause
        exit /b 1
    )
    echo [INFO] Installing required packages...
    .\venv\Scripts\python.exe -m pip install -r requirements.txt
    if errorlevel 1 (
        echo [ERROR] Failed to install packages.
        pause
        exit /b 1
    )
)

:: Check if database is initialized
if not exist "skillsync.db" (
    echo [INFO] Initializing and seeding database with BMSIT^&M CSE 13 cohort data...
    .\venv\Scripts\python.exe seed.py
)

echo.
echo [INFO] Starting SkillSync Web Application...
echo [INFO] Access the platform at: http://127.0.0.1:5000
echo [INFO] Launching browser in 2 seconds...

:: Launch browser in background after short delay
start "" cmd /c "timeout /t 2 /nobreak >nul && start http://127.0.0.1:5000"

echo.
echo [READY] Server running. Press Ctrl+C in this window to stop.
echo.

.\venv\Scripts\python.exe run.py

if errorlevel 1 (
    echo.
    echo [ERROR] Server encountered an issue.
    pause
)
