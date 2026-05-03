from __future__ import annotations

from typing import Any


def build_tips(snapshot: dict[str, Any]) -> list[dict[str, str]]:
    tips: list[dict[str, str]] = []
    docker = snapshot.get("docker", {})
    system = snapshot.get("system", {})
    containers = snapshot.get("containers", [])

    if not docker.get("available"):
        tips.append({
            "level": "critical",
            "title": "Docker is not available",
            "detail": "Install Docker, start the daemon, or add this user to the docker group.",
        })
        return tips

    running = [c for c in containers if "Up" in str(c.get("Status", ""))]
    stopped = [c for c in containers if "Exited" in str(c.get("Status", ""))]
    unhealthy = [c for c in containers if str(c.get("Health", "")).lower() == "unhealthy"]
    restarting = [c for c in containers if "Restarting" in str(c.get("Status", ""))]
    crashed = [c for c in containers if any(str(p).startswith("exit-") for p in c.get("Problems", []))]
    oom = [c for c in containers if "oom-killed" in c.get("Problems", [])]
    log_errors = [c for c in containers if c.get("LogErrors")]
    high_mem = [c for c in containers if "high-memory" in c.get("Problems", [])]

    if unhealthy:
        names = ", ".join(str(c.get("Names", c.get("ID", ""))) for c in unhealthy[:4])
        tips.append({"level": "critical", "title": "Unhealthy containers", "detail": f"Check healthchecks and logs for: {names}."})
    if restarting:
        names = ", ".join(str(c.get("Names", c.get("ID", ""))) for c in restarting[:4])
        tips.append({"level": "critical", "title": "Restart loop detected", "detail": f"Run adm logs on: {names}."})
    if crashed:
        names = ", ".join(str(c.get("Names", c.get("ID", ""))) for c in crashed[:4])
        tips.append({"level": "critical", "title": "Containers exited with errors", "detail": f"Inspect exit codes and logs for: {names}."})
    if oom:
        names = ", ".join(str(c.get("Names", c.get("ID", ""))) for c in oom[:4])
        tips.append({"level": "critical", "title": "Container OOM kill detected", "detail": f"Increase memory, reduce workload, or set safer limits for: {names}."})
    if log_errors:
        names = ", ".join(str(c.get("Names", c.get("ID", ""))) for c in log_errors[:4])
        tips.append({"level": "warn", "title": "Recent error logs found", "detail": f"Open logs in ADM for: {names}."})
    if high_mem:
        names = ", ".join(str(c.get("Names", c.get("ID", ""))) for c in high_mem[:4])
        tips.append({"level": "warn", "title": "Container memory high", "detail": f"Memory usage is above 85% for: {names}."})
    if stopped and running:
        tips.append({"level": "warn", "title": "Stopped containers present", "detail": f"{len(stopped)} containers are stopped. Remove old ones or restart the expected services."})
    if not running and containers:
        tips.append({"level": "critical", "title": "No running containers", "detail": "All containers are stopped. Run adm start <name> for the service you expect online."})
    if not containers:
        tips.append({"level": "info", "title": "No containers found", "detail": "Docker is ready, but there are no containers yet."})

    disk_percent = system.get("disk", {}).get("percent", 0)
    mem_percent = system.get("memory", {}).get("percent", 0)
    load_percent = system.get("load_percent", 0)
    if disk_percent >= 85:
        tips.append({"level": "critical", "title": "Disk pressure", "detail": "Disk usage is high. Run adm prune after checking unused images and volumes."})
    elif disk_percent >= 70:
        tips.append({"level": "warn", "title": "Disk usage rising", "detail": "Review old images, stopped containers, and log growth."})
    if mem_percent >= 85:
        tips.append({"level": "warn", "title": "Memory pressure", "detail": "Memory usage is high. Inspect container limits and recent deploys."})
    if load_percent >= 100:
        tips.append({"level": "warn", "title": "CPU load is saturated", "detail": "The 1-minute load average is at or above CPU capacity."})
    if len(tips) == 0:
        tips.append({"level": "good", "title": "System looks steady", "detail": "Docker is responding and no obvious host pressure was detected."})
    return tips
