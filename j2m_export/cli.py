import sys
import json
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional

from .config import Config
from .jira import JiraClient
from .converter import MarkdownConverter
from .utils import get_unique_filename, bytes_to_mb, is_within_size_limit

logger = logging.getLogger(__name__)

# Mandatory fields that cannot be excluded
NON_IGNORABLE_IDS = ['summary', 'project', 'status', 'assignee', 'created', 'key']

def format_field_value(value: Any) -> str:
    """
    Format Jira field value based on its type.
    """
    if value is None:
        return ""
    if isinstance(value, (str, int, float, bool)):
        return str(value)
    if isinstance(value, dict):
        # Prefer displayName or name for objects
        return value.get('displayName') or value.get('name') or json.dumps(value, ensure_ascii=False)
    if isinstance(value, list):
        # Format list as comma separated strings or JSON if complex
        formatted_list = []
        for item in value:
            if isinstance(item, dict):
                val = item.get('displayName') or item.get('name')
                if val:
                    formatted_list.append(str(val))
                else:
                    formatted_list.append(json.dumps(item, ensure_ascii=False))
            else:
                formatted_list.append(str(item))
        return ", ".join(formatted_list)

    return json.dumps(value, ensure_ascii=False)

def format_issue_md(issue: Dict, converter: MarkdownConverter, base_url: str, exclude_fields: Optional[List[str]] = None) -> str:
    """
    Format a single issue into a Markdown string.
    """
    exclude_fields = exclude_fields or []
    fields = issue.get('fields') or {}
    rendered = issue.get('renderedFields') or {}
    names = issue.get('names') or {}
    schema = issue.get('schema') or {}

    key = issue.get('key')
    summary = fields.get('summary') or 'No Summary'
    url = f"{base_url}/browse/{key}"

    md = f"\n---\n# {summary}\n"
    md += f"- **Key**: {key}\n"

    # Define standard fields to always show first if not excluded
    standard_order = ['project', 'status', 'priority', 'assignee', 'reporter', 'created', 'updated', 'duedate', 'resolution']
    processed_fields = {'summary', 'description', 'comment', 'worklog', 'attachment'}

    # 1. Output mandatory and common standard fields
    for fid in standard_order:
        if fid in processed_fields: continue
        if fid in exclude_fields and fid not in NON_IGNORABLE_IDS:
            continue

        val = fields.get(fid)
        if val is not None:
            label = names.get(fid, fid.capitalize())
            md += f"- **{label}**: {format_field_value(val)}\n"
            processed_fields.add(fid)

    # 2. Output other standard fields (網羅的に出力)
    for fid, val in fields.items():
        if fid in processed_fields: continue
        if fid in exclude_fields and fid not in NON_IGNORABLE_IDS:
            continue

        # Skip custom fields
        f_schema = schema.get(fid, {})
        if f_schema.get('custom'):
            continue

        if val is not None:
            label = names.get(fid, fid.capitalize())
            md += f"- **{label}**: {format_field_value(val)}\n"
            processed_fields.add(fid)

    md += f"- **URL**: {url}\n\n"

    md += "## Description\n"
    description = rendered.get('description', fields.get('description', ''))
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

    # Validate exclude_fields once
    for eid in config.exclude_fields:
        if eid in NON_IGNORABLE_IDS:
            logger.warning(f"Field '{eid}' is mandatory and cannot be excluded.")

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

    # 3. If no issues found yet but labels are specified, fetch by labels
    if not issues_to_process and config.labels:
        try:
            # Construct JQL for labels (escape double quotes)
            escaped_labels = [f'"{l.replace("\"", "\\\"")}"' for l in config.labels]
            label_jql = f"labels IN ({', '.join(escaped_labels)})"
            logger.info(f"Fetching issues by labels JQL: {label_jql}")
            issues_to_process = client.search_issues(label_jql)
        except Exception as e:
            logger.error(f"Failed to fetch issues by labels: {e}")

    if not issues_to_process:
        logger.warning("No issues found to process.")
        return

    # 4. Filter issues by labels if specified (post-filtering)
    if config.labels:
        filtered_issues = []
        label_set = {l.lower() for l in config.labels}
        for issue in issues_to_process:
            issue_labels = [l.lower() for l in issue.get('fields', {}).get('labels', [])]
            # Jiraの挙動（ケースインセンシティブ）に合わせ、大文字小文字を区別せずにラベルをチェック
            if any(label in label_set for label in issue_labels):
                filtered_issues.append(issue)

        issues_to_process = filtered_issues
        logger.info(f"Filtered to {len(issues_to_process)} issues matching labels: {', '.join(config.labels)}")

    if not issues_to_process:
        logger.warning("No issues found matching labels.")
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
            issue_md = format_issue_md(issue, converter, config.base_url, config.exclude_fields)
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
