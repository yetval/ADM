from __future__ import annotations

import curses
import json
import time
from typing import Any

from . import dockerctl
from .dockerctl import docker_fix_message
from .snapshot import collect_snapshot

SCAN_INTERVAL = 3.0


class AdmConsole:
    def __init__(self, screen: Any) -> None:
        self.screen = screen
        self.command = "adm status"
        self.output = "Live scanner started. Press / for commands or q to quit."
        self.snapshot: dict[str, Any] = {}
        self.selected = 0
        self.last_refresh = 0.0
        self.scan_count = 0
        self.scan_error = ""

    def run(self) -> int:
        curses.curs_set(0)
        self.screen.nodelay(True)
        self.screen.keypad(True)
        curses.start_color()
        curses.use_default_colors()
        curses.init_pair(1, curses.COLOR_GREEN, -1)
        curses.init_pair(2, curses.COLOR_YELLOW, -1)
        curses.init_pair(3, curses.COLOR_RED, -1)
        curses.init_pair(4, curses.COLOR_CYAN, -1)
        curses.init_pair(5, curses.COLOR_BLACK, curses.COLOR_WHITE)
        curses.init_pair(6, curses.COLOR_MAGENTA, -1)
        curses.init_pair(7, curses.COLOR_BLUE, -1)
        self.refresh()

        while True:
            if time.monotonic() - self.last_refresh >= SCAN_INTERVAL:
                self.refresh()
            self.draw()
            key = self.screen.getch()
            if key == -1:
                time.sleep(0.07)
                continue
            if key in (ord("q"), ord("Q")):
                return 0
            if key in (ord("r"), ord("R")):
                self.refresh()
            elif key in (curses.KEY_UP, ord("k")):
                self.move_selection(-1)
            elif key in (curses.KEY_DOWN, ord("j")):
                self.move_selection(1)
            elif key == ord("/"):
                self.read_command()
            elif key in (ord("s"), ord("S")):
                self.action_selected("start")
            elif key in (ord("x"), ord("X")):
                self.action_selected("stop")
            elif key in (ord("e"), ord("E")):
                self.action_selected("restart")
            elif key in (ord("l"), ord("L")):
                self.logs_selected()
            elif key in (ord("i"), ord("I")):
                self.inspect_selected()

    def refresh(self) -> None:
        try:
            self.snapshot = collect_snapshot(include_inventory=False)
            self.scan_error = ""
            self.scan_count += 1
        except Exception as exc:  # Defensive: the dashboard should keep running.
            self.scan_error = str(exc)
        self.last_refresh = time.monotonic()
        containers = self.snapshot.get("containers", [])
        if self.selected >= len(containers):
            self.selected = max(len(containers) - 1, 0)

    def move_selection(self, delta: int) -> None:
        total = len(self.snapshot.get("containers", []))
        if total:
            self.selected = max(0, min(total - 1, self.selected + delta))

    def selected_row(self) -> dict[str, Any]:
        rows = self.snapshot.get("containers", [])
        if not rows:
            return {}
        return rows[self.selected]

    def selected_container(self) -> str:
        row = self.selected_row()
        return str(row.get("Names") or row.get("ID") or "")

    def action_selected(self, action: str) -> None:
        target = self.selected_container()
        if not target:
            self.output = "No container selected."
            return
        result = dockerctl.container_action(action, target)
        self.output = result.stdout or result.stderr or f"{action} {target}: exit {result.code}"
        self.refresh()

    def logs_selected(self) -> None:
        target = self.selected_container()
        if not target:
            self.output = "No container selected."
            return
        result = dockerctl.logs(target, 120)
        self.output = result.stdout or result.stderr or "No log output."

    def inspect_selected(self) -> None:
        target = self.selected_container()
        if not target:
            self.output = "No container selected."
            return
        self.output = json.dumps(dockerctl.inspect_container(target), indent=2)

    def read_command(self) -> None:
        height, width = self.screen.getmaxyx()
        curses.curs_set(1)
        self.screen.nodelay(False)
        prompt = "adm> "
        self._write(height - 1, 0, " " * max(width - 1, 0), curses.color_pair(5))
        self._write(height - 1, 0, prompt, curses.color_pair(5))
        curses.echo()
        try:
            raw = self.screen.getstr(height - 1, len(prompt), max(width - len(prompt) - 1, 1))
        finally:
            curses.noecho()
            curses.curs_set(0)
            self.screen.nodelay(True)
        command = raw.decode("utf-8", errors="replace").strip()
        if command:
            self.command = command if command.lower().startswith("adm") else f"adm {command}"
            self.execute(self.command)

    def execute(self, command: str) -> None:
        parts = command.split()
        if parts and parts[0].lower() == "adm":
            parts = parts[1:]
        if not parts or parts[0] in {"status", "list"}:
            self.refresh()
            self.output = "Refreshed."
            return
        name = parts[1] if len(parts) > 1 else self.selected_container()
        if parts[0] in {"start", "stop", "restart", "pause", "unpause", "kill", "rm"}:
            if not name:
                self.output = f"Usage: adm {parts[0]} <container>"
                return
            result = dockerctl.container_action(parts[0], name)
            self.output = result.stdout or result.stderr or f"{parts[0]} {name}: exit {result.code}"
            self.refresh()
            return
        if parts[0] == "logs":
            if not name:
                self.output = "Usage: adm logs <container>"
                return
            result = dockerctl.logs(name, 120)
            self.output = result.stdout or result.stderr or "No log output."
            return
        if parts[0] == "inspect":
            if not name:
                self.output = "Usage: adm inspect <container>"
                return
            self.output = json.dumps(dockerctl.inspect_container(name), indent=2)
            return
        if parts[0] == "prune":
            result = dockerctl.prune()
            self.output = result.stdout or result.stderr or f"prune: exit {result.code}"
            self.refresh()
            return
        self.output = "Commands: status, list, start, stop, restart, logs, inspect, prune."

    def draw(self) -> None:
        self.screen.erase()
        height, width = self.screen.getmaxyx()
        if height < 22 or width < 76:
            self._write(0, 0, "ADM needs at least 76x22 terminal space.")
            self.screen.refresh()
            return
        self.draw_header(0, 0, width)
        self.draw_metrics(3, 0, width)
        content_top = 7
        content_height = max(8, height - 16)
        left_width = max(32, min(44, width // 3))
        self.draw_tips(content_top, 0, left_width, content_height)
        self.draw_containers(content_top, left_width + 1, width - left_width - 2, content_height)
        self.draw_details(height - 8, 0, left_width, 7)
        self.draw_output(height - 8, left_width + 1, width - left_width - 2, 7)
        self._write(height - 1, 0, " / command   r refresh   j/k move   s start   x stop   e restart   l logs   i inspect   q quit "[: width - 1], curses.color_pair(5))
        self.screen.refresh()

    def draw_header(self, y: int, x: int, width: int) -> None:
        system = self.snapshot.get("system", {})
        aws = system.get("aws", {})
        left = f" ADM LIVE | {system.get('hostname', 'host')} "
        if aws.get("available"):
            left += f"| {aws.get('instance_id')} {aws.get('instance_type')} {aws.get('availability_zone')} "
        seconds = max(0, SCAN_INTERVAL - (time.monotonic() - self.last_refresh))
        right = f"scan #{self.scan_count} | next {seconds:0.1f}s"
        self._write(y, x, " " * (width - 1), curses.color_pair(5))
        self._write(y, x, left[: width - 1], curses.A_BOLD | curses.color_pair(5))
        self._write(y, max(x, width - len(right) - 1), right, curses.A_BOLD | curses.color_pair(5))
        status = self.health_line()
        color = self.severity_color(status[0])
        self._write(y + 1, x, status[1][: width - 1], curses.A_BOLD | color)

    def health_line(self) -> tuple[str, str]:
        if self.scan_error:
            return "critical", f"SCAN ERROR: {self.scan_error}"
        docker = self.snapshot.get("docker", {})
        if not docker.get("available"):
            message = docker_fix_message(str(docker.get("diagnosis", "")), str(docker.get("error", "")))
            return "critical", message
        rows = self.snapshot.get("containers", [])
        bad = [row for row in rows if row.get("Problems") or row.get("LogErrors")]
        if bad:
            return "critical", f"{len(bad)} container(s) need attention. Select one for details or press l for logs."
        return "good", "All scanned containers look steady."

    def draw_metrics(self, y: int, x: int, width: int) -> None:
        docker = self.snapshot.get("docker", {})
        system = self.snapshot.get("system", {})
        containers = self.snapshot.get("containers", [])
        running = sum(1 for row in containers if "Up" in str(row.get("Status", "")))
        problem_count = sum(1 for row in containers if row.get("Problems") or row.get("LogErrors"))
        metrics = [
            ("DOCKER", "online" if docker.get("available") else "offline", "good" if docker.get("available") else "critical"),
            ("RUNNING", f"{running}/{len(containers)}", "good" if running or not containers else "critical"),
            ("PROBLEMS", str(problem_count), "critical" if problem_count else "good"),
            ("CPU LOAD", f"{system.get('load_percent', 0)}%", self.percent_level(system.get("load_percent", 0), 80, 100)),
            ("MEMORY", f"{system.get('memory', {}).get('percent', 0)}%", self.percent_level(system.get("memory", {}).get("percent", 0), 70, 85)),
            ("DISK", f"{system.get('disk', {}).get('percent', 0)}%", self.percent_level(system.get("disk", {}).get("percent", 0), 70, 85)),
        ]
        gap = 1
        card_width = max(12, (width - gap * (len(metrics) - 1)) // len(metrics))
        for index, (label, value, level) in enumerate(metrics):
            card_x = x + index * (card_width + gap)
            if card_x + card_width >= width:
                break
            self.box(y, card_x, card_width, 3, label, curses.A_BOLD)
            self._write(y + 1, card_x + 2, value[: card_width - 4], curses.A_BOLD | self.severity_color(level))

    def draw_tips(self, y: int, x: int, width: int, height: int) -> None:
        self.box(y, x, width, height, "ADVICE", curses.A_BOLD | curses.color_pair(4))
        row = y + 2
        for tip in self.snapshot.get("tips", [])[: max(height // 4, 1)]:
            level = str(tip.get("level", "info"))
            self._write(row, x + 2, str(tip.get("title", ""))[: width - 4], curses.A_BOLD | self.severity_color(level))
            row += 1
            for line in self.wrap(str(tip.get("detail", "")), width - 5)[:2]:
                if row >= y + height - 1:
                    return
                self._write(row, x + 3, line, self.severity_color(level))
                row += 1
            row += 1

    def draw_containers(self, y: int, x: int, width: int, height: int) -> None:
        self.box(y, x, width, height, "CONTAINERS", curses.A_BOLD | curses.color_pair(4))
        headers = f"{'NAME':22} {'STATE':12} {'CPU':>7} {'MEM':>7} FLAGS"
        self._write(y + 1, x + 2, headers[: width - 4], curses.A_DIM)
        rows = self.snapshot.get("containers", [])
        if not rows:
            self._write(y + 3, x + 2, "No containers found."[: width - 4])
            return
        visible_count = max(0, height - 3)
        start = max(0, min(self.selected - visible_count + 1, max(len(rows) - visible_count, 0)))
        visible = rows[start : start + visible_count]
        for offset, item in enumerate(visible):
            absolute_index = start + offset
            row_y = y + 2 + offset
            name = str(item.get("Names") or item.get("ID") or "-")
            state = self.container_state(item)
            cpu = str(item.get("CPUPerc") or "-")
            mem = str(item.get("MemPerc") or "-")
            flags = ",".join(item.get("Problems", []))
            if item.get("LogErrors"):
                flags = f"{flags},log-error".strip(",")
            line = f"{name[:22]:22} {state[:12]:12} {cpu[-7:]:>7} {mem[-7:]:>7} {flags}"
            attr = curses.A_REVERSE if absolute_index == self.selected else curses.A_NORMAL
            attr |= self.severity_color(self.container_level(item))
            self._write(row_y, x + 1, line[: width - 3].ljust(width - 3), attr)

    def draw_details(self, y: int, x: int, width: int, height: int) -> None:
        self.box(y, x, width, height, "SELECTED", curses.A_BOLD | curses.color_pair(4))
        row = self.selected_row()
        if not row:
            self._write(y + 2, x + 2, "No container selected."[: width - 4])
            return
        lines = [
            f"name: {row.get('Names') or row.get('ID')}",
            f"image: {row.get('Image', '-')}",
            f"status: {row.get('Status', '-')}",
            f"health: {row.get('Health') or '-'} restarts: {row.get('RestartCount', 0)}",
        ]
        problems = row.get("Problems", [])
        if problems:
            lines.append(f"flags: {', '.join(problems)}")
        if row.get("LogErrors"):
            lines.append(f"log: {row['LogErrors'][0]}")
        for index, line in enumerate(lines[: height - 2]):
            self._write(y + 1 + index, x + 2, line[: width - 4], self.severity_color(self.container_level(row)) if index == 0 else 0)

    def draw_output(self, y: int, x: int, width: int, height: int) -> None:
        self.box(y, x, width, height, "OUTPUT", curses.A_BOLD | curses.color_pair(4))
        lines: list[str] = []
        for raw in self.output.splitlines() or [""]:
            lines.extend(self.wrap(raw, width - 4))
        for index, line in enumerate(lines[-(height - 2):]):
            self._write(y + 1 + index, x + 2, line[: width - 4])

    def container_state(self, row: dict[str, Any]) -> str:
        if "Restarting" in str(row.get("Status", "")):
            return "restarting"
        if str(row.get("Health", "")).lower() == "unhealthy":
            return "unhealthy"
        if "Exited" in str(row.get("Status", "")):
            return "down"
        if "Up" in str(row.get("Status", "")):
            return "running"
        return str(row.get("State") or row.get("Status") or "unknown")

    def container_level(self, row: dict[str, Any]) -> str:
        problems = set(row.get("Problems", []))
        if problems.intersection({"restart-loop", "unhealthy", "oom-killed", "dead"}) or any(str(p).startswith("exit-") for p in problems):
            return "critical"
        if row.get("LogErrors") or problems:
            return "warn"
        if "Up" in str(row.get("Status", "")):
            return "good"
        return "info"

    def percent_level(self, value: Any, warn: float, critical: float) -> str:
        try:
            number = float(value)
        except (TypeError, ValueError):
            return "info"
        if number >= critical:
            return "critical"
        if number >= warn:
            return "warn"
        return "good"

    def severity_color(self, level: str) -> int:
        return {
            "good": curses.color_pair(1),
            "warn": curses.color_pair(2),
            "critical": curses.color_pair(3),
            "info": curses.color_pair(4),
        }.get(level, curses.color_pair(4))

    def box(self, y: int, x: int, width: int, height: int, title: str, attr: int = 0) -> None:
        if width < 4 or height < 3:
            return
        horizontal = "-" * (width - 2)
        self._write(y, x, f"+{horizontal}+")
        for row in range(y + 1, y + height - 1):
            self._write(row, x, "|")
            self._write(row, x + width - 1, "|")
        self._write(y + height - 1, x, f"+{horizontal}+")
        label = f" {title} "
        self._write(y, x + 2, label[: max(width - 4, 0)], attr)

    def wrap(self, value: str, width: int) -> list[str]:
        if width <= 0:
            return [""]
        words = value.split()
        lines: list[str] = []
        current = ""
        for word in words:
            if len(word) > width:
                if current:
                    lines.append(current)
                    current = ""
                lines.extend(word[i : i + width] for i in range(0, len(word), width))
            elif len(current) + len(word) + 1 <= width:
                current = f"{current} {word}".strip()
            else:
                lines.append(current)
                current = word
        if current:
            lines.append(current)
        return lines or [""]

    def _write(self, y: int, x: int, value: str, attr: int = 0) -> None:
        height, width = self.screen.getmaxyx()
        if y < 0 or y >= height or x < 0 or x >= width:
            return
        self.screen.addstr(y, x, value[: max(width - x - 1, 0)], attr)


def run_console() -> int:
    return curses.wrapper(lambda screen: AdmConsole(screen).run())
