# Contributing

## Prerequisites

- [Zelos CLI](https://docs.zeloscloud.io/cli)
- [just](https://github.com/casey/just)
- [uv](https://docs.astral.sh/uv/), when the project has an agent runtime (`pyproject.toml`)
- Node.js 24 LTS (see `web/.nvmrc`), when the project has a web project (`web/package.json`)

## Layout

`extension.toml` describes everything the extension contributes:

| Part | Files | Manifest |
| ---- | ----- | -------- |
| Agent runtime | `main.py`, the Python package, `pyproject.toml`, `config.schema.json` | `[agent]` |
| Tab | `web/src/tab/` | `[app] tab` |
| Panels | `web/src/panels/<id>.html`, `web/src/panels/<id>/` | `[[app.panels]]` |

The web project builds every tab and panel document into `dist/` at the project root. A new
project ships this `dist/` prebuilt, so it installs in Zelos before its first build; the first
`just build` (`npm run build`) replaces it.

## Commands

| Command                | Description                                        |
| ---------------------- | -------------------------------------------------- |
| `just install`         | Install dependencies and the pre-commit hooks      |
| `just format`          | Format code with ruff and Prettier                 |
| `just check`           | Check formatting, lint (ruff, ESLint), type-check  |
| `just test`            | Run tests (pytest, Vitest)                         |
| `just build`           | Build the web project into `dist/`                 |
| `just package`         | Build and package for the Zelos marketplace        |
| `just release VERSION` | Bump version, check, test, build, commit, tag      |
| `just clean`           | Remove build output, caches and packages           |

`just --list` also shows the recipes each part adds. `just install` installs the
pre-commit hooks in `.pre-commit-config.yaml` when the project has an agent runtime; with a
web project only, install [pre-commit](https://pre-commit.com) yourself and run
`pre-commit install`.

## Run it in Zelos

```bash
just build
zelos extensions install-local .
```

A local install reads your project directory on every request. After a rebuild, reload the
tab or the panel to see the change; you do not need to install again. With a web project, keep
`just watch` running to rebuild on every save, and use `just dev` to work on a tab or panel in
the browser against the mock host of the SDK.

## Packaging

```bash
just package
```

The archive lands next to `extension.toml` as `{name}-{version}.tar.gz`. It contains the
paths listed in `[package] paths`.

## Release

```bash
just release 1.0.0
git push --follow-tags
```

The release workflow checks, tests, builds and packages the extension, then attaches the
archive to a GitHub release.
