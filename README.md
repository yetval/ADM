# AWS Docker Manager

`adm` is a contained command-line dashboard for managing Docker containers on an AWS host.

Type `adm` or `ADM` and it opens the terminal console. No browser, no web service.

## Preview

```text
 ADM LIVE | ip-172-31-22-10                         scan #42 | next 2.7s
All scanned containers look steady.

+ DOCKER --+ + RUNNING -+ + PROBLEM -+ + CPU LOAD + + MEMORY -+ + DISK ---+
| online   | | 4/5      | | 1        | | 38.2%    | | 61.4%    | | 72.1%  |
+----------+ +----------+ +----------+ +----------+ +----------+ +--------+

+ ADVICE ----------------------+ + CONTAINERS --------------------------------+
| Recent error logs found      | | NAME                   STATE        CPU  MEM FLAGS
|  Open logs in ADM for: api   | | api                    running      2%   22% log-error
|                              | | worker                 restarting   0%   8%  restart-loop
+------------------------------+ +--------------------------------------------+

+ SELECTED --------------------+ + OUTPUT ------------------------------------+
| name: worker                 | | Live scanner started. Press / for commands |
| status: Restarting (1)       | | or q to quit.                              |
+------------------------------+ +--------------------------------------------+
```

## Install on AWS

```bash
git clone <repo-url> awsdockermanager
cd awsdockermanager
sudo ./scripts/install-aws.sh
```

After install:

```bash
adm status
adm list
adm
```

## Three-word commands

The command shape is intentionally short:

```bash
adm status
adm list
adm start <container>
adm stop <container>
adm restart <container>
adm logs <container>
adm inspect <container>
adm images
adm volumes
adm networks
adm prune
adm console
```

Inside the terminal console:

- `/` opens the command prompt.
- `r` refreshes.
- `j` / `k` or arrow keys move through containers.
- `s` starts the selected container.
- `x` stops the selected container.
- `e` restarts the selected container.
- `l` shows logs for the selected container.
- `q` quits.

## What the terminal dashboard shows

- Host CPU, memory, disk, load average, uptime, kernel, architecture, and AWS metadata when available.
- Docker daemon availability and version.
- Containers with state, image, health, restart count, and quick keyboard actions.
- A persistent live scan every three seconds.
- Problem flags for down containers, non-zero exits, unhealthy healthchecks, restart loops, OOM kills, Docker errors, high memory, and recent error-looking log lines.
- Tips for stopped, unhealthy, restarting, high-memory, high-disk, error-log, and missing-Docker situations.

## Development

Run without installing:

```bash
python3 -m awsdockermanager.cli status
python3 -m awsdockermanager.cli
```

Run checks:

```bash
python3 -m compileall awsdockermanager tests
python3 -m unittest discover -s tests
```

## Safety

ADM executes Docker operations as the current user. On AWS, run it as a user that has Docker permissions and avoid running arbitrary container names from untrusted input.
