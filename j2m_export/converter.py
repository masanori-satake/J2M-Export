from bs4 import BeautifulSoup, Tag
import html
import re
import logging

logger = logging.getLogger(__name__)

class MarkdownConverter:
    """
    Convert Jira rendered HTML to Markdown.
    """
    def __init__(self, base_url: str):
        self.base_url = base_url

    def convert(self, html_content: str) -> str:
        """
        Entry point for HTML to Markdown conversion.
        """
        if not html_content:
            return ""
        soup = BeautifulSoup(html_content, "html.parser")
        return self._walk(soup)

    def _walk(self, node) -> str:
        """
        Recursively walk the DOM tree.
        """
        md = ""
        for child in node.children:
            if isinstance(child, Tag):
                md += self._process_tag(child)
            else:
                # Jira might have some unescaped HTML characters
                md += html.unescape(str(child))
        return md

    def _process_tag(self, tag: Tag) -> str:
        """
        Define conversion rules per tag.
        """
        name = tag.name

        if re.match(r'h[1-6]', name):
            h_level = int(name[1])
            return f"\n{'#' * h_level} {self._walk(tag)}\n"

        if name == 'p':
            return f"\n{self._walk(tag)}\n"

        if name == 'br':
            return "\n"

        if name in ['strong', 'b']:
            return f"**{self._walk(tag)}**"

        if name in ['em', 'i']:
            return f"*{self._walk(tag)}*"

        if name == 'code':
            return f"`{self._walk(tag)}`"

        if name == 'ul':
            return f"\n{self._walk(tag)}\n"

        if name == 'ol':
            return f"\n{self._walk(tag)}\n"

        if name == 'li':
            parent = tag.parent
            if parent and parent.name == 'ol':
                return f"1. {self._walk(tag)}\n"
            else:
                return f"- {self._walk(tag)}\n"

        if name == 'table':
            return self._handle_table(tag)

        if name == 'a':
            href = tag.get('href', '')
            if href.startswith('/'):
                href = self.base_url + href
            return f"[{self._walk(tag)}]({href})"

        if name == 'pre' or 'code' in tag.get('class', []):
             return f"\n```\n{tag.get_text()}\n```\n"

        # Handle Jira specific blocks if any (e.g., panel, info)
        if tag.get('class') and any(c in tag.get('class') for c in ['panel', 'confluence-information-macro']):
            title = ""
            title_node = tag.find(class_=re.compile("header|title"))
            if title_node:
                title = title_node.get_text().strip()

            body_node = tag.find(class_=re.compile("content|body"))
            if body_node:
                body_md = self._walk(body_node).strip()
            else:
                body_md = self._walk(tag).strip()

            result = "\n"
            if title:
                result += f"**{title}**\n"
            if body_md:
                result += f"{body_md}\n"
            return result

        # Default: recursively process children
        return self._walk(tag)

    def _handle_table(self, table: Tag) -> str:
        """
        Convert HTML table to Markdown table.
        """
        rows = []
        for tr in table.find_all('tr', recursive=False):
            cols = []
            for cell in tr.find_all(['th', 'td'], recursive=False):
                cell_text = self._walk(cell).strip().replace('\n', '<br>')
                cols.append(cell_text)
            rows.append(cols)

        if not rows:
            return ""

        md = "\n"
        md += "| " + " | ".join(rows[0]) + " |\n"
        md += "| " + " | ".join(["---"] * len(rows[0])) + " |\n"
        for row in rows[1:]:
            if len(row) < len(rows[0]):
                row += [""] * (len(rows[0]) - len(row))
            md += "| " + " | ".join(row[:len(rows[0])]) + " |\n"

        return md + "\n"
