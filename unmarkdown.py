"""Module to convert markdown to plain text. Code based on https://stackoverflow.com/a/54923798"""
from io import StringIO

from markdown import Markdown


def unmark_element(element, stream=None):
    """Custom plain output format for markdown."""
    if stream is None:
        stream = StringIO()
    if element.text:
        stream.write(element.text)
    for sub in element:
        unmark_element(sub, stream)
    if element.tail:
        stream.write(element.tail)
    return stream.getvalue()


Markdown.output_formats.update(plain=unmark_element)


def unmark(text: str) -> str:
    """Convert markdown-formatted text to plain text."""
    md = Markdown(output_format="plain")  # type: ignore
    md.stripTopLevelTags = False
    return md.convert(text)
