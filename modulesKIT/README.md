# MODULESKIT

Trying to make modules for a fun Discord bot...

It's still a "work in progress" as of now... And there is a lot of room for improvement.

The main goal here is to try to make somewhat generic modules that can be easily added / removed with minimal code change on the bot side.

Each module is its own small [FastAPI](https://fastapi.tiangolo.com/) service — its own process, its own port, its own `main_<module>.py` launcher. A module advertises what it offers at `/api/<module>/url-list` using the shared [`contractsKIT`](../contractsKIT) contract, and [LuraminaKIT](../LuraminaKIT) discovers and calls those routes at runtime, so adding a new module shouldn't require touching the bot's code.

## MODULES

Each module has its own doc under [`docs/`](docs) — routes, config, data files, examples:

- [**anyquotes**](docs/anyquotes.md) (`main_anyquotes.py`, port `8001`) — random quotes from CSV files, rendered through a configurable template.
- [**tb1**](docs/tb1.md) (`main_tb1.py`, port `8002`) — Terra Battle 1 companion: pact roll simulator, daily quest forecast, event info.

## INSTALLATION

See [`INSTALL.md`](INSTALL.md) for step-by-step setup instructions (Windows, Debian/Ubuntu, Arch Linux).

## RUNNING

Each module is its own launcher; run whichever ones you need, with the shared venv active:

```bash
python main_anyquotes.py
python main_tb1.py
```

Every launcher resolves `config.json`, `data/`, and `logs/` relative to its own location (not your current directory), so this also works from anywhere:

```bash
python /path/to/modulesKIT/main_tb1.py
```

Pass `-c /path/to/other-config.json` to use a different config file.

## ADDING A NEW MODULE

See [`HOWTO.md`](HOWTO.md) for a full walkthrough (scaffolding, wiring routes, the launcher script, registering with LuraminaKIT) with a worked example.

## VERSIONS

- 0.0.1-alpha: First release

## TABLE OF CONTENT

<!-- TOC -->

- [MODULESKIT](#moduleskit)
  - [MODULES](#modules)
  - [INSTALLATION](#installation)
  - [RUNNING](#running)
  - [ADDING A NEW MODULE](#adding-a-new-module)
  - [VERSIONS](#versions)
  - [TABLE OF CONTENT](#table-of-content)

<!-- /TOC -->
