# Installing contractsKIT

`contractsKIT` is a dependency-only library — shared pydantic contracts used by [modulesKIT](../modulesKIT) and [LuraminaKIT](../LuraminaKIT). It has no launcher of its own, so "installing" it means installing it editable into the same virtual environment as whichever of those two projects you're running.

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

## 2. Clone alongside its dependents

`contractsKIT` is meant to sit next to `modulesKIT` and/or `LuraminaKIT` as sibling folders:

```bash
git clone <this-repo-url> Discord_Bot
cd Discord_Bot
```

## 3. Create and activate a virtual environment

From the repository root (shared with any sibling project you're also installing):

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

## 4. Install, editable

```bash
pip install --upgrade pip
pip install -e ./contractsKIT
```

If you're also setting up `modulesKIT` and/or `LuraminaKIT` in the same environment, see their own `INSTALL.md` — install `contractsKIT` first since both depend on it.

## Verify

```bash
python -c "import contractsKIT; print(contractsKIT.__file__)"
```

This should print a path under `contractsKIT/src/contractsKIT/__init__.py`.
