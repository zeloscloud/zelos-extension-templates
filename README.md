# Zelos Extension Templates

Official starter templates for [Zelos](https://github.com/zeloscloud) extensions. Templates are consumed by the `zelos` CLI, which uses a **MiniJinja** engine to render project files.

## Available Templates

| Template | Type | Stack | Description |
|----------|------|-------|-------------|
| `agent/python` | Agent | Python | Python agent extension with data streaming, actions, and configuration |
| `app/react` | App | React + Vite | React web app extension with the Zelos app extension SDK |

## Quickstart

```bash
# Create an agent extension
zelos extensions create my-sensor --type agent

# Create an app extension
zelos extensions create my-dashboard --type app
```

The CLI prompts for variables defined in each template's `template.toml`, renders the project, installs dependencies, and initializes a git repository.

## Layout

```
zelos-extension-templates/
├── agent/python/
│   ├── template.toml          # Variables, includes, dir_renames
│   └── template/              # Project files (MiniJinja expressions)
├── app/react/
│   ├── template.toml
│   └── template/
└── .github/workflows/         # CI validates both templates
```

## Template Structure

Each template has:
- **`template.toml`** — declares variables (name, prompt, default, pattern), substitution includes, and optional directory renames
- **`template/`** — the project skeleton; files listed in `[template.substitution].include` are rendered through MiniJinja, all others are copied as-is

## CI

CI renders each template through the published Zelos CLI (the same engine users use), then runs the generated project's full check suite — lint, type-check, test, build, and package. A separate release workflow re-runs these checks on tag push and only creates the GitHub release if all pass.

## Contributing

See [CONTRIBUTING.md](./CONTRIBUTING.md) for local testing, the release process, and development guidelines.
