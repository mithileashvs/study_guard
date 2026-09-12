@echo off
REM ---------------------------------------------------------------------
REM Study Guard -- one-click startup script.
REM
REM What this does:
REM   1. Activates the venv (assumed at <project root>\venv, i.e. the
REM      same folder this .bat file lives in -- adjust VENV_DIR below
REM      if yours is somewhere else).
REM   2. Switches into desktop-agent\ and runs launcher.py, which:
REM        - builds the frontend if it hasn't been built yet
REM        - starts the Flask API + all monitor threads
REM        - opens your browser to http://127.0.0.1:8000 once it's up
REM
REM Double-click this file, or right-click -> "Create shortcut" and
REM drop that shortcut into your Windows Startup folder
REM (Win+R -> shellstartup) if you want Study Guard to launch every
REM time you log in.
REM ---------------------------------------------------------------------

setlocal

REM Directory this .bat file is in (the project root), regardless of
REM where it's double-clicked from.
set PROJECT_DIR=%~dp0
set VENV_DIR=%PROJECT_DIR%venv

title Study Guard

if exist "%VENV_DIR%\Scripts\activate.bat" (
    echo Activating virtual environment...
    call "%VENV_DIR%\Scripts\activate.bat"
) else (
    echo WARNING: no venv found at "%VENV_DIR%".
    echo Continuing with the system Python instead -- if Study Guard's
    echo dependencies aren't installed globally, this will fail.
    echo ^(Edit VENV_DIR at the top of this file if your venv lives
    echo  somewhere else.^)
)

cd /d "%PROJECT_DIR%desktop-agent"

echo.
echo Starting Study Guard...
echo   Web UI:  http://127.0.0.1:8000
echo   Press Ctrl+C in this window to stop.
echo.

python launcher.py

REM Keep the window open after Study Guard exits (normal shutdown or a
REM crash) so any error message stays visible instead of the window
REM just vanishing.
echo.
echo Study Guard has stopped.
pause
