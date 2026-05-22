import sys
import logging
from pathlib import Path
from typing import List, Dict

from .config import Config
from .jira import JiraClient
from .converter import MarkdownConverter
from .utils import get_unique_filename, bytes_to_mb, is_within_size_limit

logger = logging.getLogger(__name__)

def format_issue_md(issue: Dict, converter: MarkdownConverter, base_url: str) -> str:
    """
    Format a single issue into a Markdown string.
    """
    fields = issue.get('fields') or {}
    rendered = issue.get('renderedFields') or {}

    key = issue.get('key')
    summary = fields.get('summary') or 'No Summary'
    description = rendered.get('description', fields.get('description', ''))
    project = fields.get('project', {}).get('key', 'UNKNOWN')
    status = fields.get('status', {}).get('name', 'UNKNOWN')
    assignee = (fields.get('assignee') or {}).get('displayName') or 'Unassigned'
    created = fields.get('created')

    url = f"{base_url}/browse/{key}"

    md = f"\n---\n# {summary}\n"
    md += f"- **Key**: {key}\n"
    md += f"- **Project**: {project}\n"
    md += f"- **Status**: {status}\n"
    md += f"- **Assignee**: {assignee}\n"
    md += f"- **Created**: {created}\n"
    md += f"- **URL**: {url}\n\n"

    md += "## Description\n"
    md += converter.convert(description)

    # Comments
    comments_data = fields.get('comment', {}).get('comments', [])
    if comments_data:
        md += "\n## Comments\n"
        # Note: renderedFields for comments is usually under issue['renderedFields']['comment']['comments']
        rendered_comments = rendered.get('comment', {}).get('comments', [])

        for i, comment in enumerate(comments_data):
            author = comment.get('author', {}).get('displayName', 'Anonymous')
            created_at = comment.get('created')

            # Try to get rendered comment body
            body_html = ""
            if i < len(rendered_comments):
                body_html = rendered_comments[i].get('body')

            body = body_html if body_html else comment.get('body', '')

            md += f"\n### Comment by {author} ({created_at})\n"
            md += converter.convert(body)

    return md

def main():
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s [%(levelname)s] %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    config = Config()
    try:
        config.load()
        config.validate()
    except Exception as e:
        logger.error(f"Configuration error: {e}")
        sys.exit(1)

    client = JiraClient(config.base_url, config.token, config.proxy)
    converter = MarkdownConverter(config.base_url)

    issues_to_process = []

    # 1. Collect issues from Keys
    if config.issue_keys:
        for key in config.issue_keys:
            try:
                issue = client.get_issue(key)
                issues_to_process.append(issue)
            except Exception as e:
                logger.error(f"Failed to fetch issue {key}: {e}")

    # 2. Collect issues from JQL
    if config.jql:
        try:
            jql_issues = client.search_issues(config.jql)
            # Avoid duplicates if key was also specified
            existing_keys = {i['key'] for i in issues_to_process}
            for issue in jql_issues:
                if issue['key'] not in existing_keys:
                    issues_to_process.append(issue)
        except Exception as e:
            logger.error(f"JQL search failed: {e}")

    if not issues_to_process:
        logger.warning("No issues found to process.")
        return

    # Process and Save
    output_dir = Path(config.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    total_bytes = 0
    issue_count = 0

    for issue in issues_to_process:
        key = issue['key']
        summary = issue['fields'].get('summary', 'No Summary')
        project_key = issue['fields'].get('project', {}).get('key', 'UNKNOWN')

        try:
            issue_md = format_issue_md(issue, converter, config.base_url)
            md_bytes = len(issue_md.encode('utf-8'))

            if not is_within_size_limit(total_bytes + md_bytes, config.stop_threshold_mb):
                logger.warning(f"Stop threshold ({config.stop_threshold_mb}MB) reached. Stopping export.")
                break

            output_path = get_unique_filename(config.output_dir, project_key, summary, key)

            output_path.write_text(issue_md, encoding="utf-8")

            total_bytes += md_bytes
            issue_count += 1
            logger.info(f"Exported {key}: {summary}")

        except Exception:
            logger.exception(f"Failed to process issue {key}")

    logger.info("-" * 50)
    logger.info(f"Successfully exported {issue_count} issues.")
    logger.info(f"Total size: {bytes_to_mb(total_bytes):.2f}MB")

if __name__ == "__main__":
    main()
