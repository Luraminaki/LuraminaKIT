# Installing modulesKIT

`modulesKIT` depends on the sibling [`contractsKIT`](../contractsKIT) project, so both need to be installed editable into the same virtual environment.

## Prerequisites

- **Python 3.12 or newer**.
- **git**.

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

`modulesKIT` expects `contractsKIT` to be checked out as a sibling folder:

```bash
git clone <this-repo-url> Discord_Bot
cd Discord_Bot
ls   # should show both contractsKIT/ and modulesKIT/
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

`contractsKIT` first, since `modulesKIT` depends on it:

```bash
pip install --upgrade pip
pip install -e ./contractsKIT -e ./modulesKIT
```

This pulls in `modulesKIT`'s third-party dependencies too (FastAPI, uvicorn, pydantic, unidecode).

## 5. Configure

`modulesKIT/config.json` holds per-module settings (port, description, module-specific data like the `anyquotes` quote template) — it's not part of the installed package, so it's safe to edit freely. Paths inside it (like the data directory) are resolved relative to `modulesKIT/`, not your current directory.

## 6. Run

```bash
python modulesKIT/main_anyquotes.py
```

Works from any directory — the launcher resolves its own `config.json`, `data/`, and `logs/` relative to its own location. Pass `-c /path/to/other-config.json` to use a different config file.

## Verify

With `anyquotes` running:

```bash
curl http://127.0.0.1:8001/api/anyquotes/url-list
curl http://127.0.0.1:8001/api/anyquotes/quote
```

Both should return a JSON body shaped like `{"status": "SUCCESS", "data": ..., "error": ""}`.

## Optional: OCR module dependencies

A future OCR-based module will need extra, heavier dependencies. They're declared separately so they aren't installed by default:

```bash
pip install -e "./modulesKIT[ocr]"
```
