# ADM

[![CI](https://github.com/yetval/ADM/actions/workflows/ci.yml/badge.svg)](https://github.com/yetval/ADM/actions/workflows/ci.yml)

ADM is a contained terminal dashboard for managing Docker containers on an AWS host.

Type `adm` or `ADM` and it opens the live console. No browser. No web service.

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

## Install On AWS

```bash
git clone https://github.com/yetval/ADM.git
cd ADM
sudo ./scripts/install-aws.sh
```

The installer creates an isolated Python environment at `/opt/adm`, installs `adm` into it, and links `adm` and `ADM` into `/usr/local/bin`.

If Docker group permissions were changed during install, log out and back in before running ADM as your normal user. On a fresh EC2 install, this is usually required. You can also run `newgrp docker` in the current shell.

Upgrade an existing install:

```bash
ADM update
```

## Use

Open the live terminal console:

```bash
adm
```

Run direct commands:

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
ADM update
```

Inside the terminal console:

- `/` opens the command prompt.
- `r` refreshes immediately.
- `j` / `k` or arrow keys move through containers.
- `s` starts the selected container.
- `x` stops the selected container.
- `e` restarts the selected container.
- `l` shows logs for the selected container.
- `i` inspects the selected container.
- `q` quits.

## Live Scanning

ADM scans continuously every three seconds and highlights:

- Docker offline or unreachable.
- Containers that are down or exited.
- Non-zero container exit codes.
- Unhealthy Docker healthchecks.
- Restart loops.
- OOM kills.
- Docker state errors.
- High container memory usage.
- Recent log lines containing error, fatal, exception, traceback, panic, critical, permission denied, connection refused, or out-of-memory signals.
- Host CPU, memory, and disk pressure.

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

Install locally:

```bash
python3 -m pip install -e .
adm
```

## Security

ADM executes Docker operations as the current user. On AWS, run it as a trusted user with Docker permissions. Do not expose a shell running ADM to untrusted users.

## License

MIT. See [LICENSE](LICENSE).
