# Contributing

## Prerequisites

- [Zelos CLI](https://release.zeloscloud.io) (`zelos` on PATH, or set `ZELOS_BIN`)
- Python 3.11+ with [ruff](https://docs.astral.sh/ruff/)
- Node.js 24 LTS with npm
- [actionlint](https://github.com/rhysd/actionlint) (the smoke tests lint the rendered workflows)

## Quick reference

```bash
just fmt          # Format template source files
just smoke        # Test the parts renderer, render all five combinations of parts and run their CI
just render-parts agent-python,panel /tmp/probe   # Render one combination of parts
just ci           # Run everything: parts smoke, validate, format-check, render + test both templates
just smoke-agent  # Render + test agent template only
just smoke-app    # Render + test app template only
just validate     # Fast structural check (no CLI needed)
```

## Using an unreleased CLI

Set `ZELOS_BIN` to test with a local CLI build:

```bash
ZELOS_BIN=~/path/to/src/api/rs/target/debug/zelos just ci
```

## Test template changes locally

### Full CI (both templates)

```bash
just ci
```

This validates structure, checks source formatting, renders both templates through the CLI, and runs each generated project's full `just ci` — format-check, lint, type-check, test, and package.

### Agent (Python)

```bash
just smoke-agent
```

### App (React)

```bash
just smoke-app
```

### App — local output for manual testing

Renders the app template to a persistent directory (default `~/Desktop/delete`):

```bash
just test-app-local
just test-app-local my-dashboard
```

Override the output location:

```bash
ZELOS_TEMPLATE_OUTPUT_ROOT=/tmp just test-app-local my-app
```

## Parts development

- `scripts/render_parts.py` is the executable form of the merge rules in `parts/README.md`. Change both together; the CLI copies its behavior from them.
- Add a file with `{{ }}` or `{% %}` expressions to the part's `include` list. Keep files without variables out of it, so `${{ }}` and Justfile `{{VERSION}}` need no `{% raw %}`.
- A part never overwrites another part's file. Extend `extension.toml` with `extension.toml.part` and the `Justfile` with `Justfile.part`.
- `just smoke` must pass; it also checks that the worked example in `parts/README.md` matches a real render. It needs uv, npm and actionlint. Before the app extension SDK version that `web/package.json` names is on npm, set `SDK_TGZ` to a tarball from `npm pack`; without it the web projects are rendered and checked, and their CI is skipped. Packaging runs when `ZELOS_BIN` (or `zelos`) has `extensions create --with`.

## Template development

### Adding or modifying template files

- Files containing `{{ }}` or `{% %}` expressions **must** be listed in `[template.substitution].include` in the template's `template.toml`
- Static files (no MiniJinja expressions) are copied as-is and do **not** need to be in the include list
- Keep both templates consistent: same variable names, same Justfile recipe names, same CI structure

### App template `dist/`

The app template ships a prebuilt `dist/`, so a new project installs without a build. After changing the app template's source or dependencies, rebuild it in place and stage it with `-f`, because the template's own `.gitignore` ignores `dist/`:

```bash
cd app/react/template && npm ci && npm run build
git add -f dist
```

`just smoke-app` fails when the committed `dist/` differs from a fresh build.

### Generated project Justfile contract

Both templates expose the same top-level commands for extension developers:

`install`, `dev`, `format`, `check`, `test`, `build`, `package`, `release VERSION`, `clean`

Plus a unified `ci` recipe used by this repo's smoke tests and by the generated project's own CI workflow.

### Adding a new template variant

1. Create `{type}/{stack}/template.toml` with variables and include list
2. Create `{type}/{stack}/template/` with the project skeleton
3. Add a smoke test in the root `Justfile`
4. Add the template to the CI workflow
5. Update `README.md`

## Release process

1. `just fmt` — format template source files
2. `just ci` — validate + render + test + package both templates
3. `just release X.Y.Z` — runs `ci` again, then tags and pushes
4. CI re-validates on the tag and creates the GitHub release automatically

### Release ordering

Templates depend on CLI features. When CLI and templates change together:

1. **Merge and publish** CLI changes first
2. **Push** template changes that use the new CLI features
3. **Tag** a template release

Template repo tags are independent of the CLI version.

When the **app** template must align with a **new published** SDK:

1. **Publish** `@zeloscloud/app-extension-sdk` to npm
2. **Update** `app/react/template/package.json` to the published semver range
3. **Push** and **tag** a template release

## Pull requests

- Keep `template.toml` variables and substitution lists in sync with the Zelos CLI create flow
- Run `just ci` before submitting
- Both templates must maintain DX parity: same Justfile commands, same CI structure, same VS Code configuration
