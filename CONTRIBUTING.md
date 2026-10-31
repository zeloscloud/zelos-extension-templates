# Contributing

## Prerequisites

- [Zelos CLI](https://docs.zeloscloud.io/getting-started/install-cli/) with `extensions create --with` (`zelos` on PATH, or set `ZELOS_BIN`)
- Python 3.11+, [uv](https://docs.astral.sh/uv/) and [ruff](https://docs.astral.sh/ruff/)
- Node.js 24 LTS with npm
- [actionlint](https://github.com/rhysd/actionlint) (the smoke tests lint the rendered workflows)

## Quick reference

```bash
just fmt          # Format the scripts and the template sources
just smoke        # Test the parts renderer, render all five combinations of parts and run their CI
just render-parts agent-python,panel /tmp/probe   # Render one combination of parts
just verify-dist  # Rebuild each web part and compare it with the dist/ it ships
just validate     # Check the structure of the whole-project templates (no CLI needed)
just ci           # Run everything: smoke, verify-dist, validate, format check, smoke-agent, smoke-app
```

## Using an unreleased CLI

Set `ZELOS_BIN` to test with a local CLI build:

```bash
ZELOS_BIN=~/path/to/src/api/rs/target/debug/zelos just ci
```

## Parts development

- `scripts/render_parts.py` is the executable form of the merge rules in `parts/README.md`. Change both together; the CLI copies its behavior from them.
- Add a file with `{{ }}` or `{% %}` expressions to the part's `include` list. Keep files without variables out of it, so `${{ }}` and Justfile `{{VERSION}}` need no `{% raw %}`.
- A part never overwrites another part's file. Extend `extension.toml` with `extension.toml.part` and the `Justfile` with `Justfile.part`.
- `just smoke` must pass; it also checks that the worked example in `parts/README.md` matches a real render. It needs uv, npm and actionlint. Before the app extension SDK version that `web/package.json` names is on npm, set `SDK_TGZ` to a tarball from `npm pack`; without it the web projects are rendered and checked, and their CI is skipped. It needs a Zelos CLI with `extensions create --with` (`zelos`, or `ZELOS_BIN`): packaging each project runs the CLI's manifest validator.
- After a change to a web part's source or dependencies, run `just verify-dist`. It rebuilds a stale `dist/` in place; commit it with `git add -f`, because `.gitignore` ignores `dist/`.

### Generated project Justfile contract

Every combination of parts has the same shared recipes, which act on the parts the project has:

`install`, `ci-install`, `format`, `check`, `test`, `build`, `package`, `ci`, `release VERSION`, `delete-release VERSION`, `clean`

`agent-python` adds `run` and `lock`; `app-react` adds `dev`, `watch` and `test-watch`. The generated CI workflow runs the steps of `ci`: `ci-install`, `check`, `test` and `package`.

## Whole-project templates (deprecated)

`agent/python` and `app/react` serve Zelos CLI 0.1.10 and older and Create Extension in Zelos 26.0.9 and older. Change them only to keep those working.

- `just smoke-agent` and `just smoke-app` render them with `--type` and run the project's CI. With a CLI that has `--with` they exit without testing, because such a CLI renders parts for `--type`. Set `ZELOS_BIN` to CLI 0.1.10 or older to test them.
- `just test-app-local [NAME]` renders `--type app` from this checkout into `~/Desktop/delete/NAME` (or `$ZELOS_TEMPLATE_OUTPUT_ROOT/NAME`) and runs its `just ci`. A CLI with `--with` renders the tab part there; an older one renders `app/react`.
- `app/react` ships a prebuilt `dist/`. After a change to its source or dependencies, rebuild it with `cd app/react/template && npm ci && npm run build`, then `git add -f dist`.

## Release process

1. `just fmt` — format the scripts and the template sources
2. `just ci` — run every check
3. `just release X.Y.Z` — runs `ci` again, then tags and pushes
4. The release workflow runs CI on the tag and creates the GitHub release with `parts.tar.gz`

### Release ordering

Templates depend on CLI features. When CLI and templates change together:

1. **Merge and publish** CLI changes first
2. **Push** template changes that use the new CLI features
3. **Tag** a template release

Template repo tags are independent of the CLI version.

When the web parts must align with a **new published** SDK:

1. **Publish** `@zeloscloud/app-extension-sdk` to npm
2. **Update** `parts/app-react/template/web/package.json` to the published semver range, and run `just verify-dist`
3. **Push** and **tag** a template release

## Pull requests

- Keep `template.toml` variables and substitution lists in sync with the Zelos CLI create flow
- Run `just ci` before submitting
