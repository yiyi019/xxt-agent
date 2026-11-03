@echo off
chcp 65001 >nul
title 学习通自动化 - 课程代办排队表 (自动换课)
cd /d D:\Xuexitong_shuake
set PYTHONPATH=D:\Xuexitong_shuake
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
C:\Users\yiyi\miniconda3\python.exe -m xxt_agent.cli queue run --courses %q_courses% --gui --speed 1.0
pause
