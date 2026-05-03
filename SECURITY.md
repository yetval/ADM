# Security

ADM manages Docker containers through the local Docker CLI. Anyone who can run ADM with Docker permissions can start, stop, inspect, remove, and prune Docker resources on that host.

## Reporting Issues

Open a private security advisory on GitHub if the issue is sensitive:

https://github.com/yetval/ADM/security/advisories

For normal bugs, use GitHub issues:

https://github.com/yetval/ADM/issues

## Operational Guidance

- Run ADM only as a trusted user.
- Do not expose a shell running ADM to untrusted users.
- Avoid running ADM as root unless your deployment requires it.
- Review `adm prune` usage before running it on production hosts.
- Keep Docker and the host OS patched.
