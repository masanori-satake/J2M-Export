import pytest
from j2m_export.converter import MarkdownConverter

def test_converter_basic():
    converter = MarkdownConverter("https://jira.example.com")
    html = "<h1>Title</h1><p>This is a <b>test</b>.</p>"
    md = converter.convert(html)
    assert "# Title" in md
    assert "This is a **test**." in md

def test_converter_table():
    converter = MarkdownConverter("https://jira.example.com")
    html = "<table><tr><th>Header</th></tr><tr><td>Data</td></tr></table>"
    md = converter.convert(html)
    assert "| Header |" in md
    assert "| --- |" in md
    assert "| Data |" in md

def test_converter_links():
    converter = MarkdownConverter("https://jira.example.com")
    html = '<a href="/browse/PROJ-1">Issue</a>'
    md = converter.convert(html)
    assert "[Issue](https://jira.example.com/browse/PROJ-1)" in md

def test_converter_code():
    converter = MarkdownConverter("https://jira.example.com")
    html = '<pre>print("hello")</pre>'
    md = converter.convert(html)
    assert "```" in md
    assert 'print("hello")' in md
