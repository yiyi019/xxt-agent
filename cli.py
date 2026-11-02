# -*- coding: utf-8 -*-
"""
Agent-Optimized Command Line Interface (CLI) for Xuexitong Agent.
Supports deterministic JSON outputs and structured error codes for AI agents.
"""
import sys
import json
import argparse
from typing import Any, Optional, List

from xxt_agent.config import XXTConfig
from xxt_agent.ai_solver import DeepSeekSolver

def output_result(data: Any, is_json: bool):
    """Output structured data to stdout."""
    if is_json:
        print(json.dumps(data, ensure_ascii=False, indent=2))
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
    parser = argparse.ArgumentParser(
        description="Xuexitong Agent CLI - Lightweight course automation optimized for AI agents."
    )
    parser.add_argument("--json", action="store_true", help="Output results strictly in JSON format.")
    parser.add_argument("--format", choices=["json", "text"], default="text", help="Output format.")
    parser.add_argument("--gui", action="store_true", help="Disable headless mode and show browser UI.")

    subparsers = parser.add_subparsers(dest="command", help="Available subcommands")

    # Command: status
    subparsers.add_parser("status", help="Check system readiness, driver, cookies, and AI keys.")

    # Command: config
    cfg_parser = subparsers.add_parser("config", help="Configuration operations.")
    cfg_parser.add_argument("config_action", nargs="?", default="show", choices=["show"], help="Config action (default: show).")

    # Command: list-courses
    subparsers.add_parser("list-courses", help="Retrieve all enrolled courses under current account.")
    subparsers.add_parser("courses", help="Alias for list-courses.")

    # Command: chapters
    cap_parser = subparsers.add_parser("chapters", help="List chapters for a specific course.")
    cap_parser.add_argument("--course", "-c", required=True, help="Course title to inspect.")

    # Command: run
    run_parser = subparsers.add_parser("run", help="Run automated study on a specified course.")
    run_parser.add_argument("--course", "-c", required=True, help="Course title to run.")
    run_parser.add_argument("--duration", "-d", type=int, default=3600, help="Maximum run duration in seconds (default: 3600).")
    run_parser.add_argument("--speed", "-s", type=float, default=2.0, help="Playback speed (e.g. 1.0, 2.0, 4.0).")
    run_parser.add_argument("--max-chapters", "-m", type=int, default=15, help="Maximum number of chapters to process.")

    # Command: solve
    solve_parser = subparsers.add_parser("solve", help="Directly solve a question via DeepSeek AI.")
    solve_parser.add_argument("--question", "-q", required=True, help="Question text.")
    solve_parser.add_argument("--type", "-t", default="单选题", help="Question type (单选题, 多选题, 判断题, 填空题, 简答题).")
    solve_parser.add_argument("--options", "-o", action="append", default=[], help="Candidate option (can be repeated).")

    # Command: tools
    subparsers.add_parser("tools", help="Export Agent Tool Definition (JSON Schema for LLM function calling).")

    return parser

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
    if args.gui:
        config.headless = False

    try:
        if args.command == "config":
            output_result(config.to_dict(), is_json)
            return 0

        elif args.command == "status":
            import os
            res = {
                "ok": True,
                "browser": config.browser,
                "driver_path": config.driver_path,
                "driver_exists": bool(config.driver_path and os.path.exists(config.driver_path)),
                "cookies_exist": bool(config.cookies_path and os.path.exists(config.cookies_path)),
                "api_key_configured": bool(config.api_key and "sk-" in config.api_key),
                "deepseek_model": config.api_model,
                "headless_mode": config.headless,
                "default_speed": config.speed
            }
            output_result(res, is_json)
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
