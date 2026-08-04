# Installing LuraminaKIT

`LuraminaKIT` depends on the sibling [`contractsKIT`](../contractsKIT) project, so both need to be installed editable into the same virtual environment. It also needs at least one [modulesKIT](../modulesKIT) module running to have any commands to proxy.

## Prerequisites

- **Python 3.12 or newer** (required — `LuraminaKIT` uses `typing.override`, a 3.12 feature).
- **git**.
- A Discord bot token — see [Discord's developer portal](https://discord.com/developers/applications) if you don't have one yet.

## 1. Get Python 3.12+

### Windows

1. Install from [python.org/downloads](https://www.python.org/downloads/) (check **"Add python.exe to PATH"**), or:
   ```powershell
   winget install Python.Python.3.12
   ```
2. Verify:
   ```powershell
   py -3.12 --version
   ```

### Debian / Ubuntu (apt)

```bash
sudo apt update
sudo apt install python3.12 python3.12-venv python3-pip git
```

If `python3.12` isn't available on your release yet, add the [deadsnakes PPA](https://launchpad.net/~deadsnakes/+archive/ubuntu/ppa) first:

```bash
sudo add-apt-repository ppa:deadsnakes/ppa
sudo apt update
sudo apt install python3.12 python3.12-venv
```

### Arch Linux (pacman)

```bash
sudo pacman -S python git
python --version   # confirm it's 3.12+
```

## 2. Clone the repository

`LuraminaKIT` expects `contractsKIT` to be checked out as a sibling folder:

```bash
git clone <this-repo-url> Discord_Bot
cd Discord_Bot
ls   # should show both contractsKIT/ and LuraminaKIT/
```

## 3. Create and activate a virtual environment

From the repository root:

**Linux (Debian/Ubuntu or Arch):**
```bash
python3.12 -m venv .venv
source .venv/bin/activate
```

**Windows (PowerShell):**
```powershell
py -3.12 -m venv .venv
.venv\Scripts\Activate.ps1
```
> If PowerShell refuses to run the activation script: `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` (once, as the current user).

Your prompt should now be prefixed with `(.venv)`.

## 4. Install, editable

`contractsKIT` first, since `LuraminaKIT` depends on it:

```bash
pip install --upgrade pip
pip install -e ./contractsKIT -e ./LuraminaKIT
```

This pulls in `LuraminaKIT`'s third-party dependencies too (discord.py, aiohttp, pydantic, pydantic-settings, python-dotenv, langchain-text-splitters, psutil).

## 5. Configure

Configuration is split across two files, merged at startup:

- **`config.json`** (not part of the installed package, safe to edit freely) — `modules`: the modulesKIT modules to poll for commands (`name`/`port`/`prefix` must match that module's own `modulesKIT/config.json` entry).
- **`.env`** — your Discord bot token, kept separate so it's never accidentally committed:
  ```bash
  cp LuraminaKIT/.env.example LuraminaKIT/.env
  ```
  then edit `LuraminaKIT/.env` and set `DISCORD_TOKEN=<your token>`. `.env` is gitignored.

## 6. Run

With at least one modulesKIT module already running:

```bash
python LuraminaKIT/main.py
```

Works from any directory — the launcher resolves its own `config.json`, `.env`, and `logs/` relative to its own location. Pass `-c /path/to/other-config.json` to use a different config file.
