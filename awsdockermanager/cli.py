from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

from . import dockerctl
from .snapshot import collect_snapshot
from .systeminfo import as_json
from .tui import run_console


def _table(rows: list[dict[str, Any]], columns: list[str]) -> str:
    if not rows:
        return "No rows."
    widths = {col: max(len(col), *(len(str(row.get(col, ""))) for row in rows)) for col in columns}
    header = "  ".join(col.ljust(widths[col]) for col in columns)
    line = "  ".join("-" * widths[col] for col in columns)
    body = ["  ".join(str(row.get(col, "")).ljust(widths[col]) for col in columns) for row in rows]
    return "\n".join([header, line, *body])


def cmd_status(args: argparse.Namespace) -> int:
    snap = collect_snapshot(include_events=args.json)
    if args.json:
        print(as_json(snap))
        return 0
    system = snap["system"]
    docker = snap["docker"]
    containers = snap["containers"]
    running = sum(1 for c in containers if "Up" in str(c.get("Status", "")))
    print("ADM status")
    print(f"Host: {system['hostname']} | Docker: {'online' if docker.get('available') else 'offline'} | Containers: {running}/{len(containers)} running")
    print(f"CPU load: {system['load_percent']}% | Memory: {system['memory']['percent']}% | Disk: {system['disk']['percent']}%")
    aws = system.get("aws", {})
    if aws.get("available"):
        print(f"AWS: {aws.get('instance_id')} {aws.get('instance_type')} {aws.get('availability_zone')} {aws.get('public_ipv4')}")
    print()
    for tip in snap["tips"]:
        print(f"[{tip['level'].upper()}] {tip['title']}: {tip['detail']}")
    return 0 if docker.get("available") else 2


def cmd_list(args: argparse.Namespace) -> int:
    rows = dockerctl.containers()
    if args.json:
        print(json.dumps(rows, indent=2))
        return 0
    print(_table(rows, ["Names", "Image", "Status", "Ports", "Health"]))
    return 0


def cmd_simple(args: argparse.Namespace) -> int:
    result = dockerctl.container_action(args.command, args.container)
    if result.stdout:
        print(result.stdout)
    if result.stderr:
        print(result.stderr, file=sys.stderr)
    return result.code


def cmd_logs(args: argparse.Namespace) -> int:
    result = dockerctl.logs(args.container, args.lines)
    if result.stdout:
        print(result.stdout)
    if result.stderr:
        print(result.stderr, file=sys.stderr)
    return result.code


def cmd_inspect(args: argparse.Namespace) -> int:
    print(json.dumps(dockerctl.inspect_container(args.container), indent=2))
    return 0


def cmd_resources(args: argparse.Namespace) -> int:
    if args.kind == "images":
        rows = dockerctl.images()
        cols = ["Repository", "Tag", "ID", "Size"]
    elif args.kind == "volumes":
        rows = dockerctl.volumes()
        cols = ["Name", "Driver", "Mountpoint"]
    else:
        rows = dockerctl.networks()
        cols = ["Name", "Driver", "Scope", "ID"]
    print(json.dumps(rows, indent=2) if args.json else _table(rows, cols))
    return 0


def cmd_prune(args: argparse.Namespace) -> int:
    result = dockerctl.prune()
    if result.stdout:
        print(result.stdout)
    if result.stderr:
        print(result.stderr, file=sys.stderr)
    return result.code


def cmd_console(args: argparse.Namespace) -> int:
    if not sys.stdin.isatty() or not sys.stdout.isatty():
        return cmd_status(argparse.Namespace(json=False))
    return run_console()


def _repo_dir() -> Path:
    installed = Path("/opt/adm/src")
    if (installed / ".git").exists():
        return installed
    cwd = Path.cwd()
    if (cwd / ".git").exists():
        return cwd
    package_root = Path(__file__).resolve().parents[1]
    if (package_root / ".git").exists():
        return package_root
    return cwd


def _run_update_command(args: list[str], cwd: Path) -> int:
    print(f"$ {' '.join(args)}")
    proc = subprocess.run(args, cwd=str(cwd), check=False)
    return int(proc.returncode)


def cmd_update(args: argparse.Namespace) -> int:
    repo = _repo_dir()
    if os.name != "nt" and hasattr(os, "geteuid") and os.geteuid() != 0:
        if not shutil.which("sudo"):
            print("ADM update needs root permissions, and sudo is not available.", file=sys.stderr)
            return 1
        print("ADM update needs root permissions. Re-running with sudo...")
        return subprocess.call(["sudo", sys.executable, "-m", "awsdockermanager.cli", "update"])

    if not (repo / ".git").exists():
        print(f"Cannot update: {repo} is not a git checkout.", file=sys.stderr)
        print("Install from https://github.com/yetval/ADM.git or run the installer from a cloned repo.", file=sys.stderr)
        return 1
    if not shutil.which("git"):
        print("Cannot update: git is not installed.", file=sys.stderr)
        return 1
    installer = repo / "scripts" / "install-aws.sh"
    if not installer.exists():
        print(f"Cannot update: missing installer at {installer}.", file=sys.stderr)
        return 1

    print(f"Updating ADM from {repo}")
    code = _run_update_command(["git", "pull", "--ff-only"], repo)
    if code != 0:
        return code
    code = _run_update_command(["bash", str(installer)], repo)
    if code != 0:
        return code
    print("ADM update complete.")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="adm", description="AWS Docker Manager")
    sub = parser.add_subparsers(dest="command")

    status = sub.add_parser("status", help="Show host, Docker, containers, and tips.")
    status.add_argument("--json", action="store_true")
    status.set_defaults(func=cmd_status)

    list_cmd = sub.add_parser("list", help="List containers.")
    list_cmd.add_argument("--json", action="store_true")
    list_cmd.set_defaults(func=cmd_list)

    for action in ["start", "stop", "restart", "pause", "unpause", "kill", "rm"]:
        p = sub.add_parser(action, help=f"{action} a container.")
        p.add_argument("container")
        p.set_defaults(func=cmd_simple)

    logs = sub.add_parser("logs", help="Show container logs.")
    logs.add_argument("container")
    logs.add_argument("--lines", type=int, default=120)
    logs.set_defaults(func=cmd_logs)

    inspect = sub.add_parser("inspect", help="Show full Docker inspect JSON.")
    inspect.add_argument("container")
    inspect.set_defaults(func=cmd_inspect)

    for kind in ["images", "volumes", "networks"]:
        p = sub.add_parser(kind, help=f"List Docker {kind}.")
        p.add_argument("--json", action="store_true")
        p.set_defaults(func=cmd_resources, kind=kind)

    prune_cmd = sub.add_parser("prune", help="Remove unused Docker objects.")
    prune_cmd.set_defaults(func=cmd_prune)

    console = sub.add_parser("console", help="Open the contained terminal dashboard.")
    console.set_defaults(func=cmd_console)

    update = sub.add_parser("update", help="Pull the latest ADM from GitHub and reinstall it.")
    update.set_defaults(func=cmd_update)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if not hasattr(args, "func"):
        return cmd_console(argparse.Namespace())
    return int(args.func(args) or 0)


if __name__ == "__main__":
    raise SystemExit(main())
