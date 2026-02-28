@echo off
title IronLung 3 — Update
cd /d "%~dp0"

echo ============================================
echo   IronLung 3 — Pulling Latest Code
echo ============================================
echo.

REM --- Fix the git remote if it points at a sandbox proxy ---
for /f "tokens=*" %%u in ('git remote get-url origin 2^>nul') do set "REMOTE_URL=%%u"

echo Current remote: %REMOTE_URL%

echo %REMOTE_URL% | findstr /i "127.0.0.1" >nul 2>&1
if %errorlevel%==0 (
    echo Detected sandbox proxy — fixing remote...
    git remote set-url origin https://github.com/SodieTX/IronLungThree.git
    echo Remote reset to GitHub.
) else (
    echo %REMOTE_URL% | findstr /i "github.com" >nul 2>&1
    if %errorlevel% neq 0 (
        echo Remote doesn't point to GitHub — fixing...
        git remote set-url origin https://github.com/SodieTX/IronLungThree.git
        echo Remote reset to GitHub.
    ) else (
        echo Remote OK.
    )
)

echo.

REM --- Make sure we're on main ---
echo Switching to main branch...
git checkout main
if %errorlevel% neq 0 (
    echo ERROR: Could not switch to main. You may have uncommitted changes.
    echo Try: git stash   then re-run this script.
    pause
    exit /b 1
)

echo.

REM --- Pull latest ---
echo Pulling latest from GitHub...
git pull origin main
if %errorlevel% neq 0 (
    echo.
    echo ERROR: Pull failed. Trying harder...
    git fetch origin main
    git reset --hard origin/main
)

echo.

REM --- Install any new dependencies ---
echo Checking dependencies...
pip install -r requirements.txt --quiet 2>nul
if %errorlevel% neq 0 (
    echo Note: pip install had issues — you may need to run it manually.
) else (
    echo Dependencies OK.
)

echo.
echo ============================================
echo   Update complete! You can now run the app.
echo ============================================
echo.
pause
