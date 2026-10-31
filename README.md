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

> **Deprecated:** `agent/python` and `app/react` serve Zelos CLI 0.1.10 and older (`--type`) and Create Extension in Zelos 26.0.9 and older, which render a whole-project template from the latest release. Their manifests use the old `[host]` form, which `zelos extensions package` refuses from CLI 0.1.11 on. New projects use the parts above.

| Template | Type | Stack | Description |
|----------|------|-------|-------------|
| `agent/python` | Agent | Python | Python agent extension with data streaming, actions, and configuration |
| `app/react` | App | React + Vite | React web app extension with the Zelos app extension SDK |

With Zelos CLI 0.1.10 or older:

```bash
zelos extensions create my-sensor --type agent
zelos extensions create my-dashboard --type app
```

The CLI renders the project from the variables in the template's `template.toml`, installs dependencies, and initializes a git repository. CLI 0.1.11 and later read `--type` as `--with` and render parts.

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
└── .github/workflows/         # CI and the release workflow
```

## Whole-project template structure

Each deprecated template has:
- **`template.toml`** — declares variables (name, prompt, default, pattern), substitution includes, and optional directory renames
- **`template/`** — the project skeleton; files listed in `[template.substitution].include` are rendered through MiniJinja, all others are copied as-is

## CI

CI runs on pushes to `main` and on pull requests:

- **Validate** runs `just validate` on the whole-project templates and checks the formatting of the scripts, the parts' web sources and the whole-project templates' sources.
- **Smoke test template parts** runs `just smoke`: the renderer's tests, then the five combinations of parts (agent; tab; panel; agent + panel; agent + tab + panel) rendered with the reference renderer. It checks each project, lints its workflows with actionlint, packages it with the published Zelos CLI, and runs its CI: install, check, test, build and package. Then `just verify-dist` compares each web part's shipped lockfile with what `npm install` writes, and its `dist/` with a fresh build.
- **Smoke test agent/python** and **Smoke test app/react** run `just smoke-agent` and `just smoke-app`. They test a whole-project template only with a CLI without `--with`, so with the published CLI they exit without testing it.

The release workflow runs the same jobs on a tag push, creates the GitHub release only if all pass, and attaches `parts.tar.gz`.

## Contributing

See [CONTRIBUTING.md](./CONTRIBUTING.md) for local testing, the release process, and development guidelines.
