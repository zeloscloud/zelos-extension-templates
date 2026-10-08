set shell := ["bash", "-eu", "-o", "pipefail", "-c"]

export ZELOS_EXTENSION_TEMPLATES_DIR := justfile_directory()
zelos_bin := env_var_or_default("ZELOS_BIN", "zelos")

default:
    @just --list

# ---------- checks ----------

# Fast structural validation (no CLI needed)
validate:
    #!/usr/bin/env bash
    set -eu -o pipefail
    errors=0

    for tpl in agent/python app/react; do
      echo "Checking $tpl ..."

      if [[ ! -f "$tpl/template.toml" ]]; then
        echo "  ✗ missing template.toml"; errors=$((errors+1)); continue
      fi
      echo "  ✓ template.toml"

      if [[ ! -d "$tpl/template" ]]; then
        echo "  ✗ missing template/ directory"; errors=$((errors+1)); continue
      fi
      echo "  ✓ template/ directory"

      includes=$(python3 -c "
    import pathlib, sys
    try:
        import tomllib
    except ModuleNotFoundError:
        import importlib
        tomllib = importlib.import_module('tomli')
    cfg = tomllib.loads(pathlib.Path('$tpl/template.toml').read_text())
    for f in cfg['template']['substitution']['include']:
        print(f)
    " 2>/dev/null || uvx --quiet --with tomli python3 -c "
    import tomli, pathlib
    cfg = tomli.loads(pathlib.Path('$tpl/template.toml').read_text())
    for f in cfg['template']['substitution']['include']:
        print(f)
    ")
      while IFS= read -r f; do
        if [[ ! -f "$tpl/template/$f" ]]; then
          echo "  ✗ include list references missing file: $f"; errors=$((errors+1))
        fi
      done <<< "$includes"
      echo "  ✓ include list files exist"

      for required in extension.toml README.md Justfile .gitignore; do
        if [[ ! -f "$tpl/template/$required" ]]; then
          echo "  ✗ missing required file: $required"; errors=$((errors+1))
        fi
      done
      echo "  ✓ required files present"

      for dx in .github/workflows/CI.yml .github/workflows/release.yml .github/dependabot.yml .vscode/settings.json .vscode/extensions.json; do
        if [[ ! -f "$tpl/template/$dx" ]]; then
          echo "  ✗ missing DX file: $dx"; errors=$((errors+1))
        fi
      done
      echo "  ✓ CI/DX files present"
    done

    if [[ $errors -gt 0 ]]; then
      echo ""
      echo "✗ $errors error(s) found"
      exit 1
    fi
    echo ""
    echo "✓ Structure validation passed"

# Format template source files (safe pre-render subset)
fmt:
    #!/usr/bin/env bash
    set -eu -o pipefail
    echo "Formatting Python template sources ..."
    ruff format --isolated --no-respect-gitignore agent/python/template/tests/
    ruff check --isolated --no-respect-gitignore --fix agent/python/template/tests/
    echo "Formatting parts sources and scripts ..."
    ruff format --isolated --target-version py311 --no-respect-gitignore scripts/ parts/agent-python/template/tests/
    ruff check --isolated --target-version py311 --no-respect-gitignore --fix scripts/ parts/agent-python/template/tests/
    npx -y prettier@3 --write "parts/**/*.{ts,tsx,css,mjs}"
    echo "Formatting React template sources ..."
    cd app/react/template && npx -y prettier@3 --write src/

# Run all checks: parts smoke, validate, format, render + test both templates
ci:
    just smoke
    just verify-dist
    just validate
    just _fmt-check
    just smoke-agent
    just smoke-app
    @echo ""
    @echo "✓ All CI checks passed"

# ---------- smoke tests ----------

# Render template parts into OUT (base is always included), e.g. just render-parts agent-python,panel /tmp/probe
render-parts PARTS OUT NAME="probe":
    python3 scripts/render_parts.py --parts "{{PARTS}}" --out "{{OUT}}" --var name="{{NAME}}"

# Test the parts renderer, render the five combinations of parts, check each one and run its CI
smoke:
    #!/usr/bin/env bash
    set -eu -o pipefail
    python3 -c 'import sys; sys.exit(sys.version_info < (3, 11))' || { echo "Error: Python 3.11+ required"; exit 1; }
    for tool in uv npm actionlint; do
      command -v "$tool" &>/dev/null || { echo "Error: $tool not found"; exit 1; }
    done

    echo "Testing the parts renderer ..."
    python3 -m unittest discover -s scripts -p 'test_*.py'

    sdk=$(just _sdk)
    if [[ -z "$sdk" ]]; then
      echo "Warning: the app extension SDK is not on npm at the range web/package.json names, and SDK_TGZ is not set."
      echo "  Projects with a web project are rendered, checked and packaged, but their CI is skipped."
    fi
    # Packaging needs a CLI that reads the [agent] and [app] manifest form, i.e. one with --with.
    zelos=""
    if "{{zelos_bin}}" extensions create --help 2>/dev/null | grep -q -- "--with"; then
      zelos=$(command -v "{{zelos_bin}}")
    else
      echo "Warning: '{{zelos_bin}}' cannot package projects made from parts; packaging is skipped."
      echo "  Set ZELOS_BIN to a CLI whose 'extensions create' has --with."
    fi

    out=$(mktemp -d)
    trap 'rm -rf "$out"' EXIT
    skipped=0
    for combo in agent-python:agent app-react:tab panel:panel agent-python,panel:agent,panel agent-python,app-react,panel:agent,tab,panel; do
      parts="${combo%%:*}"
      expect="${combo##*:}"
      project="$out/${expect//,/-}/probe"
      echo ""
      echo "== base,$parts"
      python3 scripts/render_parts.py --parts "base,$parts" --out "$project" \
        --var name=probe --var description="Probe sensors" --var author="Ada Lovelace" --var github=your-org
      python3 scripts/check_project.py "$project" --expect "$expect"
      cat "$project/extension.toml"
      actionlint "$project"/.github/workflows/*.yml
      if [[ -n "$zelos" ]]; then
        # The project packages as rendered, before any install or build: the web parts ship a built dist/.
        (
          cd "$project"
          "$zelos" extensions package .
          if [[ -f web/package.json ]]; then
            tar -tzf probe-0.1.0.tar.gz | grep -E '^(\./)?dist/.+[^/]$' || { echo "  ✗ the package has no dist/"; exit 1; }
          fi
          rm probe-0.1.0.tar.gz
        )
      fi
      if [[ -f "$project/web/package.json" && -z "$sdk" ]]; then
        echo "  - skipped the project CI: no app extension SDK to install"
        skipped=$((skipped + 1))
        continue
      fi
      (
        cd "$project"
        # Install as zelos extensions create does, then run the project's CI recipes.
        if [[ -f pyproject.toml ]]; then uv sync --quiet; fi
        if [[ $sdk != npm && -f web/package.json ]]; then
          (cd web && npm install --no-audit --no-fund "$sdk")
        fi
        just ci-install check test build
        if [[ -n "$zelos" ]]; then "$zelos" extensions package .; fi
      )
    done
    echo ""
    if [[ $skipped -gt 0 ]]; then
      echo "✓ All five combinations of parts passed; the CI of $skipped web projects was skipped"
    else
      echo "✓ All five combinations of parts passed, each with its own CI"
    fi

# Rebuild each web part alone and compare with the dist/ it ships; a stale dist/ is rebuilt in place
verify-dist:
    #!/usr/bin/env bash
    set -eu -o pipefail
    sdk=$(just _sdk)
    if [[ -z "$sdk" ]]; then
      echo "Warning: the app extension SDK is not on npm at the range web/package.json names, and SDK_TGZ is not set."
      echo "  Skipped the check of the shipped dist/: nothing to build it with."
      exit 0
    fi
    out=$(mktemp -d)
    trap 'rm -rf "$out"' EXIT
    stale=()
    for part in app-react panel; do
      echo "== $part"
      project="$out/$part/probe"
      python3 scripts/render_parts.py --parts "base,$part" --out "$project" --var name=probe
      cp -R "$project/dist" "$out/$part/shipped"
      if [[ $sdk == npm ]]; then
        (cd "$project/web" && npm install --no-audit --no-fund)
      else
        (cd "$project/web" && npm install --no-audit --no-fund --no-save "$sdk")
      fi
      (cd "$project/web" && npm run build)
      if diff -r "$out/$part/shipped" "$project/dist"; then
        echo "  ✓ parts/$part/template/dist matches its source"
        continue
      fi
      stale+=("parts/$part/template/dist")
      rm -rf "parts/$part/template/dist"
      cp -R "$project/dist" "parts/$part/template/dist"
      # Rendered documents keep their template expressions, e.g. the tab's <title>.
      python3 - "$part" <<'EOF'
    import pathlib, re, sys, tomllib
    part = pathlib.Path("parts", sys.argv[1])
    config = tomllib.loads((part / "template.toml").read_text())
    for entry in config["template"]["substitution"]["include"]:
        if entry.startswith("dist/"):
            source = (part / "template/web/src" / entry.removeprefix("dist/")).read_text()
            title = re.search(r"<title>.*?</title>", source).group(0)
            built = part / "template" / entry
            built.write_text(re.sub(r"<title>.*?</title>", lambda _: title, built.read_text(), count=1))
    EOF
    done
    if [[ ${#stale[@]} -gt 0 ]]; then
      echo ""
      echo "✗ ${stale[*]} did not match the source; it is now rebuilt."
      echo "  Commit it with: git add -f -A ${stale[*]}"
      exit 1
    fi
    echo ""
    echo "✓ The shipped dist/ of each web part matches its source"

# Render + test agent/python template
smoke-agent:
    #!/usr/bin/env bash
    set -eu -o pipefail

    if ! command -v "{{zelos_bin}}" &>/dev/null; then
      echo "Error: Zelos CLI not found at '{{zelos_bin}}'"
      echo "  Install: curl -fsSL https://release.zeloscloud.io/cli/install.sh | bash"
      echo "  Or set:  ZELOS_BIN=/path/to/zelos just smoke-agent"
      exit 1
    fi
    if ! command -v actionlint &>/dev/null; then
      echo "Error: actionlint not found (https://github.com/rhysd/actionlint)"
      exit 1
    fi

    out=$(mktemp -d)
    trap "rm -rf $out" EXIT

    echo "Rendering agent template → $out/test-smoke-agent ..."
    "{{zelos_bin}}" extensions create test-smoke-agent --type agent --no-setup --output "$out"

    cd "$out/test-smoke-agent"
    echo "Linting generated workflows ..."
    actionlint .github/workflows/*.yml
    echo "Locking dependencies as zelos extensions create does ..."
    uv sync
    echo "Installing from the lock as the generated CI does ..."
    just ci-install
    echo "Running generated project CI ..."
    just ci

    echo ""
    echo "✓ agent/python passed"

# Render + test app/react template
smoke-app:
    #!/usr/bin/env bash
    set -eu -o pipefail

    if ! command -v "{{zelos_bin}}" &>/dev/null; then
      echo "Error: Zelos CLI not found at '{{zelos_bin}}'"
      echo "  Install: curl -fsSL https://release.zeloscloud.io/cli/install.sh | bash"
      echo "  Or set:  ZELOS_BIN=/path/to/zelos just smoke-app"
      exit 1
    fi
    if ! command -v actionlint &>/dev/null; then
      echo "Error: actionlint not found (https://github.com/rhysd/actionlint)"
      exit 1
    fi

    out=$(mktemp -d)
    template_dir=$(mktemp -d)
    trap "rm -rf $out $template_dir" EXIT

    rsync -a --exclude node_modules --exclude .git "$ZELOS_EXTENSION_TEMPLATES_DIR/" "$template_dir/"

    echo "Rendering app template → $out/test-smoke-app ..."
    ZELOS_EXTENSION_TEMPLATES_DIR="$template_dir" "{{zelos_bin}}" extensions create test-smoke-app --type app --no-setup --output "$out"

    cd "$out/test-smoke-app"
    echo "Linting generated workflows ..."
    actionlint .github/workflows/*.yml
    echo "Checking the shipped dist/ against a fresh build ..."
    just install
    just verify-dist
    echo "Running generated project CI ..."
    just ci

    echo ""
    echo "✓ app/react passed"

# Render app template locally for manual testing
test-app-local NAME="test-smoke-app":
    #!/usr/bin/env bash
    set -eu -o pipefail

    if ! command -v "{{zelos_bin}}" &>/dev/null; then
      echo "Error: Zelos CLI not found at '{{zelos_bin}}'"
      echo "  Install: curl -fsSL https://release.zeloscloud.io/cli/install.sh | bash"
      echo "  Or set:  ZELOS_BIN=/path/to/zelos just test-app-local"
      exit 1
    fi

    out="${ZELOS_TEMPLATE_OUTPUT_ROOT:-$HOME/Desktop/delete}"
    mkdir -p "$out"
    rm -rf "$out/{{NAME}}"

    template_dir=$(mktemp -d)
    trap "rm -rf $template_dir" EXIT
    rsync -a --exclude node_modules --exclude .git "$ZELOS_EXTENSION_TEMPLATES_DIR/" "$template_dir/"

    echo "Rendering app template → $out/{{NAME}} ..."
    ZELOS_EXTENSION_TEMPLATES_DIR="$template_dir" "{{zelos_bin}}" extensions create "{{NAME}}" --type app --no-setup --output "$out"

    cd "$out/{{NAME}}"
    just ci

    echo ""
    echo "✓ Local app test passed: $out/{{NAME}}"

# ---------- release ----------

# Tag a new release (CI creates the GitHub release after validation)
release VERSION:
    #!/usr/bin/env bash
    set -eux -o pipefail

    git diff-index --quiet HEAD || (echo "Uncommitted changes! Commit or stash first." && exit 1)

    if ! [[ "{{VERSION}}" =~ ^[0-9]+\.[0-9]+\.[0-9]+(-[a-zA-Z0-9.]+)?$ ]]; then
      echo "Error: '{{VERSION}}' is not valid semver (expected X.Y.Z)"
      exit 1
    fi

    just ci

    echo "Tagging v{{VERSION}} ..."
    git tag -a "v{{VERSION}}" -m "Release v{{VERSION}}"
    git push --follow-tags

    echo ""
    echo "✓ Tagged v{{VERSION}} and pushed."
    echo "  CI will create the GitHub release after validation passes."

# Delete a GitHub release and its tags
delete-release VERSION:
    #!/usr/bin/env bash
    set -euo pipefail

    tag="v{{VERSION}}"

    echo "Deleting GitHub release $tag ..."
    gh release delete "$tag" --yes 2>/dev/null && echo "  ✓ release deleted" || echo "  - no release found"

    echo "Deleting remote tag $tag ..."
    git push origin --delete "$tag" 2>/dev/null && echo "  ✓ remote tag deleted" || echo "  - no remote tag"

    echo "Deleting local tag $tag ..."
    git tag -d "$tag" 2>/dev/null && echo "  ✓ local tag deleted" || echo "  - no local tag"

    echo ""
    echo "✓ Cleaned up $tag"

# ---------- cleanup ----------

# Remove generated test artifacts
clean:
    rm -rf .ruff_cache

# ---------- internal ----------

# Print where the web projects get the app extension SDK: SDK_TGZ as an absolute path, "npm", or nothing.
# SDK_TGZ=/path/to/sdk.tgz installs it from a local tarball (npm pack) before it is published.
_sdk:
    #!/usr/bin/env bash
    set -eu -o pipefail
    if [[ -n "${SDK_TGZ:-}" ]]; then
      [[ -f "$SDK_TGZ" ]] || { echo "Error: SDK_TGZ=$SDK_TGZ does not exist" >&2; exit 1; }
      echo "$(cd "$(dirname "$SDK_TGZ")" && pwd)/$(basename "$SDK_TGZ")"
      exit 0
    fi
    range=$(python3 -c "import json; print(json.load(open('parts/app-react/template/web/package.json'))['dependencies']['@zeloscloud/app-extension-sdk'])")
    if [[ -n "$(npm view "@zeloscloud/app-extension-sdk@$range" version 2>/dev/null)" ]]; then echo npm; fi

_fmt-check:
    #!/usr/bin/env bash
    set -eu -o pipefail
    echo "Checking template source formatting ..."
    ruff format --isolated --no-respect-gitignore --check agent/python/template/tests/
    ruff check --isolated --no-respect-gitignore agent/python/template/tests/
    ruff format --isolated --target-version py311 --no-respect-gitignore --check scripts/ parts/agent-python/template/tests/
    ruff check --isolated --target-version py311 --no-respect-gitignore scripts/ parts/agent-python/template/tests/
    npx -y prettier@3 --check "parts/**/*.{ts,tsx,css,mjs}"
    cd app/react/template && npx -y prettier@3 --check src/
