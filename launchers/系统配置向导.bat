@echo off
chcp 65001 >nul
title 学习通自动化 - 开箱即用交互配置向导
cd /d D:\Xuexitong_shuake
set PYTHONPATH=D:\Xuexitong_shuake
set PYTHONIOENCODING=utf-8
C:\Users\yiyi\miniconda3\python.exe -m xxt_agent.cli wizard
pause
