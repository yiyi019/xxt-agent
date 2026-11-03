@echo off
chcp 65001 >nul
title 学习通前台可视化刷课 (1.0x 倍速)
cd /d D:\Xuexitong_shuake
set PYTHONPATH=D:\Xuexitong_shuake
set PYTHONIOENCODING=utf-8
echo ========================================================
echo       🚀 学习通前台可视化刷课 (桌面独立浏览器窗口)
echo ========================================================
echo.
set /p course_name="请输入要刷的课程名称 [直接回车默认: 音乐鉴赏]: "
if "%course_name%"=="" set course_name=音乐鉴赏
echo.
echo 正在为您启动 Edge 浏览器窗口，执行课程: %course_name% ...
echo.
C:\Users\yiyi\miniconda3\python.exe -m xxt_agent.cli run --course "%course_name%" --gui --speed 1.0
pause
