#!/usr/bin/env python3
"""Tests for the reference parts renderer: the template engine and merge rules T1-T4.

Run: python3 -m unittest discover -s scripts -p 'test_*.py'
"""

from __future__ import annotations

import re
import tempfile
import textwrap
import unittest
from pathlib import Path
from unittest import mock

from render_parts import (
    Fragment,
    RenderError,
    merge_extension_toml,
    render_parts,
    render_template,
)

REPO = Path(__file__).resolve().parent.parent
WORKED_EXAMPLE_VARS = {
    "name": "probe",
    "description": "Probe sensors",
    "author": "Ada Lovelace",
    "github": "your-org",
}


class TemplateEngineTest(unittest.TestCase):
    """Expected strings come from MiniJinja 2.18 with trim_blocks and lstrip_blocks."""

    def test_trim_and_lstrip_blocks(self) -> None:
        source = "a\n  {% if x %}\n  y\n  {% endif %}\nz\n"
        self.assertEqual(render_template(source, {"x": "1"}), "a\n  y\nz\n")
        self.assertEqual(render_template(source, {}), "a\nz\n")

    def test_elif_else_and_operators(self) -> None:
        source = "{% if x and y %}AB{% elif x or y %}one{% else %}none{% endif %}"
        self.assertEqual(render_template(source, {"x": "1", "y": "1"}), "AB")
        self.assertEqual(render_template(source, {"y": "1"}), "one")
        self.assertEqual(render_template(source, {}), "none")
        self.assertEqual(render_template("{% if not x %}n{% endif %}", {}), "n")

    def test_raw_trims_the_newline_after_endraw(self) -> None:
        self.assertEqual(
            render_template("k: {% raw %}${{ a }}{% endraw %}\nnext\n", {}),
            "k: ${{ a }}next\n",
        )

    def test_filters_and_undefined(self) -> None:
        variables = {"name": "my-ext", "v": "3.11", "q": 'say "hi"\n'}
        source = "{{ name | replace('-', ' ') | title }}|{{ v|replace(\".\", \"\") }}|{{ q | toml_escape }}|{{ q|json_escape }}|{{ missing }}"
        self.assertEqual(
            render_template(source, variables),
            'My Ext|311|say \\"hi\\"\\n|say \\"hi\\"\\n|',
        )

    def test_unsupported_syntax_fails(self) -> None:
        for source in (
            "{% for x in y %}{% endfor %}",
            "{{ x | nope }}",
            "{%- if x %}{% endif %}",
            "{% if x %}",
        ):
            with self.assertRaises(RenderError, msg=source):
                render_template(source, {"x": "1"})


def _write(root: Path, files: dict[str, str]) -> None:
    for relative, content in files.items():
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(textwrap.dedent(content).lstrip("\n").encode("utf-8"))


def _part(name: str, include: list[str], extra: str = "") -> str:
    quoted = ", ".join(f'"{entry}"' for entry in include)
    return f'[template]\npart = "{name}"\n{extra}\n[template.substitution]\ninclude = [{quoted}]\n'


BASE_FILES = {
    "base/template.toml": _part("base", ["extension.toml"])
    + '[[template.variables]]\nname = "name"\nprompt = "Name"\n',
    "base/template/extension.toml": """
        name = "{{ name }}"
        version = "0.1.0"

        [zelos]
        version = ">=26.0.10"

        [package]
        paths = ["README.md"]
    """,
    "base/template/README.md": "readme\n",
    "base/template/Justfile": "default:\n    @just --list\n",
}


class MergeRulesTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self.parts = self.tmp / "parts"
        _write(self.parts, BASE_FILES)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def render(self, names: list[str]) -> Path:
        self.renders = getattr(self, "renders", 0) + 1
        out = self.tmp / f"out-{self.renders}"
        render_parts(names, out, {"name": "probe"}, self.parts)
        return out

    def test_t1_later_part_cannot_overwrite_a_file(self) -> None:
        _write(
            self.parts,
            {
                "agent-python/template.toml": _part("agent-python", ["README.md"]),
                "agent-python/template/README.md": "other\n",
            },
        )
        with self.assertRaisesRegex(
            RenderError, "README.md was already produced by base"
        ):
            self.render(["agent-python"])

    def test_t1_order_is_fixed(self) -> None:
        _write(
            self.parts,
            {
                "agent-python/template.toml": _part(
                    "agent-python", ["extension.toml.part"]
                ),
                "agent-python/template/extension.toml.part": '[agent]\nentry = "main.py"\n',
                "panel/template.toml": _part("panel", ["extension.toml.part"]),
                "panel/template/extension.toml.part": '[[app.panels]]\nid = "a"\n',
            },
        )
        manifest = (
            self.render(["panel", "agent-python"]) / "extension.toml"
        ).read_text()
        self.assertLess(manifest.index("[agent]"), manifest.index("[[app.panels]]"))

    def test_t2_tables_append_and_paths_union_last(self) -> None:
        fragments = [
            Fragment(
                "extension.toml",
                "agent-python",
                '[agent]\nentry = "main.py"\n\n[package]\npaths = ["main.py", "README.md"]\n',
            ),
            Fragment(
                "extension.toml",
                "app-react",
                '[app]\ntab = "dist/tab/index.html"\n\n[package]\npaths = ["dist"]\n',
            ),
            Fragment(
                "extension.toml",
                "panel",
                '[[app.panels]]\nid = "a"\n\n[package]\npaths = ["dist"]\n',
            ),
            Fragment("extension.toml", "panel", '[[app.panels]]\nid = "b"\n'),
        ]
        base = 'name = "x"\n\n[package]\npaths = ["README.md"]\n\n[zelos]\nversion = ">=26.0.10"\n'
        merged = merge_extension_toml(base, "base", fragments)
        self.assertTrue(
            merged.endswith('[package]\npaths = ["README.md", "main.py", "dist"]\n'),
            merged,
        )
        self.assertEqual(merged.count("[package]"), 1)
        self.assertEqual(merged.count("[[app.panels]]"), 2)

    def test_t2_fragment_cannot_redeclare_a_table(self) -> None:
        fragments = [
            Fragment("extension.toml", "agent-python", "[agent]\nentry = 'a'\n"),
            Fragment("extension.toml", "panel", "[agent]\nentry = 'b'\n"),
        ]
        with self.assertRaisesRegex(
            RenderError, r"declares \[agent\], which agent-python already declares"
        ):
            merge_extension_toml('name = "x"\n', "base", fragments)
        with self.assertRaisesRegex(
            RenderError, r"declares \[zelos\], which base already declares"
        ):
            merge_extension_toml(
                '[zelos]\nversion = "1"\n',
                "base",
                [Fragment("extension.toml", "p", '[zelos]\nversion = "2"\n')],
            )

    def test_t2_fragment_holds_tables_only(self) -> None:
        with self.assertRaisesRegex(RenderError, "may only hold tables"):
            merge_extension_toml(
                'name = "x"\n',
                "base",
                [Fragment("extension.toml", "p", 'version = "2"\n')],
            )
        with self.assertRaisesRegex(RenderError, "may only hold paths"):
            merge_extension_toml(
                'name = "x"\n',
                "base",
                [Fragment("extension.toml", "p", "[package]\nexclude = []\n")],
            )

    def test_t3_justfile_fragments_append_and_reject_duplicates(self) -> None:
        _write(
            self.parts,
            {
                "agent-python/template.toml": _part("agent-python", ["Justfile.part"]),
                "agent-python/template/Justfile.part": "run:\n    echo run\n",
            },
        )
        self.assertIn(
            "run:\n    echo run",
            (self.render(["agent-python"]) / "Justfile").read_text(),
        )
        _write(
            self.parts,
            {"agent-python/template/Justfile.part": "default:\n    echo again\n"},
        )
        with self.assertRaisesRegex(RenderError, "recipe 'default' twice"):
            self.render(["agent-python"])

    def test_t3_borrow_only_when_lender_is_not_selected(self) -> None:
        _write(
            self.parts,
            {
                "app-react/template.toml": _part("app-react", ["web/package.json"]),
                "app-react/template/web/package.json": '{"name": "{{ name }}"}\n',
                "app-react/template/web/src/tab/main.tsx": "tab\n",
                "app-react/template/extension.toml.part": '[app]\ntab = "dist/tab/index.html"\n',
                "panel/template.toml": _part(
                    "panel",
                    ["extension.toml.part"],
                    '[template.borrow]\npart = "app-react"\nexclude = ["web/src/tab", "extension.toml.part"]\n',
                ),
                "panel/template/extension.toml.part": '[[app.panels]]\nid = "a"\n',
                "panel/template/web/src/panels/a.html": "panel\n",
            },
        )
        out = self.render(["panel"])
        self.assertEqual((out / "web/package.json").read_text(), '{"name": "probe"}\n')
        self.assertFalse((out / "web/src/tab").exists())
        self.assertNotIn("tab =", (out / "extension.toml").read_text())

        out = self.render(["app-react", "panel"])
        self.assertTrue((out / "web/src/tab/main.tsx").exists())
        self.assertIn(
            'tab = "dist/tab/index.html"', (out / "extension.toml").read_text()
        )

    def test_fragment_needs_a_known_target(self) -> None:
        _write(
            self.parts,
            {
                "agent-python/template.toml": _part("agent-python", ["README.md.part"]),
                "agent-python/template/README.md.part": "more\n",
            },
        )
        with self.assertRaisesRegex(RenderError, "not a known fragment"):
            self.render(["agent-python"])

    def test_unknown_part_and_missing_variable(self) -> None:
        with self.assertRaisesRegex(RenderError, "unknown part"):
            self.render(["agent-rust"])
        with self.assertRaisesRegex(RenderError, "missing template variable: name"):
            render_parts([], self.tmp / "o", {}, self.parts)

    def test_rendered_files_keep_the_source_newlines(self) -> None:
        (self.parts / "base/template/extension.toml").write_bytes(
            b'name = "{{ name }}"\r\n\r\n[package]\r\npaths = ["README.md"]\r\n'
        )
        out = self.render([])
        self.assertEqual(
            (out / "extension.toml").read_bytes(),
            b'name = "probe"\r\n\r\n[package]\r\npaths = ["README.md"]\r\n',
        )


class RealPartsTest(unittest.TestCase):
    def test_worked_example_in_readme_matches_render(self) -> None:
        readme = (REPO / "parts/README.md").read_text()
        match = re.search(
            r"<!-- worked-example -->\s*```toml\n(.*?)```", readme, re.DOTALL
        )
        assert match, "parts/README.md has no worked example block"
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "probe"
            render_parts(
                ["base", "agent-python", "panel"], out, dict(WORKED_EXAMPLE_VARS)
            )
            self.assertEqual((out / "extension.toml").read_text(), match.group(1))

    def test_output_bytes_match_the_sources_on_every_os(self) -> None:
        # Text mode writes CRLF on Windows; the renderer must not use it.
        fail = mock.Mock(side_effect=AssertionError("text-mode file IO"))
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "probe"
            with (
                mock.patch.object(Path, "read_text", fail),
                mock.patch.object(Path, "write_text", fail),
            ):
                render_parts(
                    ["base", "agent-python", "app-react", "panel"],
                    out,
                    dict(WORKED_EXAMPLE_VARS),
                )
            for path in out.rglob("*"):
                if path.is_file():
                    self.assertNotIn(b"\r", path.read_bytes(), str(path))

    def test_web_parts_ship_their_dist_byte_for_byte(self) -> None:
        def shipped(part: str) -> set[Path]:
            root = REPO / "parts" / part / "template"
            return {
                p.relative_to(root) for p in (root / "dist").rglob("*") if p.is_file()
            }

        tab, panel = shipped("app-react"), shipped("panel")
        self.assertIn(Path("dist/tab/index.html"), tab)
        self.assertIn(Path("dist/panels/example.html"), panel)
        self.assertFalse(tab & panel, "the two builds must not share a path")
        templated = {Path("dist/tab/index.html")}
        for parts, expected in (
            (["app-react"], {"app-react": tab}),
            (["panel"], {"panel": panel}),
            (["app-react", "panel"], {"app-react": tab, "panel": panel}),
        ):
            with tempfile.TemporaryDirectory() as tmp:
                out = Path(tmp) / "probe"
                render_parts(parts, out, dict(WORKED_EXAMPLE_VARS))
                files = {
                    p.relative_to(out) for p in (out / "dist").rglob("*") if p.is_file()
                }
                self.assertEqual(files, set().union(*expected.values()), parts)
                for part, paths in expected.items():
                    for path in paths - templated:
                        source = REPO / "parts" / part / "template" / path
                        self.assertEqual(
                            (out / path).read_bytes(), source.read_bytes(), path
                        )
                if "app-react" in parts:
                    self.assertIn(
                        b"<title>Probe</title>",
                        (out / "dist/tab/index.html").read_bytes(),
                    )


if __name__ == "__main__":
    unittest.main()
