# Installing the whole monorepo

This is the full walkthrough for setting up all three projects together. If you only care about one project in isolation, its own `INSTALL.md` ([`contractsKIT/INSTALL.md`](contractsKIT/INSTALL.md), [`modulesKIT/INSTALL.md`](modulesKIT/INSTALL.md), [`LuraminaKIT/INSTALL.md`](LuraminaKIT/INSTALL.md)) covers the same steps without the other two — this file just avoids repeating the shared setup three times.

## Prerequisites

- **Python 3.12 or newer** (all three projects require it — `LuraminaKIT` uses `typing.override`, a 3.12 feature).
- **git**.
- A Discord bot token for `LuraminaKIT` — see [Discord's developer portal](https://discord.com/developers/applications) if you don't have one yet.

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

```bash
git clone <this-repo-url> Discord_Bot
cd Discord_Bot
```

## 3. Create and activate the shared virtual environment

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

## 4. Install all three projects, editable

`contractsKIT` first, since the other two depend on it:

```bash
pip install --upgrade pip
pip install -e ./contractsKIT -e ./modulesKIT -e ./LuraminaKIT
```

## 5. Configure

- **`modulesKIT/config.json`** — module ports, descriptions, per-module settings. Not part of the installed package, safe to edit freely.
- **`LuraminaKIT/config.json`** — bot behavior and the list of modules to poll (`name`/`port`/`prefix` must match the corresponding `modulesKIT/config.json` entry).
- **`LuraminaKIT/.env`** — the Discord bot token, kept out of `config.json` on purpose so it's never accidentally committed. Copy the template and fill it in:
  ```bash
  cp LuraminaKIT/.env.example LuraminaKIT/.env
  ```
  then edit `LuraminaKIT/.env` and set `DISCORD_TOKEN=<your token>`. `.env` is gitignored; `.env.example` is the committed template.

## 6. Run

**All at once** — `run.py` at the repo root starts every module with `auto_start`
enabled in `modulesKIT/config.json` (defaults to `true`; set a module's own entry
to `false` to skip it, e.g. on weaker hardware), then runs the bot in the
foreground so its logs stream to this terminal. Ctrl+C stops everything, modules
included:

```bash
python run.py
```

**Individually** — each launcher resolves its own `config.json`/`.env`/`data/`/
`logs/` relative to its own location, so these work from anywhere and don't need
`run.py` at all:

```bash
python modulesKIT/main_anyquotes.py   # starts the anyquotes FastAPI service (port 8001 by default)
python LuraminaKIT/main.py            # starts the Discord bot
```

Logs are written next to each project (`modulesKIT/logs/`, `LuraminaKIT/logs/`) and roll over automatically once they reach 5 MiB, keeping the last 5 files.

## 7. Verify

With `anyquotes` running:

```bash
curl http://127.0.0.1:8001/api/anyquotes/url-list
curl http://127.0.0.1:8001/api/anyquotes/quote
```

Both should return a JSON body shaped like `{"status": "SUCCESS", "data": ..., "error": ""}`.
