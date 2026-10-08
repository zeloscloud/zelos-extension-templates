# Zelos Extension Templates

Official starter templates for [Zelos](https://github.com/zeloscloud) extensions. Templates are consumed by the `zelos` CLI, which uses a **MiniJinja** engine to render project files.

## Template parts

A project is assembled from parts, so one extension can combine an agent runtime, a tab and panels under one `extension.toml`.

| Part | Adds | `--with` |
|------|------|----------|
| `parts/base` | Manifest, README, license, Justfile, CI and release workflows | always |
| `parts/agent-python` | Python agent runtime (`[agent]`) | `agent` |
| `parts/app-react` | React + Vite web project with a tab (`[app] tab`) | `tab` |
| `parts/panel` | A layout panel (`[[app.panels]]`) | `panel` |

```bash
zelos extensions create probe --with agent,panel
```

[`parts/README.md`](parts/README.md) holds the merge rules every renderer follows and a worked example. [`scripts/render_parts.py`](scripts/render_parts.py) is the reference renderer:

```bash
just render-parts agent-python,panel /tmp/probe   # render one combination
just smoke                                        # render all five combinations and run their CI
```

## Whole-project templates (deprecated)

> **Deprecated:** `agent/python` and `app/react` stay for CLIs without `--with` for one more release, then they are removed. New projects use the parts above.

| Template | Type | Stack | Description |
|----------|------|-------|-------------|
| `agent/python` | Agent | Python | Python agent extension with data streaming, actions, and configuration |
| `app/react` | App | React + Vite | React web app extension with the Zelos app extension SDK |

```bash
zelos extensions create my-sensor --type agent
zelos extensions create my-dashboard --type app
```

The CLI prompts for variables defined in each template's `template.toml`, renders the project, installs dependencies, and initializes a git repository.

## Layout

```
zelos-extension-templates/
├── parts/                     # base, agent-python, app-react, panel; README.md has the merge rules
│   └── <part>/
│       ├── template.toml      # Variables, includes, dir_renames, borrow
│       └── template/          # Project files and .part fragments
├── scripts/                   # Reference renderer, project checks and their tests
├── agent/python/              # Deprecated whole-project template
├── app/react/                 # Deprecated whole-project template
└── .github/workflows/         # CI validates the parts and both templates
```

## Template Structure

Each template has:
- **`template.toml`** — declares variables (name, prompt, default, pattern), substitution includes, and optional directory renames
- **`template/`** — the project skeleton; files listed in `[template.substitution].include` are rendered through MiniJinja, all others are copied as-is

## CI

On every push, CI renders the five combinations of parts (agent; tab; panel; agent + panel; agent + tab + panel) with the reference renderer, checks each project, lints its workflows with actionlint and runs its CI: install, format check, lint, type-check, test and build. It also renders each whole-project template through the published Zelos CLI, then runs the generated project's full check suite — lint, type-check, test, build, and package. A separate release workflow re-runs these checks on tag push, creates the GitHub release only if all pass, and attaches `parts.tar.gz`.

## Contributing

See [CONTRIBUTING.md](./CONTRIBUTING.md) for local testing, the release process, and development guidelines.
