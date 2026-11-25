"""
Publish Markdown files to Confluence wiki.

Copyright 2022-2026, Levente Hunyadi

:see: https://github.com/hunyadi/md2conf
"""

import json
import logging
import os
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path
from unittest.mock import MagicMock

from md2conf.csf import ElementType
from md2conf.extension import ExtensionOptions, ImageGenerator
from md2conf.formatting import ImageAttributes
from md2conf.mermaid.confluence_macro import ConfluenceMermaidMacroExtension, _macro_body
from md2conf.mermaid.render import has_mmdc, render_diagram
from tests.mermaid_tree import render_mermaid_tree
from tests.utility import TypedTestCase

AC = "{http://atlassian.com/content}"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(funcName)s [%(lineno)d] - %(message)s",
)

MERMAID_SOURCE = """
graph TD
  C{ How to contribute? }
  C --> D[ Reporting bugs ]
  C --> E[ Sharing ideas ]
"""

MERMAID_CLASS_DIAGRAM = """classDiagram
Entity <|-- Product
Entity <|-- Stakeholder
Stakeholder <|-- External
External <|-- Customer
Stakeholder <|-- Internal
Entity <|-- Vendor
Vendor <|-- Store
Entity <|-- Project
"""

MERMAID_TREE_DIAGRAM = """Entity
├── Product
├── Stakeholder
│   ├── External
│   │   └── Customer
│   └── Internal
├── Vendor
│   └── Store
└── Project"""


class TestMermaidTree(TypedTestCase):
    def test_render_simple_svg(self) -> None:
        self.assertEqual(render_mermaid_tree(MERMAID_CLASS_DIAGRAM), MERMAID_TREE_DIAGRAM)


class TestConfluenceMermaidMacro(TypedTestCase):
    def _extension(self, render: bool = False) -> ConfluenceMermaidMacroExtension:
        generator = MagicMock(spec=ImageGenerator)
        return ConfluenceMermaidMacroExtension(generator, ExtensionOptions(render=render))

    def test_matches(self) -> None:
        extension = self._extension()
        self.assertTrue(extension.matches_fenced("mermaid", MERMAID_SOURCE))
        self.assertTrue(extension.matches_image(Path("diagram.mmd")))
        self.assertFalse(extension.matches_fenced("plantuml", MERMAID_SOURCE))

    def _assert_macro(self, element: ElementType, source: str) -> None:
        self.assertEqual(element.tag, f"{AC}structured-macro")
        self.assertEqual(element.get(f"{AC}name"), "confluence-mermaid-macro")

        params = {p.get(f"{AC}name"): p.text for p in element.findall(f"{AC}parameter")}
        self.assertEqual(params["searchText"], " ".join(source.split()))

        body = element.find(f"{AC}plain-text-body")
        assert body is not None and body.text is not None
        self.assertEqual(json.loads(body.text), [{"body": source, "date": 0}])

    def test_fenced_macro(self) -> None:
        self._assert_macro(self._extension().transform_fenced(MERMAID_SOURCE), MERMAID_SOURCE)

    def test_body_escapes_cdata_terminator(self) -> None:
        source = "graph LR\n  A --> B\n  ]]> end"
        self.assertNotIn("]]>", _macro_body(source))
        self._assert_macro(self._extension().transform_fenced(source), source)

    def test_image_macro(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "diagram.mmd"
            path.write_text(MERMAID_SOURCE, encoding="utf-8")
            element = self._extension().transform_image(path, ImageAttributes.EMPTY_BLOCK)

        self._assert_macro(element, MERMAID_SOURCE)


@unittest.skipUnless(has_mmdc(), "mmdc is not available")
@unittest.skipUnless(os.getenv("TEST_MERMAID"), "mermaid tests are disabled")
class TestMermaidRendering(TypedTestCase):
    def test_render_simple_svg(self) -> None:
        svg = render_diagram(MERMAID_SOURCE, output_format="svg")
        root = ET.fromstring(svg)
        self.assertTrue(root.tag.lower() == "svg" or root.tag.endswith("}svg"))

    def test_render_simple_png(self) -> None:
        png = render_diagram(MERMAID_SOURCE)
        self.assertIn(b"PNG", png)


if __name__ == "__main__":
    unittest.main()
