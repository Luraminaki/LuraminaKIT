# CONTRACTSKIT

Shared pydantic contracts between [modulesKIT](../modulesKIT) and [LuraminaKIT](../LuraminaKIT).

It's still a "work in progress" as of now... And there is a lot of room for improvement.

This package holds the wire format the two projects agree on, so neither has to guess at the shape of the other's responses:

- `StatusFunction` / `StandardResponse[T]` — the standard `{status, data, error}` envelope every modulesKIT route returns.
- `ModuleManifest` / `RouteDescriptor` / `ParamDescriptor` — the self-description a module advertises at its `/url-list` route, letting LuraminaKIT discover commands without either side hard-coding the other's routes.
- `configure_launcher_logging` — shared, rotating-file logging setup used by both projects' launcher scripts.

It has no launcher of its own; it exists purely to be installed editable alongside the other two. See [`INSTALL.md`](INSTALL.md) for setup instructions.

## CONTRIBUTING

See [`HOWTO.md`](HOWTO.md) before changing anything here — this package is shared by both other projects, and a change here can affect both.

## VERSIONS

- 0.1.0-alpha: First release

## TABLE OF CONTENT

<!-- TOC -->

- [CONTRACTSKIT](#contractskit)
  - [CONTRIBUTING](#contributing)
  - [VERSIONS](#versions)
  - [TABLE OF CONTENT](#table-of-content)

<!-- /TOC -->
