from __future__ import annotations

import json
import re
import shutil
import subprocess
from dataclasses import dataclass
from typing import Any


@dataclass
class CommandResult:
    ok: bool
    stdout: str
    stderr: str
    code: int


def docker_available() -> bool:
    return shutil.which("docker") is not None


def run_docker(args: list[str], timeout: int = 20) -> CommandResult:
    if not docker_available():
        return CommandResult(False, "", "Docker CLI is not installed or not in PATH.", 127)
    try:
        proc = subprocess.run(
            ["docker", *args],
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as exc:
        return CommandResult(False, exc.stdout or "", "Docker command timed out.", 124)
    except OSError as exc:
        return CommandResult(False, "", str(exc), 1)
    return CommandResult(proc.returncode == 0, proc.stdout.strip(), proc.stderr.strip(), proc.returncode)


def _json_lines(output: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line in output.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            rows.append({"raw": line})
    return rows


ERROR_PATTERNS = re.compile(
    r"\b(error|exception|traceback|panic|fatal|critical|segfault|oom|out of memory|connection refused|permission denied)\b",
    re.IGNORECASE,
)


def docker_version() -> dict[str, Any]:
    result = run_docker(["version", "--format", "{{json .}}"])
    if not result.ok:
        error = result.stderr or result.stdout
        return {
            "available": False,
            "error": error,
            "diagnosis": docker_error_diagnosis(error, result.code),
        }
    try:
        data = json.loads(result.stdout)
    except json.JSONDecodeError:
        data = {"raw": result.stdout}
    data["available"] = True
    return data


def docker_error_diagnosis(error: str, code: int = 1) -> str:
    lowered = error.lower()
    if code == 127 or "not installed" in lowered or "not in path" in lowered:
        return "docker-cli-missing"
    if "permission denied" in lowered or "var/run/docker.sock" in lowered:
        return "docker-permission-denied"
    if "cannot connect to the docker daemon" in lowered or "is the docker daemon running" in lowered:
        return "docker-daemon-unreachable"
    if "connection refused" in lowered:
        return "docker-daemon-unreachable"
    return "docker-unavailable"


def docker_fix_message(diagnosis: str, error: str = "") -> str:
    if diagnosis == "docker-permission-denied":
        return "Docker is installed, but this shell cannot access /var/run/docker.sock. Run: newgrp docker. If that fails, log out and back in, or use sudo adm."
    if diagnosis == "docker-daemon-unreachable":
        return "Docker CLI is installed, but the daemon is not reachable. Run: sudo systemctl enable --now docker."
    if diagnosis == "docker-cli-missing":
        return "Docker CLI is missing. Run the installer again: sudo ./scripts/install-aws.sh."
    if error:
        return f"Docker is unavailable: {error}"
    return "Docker is unavailable. Check docker ps, Docker service status, and user permissions."


def containers(all_containers: bool = True) -> list[dict[str, Any]]:
    args = ["ps", "--format", "{{json .}}"]
    if all_containers:
        args.insert(1, "-a")
    result = run_docker(args)
    if not result.ok:
        return []
    rows = _json_lines(result.stdout)
    stats_by_key = container_stats()
    for row in rows:
        cid = str(row.get("ID", ""))
        if cid:
            details = inspect_container(cid)
            if details:
                state = details.get("State", {})
                row["Health"] = state.get("Health", {}).get("Status", "")
                row["RestartCount"] = details.get("RestartCount", 0)
                row["StartedAt"] = state.get("StartedAt", "")
                row["FinishedAt"] = state.get("FinishedAt", "")
                row["ExitCode"] = state.get("ExitCode")
                row["OOMKilled"] = state.get("OOMKilled", False)
                row["Error"] = state.get("Error", "")
                row["Running"] = state.get("Running", False)
                row["Paused"] = state.get("Paused", False)
                row["Dead"] = state.get("Dead", False)
                row["State"] = state.get("Status", "")
        name = str(row.get("Names") or "")
        stat = stats_by_key.get(cid) or stats_by_key.get(name)
        if stat:
            row["CPUPerc"] = stat.get("CPUPerc", "")
            row["MemUsage"] = stat.get("MemUsage", "")
            row["MemPerc"] = stat.get("MemPerc", "")
            row["NetIO"] = stat.get("NetIO", "")
            row["BlockIO"] = stat.get("BlockIO", "")
        row["Problems"] = container_problems(row)
        row["LogErrors"] = log_error_summary(name or cid)
    return rows


def inspect_container(name: str) -> dict[str, Any]:
    result = run_docker(["inspect", name])
    if not result.ok:
        return {}
    try:
        parsed = json.loads(result.stdout)
    except json.JSONDecodeError:
        return {}
    return parsed[0] if parsed else {}


def images() -> list[dict[str, Any]]:
    result = run_docker(["images", "--format", "{{json .}}"])
    return _json_lines(result.stdout) if result.ok else []


def volumes() -> list[dict[str, Any]]:
    result = run_docker(["volume", "ls", "--format", "{{json .}}"])
    return _json_lines(result.stdout) if result.ok else []


def networks() -> list[dict[str, Any]]:
    result = run_docker(["network", "ls", "--format", "{{json .}}"])
    return _json_lines(result.stdout) if result.ok else []


def container_stats() -> dict[str, dict[str, Any]]:
    result = run_docker(["stats", "--no-stream", "--format", "{{json .}}"], timeout=12)
    if not result.ok:
        return {}
    stats: dict[str, dict[str, Any]] = {}
    for row in _json_lines(result.stdout):
        for key in (row.get("ID"), row.get("Name"), row.get("Container")):
            if key:
                stats[str(key)] = row
    return stats


def container_problems(row: dict[str, Any]) -> list[str]:
    problems: list[str] = []
    status = str(row.get("Status", ""))
    health = str(row.get("Health", "")).lower()
    exit_code = row.get("ExitCode")
    if "Restarting" in status:
        problems.append("restart-loop")
    if "Exited" in status:
        problems.append("down")
    if health == "unhealthy":
        problems.append("unhealthy")
    if row.get("OOMKilled"):
        problems.append("oom-killed")
    if row.get("Dead"):
        problems.append("dead")
    if exit_code not in (None, "", 0, "0") and "Exited" in status:
        problems.append(f"exit-{exit_code}")
    if row.get("Error"):
        problems.append("docker-error")
    try:
        restarts = int(row.get("RestartCount") or 0)
    except (TypeError, ValueError):
        restarts = 0
    if restarts >= 3:
        problems.append(f"{restarts}-restarts")
    mem_perc = str(row.get("MemPerc", "")).strip().rstrip("%")
    try:
        if mem_perc and float(mem_perc) >= 85:
            problems.append("high-memory")
    except ValueError:
        pass
    return problems


def log_error_summary(target: str, lines: int = 80) -> list[str]:
    if not target:
        return []
    result = logs(target, lines=lines, timeout=5)
    combined = "\n".join(part for part in (result.stdout, result.stderr) if part)
    if not result.ok or not combined:
        return []
    matches: list[str] = []
    for line in combined.splitlines():
        clean = line.strip()
        if clean and ERROR_PATTERNS.search(clean):
            matches.append(clean[:180])
        if len(matches) >= 3:
            break
    return matches


def events(limit: int = 20) -> list[dict[str, Any]]:
    result = run_docker(["events", "--since", "24h", "--until", "0s", "--format", "{{json .}}"], timeout=8)
    if not result.ok:
        return []
    return _json_lines("\n".join(result.stdout.splitlines()[-limit:]))


def container_action(action: str, target: str) -> CommandResult:
    allowed = {"start", "stop", "restart", "pause", "unpause", "kill", "rm"}
    if action not in allowed:
        return CommandResult(False, "", f"Unsupported action: {action}", 2)
    return run_docker([action, target], timeout=60)


def logs(target: str, lines: int = 120, timeout: int = 20) -> CommandResult:
    return run_docker(["logs", "--tail", str(lines), target], timeout=timeout)


def prune() -> CommandResult:
    return run_docker(["system", "prune", "-f"], timeout=120)
