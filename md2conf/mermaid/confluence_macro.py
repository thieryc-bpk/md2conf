"""
Publish Markdown files to Confluence wiki.

Copyright 2022-2026, Levente Hunyadi

:see: https://github.com/hunyadi/md2conf
"""

import json
from pathlib import Path

from lxml.etree import CDATA

from md2conf.compatibility import override
from md2conf.csf import AC_ATTR, AC_ELEM, ElementType
from md2conf.extension import ExtensionOptions, ImageGenerator, MarketplaceExtension, MarketplaceExtensionFactory
from md2conf.formatting import ImageAttributes

from .extension import MermaidExtension

MERMAID_MACRO_NAME = "confluence-mermaid-macro"

# default macro parameters; `None` values produce empty parameter elements (flags)
_DEFAULT_PARAMETERS: list[tuple[str, str | None]] = [
    ("panZoom", "true"),
    ("zoom", None),
    ("look", "neo"),
    ("download", "true"),
    ("fullscreen", "true"),
    ("theme", "default"),
    ("disableUseMaxWidth", None),
    ("copy", None),
    ("alignment", "center"),
    ("exportWidth", None),
    ("height", None),
]


def _macro_body(source: str) -> str:
    "Serializes the diagram source into the JSON body expected by the macro."

    # `date` is fixed so that unchanged diagrams produce identical storage format (and no spurious page versions)
    body = json.dumps([{"body": source, "date": 0}], ensure_ascii=False)
    # escape `>` so that the sequence `]]>` cannot terminate the surrounding CDATA section
    return body.replace(">", "\\u003e")


class ConfluenceMermaidMacroExtension(MermaidExtension):
    """
    Integration for the Confluence Data Center / Server app *Mermaid for Confluence* (macro `confluence-mermaid-macro`).

    With pre-rendering disabled, the diagram source is stored inside the macro body and rendered by the app when the page is viewed.
    With pre-rendering enabled, the diagram is converted to an image attachment as with the default Mermaid integration.
    """

    @override
    def transform_image(self, absolute_path: Path, attrs: ImageAttributes) -> ElementType:
        if self.options.render:
            return super().transform_image(absolute_path, attrs)

        content = absolute_path.read_text(encoding="utf-8")
        return self._create_macro(content)

    @override
    def transform_fenced(self, content: str) -> ElementType:
        if self.options.render:
            return super().transform_fenced(content)

        return self._create_macro(content)

    def _create_macro(self, source: str) -> ElementType:
        "A Mermaid diagram stored in the body of a `confluence-mermaid-macro` macro."

        parameters: list[ElementType] = []
        for name, value in _DEFAULT_PARAMETERS:
            attrs = {AC_ATTR("name"): name}
            parameters.append(AC_ELEM("parameter", attrs) if value is None else AC_ELEM("parameter", attrs, value))
        parameters.append(AC_ELEM("parameter", {AC_ATTR("name"): "searchText"}, " ".join(source.split())))

        return AC_ELEM(
            "structured-macro",
            {
                AC_ATTR("name"): MERMAID_MACRO_NAME,
                AC_ATTR("schema-version"): "1",
            },
            *parameters,
            AC_ELEM("plain-text-body", CDATA(_macro_body(source))),
        )


class ConfluenceMermaidMacroExtensionFactory(MarketplaceExtensionFactory):
    @override
    def create(self, generator: ImageGenerator, options: ExtensionOptions) -> MarketplaceExtension:
        return ConfluenceMermaidMacroExtension(generator, options)
