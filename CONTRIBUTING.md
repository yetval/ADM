# Contributing

Thanks for improving ADM.

## Local Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e .
python -m unittest discover -s tests
```

## Checks

Run these before opening a pull request:

```bash
python -m compileall awsdockermanager tests
python -m unittest discover -s tests
adm --help
```

## Notes

- Keep ADM fully contained in the terminal. Do not add a web server or browser UI.
- Keep Docker access behind the Docker CLI wrapper in `awsdockermanager/dockerctl.py`.
- Tests should not require Docker to be installed.
