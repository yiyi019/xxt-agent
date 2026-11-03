@echo off
chcp 65001 >nul
title 学习通自动化 - 开箱即用交互配置向导

:: 动态定位项目路径 (支持直接运行或作为快捷方式运行)
set "CURRENT_DIR=%~dp0"
if exist "%CURRENT_DIR%xxt_agent" (
    cd /d "%CURRENT_DIR%"
) else if exist "%CURRENT_DIR%..\xxt_agent" (
    cd /d "%CURRENT_DIR%.."
) else (
    cd /d "%CURRENT_DIR%"
)

set "PYTHONPATH=%cd%"
set PYTHONIOENCODING=utf-8
python -m xxt_agent.cli wizard
pause
