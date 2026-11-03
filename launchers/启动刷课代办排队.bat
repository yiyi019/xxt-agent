@echo off
chcp 65001 >nul
title 学习通自动化 - 课程代办排队表 (自动换课)

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
echo ========================================================
echo       🚀 学习通多门课程排队代办运行器 (自动换课)
echo  单门课程达今日时长上限后，将自动平滑切换至下一门代办课程
echo ========================================================
echo.
set /p q_courses="请输入排队课程以空格隔开 [回车默认: 音乐鉴赏 艺术鉴赏 大学生心理健康教育]: "
if "%q_courses%"=="" set q_courses=音乐鉴赏 艺术鉴赏 大学生心理健康教育
echo.
echo 正在启动前台排队表: %q_courses% ...
echo.
python -m xxt_agent.cli queue run --courses %q_courses% --gui --speed 1.0
pause
