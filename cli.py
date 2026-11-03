# -*- coding: utf-8 -*-
"""
Agent-Optimized Command Line Interface (CLI) for Xuexitong Agent.
Supports deterministic JSON outputs and structured error codes for AI agents.
"""
import os
import sys
import json
import time
import argparse
import threading
import unicodedata
from typing import Any, Optional, List

if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
if sys.stderr and hasattr(sys.stderr, "reconfigure"):
    try:
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from xxt_agent.config import XXTConfig
from xxt_agent.ai_solver import DeepSeekSolver

STATUS_FILE = r"D:\Xuexitong_shuake\live_status.json"

def _sanitize_data(data: Any) -> Any:
    if isinstance(data, str):
        return unicodedata.normalize("NFKC", data).replace("\xa0", " ")
    if isinstance(data, dict):
        return {k: _sanitize_data(v) for k, v in data.items()}
    if isinstance(data, list):
        return [_sanitize_data(x) for x in data]
    return data

def output_result(data: Any, is_json: bool):
    """Output structured data to stdout."""
    data = _sanitize_data(data)
    if is_json:
        out_str = json.dumps(data, ensure_ascii=False, indent=2)
        try:
            print(out_str)
        except UnicodeEncodeError:
            print(out_str.encode("utf-8", errors="replace").decode(sys.stdout.encoding or "utf-8", errors="replace"))
    else:
        if isinstance(data, dict):
            for k, v in data.items():
                print(f"[{k}] {v}")
        elif isinstance(data, list):
            for item in data:
                print(f"- {item}")
        else:
            print(data)

def build_parser() -> argparse.ArgumentParser:
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--json", action="store_true", default=argparse.SUPPRESS, help="Output results strictly in JSON format.")
    common.add_argument("--format", choices=["json", "text"], default=argparse.SUPPRESS, help="Output format.")
    common.add_argument("--gui", action="store_true", default=argparse.SUPPRESS, help="Disable headless mode and show browser UI.")

    parser = argparse.ArgumentParser(
        parents=[common],
        description="Xuexitong Agent CLI - Lightweight course automation optimized for AI agents."
    )

    subparsers = parser.add_subparsers(dest="command", help="Available subcommands")

    # Command: status
    subparsers.add_parser("status", parents=[common], help="Check system readiness, driver, cookies, and AI keys.")

    # Command: live-status
    subparsers.add_parser("live-status", parents=[common], help="Inspect live real-time course playback metrics.")

    # Command: config
    cfg_parser = subparsers.add_parser("config", parents=[common], help="Configuration operations.")
    cfg_parser.add_argument("config_action", nargs="?", default="show", choices=["show"], help="Config action (default: show).")

    # Command: list-courses
    subparsers.add_parser("list-courses", parents=[common], help="Retrieve all enrolled courses under current account.")
    subparsers.add_parser("courses", parents=[common], help="Alias for list-courses.")

    # Command: chapters
    cap_parser = subparsers.add_parser("chapters", parents=[common], help="List chapters for a specific course.")
    cap_parser.add_argument("--course", "-c", required=True, help="Course title to inspect.")

    # Command: run
    run_parser = subparsers.add_parser("run", parents=[common], help="Run automated study on a specified course.")
    run_parser.add_argument("--course", "-c", required=True, help="Course title to run.")
    run_parser.add_argument("--duration", "-d", type=int, default=3600, help="Maximum run duration in seconds (default: 3600).")
    run_parser.add_argument("--speed", "-s", type=float, default=2.0, help="Playback speed (e.g. 1.0, 2.0, 4.0).")
    run_parser.add_argument("--max-chapters", "-m", type=int, default=15, help="Maximum number of chapters to process.")
    run_parser.add_argument("--tui", action="store_true", help="Launch interactive Terminal UI (TUI) dashboard.")

    # Command: tui
    tui_parser = subparsers.add_parser("tui", parents=[common], help="Launch interactive Terminal UI (TUI) dashboard.")
    tui_parser.add_argument("--course", "-c", default="艺术鉴赏", help="Course title to run (default: 艺术鉴赏).")
    tui_parser.add_argument("--speed", "-s", type=float, default=2.0, help="Playback speed (default: 2.0).")
    tui_parser.add_argument("--max-chapters", "-m", type=int, default=15, help="Maximum chapters (default: 15).")

    # Command: solve
    solve_parser = subparsers.add_parser("solve", parents=[common], help="Directly solve a question via DeepSeek AI.")
    solve_parser.add_argument("--question", "-q", required=True, help="Question text.")
    solve_parser.add_argument("--type", "-t", default="单选题", help="Question type (单选题, 多选题, 判断题, 填空题, 简答题).")
    solve_parser.add_argument("--options", "-o", action="append", default=[], help="Candidate option (can be repeated).")

    # Command: tools
    subparsers.add_parser("tools", parents=[common], help="Export Agent Tool Definition (JSON Schema for LLM function calling).")

    return parser

def run_tui_mode(course_name: str, config: XXTConfig, max_chapters: int = 15):
    from rich.live import Live
    from xxt_agent.tui import AgentTUI
    from xxt_agent.agent import XXTAgent

    tui = AgentTUI(course_name, config)
    agent = XXTAgent(config, event_callback=tui.handle_event)

    def worker():
        try:
            with agent:
                agent.run_course(course_name, max_chapters=max_chapters)
        except Exception as e:
            tui.add_event("运行异常", "bold red", str(e))
        finally:
            tui.status_text = "本次刷课运行结束。"

    th = threading.Thread(target=worker, daemon=True)
    th.start()

    try:
        if sys.stdout.isatty():
            with Live(tui.render(), refresh_per_second=4, screen=False) as live:
                while th.is_alive():
                    live.update(tui.render())
                    time.sleep(0.25)
                live.update(tui.render())
                time.sleep(2)
        else:
            # Fallback for redirected streams / non-TTY
            print(f"[TUI Headless Mode Started] Course: {course_name} | Max Chapters: {max_chapters}", flush=True)
            while th.is_alive():
                time.sleep(1)
            print("[TUI Headless Mode Finished]", flush=True)
    except KeyboardInterrupt:
        tui.add_event("用户中断", "bold yellow", "收到退出指令，正在关闭后台浏览器...")
        agent.close()

def main(argv: Optional[List[str]] = None) -> int:
    raw_argv = list(argv) if argv is not None else sys.argv[1:]
    is_json = ("--json" in raw_argv) or ("json" in raw_argv)

    parser = build_parser()
    args = parser.parse_args(raw_argv)

    if not args.command:
        parser.print_help()
        return 0

    if getattr(args, "json", False) or getattr(args, "format", "") == "json":
        is_json = True

    config = XXTConfig.load()
    if getattr(args, "gui", False):
        config.headless = False

    try:
        if args.command == "config":
            output_result(config.to_dict(), is_json)
            return 0

        elif args.command == "status":
            res = {
                "ok": True,
                "phone_configured": bool(config.phone_number),
                "browser": config.browser,
                "driver_path": config.driver_path,
                "driver_exists": bool(config.driver_path and os.path.exists(config.driver_path)),
                "cookies_exist": bool(config.cookies_path and os.path.exists(config.cookies_path)),
                "api_key_configured": bool(config.api_key and "sk-" in config.api_key),
                "deepseek_model": config.api_model,
                "headless_mode": config.headless,
                "default_speed": config.speed,
                "default_courses": config.default_courses
            }
            output_result(res, is_json)
            return 0

        elif args.command == "live-status":
            if os.path.exists(STATUS_FILE):
                try:
                    with open(STATUS_FILE, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    output_result({"ok": True, **data}, is_json)
                    return 0
                except Exception as e:
                    output_result({"ok": False, "error": str(e)}, is_json)
                    return 1
            else:
                output_result({"ok": False, "status": "idle", "message": "No active course running currently."}, is_json)
                return 0

        elif args.command in ["list-courses", "courses"]:
            from xxt_agent.agent import XXTAgent
            with XXTAgent(config) as agent:
                courses = agent.list_courses()
                course_list = [c.to_dict() if hasattr(c, "to_dict") else c for c in courses]
                output_result({"ok": True, "count": len(course_list), "courses": course_list}, is_json)
            return 0

        elif args.command == "chapters":
            from xxt_agent.agent import XXTAgent
            with XXTAgent(config) as agent:
                agent.start()
                chapters = agent._course_runner.get_chapters(args.course)
                output_result({"ok": True, "course": args.course, "chapters": chapters}, is_json)
            return 0

        elif args.command == "tui" or (args.command == "run" and getattr(args, "tui", False)):
            course = getattr(args, "course", "艺术鉴赏")
            if getattr(args, "speed", None):
                config.speed = args.speed
            max_c = getattr(args, "max_chapters", 15)
            run_tui_mode(course, config, max_chapters=max_c)
            return 0

        elif args.command == "run":
            from xxt_agent.agent import XXTAgent
            with XXTAgent(config) as agent:
                res = agent.run_course(
                    course_name=args.course,
                    max_chapters=args.max_chapters
                )
                output_result(res.to_dict() if hasattr(res, "to_dict") else res, is_json)
            return 0

        elif args.command == "solve":
            solver = DeepSeekSolver(
                api_key=config.api_key,
                primary_model=config.api_model,
                base_url=config.api_base_url
            )
            answers = solver.solve_single(args.question, args.options, args.type)
            matched_indices = solver.match_options(answers, args.options, args.type) if args.options else []
            res = {
                "question": args.question,
                "type": args.type,
                "options": args.options,
                "answers": answers,
                "matched_option_indices": matched_indices
            }
            output_result(res, is_json)
            return 0

        elif args.command == "tools":
            from xxt_agent.core.tool_schema import get_agent_tools_schema
            schemas = get_agent_tools_schema()
            output_result(schemas, True)
            return 0

    except KeyboardInterrupt:
        output_result({"ok": False, "error": "Interrupted by user."}, is_json)
        return 130
    except Exception as e:
        output_result({"ok": False, "error": str(e)}, is_json)
        return 1

    return 0

if __name__ == "__main__":
    sys.exit(main())
