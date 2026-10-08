# Template parts

A Zelos extension project is assembled from parts. Each part adds one thing: the shared
project files, an agent runtime, a tab, or a panel. One project can combine an agent
runtime, a tab and panels, and one `extension.toml` describes all of them.

| Part | Adds | Manifest | `zelos extensions create --with` |
| ---- | ---- | -------- | -------------------------------- |
| `base` | `extension.toml`, README, license, Justfile, CI and release workflows, dependabot, pre-commit hooks, VS Code settings | identity, `[zelos]`, `[package]` | always |
| `agent-python` | `main.py`, the Python package, `pyproject.toml`, `config.schema.json`, tests | `[config]`, `[agent]` | `agent` |
| `app-react` | the Vite + React + Tailwind project under `web/` (ESLint, Prettier, Vitest), with a tab in `web/src/tab/` and its build in `dist/` | `[app] tab` | `tab` |
| `panel` | one panel, `example`, in `web/src/panels/`, and its build in `dist/` | `[[app.panels]]` | `panel` |

The renderer in this repository, [`scripts/render_parts.py`](../scripts/render_parts.py), is
the executable form of the rules below. The `zelos` CLI must produce byte-identical output.

```bash
python3 scripts/render_parts.py --parts base,agent-python,panel --out /tmp/probe \
  --var name=probe --var python_version=3.11
just render-parts agent-python,panel /tmp/probe   # the same, with default variables
just smoke                                        # five combinations, checked and run
```

## Layout of a part

```
parts/<part>/
├── template.toml      # metadata, variables, substitution, optional borrow
└── template/          # files copied into the project
    ├── extension.toml.part   # optional fragment: tables for extension.toml (T2)
    └── Justfile.part         # optional fragment: recipes for the Justfile (T3)
```

`template.toml` keeps the schema of the whole-project templates, with two changes: `part`
replaces `host_type`, and an optional `[template.borrow]` table implements T3.

```toml
[template]
part = "panel"                      # must equal the directory name
description = "One layout panel"

[[template.variables]]              # same fields as today: name, prompt, default, pattern
name = "python_version"
prompt = "Python version (major.minor, e.g. 3.11)"
default = "3.11"

[template.borrow]                   # optional, see T3
part = "app-react"
exclude = ["web/src/tab", "dist", "extension.toml.part"]

[template.substitution]
include = ["extension.toml.part"]   # files rendered through MiniJinja; must not be empty

[template.substitution.dir_renames] # optional; rendered after substitution
extension = "{{ project_slug }}"
```

## Rendering

The renderer resolves the selection, renders each part into its own staging directory, and
then merges the staging directories into the project in order.

1. **Selection.** `base` is always selected. A name outside the four parts is an error.
2. **Variables.** The variables are the union of the `[[template.variables]]` of every
   rendered part, including a borrowed one; the first declaration of a name wins. A missing
   value takes its `default`; a variable without a default is required. A `pattern` must
   match the whole value. Empty values are then removed, so `{% if var %}` is false. Two
   values are derived last: `project_slug` is `name` in lowercase with `-` replaced by `_`,
   and `repository` is `https://github.com/<github>/<name>` when `github` is set.
3. **One part.** Copy `template/` to a staging directory. Render every path in `include`
   through MiniJinja. Apply each `dir_renames` entry: render the target name, and fail when
   the source is missing or the target exists. Paths in `include` and `dir_renames` are the
   paths before renaming, and they are safe relative paths.
4. **Merge.** Walk the staging directory. A file named `extension.toml.part` or
   `Justfile.part` at its root is a fragment: keep its rendered text for T2 or T3 and never
   copy it into the project. Any other `*.part` file is an error. Every other file is copied
   into the project under T1, with its file mode.
5. **Fragments.** After the last part, merge the fragments into `extension.toml` (T2) and
   the `Justfile` (T3), in part order.
6. **Output.** Build the project in a staging directory and move it to the output path only
   when every step succeeded. The output path must not exist, or must be empty.

MiniJinja settings, as in the CLI today: `trim_blocks` and `lstrip_blocks` on; an undefined
variable renders as an empty string; a trailing newline that `trim_blocks` removed at the end
of a file is restored. Filters: `toml_escape`, `json_escape`, `title` (each word: first letter
uppercase, the rest lowercase), and the built-ins `replace`, `lower` and `upper`. The parts
use only `{{ … }}` expressions with filters and `{% if %}` / `{% elif %}` / `{% else %}`
blocks with `and`, `or` and `not`. A file with no variables stays out of `include`, so the
`${{ … }}` expressions in workflows and `{{VERSION}}` in Justfiles need no `{% raw %}`.

## Merge rules

### T1 · Order and ownership

Parts render in this order, whatever order the caller gives: `base`, `agent-python`,
`app-react`, `panel`. A later part can add files. It never overwrites a file that an earlier
part produced, except through a `.part` fragment. The renderer fails with
`<part>: <path> was already produced by <earlier part>; extend it with a .part fragment instead`.

### T2 · `extension.toml.part`

A fragment appends TOML tables to `extension.toml`.

- A fragment holds tables only. A key above its first table header is an error; comments
  and blank lines there are kept.
- A standard table header (`[agent]`, `[agent.stop]`) that an earlier part already declared
  is an error: `<part>: extension.toml.part declares [agent], which <earlier part> already declares`.
- An array-of-tables header (`[[app.panels]]`) always appends, from any number of parts. It
  is an error when an earlier part declared the same key as a standard table.
- `[package]` is special. In `base` and in every fragment it may hold only `paths`. The
  merged `paths` is the union of every part's `paths`, in part order, without duplicates,
  starting with the paths of `base`. `[package.*]` and `[[package]]` are errors.
- Output: the text of `base` without its `[package]` table, then each fragment's text
  without its `[package]` table, then `[package]` with the merged `paths` written on one line
  as `paths = ["a", "b"]`. Chunks are separated by one blank line, and the file ends with
  one newline. Tables are copied as text, so comments and formatting stay as written.
- The merged text must parse as TOML, else the renderer fails.

### T3 · `Justfile.part` and the web scaffold

A `Justfile.part` appends recipes to the `Justfile`: the `Justfile` text, a blank line, then
each fragment in part order. A recipe name may appear once in the merged file; a duplicate
is an error. The shared verbs (`install`, `ci-install`, `format`, `check`, `test`, `build`,
`package`, `ci`, `release`, `clean`) live in `base` and act on what exists: the agent runtime
when `pyproject.toml` exists, the web project when `web/package.json` exists. Fragments add
distinct names only: `agent-python` adds `run` and `lock`, `app-react` adds `dev`, `watch` and
`test-watch`.

The same holds for the other files every project shares, because only one part can produce a
file: `base` owns `.pre-commit-config.yaml` (ruff hooks for Python files, Prettier and ESLint
hooks for `web/`), `.github/dependabot.yml` (uv at `/`, npm at `/web`, GitHub Actions) and
`.vscode/`.

`web/package.json` exists only when `app-react` or `panel` is selected. `app-react` owns the
web scaffold. `panel` without `app-react` brings the same scaffold minus the tab, through
`[template.borrow]`:

- When a selected part borrows from a part that is not selected, the renderer renders the
  lender's `template/` as an extra step just before the borrower, with the lender's
  `include` and `dir_renames`, skipping every path equal to or under an `exclude` entry.
  Files from this step count as produced by the borrower for T1.
- When the lender is selected, the borrow does nothing.

`panel` borrows `app-react` and excludes `web/src/tab`, `dist` and `extension.toml.part`, so a
panel-only project has the web scaffold and no tab, no built tab and no `[app] tab`.

The web project builds every document into `dist/` at the project root. `vite.config.ts`
finds the documents on disk, so adding a panel needs no config change:

| Source | Output | Manifest |
| ------ | ------ | -------- |
| `web/src/tab/index.html` | `dist/tab/index.html` | `[app] tab` |
| `web/src/panels/<id>.html` | `dist/panels/<id>.html` | `[[app.panels]] entry` |
| `web/public/panels/<id>.options.json` | `dist/panels/<id>.options.json` | `[[app.panels]] options_schema` |

A web part ships its build in `template/dist/`, so a new project installs in Zelos before
anyone runs npm. Each part's `dist/` is the build of that part rendered alone, and holds only
its own documents and their hashed assets. A project with the tab and a panel gets the union of
both, and its first `npm run build` replaces it. The hashed assets stay out of `include`, so
they copy byte for byte; a document that shows a variable, such as the tab's `<title>`, is in
`include`. `just verify-dist` builds each web part again and compares the result with its
`dist/`. It rewrites a stale `dist/` in place; commit it with `git add -f`, because
`.gitignore` ignores `dist/`.

### T4 · Release workflow

`base` ships one `.github/workflows/release.yml` for every combination. Its steps are
conditional on files, not on the parts that were selected:

- The uv setup runs when `pyproject.toml` exists: `if: hashFiles('pyproject.toml') != ''`.
- The Node setup runs when `web/package.json` exists: `if: hashFiles('web/package.json') != ''`.
- The install, check, test and package steps run the shared `just` recipes, which act on what
  exists (T3). One `zelos extensions package .` packages everything.

`.github/workflows/CI.yml` follows the same conditions. A project that adds a part by hand
later keeps working without a workflow change.

## Worked example: agent + panel

`--parts base,agent-python,panel` with `name=probe`, `description=Probe sensors`,
`author=Ada Lovelace`, `github=your-org` and the default `python_version` renders this
`extension.toml`. The units render in the order `base`, `agent-python`,
`panel (from app-react)`, `panel`. A test renders it and compares it with this block.

<!-- worked-example -->
```toml
name = "Probe"
version = "0.1.0"
description = "Probe sensors"
author = "Ada Lovelace"
repository = "https://github.com/your-org/probe"
icon = "assets/icon.svg"
readme = "README.md"

[zelos]
version = ">=26.0.10"

[config]
schema = "config.schema.json"

[agent]
runtime = "python"
entry = "main.py"
python_version = "3.11"

[[app.panels]]
id = "example"
name = "Example Panel"
description = "Latest value of each bound signal"
# icon = "assets/example.svg"        # optional; list its directory in [package] paths
entry = "dist/panels/example.html"
accepts = []                         # event-type prefixes (e.g. "zelos.can.frame.") a drop routes to this panel
affiliates = []                      # prefixes that ride along with an accepted drop
binds = "any"                        # "any" or "accepted"
default_height = 2
live_only = false
options_schema = "dist/panels/example.options.json"
ai_guidance = "Shows the latest value of each bound signal, one row per signal."

[package]
paths = ["main.py", "probe", "dist"]
```

`base` contributes the identity keys, `[zelos]` and an empty `paths`. `agent-python`
contributes `[config]`, `[agent]` and the paths `main.py` and `probe` (the renamed package).
The borrowed scaffold contributes no table, because `extension.toml.part` of `app-react` is
excluded. `panel` contributes `[[app.panels]]` and the path `dist`.

A manifest with panels must set `[zelos] version = ">=26.0.10"` or stricter, so `base` sets
it for every combination.

## Release archive

A tag publishes `parts.tar.gz` beside the source archives. Its root holds the `parts/`
directory as it is in this repository: `parts/<part>/template.toml` and
`parts/<part>/template/…`. The CLI reads it from the release, or from a local file named by
`ZELOS_EXTENSION_TEMPLATE_ARCHIVE`.
