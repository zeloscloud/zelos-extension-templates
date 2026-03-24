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
    echo "Formatting React template sources ..."
    cd app/react/template && npx -y prettier@3 --write src/

# Run all checks: validate, format, render + test both templates
ci:
    just validate
    just _fmt-check
    just smoke-agent
    just smoke-app
    @echo ""
    @echo "✓ All CI checks passed"

# ---------- smoke tests ----------

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

    out=$(mktemp -d)
    trap "rm -rf $out" EXIT

    echo "Rendering agent template → $out/test-smoke-agent ..."
    "{{zelos_bin}}" extensions create test-smoke-agent --type agent --no-setup --output "$out"

    cd "$out/test-smoke-agent"
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

    out=$(mktemp -d)
    template_dir=$(mktemp -d)
    trap "rm -rf $out $template_dir" EXIT

    rsync -a --exclude node_modules --exclude .git "$ZELOS_EXTENSION_TEMPLATES_DIR/" "$template_dir/"

    echo "Rendering app template → $out/test-smoke-app ..."
    ZELOS_EXTENSION_TEMPLATES_DIR="$template_dir" "{{zelos_bin}}" extensions create test-smoke-app --type app --no-setup --output "$out"

    cd "$out/test-smoke-app"
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

_fmt-check:
    #!/usr/bin/env bash
    set -eu -o pipefail
    echo "Checking template source formatting ..."
    ruff format --isolated --no-respect-gitignore --check agent/python/template/tests/
    ruff check --isolated --no-respect-gitignore agent/python/template/tests/
    cd app/react/template && npx -y prettier@3 --check src/
