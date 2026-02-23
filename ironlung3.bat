@echo off
title IronLung 3
cd /d "%~dp0"
python ironlung3.py %*
if errorlevel 1 pause
