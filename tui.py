# -*- coding: utf-8 -*-
"""
Terminal User Interface (TUI) Dashboard for Xuexitong Agent.
Built with `rich` to provide live real-time visual monitoring of course progression,
video playback, anti-detection status, and AI problem solving.
"""
import os
import sys
import time
import json
import datetime
from typing import Optional, List, Dict, Any, Tuple

from rich.console import Console
from rich.layout import Layout
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.live import Live

from xxt_agent.models import RunEvent
from xxt_agent.config import XXTConfig

STATUS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "live_status.json")

class AgentTUI:
    def __init__(self, course_name: str, config: XXTConfig):
        self.course_name = course_name
        self.config = config
        self.console = Console(force_terminal=sys.stdout.isatty())
        self.start_time = time.time()
        self.status_text = "正在启动无头浏览器并加载会话..."
        
        # State variables
        self.current_video_idx = 0
        self.total_videos = 0
        self.current_percent = 0.0
        self.current_time_str = "00:00"
        self.duration_str = "00:00"
        self.chapters_completed = 0
        self.events_log: List[Tuple[str, str, str]] = []
        self.face_bypass_count = 0
        self.quizzes_answered = 0
        self.last_flush_time = 0

        self.save_status()

    def save_status(self):
        """Save live state to disk so any agent or process can inspect real-time progress."""
        elapsed_sec = int(time.time() - self.start_time)
        data = {
            "course": self.course_name,
            "status": self.status_text,
            "percent": self.current_percent,
            "current_time": self.current_time_str,
            "duration": self.duration_str,
            "speed": self.config.speed,
            "video_index": self.current_video_idx,
            "total_videos": self.total_videos,
            "chapters_completed": self.chapters_completed,
            "face_bypasses": self.face_bypass_count,
            "elapsed_seconds": elapsed_sec,
            "elapsed_formatted": f"{elapsed_sec // 60:02d}:{elapsed_sec % 60:02d}",
            "updated_at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        try:
            with open(STATUS_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def add_event(self, tag: str, style: str, message: str):
        now = datetime.datetime.now().strftime("%H:%M:%S")
        self.events_log.append((now, f"[{style}]{tag}[/{style}]", message))
        if len(self.events_log) > 10:
            self.events_log.pop(0)

        # Print fallback line for non-TTY redirected logs
        if not sys.stdout.isatty():
            try:
                print(f"[{now}] [{tag}] {message}", flush=True)
            except Exception:
                pass
        self.save_status()

    def handle_event(self, event: RunEvent):
        etype = event.event_type
        edata = event.data or {}

        if etype == "course_run_start":
            self.status_text = f"正在加载课程【{edata.get('course')}】目录..."
            self.add_event("课程启动", "green", f"开始自动化运行课程: {edata.get('course')}")

        elif etype == "chapter_content_detected":
            types = edata.get("types", [])
            types_str = ", ".join(types) if types else "常规章节"
            self.status_text = f"检测到任务点: [{types_str}]"
            self.add_event("任务探测", "cyan", f"当前页面包含任务点: {types_str}")

        elif etype == "video_batch_found":
            self.total_videos = edata.get("total", 0)
            self.add_event("视频发现", "magenta", f"当前章节共发现 {self.total_videos} 个视频任务")

        elif etype == "video_start":
            self.current_video_idx = edata.get("index", 1)
            self.total_videos = edata.get("total", 1)
            self.status_text = f"正在播放第 {self.current_video_idx}/{self.total_videos} 个视频 (倍速: {self.config.speed}x)"
            self.add_event("视频开始", "blue", f"开始播放视频 [{self.current_video_idx}/{self.total_videos}]，倍速 {self.config.speed}x")

        elif etype == "video_progress":
            self.current_percent = edata.get("percent", 0.0)
            self.current_time_str = edata.get("current", "00:00")
            self.duration_str = edata.get("duration", "00:00")
            self.status_text = f"正在播放第 {self.current_video_idx} 个视频: {self.current_percent}% ({self.current_time_str} / {self.duration_str})"

            # Heartbeat print every 10s for non-TTY
            if not sys.stdout.isatty() and (time.time() - self.last_flush_time >= 10):
                print(f"[{datetime.datetime.now().strftime('%H:%M:%S')}] [播放进度] {self.current_percent}% ({self.current_time_str} / {self.duration_str}) | 倍速 {self.config.speed}x", flush=True)
                self.last_flush_time = time.time()
                self.save_status()

        elif etype == "in_video_quiz_detected":
            self.add_event("弹题拦截", "yellow", "检测到视频播放中途弹出测试题，正在交由 AI 解答...")

        elif etype == "face_popup_detected":
            self.face_bypass_count += 1
            self.add_event("人脸识别", "red", "拦截到人脸验证弹窗，已自动执行 DOM 移除与绕过")

        elif etype == "video_finished":
            dur = edata.get("duration_sec", 0)
            self.add_event("视频完成", "green", f"视频任务已圆满播放完成 (耗时: {dur}秒)")

        elif etype == "chapter_completed":
            self.chapters_completed = edata.get("chapter_index", self.chapters_completed + 1)
            self.add_event("章节达成", "bold green", f"第 {self.chapters_completed} 节全部任务已完成，准备进入下一节")

        elif etype == "daily_limit_reached":
            c_name = edata.get("course") or self.course_name
            reason = edata.get("reason") or "今日观看时长或任务点已达上限"
            self.status_text = f"【{c_name}】{reason}，已自动停止"
            self.add_event("上限拦截", "bold yellow", f"【{c_name}】{reason}！已自动关闭本门课程")

        elif etype == "queue_start":
            courses = edata.get("courses", [])
            self.add_event("队列启动", "bold magenta", f"启动课程代办排队表: 共 {len(courses)} 门课程 {courses}")

        elif etype == "queue_course_start":
            self.course_name = edata.get("course", self.course_name)
            self.chapters_completed = 0
            self.add_event("课程切换", "bold cyan", f"开始执行队列第 {edata.get('index')}/{edata.get('total')} 门: 【{self.course_name}】")

        elif etype == "queue_course_switched":
            c_name = edata.get("course", self.course_name)
            self.add_event("自动换课", "bold yellow", f"【{c_name}】今日上限已满，已自动平滑切换至下一门代办课程！")

        elif etype == "queue_complete":
            self.status_text = "课程代办排队表全部执行完成！"
            statuses = edata.get("statuses", {})
            self.add_event("代办圆满", "bold green", f"所有排队课程均已完成或达上限: {statuses}")

        elif etype == "course_run_complete":
            self.status_text = "课程指定目标已圆满完成！"
            self.add_event("任务圆满", "bold magenta", "所有目标章节均已刷完！")

    def make_header(self) -> Panel:
        title = Text("=== Xuexitong Agent TUI · 学习通智能体终端监控控制台 ===", style="bold white on blue", justify="center")
        return Panel(title, style="blue")

    def make_metrics_table(self) -> Table:
        table = Table(expand=True, box=None, padding=(0, 1))
        table.add_column("目标信息", style="bold cyan")
        table.add_column("防护状态", style="bold green")
        table.add_column("运行性能", style="bold yellow")

        elapsed_sec = int(time.time() - self.start_time)
        elapsed_str = f"{elapsed_sec // 60:02d}:{elapsed_sec % 60:02d}"

        phone = self.config.phone_number
        masked_phone = f"{phone[:3]}****{phone[-4:]}" if len(phone) >= 11 else (phone or "免密Cookie")
        mode_disp = "[yellow]GUI (前台可视化)[/yellow]" if not self.config.headless else "[green]Headless (静默后台)[/green]"

        table.add_row(
            f"课程: [white]{self.course_name}[/white]",
            f"切屏防失焦: [green][OK] 已激活[/green]",
            f"播放倍速: [white]{self.config.speed}x (静音)[/white]"
        )
        table.add_row(
            f"账号: [white]{masked_phone}[/white]",
            f"人脸自动跳过: [green][OK] 拦截 {self.face_bypass_count} 次[/green]",
            f"AI 模型: [white]{self.config.api_model} (在线)[/white]"
        )
        table.add_row(
            f"状态: [white]{self.status_text}[/white]",
            f"浏览器模式: {mode_disp}",
            f"运行耗时: [white]{elapsed_str}[/white]"
        )
        return table

    def make_progress_panel(self) -> Panel:
        pct = max(0.0, min(100.0, self.current_percent))
        filled = int(pct / 2.5)
        bar = "=" * filled + " " * (40 - filled)
        
        text = Text()
        text.append(f" [视频进度] [{bar}] ", style="bold green")
        text.append(f"{pct:.1f}% ", style="bold yellow")
        text.append(f"({self.current_time_str} / {self.duration_str})\n", style="white")
        text.append(f" [章节累计] 已完成 {self.chapters_completed} 节任务点", style="cyan")
        
        return Panel(text, title="[bold]实 时 进 度 监 控[/bold]", border_style="cyan")

    def make_events_panel(self) -> Panel:
        table = Table(expand=True, box=None, show_header=True, padding=(0, 1))
        table.add_column("时间", style="dim", width=10)
        table.add_column("类型", width=14)
        table.add_column("详细内容", style="white")

        if not self.events_log:
            table.add_row("--:--:--", "[dim]等待中[/dim]", "调度器已就绪，正在接收前端事件流...")
        else:
            for t, tag, msg in self.events_log:
                table.add_row(t, tag, msg)

        return Panel(table, title="[bold]动 态 事 件 日 志 (Live Feed)[/bold]", border_style="green")

    def render(self) -> Layout:
        layout = Layout()
        layout.split(
            Layout(self.make_header(), name="header", size=3),
            Layout(Panel(self.make_metrics_table(), title="[bold]核 心 运 行 指 标[/bold]", border_style="yellow"), name="metrics", size=6),
            Layout(self.make_progress_panel(), name="progress", size=5),
            Layout(self.make_events_panel(), name="events", ratio=1),
        )
        return layout
