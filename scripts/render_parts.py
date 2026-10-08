#!/usr/bin/env python3
"""Reference renderer for Zelos extension template parts.

This script is the executable form of the merge rules T1-T4 in parts/README.md.
The `zelos extensions create --with ...` renderer must produce the same output.

Usage:
    python3 scripts/render_parts.py --parts base,agent-python,panel --out DIR \
        --var name=probe --var python_version=3.11

Standard library only (Python 3.11+).
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
import tempfile
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

PARTS_DIR = Path(__file__).resolve().parent.parent / "parts"

# T1: parts always render in this order, whatever order the caller gives.
PART_ORDER = ("base", "agent-python", "app-react", "panel")
ALWAYS = "base"

# T2/T3: a fragment `<target>.part` at a part's root extends `<target>`.
FRAGMENT_TARGETS = ("extension.toml", "Justfile")
FRAGMENT_SUFFIX = ".part"


class RenderError(Exception):
    pass


# Bytes, not text mode: text mode rewrites newlines (CRLF on Windows), and the CLI does not.
def _read(path: Path) -> str:
    return path.read_bytes().decode("utf-8")


def _write(path: Path, text: str) -> None:
    path.write_bytes(text.encode("utf-8"))


# --------------------------------------------------------------------------------------
# Template engine: the subset of MiniJinja the parts use, with the CLI's settings
# (trim_blocks, lstrip_blocks, undefined renders as "", custom filters).
# --------------------------------------------------------------------------------------

_TAG_RE = re.compile(r"\{\{(.*?)\}\}|\{%(.*?)%\}|\{#.*?#\}", re.DOTALL)
_ENDRAW_RE = re.compile(r"\{%\s*endraw\s*%\}")


def _toml_escape(value: str) -> str:
    return (
        value.replace("\\", "\\\\")
        .replace('"', '\\"')
        .replace("\n", "\\n")
        .replace("\r", "\\r")
        .replace("\t", "\\t")
        .replace("\b", "\\b")
        .replace("\f", "\\f")
    )


def _json_escape(value: str) -> str:
    return json.dumps(value, ensure_ascii=False)[1:-1]


def _title(value: str) -> str:
    return " ".join(word[:1].upper() + word[1:].lower() for word in value.split())


FILTERS = {
    "toml_escape": (_toml_escape, 0),
    "json_escape": (_json_escape, 0),
    "title": (_title, 0),
    "replace": (str.replace, 2),
    "lower": (str.lower, 0),
    "upper": (str.upper, 0),
}

_EXPR_TOKEN_RE = re.compile(
    r"""\s*(?:(?P<str>"(?:[^"\\]|\\.)*"|'(?:[^'\\]|\\.)*')|(?P<name>[A-Za-z_][A-Za-z0-9_]*)|(?P<op>[|(),]))"""
)


_ESCAPES = {"n": "\n", "t": "\t", "r": "\r"}


def _expr_tokens(source: str) -> list[tuple[str, str]]:
    tokens: list[tuple[str, str]] = []
    pos = 0
    source = source.strip()
    while pos < len(source):
        match = _EXPR_TOKEN_RE.match(source, pos)
        if not match:
            raise RenderError(f"unsupported expression: {source!r}")
        kind = match.lastgroup
        text = match.group(kind)
        if kind == "str":
            text = re.sub(
                r"\\(.)", lambda m: _ESCAPES.get(m.group(1), m.group(1)), text[1:-1]
            )
        tokens.append((kind, text))
        pos = match.end()
    return tokens


class _Expr:
    """Recursive-descent parser for: names, string literals, `|` filters, and/or/not."""

    def __init__(self, source: str) -> None:
        self.source = source
        self.tokens = _expr_tokens(source)
        self.pos = 0

    def parse(self):
        node = self._or()
        if self.pos != len(self.tokens):
            raise RenderError(f"unexpected token in expression: {self.source!r}")
        return node

    def _peek(self) -> tuple[str, str] | None:
        return self.tokens[self.pos] if self.pos < len(self.tokens) else None

    def _take(self, kind: str, text: str | None = None) -> str:
        token = self._peek()
        if token is None or token[0] != kind or (text is not None and token[1] != text):
            raise RenderError(f"malformed expression: {self.source!r}")
        self.pos += 1
        return token[1]

    def _is(self, kind: str, text: str) -> bool:
        return self._peek() == (kind, text)

    def _or(self):
        node = self._and()
        while self._is("name", "or"):
            self.pos += 1
            node = ("or", node, self._and())
        return node

    def _and(self):
        node = self._not()
        while self._is("name", "and"):
            self.pos += 1
            node = ("and", node, self._not())
        return node

    def _not(self):
        if self._is("name", "not"):
            self.pos += 1
            return ("not", self._not())
        return self._filtered()

    def _filtered(self):
        node = self._primary()
        while self._is("op", "|"):
            self.pos += 1
            name = self._take("name")
            if name not in FILTERS:
                raise RenderError(f"unknown filter {name!r} in {self.source!r}")
            args: list[str] = []
            if self._is("op", "("):
                self.pos += 1
                while not self._is("op", ")"):
                    args.append(self._take("str"))
                    if not self._is("op", ")"):
                        self._take("op", ",")
                self._take("op", ")")
            if len(args) != FILTERS[name][1]:
                raise RenderError(
                    f"filter {name!r} takes {FILTERS[name][1]} argument(s)"
                )
            node = ("filter", name, node, args)
        return node

    def _primary(self):
        token = self._peek()
        if token is None:
            raise RenderError(f"empty expression: {self.source!r}")
        if token == ("op", "("):
            self.pos += 1
            node = self._or()
            self._take("op", ")")
            return node
        self.pos += 1
        if token[0] == "str":
            return ("lit", token[1])
        if token[0] == "name" and token[1] not in ("and", "or", "not"):
            return ("var", token[1])
        raise RenderError(f"malformed expression: {self.source!r}")


def _evaluate(node, variables: dict[str, str]):
    kind = node[0]
    if kind == "lit":
        return node[1]
    if kind == "var":
        return variables.get(node[1])  # undefined is None, renders as ""
    if kind == "not":
        return not _evaluate(node[1], variables)
    if kind == "and":
        return _evaluate(node[1], variables) and _evaluate(node[2], variables)
    if kind == "or":
        return _evaluate(node[1], variables) or _evaluate(node[2], variables)
    if kind == "filter":
        _, name, inner, args = node
        return FILTERS[name][0](_to_str(_evaluate(inner, variables)), *args)
    raise AssertionError(kind)


def _to_str(value) -> str:
    if value is None:
        return ""
    if value is True:
        return "true"
    if value is False:
        return "false"
    return str(value)


def _evaluate_source(source: str, variables: dict[str, str]):
    return _evaluate(_Expr(source).parse(), variables)


def _push_text(tokens: list[tuple[str, str]], text: str) -> None:
    if text:
        tokens.append(("text", text))


def _lstrip_before(source: str, start: int, tokens: list[tuple[str, str]]) -> None:
    """lstrip_blocks: drop spaces/tabs between the line start and a block tag."""
    prefix = source[source.rfind("\n", 0, start) + 1 : start]
    if not prefix or prefix.strip(" \t") or not tokens or tokens[-1][0] != "text":
        return
    text = tokens[-1][1]
    if text.endswith(prefix):
        tokens.pop()
        _push_text(tokens, text[: -len(prefix)])


def _trim_after(source: str, end: int) -> int:
    """trim_blocks: drop the first newline after a block tag."""
    for newline in ("\r\n", "\n"):
        if source.startswith(newline, end):
            return end + len(newline)
    return end


def _lex(source: str) -> list[tuple[str, str]]:
    """Split a template into text, var and block tokens, applying trim/lstrip rules."""
    tokens: list[tuple[str, str]] = []
    pos = 0
    while match := _TAG_RE.search(source, pos):
        _push_text(tokens, source[pos : match.start()])
        pos = _lex_tag(source, match, tokens)
    _push_text(tokens, source[pos:])
    return tokens


def _lex_tag(source: str, match: re.Match, tokens: list[tuple[str, str]]) -> int:
    """Append the tokens of one tag; return the position after it."""
    var, block = match.group(1), match.group(2)
    if var is not None:
        if var.startswith("-") or var.endswith("-"):
            raise RenderError("whitespace control ('-') is not supported")
        tokens.append(("var", var))
        return match.end()
    _lstrip_before(source, match.start(), tokens)
    if block is None:  # comment
        return _trim_after(source, match.end())
    if block.startswith(("-", "+")) or block.endswith(("-", "+")):
        raise RenderError("whitespace control ('-', '+') is not supported")
    statement = block.strip()
    if statement != "raw":
        tokens.append(("block", statement))
        return _trim_after(source, match.end())
    end = _ENDRAW_RE.search(source, match.end())
    if not end:
        raise RenderError("{% raw %} without {% endraw %}")
    _push_text(tokens, source[_trim_after(source, match.end()) : end.start()])
    _lstrip_before(source, end.start(), tokens)
    return _trim_after(source, end.end())


def _apply_block(
    statement: str, stack: list[list[bool]], emitting: bool, variables: dict[str, str]
) -> bool:
    """Apply one if/elif/else/endif tag; return whether output is emitted after it."""
    keyword, _, rest = statement.partition(" ")
    if keyword == "if":
        cond = emitting and bool(_evaluate_source(rest, variables))
        stack.append([emitting, cond])
        return cond
    if keyword not in ("elif", "else", "endif") or (keyword != "elif" and rest):
        raise RenderError(f"unsupported block tag: {{% {statement} %}}")
    if not stack:
        raise RenderError(f"{{% {keyword} %}} without {{% if %}}")
    if keyword == "endif":
        return stack.pop()[0]
    # Each frame is [parent_emitting, branch_taken].
    frame = stack[-1]
    cond = (
        frame[0]
        and not frame[1]
        and (keyword == "else" or bool(_evaluate_source(rest, variables)))
    )
    frame[1] = frame[1] or cond
    return cond


def render_template(source: str, variables: dict[str, str]) -> str:
    output: list[str] = []
    stack: list[list[bool]] = []
    emitting = True
    for kind, value in _lex(source):
        if kind == "block":
            emitting = _apply_block(value, stack, emitting, variables)
        elif emitting:
            output.append(
                value if kind == "text" else _to_str(_evaluate_source(value, variables))
            )
    if stack:
        raise RenderError("{% if %} without {% endif %}")
    rendered = "".join(output)
    # The CLI restores a trailing newline that trim_blocks removed.
    if source.endswith("\n") and not rendered.endswith("\n"):
        rendered += "\n"
    return rendered


# --------------------------------------------------------------------------------------
# Parts and variables
# --------------------------------------------------------------------------------------


@dataclass
class Part:
    name: str
    template_dir: Path
    variables: list[dict]
    include: list[str]
    dir_renames: dict[str, str]
    borrow_part: str | None
    borrow_exclude: list[str]


def load_part(parts_dir: Path, name: str) -> Part:
    root = parts_dir / name
    config_path = root / "template.toml"
    if not config_path.is_file():
        raise RenderError(f"unknown part {name!r}: {config_path} is missing")
    config = tomllib.loads(_read(config_path))["template"]
    if config.get("part") != name:
        raise RenderError(f"{config_path}: [template] part must be {name!r}")
    substitution = config.get("substitution", {})
    include = substitution.get("include", [])
    if not include:
        raise RenderError(
            f"{config_path}: template.substitution.include must not be empty"
        )
    borrow = config.get("borrow", {})
    return Part(
        name=name,
        template_dir=root / "template",
        variables=config.get("variables", []),
        include=include,
        dir_renames=substitution.get("dir_renames", {}),
        borrow_part=borrow.get("part"),
        borrow_exclude=borrow.get("exclude", []),
    )


def resolve_variables(parts: list[Part], given: dict[str, str]) -> dict[str, str]:
    """Defaults, validation, empty stripping and derived values, as the CLI does."""
    values = dict(given)
    declared: dict[str, dict] = {}
    for part in parts:
        for variable in part.variables:
            declared.setdefault(variable["name"], variable)
    for name, variable in declared.items():
        if name not in values:
            if "default" not in variable:
                raise RenderError(f"missing template variable: {name}")
            values[name] = variable["default"]
        value = values[name]
        pattern = variable.get("pattern")
        if pattern and not re.fullmatch(f"(?:{pattern})", value):
            raise RenderError(f"value for {name!r} does not match required pattern")
    if "python_version" in declared and not re.fullmatch(
        r"\d+\.\d+", values["python_version"]
    ):
        raise RenderError("python_version must look like 3.11")
    values = {key: value for key, value in values.items() if value != ""}
    values["project_slug"] = values["name"].lower().replace("-", "_")
    if "github" in values:
        values["repository"] = f"https://github.com/{values['github']}/{values['name']}"
    return values


def _safe_relative(path: str, context: str) -> Path:
    candidate = Path(path)
    if candidate.is_absolute() or ".." in candidate.parts or not candidate.parts:
        raise RenderError(f"{context} must be a safe relative path: {path!r}")
    return candidate


def _excluded(relative: Path, exclude: list[str]) -> bool:
    return any(relative.is_relative_to(e) for e in exclude)


@dataclass
class Unit:
    """One rendering step: a part's own tree, or a tree it borrows (T3)."""

    label: str
    source: Part
    exclude: list[str]


def plan_units(parts: list[Part], parts_dir: Path, selected: set[str]) -> list[Unit]:
    units: list[Unit] = []
    for part in parts:
        if part.borrow_part and part.borrow_part not in selected:
            lender = load_part(parts_dir, part.borrow_part)
            label = f"{part.name} (from {lender.name})"
            units.append(Unit(label, lender, part.borrow_exclude))
        units.append(Unit(part.name, part, []))
    return units


def render_unit(unit: Unit, variables: dict[str, str], stage: Path) -> None:
    _copy_tree(unit, stage)
    _substitute(unit, variables, stage)
    _rename_dirs(unit, variables, stage)


def _copy_tree(unit: Unit, stage: Path) -> None:
    template_dir = unit.source.template_dir
    for path in sorted(template_dir.rglob("*")):
        relative = path.relative_to(template_dir)
        if path.is_dir() or _excluded(relative, unit.exclude):
            continue
        target = stage / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, target)


def _substitute(unit: Unit, variables: dict[str, str], stage: Path) -> None:
    for entry in unit.source.include:
        relative = _safe_relative(entry, "include entry")
        if _excluded(relative, unit.exclude):
            continue
        path = stage / relative
        if not path.is_file():
            raise RenderError(f"{unit.label}: include lists missing file {entry!r}")
        try:
            _write(path, render_template(_read(path), variables))
        except RenderError as error:
            raise RenderError(f"{unit.label}: {entry}: {error}") from None


def _rename_dirs(unit: Unit, variables: dict[str, str], stage: Path) -> None:
    for source, target_template in unit.source.dir_renames.items():
        relative = _safe_relative(source, "dir_renames source")
        if _excluded(relative, unit.exclude):
            continue
        source_path = stage / relative
        if not source_path.is_dir():
            raise RenderError(
                f"{unit.label}: dir_renames source {source!r} does not exist"
            )
        target = render_template(target_template, variables)
        target_path = stage / _safe_relative(target, "dir_renames target")
        if target_path.exists():
            raise RenderError(
                f"{unit.label}: dir_renames target {target!r} already exists"
            )
        source_path.rename(target_path)


# --------------------------------------------------------------------------------------
# Merge rules
# --------------------------------------------------------------------------------------


@dataclass
class Fragment:
    target: str
    producer: str
    text: str


_HEADER_RE = re.compile(r"^\s*(\[\[|\[)\s*([^\[\]#]+?)\s*(\]\]|\])\s*(?:#.*)?$")


def _table_key(raw: str) -> str:
    return ".".join(piece.strip() for piece in raw.split("."))


@dataclass
class _Section:
    key: str | None  # None for the preamble before the first header
    array: bool
    lines: list[str]

    @property
    def text(self) -> str:
        return "\n".join(self.lines)


def _sections(text: str) -> list[_Section]:
    sections = [_Section(None, False, [])]
    for line in text.splitlines():
        match = _HEADER_RE.match(line)
        if match and (match.group(1) == "[[") == (match.group(3) == "]]"):
            sections.append(
                _Section(_table_key(match.group(2)), match.group(1) == "[[", [line])
            )
        else:
            sections[-1].lines.append(line)
    return sections


def _package_paths(section: _Section, producer: str) -> list[str]:
    if section.array:
        raise RenderError(
            f"{producer}: [[package]] is not allowed; use [package] paths"
        )
    table = tomllib.loads(section.text).get("package", {})
    extra = sorted(set(table) - {"paths"})
    if extra:
        raise RenderError(
            f"{producer}: [package] in a part may only hold paths, found {extra}"
        )
    paths = table.get("paths", [])
    if not all(isinstance(p, str) for p in paths):
        raise RenderError(f"{producer}: [package] paths must be strings")
    return paths


def _require_toml(text: str, what: str) -> None:
    try:
        tomllib.loads(text)
    except tomllib.TOMLDecodeError as error:
        raise RenderError(f"{what} does not parse: {error}") from None


def _require_tables_only(preamble: _Section, producer: str) -> None:
    if any(
        line.strip() and not line.strip().startswith("#") for line in preamble.lines
    ):
        raise RenderError(
            f"{producer}: extension.toml.part may only hold tables; "
            "move top-level keys under a table"
        )


@dataclass
class _ManifestMerge:
    """T2 state: kept chunks, the [package].paths union, and who declared each table."""

    chunks: list[str] = field(default_factory=list)
    paths: list[str] = field(default_factory=list)
    has_package: bool = False
    declared: dict[str, tuple[bool, str]] = field(default_factory=dict)

    def absorb(self, text: str, producer: str, is_fragment: bool) -> None:
        kept: list[str] = []
        for section in _sections(text):
            if section.key == "package":
                self._add_paths(section, producer)
                continue
            if section.key is None:
                if is_fragment:
                    _require_tables_only(section, producer)
            else:
                self._declare(section, producer)
            kept.append(section.text)
        chunk = "\n".join(kept).strip("\n")
        if chunk:
            self.chunks.append(chunk)

    def _add_paths(self, section: _Section, producer: str) -> None:
        self.has_package = True
        for path in _package_paths(section, producer):
            if path not in self.paths:
                self.paths.append(path)

    def _declare(self, section: _Section, producer: str) -> None:
        key = section.key
        if key.startswith("package."):
            raise RenderError(f"{producer}: [{key}] is not allowed in a part")
        earlier = self.declared.get(key)
        if earlier is not None and not (section.array and earlier[0]):
            raise RenderError(
                f"{producer}: extension.toml.part declares [{key}], "
                f"which {earlier[1]} already declares"
            )
        self.declared.setdefault(key, (section.array, producer))


def merge_extension_toml(
    base_text: str, base_producer: str, fragments: list[Fragment]
) -> str:
    """T2: append fragment tables; union [package].paths; emit [package] last."""
    _require_toml(base_text, f"{base_producer}: extension.toml")
    merge = _ManifestMerge()
    merge.absorb(base_text, base_producer, is_fragment=False)
    for fragment in fragments:
        _require_toml(fragment.text, f"{fragment.producer}: extension.toml.part")
        merge.absorb(fragment.text, fragment.producer, is_fragment=True)
    chunks = merge.chunks
    if merge.has_package:
        paths = ", ".join(f'"{_toml_escape(p)}"' for p in merge.paths)
        chunks.append(f"[package]\npaths = [{paths}]")
    merged = "\n\n".join(chunks) + "\n"
    _require_toml(merged, "merged extension.toml")
    return merged


_RECIPE_RE = re.compile(r"^@?([A-Za-z_][A-Za-z0-9_-]*)(?:\s[^:=]*)?:(?!=)")
_JUST_NON_RECIPE = ("set ", "export ", "alias ", "import ", "mod ", "#", "[")


def recipe_names(justfile: str) -> list[str]:
    names = []
    for line in justfile.splitlines():
        if not line or line[0].isspace() or line.startswith(_JUST_NON_RECIPE):
            continue
        match = _RECIPE_RE.match(line)
        if match:
            names.append(match.group(1))
    return names


def merge_justfile(base_text: str, fragments: list[Fragment]) -> str:
    """T3: append recipes; a recipe name may appear once."""
    merged = base_text.rstrip("\n") + "\n"
    for fragment in fragments:
        merged += "\n" + fragment.text.strip("\n") + "\n"
    seen: set[str] = set()
    for name in recipe_names(merged):
        if name in seen:
            raise RenderError(f"merged Justfile defines recipe {name!r} twice")
        seen.add(name)
    return merged


def render_parts(
    part_names: list[str],
    out: Path,
    given: dict[str, str],
    parts_dir: Path = PARTS_DIR,
) -> list[str]:
    """Render the parts into `out`. Returns the ordered unit labels."""
    unknown = [name for name in part_names if name not in PART_ORDER]
    if unknown:
        raise RenderError(
            f"unknown part(s): {', '.join(unknown)}; known: {', '.join(PART_ORDER)}"
        )
    selected = set(part_names) | {ALWAYS}
    ordered = [name for name in PART_ORDER if name in selected]

    parts = [load_part(parts_dir, name) for name in ordered]
    units = plan_units(parts, parts_dir, selected)
    variables = resolve_variables([unit.source for unit in units], given)

    if out.exists() and any(out.iterdir()):
        raise RenderError(f"output directory is not empty: {out}")
    out.parent.mkdir(parents=True, exist_ok=True)
    # Render into a staging directory next to `out`; move it into place only on success.
    with tempfile.TemporaryDirectory(prefix=".zelos-parts-", dir=out.parent) as scratch:
        project = Path(scratch) / "project"
        project.mkdir()
        _render_into(units, variables, project, Path(scratch))
        if out.exists():
            out.rmdir()
        project.rename(out)
    return [unit.label for unit in units]


def _render_into(
    units: list[Unit], variables: dict[str, str], out: Path, scratch: Path
) -> None:
    producers: dict[Path, str] = {}
    fragments: list[Fragment] = []
    for index, unit in enumerate(units):
        stage = scratch / f"unit-{index}"
        stage.mkdir()
        render_unit(unit, variables, stage)
        _collect(unit.label, stage, out, producers, fragments)
    for target in FRAGMENT_TARGETS:
        target_fragments = [f for f in fragments if f.target == target]
        if target_fragments:
            _merge_fragments(out, target, producers, target_fragments)


def _collect(
    label: str,
    stage: Path,
    out: Path,
    producers: dict[Path, str],
    fragments: list[Fragment],
) -> None:
    """Copy a unit's files into `out` and set aside its fragments."""
    for path in sorted(stage.rglob("*")):
        if path.is_dir():
            continue
        relative = path.relative_to(stage)
        if relative.name.endswith(FRAGMENT_SUFFIX):
            target = _fragment_target(label, relative)
            fragments.append(Fragment(target, label, _read(path)))
            continue
        # T1: a later part never overwrites an earlier part's file.
        if relative in producers:
            raise RenderError(
                f"{label}: {relative} was already produced by {producers[relative]}; "
                "extend it with a .part fragment instead"
            )
        destination = out / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, destination)
        producers[relative] = label


def _fragment_target(label: str, relative: Path) -> str:
    target = relative.name.removesuffix(FRAGMENT_SUFFIX)
    if relative.parent != Path(".") or target not in FRAGMENT_TARGETS:
        known = ", ".join(t + FRAGMENT_SUFFIX for t in FRAGMENT_TARGETS)
        raise RenderError(
            f"{label}: {relative} is not a known fragment (only {known} at the part root)"
        )
    return target


def _merge_fragments(
    out: Path, target: str, producers: dict[Path, str], fragments: list[Fragment]
) -> None:
    producer = producers.get(Path(target))
    if producer is None:
        raise RenderError(
            f"{fragments[0].producer}: {target}.part needs an earlier part to produce {target}"
        )
    target_path = out / target
    base_text = _read(target_path)
    if target == "extension.toml":
        merged = merge_extension_toml(base_text, producer, fragments)
    else:
        merged = merge_justfile(base_text, fragments)
    _write(target_path, merged)


def _parse_vars(pairs: list[str]) -> dict[str, str]:
    values: dict[str, str] = {}
    for pair in pairs:
        key, sep, value = pair.partition("=")
        if not sep or not key:
            raise RenderError(f"--var expects NAME=VALUE, got {pair!r}")
        values[key] = value
    return values


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--parts", required=True, help="comma list, e.g. base,agent-python,panel"
    )
    parser.add_argument(
        "--out", required=True, type=Path, help="project directory to create"
    )
    parser.add_argument("--var", action="append", default=[], metavar="NAME=VALUE")
    args = parser.parse_args(argv)
    try:
        names = [name.strip() for name in args.parts.split(",") if name.strip()]
        units = render_parts(names, args.out, _parse_vars(args.var))
    except RenderError as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    print(f"rendered {' -> '.join(units)} into {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
