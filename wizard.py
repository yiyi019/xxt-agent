# -*- coding: utf-8 -*-
"""
Interactive setup wizard and configuration guide for Xuexitong Agent.
Ensures zero-friction, out-of-the-box (开箱即用) setup for users and AI agents.
"""

import getpass
import json
import logging
import os
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

from xxt_agent.config import XXTConfig

logger = logging.getLogger(__name__)


def is_configured(config: XXTConfig) -> bool:
    """Checks whether the agent has minimum required configuration to run."""
    has_credentials = bool(config.phone_number and config.password)
    if not has_credentials:
        return False
    if config.quiz_solve_mode == "ai" and not config.api_key:
        return False
    return True


def prompt_input(prompt_text: str, default: Optional[str] = None, is_password: bool = False) -> str:
    """Helper to prompt user input with defaults in terminal."""
    if default:
        suffix = f" [默认: {default}]: "
    else:
        suffix = ": "

    full_prompt = prompt_text + suffix
    try:
        if is_password and sys.stdin.isatty():
            val = getpass.getpass(full_prompt)
        else:
            val = input(full_prompt)
    except (EOFError, KeyboardInterrupt):
        print("\n[向导已取消]")
        sys.exit(0)

    val = val.strip()
    return val if val else (default or "")


def run_interactive_wizard(config: Optional[XXTConfig] = None) -> XXTConfig:
    """
    Guides the user interactively through 4 quick steps:
    1. Credentials (phone, password)
    2. AI Quiz solving (DeepSeek key, mode)
    3. Course Queue (multi-course schedule)
    4. Display mode (GUI, Headless, TUI)
    Saves everything to config.json once.
    """
    if sys.stdout and hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

    config = config or XXTConfig.load()

    print("=" * 64)
    print("      🚀 学习通自动化 Agent 开箱即用配置向导 (Setup Wizard)")
    print("=" * 64)
    print("只需一次配置即可保存，后续可全自动后台/可视化/多门排队刷课。\n")

    # 1. 登录凭据
    print("【第一步：学习通账号与登录方式】")
    phone = prompt_input("1. 学习通绑定手机号", default=config.phone_number)
    pwd = prompt_input("2. 学习通登录密码", default=config.password, is_password=False)
    browser = prompt_input("3. 浏览器内核 (edge / chrome)", default=config.browser or "edge").lower()
    if browser not in ["edge", "chrome"]:
        browser = "edge"

    config.phone_number = phone
    config.password = pwd
    config.browser = browser

    # 2. 章节测验与 AI 答题
    print("\n【第二步：章节测验与 AI 答题策略】")
    print("   1: 开启 DeepSeek AI 智能答题 (推荐，结合字体反混淆自动满分/高分提交)")
    print("   2: 跳过章节测验 (不刷题，只刷视频与阅读)")
    quiz_choice = prompt_input("请选择章节测验处理方式 (1 或 2)", default="1" if config.quiz_solve_mode != "skip" else "2")

    if quiz_choice == "2":
        config.quiz_solve_mode = "skip"
        print("-> 已设定：跳过章节测验，仅自动化刷视频/阅读任务点。")
    else:
        config.quiz_solve_mode = "ai"
        api_key_default = config.api_key or ""
        masked_default = (api_key_default[:6] + "..." + api_key_default[-4:]) if len(api_key_default) > 10 else api_key_default
        key_input = prompt_input(
            "请输入 DeepSeek API Key (回车保留现有)",
            default=masked_default
        )
        if key_input and key_input != masked_default:
            config.api_key = key_input.strip()

        config.api_model = prompt_input("DeepSeek 模型名称", default=config.api_model or "deepseek-flash")
        config.api_base_url = prompt_input("DeepSeek Base URL", default=config.api_base_url or "https://api.deepseek.com")

    # 3. 课程代办排队表 (Multi-course queue)
    print("\n【第三步：课程代办排队表 (待刷课程队列)】")
    print("可输入多门课程，单门课今日时长满时将自动无缝平滑切换到下一门。")
    print("示例: 艺术鉴赏, 传统文化, 心理健康教育")
    existing_courses = ", ".join(config.default_courses) if config.default_courses else "艺术鉴赏"
    courses_raw = prompt_input("要刷的课程列表 (以逗号或空格隔开)", default=existing_courses)

    parsed_courses = [c.strip() for c in re.split(r"[,;，；\s]+", courses_raw) if c.strip()]
    if not parsed_courses:
        parsed_courses = ["艺术鉴赏"]
    config.default_courses = parsed_courses
    print(f"-> 待刷课程排队列表: {parsed_courses}")

    # 4. 运行方式偏好
    print("\n【第四步：刷课运行模式与显示方式】")
    print("   1: 可视化浏览器界面 (GUI, 实时看到浏览器播放，适合前台观察)")
    print("   2: 纯后台静默运行 (Headless, 无界面不遮挡屏幕，适合无人值守挂机)")
    print("   3: 终端动态仪表盘 (TUI, 命令行富文本实时面板)")
    mode_choice = prompt_input("请选择模式 (1, 2, 3)", default="1" if not config.headless else "2")

    if mode_choice == "1":
        config.headless = False
        mode_name = "可视化浏览器界面 (GUI)"
    elif mode_choice == "3":
        config.headless = False
        mode_name = "终端动态仪表盘 (TUI)"
    else:
        config.headless = True
        mode_name = "纯后台静默模式 (Headless)"

    # 5. 保存并展示
    config.save()
    print("\n" + "=" * 64)
    print("      🎉 配置保存成功！(Config Successfully Saved)")
    print("=" * 64)
    print(f"  • 账号: {config.phone_number}")
  
    print(f"  • 浏览器: {config.browser}")
    print(f"  • 测验答题: {config.quiz_solve_mode} ({'AI 模型: ' + config.api_model if config.quiz_solve_mode == 'ai' else '已跳过'})")
    print(f"  • 课程排队代办: {' -> '.join(config.default_courses)}")
    print(f"  • 运行模式: {mode_name}")
    print("=" * 64)
    print("配置文件已持久化至: xxt_agent/config.json")
    print("后续可随时通过桌面的快捷方式启动，或使用命令:")
    print("  python -m xxt_agent.cli run")
    print("=" * 64 + "\n")

    return config


def check_and_prompt_if_unconfigured(config: Optional[XXTConfig] = None) -> XXTConfig:
    """Auto-detects unconfigured settings before run, invoking wizard if needed."""
    config = config or XXTConfig.load()
    if not config.phone_number or not config.password:
        if sys.stdin.isatty():
            print("[提示] 检测到学习通账号尚未配置，正在启动快速初始化向导...")
            config = run_interactive_wizard(config)
        else:
            raise RuntimeError("系统未配置账号密码，请先在终端运行 'python -m xxt_agent.cli wizard' 进行初始化。")
    return config
