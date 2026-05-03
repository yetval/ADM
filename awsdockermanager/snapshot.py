from __future__ import annotations

from typing import Any

from . import dockerctl
from .advisor import build_tips
from .systeminfo import collect_system


def collect_snapshot(include_inventory: bool = True, include_events: bool = False) -> dict[str, Any]:
    snapshot: dict[str, Any] = {
        "system": collect_system(),
        "docker": dockerctl.docker_version(),
        "containers": dockerctl.containers(),
        "images": [],
        "volumes": [],
        "networks": [],
        "events": [],
    }
    if include_inventory:
        snapshot["images"] = dockerctl.images()
        snapshot["volumes"] = dockerctl.volumes()
        snapshot["networks"] = dockerctl.networks()
    if include_events:
        snapshot["events"] = dockerctl.events()
    snapshot["tips"] = build_tips(snapshot)
    return snapshot
