@echo off
cd /d "%~dp0"
".venv\Scripts\python.exe" main.py >> bot-bsc-task.log 2>> bot-bsc-task.err.log
