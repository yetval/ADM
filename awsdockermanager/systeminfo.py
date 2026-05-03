from __future__ import annotations

import json
import os
import platform
import re
import shutil
import socket
import subprocess
import time
import urllib.error
import urllib.request
from typing import Any


def _read(path: str) -> str:
    try:
        with open(path, "r", encoding="utf-8") as handle:
            return handle.read().strip()
    except OSError:
        return ""


def _run(args: list[str], timeout: int = 5) -> str:
    try:
        proc = subprocess.run(args, check=False, capture_output=True, text=True, timeout=timeout)
    except (OSError, subprocess.TimeoutExpired):
        return ""
    return proc.stdout.strip()


def _meminfo() -> dict[str, int]:
    info: dict[str, int] = {}
    for line in _read("/proc/meminfo").splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        digits = "".join(ch for ch in value if ch.isdigit())
        if digits:
            info[key] = int(digits) * 1024
    return info


def _memory() -> dict[str, float | int]:
    linux = _meminfo()
    if linux.get("MemTotal"):
        total = linux.get("MemTotal", 0)
        available = linux.get("MemAvailable", 0)
        used = max(total - available, 0)
        return {
            "total": total,
            "available": available,
            "used": used,
            "percent": round((used / total) * 100, 1) if total else 0,
        }

    total_raw = _run(["sysctl", "-n", "hw.memsize"])
    page_size_raw = _run(["sysctl", "-n", "hw.pagesize"])
    vm_stat = _run(["vm_stat"])
    page_size_match = re.search(r"page size of (\d+) bytes", vm_stat)
    try:
        total = int(total_raw)
        page_size = int(page_size_raw or (page_size_match.group(1) if page_size_match else "4096"))
    except ValueError:
        total = 0
        page_size = int(page_size_match.group(1)) if page_size_match else 4096
    free_pages = 0
    inactive_pages = 0
    speculative_pages = 0
    active_pages = 0
    wired_pages = 0
    compressor_pages = 0
    for line in vm_stat.splitlines():
        clean = line.replace(".", "").replace(":", "")
        parts = clean.split()
        if not parts:
            continue
        try:
            count = int(parts[-1])
        except ValueError:
            continue
        label = " ".join(parts[:-1])
        if label == "Pages free":
            free_pages = count
        elif label == "Pages active":
            active_pages = count
        elif label == "Pages inactive":
            inactive_pages = count
        elif label == "Pages speculative":
            speculative_pages = count
        elif label == "Pages wired down":
            wired_pages = count
        elif label == "Pages occupied by compressor":
            compressor_pages = count
    if not total and vm_stat:
        total_pages = free_pages + active_pages + inactive_pages + speculative_pages + wired_pages + compressor_pages
        total = total_pages * page_size
    available = (free_pages + inactive_pages + speculative_pages) * page_size if total else 0
    used = max(total - available, 0)
    return {
        "total": total,
        "available": available,
        "used": used,
        "percent": round((used / total) * 100, 1) if total else 0,
    }


def _aws_metadata() -> dict[str, Any]:
    token_req = urllib.request.Request(
        "http://169.254.169.254/latest/api/token",
        method="PUT",
        headers={"X-aws-ec2-metadata-token-ttl-seconds": "60"},
    )
    try:
        with urllib.request.urlopen(token_req, timeout=0.4) as response:
            token = response.read().decode("utf-8")
    except (urllib.error.URLError, TimeoutError, OSError):
        return {"available": False}

    def get(path: str) -> str:
        req = urllib.request.Request(
            f"http://169.254.169.254/latest/meta-data/{path}",
            headers={"X-aws-ec2-metadata-token": token},
        )
        try:
            with urllib.request.urlopen(req, timeout=0.4) as response:
                return response.read().decode("utf-8")
        except (urllib.error.URLError, TimeoutError, OSError):
            return ""

    return {
        "available": True,
        "instance_id": get("instance-id"),
        "instance_type": get("instance-type"),
        "availability_zone": get("placement/availability-zone"),
        "public_ipv4": get("public-ipv4"),
        "local_ipv4": get("local-ipv4"),
    }


def collect_system() -> dict[str, Any]:
    usage = shutil.disk_usage("/")
    memory = _memory()
    cpu_count = os.cpu_count() or 1
    load = os.getloadavg() if hasattr(os, "getloadavg") else (0.0, 0.0, 0.0)
    uptime_seconds = 0.0
    raw_uptime = _read("/proc/uptime").split(" ", 1)[0]
    if raw_uptime:
        try:
            uptime_seconds = float(raw_uptime)
        except ValueError:
            uptime_seconds = time.monotonic()

    return {
        "hostname": socket.gethostname(),
        "platform": platform.platform(),
        "kernel": platform.release(),
        "architecture": platform.machine(),
        "python": platform.python_version(),
        "cpu_count": cpu_count,
        "load_average": list(load),
        "load_percent": round((load[0] / cpu_count) * 100, 1),
        "memory": memory,
        "disk": {
            "total": usage.total,
            "used": usage.used,
            "free": usage.free,
            "percent": round((usage.used / usage.total) * 100, 1),
        },
        "uptime_seconds": uptime_seconds,
        "docker_path": shutil.which("docker") or "",
        "aws": _aws_metadata(),
        "top": _run(["sh", "-c", "ps -eo pid,comm,%cpu,%mem --sort=-%cpu | head -8"]).splitlines(),
    }


def as_json(data: Any) -> str:
    return json.dumps(data, indent=2, sort_keys=True)
